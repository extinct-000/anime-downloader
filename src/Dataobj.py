import aria2p
from aiohttp import ClientSession
from typing import Literal
from dataclasses import dataclass
from pathlib import Path


# FIXME: Refactor the vegamovie.py for the new Stream Implementation
@dataclass
class Stream:
    link: str
    headers: list[str]
    headers_dict: dict[str, str]


@dataclass
class Direct:
    link: str
    headers: list[str]


@dataclass
class Mux_Info_:
    filename: str
    temp: Path
    m3u8_segments_local: str


@dataclass
class Episode:
    name: str  # use the clean function from the utils to remove problematics filenames e.g episode.name = clean(episode.name)
    video: Stream | Direct | None
    audio: Stream | None
    subtitle: Direct | None


@dataclass
class CTX:
    dir_: Path
    session: ClientSession
    client: aria2p.Client
    aria: aria2p.API


@dataclass
class Media:
    name: str
    link: list[str]
    status: bool


@dataclass
class Server:
    name: str
    link: str


@dataclass
class Season:
    name: str
    crawl_link: list[Server]
    episode_server: list[list[Server]]
    episode: list[list[Server]] | list[list[Stream]]


@dataclass
class UIEvent:
    category: Literal[
        "video",
        "subtitle",
        "mux",
    ]

    action: Literal[
        "queued",
        "started",
        "progress",
        "finished",
        "error",
    ]

    id: str

    title: str = ""

    completed: int = 0
    total: int = 0

    speed: str = ""
    eta: str = ""

    status: str = ""
