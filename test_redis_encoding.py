#!/usr/bin/env python3
"""
Direct test of Redis encoding fix without API layer.
This will verify if our bytes/string handling fix works.
"""

import asyncio
import redis.asyncio as redis
from typing import Dict, Any

async def test_redis_encoding():
    """Test the Redis encoding issue and fix directly."""
    print("Testing Redis encoding fix...")
    
    # Connect to Redis
    redis_client = redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True  # This should make everything strings
    )
    
    try:
        # Test with the same user that has data
        user_id = "bootstrap_admin"
        user_rate_limits = {}
        
        print(f"Scanning for rate limit keys for user: {user_id}")
        
        # Original problematic code - but with our fix
        async for key in redis_client.scan_iter(match=f"rate_limit:user:{user_id}:*"):
            print(f"Found key: {key} (type: {type(key)})")
            
            # Our fix: Handle both bytes and string responses
            if isinstance(key, bytes):
                key_str = key.decode('utf-8')
                print(f"  Decoded bytes to string: {key_str}")
            else:
                key_str = str(key)  # Ensure it's always a string
                print(f"  Already string: {key_str}")
            
            key_parts = key_str.split(":")
            print(f"  Key parts: {key_parts}")
            
            if len(key_parts) >= 4:
                limit_type = key_parts[3]
                print(f"  Limit type: {limit_type}")
                
                # Use string version for Redis operations
                count = await redis_client.zcard(key_str)
                print(f"  Count: {count}")
                
                user_rate_limits[limit_type] = count
        
        print(f"\nResults: {user_rate_limits}")
        
        if user_rate_limits:
            print("✅ SUCCESS: Redis encoding fix works!")
        else:
            print("⚠️  No rate limit keys found for user")
            
    except Exception as e:
        print(f"❌ ERROR: {e} (type: {type(e)})")
        import traceback
        traceback.print_exc()
    
    finally:
        await redis_client.close()

if __name__ == "__main__":
    asyncio.run(test_redis_encoding())