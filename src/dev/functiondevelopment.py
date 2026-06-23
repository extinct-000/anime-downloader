from urllib.parse import urljoin
from aiohttp import ClientSession
from rich.console import Console
from m3u8 import M3U8
from asyncio import Semaphore
import asyncio
import m3u8

console: Console = Console()
global_last_phase_validation_semaphore: Semaphore = Semaphore(40)
global_validation_semaphore: Semaphore = Semaphore(20)


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


async def m3u8_validate_(
    url: str, idx: int, session: ClientSession, headers: dict[str, str]
) -> dict[str, int | str | bool]:

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
                "idx": idx,
                "quality": height,
                "uri": urljoin(url, play.uri),
                "bandwidth": play.stream_info.bandwidth,
                "valid": False,
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


async def fetch_with_global_first_validation_semaphore(
    url: str, session: ClientSession, headers: dict[str, str]
):

    async with global_validation_semaphore:
        async with session.get(url, headers=headers) as response:
            if response.status >= 200 and response.status <= 300:
                return await response.text()

            return response.status


async def main():
    url = "https://cdn.mewstream.buzz/anime/d60e6dacf1c89065aa8738b5c569967b/4a630840dd91a0ad78db9ce019a59359/master.m3u8"

    headers = {
        "Origin": "https://megaplay.buzz",
        "Referer": "https://megaplay.buzz/",
    }

    async with ClientSession() as session:
        result = await m3u8_validate_(url=url, idx=1, session=session, headers=headers)

    if result:
        console.print(result)
    else:
        console.print("See there is no data".title())


if __name__ == "__main__":
    asyncio.run(main())
