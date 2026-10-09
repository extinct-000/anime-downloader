from asyncio import Semaphore
from aiohttp import ClientSession
from rich.console import Console
import asyncio

console: Console = Console()


async def fetch(
    SESSION: ClientSession,
    url: str,
    semaphore: Semaphore,
    headers=None,
    params=None,
    json: bool = False,
):
    delay = 1

    for attempt in range(3):
        try:
            async with semaphore:
                async with SESSION.get(
                    url=url, params=params, headers=headers
                ) as response:
                    if response.status == 429:
                        console.print("STATUS : ", response.status)
                        console.print("URL : ", url)

                        # NOTE : Leave Release Semaphore
                        continue

                    if json and "application/json" in response.content_type:
                        return await response.json()

                    return await response.text()
        except Exception:
            if attempt == 3:
                raise

            await asyncio.sleep(delay)
            delay *= 2


async def main():
    pass


if __name__ == "__main__":
    asyncio.run(main())
