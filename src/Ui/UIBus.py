from Dataobj import BaseEvent
from typing import Any
import asyncio


class UIBus:
    def __init__(self):

        self._queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self._latest = {}

    async def emit(self, event: BaseEvent) -> None:
        """Apply lifecycle events immdiately."""
        # if event_type in {"downloadComplete", "downloadFailed"}:
        #     self._latest.pop(download_id, None)
        #     self._finished.add(download_id)
        await self._queue.put(event)

    async def emit_progress(self, event: BaseEvent) -> None:
        pass

    async def emit() -> None:
        pass

    async def flush(self, interval: float = 0.2) -> None:
        """Apply coalesced progress updates periodically"""
        while True:
            await asyncio.sleep(interval)

            batch = self._latest

            self._latest = {}

            for event in batch.values():
                await self._queue.put(event)

    async def receive(self) -> BaseEvent:
        return await self._queue.get()


def main():
    print("debuging related work...")
    pass


bus: UIBus = UIBus()


if __name__ == "__main__":
    main()
