from typing import Any
import asyncio


class UIBus:
    def __init__(self):

        self._queue = asyncio.Queue()

    async def emit(self, event: dict[str, Any]):
        pass

    async def emit_nowait(self, event: dict[str, Any]):
        pass

    async def emit():
        pass
