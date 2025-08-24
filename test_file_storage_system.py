#!/usr/bin/env python3
"""
Test script for the new file storage system.
Validates basic functionality before full application testing.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cache.base import FileStorageClient


async def test_file_storage_system():
    """Test the file storage system functionality."""
    print("🧪 Testing File Storage System...")
    
    # Initialize storage client
    storage = FileStorageClient()
    await storage.connect()
    
    try:
        # Test 1: Basic set/get operations
        print("\n1️⃣ Testing basic set/get operations...")
        
        await storage.set("test_key", "test_value")
        result = await storage.get("test_key")
        assert result == "test_value", f"Expected 'test_value', got {result}"
        print("   ✅ Basic string storage works")
        
        # Test 2: Complex data structures
        print("\n2️⃣ Testing complex data structures...")
        
        complex_data = {
            "functions": ["main", "init", "cleanup"],
            "metadata": {
                "binary_size": 1024,
                "architecture": "x64",
                "translation_results": {
                    "main": "Main function that initializes the program",
                    "init": "Initialization routine for setup"
                }
            },
            "count": 42
        }
        
        await storage.set("complex_test", complex_data)
        retrieved = await storage.get("complex_test")
        assert retrieved == complex_data, "Complex data structure mismatch"
        print("   ✅ Complex data structures work")
        
        # Test 3: TTL expiration
        print("\n3️⃣ Testing TTL expiration...")
        
        await storage.set("expire_test", "will_expire", ttl=1)  # 1 second TTL
        immediate = await storage.get("expire_test")
        assert immediate == "will_expire", "Immediate retrieval failed"
        
        print("   ⏳ Waiting 2 seconds for expiration...")
        await asyncio.sleep(2)
        
        expired = await storage.get("expire_test")
        assert expired is None, f"Expected None after expiration, got {expired}"
        print("   ✅ TTL expiration works")
        
        # Test 4: Multiple keys and exists check
        print("\n4️⃣ Testing multiple keys and existence checks...")
        
        await storage.set("key1", "value1")
        await storage.set("key2", "value2") 
        await storage.set("key3", "value3")
        
        exists_count = await storage.exists("key1", "key2", "key3", "nonexistent")
        assert exists_count == 3, f"Expected 3 existing keys, got {exists_count}"
        print("   ✅ Multiple keys and existence checks work")
        
        # Test 5: Key listing
        print("\n5️⃣ Testing key listing...")
        
        keys = await storage.keys("*")
        expected_keys = {"test_key", "complex_test", "key1", "key2", "key3"}
        found_keys = set(keys)
        
        # Check if expected keys are present (may have additional keys from previous tests)
        assert expected_keys.issubset(found_keys), f"Missing keys. Expected subset: {expected_keys}, Found: {found_keys}"
        print(f"   ✅ Key listing works - found {len(keys)} total keys")
        
        # Test 6: Deletion
        print("\n6️⃣ Testing key deletion...")
        
        deleted_count = await storage.delete("key1", "key2", "key3")
        assert deleted_count == 3, f"Expected 3 deletions, got {deleted_count}"
        
        exists_after_delete = await storage.exists("key1", "key2", "key3")
        assert exists_after_delete == 0, f"Expected 0 keys after deletion, got {exists_after_delete}"
        print("   ✅ Key deletion works")
        
        # Test 7: Health check
        print("\n7️⃣ Testing health check...")
        
        health_status = await storage.health_check()
        assert health_status is True, "Health check failed"
        print("   ✅ Health check works")
        
        # Test 8: Performance stats
        print("\n8️⃣ Testing performance stats...")
        
        stats = storage.get_stats()
        assert stats["connected"] is True, "Stats show not connected"
        assert stats["operation_count"] > 0, "No operations recorded"
        print(f"   ✅ Stats work - {stats['operation_count']} operations, {stats['error_count']} errors")
        print(f"      Average response time: {stats['average_response_time_seconds']:.4f}s")
        print(f"      Storage: {stats['storage_stats']['file_count']} files, {stats['storage_stats']['total_size_bytes']} bytes")
        
        print("\n🎉 ALL FILE STORAGE TESTS PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        await storage.flushdb()  # Clear test data
        await storage.disconnect()


async def test_compatibility_aliases():
    """Test that the Redis compatibility aliases work."""
    print("\n🔄 Testing Redis compatibility aliases...")
    
    # Import using the old Redis names
    from cache.base import RedisClient, get_redis_client
    
    # Test that the aliases point to the file storage classes
    assert RedisClient is FileStorageClient, "RedisClient alias not working"
    
    # Test getting client through old interface
    client = await get_redis_client()
    assert isinstance(client, FileStorageClient), "get_redis_client() not returning FileStorageClient"
    
    # Test basic operation through alias
    await client.set("alias_test", "works")
    result = await client.get("alias_test")
    assert result == "works", "Alias operation failed"
    
    print("   ✅ Redis compatibility aliases work perfectly")
    
    await client.disconnect()


async def main():
    """Run all file storage tests."""
    print("🚀 Starting File Storage System Tests...")
    print("=" * 50)
    
    # Test the core file storage functionality
    core_success = await test_file_storage_system()
    
    # Test compatibility aliases
    if core_success:
        await test_compatibility_aliases()
        print("\n🎯 All tests completed successfully!")
        print("   The file storage system is ready for production use.")
        return True
    else:
        print("\n💥 Core tests failed - compatibility tests skipped")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)