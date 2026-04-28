from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator


class SSEEmitter:
    """SSE 이벤트를 생성하는 헬퍼"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()

    def emit(self, event: str, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        self._queue.put_nowait(f"event: {event}\ndata: {payload}\n\n")

    def done(self) -> None:
        self._queue.put_nowait(None)

    async def stream(self) -> AsyncGenerator[str, None]:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item
