"""
Database operations for the hybrid PostgreSQL + File Storage system.
"""

import asyncio
import json
import time
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from .connection import get_database, safe_execute, DatabaseTransaction
from .models import (
    Job, CacheEntry, RateLimit, Session, SystemStat, WorkerHeartbeat,
    JobPriority, RateLimitScope, JobQueueStats, CachePerformance
)
from ..models.shared.enums import JobStatus
from ..cache.base import FileStorageClient, get_file_storage_client
from ..core.logging import get_logger
from ..core.exceptions import ProcessingException, CacheException


def compute_file_hash(file_path: str) -> str:
    """
    Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA256 hash as hex string
    """
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        # Fallback to a hash of the filename if file reading fails
        return hashlib.sha256(file_path.encode()).hexdigest()


class JobQueue:
    """
    Hybrid PostgreSQL + File Storage job queue.
    
    Uses PostgreSQL for job metadata, queuing, and state management.
    Uses file storage for large result payloads.
    """
    
    def __init__(self, file_storage: Optional[FileStorageClient] = None):
        self.file_storage = file_storage
        self.logger = get_logger(__name__)
    
    async def _get_storage(self) -> FileStorageClient:
        """Get file storage client."""
        if self.file_storage is None:
            self.file_storage = await get_file_storage_client()
        return self.file_storage
    
    async def enqueue_job(
        self,
        file_reference: str,
        filename: str,
        analysis_config: Dict[str, Any],
        priority: str = "normal",
        callback_url: Optional[str] = None,
        submitted_by: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a job to the queue.
        
        Args:
            file_reference: Reference to uploaded file
            filename: Original filename
            analysis_config: Analysis configuration
            priority: Job priority (low, normal, high, urgent)
            callback_url: Optional webhook URL
            submitted_by: API key or user identifier
            correlation_id: Request correlation ID
            metadata: Additional job metadata
            
        Returns:
            Job ID
        """
        try:
            # Validate priority
            if priority not in [p for p in JobPriority]:
                raise ProcessingException(f"Invalid priority: {priority}")
            
            # Compute proper file hash
            file_hash = compute_file_hash(file_reference)
            
            # Create job instance
            job = Job(
                file_hash=file_hash,
                filename=filename,
                file_reference=file_reference,
                analysis_config=analysis_config,
                priority=JobPriority(priority),
                submitted_by=submitted_by,
                callback_url=callback_url,
                correlation_id=correlation_id,
                metadata=metadata or {}
            )
            
            # Insert into database
            db = await get_database()
            
            query = """
                INSERT INTO jobs (
                    id, status, priority, file_hash, filename, file_reference,
                    analysis_config, submitted_by, callback_url, correlation_id,
                    metadata, created_at, updated_at
                ) VALUES (
                    :id, :status, :priority, :file_hash, :filename, :file_reference,
                    :analysis_config, :submitted_by, :callback_url, :correlation_id,
                    :metadata, :created_at, :updated_at
                )
            """
            
            await db.execute(query, {
                'id': str(job.id),
                'status': job.status,
                'priority': job.priority,
                'file_hash': job.file_hash,
                'filename': job.filename,
                'file_reference': job.file_reference,
                'analysis_config': json.dumps(job.analysis_config),
                'submitted_by': job.submitted_by,
                'callback_url': job.callback_url,
                'correlation_id': job.correlation_id,
                'metadata': json.dumps(job.metadata),
                'created_at': job.created_at,
                'updated_at': job.updated_at
            })
            
            # Update statistics
            await self._update_stat("jobs_total", 1)
            
            self.logger.info(
                "Job enqueued successfully",
                extra={
                    "job_id": str(job.id),
                    "priority": job.priority,
                    "filename": filename,
                    "submitted_by": submitted_by
                }
            )
            
            return str(job.id)
            
        except Exception as e:
            self.logger.error(
                "Failed to enqueue job",
                extra={"error": str(e), "filename": filename}
            )
            raise ProcessingException(f"Failed to enqueue job: {e}")
    
    async def dequeue_job(self, worker_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Atomically dequeue the next highest priority job.
        
        Args:
            worker_id: Unique worker identifier
            
        Returns:
            Tuple of (job_id, job_data) or None if no jobs available
        """
        try:
            db = await get_database()
            
            # Use the stored function for atomic dequeue
            result = await db.fetch_one(
                "SELECT * FROM dequeue_next_job(:worker_id)",
                {"worker_id": worker_id}
            )
            
            if not result:
                return None
            
            job_data = {
                'job_id': str(result['job_id']),
                'file_hash': result['file_hash'],
                'filename': result['filename'],
                'file_reference': result['file_reference'],
                'analysis_config': result['analysis_config'],
                'priority': result['priority'],
                'metadata': result['metadata']
            }
            
            self.logger.info(
                "Job dequeued successfully",
                extra={
                    "job_id": str(result['job_id']),
                    "worker_id": worker_id,
                    "priority": result['priority']
                }
            )
            
            return str(result['job_id']), job_data
            
        except Exception as e:
            self.logger.error(
                "Failed to dequeue job",
                extra={"error": str(e), "worker_id": worker_id}
            )
            return None
    
    async def complete_job(self, job_id: str, worker_id: str, result_data: Any) -> bool:
        """
        Mark job as completed and store result.
        
        Args:
            job_id: Job ID
            worker_id: Worker ID
            result_data: Job result data
            
        Returns:
            True if successful
        """
        try:
            # Store result data in file storage
            storage = await self._get_storage()
            result_file_path = f"results/{job_id}.json"
            
            success = await storage.set(result_file_path, result_data)
            if not success:
                raise Exception("Failed to store result data")
            
            # Update job status in database
            db = await get_database()
            
            query = """
                UPDATE jobs 
                SET status = 'completed',
                    result_file_path = :result_file_path,
                    completed_at = NOW(),
                    updated_at = NOW(),
                    progress_percentage = 100.0,
                    processing_time_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
                WHERE id = :job_id AND worker_id = :worker_id
            """
            
            rows_updated = await db.execute(query, {
                'job_id': job_id,
                'worker_id': worker_id,
                'result_file_path': result_file_path
            })
            
            if rows_updated == 0:
                self.logger.warning(
                    "Job not found or worker mismatch",
                    extra={"job_id": job_id, "worker_id": worker_id}
                )
                return False
            
            # Update statistics
            await self._update_stat("jobs_completed", 1)
            
            self.logger.info(
                "Job completed successfully",
                extra={
                    "job_id": job_id,
                    "worker_id": worker_id,
                    "result_file_path": result_file_path
                }
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to complete job",
                extra={"error": str(e), "job_id": job_id, "worker_id": worker_id}
            )
            return False
    
    async def fail_job(self, job_id: str, worker_id: str, error_message: str) -> bool:
        """
        Mark job as failed.
        
        Args:
            job_id: Job ID
            worker_id: Worker ID
            error_message: Error description
            
        Returns:
            True if successful
        """
        try:
            db = await get_database()
            
            query = """
                UPDATE jobs 
                SET status = 'failed',
                    error_message = :error_message,
                    completed_at = NOW(),
                    updated_at = NOW(),
                    processing_time_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
                WHERE id = :job_id AND worker_id = :worker_id
            """
            
            rows_updated = await db.execute(query, {
                'job_id': job_id,
                'worker_id': worker_id,
                'error_message': error_message
            })
            
            if rows_updated == 0:
                return False
            
            # Update statistics
            await self._update_stat("jobs_failed", 1)
            
            self.logger.info(
                "Job marked as failed",
                extra={"job_id": job_id, "worker_id": worker_id, "error": error_message}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to mark job as failed",
                extra={"error": str(e), "job_id": job_id}
            )
            return False
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and metadata."""
        try:
            db = await get_database()
            
            result = await db.fetch_one(
                "SELECT * FROM jobs WHERE id = :job_id",
                {"job_id": job_id}
            )
            
            if not result:
                return None
            
            job_data = dict(result)
            
            # Parse JSON fields
            if job_data.get('analysis_config'):
                job_data['analysis_config'] = json.loads(job_data['analysis_config'])
            if job_data.get('metadata'):
                job_data['metadata'] = json.loads(job_data['metadata'])
            
            return job_data
            
        except Exception as e:
            self.logger.error(
                "Failed to get job status",
                extra={"error": str(e), "job_id": job_id}
            )
            return None
    
    async def get_job_result(self, job_id: str) -> Optional[Any]:
        """Get job result from file storage."""
        try:
            # First get the result file path from database
            job_status = await self.get_job_status(job_id)
            if not job_status or not job_status.get('result_file_path'):
                return None
            
            # Get result from file storage
            storage = await self._get_storage()
            result_data = await storage.get(job_status['result_file_path'])
            
            return result_data
            
        except Exception as e:
            self.logger.error(
                "Failed to get job result",
                extra={"error": str(e), "job_id": job_id}
            )
            return None
    
    async def update_job_progress(
        self,
        job_id: str,
        worker_id: str,
        progress_percentage: float,
        current_stage: Optional[str] = None,
        estimated_completion_seconds: Optional[int] = None
    ) -> bool:
        """Update job progress."""
        try:
            db = await get_database()
            
            query = """
                UPDATE jobs 
                SET progress_percentage = :progress_percentage,
                    current_stage = :current_stage,
                    estimated_completion_seconds = :estimated_completion_seconds,
                    updated_at = NOW()
                WHERE id = :job_id
            """
            
            rows_updated = await db.execute(query, {
                'job_id': job_id,
                'progress_percentage': progress_percentage,
                'current_stage': current_stage,
                'estimated_completion_seconds': estimated_completion_seconds
            })
            
            return (rows_updated or 0) > 0
            
        except Exception as e:
            self.logger.error(
                "Failed to update job progress",
                extra={"error": str(e), "job_id": job_id}
            )
            return False
    
    async def update_job_status(
        self,
        job_id: str,
        worker_id: str,
        status: str,
        progress_percentage: Optional[float] = None,
        current_stage: Optional[str] = None,
        estimated_completion_seconds: Optional[int] = None
    ) -> bool:
        """Update job status and optionally progress."""
        try:
            db = await get_database()
            
            # Build dynamic query based on provided parameters
            update_fields = ["status = :status", "worker_id = :worker_id", "updated_at = NOW()"]
            params = {"job_id": job_id, "worker_id": worker_id, "status": status}
            
            if progress_percentage is not None:
                update_fields.append("progress_percentage = :progress_percentage")
                params["progress_percentage"] = progress_percentage
            
            if current_stage is not None:
                update_fields.append("current_stage = :current_stage")
                params["current_stage"] = current_stage
                
            if estimated_completion_seconds is not None:
                update_fields.append("estimated_completion_seconds = :estimated_completion_seconds")
                params["estimated_completion_seconds"] = estimated_completion_seconds
            
            query = f"""
                UPDATE jobs 
                SET {', '.join(update_fields)}
                WHERE id = :job_id
            """
            
            rows_updated = await db.execute(query, params)
            
            return (rows_updated or 0) > 0
            
        except Exception as e:
            self.logger.error(
                "Failed to update job status",
                extra={"error": str(e), "job_id": job_id, "status": status}
            )
            return False
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get job queue statistics."""
        try:
            db = await get_database()
            
            # Get queue stats from view
            queue_stats = await db.fetch_all("SELECT * FROM job_queue_stats")
            
            # Convert to list of dictionaries
            stats_data = []
            for row in queue_stats:
                stats_data.append(dict(row))
            
            # Get overall counts
            total_counts = await db.fetch_one("""
                SELECT 
                    COUNT(*) as total_jobs,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_jobs,
                    COUNT(*) FILTER (WHERE status = 'in_progress') as active_jobs,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_jobs,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs
                FROM jobs
            """)
            
            return {
                'queue_breakdown': stats_data,
                'totals': dict(total_counts) if total_counts else {},
                'timestamp': time.time()
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get queue stats",
                extra={"error": str(e)}
            )
            return {}
    
    async def _update_stat(self, stat_key: str, increment: int = 1) -> None:
        """Update system statistics."""
        try:
            db = await get_database()
            
            query = """
                INSERT INTO system_stats (stat_key, stat_value)
                VALUES (:stat_key, :increment)
                ON CONFLICT (stat_key)
                DO UPDATE SET 
                    stat_value = system_stats.stat_value + :increment,
                    updated_at = NOW()
            """
            
            await db.execute(query, {
                'stat_key': stat_key,
                'increment': increment
            })
            
        except Exception:
            # Don't fail operations due to stats errors
            pass


class ResultCache:
    """
    Hybrid PostgreSQL + File Storage result cache.
    
    Uses PostgreSQL for cache metadata and indexing.
    Uses file storage for actual cache data.
    """
    
    def __init__(self, file_storage: Optional[FileStorageClient] = None):
        self.file_storage = file_storage
        self.logger = get_logger(__name__)
        self.cache_version = "1.0"
    
    async def _get_storage(self) -> FileStorageClient:
        """Get file storage client."""
        if self.file_storage is None:
            self.file_storage = await get_file_storage_client()
        return self.file_storage
    
    async def get(self, cache_key: str) -> Optional[Any]:
        """Get cached data."""
        try:
            db = await get_database()
            
            # Get cache metadata
            cache_meta = await db.fetch_one("""
                SELECT * FROM cache_entries 
                WHERE cache_key = :cache_key 
                AND expires_at > NOW()
            """, {"cache_key": cache_key})
            
            if not cache_meta:
                await self._update_stat("cache_misses", 1)
                return None
            
            # Get data from file storage
            storage = await self._get_storage()
            cache_data = await storage.get(cache_meta['file_path'])
            
            if cache_data is None:
                # File missing, clean up metadata
                await db.execute(
                    "DELETE FROM cache_entries WHERE cache_key = :cache_key",
                    {"cache_key": cache_key}
                )
                await self._update_stat("cache_misses", 1)
                return None
            
            # Update access statistics
            await db.execute("""
                UPDATE cache_entries 
                SET access_count = access_count + 1,
                    last_accessed = NOW()
                WHERE cache_key = :cache_key
            """, {"cache_key": cache_key})
            
            await self._update_stat("cache_hits", 1)
            
            return cache_data
            
        except Exception as e:
            self.logger.error(
                "Failed to get cached data",
                extra={"error": str(e), "cache_key": cache_key}
            )
            return None
    
    async def set(
        self,
        cache_key: str,
        data: Any,
        ttl_seconds: int = 86400,  # 24 hours default
        file_hash: Optional[str] = None,
        config_hash: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set cached data."""
        try:
            # Store data in file storage
            storage = await self._get_storage()
            file_path = f"cache/{cache_key}.json"
            
            success = await storage.set(file_path, data)
            if not success:
                return False
            
            # Store metadata in database
            db = await get_database()
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            
            # Calculate data size
            data_size = len(json.dumps(data, default=str))
            
            query = """
                INSERT INTO cache_entries (
                    cache_key, file_hash, config_hash, file_path,
                    cache_version, tags, expires_at, data_size_bytes
                ) VALUES (
                    :cache_key, :file_hash, :config_hash, :file_path,
                    :cache_version, :tags, :expires_at, :data_size_bytes
                )
                ON CONFLICT (cache_key) 
                DO UPDATE SET
                    file_path = EXCLUDED.file_path,
                    expires_at = EXCLUDED.expires_at,
                    data_size_bytes = EXCLUDED.data_size_bytes,
                    cache_version = EXCLUDED.cache_version,
                    tags = EXCLUDED.tags
            """
            
            await db.execute(query, {
                'cache_key': cache_key,
                'file_hash': file_hash or '',
                'config_hash': config_hash or '',
                'file_path': file_path,
                'cache_version': self.cache_version,
                'tags': tags or [],
                'expires_at': expires_at,
                'data_size_bytes': data_size
            })
            
            await self._update_stat("cache_sets", 1)
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to set cached data",
                extra={"error": str(e), "cache_key": cache_key}
            )
            return False
    
    async def delete(self, cache_key: str) -> bool:
        """Delete cached data."""
        try:
            db = await get_database()
            
            # Get file path first
            cache_meta = await db.fetch_one(
                "SELECT file_path FROM cache_entries WHERE cache_key = :cache_key",
                {"cache_key": cache_key}
            )
            
            if cache_meta:
                # Delete from file storage
                storage = await self._get_storage()
                await storage.delete(cache_meta['file_path'])
                
                # Delete from database
                await db.execute(
                    "DELETE FROM cache_entries WHERE cache_key = :cache_key",
                    {"cache_key": cache_key}
                )
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(
                "Failed to delete cached data",
                extra={"error": str(e), "cache_key": cache_key}
            )
            return False
    
    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        try:
            db = await get_database()
            
            # Get expired entries
            expired_entries = await db.fetch_all(
                "SELECT file_path FROM cache_entries WHERE expires_at < NOW()"
            )
            
            if not expired_entries:
                return 0
            
            # Delete files from storage
            storage = await self._get_storage()
            for entry in expired_entries:
                try:
                    await storage.delete(entry['file_path'])
                except:
                    pass  # Continue cleanup even if some files fail
            
            # Delete from database
            deleted_count = await db.execute(
                "DELETE FROM cache_entries WHERE expires_at < NOW()"
            )
            
            self.logger.info(
                "Cleaned up expired cache entries",
                extra={"deleted_count": deleted_count}
            )
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup expired cache",
                extra={"error": str(e)}
            )
            return 0
    
    async def _update_stat(self, stat_key: str, increment: int = 1) -> None:
        """Update cache statistics."""
        try:
            db = await get_database()
            
            query = """
                INSERT INTO system_stats (stat_key, stat_value)
                VALUES (:stat_key, :increment)
                ON CONFLICT (stat_key)
                DO UPDATE SET 
                    stat_value = system_stats.stat_value + :increment,
                    updated_at = NOW()
            """
            
            await db.execute(query, {
                'stat_key': stat_key,
                'increment': increment
            })
            
        except Exception:
            pass


class RateLimiter:
    """PostgreSQL-based rate limiting."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def check_rate_limit(
        self,
        identifier: str,
        scope: str = "api_key",
        window_seconds: int = 60,
        max_requests: int = 100
    ) -> bool:
        """
        Check if request is within rate limit.
        
        Args:
            identifier: API key, IP address, etc.
            scope: Rate limit scope (api_key, ip_address, global)
            window_seconds: Time window in seconds
            max_requests: Maximum requests in window
            
        Returns:
            True if within limit, False if exceeded
        """
        try:
            db = await get_database()
            
            # Use the stored function for atomic rate limit check
            result = await db.fetch_val("""
                SELECT check_rate_limit(
                    :scope::rate_limit_scope, 
                    :identifier, 
                    :window_seconds, 
                    :max_requests
                )
            """, {
                'scope': scope,
                'identifier': identifier,
                'window_seconds': window_seconds,
                'max_requests': max_requests
            })
            
            if result:
                await self._update_stat("rate_limit_hits", 1)
            else:
                await self._update_stat("rate_limit_blocks", 1)
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Rate limit check failed",
                extra={"error": str(e), "identifier": identifier}
            )
            # Default to allowing on error
            return True
    
    async def _update_stat(self, stat_key: str, increment: int = 1) -> None:
        """Update rate limit statistics."""
        try:
            db = await get_database()
            
            query = """
                INSERT INTO system_stats (stat_key, stat_value)
                VALUES (:stat_key, :increment)
                ON CONFLICT (stat_key)
                DO UPDATE SET 
                    stat_value = system_stats.stat_value + :increment,
                    updated_at = NOW()
            """
            
            await db.execute(query, {
                'stat_key': stat_key,
                'increment': increment
            })
            
        except Exception:
            pass


class SessionManager:
    """PostgreSQL-based session management."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def create_session(
        self,
        session_key: str,
        session_data: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
        api_key_hash: Optional[str] = None,
        user_tier: str = "basic"
    ) -> bool:
        """Create a new session."""
        try:
            db = await get_database()
            
            expires_at = None
            if ttl_seconds:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            
            query = """
                INSERT INTO sessions (
                    session_key, session_data, api_key_hash, user_tier, expires_at
                ) VALUES (
                    :session_key, :session_data, :api_key_hash, :user_tier, :expires_at
                )
                ON CONFLICT (session_key)
                DO UPDATE SET
                    session_data = EXCLUDED.session_data,
                    last_accessed = NOW(),
                    expires_at = EXCLUDED.expires_at
            """
            
            await db.execute(query, {
                'session_key': session_key,
                'session_data': json.dumps(session_data),
                'api_key_hash': api_key_hash,
                'user_tier': user_tier,
                'expires_at': expires_at
            })
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to create session",
                extra={"error": str(e), "session_key": session_key}
            )
            return False
    
    async def get_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        try:
            db = await get_database()
            
            result = await db.fetch_one("""
                SELECT * FROM sessions 
                WHERE session_key = :session_key 
                AND (expires_at IS NULL OR expires_at > NOW())
            """, {"session_key": session_key})
            
            if not result:
                return None
            
            # Update last accessed
            await db.execute("""
                UPDATE sessions 
                SET last_accessed = NOW() 
                WHERE session_key = :session_key
            """, {"session_key": session_key})
            
            session_data = dict(result)
            if session_data.get('session_data'):
                session_data['session_data'] = json.loads(session_data['session_data'])
            
            return session_data
            
        except Exception as e:
            self.logger.error(
                "Failed to get session",
                extra={"error": str(e), "session_key": session_key}
            )
            return None
    
    async def delete_session(self, session_key: str) -> bool:
        """Delete a session."""
        try:
            db = await get_database()
            
            rows_deleted = await db.execute(
                "DELETE FROM sessions WHERE session_key = :session_key",
                {"session_key": session_key}
            )
            
            return rows_deleted > 0
            
        except Exception as e:
            self.logger.error(
                "Failed to delete session",
                extra={"error": str(e), "session_key": session_key}
            )
            return False