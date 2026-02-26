import asyncio
from tavily import TavilyClient
from trafilatura import extract
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class WebTools:
    def __init__(self):
        self.tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Returns a list of dicts: {'url': '...', 'content': '...'}
        Tavily Pro provides raw content, but we will scrape manually for higher quality.
        """
        logger.info(f"Searching Tavily for: {query}")
        
        # --- FIXED: Non-blocking execution ---
        results = await asyncio.to_thread(
            self.tavily.search, query=query, max_results=max_results, include_raw_content=False
        )
        
        return [r for r in results.get("results", [])]

    async def scrape(self, url: str) -> str | None:
        """
        Downloads and extracts clean text from a URL.
        Uses browser headers to bypass VPN blocks.
        """
        import httpx
        logger.info(f"Scraping: {url}")
        
        # Define headers to mimic a real browser (Chrome on Windows)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

            # Trafilatura extracts the main text content
            text = extract(response.content)
            return text
        except Exception as e:
            logger.warning(f"Failed to scrape {url}: {e}")
            return None