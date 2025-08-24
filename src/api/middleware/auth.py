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
from ...database.connection import get_database

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
    
    Uses PostgreSQL database for fast key lookups and usage tracking.
    """
    
    def __init__(self):
        self.settings = get_settings()
    
    async def _get_database(self):
        """Get database connection."""
        return await get_database()
    
    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate API key and return user metadata.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            Dictionary with user info if valid, None if invalid
        """
        try:
            if not api_key or not api_key.startswith(self.settings.security.api_key_prefix):
                return None
            
            db = await self._get_database()
            
            # Hash the API key for secure storage lookup
            key_hash = self._hash_api_key(api_key)
            
            # Look up key metadata in PostgreSQL
            result = await db.fetch_one("""
                SELECT user_id, key_id, tier, permissions, status,
                       created_at, last_used_at, expires_at
                FROM api_keys 
                WHERE key_hash = :key_hash AND status = 'active'
                AND (expires_at IS NULL OR expires_at > NOW())
            """, {"key_hash": key_hash})
            
            if not result:
                logger.warning(f"Invalid API key attempted: {api_key[:10]}...")
                return None
            
            # Update last used timestamp
            await db.execute("""
                UPDATE api_keys 
                SET last_used_at = NOW()
                WHERE key_hash = :key_hash
            """, {"key_hash": key_hash})
            
            # Return user metadata
            return {
                "user_id": result['user_id'],
                "key_id": result['key_id'], 
                "tier": result['tier'] or "basic",
                "permissions": result['permissions'].split(",") if result['permissions'] else ["read"],
                "created_at": result['created_at'].isoformat() if result['created_at'] else None,
                "last_used_at": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            # Log the error but don't expose it to prevent information leakage
            logger.error(f"Error during API key validation: {e}")
            return None
    
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
        db = await self._get_database()
        
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
        
        # Store key metadata in PostgreSQL
        key_hash = self._hash_api_key(api_key)
        
        await db.execute("""
            INSERT INTO api_keys (
                key_id, user_id, key_hash, tier, permissions, 
                status, created_at, expires_at
            ) VALUES (
                :key_id, :user_id, :key_hash, :tier, :permissions,
                'active', NOW(), :expires_at
            )
        """, {
            "key_id": key_id,
            "user_id": user_id,
            "key_hash": key_hash,
            "tier": tier,
            "permissions": ",".join(permissions or ["read"]),
            "expires_at": expires_at
        })
        
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
        db = await self._get_database()
        key_hash = self._hash_api_key(api_key)
        
        # Update key status to inactive
        rows_updated = await db.execute("""
            UPDATE api_keys 
            SET status = 'inactive'
            WHERE key_hash = :key_hash
        """, {"key_hash": key_hash})
        
        success = rows_updated > 0
        if success:
            logger.info(f"Revoked API key with hash: {key_hash[:16]}...")
        
        return success
    
    async def list_user_keys(self, user_id: str) -> list:
        """
        List all API keys for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of key metadata dictionaries
        """
        db = await self._get_database()
        
        # Get all API keys for the user from PostgreSQL
        results = await db.fetch_all("""
            SELECT key_id, user_id, tier, permissions, status,
                   created_at, last_used_at, expires_at
            FROM api_keys 
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """, {"user_id": user_id})
        
        keys_info = []
        for row in results:
            keys_info.append({
                "key_id": row['key_id'],
                "user_id": row['user_id'],
                "tier": row['tier'],
                "permissions": row['permissions'].split(",") if row['permissions'] else [],
                "status": row['status'],
                "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                "last_used_at": row['last_used_at'].isoformat() if row['last_used_at'] else None,
                "expires_at": row['expires_at'].isoformat() if row['expires_at'] else None
            })
        
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
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Authentication required"},
                    headers={"WWW-Authenticate": "Bearer"}
                )
            else:
                # Continue without authentication (development mode)
                request.state.user = None
                return await call_next(request)
        
        # Validate API key
        user_info = await self.api_key_manager.validate_api_key(api_key)
        if not user_info:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired API key"},
                headers={"WWW-Authenticate": "Bearer"}
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
            "/favicon.ico",
            "/api/v1/admin/bootstrap/create-admin"
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user


def require_permission(permission):
    """
    Dependency factory to require specific permission(s).
    
    Args:
        permission: Required permission (string) or list of permissions (any one required)
        
    Returns:
        Dependency function
    """
    def check_permission(request: Request) -> Dict[str, Any]:
        user = require_auth(request)
        user_permissions = user.get("permissions", [])
        
        # Handle both single permission and list of permissions
        if isinstance(permission, str):
            # Single permission required
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required"
                )
        elif isinstance(permission, list):
            # Any one of the permissions required
            if not any(perm in user_permissions for perm in permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of permissions {permission} required"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid permission specification"
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