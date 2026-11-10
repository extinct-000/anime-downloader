from rich.panel import Panel
from dataclasses import dataclass, field
from time import monotonic
from enum import StrEnum
import aria2p
from aiohttp import ClientSession
from typing import Literal
from dataclasses import dataclass
from pathlib import Path


# FIXME : Refactor the vegamovie.py for the new Stream Implementation
@dataclass
class Stream:
    link                       : str
    headers                    : list[str]
    headers_dict               : dict[str, str]


@dataclass
class PreparedStream:
    stream_type                : str
    playlist_path              : Path
    segments_path              : list[Path]
    multicall                  : list[dict]
    segment_count              : int


@dataclass
class Direct:
    link                       : str
    headers                    : list[str]


@dataclass
class Mux_Info_                :
    out                        : Path
    temp                       : Path
    video                      : Path
    audio                      : Path | None
    subtitle                   : Path | None


@dataclass
class Episode                  :
    name                       : str  # use the clean function from the utils to remove problematics filenames e.g episode.name = clean(episode.name)
    video                      : Stream | Direct | None
    audio                      : Stream | None
    subtitle                   : Direct | None


@dataclass
class CTX:
    dir_                       : Path
    session                    : ClientSession
    client                     : aria2p.Client
    aria                       : aria2p.API


@dataclass
class Media:
    name                       : str
    link                       : list[str]
    status                     : bool


@dataclass
class Server:
    name                       : str
    link                       : str


@dataclass
class Season:
    name                       : str
    crawl_link                 : list[Server]
    episode_server             : list[list[Server]]
    episode                    : list[list[Server]] | list[list[Stream]]

class EventType(StrEnum):
    DOWNLOAD = "download"
    SCRAPER  = "scraper"
    MUX      = "muxing"

@dataclass
class BaseEvent:
    type                       : EventType

    id                         : str


@dataclass
class StartEvent(BaseEvent):
    title                      : str = ""


@dataclass
class ProgressEvent(BaseEvent) :
    eta                        : float
    speed                      : float
    completed                  : int


@dataclass
class CompletedEvent(BaseEvent):
    title                      : str = "Finished"






@dataclass
class EpisodeMetrics:
    episode_id    : str

    started_at    : float            = field(default_factory = monotonic)
    finished_at   : float | None     = None

    status        : str              = "pending"
    current_stage : str              = "waiting"

    bytes_received: int              = 0
    requests      : int              = 0

    stage_times   : dict[str, float] = field(default_factory = dict)

    @property
    def elapsed(self) -> float:
        end = self.finished_at or monotonic()
        return end - self.started_at

    @property
    def completed(self) -> bool:
        return self.finished_at is not None

    @property
    def average_speed(self) -> float:
        network_time = self.stage_times.get("network", 0.0)

        if network_time <= 0:
            return 0.0

        return self.bytes_received / network_time

    def format_duration(self,seconds: float) -> str:
        if seconds < 1:
            return f"{seconds * 1000:.2f} ms"

        if seconds < 60:
            return f"{seconds:.2f} s"

        minutes, seconds = divmod(seconds, 60)

        if minutes < 60:
            return f"{int(minutes)}m {seconds:.1f}s"

        hours, minutes = divmod(minutes, 60)
        return f"{int(hours)}h {int(minutes)}m {seconds:.1f}s"


    def format_bytes(self,size: int) -> str:
        units = ("B", "KB", "MB", "GB", "TB")

        value = float(size)

        for unit in units:
            if value < 1024 or unit == "TB":
                return f"{value:.2f} {unit}"

            value /= 1024

        return f"{value:.2f} TB"


    def format_speed(self,bytes_per_second: float) -> str:
        return f"{self.format_bytes(int(bytes_per_second))}/s"

    def finish(self, status: str = "completed"):
        self.finished_at = monotonic()
        self.status = status
        self.current_stage = "finished"

    def __rich__(self) -> Panel:
        
        color = "green"
        if self.status == "pending": 
            color = "red"

        lines = [
            f"[reverse][bold]Episode: [/bold]{self.episode_id}[/reverse]",
            f"[bold]Status               :[/] [{color}]{self.status}[/]",
            f"[bold]Total elapsed        :[/] {self.format_duration(self.elapsed)}",
            f"[bold]HTTP requests        :[/] {self.requests}",
            f"[bold]Data received        :[/] {self.format_bytes(self.bytes_received)}",
            f"[bold]Average network speed:[/] {self.format_speed(self.average_speed)}",
            "",
            "[reverse bold]Stage breakdown:[/]",
        ]

        max_stage_width = max(map(len,self.stage_times),default=0)
        for stage, duration in self.stage_times.items():
            percentage = (
                duration / self.elapsed * 100
                if self.elapsed > 0 else 0
            )

            lines.append(
                f"  {stage:<{max_stage_width}} :"
                f" {self.format_duration(duration):<10} "
                f"({percentage:.1f}%)"
            )

        return Panel("\n".join(lines),title=self.episode_id)
