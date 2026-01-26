import asyncio
import pytest

from jarvis.server import StreamRegistry, _StreamEntry


async def _dummy_task(cancel_event: asyncio.Event):
    try:
        while not cancel_event.is_set():
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        raise


@pytest.mark.asyncio
async def test_register_cancels_existing_same_session():
    reg = StreamRegistry()
    evt1 = asyncio.Event()
    task1 = asyncio.create_task(_dummy_task(evt1))
    entry1: _StreamEntry = {
        "session_id": "s1",
        "trace_id": "t1",
        "request_id": "r1",
        "task": task1,
        "cancel_event": evt1,
        "started_at": 0.0,
        "last_activity_at": 0.0,
    }
    await reg.register(entry1)

    evt2 = asyncio.Event()
    task2 = asyncio.create_task(_dummy_task(evt2))
    entry2: _StreamEntry = {
        "session_id": "s1",
        "trace_id": "t2",
        "request_id": "r2",
        "task": task2,
        "cancel_event": evt2,
        "started_at": 0.0,
        "last_activity_at": 0.0,
    }
    await reg.register(entry2)

    # old task should be cancelled
    await asyncio.sleep(0.05)
    assert task1.cancelled() or task1.done()
    assert await reg.get("t2") is not None

    # cleanup
    task2.cancel()
    await reg.pop("t2")


@pytest.mark.asyncio
async def test_cancel_and_pop():
    reg = StreamRegistry()
    evt = asyncio.Event()
    task = asyncio.create_task(_dummy_task(evt))
    entry: _StreamEntry = {
        "session_id": "s2",
        "trace_id": "t3",
        "request_id": "r3",
        "task": task,
        "cancel_event": evt,
        "started_at": 0.0,
        "last_activity_at": 0.0,
    }
    await reg.register(entry)
    await reg.cancel("t3", reason="test")
    await asyncio.sleep(0.05)
    assert task.cancelled() or task.done()
    await reg.pop("t3")
    assert await reg.get("t3") is None
