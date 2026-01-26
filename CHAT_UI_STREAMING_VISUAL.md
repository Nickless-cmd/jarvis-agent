# Chat UI Streaming - Visual Fix Explanation

## The Race Condition (Before)

```
Timeline of User Actions and Component State

0ms ──────────────────────────────────────────────────────────────────
     User clicks "Send" button
     
     ┌─ sendMessage() starts
     │  ├─ Create controller = new AbortController()
     │  ├─ Call streamChat(controller.signal, ...)
     │  └─ abortRef.current = () => { controller.abort() }  ← Closure assignment
     │                                                          (some delay here)
     │
     └─> streamChat() starts async fetch
         └─> waiting for network...

1ms ──────────────────────────────────────────────────────────────────
     User clicks "Stop" button (impatient!)
     
     stopStreaming() calls:
     └─> abortRef.current?.()
         
         BUT: abortRef.current assignment hasn't finished yet!
         └─> Might call old value or undefined
             └─> controller.abort() NOT called
                 └─> Stream continues! ❌

500ms ────────────────────────────────────────────────────────────────
      abortRef.current assignment finally completes
      
      But it's too late, user has already stopped waiting

2s ───────────────────────────────────────────────────────────────────
      Stream finally completes
      └─> onDone() fires
          └─> setMessages(prev => ... updated for old message)
              └─> UI shows response for first message when
                  user was expecting response for second message! ❌
```

### The Bug: Closure Reassignment Race

```javascript
// WRONG: Race condition because of callback closure

const abortRef = useRef<() => void>(() => {})  // Initial empty callback

async function sendMessage(prompt) {
  const controller = new AbortController()
  
  // This assignment is ASYNC-aware but happens in the function body
  // It might not complete before user clicks Stop!
  abortRef.current = () => {
    controller.abort()
  }
  
  const handle = await streamChat({signal: controller.signal, ...})
}

function stopStreaming() {
  // If this executes before abortRef.current assignment above,
  // it calls the OLD callback or undefined!
  abortRef.current?.()
}

// Timeline:
// 0ms:   sendMessage() called
// 0.5ms: sendMessage() creates controller
// 0.9ms: User clicks Stop → stopStreaming() → OLD abortRef.current called
// 1.1ms: abortRef.current reassignment completes (too late!)
```

## The Fix (After)

```
Timeline with Fixed Code

0ms ──────────────────────────────────────────────────────────────────
     User clicks "Send" button
     
     sendMessage() starts
     │
     ├─ Create controller = new AbortController()
     │
     ├─ abortControllerRef.current = controller  ← Direct ref (no closure!)
     │                                              (synchronous, fast)
     │
     ├─ isAbortedRef.current = false
     │
     └─> streamChat(controller.signal, ...) starts
         with onDelta, onDone, onError callbacks
         └─> These check: if (isAbortedRef.current) return

1ms ──────────────────────────────────────────────────────────────────
     User clicks "Stop" button
     
     stopStreaming() executes:
     │
     ├─ isAbortedRef.current = true  ← Blocks all callbacks
     │
     └─> abortControllerRef.current.abort()  ← Direct call (no closure)
         └─> Signal immediately aborted
             └─> StreamChat gets CancelledError ✅

500ms ────────────────────────────────────────────────────────────────
      streamChat resolves with CancelledError
      
      ├─ All callbacks check: if (isAbortedRef.current) return
      ├─ onDelta checks: return (no update)
      ├─ onDone checks: return (no update)
      └─ onError checks: return (no update)
         
         NO STATE UPDATES! ✅

2s ───────────────────────────────────────────────────────────────────
      Component continues normally
      User's UI is clean (no stale responses)
      Ready for new message ✅
```

### The Fix: Direct Ref + Abort Guard

```javascript
// CORRECT: No race condition

const abortControllerRef = useRef<AbortController | null>(null)
const isAbortedRef = useRef(false)

async function sendMessage(prompt) {
  const controller = new AbortController()
  
  // Direct sync assignment (no closure)
  abortControllerRef.current = controller
  isAbortedRef.current = false
  
  const handle = await streamChat({
    signal: controller.signal,
    onDelta: (delta) => {
      if (isAbortedRef.current) return  // Guard against stale callback
      setMessages(...)
    },
    onDone: () => {
      if (isAbortedRef.current) return  // Guard
      setIsStreaming(false)
    }
  })
}

function stopStreaming() {
  // Direct check + direct abort (no closure indirection)
  if (!abortControllerRef.current || isAbortedRef.current) return
  
  isAbortedRef.current = true  // Block all callbacks FIRST
  try {
    abortControllerRef.current.abort()  // Then abort SIGNAL
  } catch {}
  
  setIsStreaming(false)  // Update UI immediately
}

// Timeline:
// 0ms:   sendMessage() → controller = new ... → abortControllerRef set
// 1ms:   User clicks → stopStreaming() → isAbortedRef = true → abort()
// Result: No race! Abort is guaranteed to execute and callbacks are guarded.
```

## Message State Transitions

### Problem: "Thinking" Status Never Cleared

```
Assistant Message State Over Time

Initial: {id: "a-123", role: "assistant", content: "", status: "thinking"}
         └─ Shows: "Thinking…" ✓

Token 1 "H": {id: "a-123", role: "assistant", content: "H", status: "thinking"}
             └─ Shows: "Thinking…" + "H"  ❌ (Both shown! Confusing)

Token 2 "e": {id: "a-123", role: "assistant", content: "He", status: "thinking"}
             └─ Shows: "Thinking…" + "He"  ❌

... continues with "Thinking…" label visible forever
```

### Solution: Track First Token

```javascript
let isFirstToken = true  // Local variable in sendMessage

const handle = await streamChat(
  { ... },
  (delta: string) => {
    // Guard against post-abort updates
    if (isAbortedRef.current) return
    
    setMessages(prev => {
      const copy = prev.slice()
      const idx = copy.findIndex(m => m.id === assistantId)
      if (idx === -1) return copy
      const msg = copy[idx]
      
      if (isFirstToken) {
        // REPLACE content, REPLACE status (remove "thinking")
        isFirstToken = false
        copy[idx] = { 
          ...msg, 
          content: delta,         // Start with first token
          status: 'streaming'     // Change status!
        }
      } else {
        // Subsequent tokens: APPEND content only
        copy[idx] = { 
          ...msg, 
          content: msg.content + delta  // Append
          // status stays 'streaming'
        }
      }
      return copy
    })
  },
  () => {
    // Guard
    if (isAbortedRef.current) return
    setIsStreaming(false)
    setMessages(prev => prev.map(m => 
      m.id === assistantId ? { ...m, status: 'done' } : m
    ))
  }
)
```

### Result: Clean State Transition

```
Initial:  {content: "",            status: "thinking"}  → UI shows: "Thinking…"
Token 1:  {content: "H",           status: "streaming"} → UI shows: "H"
Token 2:  {content: "He",          status: "streaming"} → UI shows: "He"
Token 3:  {content: "Hel",         status: "streaming"} → UI shows: "Hel"
...
Final:    {content: "Hello world!", status: "done"}     → UI shows: "Hello world!"
```

## Stop Button State Machine

### Before (Broken)

```
User clicks Stop:
  ┌─ stopStreaming() called
  ├─ abortRef.current?.() called
  │  └─ But what is abortRef.current?
  │     ├─ Old callback? → Calls old controller (not current)
  │     ├─ Undefined? → Nothing happens
  │     └─ Current callback? → Works (but timing unclear)
  │
  └─ User confused (did it work?)

Then later:
  ├─ onDone() fires (stream completed)
  ├─ setIsStreaming(false)
  └─ Message updates (race with UI)

Then user clicks Stop again:
  ├─ controller.abort() called AGAIN
  ├─ abort() on already-aborted controller
  └─ Throws error? Unpredictable behavior
```

### After (Fixed)

```
User clicks Stop:
  ┌─ stopStreaming() called
  ├─ Early return if already aborted (idempotent)
  ├─ isAbortedRef.current = true (blocks all state updates)
  ├─ abortControllerRef.current.abort() (direct, guaranteed to work)
  ├─ setIsStreaming(false) (UI updates immediately)
  │
  └─ Result: Stream aborted, UI responds immediately

Then later:
  ├─ onDone() fires
  ├─ First check: if (isAbortedRef.current) return
  ├─ No state updates (guarded)
  └─ UI clean

Then user clicks Stop again:
  ├─ stopStreaming() checks: if (isAbortedRef.current) return
  ├─ Early return (idempotent)
  └─ No error, no crash
```

## Key Insights

1. **Closure Race**: Assigning callbacks in closures is dangerous with rapid user interaction
2. **Direct Refs**: Storing the actual object (AbortController) is safer than storing callbacks
3. **Guard Flag**: `isAbortedRef` flag ensures callbacks are idempotent and can't update stale state
4. **First Token**: Needs special handling to transition from "thinking" → "streaming"
5. **State Immutability**: Each setMessages() creates new message object to ensure React detects change

---

**Visual Updated**: 2026-01-26  
**Key Learning**: Direct refs + guard flags beat closure callbacks for async abort patterns
