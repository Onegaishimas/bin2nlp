#!/usr/bin/env python3
"""
Admin Management CLI
Bootstrap and manage admin users for bin2nlp API
"""

import asyncio
import sys
import argparse
from typing import Optional

from ..core.config import get_settings
from ..core.logging import configure_logging, get_logger
from ..api.middleware.auth import APIKeyManager


logger = get_logger(__name__)


async def create_admin_key(user_id: str, description: Optional[str] = None) -> str:
    """Create an admin API key."""
    try:
        manager = APIKeyManager()
        api_key, key_id = await manager.create_api_key(
            user_id=user_id,
            tier="enterprise",
            permissions=["read", "write", "admin"],
        )
        
        logger.info(f"Created admin API key for user {user_id}")
        logger.info(f"Key ID: {key_id}")
        
        return api_key
        
    except Exception as e:
        logger.error(f"Failed to create admin API key: {e}")
        raise


async def bootstrap_admin(user_id: str = "admin") -> str:
    """Bootstrap the initial admin user."""
    settings = get_settings()
    configure_logging(settings.logging)
    
    logger.info("🚀 Bootstrapping bin2nlp admin user")
    logger.info(f"Environment: {settings.environment}")
    
    try:
        # Initialize Redis connection
        from ..cache.base import get_redis_client
        redis = get_redis_client()
        await redis.ping()
        logger.info("✅ Redis connection established")
        
        # Create admin API key
        api_key = await create_admin_key(
            user_id=user_id,
            description="Bootstrap admin key"
        )
        
        logger.info("✅ Admin user bootstrapped successfully!")
        logger.info("")
        logger.info("=" * 60)
        logger.info("🔑 ADMIN API KEY (save this securely!):")
        logger.info(f"   {api_key}")
        logger.info("=" * 60)
        logger.info("")
        logger.info("You can now use this key to:")
        logger.info("- Access admin endpoints: /api/v1/admin/*")
        logger.info("- Create additional API keys for other users")
        logger.info("- Manage system configuration and monitoring")
        logger.info("")
        logger.info("Example usage:")
        logger.info(f'  curl -H "Authorization: Bearer {api_key}" \\')
        logger.info("    http://localhost:8000/api/v1/admin/stats")
        
        return api_key
        
    except Exception as e:
        logger.error(f"❌ Failed to bootstrap admin user: {e}")
        raise
    finally:
        try:
            redis = get_redis_client()
            await redis.close()
        except:
            pass


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="bin2nlp Admin Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Bootstrap initial admin user
  python -m src.cli.admin bootstrap

  # Create admin key for specific user
  python -m src.cli.admin create-admin-key --user-id production_admin

  # Quick bootstrap (Docker)
  docker exec bin2nlp-api python -m src.cli.admin bootstrap
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Bootstrap command
    bootstrap_parser = subparsers.add_parser(
        "bootstrap", 
        help="Bootstrap initial admin user"
    )
    bootstrap_parser.add_argument(
        "--user-id",
        default="admin",
        help="Admin user ID (default: admin)"
    )
    
    # Create admin key command  
    create_parser = subparsers.add_parser(
        "create-admin-key",
        help="Create an admin API key"
    )
    create_parser.add_argument(
        "--user-id",
        required=True,
        help="User ID for the admin key"
    )
    create_parser.add_argument(
        "--description",
        help="Description for the API key"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "bootstrap":
            asyncio.run(bootstrap_admin(args.user_id))
        elif args.command == "create-admin-key":
            asyncio.run(create_admin_key(args.user_id, args.description))
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()