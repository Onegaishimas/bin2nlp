"""
Authentication Middleware

API key-based authentication for production deployment with
support for different access tiers and usage tracking.
"""

import hashlib
import hmac
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ...core.config import get_settings
from ...core.logging import get_logger
from ...cache.base import get_redis_client

logger = get_logger(__name__)

# API key security scheme for OpenAPI documentation
api_key_scheme = HTTPBearer(
    scheme_name="API Key",
    description="Provide your API key in the Authorization header as 'Bearer <api_key>'"
)


class AuthenticationError(HTTPException):
    """Custom exception for authentication errors."""
    
    def __init__(self, detail: str, headers: Dict[str, str] = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers
        )


class APIKeyManager:
    """
    Manages API key validation, storage, and metadata.
    
    Uses Redis for fast key lookups and usage tracking.
    """
    
    def __init__(self):
        self.redis = get_redis_client()
        self.settings = get_settings()
    
    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate API key and return user metadata.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            Dictionary with user info if valid, None if invalid
        """
        if not api_key or not api_key.startswith(self.settings.security.api_key_prefix):
            return None
        
        # Hash the API key for secure storage lookup
        key_hash = self._hash_api_key(api_key)
        
        # Look up key metadata in Redis
        key_data = await self.redis.hgetall(f"api_key:{key_hash}")
        if not key_data:
            logger.warning(f"Invalid API key attempted: {api_key[:10]}...")
            return None
        
        # Check if key is expired
        expires_at = key_data.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            logger.warning(f"Expired API key used: {api_key[:10]}...")
            await self.redis.delete(f"api_key:{key_hash}")
            return None
        
        # Check if key is disabled
        if key_data.get("status") != "active":
            logger.warning(f"Inactive API key used: {api_key[:10]}...")
            return None
        
        # Update last used timestamp
        await self.redis.hset(
            f"api_key:{key_hash}",
            "last_used_at",
            datetime.now(timezone.utc).isoformat()
        )
        
        # Return user metadata
        return {
            "user_id": key_data.get("user_id"),
            "key_id": key_data.get("key_id"),
            "tier": key_data.get("tier", "basic"),
            "permissions": key_data.get("permissions", "read").split(","),
            "created_at": key_data.get("created_at"),
            "last_used_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def create_api_key(
        self,
        user_id: str,
        tier: str = "basic",
        permissions: list = None,
        expires_days: int = None
    ) -> Tuple[str, str]:
        """
        Create a new API key for a user.
        
        Args:
            user_id: User identifier
            tier: Access tier (basic, standard, premium, enterprise)
            permissions: List of permissions
            expires_days: Expiry in days (None for default)
            
        Returns:
            Tuple of (api_key, key_id)
        """
        # Generate API key
        import secrets
        key_id = secrets.token_hex(8)  # 16 character key ID
        api_key = f"{self.settings.security.api_key_prefix}{secrets.token_urlsafe(32)}"
        
        # Set expiry
        expires_at = None
        if expires_days or self.settings.security.api_key_expiry_days:
            from datetime import timedelta
            days = expires_days or self.settings.security.api_key_expiry_days
            expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        
        # Store key metadata
        key_hash = self._hash_api_key(api_key)
        key_data = {
            "user_id": user_id,
            "key_id": key_id,
            "tier": tier,
            "permissions": ",".join(permissions or ["read"]),
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used_at": None
        }
        
        if expires_at:
            key_data["expires_at"] = expires_at.isoformat()
        
        await self.redis.hset(f"api_key:{key_hash}", mapping=key_data)
        
        # Track user's keys
        await self.redis.sadd(f"user_keys:{user_id}", key_id)
        
        logger.info(f"Created API key for user {user_id}, tier: {tier}, key_id: {key_id}")
        return api_key, key_id
    
    async def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: The API key to revoke
            
        Returns:
            True if successfully revoked, False if key not found
        """
        key_hash = self._hash_api_key(api_key)
        key_data = await self.redis.hgetall(f"api_key:{key_hash}")
        
        if not key_data:
            return False
        
        user_id = key_data.get("user_id")
        key_id = key_data.get("key_id")
        
        # Remove key data
        await self.redis.delete(f"api_key:{key_hash}")
        
        # Remove from user's key set
        if user_id and key_id:
            await self.redis.srem(f"user_keys:{user_id}", key_id)
        
        logger.info(f"Revoked API key: {key_id}")
        return True
    
    async def list_user_keys(self, user_id: str) -> list:
        """
        List all API keys for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of key metadata dictionaries
        """
        key_ids = await self.redis.smembers(f"user_keys:{user_id}")
        keys_info = []
        
        for key_id in key_ids:
            # Find the key data by scanning for this key_id
            # This is inefficient but needed for the current storage structure
            async for key_name in self.redis.scan_iter(match="api_key:*"):
                key_data = await self.redis.hgetall(key_name)
                if key_data.get("key_id") == key_id:
                    keys_info.append({
                        "key_id": key_id,
                        "tier": key_data.get("tier"),
                        "permissions": key_data.get("permissions", "").split(","),
                        "status": key_data.get("status"),
                        "created_at": key_data.get("created_at"),
                        "last_used_at": key_data.get("last_used_at"),
                        "expires_at": key_data.get("expires_at")
                    })
                    break
        
        return keys_info
    
    def _hash_api_key(self, api_key: str) -> str:
        """Create a secure hash of the API key for storage."""
        # Use HMAC with a secret for secure hashing
        secret = self.settings.security.api_key_prefix.encode()
        return hmac.new(secret, api_key.encode(), hashlib.sha256).hexdigest()


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle API key authentication.
    
    Validates API keys and sets user context for authenticated requests.
    """
    
    def __init__(self, app, require_auth: bool = True):
        super().__init__(app)
        self.require_auth = require_auth
        self.api_key_manager = APIKeyManager()
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with authentication."""
        # Skip authentication for health and documentation endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Extract API key from request
        api_key = self._extract_api_key(request)
        
        if not api_key:
            if self.require_auth:
                raise AuthenticationError(
                    "API key required. Provide it in the Authorization header as 'Bearer <api_key>'",
                    {"WWW-Authenticate": "Bearer"}
                )
            else:
                # Continue without authentication (development mode)
                request.state.user = None
                return await call_next(request)
        
        # Validate API key
        user_info = await self.api_key_manager.validate_api_key(api_key)
        if not user_info:
            raise AuthenticationError(
                "Invalid or expired API key",
                {"WWW-Authenticate": "Bearer"}
            )
        
        # Set user context on request
        request.state.user = user_info
        request.state.api_key_id = user_info["key_id"]
        request.state.user_tier = user_info["tier"]
        
        # Log successful authentication
        logger.debug(
            f"Authenticated user {user_info['user_id']} "
            f"(tier: {user_info['tier']}, key: {user_info['key_id']})"
        )
        
        return await call_next(request)
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from Authorization header or query parameter."""
        # Check Authorization header first (preferred)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        
        # Fallback to query parameter (less secure)
        return request.query_params.get("api_key")
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint should be publicly accessible."""
        public_paths = [
            "/",
            "/health",
            "/api/v1/health",
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/favicon.ico"
        ]
        
        return path in public_paths or path.startswith("/static/")


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user from request context.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User info dictionary if authenticated, None otherwise
    """
    return getattr(request.state, "user", None)


def require_auth(request: Request) -> Dict[str, Any]:
    """
    Dependency to require authentication.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User info dictionary
        
    Raises:
        AuthenticationError: If user is not authenticated
    """
    user = get_current_user(request)
    if not user:
        raise AuthenticationError("Authentication required")
    return user


def require_permission(permission: str):
    """
    Dependency factory to require specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Dependency function
    """
    def check_permission(request: Request) -> Dict[str, Any]:
        user = require_auth(request)
        if permission not in user.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return user
    
    return check_permission


def require_tier(min_tier: str):
    """
    Dependency factory to require minimum access tier.
    
    Args:
        min_tier: Minimum required tier
        
    Returns:
        Dependency function
    """
    tier_levels = {"basic": 1, "standard": 2, "premium": 3, "enterprise": 4}
    min_level = tier_levels.get(min_tier, 1)
    
    def check_tier(request: Request) -> Dict[str, Any]:
        user = require_auth(request)
        user_level = tier_levels.get(user.get("tier", "basic"), 1)
        
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access tier '{min_tier}' or higher required"
            )
        return user
    
    return check_tier


# Development utilities
async def create_dev_api_key(user_id: str = "dev_user") -> str:
    """
    Create a development API key for testing.
    
    Args:
        user_id: User identifier
        
    Returns:
        API key string
    """
    api_key_manager = APIKeyManager()
    api_key, key_id = await api_key_manager.create_api_key(
        user_id=user_id,
        tier="enterprise",  # Full access for development
        permissions=["read", "write", "admin"]
    )
    
    logger.info(f"Created development API key: {api_key}")
    logger.info(f"Key ID: {key_id}")
    
    return api_key