import os
import logging
from typing import Dict, Any, List
from fastmcp import FastMCP
from dotenv import load_dotenv

from tools.tavily_search_tool import get_tavily_client, TavilySearchError

_ = load_dotenv()  # Load environment variables from .env file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#Initialize MCP server
mcp = FastMCP(name="Innobutler-MCP", port=8080)

@mcp.tool()
async def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic"
) -> List[Dict[str, Any]]:
    """
    This tool performs web searches and returns relevant results with titles,
    URLs, content snippets, and an AI-generated answer when available.
    
    Args:
        query: The search query string (required)
        max_results: Maximum number of results to return (1-20, default: 5)
        search_depth: Search depth - "basic" for quick results or "advanced" for more comprehensive search (default: "basic")
    
    Returns:
        List of search results, each containing:
        - title: Page title
        - url: Page URL  
        - content: Content snippet
        - score: Relevance score
        Plus an optional AI-generated answer summary
    """
    try:
        # Validate inputs
        if not isinstance(query, str) or not query.strip():
            return [{"error": "Query parameter is required and must be a non-empty string"}]
        
        max_results = max(1, min(int(max_results), 20))  # Clamp between 1-20
        
        if search_depth not in ["basic", "advanced"]:
            search_depth = "basic"
        
        # Perform search
        client = get_tavily_client()
        results = await client.search(query, max_results, search_depth)
        
        # Format results
        formatted_results = []
        
        # Add AI answer if available
        if results.get("answer"):
            formatted_results.append({
                "type": "answer",
                "content": results["answer"],
                "query": query
            })
        
        # Add search results
        for result in results.get("results", []):
            formatted_results.append({
                "type": "result",
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "score": result.get("score", 0.0)
            })
        
        return formatted_results
        
    except TavilySearchError as e:
        logger.error(f"Tavily search error: {e}")
        return [{"error": f"Search failed: {str(e)}"}]
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return [{"error": f"Configuration error: {str(e)}"}]
    except Exception as e:
        logger.error(f"Unexpected error in tavily_search: {e}")
        return [{"error": f"Unexpected error: {str(e)}"}]

def main():
    """Run the MCP server."""
    try:
        # Validate environment
        if not os.getenv("TAVILY_API_KEY"):
            logger.error("TAVILY_API_KEY environment variable is required")
            return
        
        logger.info("Starting Tavily Search MCP Server...")
        mcp.run(transport="sse")
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    main()