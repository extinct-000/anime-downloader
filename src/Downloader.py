import Scrapers.myanimelive
import aiohttp
import sys
from m3u8.model import InitializationSection
from aiohttp import (
    ClientSession,
    StreamReader,
    ClientTimeout,
    TCPConnector,
    ClientConnectionResetError,
)
from Scrapers.animesuge import Scrape
from rich.console import Console
from asyncio import Semaphore
from asyncio.subprocess import Process
from pathlib import Path
from urllib.parse import urljoin
from dataclasses import dataclass
from m3u8 import M3U8
from Dataobj import Season, Stream, Server, Episode, CTX
from Scrapers.myanimelive import Scrape as myanime

import aria2p.api
import asyncio
import pathlib
import m3u8
import aria2p
import shutil
import base64
import re
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# Same constants from client.js
KEY_STR = "i?LMTAx0Q6,:}50U"
IV_STR = "W0;27ToaUpl_P%'c"

# Regex patterns from client.js
SEGMENT_PATH_RE = re.compile(r"/segment/([A-Za-z0-9_-]+)")

console: Console = Console()

RETRYABLE_ERRORS = (
    aiohttp.ClientConnectorError,
    aiohttp.ClientConnectorDNSError,
    aiohttp.ServerDisconnectedError,
    aiohttp.ConnectionTimeoutError,
    aiohttp.SocketTimeoutError,
    aiohttp.ClientOSError,
    aiohttp.ClientConnectionError,
    asyncio.TimeoutError,
    ClientConnectionResetError,
)

global_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
}


global_video_semaphore: Semaphore = Semaphore(3)
global_mux_semaphore: Semaphore = Semaphore(4)
global_validation_semaphore: Semaphore = Semaphore(10)
global_subtitle_semaphore: Semaphore = Semaphore(10)
global_last_phase_validation_semaphore: Semaphore = Semaphore(10)
global_m3u8__semaphore: Semaphore = Semaphore(5)


def pad_key_bytes(key_str: str) -> bytes:
    """Pad key to 32 bytes (AES-256)"""

    key_bytes = key_str.encode("utf-8")
    key = bytearray(32)
    length = min(32, len(key_bytes))
    key[:length] = key_bytes[:length]

    return bytes(key)


def b64url_decode(token: str) -> bytes:
    """Base64url decode (client.js style)"""
    # Replace URL-safe chars
    s = token.replace("-", "+").replace("_", "/")
    # Add padding
    pad = len(s) % 4
    if pad:
        s += "===="[: 4 - pad]
    return base64.b64decode(s)


def decrypt_segment_token(token: str) -> str:
    """
    Decrypt a segment token using AES-256-CBC.
    Same as client.js decryptToken().
    """
    key = pad_key_bytes(KEY_STR)
    iv = IV_STR.encode("utf-8")

    # Decode base64url token
    ciphertext = b64url_decode(token)

    # Decrypt AES-CBC
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    plaintext = cipher.decrypt(ciphertext)

    # Remove PKCS7 padding
    try:
        plaintext = unpad(plaintext, AES.block_size)
    except ValueError:
        # If unpad fails, try without (might already be clean)
        pass

    return plaintext.decode("utf-8")


def extract_segment_token(url: str) -> str | None:
    """Extract token from /segment/{token} URL"""
    match = SEGMENT_PATH_RE.search(str(url))
    return match.group(1) if match else None


def is_segment_url(url: str) -> bool:
    """Check if URL contains /segment/ path"""
    return bool(SEGMENT_PATH_RE.search(str(url)))


def resolve_segment_url(url: str) -> str:
    """
    Main function: detect if URL has /segment/, decrypt token, return real URL.
    If not a segment URL, returns original URL unchanged.
    """
    if not url or not is_segment_url(url):
        return url

    token = extract_segment_token(url)
    if not token:
        return url

    real_url = decrypt_segment_token(token)
    return real_url


async def fetch_with_global_first_validation_semaphore(
    url: str, session: ClientSession, headers: dict[str, str]
):

    delay = 1
    for attempt in range(4):
        try:
            async with global_validation_semaphore:
                async with session.get(url, headers=headers, ssl=False) as response:
                    if response.status >= 200 and response.status <= 300:
                        return await response.text()

                    return response.status

        except RETRYABLE_ERRORS as e:
            if attempt == 4:
                raise
            await asyncio.sleep(delay)
            delay *= 2
            console.print(e)
        except:
            return False

    return False


async def fetch_with_global_last_phase_validation_semaphore_validation_(
    url: str, headers: dict[str, str], session
) -> bool:  # ty:ignore[invalid-return-type]

    delay: int = 1

    try:
        async with global_last_phase_validation_semaphore:
            async with session.get(url=url, headers=headers, ssl=False) as response:
                if not (response.status >= 200 and response.status <= 300):
                    return False

                async for line in response.content:
                    link = line.decode()
                    if not link.startswith("#"):
                        response.release()
                        break
    except:
        return False

    for attempt in range(4):
        try:
            async with global_last_phase_validation_semaphore:
                async with session.get(
                    url=resolve_segment_url(link), headers=headers, ssl=False
                ) as response:
                    return response.status >= 200 and response.status <= 300
        except RETRYABLE_ERRORS as e:
            if attempt == 4:
                raise
            await asyncio.sleep(delay)
            delay *= 2

        except:
            return False


async def init_aria() -> tuple[aria2p.API, aria2p.Client, Process] | None:
    j = 127

    cmd = [
        "aria2c",
        "--enable-rpc",
        "-x",
        "1",
        "-s",
        "1",
        "-j",
        str(j),
        "-k",
        "32M",
        "--file-allocation=none",
        "--disk-cache=32M",
    ]

    try:
        aria_process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            # stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.STDOUT,
        )

        await asyncio.sleep(1)
        console.print("[green bold]Aria Has start sucessfully[/]")

        client = aria2p.Client(
            host="http://localhost",
            port=6800,
            secret="",
        )

        aria = aria2p.API(client)

    except:
        return None

    return aria, client, aria_process


async def cleanup_aria(aria_process: Process):

    if aria_process and not aria_process.returncode:
        console.print("Stopping the aria2 process ...")
    try:
        aria_process.terminate()
        await asyncio.wait_for(aria_process.wait(), timeout=5.0)
        console.print("Stopped the aria2")
    except:
        aria_process.kill()
        console.print("Forced Killed")


async def process_episode(
    episode: Episode,
    dir_: Path,
    session: ClientSession,
    client: aria2p.Client,
    aria: aria2p.API,
):

    video_task = asyncio.create_task(
        aria_stream(
            episode=episode, session=session, dir_=dir_, client=client, aria=aria
        )
    )
    subtitle_task = asyncio.create_task(
        aria_direct(episode=episode, dir_=dir_, aria=aria, client=client)
        # download_subtitle(idx=idx, episode=episode, dir_=dir_)
    )

    video_result_tuple, subtitle = await asyncio.gather(video_task, subtitle_task)

    filename, temp_, segment = video_result_tuple

    return await mux(filename, segment, temp_, subtitle, dir_)


async def download_video(idx: int, episode: Episode, dir_: Path) -> str:

    filename = clean(episode.name)
    filename = f"{str(idx)} {filename}"

    output = str(dir_ / (f"{filename}.%(ext)s"))

    cmd = [
        "yt-dlp",
        episode.video_link,
        "-o",
        output,
        "-N",
        "4",
        "--add-header",
        f"Origin:{episode.video_link_headers['Origin']}",  # ty:ignore[invalid-argument-type]
        "--add-header",
        f"Referer:{episode.video_link_headers['Referer']}",  # ty:ignore[invalid-argument-type]
        "--external-downloader",
        "aria2c",
        "--external-downloader-args",
        "--check-certificate=false "
        f"--header=Origin:{episode.video_link_headers['Origin']}"  # ty:ignore[invalid-argument-type]
        f"--header=Referer:{episode.video_link_headers['Referer']}/"  # ty:ignore[invalid-argument-type]
        f"--header=User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0"
        "-x1 -s1 -j100 -k32M",
    ]

    console.print(f"[green]Video {filename}")

    async with global_video_semaphore:
        await run(cmd)

    return filename


async def aria_direct(
    episode: Episode, dir_: Path, aria: aria2p.API, client: aria2p.Client
) -> str:

    if not episode.sub_link:
        return ""

    filename: str = episode.name


    temp: Path = dir_ / filename

    temp.mkdir(exist_ok=True)

    out = filename + ".vtt"

    async with global_subtitle_semaphore:
        gid = client.add_uri(
            [episode.sub_link],
            options={
                "dir": str(temp),
                "out": out,
                "header": episode.sub_link_headers,
            },
        )
        console.print(gid)

        dl = aria.get_download(gid)

        while not dl.is_complete:  # ty:ignore[unresolved-attribute]
            if not dl.update():
                break

        console.print(f"[bold yellow]The sub file {filename} has completed[/]")

    return out


async def download_subtitle(idx: int, episode: Episode, dir_: Path) -> str:

    if not episode.sub_link:
        return ""

    filename: str = clean(episode.name)
    path: Path = dir_ / (str(idx) + " " + filename + ".vtt")

    console.print(f"[cyan]Subtitle {filename}")

    cmd = [
        "aria2c",
        "--check-certificate=false",
        f"--header=Origin:{episode.sub_link_headers['Origin']}",  # ty:ignore[invalid-argument-type]
        f"--header=Referer:{episode.sub_link_headers['Referer']}",  # ty:ignore[invalid-argument-type]
        f"--header=User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
        f"-d {dir_}",
        "-x1",
        "-s1",
        "-j8",
        "-k32M",
        f"-o {str(idx)} {filename}.vtt",
        episode.sub_link,
    ]

    async with global_subtitle_semaphore:
        await run(cmd)

    return filename


async def mux(filename: str, segment: str, temp_: Path, subtitle: str, dir_: Path):

    temp = dir_ / temp_

    vtt: Path = temp / (filename + ".vtt")
    mkv: Path = dir_ / (filename + ".mkv")

    has_sub = vtt is not None and vtt.exists()

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(segment),
    ]

    if has_sub:
        cmd.extend(["-i", str(vtt)])

    cmd.extend(
        [
            "-map",
            "0:v",
            "-map",
            "0:a?",
        ]
    )

    if has_sub:
        cmd.extend(
            [
                "-map",
                "1:s:0",
                "-c",
                "copy",
                "-c:s",
                "webvtt",
                "-disposition:s:0",
                "default",
            ]
        )
    else:
        cmd.extend(["-c", "copy"])

    cmd.append(str(mkv))

    async with global_mux_semaphore:
        await run(cmd)

    if mkv.exists():
        shutil.rmtree(temp, ignore_errors=True)


def clean(name: str) -> str:
    invalid = '–<>:"/\\|?*-'

    for c in invalid:
        name = name.replace(c, "_")

    return name


async def run(cmd: list[str]):

    console.print("____________________________________________________--")
    console.print(*cmd)
    console.print("____________________________________________________--")

    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )

    while True:
        line: bytes = await process.stdout.readline()  # ty:ignore[unresolved-attribute]

        if not line:
            break

        console.print(line.decode(errors="ignore").rstrip())

    await process.wait()

    if process.returncode != 0:
        raise RuntimeError(
            f"returncode  : {process.returncode} \nFailed: \n{' '.join(cmd)}"
        )


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
    # console.print(url, response)

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
                    url=stream["uri"],  # ty: ignore[invalid-argument-type]
                    headers=headers,
                    session=session,  # ty:ignore[invalid-argument-type]
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
    streams: list[Stream],
    idx: int,
    name: str,
    session: ClientSession,
    dir_: Path,
    client: aria2p.Client,
    aria: aria2p.API,
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
        headers.update(global_headers)

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

    result_video: list[dict[str, int | str | bool]] = await asyncio.gather(*video_task)  # ty:ignore[invalid-assignment]
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
        name=f"{str(idx)} {clean(name)}",
        video_link=video["uri"],  # ty:ignore[invalid-argument-type]
        video_link_headers=[f"{k}:{v}" for k, v in video["headers"].items()],  # ty:ignore[unresolved-attribute]
        video_link_headers_dict=video["headers"],  # ty:ignore[invalid-argument-type]
        sub_link=sub.sub_link,
        sub_link_headers=[f"Origin:{sub.referrer}", f"Referer:{sub.referrer}/"],
    )

    console.print("____________________________________________________--")
    console.print(episode)
    console.print("____________________________________________________--")

    return await process_episode(
        episode=episode, dir_=dir_, session=session, client=client, aria=aria
    )


async def startup(session: ClientSession, season: Season):


    links = []
    for stream in season.episode[0]:
        headers = {
            "Origin": stream.referrer,  # ty:ignore[unresolved-attribute]
            "Referer": f"{stream.referrer}/",  # ty:ignore[unresolved-attribute]
        }
        headers.update(global_headers)
        links.append(
            await m3u8_validate_(url=stream.link, session=session, headers=headers)
        )

    for valid in links:
        if valid:
            video = valid
            break
    if video:
        response = await fetch_with_no_semaphore(
            url=video["uri"],  # ty:ignore[invalid-argument-type]
            session=session,
            headers=video["headers"],  # ty:ignore[invalid-argument-type]
        )

    try:
        playlist: M3U8 = m3u8.loads(response)
    except:
        console.print("startup failed......")
        sys.exit(1)

    return min(len(playlist.segments), 128)


async def pipeline2(
    episodes: list[Episode], name: str, session: ClientSession, dir_: Path
):

    dir_ = dir_ / (clean(name))

    dir_.mkdir(exist_ok=True)

    tasks = []

    aria, client, process = await init_aria()  # ty:ignore[not-iterable]


    for episode in episodes:
        console.print(episode)
        task = asyncio.create_task(
            process_episode(
                episode=episode, dir_=dir_, session=session, client=client, aria=aria
            )
        )
        tasks.append(task)

    await asyncio.gather(*tasks)

    console.print("[green]Downloads completed")

    await cleanup_aria(process)
    console.print("[bold green]Everything Completed")


async def pipeline(season: Season, session: ClientSession, dir_: Path):

    dir_ = dir_ / (clean(season.name))

    dir_.mkdir(exist_ok=True)

    tasks = []

    aria, client, process = await init_aria()  # ty:ignore[not-iterable]


    for idx, streams in enumerate(season.episode):
        task = asyncio.create_task(
            to_Episode(
                streams=streams,  # ty:ignore[invalid-argument-type]
                idx=idx + 1,
                name=season.crawl_link[idx].name,
                session=session,
                dir_=dir_,
                client=client,
                aria=aria,
            )
        )
        tasks.append(task)

    await asyncio.gather(*tasks)

    console.print("[green]Downloads completed")

    await cleanup_aria(process)
    console.print("[bold green]Everything Completed")


async def main():

    name = "Aliens Among Immortals"
    session: ClientSession = ClientSession()

    episodes, _ = await myanime(name=name, session=session)

    await pipeline2(
        episodes=episodes,
        name=name,
        session=session,
        dir_=Path("C:/Users/coolk/Videos/Anime/"),
    )

    await session.close()


async def fetch_with_no_semaphore(
    url: str, session: ClientSession, headers: dict[str, str]
):

    delay = 1

    for attempt in range(5):
        try:
            async with global_m3u8__semaphore:
                async with session.get(url, headers=headers, ssl=False) as response:
                    console.print(response)
                    if response.status >= 200 and response.status <= 300:
                        return await response.text()

        except RETRYABLE_ERRORS as e:
            if attempt == 4:
                raise
            await asyncio.sleep(delay)
            delay *= 2
    return response.status


# async def get_size(
#     url: str,
#     session: ClientSession,
#     headers: dict[str, str],
# ) -> int:
#
#     async with session.head(url, headers=headers) as resp:
#         return int(resp.headers.get("Content-Length", 0))


async def aria_stream(
    episode: Episode,
    session: ClientSession,
    dir_: Path,
    client: aria2p.Client,
    aria: aria2p.API,
) -> tuple[str, Path, str]:

    response = await fetch_with_no_semaphore(
        url=episode.video_link,
        session=session,
        headers=episode.video_link_headers_dict,
    )

    # async with session.get(
    #     url="https://cdn.mewstream.buzz/anime/33c14ab38a8923e563e17b79e41693ba/b643ba74799b456c16464224dc8a1748/index-f1.m3u8",
    #     session=session,
    #     headers=episode.episode_link_headers_dict,
    # ) as resss:
    #     console.print(await resss.text())

    console.print(response)

    dir_.mkdir(exist_ok=True)

    # console.print(episode)

    filename: str = clean(episode.name)

    # filename: str = f"{str(idx)} {filename}"

    temp: Path = dir_ / filename

    segment_txt: Path = temp / "local.m3u8"

    temp.mkdir(exist_ok=True)

    if not response.startswith("#EXTM3U"):
        response = base64.b64decode(response, validate=True)

    try:
        playlist: M3U8 = m3u8.loads(response)
    except:
        console.print(episode)

    # console.print(response)
    # console.print(playlist.segments.uri)

    total_seg = len(playlist.segments.uri)

    # console.print(total_seg)

    multicall: list = []

    # episode_headers = [f"{k}:{v}" for k, v in episode.episode_link_headers.items()]
    # console.print(episode_headers)

    for i, seg in enumerate(playlist.segments):
        out = f"{filename} {i:05}.ts"
        out = clean(out)
        resolved_url = resolve_segment_url(seg.uri)

        multicall.append(
            {
                "methodName": "aria2.addUri",
                "params": [
                    [urljoin(episode.video_link, resolved_url)],
                    {
                        "dir": str(temp),
                        "out": out,
                        "header": episode.video_link_headers,
                    },
                ],
            }
        )
        seg.uri = out

    text = playlist.dumps()

    for i, map in enumerate(playlist.segment_map):
        out = f"{filename} {i:05}.mp4"
        out = clean(out)

        text = text.replace(f'#EXT-X-MAP:URI="{map.uri}"', f'#EXT-X-MAP:URI="{out}"')  # ty:ignore[unresolved-attribute]

        multicall.append(
            {
                "methodName": "aria2.addUri",
                "params": [
                    [urljoin(episode.video_link, map.uri)],  # ty:ignore[unresolved-attribute]
                    {
                        "dir": str(temp),
                        "out": out,
                        "header": episode.video_link_headers,
                    },
                ],
            }
        )
        map.uri = out  # ty:ignore[invalid-assignment]

    # playlist.dumps()
    console.print(playlist.dumps())

    with open(segment_txt, "w") as file:
        file.write(text)

    result = client.multicall(multicall)
    gids = [gid[0] for gid in result]  # ty:ignore[not-subscriptable]

    remaining = set(gids)
    console.print(aria.get_stats())

    while remaining:
        finished = set()

        total_speed = 0
        completed = 0

        for gid in remaining:
            try:
                dl = aria.get_download(gid)
                total_speed += dl.download_speed
                # completed += dl.completed_length

                if dl.is_complete or dl.is_removed or dl.has_failed:
                    finished.add(gid)

            except aria2p.client.ClientException:
                finished.add(gid)

        remaining -= finished

        eta = 0
        if total_speed > 0:
            remaining_bytes = sum(
                dl.total_length
                for dl in [aria.get_download(g) for g in remaining]
                if dl.total_length > 0
            )
            eta = remaining_bytes / total_speed
            console.print(f"{episode.name}|... | ETA: {eta:.1f}s")
            completed_segment = total_seg - len(remaining)

            percent = (completed_segment / total_seg) * 100

            console.print(
                f"{percent:.2f}%  | {total_speed / 1024 / 1024:.2f}MB/s | ETA: {eta:.1f}s"
            )

        # if total_speed != 0:

        await asyncio.sleep(1)

    console.print(f"[green bold]Completed {filename}[/]")

    async with global_video_semaphore:
        await asyncio.gather(
            *(
                asyncio.to_thread(strip_png_wrapper, Path(temp / map.uri))  # ty:ignore[unresolved-attribute]
                for map in playlist.segment_map
            )
        )
        await asyncio.gather(
            *(
                asyncio.to_thread(strip_png_wrapper, Path(temp / seg))
                for seg in playlist.segments.uri
            )
        )

    return filename, temp, str(segment_txt)


def strip_png_wrapper(path: Path):
    """Fix both types of corruption: extra byte + full PNG wrapper"""

    if not path.exists():
        return

    with open(path, "rb+") as file:
        data = file.read(16384)  # Read enough for header + PNG

        original_size = file.tell()

        ftyp_pos = data.find(b"ftyp")
        if ftyp_pos == 252 - 4:  # ftyp at position 248 (after 252-byte header)
            file.seek(252)
            payload = file.read()
            file.seek(0)
            file.write(payload)
            file.truncate()
            print(f"✓ Removed 252-byte header: {path.name}")
            return

        # === Case 1: Extra leading byte (like 0x0A) ===
        if data[0] == 0x0A and data[1:5] == b"\x00\x00\x00\x18":  # ftyp after one byte
            file.seek(1)
            payload = file.read()
            file.seek(0)
            file.write(payload)
            file.truncate()
            print(f"✓ Removed leading byte: {path.name}")
            return

        # === Case 2: Full PNG wrapper ===
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            iend_pos = data.find(b"IEND")
            if iend_pos != -1:
                start = iend_pos + 12  # IEND + CRC (4 bytes)
                file.seek(start)
                payload = file.read()
                file.seek(0)
                file.write(payload)
                file.truncate()
                print(f"✓ Removed PNG wrapper: {path.name}")
                return

        # === Case 3: Look for 'ftyp' anywhere near start ===
        ftyp_pos = data.find(b"ftyp")
        if 0 < ftyp_pos < 100:  # Found but not at position 0
            # Go back 4 bytes for box length
            file.seek(ftyp_pos - 4)
            payload = file.read()
            file.seek(0)
            file.write(payload)
            file.truncate()
            print(f"✓ Fixed offset to ftyp: {path.name}")
            return

        print(f"⚠ No change needed or unrecognized format: {path.name}")

if __name__ == "__main__":
    asyncio.run(main())
