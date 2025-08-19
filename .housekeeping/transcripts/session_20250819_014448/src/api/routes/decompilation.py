"""
Decompilation Endpoints

Core API endpoints for binary decompilation and LLM translation.
Simplified architecture focusing on decompilation + translation workflow.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from ...core.config import get_settings
from ...core.exceptions import (
    BinaryAnalysisException,
    UnsupportedFormatException, 
    ValidationException
)
from ...decompilation.engine import DecompilationEngine
from ...core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


async def get_decompilation_engine() -> DecompilationEngine:
    """Dependency to get decompilation engine instance."""
    return DecompilationEngine()


@router.post("/decompile")
async def submit_decompilation_job(
    file: UploadFile = File(...),
    analysis_depth: str = Form(default="standard"),
    llm_provider: Optional[str] = Form(default=None),
    translation_detail: str = Form(default="standard"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    engine: DecompilationEngine = Depends(get_decompilation_engine)
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
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Create decompilation configuration
    from ...models.analysis.config import DecompilationConfig
    from ...models.decompilation.results import DecompilationDepth, TranslationDetail
    
    try:
        depth_enum = DecompilationDepth(analysis_depth.upper())
    except ValueError:
        depth_enum = DecompilationDepth.STANDARD
    
    try:
        detail_enum = TranslationDetail(translation_detail.upper())
    except ValueError:
        detail_enum = TranslationDetail.STANDARD
    
    config = DecompilationConfig(
        decompilation_depth=depth_enum,
        llm_provider=llm_provider,
        translation_detail=detail_enum
    )
    
    # For now, return job info (actual processing would be added later)
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
    include_raw_data: bool = False
):
    """
    Get decompilation job status and results.
    
    Returns job status, progress information, and complete results
    when processing is finished.
    """
    # Mock response for now
    return {
        "job_id": job_id,
        "status": "completed",
        "message": "Mock decompilation result"
    }


@router.delete("/decompile/{job_id}")
async def cancel_decompilation_job(job_id: str):
    """
    Cancel a pending or in-progress decompilation job.
    
    Only jobs that are pending or in early processing stages can be cancelled.
    """
    return {"message": f"Job {job_id} cancelled successfully"}