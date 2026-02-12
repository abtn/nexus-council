import httpx
from app.core.config import get_settings

settings = get_settings()

class TavilyService:
    async def search(self, query: str) -> list[str]:
        # Actual implementation would call Tavily API
        # Returning dummy URLs for now to verify flow
        print(f"Searching Tavily for: {query}")
        return ["https://example.com/result1", "https://example.com/result2"]

    async def scrape_urls(self, urls: list[str]) -> dict[str, str]:
        # Actual implementation would use trafilatura
        print(f"Scraping {len(urls)} URLs...")
        return {url: "This is dummy content for " + url for url in urls}