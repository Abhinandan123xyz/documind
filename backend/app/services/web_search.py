from tavily import TavilyClient
from app.config import get_settings
import httpx
from datetime import datetime

settings = get_settings()

async def search_web(query: str, max_results: int = 5) -> str:
    """Search the web using Tavily API with DuckDuckGo fallback."""
    
    # Try Tavily first
    if settings.TAVILY_API_KEY:
        try:
            tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
            
            # Add "current" or year to query for better results
            enhanced_query = query
            current_year = datetime.now().year
            
            # If asking about current events, add the year
            if any(word in query.lower() for word in ["current", "present", "now", "today", "latest"]):
                enhanced_query = f"{query} {current_year}"
            
            print(f"🔍 Tavily search: '{enhanced_query}'")
            
            response = tavily.search(
                query=enhanced_query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True,
                include_raw_content=False,
                include_images=False,
                include_domains=["wikipedia.org", "bbc.com", "reuters.com", "apnews.com", "india.gov.in"]
            )
            
            results = []
            
            # Get the AI-generated answer if available
            if response.get("answer"):
                results.append(f"**Summary**: {response['answer']}")
            
            # Get search results
            if response.get("results"):
                results.append("\n**Latest Sources**:")
                for result in response["results"][:max_results]:
                    title = result.get("title", "")
                    content = result.get("content", "")
                    url = result.get("url", "")
                    published = result.get("published_date", "")
                    
                    if content:
                        date_str = f" ({published})" if published else ""
                        short_content = content[:400] + "..." if len(content) > 400 else content
                        results.append(f"\n📰 **{title}**{date_str}\n{short_content}\n🔗 {url}")
            
            if results:
                print(f"✅ Tavily found {len(results)} results")
                return "\n".join(results)
                
        except Exception as e:
            print(f"❌ Tavily error: {e}")
    
    # Fallback to DuckDuckGo
    try:
        print("🔄 Falling back to DuckDuckGo...")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1"
                },
                headers={"User-Agent": "DocuMind/1.0"}
            )
            data = resp.json()
            
            results = []
            
            if data.get("AbstractText"):
                heading = data.get("Heading", "")
                results.append(f"**{heading}**\n{data['AbstractText']}")
            
            if data.get("Answer"):
                results.append(f"\n**Quick Answer**: {data['Answer']}")
            
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(f"• {topic['Text']}")
            
            return "\n\n".join(results) if results else ""
            
    except Exception as e:
        print(f"❌ DuckDuckGo error: {e}")
        return ""

async def search_wikipedia(query: str) -> str:
    """Fallback to Wikipedia."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "utf8": 1,
                    "srlimit": 3
                },
                headers={"User-Agent": "DocuMind/1.0"}
            )
            data = resp.json()
            
            results = []
            if data.get("query", {}).get("search"):
                for item in data["query"]["search"]:
                    title = item["title"]
                    snippet = item["snippet"].replace('<span class="searchmatch">', '**').replace('</span>', '**')
                    results.append(f"**{title}** (Wikipedia)\n{snippet}...")
            
            return "\n\n".join(results) if results else ""
            
    except Exception as e:
        print(f"❌ Wikipedia error: {e}")
        return ""