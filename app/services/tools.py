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
        # Tavily search is synchronous in the SDK, wrap if needed or run in thread
        # For async FastAPI, running sync IO in a thread pool is safer, 
        # but here we keep it simple for the prototype.
        results = self.tavily.search(query=query, max_results=max_results, include_raw_content=False)
        
        return [r for r in results.get("results", [])]

    async def scrape(self, url: str) -> str | None:
        """
        Downloads and extracts clean text from a URL.
        """
        import httpx
        logger.info(f"Scraping: {url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
            
            # Trafilatura extracts the main text content
            text = extract(response.content)
            return text
        except Exception as e:
            logger.warning(f"Failed to scrape {url}: {e}")
            return None