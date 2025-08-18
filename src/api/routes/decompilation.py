"""
Decompilation Endpoints

Core API endpoints for binary decompilation and LLM translation.
Simplified architecture focusing on decompilation + translation workflow.
"""

import logging
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


logger = logging.getLogger(__name__)
router = APIRouter()


async def get_decompilation_engine() -> DecompilationEngine:
    """Dependency to get decompilation engine instance."""
    return DecompilationEngine()


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