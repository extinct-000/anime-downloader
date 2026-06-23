# _______________________import___________________________________
import urllib3
import os
import json
import aiohttp
import asyncio
import tree_sitter_javascript
import re

# _______________________From___________________________________
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag, ResultSet
from urllib3 import PoolManager, BaseHTTPResponse
from urllib.parse import urlparse
from rich.console import Console
from asyncio import Semaphore
from aiohttp import ClientSession
from tree_sitter import Query, Language, QueryCursor, Node, Tree, Parser
from dataobj import Server, Season, Media
from http import HTTPStatus


# _______________________Global Defaults___________________________________
console = Console()
semaphore: Semaphore = Semaphore(20)
headers_for_status = {"Range": f"bytes=0-{120}"}
JS_LANGUAGE = Language(tree_sitter_javascript.language())

parser: Parser = Parser(JS_LANGUAGE)
query: Query = Query(
    JS_LANGUAGE,
    """
value: (string(string_fragment)) @string
""",
)

cursor: QueryCursor = QueryCursor(query)


# ____________________________Functions__________________________


async def detect_if_direct_or_not_via__headers_helper(
    session: ClientSession, url
) -> bool:

    async with session.get(url) as response:
        for key, value in response.headers.items():
            if "accept-ranges" in key.lower():
                if "bytes" in value.lower():
                    return True

            if "content-type" in key.lower():
                if "application/octet-stream" in value.lower():
                    return True
    return False


async def media_phase2(medias: list[Media], session: ClientSession):

    task = []
    tasks = []
    ref = []

    async def inner_helper(link: str, session: ClientSession):
        if await detect_if_direct_or_not_via__headers_helper(session, url=link):
            return link

        async with semaphore:
            async with session.get(link) as response:
                return response.url.query_string[5:]

    for media in medias:
        for i, link in enumerate(media.link):
            task = asyncio.create_task(inner_helper(link, session))

            tasks.append(task)
            ref.append((media, i))

    results = await asyncio.gather(*tasks)

    for (media, idx), link in zip(ref, results):
        media.link[idx] = link

    console.print("[bold]Done Phase2-Media[/]")


async def get_valid_season(
    season: Season, semaphore: Semaphore, session: ClientSession
) -> Media:

    result_season: Media = Media(name=season.name, link=[], status=True)

    tasks = []

    async def inner_helper(list_of_server):
        temp = []

        for server in list_of_server:
            if server.link and "pixeldrain" not in server.link:
                status = await response_helper(server.link, semaphore, session)

                if status == HTTPStatus.PARTIAL_CONTENT:
                    return server.link
                    # result_season.link.append(server.link)
                    # break

                if status == HTTPStatus.OK:
                    temp.append(server.link)

        if not result_season.link:
            if temp:
                return temp.pop()
                # result_season.link.append(temp.pop())
                # return

            result_season.status = False
            return None

    for list_of_server in season.episode:
        tasks.append(inner_helper(list_of_server))

    result = await asyncio.gather(*tasks)
    result_season.link = [r for r in result if r]

    return result_season


def save_text(seasons: list[Season], filename: str = "Seasons"):
    i: int = 1
    list_of_servers: list[Server] = []

    list_of_links: list[str] = []

    for list_of_server in seasons[0].episode:
        for server in list_of_server:
            if "FSL Server".lower() in server.name.lower():
                console.print(server.name)
                list_of_links.append(server.link)

    with open("Season " + str(i) + ".txt", "w", encoding="utf-8") as file:
        for string in list_of_links:
            file.write(string + "\n")


def save_json(seasons: list[Season], filename: str = "Seasons"):
    with open(filename + ".json", "w", encoding="utf-8") as file:
        json.dump(to_dict(seasons), file, indent=4, ensure_ascii=False)


async def orchestra(url: str) -> tuple[list[Season], list[Media]]:

    # url = "https://vegamovies.market/download-the-boys-season-5-prime-video-480p-720p-1080p-2160p/"

    http: PoolManager = urllib3.PoolManager()
    response = http.request(
        "GET",
        url,
    )
    # response = http.request(
    #     "GET", "https://vegamovies.market/wp-content/uploads/2025/07/S-Line-Hindi-2025.jpg"
    # )
    soup: BeautifulSoup = BeautifulSoup(response.data, "lxml")

    session: ClientSession = ClientSession()
    seasons = await get_seasons(soup, session)
    # console.print("Just run get_seasons function")
    # console.print(seasons)
    # console.print("Just run get_seasons function")
    # console.print(seasons)
    await populate_episodes(seasons, session, http)

    result_media: list[Media] = []
    for season in seasons:
        result_season = await get_valid_season(season, semaphore, session=session)

        result_media.append(result_season)

        console.print("_____________________________________")
        console.print(result_season)
        console.print("_____________________________________")

    await media_phase2(medias=result_media, session=session)

    console.print("______________________________________")
    console.print(result_media)
    console.print("______________________________________")
    await session.close()

    return seasons, result_media


async def response_helper(url: str, semaphore: Semaphore, session: ClientSession):
    async with semaphore:
        async with session.get(url, headers=headers_for_status) as response:
            return response.status


async def fetch_response_helper(session: ClientSession, url) -> str:

    async with semaphore:
        async with session.get(url) as response:
            return await response.text(encoding="utf-8")


async def populate_episodes(
    seasons: list[Season], session: ClientSession, http: PoolManager
):

    tasks = []

    async def inner_helper2(server: Server):
        response: str = await fetch_response_helper(session, server.link)
        # response = http.request("GET", server.link)
        soup = BeautifulSoup(response, "lxml")
        links = await asyncio.to_thread(
            extract_link_vcloud, soup, http, urlparse(server.link)
        )
        # season.episode.append()
        return links

    async def inner_helper(season: Season, i):
        tasks_episodes = []
        for episode_server in season.episode_server:
            for server in episode_server:
                if "v-cloud" in server.name.lower():
                    tasks_episodes.append(inner_helper2(server))
                    console.print("Running populate_episodes async", i)
                    # response: str = await fetch_response_helper(session, server.link)
                    # # response = http.request("GET", server.link)
                    # soup = BeautifulSoup(response, "html.parser")
                    # season.episode.append(
                    #     extract_link_vcloud(soup, http, urlparse(server.link))
                    # )
                    break
        season.episode = await asyncio.gather(*tasks_episodes)

    i = 1
    for season in seasons:
        tasks.append(inner_helper(season, i))
        i = i + 1

    await asyncio.gather(*tasks)
    console.print(seasons)


async def get_seasons(soup: BeautifulSoup, session: ClientSession) -> list[Season]:

    seasons = get_all_seasons_crawl_link(soup)

    # console.print(seasons)
    # console.print(seasons[0].crawl_link[0].link)

    async def inner_helper(session: ClientSession, season: Season):
        for crawl in season.crawl_link:
            if "v-cloud" in crawl.name.lower():
                server = crawl
                break
            else:
                server = season.crawl_link[0]

        response: str = await fetch_response_helper(session, server.link)
        # response = http.request("GET", server.link)
        # console.print(server.link)

        soup = BeautifulSoup(response, "lxml")

        servers = get_per_episode_secondphase_link(soup)
        season.episode_server = servers

    tasks = []

    for season in seasons:
        tasks.append(inner_helper(session, season))
        # for crawl in season.crawl_link:
        #     if "v-cloud" in crawl.name.lower():
        #         server = crawl
        #         break
        #     else:
        #         server = season.crawl_link[0]
        #
        # response = http.request("GET", server.link)
        # # console.print(server.link)
        #
        # soup = BeautifulSoup(response.data, "html.parser")
        #
        # servers = get_per_episode_secondphase_link(soup)
        # season.episode_server = servers

        # console.print(season)

    # console.print(seasons)
    await asyncio.gather(*tasks)

    return seasons


def get_all_seasons_crawl_link(soup: BeautifulSoup) -> list[Season]:
    list_of_heading = soup.find_all("h3")
    # heading, server, index = get_highest_1080p_firstphase_link(list_of_heading)
    # console.print(soup.find_all())

    # console.print(soup.find_all("h3"))
    # console.print(heading.find_next("h3").text)

    seasons: list[Season] = []
    # console.print("++++++++++++++++++++++++++++++++++")
    # console.print(heading)
    # console.print("++++++++++++++++++++++++++++++++++")

    def inner_helper(list_of_heading) -> Tag | None:
        heading, server, index = get_highest_1080p_firstphase_link(list_of_heading)

        if not server:
            return heading

        season: Season = Season(
            name=heading.text, crawl_link=server, episode_server=[], episode=[]
        )

        seasons.append(season)
        del list_of_heading[index:]
        inner_helper2(list_of_heading)
        return heading

    def inner_helper2(list_of_heading):

        for i in range(len(list_of_heading) - 1, -1, -1):
            head_tag: Tag = list_of_heading[i]
            head_tag_text: str = head_tag.text.lower()

            if (
                # heading
                # and (n := heading.find_next("h3"))
                "720p"
                in head_tag_text  # and "season" in list_of_heading[i].text.lower()
                and "[" in head_tag_text
                and "]" in head_tag_text
                and (
                    "b/e" in head_tag_text
                    or "gb" in head_tag_text
                    or "mb" in head_tag_text
                )
            ):
                break
            del list_of_heading[i]

    # console.print(heading.text)
    heading = inner_helper(list_of_heading)
    # console.print("+++++++++++insides crawl_seasons+++++++++++++++++++")
    # console.print(heading.text)
    # console.print("+++++++++++insides crawl_seasons+++++++++++++++++++")
    # heading = inner_helper(heading.find_next("h3"))
    # console.print(heading.text)
    # heading = inner_helper(heading.find_next("h3"))
    # console.print(heading.text)
    # heading = inner_helper(heading.find_next("h3"))
    # console.print(heading.text)

    # console.print(heading)

    while "season" in (n := heading.text.lower()) and "B/E]".lower() in n:
        # console.print(heading)
        heading = inner_helper(list_of_heading)
        if not heading:
            break

    # season.crawl_link.extend(server)

    # heading1, server1 = get_highest_1080p_firstphase_link(heading.find_next("h3"))
    # console.print(heading1.text)
    # console.print(server1)
    console.print(seasons)
    return seasons


def extract_link_filepress(
    http: PoolManager, url: str, response: BaseHTTPResponse
) -> str:

    url2: str = response.url
    url: str = response.url

    # ---------------------

    urlparsed = urlparse(url)

    id: str = urlparsed.path.partition("file/")[-1]

    url = (
        urlparsed.scheme + "://" + urlparsed.hostname + "/api/" + "file/" + "get/" + id
    )

    # console.print((urlparsed.hostname))

    # console.print(id)
    # console.print(url)

    # https://new3.filepress.wiki/api/file/get/69f4efbc2fa72da218af4acc

    headers = {
        "Host": urlparsed.hostname,
        "User-Agent": "Mozilla/6.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=1.9",
        # "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/json",
        "Origin": "https://" + urlparsed.hostname,
        "Sec-GPC": "2",
        "Connection": "keep-alive",
        "Referer": url2,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=1",
        "TE": "trailers",
    }

    json = {
        "id": id,
        "method": "cloudR2Downlaod",
        "captchaValue": "",
    }

    response = http.request(
        "GET",
        url=url,
        # json=json,
        headers=headers,
    )

    name: str = response.json()["data"]["name"]

    # console.print(response.data.decode("utf-8"))
    # console.print(response.json())
    # console.print(name)

    # console.print(url2)

    # -----

    response = http.request(
        "POST",
        url=urlparsed.scheme + "://" + urlparsed.hostname + "/api/file/downlaod/",
        headers=headers,
        json=json,
    )
    download_id: str = response.json()["data"]["downloadId"]
    # console.print(response.json())

    new_referrer: str = (
        urlparsed.scheme + "://" + urlparsed.hostname + "/download/" + name
    )
    # console.print(new_referrer)

    headers = {
        "Host": urlparsed.hostname,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        # "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/json",
        "Origin": "https://" + urlparsed.hostname,
        "Sec-GPC": "1",
        "Connection": "keep-alive",
        "Referer": new_referrer,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=0",
        "TE": "trailers",
    }

    json2 = {
        "captchaValue": "",
        "id": download_id,
        "method": "cloudR2Downlaod",
    }
    url = urlparsed.scheme + "://" + urlparsed.hostname + "/api/file/downlaod2/"

    # console.print(url)

    response = http.request(
        "POST",
        url=url,
        json=json2,
        headers=headers,
    )

    return response.json()["data"]


def extract_link_vcloud(
    soup: BeautifulSoup, http: PoolManager, url_parsed
) -> list[Server]:

    script: Tag

    code: str = None
    # console.print(soup.find_all())

    for script in soup.find_all("script"):
        if (
            script
            and type(script.get("type")) == type("str")
            and "text/javascript" in script.get("type")
            and url_parsed.path in script.text
        ):
            # console.print(
            #     "++++++++++++++++++inside extract_link_vcloud++++++++++++++++++++++++++++++++"
            # )
            code = script.text
            # console.print(code)
            # console.print(
            # "++++++++++++++++++inside extract_link_vcloud++++++++++++++++++++++++++++++++"
            # )
            break

    if not code:
        return []

    tree: Tree = parser.parse(code.encode("utf-8"))
    root: Node = tree.root_node

    captures: dict = cursor.captures(root)

    # console.print(captures)

    list_of_variable: list = [
        variable.text.decode("utf-8") for variable in captures.get("string", [])
    ]

    link: str

    for string in list_of_variable:
        if url_parsed.path in string:
            link = string
            break

    link = link[1:-1]

    # console.print(list_of_variable)
    # console.print(link)

    # http2 = urllib3.PoolManager()
    response = http.request("GET", link)

    download_identifier: str = "fa-file-download"

    list_of_server: list[Server] = list()

    soup: BeautifulSoup = BeautifulSoup(response.data, "lxml")

    a: ResultSet[Tag] = soup.find_all("a")

    for atag in a:
        if (
            atag
            and (html_class := atag.find_next("i").get("class"))
            and download_identifier in html_class
        ):
            if "pixeldrain" in atag.get("href"):
                script: Tag = atag.find_next("script")

                script_text: bytes = script.text.encode("utf-8")

                captured: dict = cursor.captures(parser.parse(script_text).root_node)

                pixeldrain: str = captured["string"][0].text.decode("utf-8")

                list_of_server.append(Server(atag.text, pixeldrain))

                # console.print(pixeldrain)
                # console.print(script)

                continue

            list_of_server.append(Server(atag.text, atag.get("href")))
            # console.print(atag)

    return list_of_server
    # console.print(list_of_server)


def get_per_episode_secondphase_link(soup: BeautifulSoup) -> list[list[Server]]:

    list_of_server: list[list[Server]] = list()

    h4: Tag

    list_of_h4: list = list()

    for h4 in soup.find_all("h4"):
        if h4 and "episode" in h4.text.lower():
            list_of_h4.append(h4)

    # console.print(list_of_h4)

    p: Tag

    for h4 in list_of_h4:
        p = h4.find_next("p")
        # console.print(p)

        server: list = list()
        for a in p.find_all("a"):
            server.append(Server(a.text, a.get("href")))

        list_of_server.append(server)

    return list_of_server
    # console.print(list_of_server)


def get_highest_1080p_firstphase_link(
    list_of_heading: list[Tag],
) -> tuple[Tag | None, list[Server], int]:

    server: list[Server] = list()

    heading: Tag | None = None

    # while heading and "1080p" not in heading.text:
    #     heading = heading.find_next("h3")

    # console.print("++++++++++++++++++++++++++++++++++")
    # console.print(type(list_of_heading))
    # console.print("++++++++++++++++++++++++++++++++++")
    for i in range(len(list_of_heading) - 1, -1, -1):
        head_tag: Tag = list_of_heading[i]
        head_tag_text: str = head_tag.text.lower()

        if (
            # heading
            # and (n := heading.find_next("h3"))
            "1080p" in head_tag_text  # and "season" in list_of_heading[i].text.lower()
            and "[" in head_tag_text
            and "]" in head_tag_text
            and (
                "b/e" in head_tag_text or "gb" in head_tag_text or "mb" in head_tag_text
            )
        ):
            console.print("+++++++++++++++++first phase++++++++++++++++++++++++++")
            console.print(head_tag_text)
            console.print("+++++++++++++++++first phase++++++++++++++++++++++++++")
            heading = head_tag
            break

    # while (
    #     heading
    #     and (n := heading.find_next("h3"))
    #     and "1080p" in n.text
    #     and "season" in n.text.lower()
    #     and "b/e" in n.text.lower()
    # ):
    #     heading = n

    # console.print(heading)

    p: Tag | None = None

    if not heading:
        return heading, server, i

    p = heading.find_next()

    if not p:
        return heading, server, i
        # console.print("+++++++++++++++++++++++++++++++++++++++++++")
        # console.print(p.text)
        # console.print("+++++++++++++++++++++++++++++++++++++++++++")
    p = p.find_next("p")

    for a in p.find_all("a"):
        server.append(Server(a.text, a.get("href")))

    return heading, server, i
    # console.print(p.find_all("a")[0].text)
    # console.print(server)


def basic_down_image(img, http: PoolManager):

    link = img.get("src")
    url = urlparse(link)
    filename = os.path.basename(url.path)

    if (
        not link
        or link.startswith("data")
        or link.startswith("/")
        or link.startswith("\\")
    ):
        return

    response = http.request("GET", link)
    print(response.data)

    with open(filename, "wb") as image:
        image.write(response.data)


def parse_current_page_for_content(soup: BeautifulSoup):

    for a in soup.find_all("a"):
        # basicdown(img, http)
        # console.print(a)
        href = a.get("href")

        if href.startswith("https"):
            url = urlparse(href)

            if url.path.startswith("/download"):
                console.print(a.get("href"))


def to_dict(obj):
    if isinstance(obj, list):
        return [to_dict(i) for i in obj]
    if hasattr(obj, "__dict__"):
        return {k: to_dict(v) for k, v in obj.__dict__.items()}
    return obj


def sanitize_filename(name: str):
    return re.sub(r'[<>:"/\\|?*]', "_", name)


# ____________________________Functions__________________________


# ____________________________Controller__________________________
async def main():

    url: str = "https://vegamovies.market/download-from-season-1-4-web-series-hindi-english-480p-720p-1080p-web-dl/"
    # url: str = "https://vegamovies.market/download-the-chestnut-man-season-1-2-hindi-dubbed-web-series-480p-720p-1080p/"

    seasons, medias = await orchestra(url)

    parsed = urlparse(url)
    filename = (
        parsed.path[10:-1]
        .replace("-", " ")
        .title()
        .replace(" 480P ", "")
        .replace("720P", "")
    )

    save_json(seasons, filename)

    # http = PoolManager()
    # async with ClientSession() as session:
    #     response = await fetch_response_helper(
    #         session=session, url="https://vegamovies.market/"
    #     )
    #     soup = BeautifulSoup(response, "lxml")
    #     img = soup.find_all("img")
    #
    #     for image in img:
    #         basic_down_image(image, http=http)
    # console.status()

    for media in medias:
        length = len(media.link) - 1
        with open(sanitize_filename(media.name) + ".txt", "w") as file:
            for i, link in enumerate(media.link):
                file.write(link)
                if length != i:
                    file.write("\n")

    console.print(filename)


if __name__ == "__main__":
    asyncio.run(main())
