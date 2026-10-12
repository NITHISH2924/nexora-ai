import os
import re
import urllib.parse
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx

from backend.app.config import settings
from backend.app.models import SearchResultSource, SearchResponse
from backend.app.services.ai_providers.manager import ai_manager

logger = logging.getLogger("services.search")

class SearchService:
    """Service handling real web search retrieval and grounded AI synthesis with citations."""

    async def fetch_web_sources(self, query: str, max_results: int = 5) -> List[SearchResultSource]:
        """Fetch search results from search engines."""
        sources: List[SearchResultSource] = []

        # 1. Check if Tavily API key is configured
        tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
        if tavily_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": tavily_key,
                            "query": query,
                            "search_depth": "basic",
                            "max_results": max_results
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for r in data.get("results", []):
                            u = r.get("url", "")
                            domain = urllib.parse.urlparse(u).netloc.replace("www.", "")
                            sources.append(SearchResultSource(
                                title=r.get("title", domain or "Web Result"),
                                url=u,
                                snippet=r.get("content", "")[:300],
                                domain=domain
                            ))
                        if sources:
                            return sources[:max_results]
            except Exception as e:
                logger.warning(f"Tavily search error: {e}")

        # 2. DuckDuckGo HTML / Lite Search
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
                    headers=headers
                )
                if resp.status_code == 200:
                    text = resp.text
                    # Simple regex / html parser for results
                    # Look for result__title and result__snippet
                    links = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', text)
                    snippets = re.findall(r'<a class="result__snippet"[^>]*>([\s\S]*?)</a>', text)
                    titles = re.findall(r'<a class="result__title"[^>]*>([\s\S]*?)</a>', text)

                    for idx in range(min(max_results, len(links))):
                        raw_url = links[idx][0]
                        # DuckDuckGo redirect url unwrap
                        if "uddg=" in raw_url:
                            parsed_url = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query).get("uddg", [raw_url])[0]
                        else:
                            parsed_url = raw_url

                        raw_title = re.sub(r'<[^>]+>', '', titles[idx]) if idx < len(titles) else "Web Document"
                        raw_snippet = re.sub(r'<[^>]+>', '', snippets[idx]) if idx < len(snippets) else ""
                        domain = urllib.parse.urlparse(parsed_url).netloc.replace("www.", "")

                        if parsed_url.startswith("http") and domain:
                            sources.append(SearchResultSource(
                                title=raw_title.strip() or domain,
                                url=parsed_url.strip(),
                                snippet=raw_snippet.strip()[:300],
                                domain=domain
                            ))
        except Exception as e:
            logger.warning(f"DuckDuckGo search error: {e}")

        # 3. If live network returned no results, do not fabricate fake sources or citations
        return sources[:max_results]

    def _get_fallback_web_sources(self, query: str, max_results: int) -> List[SearchResultSource]:
        """Returns empty list when external network search is unavailable (never fabricates URLs)."""
        return []

    async def search_and_synthesize(
        self,
        query: str,
        max_results: int = 5,
        model: Optional[str] = None,
        search_depth: str = "standard"
    ) -> SearchResponse:
        """
        Execute full AI Deep Search:
        1. Query search provider
        2. Retrieve grounded information snippets
        3. Synthesize with citation numbers [1], [2]
        4. Return synthesis with source list
        """
        sources = await self.fetch_web_sources(query, max_results=max_results)

        # Build numbered source context for the model
        source_context_lines = []
        for idx, s in enumerate(sources, 1):
            s.index = idx
            source_context_lines.append(f"[{idx}] Source: {s.title} ({s.domain})\nURL: {s.url}\nExcerpt: {s.snippet}")
        source_context = "\n\n".join(source_context_lines)

        system_prompt = (
            "You are NEXORA AI Deep Search Engine. You synthesize verified search results into an authoritative, "
            "comprehensive, and well-structured answer. "
            "CRITICAL CITATION RULE: You MUST cite sources using bracketed numbers like [1], [2] immediately following "
            "any facts derived from them. Never fabricate sources or URL citations."
        )

        user_prompt = (
            f"User Search Query: \"{query}\"\n\n"
            f"=== RETRIEVED SEARCH RESULTS ===\n"
            f"{source_context}\n"
            f"=== END SEARCH RESULTS ===\n\n"
            f"Please synthesize the above search findings to provide a detailed, well-structured answer.\n"
            f"Structure your response with:\n"
            f"1. **Quick Answer & Summary**: 2-3 direct sentences answering the core query with citations [1], [2].\n"
            f"2. **Detailed Breakdown & Key Findings**: Clear thematic sections with bullet points.\n"
            f"3. **Comparative Analysis / Technical Nuances**: If applicable, format key trade-offs in a clean markdown table.\n"
            f"4. **Verified Sources Summary**: Concise recap of key sources utilized."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        ai_synthesis, model_used = await ai_manager.generate_response(
            messages=messages,
            model=model,
            system_prompt=system_prompt
        )

        now = datetime.now(timezone.utc).isoformat()
        return SearchResponse(
            query=query,
            synthesis=ai_synthesis,
            sources=sources,
            model=model_used,
            timestamp=now,
            searchDepth=search_depth,
            totalSourcesFound=len(sources)
        )

search_service = SearchService()
