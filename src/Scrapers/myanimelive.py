from datetime import datetime, UTC
from rich.console import Console

from aiohttp import ClientSession
from asyncio import Semaphore
from yt_dlp.networking.impersonate import ImpersonateTarget

from Dataobj import Season, Server, Episode
from typing import Any, Coroutine
from bs4.element import AttributeValueList
from bs4 import BeautifulSoup, Tag, ResultSet

import asyncio
import yt_dlp

console: Console = Console()

global_first_phase: Semaphore = Semaphore(4)
global_ytdlp: Semaphore = Semaphore(4)


#######################################################################

# NOTE:

#######################################################################

settings = {
    "id": "main",
    "ajaxurl": "https://myanime.live/?infinity=scrolling",
    "type": "scroll",
    "wrapper": "true",
    "wrapper_class": "infinite-wrap",
    "fo oter": "page",
    "click_handle": "1",
    "text": "Load more posts",
    "totop": "Scroll back to top",
    "currentday": datetime.now(UTC).strftime("%m.%d.%y"),
    "order": "DESC",
    "scripts": [],
    "styles": [],
    "google_analytics": "false",
    "offset": 1,
    "history": {
        "host": "myanime.live",
        "path": "/page/%d/",
        "use_trailing_slashes": "true",
        "parameters": "?s=Renegade+Immortal",
    },
    "query_args": {
        "s": "Renegade Immortal",
        "error": "",
        "m": "",
        "p": 0,
        "post_parent": "",
        "subpost": "",
        "subpost_id": "",
        "attachment": "",
        "attachment_id": 0,
        "name": "",
        "pagename": "",
        "page_ id": 0,
        "second": "",
        "minute": "",
        "hour": "",
        "day": 0,
        "monthnum": 0,
        "year": 0,
        "w": 0,
        "category_name": "",
        "tag": "",
        "cat": "",
        "tag_id": "",
        "author": "",
        "author _name": "",
        "feed": "",
        "tb": "",
        "paged": 0,
        "meta_key": "",
        "meta_value": "",
        "preview": "",
        "sentence": "",
        "title": "",
        "fields": "all",
        "menu_order": "",
        "embed": "",
        "category__in": [],
        "category__not_in": [],
        "category__and": [],
        "post__in": [],
        "post__not_in": [
            118926,
            118750,
            118562,
            118384,
            118191,
            117913,
            117679,
            117498,
            117281,
            117089,
        ],
        "post_name__in": [],
        "tag__in": [],
        "tag__not_in": [],
        "tag__and": [],
        "tag_slug__in": [],
        "tag_slug__and": [],
        "post_parent__in": [],
        "po st_parent__not_in": [],
        "author__in": [],
        "author__not_in": [],
        "search_columns": [],
        "posts_per_page": 10,
        "ignore_sticky_posts": "false",
        "suppress_filters": "false",
        "cache_results": "true",
        "update_post_term_cache": "true",
        "update_menu_item_cache": "false",
        "lazy_load_term_meta": "true",
        "update_post_meta_cache": "true",
        "post_type": "any",
        "nopaging": "false",
        "comments_per_page": "20",
        "no_found_rows": "false",
        "search_terms_count": 2,
        "search_terms": ["Renegade", "Immortal"],
        "search_orderby_title": [
            "wp_posts.post_title LIKE '{001423f049cc1e79a7330ca77fdbfe6d9bc7705ddc847fad4128fe0314b177d0}Renegade{001423f049cc1e79a7330ca77fdbfe6d9bc7705ddc847fad4128fe0314b177d0}'",
            "wp_posts.post_title LIKE '{001423f049cc1e79a7330ca77fdbfe6d9bc7705ddc847fad4128fe0314b177d0}Immortal{001423f049cc1e79a7330ca77fdbfe6d9bc7705ddc847fad4128fe0314b177d0}'",
        ],
        "order": "DESC",
    },
    "query_before": "2026-06-08 06:51:00",
    "last_post_date": "false",
    "body_class": "infinite-scroll neverending",
    "loading_text": "Loading new page",
    "stats": "blog=167246504\u0026host=myanime.live\u0026v=ext\u0026j=1:15.9-a.7\u0026x_pagetype=infinite-jetpack",
}

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "X-Requested-With": "XMLHttpRequest",
    # "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://myanime.live",
    "Sec-GPC": "1",
    "Alt-Used": "myanime.live",
    "sec-ch-ua-platform": "Linux",
    "Connection": "keep-alive",
    "sec-fetch-dest": "document",
    "Referer": "https://myanime.live/?s=Renegade+Immortal",
    "Cookie": "cf_clearance=J4ewRP4rAnG4jdmpYJoBPcUVC1g7gVoB9BbxEzaF3eU-1787140871-1.2.1.1-NIcasJQ_0NDKfeeBg6qbICAmOpn7Fg3NYzIPR8yJAvLWbgXms8fxVDumAGTfd0bdg0l65lWC5LxFawNU3NyQKREDaQIzrRoD8UIVBcFfJUs6OZ1sDvopiBvyvz4P5OJ3szu.5Cs3EEbTmkAf5GUuPnCSpIvhv4bEt7t.vITsthCicV1UBNrjmvCNVfXERQnef4k0EQRku86P7ZWpoHpy6OKmwOdvxxbwQbtAkpNFh2T.2bWmdwRybex2uBLUGZBAPejfDD.5WaHAml9ppVrRileKyqUh9FRYcRJKgb.nigKXDffOcFkH7Thy0VEynAeR5aDJFk1pIoU5RNDnpZDcifr1dhrlJbCXIbQh8fReW8Y",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "TE": "trailers",
}

query = {}

#######################################################################

# NOTE: QUERY_ARGS

#######################################################################


def build_query(anime: str):
    return {
        "action": "infinite_scroll",
        "page": 1,
        "currentday": settings["currentday"],
        "order": settings["query_args"]["order"],  # ty:ignore[not-subscriptable, invalid-argument-type]
        "query_args[s]": anime,
        "query_args[posts_per_page]": "100",
        "query_before": settings["query_before"],
        "last_post_date": settings["last_post_date"],
    }


#######################################################################

# NOTE: QUERY_ARGS

#######################################################################


def json_to_list(response: Any, name: str) -> list[str]:

    list_of_uris: list[str] = []
    new_name = name.replace(" ", "-").lower()

    for key in response["postflair"].keys():
        if new_name in key:
            list_of_uris.append(key)

    return list_of_uris


async def fetch_data(session: ClientSession, url: str, data, headers: dict[str, str]):
    delay = 1

    for attempt in range(4):
        try:
            async with session.post(url=url, data=data, headers=headers) as response:
                console.print(response.status)
                if response.status == 429:
                    raise
                return await response.json()
        except Exception as e:
            if attempt == 3:
                print(f"An error occurred: {e}")
                print(f"Exception type: {type(e).__name__}")
                raise
            delay *= 2
            await asyncio.sleep(delay)


async def fetch_(session: ClientSession, url: str):
    delay = 1

    for attempt in range(3):
        try:
            async with global_first_phase:
                async with session.get(url=url) as response:
                    if response.status == 429:
                        console.print("STATUS : ", response.status)
                        console.print("URL : ", url)
                        await asyncio.sleep(delay)
                    return await response.text()
        except:
            if attempt == 3:
                raise
            delay *= 2
            await asyncio.sleep(delay)


#######################################################################

# NOTE: QUERY_ARGs


#######################################################################
async def Scrape(name: str, session: ClientSession):
    response = await fetch_data(
        session=session,
        url="https://myanime.live/?infinity=scrolling",
        data=build_query(name),
        headers=headers,
    )

    list_ = json_to_list(response, name)

    episode_server: list[Server] = list()
    for uri in list_:
        episode_server.append(Server(name="dailymotion", link=uri))

    tasks = []
    for uri in list_:
        tasks.append(
            asyncio.create_task(extract_dailymotion_link(url=uri, session=session))
        )

    result = await asyncio.gather(*tasks)  # ty:ignore[invalid-assignment]

    console.print(result)

    length = len(result)

    episodes: list[Episode] = []

    with yt_dlp.YoutubeDL(
        {
            "quiet": True,
            "impersonate": ImpersonateTarget.from_str("chrome-146"),
        }
    ) as ydl:
        for idx, value in enumerate(result):
            if value[0]:
                info = ydl.extract_info(value[0], download=False)
                best = get_best_format(info["formats"])
                episodes.append(
                    Episode(
                        name=f"{length - idx} " + value[1],
                        video_link=best["url"],  # ty: ignore[unknown-argument]
                        video_link_headers_dict=best["http_headers"],  # ty: ignore[unknown-argument]
                        video_link_headers=[
                            f"{k}:{v}" for k, v in best["http_headers"].items()
                        ],  # ty: ignore[unknown-argument]
                        sub_link="",
                        sub_link_headers=[],
                    )  # ty: ignore[missing-argument]
                )
    return episodes, name


#######################################################################

# NOTE: QUERY_ARGs

#######################################################################


def get_best_format(formats):
    return max(
        formats,
        key=lambda f: (
            f.get("height") or 0,
            f.get("fps") or 0,
            f.get("tbr") or 0,
        ),
    )


def clean(name: str) -> str:
    invalid = '–<>:"/\\|?*-'

    for c in invalid:
        name = name.replace(c, "_")

    return name


#######################################################################

# NOTE: QUERY_ARGS

#######################################################################


async def extract_dailymotion_link(url: str, session: ClientSession):

    # await asyncio.sleep(1)
    response = await fetch_(session=session, url=url)

    soup: BeautifulSoup = BeautifulSoup(response, "lxml")

    name = clean(soup.find("h1").text)  # ty:ignore[unresolved-attribute]

    if n := soup.find_all("iframe"):
        for tag in n:
            uri = tag.get("src")
            if "dailymotion" in uri:  # ty: ignore[unsupported-operator]
                return uri, name

    if n := soup.find_all("video"):
        for tag in n:
            uri = tag.get("src")
            if "dailymotion" in uri:  # ty: ignore[unsupported-operator]
                return uri, name
    return "", name


#######################################################################

# NOTE: FOR DEBUGGING


#######################################################################
async def main():
    url = "https://myanime.live/?s=Renegade+Immortal"

    session: ClientSession = ClientSession()

    name: str = "Aliens Among Immortals"

    result, _ = await Scrape(name=name, session=session)
    console.print(result)

    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
