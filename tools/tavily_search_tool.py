import httpx
from typing import Dict, Any
import os
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TavilySearchError(Exception):
    """Custom exception for Tavily search errors."""
    pass

class TavilyClient:
    """Client for interacting with Tavily Search API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.tavily.com"
        self.client = httpx.Client(timeout=30.0)
    
    async def search(
        self, 
        query: str, 
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> Dict[str, Any]:
        """
        Perform a web search using Tavily API.
        
        Args:
            query: The search query string
            max_results: Maximum number of results to return (default: 5)
            search_depth: Search depth - "basic" or "advanced" (default: "basic")
            
        Returns:
            Dictionary containing search results
            
        Raises:
            TavilySearchError: If the search request fails
        """
        if not query.strip():
            raise TavilySearchError("Search query cannot be empty")
        
        payload = {
            "api_key": self.api_key,
            "query": query.strip(),
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": True,
            "include_images": False,
            "include_raw_content": False
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(f"{self.base_url}/search", json=payload)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"Tavily API error: {error_msg}")
            raise TavilySearchError(f"Search request failed: {error_msg}")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise TavilySearchError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise TavilySearchError(f"Unexpected error: {str(e)}")

def get_tavily_client() -> TavilyClient:
    """Get configured Tavily client."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY environment variable is required")
    return TavilyClient(api_key)