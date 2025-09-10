"""
API Routes

FastAPI routers for binary decompilation and LLM translation endpoints.
Simplified architecture focused on decompilation + translation workflow.
"""

from . import (
    admin,
    dashboard, 
    decompilation,
    health,
    llm_providers,
    user_llm_providers
)