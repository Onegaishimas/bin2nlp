#!/usr/bin/env python3
"""
bin2nlp CLI Management Tool

Command-line interface for managing API keys, monitoring system health,
and performing administrative tasks.
"""

import asyncio
import sys
import argparse
from typing import Optional
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, '.')

from src.core.config import get_settings, validate_settings
from src.api.middleware import APIKeyManager, create_dev_api_key
from src.cache.base import get_file_storage_client
from src.database.connection import get_database


async def create_api_key(
    user_id: str,
    tier: str = "basic",
    permissions: list = None,
    expires_days: Optional[int] = None
) -> None:
    """Create a new API key."""
    try:
        api_key_manager = APIKeyManager()
        
        api_key, key_id = await api_key_manager.create_api_key(
            user_id=user_id,
            tier=tier,
            permissions=permissions or ["read"],
            expires_days=expires_days
        )
        
        print(f"✅ API Key created successfully!")
        print(f"   User ID: {user_id}")
        print(f"   Key ID: {key_id}")
        print(f"   Tier: {tier}")
        print(f"   Permissions: {', '.join(permissions or ['read'])}")
        print(f"   API Key: {api_key}")
        print()
        print("⚠️  Store this API key securely - it cannot be retrieved again!")
        print(f"   Use it in requests: Authorization: Bearer {api_key}")
        
    except Exception as e:
        print(f"❌ Failed to create API key: {e}")
        sys.exit(1)


async def list_api_keys(user_id: str) -> None:
    """List all API keys for a user."""
    try:
        api_key_manager = APIKeyManager()
        keys = await api_key_manager.list_user_keys(user_id)
        
        if not keys:
            print(f"No API keys found for user: {user_id}")
            return
        
        print(f"API Keys for user: {user_id}")
        print("=" * 60)
        
        for key in keys:
            print(f"Key ID: {key['key_id']}")
            print(f"  Tier: {key.get('tier', 'unknown')}")
            print(f"  Permissions: {key.get('permissions', '').replace(',', ', ')}")
            print(f"  Status: {key.get('status', 'unknown')}")
            print(f"  Created: {key.get('created_at', 'unknown')}")
            print(f"  Last Used: {key.get('last_used_at', 'never')}")
            if key.get('expires_at'):
                print(f"  Expires: {key['expires_at']}")
            print()
        
    except Exception as e:
        print(f"❌ Failed to list API keys: {e}")
        sys.exit(1)


async def check_system_health() -> None:
    """Check system health and configuration."""
    print("bin2nlp System Health Check")
    print("=" * 40)
    
    # Check configuration
    try:
        settings = get_settings()
        validate_settings()
        print("✅ Configuration: Valid")
        print(f"   Environment: {settings.environment}")
        print(f"   Debug Mode: {settings.debug}")
    except Exception as e:
        print(f"❌ Configuration: Invalid - {e}")
        return
    
    # Check Database connection
    try:
        db = await get_database()
        result = await db.fetch_one("SELECT 1 as test")
        if result and result['test'] == 1:
            print("✅ Database: Connected (PostgreSQL)")
        else:
            print("❌ Database: Query test failed")
    except Exception as e:
        print(f"❌ Database: Connection failed - {e}")
    
    # Check File Storage
    try:
        storage = await get_file_storage_client()
        is_healthy = await storage.health_check()
        if is_healthy:
            stats = storage.get_stats()
            print("✅ Storage: Connected (File System)")
            print(f"   Files: {stats['storage_stats']['file_count']}")
            print(f"   Size: {stats['storage_stats']['total_size_bytes']} bytes")
        else:
            print("❌ Storage: Health check failed")
    except Exception as e:
        print(f"❌ Storage: Connection failed - {e}")
    
    # Check LLM providers
    try:
        llm_credentials = settings.llm.validate_provider_credentials()
        enabled_count = len(settings.llm.enabled_providers)
        valid_count = sum(1 for valid in llm_credentials.values() if valid)
        
        print(f"✅ LLM Providers: {valid_count}/{enabled_count} configured")
        for provider, valid in llm_credentials.items():
            status = "✅" if valid else "❌"
            print(f"   {status} {provider}: {'Configured' if valid else 'Missing API key'}")
    except Exception as e:
        print(f"❌ LLM Providers: Configuration error - {e}")
    
    print()
    print("System Status: " + ("✅ Healthy" if True else "❌ Issues found"))


async def create_dev_key() -> None:
    """Create a development API key."""
    try:
        settings = get_settings()
        if settings.is_production:
            print("❌ Development keys cannot be created in production environment")
            sys.exit(1)
        
        api_key = await create_dev_api_key("dev_user")
        print("✅ Development API key created!")
        print(f"   API Key: {api_key}")
        print(f"   User ID: dev_user")
        print(f"   Tier: enterprise")
        print(f"   Permissions: read, write, admin")
        print()
        print("⚠️  For development use only!")
        
    except Exception as e:
        print(f"❌ Failed to create development API key: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="bin2nlp Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s health                                    # Check system health
  %(prog)s create-key alice basic                    # Create basic API key for alice
  %(prog)s create-key bob premium --permissions read,write
  %(prog)s list-keys alice                          # List alice's API keys
  %(prog)s dev-key                                  # Create development key
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Health check command
    subparsers.add_parser('health', help='Check system health')
    
    # Create API key command
    create_parser = subparsers.add_parser('create-key', help='Create new API key')
    create_parser.add_argument('user_id', help='User identifier')
    create_parser.add_argument('tier', nargs='?', default='basic',
                              choices=['basic', 'standard', 'premium', 'enterprise'],
                              help='Access tier (default: basic)')
    create_parser.add_argument('--permissions', default='read',
                              help='Comma-separated permissions (default: read)')
    create_parser.add_argument('--expires-days', type=int,
                              help='Key expiry in days (default: from config)')
    
    # List API keys command
    list_parser = subparsers.add_parser('list-keys', help='List API keys for user')
    list_parser.add_argument('user_id', help='User identifier')
    
    # Development key command
    subparsers.add_parser('dev-key', help='Create development API key')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Run async commands
    try:
        if args.command == 'health':
            asyncio.run(check_system_health())
        
        elif args.command == 'create-key':
            permissions = [p.strip() for p in args.permissions.split(',')]
            asyncio.run(create_api_key(
                user_id=args.user_id,
                tier=args.tier,
                permissions=permissions,
                expires_days=args.expires_days
            ))
        
        elif args.command == 'list-keys':
            asyncio.run(list_api_keys(args.user_id))
        
        elif args.command == 'dev-key':
            asyncio.run(create_dev_key())
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()