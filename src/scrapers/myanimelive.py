from rich.console import Console

from aiohttp import ClientSession
from asyncio import Semaphore
from yt_dlp.networking.impersonate import ImpersonateTarget

from dataobj import Season, Server, Episode
from typing import Any, Coroutine
from bs4.element import AttributeValueList
from bs4 import BeautifulSoup, Tag, ResultSet

import asyncio
import yt_dlp

console: Console = Console()

global_first_phase: Semaphore = Semaphore(4)
global_ytdlp: Semaphore = Semaphore(4)

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
    "currentday": "06.04.26",
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://myanime.live",
    "Sec-GPC": "1",
    "Alt-Used": "myanime.live",
    "Connection": "keep-alive",
    "Referer": "https://myanime.live/?s=Renegade+Immortal",
    "Cookie": "cf_clearance=alxPiglajOtKBC4ib7gFPryCDfa3OaUnCloobHyRNXc-1780900393-1.2.1.1-VlNLC.duH64_DopD276hp4S7S_HzlwiKaJrYrn8x8zrg4AOzRx66qVeLMFgf_vmfBTbXnyV124NJGw.bdt59QOQyVgBYh8LbHkxIPUxss8FCkCdKaRvviU8ftlLikBlHXglop_g2seJZ.DS6u54opWGV.FUZEFUvY_OHnP32rISZB1MPRE7gTl4ZRFOfuJjXAyyURb7gKw62hAZFT.fXXKZUHDUfxNDOoF5F5duGEKGT0dJCykyxq5IYeefkSDiKyFSPbOISPOeRZVjPn9Fa5qiTP7NkG5eR22QUuRzOEt8wVyy3Rp_NgqCzS7zcxbr51nxzUbIYSzqGstUhrpz56g",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "TE": "trailers",
}

query = {}


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


async def fetch_data(session: ClientSession, url: str, data, headers: dict[str, str]):
    delay = 1

    for attempt in range(4):
        try:
            async with global_first_phase:
                async with session.post(
                    url=url, data=data, headers=headers
                ) as response:
                    console.print(response.status)
                    if response.status == 429:
                        raise
                    return await response.json()
        except:
            if attempt == 3:
                raise
            delay *= 2
            await asyncio.sleep(delay)


async def fetch_(session: ClientSession, url: str):
    delay = 1

    for attempt in range(4):
        try:
            async with global_first_phase:
                async with session.get(url=url) as response:
                    if response.status == 429:
                        raise
                    return await response.text()
        except:
            if attempt == 3:
                raise
            delay *= 2
            await asyncio.sleep(delay)


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

    length = len(result)

    episodes: list[Episode] = []

    with yt_dlp.YoutubeDL(
        {
            "quiet": True,
            "impersonate": ImpersonateTarget.from_str("chrome-136"),
        }
    ) as ydl:
        for idx, value in enumerate(result):
            info = ydl.extract_info(value[0], download=False)
            best = get_best_format(info["formats"])
            episodes.append(
                Episode(
                    name=f"{length - idx} " + value[1],
                    episode_link=best["url"],
                    episode_link_headers_dict=best["http_headers"],
                    episode_link_headers=[
                        f"{k}:{v}" for k, v in best["http_headers"].items()
                    ],
                    sub_link="",
                    sub_link_headers=[],
                )
            )
    return episodes, name


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


def extract(url):

    with yt_dlp.YoutubeDL({"format": "bv*+ba/b", "quiet": False}) as ydl:
        info = ydl.extract_info(url, download=False)
        return Episode(
            name="",
            episode_link=info["url"],
            episode_link_headers_dict=info["http_headers"],
            sub_link="",
            sub_link_headers=[],
            episode_link_headers=[],
        )


async def extract_dailymotion_link(url: str, session: ClientSession):

    # await asyncio.sleep(1)
    response = await fetch_(session=session, url=url)

    soup: BeautifulSoup = BeautifulSoup(response, "lxml")

    name = clean(soup.find("h1").text)  # ty:ignore[unresolved-attribute]

    if n := soup.find_all("iframe"):
        return n[0].get("src"), name

    if n := soup.find_all("video"):
        return n[0].get("src"), name
    # console.print(url, soup)
    return "", name


def json_to_list(response: Any, name: str) -> list[str]:

    list_of_uris: list[str] = []
    new_name = name.replace(" ", "-").lower()

    for key in response["postflair"].keys():
        if new_name in key:
            list_of_uris.append(key)

    return list_of_uris


async def main():
    url = "https://myanime.live/?s=Renegade+Immortal"

    session: ClientSession = ClientSession()

    name: str = "Aliens Among Immortals"

    result, _ = await Scrape(name=name, session=session)
    console.print(result)

    # response = await fetch_(session=session, url=url)
    # console.print(response)

    # response = await fetch_data(
    #     session=session,
    #     url="https://myanime.live/?infinity=scrolling",
    #     data=build_query(name),
    #     headers=headers,
    # )

    # list_ = json_to_list(response, name)
    #
    # console.print(await extract_dailymotion_link(list_[0], session=session))

    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
