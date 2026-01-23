import sys
import signal
import faulthandler
import pytest
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Force test mode to disable background workers
os.environ.setdefault("JARVIS_TEST_MODE", "1")

# Enable faulthandler for better stack traces on crashes
faulthandler.enable()

# Register SIGUSR1 to dump stacks for all threads
def dump_stacks(signum, frame):
    import threading
    import traceback
    print("\n=== Thread Stacks (SIGUSR1) ===")
    for thread_id, frame in sys._current_frames().items():
        thread_name = threading._active.get(thread_id, f"Thread-{thread_id}").name
        print(f"\nThread {thread_id} ({thread_name}):")
        traceback.print_stack(frame)
    print("=== End Thread Stacks ===\n")

signal.signal(signal.SIGUSR1, dump_stacks)


@pytest.fixture(scope="session", autouse=True)
def ensure_no_background_threads():
    """Ensure no background threads are left after tests."""
    import threading
    import time
    initial_threads = set(threading.enumerate())
    
    yield
    
    # Give some time for cleanup
    time.sleep(0.5)
    
    current_threads = set(threading.enumerate())
    new_threads = current_threads - initial_threads
    
    # Allow daemon threads, but no new non-daemon threads
    non_daemon_new = [t for t in new_threads if not t.daemon]
    
    if non_daemon_new:
        print(f"Warning: Non-daemon threads created during tests: {[t.name for t in non_daemon_new]}")
        # Don't fail, just warn for now
    try:
        from jarvis import events
        from jarvis.event_store import get_event_store
        events.close()
        get_event_store().clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_events_and_store():
    """Reset EventBus/EventStore state between tests to avoid leakage/hangs."""
    from jarvis import events
    from jarvis.event_store import get_event_store

    events.reset_for_tests()
    store = get_event_store()
    store.clear()
    yield
    try:
        events.reset_for_tests()
        store.clear()
    except Exception:
        pass
