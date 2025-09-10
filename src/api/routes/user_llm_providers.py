"""
API routes for user LLM provider management.

Provides CRUD operations for user-configured LLM providers with secure
API key handling and comprehensive error management.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query

from ...models.api.user_llm_providers import (
    UserLLMProviderCreate,
    UserLLMProviderUpdate,
    UserLLMProviderResponse,
    UserLLMProviderListResponse,
    ProviderTestRequest,
    ProviderTestResult,
    ProviderTypesResponse,
    ErrorResponse,
    convert_provider_to_response,
    get_provider_types_info
)
from ...repositories.user_llm_providers import user_llm_provider_repository
from ...llm.base import LLMProviderType
from ...core.logging import get_logger
from ...core.exceptions import ValidationException

logger = get_logger(__name__)

# Create router
router = APIRouter(
    prefix="/user-llm-providers",
    tags=["User LLM Providers"],
    responses={
        404: {"model": ErrorResponse, "description": "Provider not found"},
        422: {"description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)


@router.get(
    "/types",
    response_model=ProviderTypesResponse,
    summary="Get available provider types",
    description="Get information about all available LLM provider types and their configuration requirements"
)
async def get_provider_types() -> ProviderTypesResponse:
    """Get available provider types with configuration requirements."""
    try:
        provider_types = get_provider_types_info()
        
        logger.debug(
            "Retrieved provider types",
            extra={"count": len(provider_types)}
        )
        
        return ProviderTypesResponse(provider_types=provider_types)
        
    except Exception as e:
        logger.error("Failed to get provider types", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider types"
        )


@router.get(
    "",
    response_model=UserLLMProviderListResponse,
    summary="List user LLM providers",
    description="Get all user-configured LLM providers with optional filtering"
)
async def list_providers(
    active_only: bool = Query(False, description="Only return active providers"),
    provider_type: Optional[LLMProviderType] = Query(None, description="Filter by provider type")
) -> UserLLMProviderListResponse:
    """List all user LLM providers with optional filtering."""
    try:
        providers = await user_llm_provider_repository.get_all_providers(
            active_only=active_only,
            provider_type=provider_type
        )
        
        # Convert to response models
        provider_responses = [convert_provider_to_response(p) for p in providers]
        active_count = sum(1 for p in providers if p.is_active)
        
        # Bulletproof provider_type access for logging
        provider_type_str = None
        if provider_type:
            try:
                if hasattr(provider_type, 'value'):
                    provider_type_str = str(provider_type)
                else:
                    provider_type_str = str(provider_type)
            except (AttributeError, Exception):
                provider_type_str = str(provider_type)
        
        logger.info(
            "Listed user LLM providers",
            extra={
                "total_count": len(providers),
                "active_count": active_count,
                "active_only": active_only,
                "provider_type": provider_type_str
            }
        )
        
        return UserLLMProviderListResponse(
            providers=provider_responses,
            total=len(providers),
            active_count=active_count
        )
        
    except Exception as e:
        logger.error("Failed to list providers", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve providers"
        )


@router.post(
    "",
    response_model=UserLLMProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user LLM provider",
    description="Create a new user-configured LLM provider with encrypted API key storage"
)
async def create_provider(
    provider_data: UserLLMProviderCreate
) -> UserLLMProviderResponse:
    """Create a new user LLM provider."""
    try:
        # Debug the incoming provider_data
        logger.info(
            "DEBUG create_provider route - received request data",
            extra={
                "provider_name": provider_data.name,
                "provider_type": provider_data.provider_type,
                "provider_type_type": type(provider_data.provider_type).__name__,
                "provider_type_str": str(provider_data.provider_type),
                "provider_type_has_value": hasattr(provider_data.provider_type, 'value'),
                "provider_type_value": getattr(provider_data.provider_type, 'value', None) if hasattr(provider_data.provider_type, 'value') else None
            }
        )
        # Check for duplicate names
        existing = await user_llm_provider_repository.get_provider_by_name(provider_data.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Provider with name '{provider_data.name}' already exists"
            )
        
        # Create provider
        provider = await user_llm_provider_repository.create_provider(
            name=provider_data.name,
            provider_type=provider_data.provider_type,
            api_key=provider_data.api_key,
            endpoint_url=provider_data.endpoint_url,
            config_json=provider_data.config_json
        )
        
        response = convert_provider_to_response(provider)
        
        logger.info(
            "Created user LLM provider",
            extra={
                "provider_id": response.id,
                "provider_name": response.name,
                "provider_type": response.provider_type
            }
        )
        
        return response
        
    except ValidationException as e:
        logger.warning(
            "Provider creation validation failed",
            extra={"error": str(e), "provider_name": provider_data.name}
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to create provider",
            extra={"error": str(e), "provider_name": provider_data.name}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create provider"
        )


@router.get(
    "/{provider_id}",
    response_model=UserLLMProviderResponse,
    summary="Get user LLM provider",
    description="Get a specific user LLM provider by ID"
)
async def get_provider(provider_id: str) -> UserLLMProviderResponse:
    """Get a specific user LLM provider by ID."""
    try:
        # Validate UUID format
        try:
            provider_uuid = uuid.UUID(provider_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid provider ID format"
            )
        
        provider = await user_llm_provider_repository.get_provider_by_id(provider_uuid)
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        response = convert_provider_to_response(provider)
        
        logger.debug(
            "Retrieved user LLM provider",
            extra={"provider_id": provider_id, "provider_name": response.name}
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get provider",
            extra={"provider_id": provider_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider"
        )


@router.put(
    "/{provider_id}",
    response_model=UserLLMProviderResponse,
    summary="Update user LLM provider",
    description="Update a user LLM provider's configuration"
)
async def update_provider(
    provider_id: str,
    provider_data: UserLLMProviderUpdate
) -> UserLLMProviderResponse:
    """Update a user LLM provider."""
    try:
        # Validate UUID format
        try:
            provider_uuid = uuid.UUID(provider_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid provider ID format"
            )
        
        # Check if provider exists
        existing = await user_llm_provider_repository.get_provider_by_id(provider_uuid)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        # Check for name conflicts (if name is being updated)
        if provider_data.name and provider_data.name != existing.name:
            name_conflict = await user_llm_provider_repository.get_provider_by_name(provider_data.name)
            if name_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Provider with name '{provider_data.name}' already exists"
                )
        
        # Update provider
        updated_provider = await user_llm_provider_repository.update_provider(
            provider_id=provider_uuid,
            name=provider_data.name,
            api_key=provider_data.api_key,
            endpoint_url=provider_data.endpoint_url,
            config_json=provider_data.config_json,
            is_active=provider_data.is_active
        )
        
        if not updated_provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        response = convert_provider_to_response(updated_provider)
        
        logger.info(
            "Updated user LLM provider",
            extra={
                "provider_id": provider_id,
                "provider_name": response.name,
                "updated_fields": len([f for f in [
                    provider_data.name, provider_data.api_key, provider_data.endpoint_url,
                    provider_data.config_json, provider_data.is_active
                ] if f is not None])
            }
        )
        
        return response
        
    except ValidationException as e:
        logger.warning(
            "Provider update validation failed",
            extra={"error": str(e), "provider_id": provider_id}
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update provider",
            extra={"provider_id": provider_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update provider"
        )


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user LLM provider",
    description="Delete a user LLM provider"
)
async def delete_provider(provider_id: str):
    """Delete a user LLM provider."""
    try:
        # Validate UUID format
        try:
            provider_uuid = uuid.UUID(provider_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid provider ID format"
            )
        
        # Check if provider exists
        existing = await user_llm_provider_repository.get_provider_by_id(provider_uuid)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        # Delete provider
        deleted = await user_llm_provider_repository.delete_provider(provider_uuid)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        logger.info(
            "Deleted user LLM provider",
            extra={
                "provider_id": provider_id,
                "provider_name": existing.name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete provider",
            extra={"provider_id": provider_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete provider"
        )


@router.post(
    "/{provider_id}/test",
    response_model=ProviderTestResult,
    summary="Test provider connectivity",
    description="Test connectivity and configuration of a user LLM provider"
)
async def test_provider(
    provider_id: str,
    test_data: ProviderTestRequest = None
) -> ProviderTestResult:
    """Test provider connectivity."""
    try:
        # Validate UUID format
        try:
            provider_uuid = uuid.UUID(provider_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid provider ID format"
            )
        
        # Check if provider exists (bypass Pydantic validation for now)
        from ...database.connection import get_database
        db = await get_database()
        query = "SELECT * FROM user_llm_providers WHERE id = :id"
        result = await db.fetch_one(query, {"id": provider_uuid})
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        # Extract provider data directly from database result
        result_dict = dict(result)
        provider_name = result_dict.get('name', 'Unknown Provider')
        provider_type_raw = result_dict.get('provider_type', 'unknown')
        endpoint_url = result_dict.get('endpoint_url')
        
        # Convert provider_type to string safely
        provider_type_str = str(provider_type_raw)
        
        # Test provider connectivity
        test_result = await user_llm_provider_repository.test_provider_connectivity(provider_uuid)
        
        logger.info(
            "Tested user LLM provider connectivity",
            extra={
                "provider_id": provider_id,
                "provider_name": provider_name,
                "test_success": test_result.get("success", False)
            }
        )
        
        return ProviderTestResult(
            success=test_result.get("success", False),
            message=test_result.get("message", "Test completed"),
            latency_ms=test_result.get("latency_ms"),
            provider_info=test_result.get("provider_info", {
                "provider_type": provider_type_str,
                "endpoint_url": endpoint_url
            })
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to test provider",
            extra={"provider_id": provider_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test provider connectivity"
        )