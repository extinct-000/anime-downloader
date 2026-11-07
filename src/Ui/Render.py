from Dataobj import BaseEvent, StartEvent, EventType, ProgressEvent, CompletedEvent
from Ui.UIBus import UIBus
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

counter: int = 0


class UIController:
    def __init__(self, bus: UIBus):

        self._ids: dict[str, TaskID] = {}

        self._bus = bus

        self.title_style = "bold white"

        self.scraper: Progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(bar_width=1000),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            auto_refresh=False,
            expand=True,
        )

        self.download: Progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(bar_width=1000),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            auto_refresh=False,
            expand=True,
        )
        self.download_panel: Panel = Panel(
            self.download, title="[reverse]DOWNLOADING[/]", style=self.title_style
        )
        self.scrape_panel: Panel = Panel(
            self.scraper, title="[reverse]SCRAPING[/]", style=self.title_style
        )

        layout: Layout = Layout(name="root")
        layout.split_column(Layout(name="top"), Layout(name="bottom"))

        layout["top"].update(self.download_panel)
        layout["bottom"].update(self.scrape_panel)

    def run(self):
        with Live():
            while True:
                pass

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
                pass

            elif type is EventType.SCRAPER:
                pass
            return

        if isinstance(event, CompletedEvent):
            if type is EventType.DOWNLOAD:
                pass

            elif type is EventType.SCRAPER:
                pass
        pass

    pass


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
    asyncio.run(main())
