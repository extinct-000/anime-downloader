from asyncio import Semaphore
from aiohttp import ClientSession
from rich.console import Console
import asyncio

console: Console = Console()


async def fetch(session: ClientSession, url: str, SEMAPHORE: Semaphore, headers=None):
    delay = 1

    for attempt in range(3):
        try:
            async with SEMAPHORE:
                async with session.get(url=url, headers=headers) as response:
                    if response.status == 429:
                        console.print("STATUS : ", response.status)
                        console.print("URL : ", url)

                        # NOTE : Leave Release Semaphore
                        continue

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
