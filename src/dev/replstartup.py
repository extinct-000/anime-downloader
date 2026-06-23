from aiohttp.test_utils import setup_test_loop
from dataobj import Season, Stream
from aiohttp import ClientSession, StreamReader, ClientTimeout
from animesuge import Scrape
from rich.console import Console
from asyncio import Semaphore
from pathlib import Path
from urllib.parse import urljoin
from dataclasses import dataclass
from m3u8 import M3U8

import asyncio
import pathlib
import m3u8

console: Console = Console()

session: ClientSession | None = None


@dataclass
class Episode:
    name: str
    episode_link: str
    episode_link_headers: dict[str, str]
    sub_link: str
    sub_link_headers: dict[str, str]


global_video_semaphore: Semaphore = Semaphore(3)
global_mux_semaphore: Semaphore = Semaphore(4)
global_validation_semaphore: Semaphore = Semaphore(20)
global_subtitle_semaphore: Semaphore = Semaphore(20)
global_last_phase_validation_semaphore: Semaphore = Semaphore(40)


async def init():
    global session
    session = ClientSession()


async def cleanup():
    if session:
        await session.close()


async def fetch_with_global_first_validation_semaphore(
    url: str, session: ClientSession, headers: dict[str, str]
):

    async with global_validation_semaphore:
        async with session.get(url, headers=headers) as response:
            if response.status >= 200 and response.status <= 300:
                return await response.text()

            return response.status


async def fetch_with_global_last_phase_validation_semaphore_validation_(
    url: str, headers: dict[str, str], session
) -> bool:

    try:
        async with global_last_phase_validation_semaphore:
            async with session.get(url=url, headers=headers) as response:
                if not (response.status >= 200 and response.status <= 300):
                    return False

                async for line in response.content:
                    link = line.decode()
                    if not link.startswith("#"):
                        response.release()
                        break
    except:
        return False

    try:
        async with global_last_phase_validation_semaphore:
            async with session.get(url=link, headers=headers) as response:
                return response.status >= 200 and response.status <= 300
    except:
        return False


def clean(name: str) -> str:
    invalid = '<>:"/\\|?*'

    for c in invalid:
        name = name.replace(c, "_")

    return name


async def m3u8_validate_(
    url: str, session: ClientSession, headers: dict[str, str]
) -> dict[str, int | str | bool | dict[str, str]]:

    if not url:
        return {}

    response = await fetch_with_global_first_validation_semaphore(
        url=url, session=session, headers=headers
    )

    if type(response) != "str".__class__:
        return {}

    playlist: M3U8 = m3u8.loads(response)

    streams = []

    max_quality = 0

    for play in playlist.playlists:
        _, height = play.stream_info.resolution
        max_quality = max(height, max_quality)
        streams.append(
            {
                "quality": height,
                "uri": urljoin(url, play.uri),
                "bandwidth": play.stream_info.bandwidth,
                "valid": False,
                "headers": headers,
            }
        )

    max_streams = [stream for stream in streams if stream["quality"] == max_quality]

    tasks = []
    for stream in max_streams:
        tasks.append(
            asyncio.create_task(
                fetch_with_global_last_phase_validation_semaphore_validation_(
                    url=stream["uri"], headers=headers, session=session
                )
            )
        )

    results = await asyncio.gather(*tasks)

    for idx, valid in enumerate(results):
        max_streams[idx]["valid"] = valid
        if valid:
            return max_streams[idx]

    return {}


async def vtt_validate_(
    url: str, idx: int, session: ClientSession, headers: dict[str, str]
) -> tuple[bool, int]:

    if not url:
        return False, idx

    async with global_validation_semaphore:
        try:
            async with session.get(url, headers=headers) as response:
                return response.status >= 200 and response.status <= 300, idx

        except:
            return False, idx


async def to_Episode(
    streams: list[Stream], idx: int, name: str, session: ClientSession, dir_: Path
):

    video_task = []
    sub_task = []

    video: dict[str, int | str | bool] = None  # ty:ignore[invalid-assignment]

    sub: Stream = Stream(name="", episode_name="", link="", sub_link="", referrer="")

    for index, stream in enumerate(streams):
        headers = {
            "Origin": stream.referrer,
            "Referer": f"{stream.referrer}/",
        }

        video_task.append(
            asyncio.create_task(
                m3u8_validate_(stream.link, session=session, headers=headers)
            )
        )

        sub_task.append(
            asyncio.create_task(
                vtt_validate_(
                    stream.sub_link, idx=index, session=session, headers=headers
                )
            )
        )

    result_video: list[dict[str, int | str | bool]] = await asyncio.gather(*video_task)
    result_sub = await asyncio.gather(*sub_task)

    max_quality = 0

    for dict_valid in result_video:
        if dict_valid:
            max_quality = max(dict_valid["quality"], max_quality)

    for dict_valid in result_video:
        if dict_valid:
            if dict_valid["quality"] == max_quality:
                video = dict_valid
                break

    # NOTE: Very important for now , if there is no valid episode link to download then what's the point of subtitle
    if not video:
        return

    for valid, indx in result_sub:
        if valid:
            sub = streams[indx]
            break

    episode: Episode = Episode(
        name=name,
        episode_link=video["uri"],  # ty:ignore[invalid-argument-type]
        episode_link_headers=video["headers"],  # ty:ignore[invalid-argument-type]
        sub_link=sub.sub_link,
        sub_link_headers={
            "Origin": sub.referrer,
            "Referer": f"{sub.referrer}/",
        },
    )

    return episode
