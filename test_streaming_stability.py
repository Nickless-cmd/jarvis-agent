#!/usr/bin/env python3
"""
Test script to verify streaming stability fix.

GOAL: Verify that sending prompt B immediately after prompt A does NOT hang the server.

Expected behavior:
- Prompt A starts streaming
- Prompt B sent 50ms later (no Stop button pressed)
- Prompt A is cancelled cleanly
- Prompt B starts streaming
- Server remains responsive
- No kill -9 needed

Repeat 5 times to ensure stability.
"""

import time
import requests
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:8000"
API_ENDPOINT = f"{BASE_URL}/v1/chat/completions"

def send_stream_request(session_id: str, prompt: str, request_label: str):
    """Send a streaming request and collect results."""
    start_time = time.time()
    try:
        response = requests.post(
            API_ENDPOINT,
            json={
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
            headers={"X-Session-Id": session_id},
            stream=True,
            timeout=10,
        )
        
        chunks = []
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    chunks.append(data)
                except:
                    chunks.append(line.decode() if isinstance(line, bytes) else line)
        
        duration = time.time() - start_time
        return {
            "label": request_label,
            "status": response.status_code,
            "chunks": len(chunks),
            "duration": duration,
            "success": True,
        }
    
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        return {
            "label": request_label,
            "status": "timeout",
            "chunks": 0,
            "duration": duration,
            "success": False,
            "error": "Request timed out (server hung?)",
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "label": request_label,
            "status": "error",
            "chunks": 0,
            "duration": duration,
            "success": False,
            "error": str(e),
        }


def test_rapid_requests():
    """Test sending Prompt B immediately after Prompt A."""
    session_id = f"test-rapid-{int(time.time() * 1000)}"
    
    print(f"\n{'='*60}")
    print(f"SESSION: {session_id}")
    print(f"{'='*60}")
    
    # Start Prompt A
    print("[1/2] Sending Prompt A (long essay)...")
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit Prompt A
        future_a = executor.submit(
            send_stream_request,
            session_id,
            "Write a comprehensive 500-word essay about the history and future of artificial intelligence, covering major milestones and predictions.",
            "Prompt A (long)"
        )
        
        # Wait 50ms then submit Prompt B
        time.sleep(0.05)
        print("[2/2] Sending Prompt B (simple) IMMEDIATELY (no Stop pressed)...")
        
        future_b = executor.submit(
            send_stream_request,
            session_id,
            "What is 2+2?",
            "Prompt B (simple)"
        )
        
        # Collect results
        results = {}
        for future in as_completed([future_a, future_b], timeout=15):
            result = future.result()
            results[result["label"]] = result
            print(f"  ✓ {result['label']}: status={result.get('status')} chunks={result.get('chunks')} duration={result.get('duration'):.2f}s")
    
    # Analyze results
    success = True
    
    if not results.get("Prompt A (long)", {}).get("success"):
        print(f"  ⚠️  Prompt A failed: {results['Prompt A (long)'].get('error', 'Unknown')}")
        # A might be cancelled - that's OK
    
    if not results.get("Prompt B (simple)", {}).get("success"):
        print(f"  ✗ Prompt B failed: {results['Prompt B (simple)'].get('error', 'Unknown')}")
        success = False
    else:
        print(f"  ✓ Prompt B succeeded!")
    
    # Check for timeout (indicates hang)
    if results.get("Prompt A (long)", {}).get("status") == "timeout":
        print(f"  ✗ Prompt A timed out - SERVER HUNG!")
        success = False
    
    if results.get("Prompt B (simple)", {}).get("status") == "timeout":
        print(f"  ✗ Prompt B timed out - SERVER HUNG!")
        success = False
    
    return success


def test_baseline():
    """Test normal streaming (baseline)."""
    session_id = f"test-baseline-{int(time.time() * 1000)}"
    
    print(f"\n{'='*60}")
    print(f"BASELINE TEST: {session_id}")
    print(f"{'='*60}")
    
    print("[1/1] Sending normal request...")
    result = send_stream_request(session_id, "Hello, how are you?", "Baseline")
    
    if result["success"]:
        print(f"  ✓ Baseline succeeded: status={result['status']} chunks={result['chunks']} duration={result['duration']:.2f}s")
        return True
    else:
        print(f"  ✗ Baseline failed: {result.get('error', 'Unknown')}")
        return False


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          STREAMING STABILITY TEST - RAPID REQUESTS          ║
╚══════════════════════════════════════════════════════════════╝

Testing: Send Prompt B immediately after Prompt A (no Stop pressed)
Expected: Prompt A cancelled, Prompt B responds, NO HANG
Iterations: 5

""")
    
    # Test baseline first
    print("PHASE 1: Baseline Test")
    if not test_baseline():
        print("\n✗ BASELINE FAILED - Server not responding normally!")
        print("  Check if server is running: curl http://localhost:8000/health")
        return 1
    
    print("\n✓ BASELINE PASSED")
    
    # Test rapid requests 5 times
    print("\nPHASE 2: Rapid Requests (5 iterations)")
    successes = 0
    failures = 0
    
    for i in range(5):
        print(f"\n--- Iteration {i+1}/5 ---")
        if test_rapid_requests():
            successes += 1
            print(f"  ✓ Iteration {i+1} PASSED")
        else:
            failures += 1
            print(f"  ✗ Iteration {i+1} FAILED")
        
        # Small delay between iterations
        if i < 4:
            time.sleep(1)
    
    # Final report
    print(f"\n{'='*60}")
    print(f"FINAL RESULTS:")
    print(f"{'='*60}")
    print(f"  Successes: {successes}/5")
    print(f"  Failures:  {failures}/5")
    
    if failures == 0:
        print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("  Server handles rapid requests without hanging!")
        print("  Fix is working correctly.")
        return 0
    else:
        print(f"\n✗✗✗ {failures} TEST(S) FAILED ✗✗✗")
        print("  Server may still have hanging issues.")
        print("  Check logs for:")
        print("    - 'stream_cancelled' (old stream cancelled)")
        print("    - 'prev_stream_finished_cleanly' (old stream cleanup)")
        print("    - 'stream_end' (cleanup complete)")
        print("    - 'flush_scheduled', 'flush_done' (event buffer handling)")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
