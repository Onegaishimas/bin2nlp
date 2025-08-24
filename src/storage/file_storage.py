"""
Simple file-based storage as Redis alternative.

Provides equivalent functionality with just the filesystem:
- Job results stored as JSON files
- Simple, portable, no external dependencies
- Works in any environment with filesystem access
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

from ..core.logging import get_logger

logger = get_logger(__name__)


class FileStorage:
    """Simple file-based storage for job results and metadata."""
    
    def __init__(self, base_path: str = "/tmp/bin2nlp_data"):
        """Initialize file storage with base directory."""
        self.base_path = Path(base_path)
        self.results_dir = self.base_path / "results"
        self.jobs_dir = self.base_path / "jobs" 
        
        # Create directories
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"FileStorage initialized at {self.base_path}")
    
    async def set_result(self, job_id: str, result_data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Store job result as JSON file."""
        try:
            result_file = self.results_dir / f"{job_id}.json"
            
            # Add expiration timestamp
            result_with_meta = {
                "data": result_data,
                "stored_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
            }
            
            # Write JSON file
            with open(result_file, 'w') as f:
                json.dump(result_with_meta, f, indent=2)
            
            logger.info(f"Stored result for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store result for job {job_id}: {e}")
            return False
    
    async def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job result from JSON file."""
        try:
            result_file = self.results_dir / f"{job_id}.json"
            
            if not result_file.exists():
                return None
            
            # Read JSON file
            with open(result_file, 'r') as f:
                stored_data = json.load(f)
            
            # Check expiration
            expires_at = datetime.fromisoformat(stored_data["expires_at"])
            if datetime.utcnow() > expires_at:
                # File expired, delete it
                result_file.unlink()
                logger.info(f"Result for job {job_id} expired and removed")
                return None
            
            return stored_data["data"]
            
        except Exception as e:
            logger.error(f"Failed to retrieve result for job {job_id}: {e}")
            return None
    
    async def cleanup_expired(self) -> int:
        """Clean up expired result files."""
        cleaned_count = 0
        try:
            for result_file in self.results_dir.glob("*.json"):
                try:
                    with open(result_file, 'r') as f:
                        stored_data = json.load(f)
                    
                    expires_at = datetime.fromisoformat(stored_data["expires_at"])
                    if datetime.utcnow() > expires_at:
                        result_file.unlink()
                        cleaned_count += 1
                        
                except Exception as e:
                    logger.warning(f"Error checking expiration for {result_file}: {e}")
                    
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired result files")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        return cleaned_count
    
    async def list_results(self) -> List[str]:
        """List all available result job IDs."""
        try:
            job_ids = []
            for result_file in self.results_dir.glob("*.json"):
                job_id = result_file.stem
                # Check if not expired
                result = await self.get_result(job_id)
                if result is not None:
                    job_ids.append(job_id)
            return job_ids
        except Exception as e:
            logger.error(f"Error listing results: {e}")
            return []


# Global instance
_file_storage = None

def get_file_storage() -> FileStorage:
    """Get global file storage instance."""
    global _file_storage
    if _file_storage is None:
        _file_storage = FileStorage()
    return _file_storage