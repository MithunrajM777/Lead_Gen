import asyncio
from app import scraper

async def test():
    print("Testing scrape for https://www.uplogictech.com/...")
    try:
        data = await scraper.scrape_site("https://www.uplogictech.com/")
        print("Scraped Data:", data)
    except Exception as e:
        print("Scrape Failed with error:", e)

if __name__ == "__main__":
    asyncio.run(test())
