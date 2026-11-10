from rich.console import Console
from Utils.model import BaseEvent, CompletedEvent
from typing import Any
import asyncio

console: Console = Console()


class UIBus:
    def __init__(self):

        self._queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self._latest = {}

    async def emit(self, event: BaseEvent) -> None:
        """Apply lifecycle events immdiately."""
        # if event_type in {"downloadComplete", "downloadFailed"}:
        #     self._latest.pop(download_id, None)
        #     self._finished.add(download_id)
        if isinstance(event, CompletedEvent):
            self._latest.pop(event.id, None)
        await self._queue.put(event)

    async def emit_progress(self, event: BaseEvent) -> None:
        """ """
        self._latest[event.id] = event

        pass

    async def flush(self, interval: float = 0.03) -> None:
        """Apply coalesced progress updates periodically"""

        # console.print("Flusher Started")
        while True:
            # console.print("Inside the loop of the Flusher")
            await asyncio.sleep(interval)
            # console.print("Inside the loop of the Flusher - After sleep")

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
