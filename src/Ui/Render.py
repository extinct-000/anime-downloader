from Dataobj import BaseEvent, StartEvent, EventType, ProgressEvent, CompletedEvent
from Ui.UIBus import UIBus, bus
import time
import asyncio

import pdb

from rich.layout import Layout
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.live import Live
from rich.table import Table
from rich.console import Console, Group

from rich.progress import (
    Progress,
    TaskID,
    TextColumn,
    TaskProgressColumn,
    BarColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from dataclasses import dataclass, field


console: Console = Console()


class UIController:
    def __init__(self, bus: UIBus):

        self._ids: dict[str, TaskID] = {}

        self._bus = bus

        self.title_style = "bold white"

        self.scraper: Progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(bar_width=1000),
            TaskProgressColumn(),
            TimeRemainingColumn(compact=True),
            auto_refresh=False,
            expand=True,
        )

        self.download: Progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(bar_width=1000),
            TaskProgressColumn(),
            TimeRemainingColumn(compact=True),
            auto_refresh=False,
            expand=True,
        )
        self.download_panel: Panel = Panel(
            self.download, title="[reverse]DOWNLOADING[/]", style=self.title_style
        )
        self.scrape_panel: Panel = Panel(
            self.scraper, title="[reverse]SCRAPING[/]", style=self.title_style
        )

        self._layout: Layout = Layout(name="root")
        self._layout.split_column(Layout(name="top"), Layout(name="bottom"))

        self._layout["top"].update(self.download_panel)
        self._layout["bottom"].update(self.scrape_panel)

    async def run(self):
        with Live(self._layout, refresh_per_second=60):
            while True:
                event: BaseEvent = await self._bus.receive()

                self.apply(event)

    def apply(self, event: BaseEvent):
        type = event.type

        if isinstance(event, StartEvent):
            if type is EventType.DOWNLOAD:
                self._ids[event.id] = self.download.add_task(event.title, total=100)

            elif type is EventType.SCRAPER:
                self._ids[event.id] = self.scraper.add_task(event.title, total=100)
            return

        if isinstance(event, ProgressEvent):
            if type is EventType.DOWNLOAD:
                self.download.update(self._ids[event.id], completed=event.completed)

            elif type is EventType.SCRAPER:
                self.scraper.update(self._ids[event.id], completed=event.completed)
            return

        if isinstance(event, CompletedEvent):
            if type is EventType.DOWNLOAD:
                self.download.remove_task(self._ids[event.id])

            elif type is EventType.SCRAPER:
                self.scraper.remove_task(self._ids[event.id])


async def main2():

    ui: UIController = UIController(bus)

    asyncio.create_task(bus.flush())
    asyncio.create_task(ui.run())

    id = "121"

    id2 = "122"

    id3 = "123"

    id4 = "124"

    await bus.emit(StartEvent(EventType.SCRAPER, id, "Episode 1"))

    await bus.emit(StartEvent(EventType.SCRAPER, id2, "Episode 1"))

    await bus.emit(StartEvent(EventType.DOWNLOAD, id3, "Episode 4"))

    await bus.emit(StartEvent(EventType.DOWNLOAD, id4, "Episode 5"))

    for num in range(101):
        event = ProgressEvent(EventType.SCRAPER, id, 3.3, 3.3, completed=num)

        event2 = ProgressEvent(EventType.SCRAPER, id2, 3.3, 3.3, completed=num + 2)

        event3 = ProgressEvent(EventType.DOWNLOAD, id3, 3.3, 3.3, completed=num)

        event4 = ProgressEvent(EventType.DOWNLOAD, id4, 3.3, 3.3, completed=num)

        await asyncio.sleep(0.03)

        await bus.emit_progress(event)
        await bus.emit_progress(event2)
        await bus.emit_progress(event3)
        await bus.emit_progress(event4)

    await asyncio.sleep(1)

    await bus.emit(CompletedEvent(EventType.SCRAPER, id2))

    await bus.emit(CompletedEvent(EventType.DOWNLOAD, id3))

    await asyncio.sleep(0.5)

    await bus.emit(CompletedEvent(EventType.SCRAPER, id))
    await bus.emit(CompletedEvent(EventType.DOWNLOAD, id4))
    # await asyncio.gather(task_flush)
    # await asyncio.gather(task_run)


async def main():

    title = "bold white"

    scraper: Progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(bar_width=1000),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        auto_refresh=False,
        expand=True,
    )
    download: Progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(bar_width=1000),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        auto_refresh=False,
        expand=True,
    )

    scrapers: list[TaskID] = []
    downloads: list[TaskID] = []

    download_panel: Panel = Panel(
        download, title="[reverse]DOWNLOADING[/]", style=title
    )
    scrape_panel: Panel = Panel(scraper, title="[reverse]SCRAPING[/]", style=title)

    layout: Layout = Layout(name="root")

    layout.split_column(
        Layout(name="top"),
        Layout(name="bottom"),
    )

    layout["top"].update(download_panel)
    layout["bottom"].update(scrape_panel)

    for ep in range(100):
        text = f"EPISODE------------------------------------------{ep + 1:02d}"

        scrapers.append(scraper.add_task(text[:15], total=100))

        downloads.append(download.add_task(text[:60], total=100))

    with Live(layout, refresh_per_second=60):
        while not (scraper.finished and download.finished):
            for taskid in scrapers:
                scraper.advance(taskid, 1)

            for taskid in downloads:
                download.advance(taskid, 1)

            time.sleep(0.03)

        # if download.finished:
        #     for taskid in downloads:
        #         download.reset(
        #             taskid,
        #             total=None,
        #             description="Muxing...",
        #             completed=0,
        #             start=False,
        #         )
        #
        #     while download.finished:
        #         for taskid in downloads:
        #             download.update(taskid, advance=1)
        #
        #         time.sleep(0.03)


if __name__ == "__main__":
    asyncio.run(main2())
