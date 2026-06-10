"""SSE (Server-Sent Events) event manager for streaming agent progress."""

import asyncio
import json
from typing import AsyncGenerator
from app.utils.logger import logger


class SSEEventManager:
    """Manages SSE event queues per session for streaming agent progress."""

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def create_session(self, session_id: str) -> None:
        """Create a new event queue for a session."""
        self._queues[session_id] = asyncio.Queue()
        logger.info(f"SSE session created: {session_id}")

    def remove_session(self, session_id: str) -> None:
        """Remove a session's event queue."""
        self._queues.pop(session_id, None)
        logger.info(f"SSE session removed: {session_id}")

    async def emit(self, session_id: str, event: str, data: dict) -> None:
        """Emit an SSE event to a session's queue."""
        queue = self._queues.get(session_id)
        if queue:
            payload = json.dumps({"event": event, "data": data}, ensure_ascii=False)
            await queue.put(payload)

    async def event_stream(self, session_id: str) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE payloads for a session.
        EventSourceResponse from sse_starlette adds 'data:' prefix automatically.
        """
        queue = self._queues.get(session_id)
        if not queue:
            yield json.dumps({"error": "Session not found"})
            return

        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=60)
                yield payload  # EventSourceResponse adds the 'data:' prefix
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield {"comment": "heartbeat"}  # SSE comment, not data


# Global singleton
sse_manager = SSEEventManager()
