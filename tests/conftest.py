import sys
import signal
import faulthandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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
