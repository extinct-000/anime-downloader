from typing import Any
from bs4 import BeautifulSoup, ResultSet, Tag
from rich.console import Console
import asyncio
from Utils.requests import fetch
from aiohttp import ClientSession
from asyncio import Semaphore


HEADERS                        : dict[str, str] = {
    "accept"                   : "text/html,application/xhtml+xml,application/xml;q=0.9,image/jxl,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language"          : "en-US,en;q=0.5",
    "cache-control"            : "max-age=0",
    "priority"                 : "u=0, i",
    "upgrade-insecure-requests": "1",
    "cookie"                   : "cf_clearance=CnI1AY5BUe8vn6_rEBL9_4xwtSwvolw1JR5sLj_cPI9iAH7Niva2WxH9d0dW2hBggn8jQB_nzBQ_IdgfBOjOX4xrOG68bga-jnDn_9SUUmJj6Yq93sAbLw3pDjqK868SVy_efWZ4Oyh1Y8WdFoxfaPa5n9Cn22nSR6ogUc-99O2L1aYwgGLqYJ2jztxCzsBfRpR1AoEWrYBMR8Y3amcQu0GpVZfKqE_O7h1VQ_gmiusi5g4_DVNmEan6fTQrg9uhQK8guhNI9sBLNox4rc50cTmTLwfb9-7A4mdyVtoy9w",
    "Referer"                  : "https://animekhor.org/",
}

SEMAPHORE                      : Semaphore = Semaphore(10)
console                        : Console = Console()


async def main():

    session      : ClientSession  = ClientSession()

    url          : str            = "https://animekhor.org/anime/beyond-times-gaze-season-2/"

    response     : Any            = await fetch(SESSION=session, semaphore=SEMAPHORE, url=url, headers=HEADERS)

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

    console.print(episodes_link)

    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
