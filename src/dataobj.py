from typing import Literal
from dataclasses import dataclass


@dataclass
class Episode:
    name: str
    episode_link: str
    episode_link_headers: list[str]
    episode_link_headers_dict: dict[str, str]
    sub_link: str
    sub_link_headers: list[str]


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
class Stream:
    name: str
    episode_name: str
    link: str
    sub_link: str
    referrer: str


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
