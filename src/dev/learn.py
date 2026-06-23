from rich.spinner import Spinner
from time import sleep

from rich.table import Column
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TransferSpeedColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
    FileSizeColumn,
    TotalFileSizeColumn,
    DownloadColumn,
    SpinnerColumn,
    RenderableColumn,
)

text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
bar_column = BarColumn(bar_width=None, table_column=Column(ratio=2))
progress = Progress(
    text_column,
    bar_column,
    TimeElapsedColumn(),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
    MofNCompleteColumn(),
    FileSizeColumn(),
    TotalFileSizeColumn(),
    # DownloadColumn(),
    SpinnerColumn(),
    RenderableColumn(),
    expand=True,
)

with progress:
    for n in progress.track(range(100)):
        sleep(0.1)
