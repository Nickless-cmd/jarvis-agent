#!/usr/bin/env python3
"""
Test script to verify status/thinking streaming with rate-limiting.

Tests:
1. Status events published directly (NOT buffered)
2. Rate-limiting works (max 10/sec)
3. Status events don't block content tokens
4. Status events can be dropped at rate limit without affecting content
"""

import asyncio
import time
from src.jarvis.events import publish, subscribe, cleanup_request_buffers, close, reset_for_tests


def test_status_rate_limiting():
    """Test that status events are rate-limited to 10/sec."""
    print("\n=== TEST 1: Status Rate Limiting ===")
    reset_for_tests()
    
    received_status = []
    
    def status_handler(event_type, payload):
        received_status.append(payload)
    
    subscribe("chat.status", status_handler)
    
    # Send 20 status updates rapidly (should only get 10)
    request_id = "test-rate-limit-1"
    for i in range(20):
        publish("chat.status", {
            "request_id": request_id,
            "status": f"thinking_{i}",
            "session_id": "test-session",
        })
    
    # Should have received max 10 (rate limit)
    print(f"  Sent: 20 status events")
    print(f"  Received: {len(received_status)} status events")
    
    if len(received_status) == 10:
        print("  ✓ Rate limiting working (10/10)")
        return True
    else:
        print(f"  ✗ Expected 10, got {len(received_status)}")
        return False


async def test_status_not_buffered():
    """Test that status events are published immediately (NOT buffered like tokens)."""
    print("\n=== TEST 2: Status NOT Buffered ===")
    reset_for_tests()
    
    received_status = []
    received_tokens = []
    
    def status_handler(event_type, payload):
        received_status.append(payload)
    
    def token_handler(event_type, payload):
        received_tokens.append(payload)
    
    subscribe("chat.status", status_handler)
    subscribe("chat.token", token_handler)
    
    request_id = "test-buffering-1"
    
    # Publish status (should be immediate)
    publish("chat.status", {
        "request_id": request_id,
        "status": "thinking",
        "session_id": "test-session",
    })
    
    # Publish token (will be buffered for 75ms)
    publish("chat.token", {
        "request_id": request_id,
        "token": "Hello",
        "session_id": "test-session",
    })
    
    # Wait just a bit for async processing
    await asyncio.sleep(0.01)
    
    # Status should be received immediately, tokens still buffered
    print(f"  Status events received immediately: {len(received_status)}")
    print(f"  Token events (still buffered): {len(received_tokens)}")
    
    if len(received_status) == 1 and len(received_tokens) == 0:
        print("  ✓ Status immediate, tokens buffered")
        return True
    else:
        print(f"  ✗ Expected status=1 tokens=0, got status={len(received_status)} tokens={len(received_tokens)}")
        return False


def test_status_cleanup():
    """Test that status rate limit state is cleaned up with request."""
    print("\n=== TEST 3: Status Cleanup ===")
    reset_for_tests()
    
    from src.jarvis.events import _status_rate_limit
    
    request_id = "test-cleanup-1"
    
    # Publish some status events
    for i in range(5):
        publish("chat.status", {
            "request_id": request_id,
            "status": f"thinking_{i}",
            "session_id": "test-session",
        })
    
    # Check rate limit state exists
    if request_id in _status_rate_limit:
        print(f"  Rate limit state created: {len(_status_rate_limit[request_id])} entries")
    else:
        print("  ✗ Rate limit state not found")
        return False
    
    # Cleanup
    cleanup_request_buffers(request_id)
    
    # Check rate limit state removed
    if request_id not in _status_rate_limit:
        print("  ✓ Rate limit state cleaned up")
        return True
    else:
        print("  ✗ Rate limit state still present after cleanup")
        return False


async def test_status_with_async():
    """Test that status events work with async event loop."""
    print("\n=== TEST 4: Status with Async ===")
    reset_for_tests()
    
    received_status = []
    
    async def async_status_handler(event_type, payload):
        received_status.append(payload)
        await asyncio.sleep(0.001)  # Simulate async work
    
    subscribe("chat.status", async_status_handler)
    
    request_id = "test-async-1"
    
    # Publish status events
    for i in range(5):
        publish("chat.status", {
            "request_id": request_id,
            "status": f"thinking_{i}",
            "session_id": "test-session",
        })
    
    # Wait a bit for async handlers
    await asyncio.sleep(0.1)
    
    print(f"  Status events received: {len(received_status)}")
    
    if len(received_status) == 5:
        print("  ✓ Async status handlers working")
        return True
    else:
        print(f"  ✗ Expected 5, got {len(received_status)}")
        return False


def test_rate_limit_recovery():
    """Test that rate limit recovers after 1 second."""
    print("\n=== TEST 5: Rate Limit Recovery ===")
    reset_for_tests()
    
    received_status = []
    
    def status_handler(event_type, payload):
        received_status.append(payload)
    
    subscribe("chat.status", status_handler)
    
    request_id = "test-recovery-1"
    
    # Send 10 events (should all go through)
    for i in range(10):
        publish("chat.status", {
            "request_id": request_id,
            "status": f"batch1_{i}",
            "session_id": "test-session",
        })
    
    batch1_count = len(received_status)
    print(f"  Batch 1 (immediate): {batch1_count} events")
    
    # Send 10 more (should be rate limited)
    for i in range(10):
        publish("chat.status", {
            "request_id": request_id,
            "status": f"batch2_{i}",
            "session_id": "test-session",
        })
    
    batch2_count = len(received_status) - batch1_count
    print(f"  Batch 2 (immediate, rate limited): {batch2_count} events")
    
    # Wait 1.1 seconds for rate limit to reset
    print("  Waiting 1.1s for rate limit reset...")
    time.sleep(1.1)
    
    # Send 10 more (should go through again)
    for i in range(10):
        publish("chat.status", {
            "request_id": request_id,
            "status": f"batch3_{i}",
            "session_id": "test-session",
        })
    
    batch3_count = len(received_status) - batch1_count - batch2_count
    print(f"  Batch 3 (after reset): {batch3_count} events")
    
    if batch1_count == 10 and batch2_count == 0 and batch3_count == 10:
        print("  ✓ Rate limit recovery working")
        return True
    else:
        print(f"  ✗ Expected 10/0/10, got {batch1_count}/{batch2_count}/{batch3_count}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  STATUS/THINKING STREAMING TESTS")
    print("="*60)
    
    results = []
    
    # Run sync tests
    results.append(("Rate Limiting", test_status_rate_limiting()))
    results.append(("Cleanup", test_status_cleanup()))
    results.append(("Rate Limit Recovery", test_rate_limit_recovery()))
    
    # Run async tests
    async def run_async_tests():
        r = []
        r.append(await test_status_not_buffered())
        r.append(await test_status_with_async())
        return r
    
    async_results = asyncio.run(run_async_tests())
    results.append(("Not Buffered", async_results[0]))
    results.append(("Async Support", async_results[1]))
    
    # Print summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print("\n" + "="*60)
    if passed == total:
        print(f"  ✓✓✓ ALL TESTS PASSED ({passed}/{total}) ✓✓✓")
        print("="*60)
        return 0
    else:
        print(f"  ✗ SOME TESTS FAILED ({passed}/{total})")
        print("="*60)
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        close()
        exit(exit_code)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        close()
        exit(1)
