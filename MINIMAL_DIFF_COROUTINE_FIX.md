# Minimal Diff: Fix "Coroutine Was Never Awaited"

## Problem
`RuntimeWarning: coroutine was never awaited` caused by `_run_callback()` creating tasks without tracking them.

## Solution (3 changes to src/jarvis/events.py)

### 1. Add task registry (line 26)
```diff
 _chat_token_buffers: Dict[str, Dict[str, Any]] = {}
 _flush_tasks: Dict[str, asyncio.Task] = {}
+_callback_tasks: Dict[str, List[asyncio.Task]] = {}
 _MAX_BATCH_TIME_MS = 75
```

### 2. Track tasks in _run_callback() (lines 30-68)
```diff
 def _run_callback(cb, event_type, payload):
     try:
         res = cb(event_type, payload)
         if inspect.iscoroutine(res):
             try:
-                asyncio.create_task(res)
+                task = asyncio.create_task(res)
+                request_id = payload.get("request_id") if isinstance(payload, dict) else None
+                if request_id:
+                    if request_id not in _callback_tasks:
+                        _callback_tasks[request_id] = []
+                    _callback_tasks[request_id].append(task)
+                    _logger.debug(f"callback_task_created request_id={request_id}")
+                
+                def cleanup_task(t):
+                    if request_id and request_id in _callback_tasks:
+                        try:
+                            _callback_tasks[request_id].remove(t)
+                            if not _callback_tasks[request_id]:
+                                _callback_tasks.pop(request_id, None)
+                        except (ValueError, KeyError):
+                            pass
+                
+                task.add_done_callback(cleanup_task)
             except RuntimeError:
                 # fallback...
```

### 3. Cancel tasks in cleanup_request_buffers() (lines 340-376)
```diff
 def cleanup_request_buffers(request_id: str) -> None:
     if request_id in _flush_tasks:
         _flush_tasks[request_id].cancel()
         _flush_tasks.pop(request_id, None)
         _logger.debug(f"cleanup_flush_task request_id={request_id}")
     
+    if request_id in _callback_tasks:
+        tasks = _callback_tasks[request_id]
+        for task in tasks:
+            if not task.done():
+                task.cancel()
+        _callback_tasks.pop(request_id, None)
+        _logger.debug(f"cleanup_callback_tasks request_id={request_id} count={len(tasks)}")
+    
     if request_id in _chat_token_buffers:
         # ... flush and cleanup ...
+    
+    _logger.info(f"cleanup_request_complete request_id={request_id}")
```

### 4. Cancel tasks in close() and reset_for_tests()
```diff
 def close():
     # ... existing ...
     for task in list(_flush_tasks.values()):
         task.cancel()
     _flush_tasks.clear()
     
+    for tasks in list(_callback_tasks.values()):
+        for task in tasks:
+            if not task.done():
+                task.cancel()
+    _callback_tasks.clear()
```

## Logs Added
- `callback_task_created request_id=X event=Y` - Task tracked
- `cleanup_callback_tasks request_id=X count=N` - Tasks cancelled
- `cleanup_request_complete request_id=X` - Cleanup done

## Test
```bash
python test_streaming_stability.py
```

Expected: No RuntimeWarning, clean stream transitions.

---
File: src/jarvis/events.py
Lines changed: ~50
Status: Ready
