"""
Decompilation Endpoints

Core API endpoints for binary decompilation and LLM translation.
Simplified architecture focusing on decompilation + translation workflow.
"""

import os
import uuid
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
import asyncio
from fastapi.responses import JSONResponse

from ...core.config import get_settings
from ...core.exceptions import (
    BinaryAnalysisException,
    UnsupportedFormatException, 
    ValidationException
)
from ...decompilation.engine import DecompilationEngine
from ...cache.job_queue import JobQueue, JobMetadata
from ...models.shared.enums import JobStatus
from ...core.logging import get_logger
from ...llm.translation_service import get_translation_service


logger = get_logger(__name__)
router = APIRouter()


async def get_decompilation_engine() -> DecompilationEngine:
    """Dependency to get decompilation engine instance."""
    return DecompilationEngine()


async def get_job_queue() -> JobQueue:
    """Dependency to get job queue instance."""
    return JobQueue()


async def process_decompilation_job(job_id: str, file_path: str, analysis_config: Dict[str, Any]):
    """Background task to process decompilation job."""
    job_queue = JobQueue()
    
    try:
        logger.info(f"Background task started for job {job_id}")
        
        # Create decompilation config from analysis parameters
        from ...decompilation.engine import DecompilationConfig
        
        # Map analysis depth to radare2 commands
        analysis_depth = analysis_config.get("analysis_depth", "standard")
        r2_analysis_mapping = {
            "basic": "aa",
            "standard": "aaa", 
            "comprehensive": "aaaa"
        }
        
        decompilation_config = DecompilationConfig(
            r2_analysis_level=r2_analysis_mapping.get(analysis_depth, "aaa"),
            extract_functions=True,
            extract_strings=True,
            extract_imports=True
        )
        
        engine = DecompilationEngine(config=decompilation_config)
        logger.info(f"Starting decompilation job {job_id}")
        
        # Update status to processing
        await job_queue.update_job_status(
            job_id=job_id,
            worker_id="background-worker",
            status=JobStatus.PROCESSING,
            progress_percentage=10.0,
            current_stage="Starting decompilation"
        )
        
        # Perform decompilation
        result = await engine.decompile_binary(file_path)
        
        # Update progress  
        await job_queue.update_job_progress(
            job_id=job_id,
            worker_id="background-worker",
            progress_percentage=70.0,
            current_stage="Decompilation complete, starting LLM translation"
        )
        
        # Perform LLM translation if LLM provider is configured
        if analysis_config.get("llm_provider"):
            logger.info(f"LLM provider found: {analysis_config.get('llm_provider')} for job {job_id}")
            logger.info(f"Functions available for translation: {len(result.functions)} functions")
            try:
                logger.info(f"Starting LLM translation for job {job_id}")
                translation_service = await get_translation_service()
                
                # Create LLM config from analysis parameters
                llm_config = {
                    "llm_provider": analysis_config.get("llm_provider"),
                    "llm_model": analysis_config.get("llm_model"),
                    "llm_endpoint_url": analysis_config.get("llm_endpoint_url"),
                    "llm_api_key": analysis_config.get("llm_api_key"),
                    "translation_detail": analysis_config.get("translation_detail", "standard"),
                    "analysis_depth": analysis_config.get("analysis_depth", "standard")
                }
                
                # Translate the decompilation result
                translation_result = await translation_service.translate_decompilation_result(
                    decompilation_result=result,
                    llm_config=llm_config,
                    context={"job_id": job_id}
                )
                
                # Handle tuple return (result, translation_data) or just result
                if isinstance(translation_result, tuple):
                    result, llm_translations = translation_result
                    logger.info(f"Received LLM translations: {llm_translations is not None}")
                else:
                    result = translation_result
                    llm_translations = None
                    logger.warning("Translation service returned single result (no translations)")
                
                # Update progress after LLM translation
                await job_queue.update_job_progress(
                    job_id=job_id,
                    worker_id="background-worker",
                    progress_percentage=90.0,
                    current_stage="LLM translation complete"
                )
                logger.info(f"Completed LLM translation for job {job_id}")
                
            except Exception as e:
                logger.warning(f"LLM translation failed for job {job_id}: {e}")
                # Continue with original result - translation failure is not critical
                await job_queue.update_job_progress(
                    job_id=job_id,
                    worker_id="background-worker",
                    progress_percentage=90.0,
                    current_stage="LLM translation failed, proceeding with decompilation results"
                )
        else:
            logger.info(f"No LLM provider configured for job {job_id}, skipping translation")
            logger.info(f"Analysis config keys: {list(analysis_config.keys())}")
        
        # Store result (for now, we'll store in job metadata)
        # In production, you might store large results in object storage
        result_summary = {
            "success": result.success,
            "function_count": len(result.functions),
            "import_count": len(result.imports), 
            "string_count": len(result.strings),
            "duration_seconds": result.duration_seconds,
            "decompilation_id": result.decompilation_id
        }
        
        # Include LLM translation data if available
        if 'llm_translations' in locals() and llm_translations is not None:
            logger.info(f"Including LLM translations: {len(llm_translations.get('functions', []))} functions")
            result_summary["llm_translations"] = llm_translations
        else:
            logger.info("No LLM translations to include in result")
        
        # Complete the job and store results
        await job_queue.complete_job(job_id, "background-worker", result_summary)
        
        logger.info(f"Completed decompilation job {job_id}")
        
    except Exception as e:
        logger.error(f"Decompilation job {job_id} failed: {e}", exc_info=True)
        try:
            await job_queue.fail_job(job_id, "background-worker", str(e))
        except Exception as fail_error:
            logger.error(f"Failed to mark job {job_id} as failed: {fail_error}")
    finally:
        # Clean up temporary file
        try:
            import os
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary file {file_path}: {e}")


@router.post("/decompile")
async def submit_decompilation_job(
    file: UploadFile = File(...),
    analysis_depth: str = Form(default="standard"),
    llm_provider: Optional[str] = Form(default=None),
    llm_model: Optional[str] = Form(default=None),
    llm_endpoint_url: Optional[str] = Form(default=None),
    llm_api_key: Optional[str] = Form(default=None),
    translation_detail: str = Form(default="standard"),
    job_queue: JobQueue = Depends(get_job_queue)
):
    """
    Submit a binary file for decompilation and LLM translation.
    
    Uploads a binary file and starts async decompilation with optional
    LLM translation. Returns a job ID for tracking progress.
    
    Args:
        file: Binary file to decompile (PE, ELF, Mach-O, etc.)
        analysis_depth: Decompilation depth (basic, standard, comprehensive)
        llm_provider: LLM provider for translation (openai, anthropic, gemini)
        translation_detail: Translation detail level (basic, standard, detailed)
    
    Returns:
        Job information with tracking ID
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Validate file size
    settings = get_settings()
    content = await file.read()
    if len(content) > settings.analysis.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.analysis.max_file_size_mb}MB"
        )
    
    # Save uploaded file to temporary location
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"upload_{uuid.uuid4().hex}_{file.filename}")
    
    with open(temp_file_path, "wb") as temp_file:
        temp_file.write(content)
    
    # Create analysis configuration
    analysis_config = {
        "analysis_depth": analysis_depth,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_endpoint_url": llm_endpoint_url,
        "llm_api_key": llm_api_key,
        "translation_detail": translation_detail,
        "file_path": temp_file_path
    }
    
    # Enqueue the job
    job_id = await job_queue.enqueue_job(
        file_reference=temp_file_path,
        filename=file.filename,
        analysis_config=analysis_config,
        priority="normal"
    )
    
    # Start background processing with asyncio.create_task
    asyncio.create_task(process_decompilation_job(job_id, temp_file_path, analysis_config))
    
    return JSONResponse(
        status_code=202,  # Accepted for async processing
        content={
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "message": "Decompilation job submitted successfully",
            "file_info": {
                "filename": file.filename,
                "size_bytes": len(content),
                "content_type": file.content_type
            },
            "config": {
                "analysis_depth": analysis_depth,
                "llm_provider": llm_provider,
                "translation_detail": translation_detail
            },
            "estimated_completion": "5-10 minutes",
            "check_status_url": f"/api/v1/decompile/{job_id}"
        }
    )


@router.get("/decompile/test")
async def test_decompilation():
    """Test endpoint for decompilation API."""
    return {"message": "Decompilation API is working"}


@router.get("/decompile/{job_id}")
async def get_decompilation_result(
    job_id: str,
    include_raw_data: bool = False,
    job_queue: JobQueue = Depends(get_job_queue)
):
    """
    Get decompilation job status and results.
    
    Returns job status, progress information, and complete results
    when processing is finished.
    """
    # Get job progress from queue
    progress = await job_queue.get_job_progress(job_id)
    
    if not progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Convert status to clean string (remove enum prefix if present)
    status_str = str(progress.status)
    if "." in status_str:
        status_str = status_str.split(".")[-1]  # Get part after the dot
    status_str = status_str.lower()
    
    response = {
        "job_id": job_id,
        "status": status_str,
        "progress_percentage": progress.progress_percentage,
        "current_stage": progress.current_stage,
        "worker_id": progress.worker_id,
        "updated_at": progress.updated_at
    }
    
    if progress.error_message:
        response["error_message"] = progress.error_message
    
    # If job is completed, try to get results from database/storage
    if "completed" in status_str:
        try:
            from ...database.operations import JobQueue as DatabaseJobQueue
            db_queue = DatabaseJobQueue()
            result_data = await db_queue.get_job_result(job_id)
        except Exception as e:
            logger.error(f"Failed to retrieve result data for job {job_id}: {e}")
            response["message"] = "Decompilation completed but results retrieval failed"
        else:
            if result_data:
                response["results"] = result_data
                response["message"] = "Decompilation completed successfully"
            else:
                response["message"] = "Decompilation completed but results not found"
    elif "failed" in status_str:
        response["message"] = f"Decompilation failed: {progress.error_message or 'Unknown error'}"
    elif "processing" in status_str:
        response["message"] = f"Decompilation in progress: {progress.current_stage or 'Processing...'}"
    else:
        response["message"] = f"Job status: {status_str}"
    
    return response



@router.delete("/decompile/{job_id}")
async def cancel_decompilation_job(
    job_id: str, 
    job_queue: JobQueue = Depends(get_job_queue)
):
    """
    Cancel a pending or in-progress decompilation job.
    
    Only jobs that are pending or in early processing stages can be cancelled.
    """
    # First check if job exists
    progress = await job_queue.get_job_progress(job_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if job can be cancelled (not already terminal)
    status_str = str(progress.status).lower()
    if "." in status_str:
        status_str = status_str.split(".")[-1]
    
    if status_str in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in {status_str} state")
    
    success = await job_queue.cancel_job(job_id)
    
    if success:
        return {"message": f"Job {job_id} cancelled successfully"}
    else:
        raise HTTPException(status_code=400, detail="Job could not be cancelled")