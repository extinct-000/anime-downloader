from asyncio import Semaphore
from aiohttp import ClientSession
from rich.console import Console
import asyncio

console: Console = Console()


async def fetch(session: ClientSession, url: str, SEMAPHORE: Semaphore, headers=None):
    delay = 1

    for attempt in range(4):
        try:
            async with SEMAPHORE:
                async with session.get(url=url, headers=headers) as response:
                    if response.status == 429:
                        console.print("STATUS : ", response.status)
                        console.print("URL : ", url)
                        await asyncio.sleep(delay)
                        continue

                    return await response.text()
        except:
            if attempt == 3:
                raise
            delay *= 2
            await asyncio.sleep(delay)


async def main():
    pass


if __name__ == "__main__":
    asyncio.run(main())
