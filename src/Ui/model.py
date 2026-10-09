from dataclasses import dataclass, field


@dataclass
class MuxState:
    pass


@dataclass
class ScrapeState:
    pass


@dataclass
class DownloadState:
    pass


@dataclass
class UIState:
    mux      : dict[str, MuxState]            = field(default_factory=dict)
    downloads: dict[str, DownloadState]       = field(default_factory=dict)
    scrape   : dict[str, ScrapeState]         = field(default_factory=dict)
