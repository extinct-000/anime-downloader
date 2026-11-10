from urllib.parse import urljoin
import m3u8
import base64
from m3u8 import PlaylistList, Playlist, M3U8
from pathlib import Path
from Utils.model import Episode, Stream, EpisodeMetrics
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from bs4 import BeautifulSoup, ResultSet, Tag
from rich.console import Console
import asyncio
from Utils.requests import fetch
from aiohttp import ClientSession
from asyncio import Semaphore

from contextlib import contextmanager
from time import monotonic


@contextmanager
def track_stage(metrics: EpisodeMetrics, stage: str):
    started = monotonic()
    metrics.current_stage = stage

    try:
        yield
    finally:
        elapsed = monotonic() - started

        metrics.stage_times[stage] = (
            metrics.stage_times.get(stage, 0.0) + elapsed
        )

HEADERS: dict[str, str] = {
    "accept"                   : "text/html,application/xhtml+xml,application/xml;q=0.9,image/jxl,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language"          : "en-US,en;q=0.5",
    "cache-control"            : "max-age=0",
    "priority"                 : "u=0, i",
    "upgrade-insecure-requests": "1",
    "cookie"                   : "cf_clearance=CnI1AY5BUe8vn6_rEBL9_4xwtSwvolw1JR5sLj_cPI9iAH7Niva2WxH9d0dW2hBggn8jQB_nzBQ_IdgfBOjOX4xrOG68bga-jnDn_9SUUmJj6Yq93sAbLw3pDjqK868SVy_efWZ4Oyh1Y8WdFoxfaPa5n9Cn22nSR6ogUc-99O2L1aYwgGLqYJ2jztxCzsBfRpR1AoEWrYBMR8Y3amcQu0GpVZfKqE_O7h1VQ_gmiusi5g4_DVNmEan6fTQrg9uhQK8guhNI9sBLNox4rc50cTmTLwfb9-7A4mdyVtoy9w",
    "Referer"                  : "https://animekhor.org/",
}


ANIMEKHOR  : Semaphore = Semaphore(10)
OKRU       : Semaphore = Semaphore(5)

OKRU_CDN   : Semaphore = Semaphore(4)

console    : Console   = Console()

FOLDER_NAME: str


@dataclass
class Episode_CTX:
    name : str
    links: dict[str, str]


ServerExtractor = Callable[[str, ClientSession, str, Path,EpisodeMetrics], Awaitable[Episode | None]]


async def okru(
    url: str, session: ClientSession, name: str, folder_path: Path,metrics : EpisodeMetrics
) -> Episode | None:

    if Path(folder_path / (name + ".mkv")).exists():
        return None

    def get_best_format(playlist: list[PlaylistList]) -> Playlist:
        return max(
            playlist,
            key=lambda f: (f.stream_info.bandwidth or 0, f.stream_info.resolution[0] or 0,),  # ty: ignore[unresolved-attribute]
        )  # ty: ignore[no-matching-overload, invalid-return-type]

    if "https:" not in url:
        url = "https:" + url

    headers = {
        "accept"            : "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-encoding"   : "gzip, deflate, br, zstd",
        "accept-language"   : "en-US,en;q=0.6",
        "sec-ch-ua-platform": "Linux",
        "sec-fetch-dest"    : "document",
        "sec-fetch-mode"    : "navigate",
        "sec-fetch-user"    : "?0",
        "user-agent"        : "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    }
    response_html = await fetch(
        url       = url,
        SESSION   = session,
        semaphore = OKRU,
        headers   = headers,
        metrics   = metrics
    )

    soup: BeautifulSoup = BeautifulSoup(response_html, "lxml")

    data_option = soup.find(
        "div",
        attrs={
            "class"      : "vid-card_cnt h-mod",
            "data-module": "OKVideo",
        },
    ).get("data-options")  # ty: ignore[unresolved-attribute]

    if not data_option:
        return None

    m3u8_manifest: str | None

    for value in reversed(data_option.split(",")):  # ty: ignore[unresolved-attribute]
        if (
            "hlsManifestUrl" in value and "video.m3u8" in value
        ) or "ondemandHls" in value:

            m3u8_manifest = value.split('":"')[1]
            break

    try:
        m3u8_manifest = m3u8_manifest[:-1]
    except:
        console.print("url: ", url)
        console.print("name: : ", name)
        console.print(data_option)
    m3u8_manifest = m3u8_manifest.replace("\\u0026", "&")
    m3u8_manifest = m3u8_manifest.replace("%20", "")


    response_m3u8 = await fetch(
        url       = m3u8_manifest,
        SESSION   = session,
        semaphore = OKRU_CDN,
        headers   = headers,
        metrics   = metrics
    )

    if not response_m3u8.startswith("#EXTM3U"):
        response_m3u8 = base64.b64decode(response_m3u8, validate=True)

    try:
        playlist                  : M3U8     = m3u8.loads(response_m3u8)

        video_manifest_master_m3u8: Playlist = get_best_format(playlist.playlists)

        video                     : Stream   = Stream(
            link         = urljoin(m3u8_manifest, video_manifest_master_m3u8.uri),
            headers      = [f"{k}:{v}" for k, v in headers.items()],
            headers_dict = headers,
        )

    except Exception:
        console.print("error")
        raise

    return Episode(
        name     = name,
        video    = video,
        audio    = None,
        subtitle = None
    )


async def get_episodes(url: str, session: ClientSession):

    response: Any = await fetch(
        SESSION   = session,
        semaphore = ANIMEKHOR,
        url       = url,
        headers   = HEADERS
    )

    soup         : BeautifulSoup  = BeautifulSoup(response, "lxml")
    a            : ResultSet[Tag] = soup.find_all("a")

    episodes_link: list[str]      = []

    for tag in a:
        if tag.find(
            "div",
            attrs={
                "class": "epl-num",
            },
        ):
            episodes_link.append(tag.get("href"))  # ty: ignore[invalid-argument-type]

    return episodes_link


async def extract(
    SERVERS    : dict[str, ServerExtractor],
    session    : ClientSession,
    name       : str,
    url        : str,
    folder_path: Path,
    metrics    : EpisodeMetrics
) -> Episode | None:

    console.print("Extracting ... ")

    if Path(folder_path / (name + ".mkv")).exists():
        return None

    with track_stage(metrics,"extract_link"):
        ctx: Episode_CTX = await extract_link(url, session, name,metrics)

    console.print("Extracted ... links")

    for server, extractor in SERVERS.items():
        link = ctx.links.get(server)

        if not link:
            continue

        with track_stage(metrics,f"extract_{server}"):
            result: Episode | None = await extractor(
                link,
                session,
                name,
                folder_path,
                metrics,
            )
        console.print("Extracted ... server")

        if result is not None:
            metrics.finish()
            return result

    return None


async def extract_link(url: str, session: ClientSession, name: str,metrics : EpisodeMetrics) -> Episode_CTX:

    ctx     : Episode_CTX = Episode_CTX(name, {})

    response: Any         = await fetch(
        SESSION=session, url=url, semaphore=ANIMEKHOR, headers=HEADERS,metrics=metrics
    )

    soup  : BeautifulSoup = BeautifulSoup(response, "lxml")

    server: str           = ""
    for option in soup.find_all(
        "option",
        attrs={
            "data-index": True,
        },
    ):
        server += "".join(
            base64.b64decode(option.get("value"), validate=True).decode("utf-8")  # ty: ignore[invalid-argument-type]
        )

    soup: BeautifulSoup = BeautifulSoup(server, "lxml")

    for iframe in soup.find_all("iframe"):
        src = iframe.get("src")
        ctx.links[iframe.get("src").rsplit("/")[2]] = src  # ty: ignore[invalid-assignment, unresolved-attribute]

    return ctx


async def Scrape(
    url    : str,
    session: ClientSession,
    dir_   : Path
) -> tuple[list[Episode | None], str]:

    SERVERS: dict[str, ServerExtractor] = {
        "ok.ru": okru,
    }

    global FOLDER_NAME
    FOLDER_NAME       = url.rsplit("/")[4].replace("-", " ").capitalize()

    FOLDER_PATH: Path = dir_ / (FOLDER_NAME)

    console.print("Getting the Episodes")
    episodes_links = await get_episodes(url, session)

    console.print("Starting the Extraction Job")

    length = len(episodes_links)

    tasks  = []

    # tasks.append(
    #     asyncio.create_task(
    #         extract(
    #             SERVERS,
    #             session=session,
    #             name=f"Episode {length - 1}",
    #             url=episodes_links[1],
    #             folder_path=dir_ / (FOLDER_NAME),
    #         )
    #     )
    # )

    episodes_metrics : list[EpisodeMetrics] = []
    for idx, ep in enumerate(episodes_links):
        metrics : EpisodeMetrics = EpisodeMetrics(episode_id = f"Episode {length - idx}")
        episodes_metrics.append(metrics)
        tasks.append(
            asyncio.create_task(
                extract(
                    SERVERS,
                    session     = session,
                    name        = f"Episode {length - idx}",
                    url         = ep,
                    folder_path = FOLDER_PATH,
                    metrics     = metrics
                )
            )
        )

    episodes: list[Episode | None] = await asyncio.gather(*tasks)

    for epmet in episodes_metrics:
        console.print()
        console.print(epmet)

    return episodes, FOLDER_NAME


async def main():

    session: ClientSession = ClientSession()

    url    : str           = "https://animekhor.org/anime/oriental-martial-academy/"

    dir_   : Path          = Path("/home/extinct/Videos/Anime/")

    episodes = await Scrape(url, session, dir_)

    console.print(episodes)

    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
