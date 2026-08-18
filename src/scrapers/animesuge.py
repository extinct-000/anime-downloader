from Crypto.Cipher.AES import new
from aiohttp.log import client_logger
import re
from bs4 import BeautifulSoup, Tag, ResultSet
from rich.console import Console
from aiohttp import ClientSession
from asyncio import Semaphore
from ..dataobj import Server, Season, Stream

from urllib.parse import quote, urlparse
from Crypto.Cipher import ARC4

import json.encoder
import base64
import codecs
import asyncio
import aiohttp

global_html_parser: str = "lxml"
global_semaphore: Semaphore = Semaphore(15)
console: Console = Console()

global_video_semaphore: Semaphore = Semaphore(2)
global_mux_semaphore: Semaphore = Semaphore(4)


async def fetch_with_no_semaphore(
    url: str, session: ClientSession, params=None, headers=None, json: bool = False
) -> str:
    delay = 1
    for attempt in range(4):
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if json:
                    return await response.json()
                return await response.text()
        except:
            if attempt == 3:
                raise
            delay *= 2
            await asyncio.sleep(delay)


async def fetch_with_global_semaphore(
    url: str, session: ClientSession, params=None, headers=None, json: bool = False
) -> tuple[str, int]:

    delay = 1
    for attempt in range(4):
        try:
            async with global_semaphore:
                console.print(1)
                async with session.get(url, params=params, headers=headers) as response:
                    if json and "application/json" in response.content_type:
                        return await response.json(), response.status
                    return await response.text(), response.status
        except:
            if attempt == 3:
                raise
            delay *= 2
            await asyncio.sleep(delay)


async def get_episode_servers(url: str, id: int, session: ClientSession) -> Season:

    url_parse = urlparse(url)

    if url_parse.hostname:
        hostname: str = url_parse.hostname
    else:
        hostname = "animesuge.re"

    # scheme = url_parse.scheme

    link = url.partition(url_parse.path)[0]
    # link = scheme + "://" + hostname

    name_ = url_parse.path.rpartition("/")[0].rpartition("/")
    last = len(name_) - 1
    name = name_[last]

    name = name.rpartition("-")[0].replace("-", " ").title()
    season: Season = Season(name=name, crawl_link=[], episode_server=[], episode=[])

    episode_list_request_url_path = f"/ajax/episode/list/{id}"

    new_url = link + episode_list_request_url_path

    headers = {
        "Host": hostname,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive",
    }

    vrf_params = {"vrf": generate_vrf(id)}

    result = await fetch_with_no_semaphore(
        new_url, session, params=vrf_params, headers=headers
    )

    # console.print(new_url)

    response_json = json.loads(result)
    soup: BeautifulSoup = BeautifulSoup(response_json["result"], global_html_parser)

    atags = soup.find_all("a")
    atags = atags[1:]

    episode_server: list = []

    new_url = link + "/ajax/server/list"

    async def inner_episode_parser(server: str) -> list[Server]:

        serverlist: list[Server] = []

        # console.print("server = ", server)

        new_result, _ = await fetch_with_global_semaphore(
            url=new_url,
            session=session,
            params={"servers": server},
            headers=headers,
            json=True,
        )
        soup: BeautifulSoup = BeautifulSoup(new_result["result"], global_html_parser)  # ty:ignore[invalid-argument-type]
        # console.print(soup.prettify())
        # console.print("_____________________________________________")
        divs: ResultSet[Tag] = soup.find_all("div")

        def inner_helper(word: str) -> Tag | None:

            for div in divs:
                if (
                    (n := div.get("class"))
                    and "server-type" in n
                    and word in div.get("data-type")  # ty:ignore[unsupported-operator]
                ):
                    return div

            return None

        server_div_parent: Tag | None = inner_helper("dub")

        if not server_div_parent:
            server_div_parent = inner_helper("sub")
            console.print(
                "_____________________________________SUB_____________________________"
            )

        # if not server_div_parent:
        #     console.print(divs)

        server_list_divs = server_div_parent.find_all("div")  # ty:ignore[unresolved-attribute]

        for server_div in server_list_divs:
            if n := server_div.get("class"):
                if "server" in n:
                    serverlist.append(
                        Server(
                            server_div.text.replace("\n", "").lower(),
                            server_div.get("data-link-id"),  # ty:ignore[invalid-argument-type]
                        )
                    )
                    # console.print(server_div)

        # console.print(server_div_parent.prettify())
        # console.print(serverlist)
        return serverlist

    task = []
    tasks = []

    for a in atags:
        title = a.get("title")
        data_id = a.get("data-ids")

        if not data_id:
            continue

        season.crawl_link.append(Server(name=title, link=data_id))  # ty:ignore[invalid-argument-type]
        task = asyncio.create_task(inner_episode_parser(data_id))  # ty:ignore[invalid-argument-type]
        tasks.append(task)
        episode_server.append((a.get("title"), a.get("data-ids")))
        # console.print(a.get("title"))

    season.episode_server = await asyncio.gather(*tasks)

    # console.print(season)
    return season

    # console.print(episode_server)


def generate_vrf(id: int) -> str:

    def safe_b64(data: bytes | str) -> str:

        if isinstance(data, str):
            data = data.encode()

        return base64.b64encode(data).decode().replace("/", "_").replace("+", "-")

    def shift_chars(text: str) -> str:
        out = ""

        for i, c in enumerate(text):
            x = ord(c)

            mod = i % 8

            if mod == 0:
                x -= 3
            elif mod == 1:
                x += 3
            elif mod == 2:
                x -= 4
            elif mod == 3:
                x += 2
            elif mod == 4:
                x -= 2
            elif mod == 5:
                x += 5
            elif mod == 6:
                x += 4
            elif mod == 7:
                x += 5

            out += chr(x)

        return out

    RC4_KEY = "ysJhV6U27FVIjjuk"

    encoded: str = quote(str(id), safe="~()*!.'")

    encrypted: bytes = ARC4.new(RC4_KEY.encode()).encrypt(encoded.encode())
    stage1: str = safe_b64(encrypted)
    shifted: str = shift_chars(stage1)
    stage2: str = safe_b64(shifted)

    return codecs.encode(stage2, "rot_13")


async def get_data_id(url: str, session: ClientSession):

    result = await fetch_with_no_semaphore(url, session)

    soup: BeautifulSoup = BeautifulSoup(result, global_html_parser)

    divs = soup.find_all("div")

    id: int = 0

    for div in divs:
        if n := div.get("data-id"):
            id = int(n)  # ty:ignore[invalid-argument-type]
            break

    return id


async def extract_megaplay(
    server_: str,
    site: str,
    session: ClientSession,
    name: str = "Episode",
    server_name: str = "Unkown",
) -> Stream:
    # GET
    # https:[//animesuge.cz/ajax/server?get=MTF1dkFtaW9BRTZPbzJJRElFZUZrOWdjeldjOERLaWNMMXFNbVB3WUJqK1JNM1ByWFJ6Mlpicnp2TE5VY0tGMlZkNlFSaWVSa1Roa1FKcjZtS0tlQmc9PQ

    header = {"X-Requested-With": "XMLHttpRequest"}
    headers_referrer = {"Referer": "https://animesuge.cz/"}
    response, _ = await fetch_with_global_semaphore(
        site + "/ajax/server",
        session=session,
        params={"get": server_},
        headers=header,
        json=True,
    )
    new_url = response["result"]["url"]  # ty:ignore[invalid-argument-type]

    console.print(new_url)

    response2, _ = await fetch_with_global_semaphore(
        new_url,
        session=session,
        headers=headers_referrer,
    )

    soup: BeautifulSoup = BeautifulSoup(response2, global_html_parser)

    data_id = ""

    for div in soup.find_all("div"):
        if n := div.get("data-id"):
            data_id = n
            break

    new_url_ = new_url.partition(urlparse(new_url).path)[0]

    response3, status = await fetch_with_global_semaphore(
        new_url_ + "/stream/getSources",
        session=session,
        params={"id": data_id},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": new_url,
        },
        json=True,
    )

    console.print(new_url_)

    console.print("inside megaplay", status)

    if not (status >= 200 and status <= 300):
        if "vidwish" in new_url_:
            return Stream(
                name="unavailable", episode_name="", link="", sub_link="", referrer=""
            )

        response3, status = await fetch_with_global_semaphore(
            new_url_ + "/stream/getSourcesNew",
            session=session,
            params={"id": data_id},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": new_url,
            },
            json=True,
        )

        if not (status >= 200 and status <= 300):
            iframes = soup.find_all("iframe")

            for iframe in iframes:
                src = iframe.get("src")
                if "megaplay" in src:  # ty:ignore[unsupported-operator]
                    break
            console.print(src)

            response2, _ = await fetch_with_global_semaphore(
                url=str(src),
                session=session,
                headers=headers_referrer,
            )

            soup: BeautifulSoup = BeautifulSoup(response2, global_html_parser)

            data_id = ""

            for div in soup.find_all("div"):
                if n := div.get("data-id"):
                    data_id = n
                    break

            response3, status = await fetch_with_global_semaphore(
                new_url_ + "/stream/getSourcesNew",
                session=session,
                params={"id": data_id},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": new_url,
                },
                json=True,
            )

    if not (status >= 200 and status <= 300):
        return Stream(
            name="unavailable", episode_name="", link="", sub_link="", referrer=""
        )

    # console.print(status)
    console.print(response3)

    console.print("megaplay is working ")

    sub_link = ""
    if tracks := response3["tracks"]:  # ty:ignore[invalid-argument-type]
        for track in tracks:
            if "english" in track["label"].lower():
                sub_link = track["file"]
                break

    return Stream(
        name=server_name,
        episode_name=name,
        referrer=new_url_,
        link=response3["sources"]["file"],  # ty:ignore[invalid-argument-type]
        sub_link=sub_link,
    )


async def get_season(url: str, session):

    url_parsed = urlparse(url)
    console.print()
    site = url.partition(url_parsed.path)[0]

    id: int = await get_data_id(url, session)
    season = await get_episode_servers(url, session=session, id=id)

    tasks = []
    tasks2 = []

    for idx, servers in enumerate(season.episode_server):
        for server in servers:
            if "megaplay" in server.name:
                task = asyncio.create_task(
                    extract_megaplay(
                        server.link,
                        site,
                        session=session,
                        name=season.crawl_link[idx].name,
                        server_name=server.name,
                    )
                )
                tasks.append(task)

            if "vidwish" in server.name:
                task2 = asyncio.create_task(
                    extract_megaplay(
                        server.link,
                        site,
                        session=session,
                        name=season.crawl_link[idx].name,
                        server_name=server.name,
                    )
                )
                tasks2.append(task2)

    result1 = await asyncio.gather(*tasks)
    result2 = await asyncio.gather(*tasks2)
    season.episode = [list(x) for x in zip(result1, result2)]
    # season.episode = result2
    console.print("orchestra is working")

    return season


def save_for_ytdlp(season: Season):

    with open("animesuge_links.txt", "w") as file:
        for idx, stream in enumerate(season.episode):
            save = stream.link + "\n"  # ty:ignore[unresolved-attribute]
            file.write(save)
            # console.print(filename)

    with open("animesuge_subs.txt", "w") as file:
        for idx, stream in enumerate(season.episode):
            save = stream.sub_link + "\n"  # ty:ignore[unresolved-attribute]
            file.write(save)
            # console.print(filename)


async def Scrape(url: str, session: ClientSession) -> Season:

    season = await get_season(url, session=session)
    # save_for_ytdlp(season)

    # id: int = await get_data_id(url, session)
    # console.print(id)
    #
    # vrf: str = generate_vrf(id)
    # console.print(vrf)
    #
    # megaplay = "MTF1dkFtaW9BRTZPbzJJRElFZUZrOWdjeldjOERLaWNMMXFNbVB3WUJqOGdCT1JkdmlSZzZXQUg2ZjhSZ2RuMEEvVTk3bUxXeHNMYUo1SWl2THhyZkE9PQ"
    #
    # stream = await extract_megaplay(megaplay, session=session)
    # console.print(stream)

    # await get_episode_servers(url, session=session, id=id)

    return season


async def main():
    url = "https://animesuge.re/watch/the-ogre-s-bride-wdtjt/ep-6"

    # NOTE: Session must be created inside event loop
    session: ClientSession = ClientSession()

    console.print("It is working")
    season = await get_season(url, session=session)
    # save_for_ytdlp(season)
    console.print(season)

    # id: int = await get_data_id(url, session)
    # console.print(id)
    # await init()
    #
    # vrf: str = generate_vrf(id)
    # console.print(vrf)
    #
    # megaplay = "MTF1dkFtaW9BRTZPbzJJRElFZUZrOWdjeldjOERLaWNMMXFNbVB3WUJqOGdCT1JkdmlSZzZXQUg2ZjhSZ2RuMEEvVTk3bUxXeHNMYUo1SWl2THhyZkE9PQ"
    #
    # stream = await extract_megaplay(megaplay, session=session)
    # console.print(stream)

    # await get_episode_servers(url, session=session, id=id)

    await session.close()


# async def adhoc_development():
#
#     url = "https://animesuge.cz/anime/rilakkuma-lxdgk/ep-9"
#
#     await init()  # ty:ignore[unresolved-reference]
#
#     season = await get_season(url, session=session)  # ty:ignore[unresolved-reference]
#
#     test_server = "MTF1dkFtaW9BRTZPbzJJRElFZUZrOWdjeldjOERLaWNMMXFNbVB3WUJqK1 JNM1ByWFJ6Mlpicnp2TE5VY0tGMmpFcGswL0R4cWVQVVZJTGQ1UjFoT1E9PQ"
#
#     # server_ = test_server
#     # site = "https://animesuge.cz"
#     # session = session  # ty:ignore[invalid-argument-type]
#     # name = "Episode"
#     # server_name = "megaplay"
#
#     console.print(stream)
#
#     await cleanup()  # ty:ignore[unresolved-reference]


if __name__ == "__main__":
    asyncio.run(main())
