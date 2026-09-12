import logging
from typing import Optional, Dict, Any, Tuple
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

class WikipediaService:
    def __init__(self):
        self.headers = {
            "User-Agent": "AlbumDetailApp/1.0 (https://github.com/example; contact@example.com)",
            "Accept": "application/json"
        }

    async def get_artist_biography(self, artist_name: str, lang: str = "it") -> Tuple[str, str]:
        """
        Cerca la biografia dell'artista su Wikipedia.
        Tenta prima nella lingua richiesta (es. 'it'), con fallback su 'en'.
        Ritorna (biografia, fonte).
        """
        bio = await self._fetch_summary(artist_name, lang=lang)
        if bio:
            return bio, f"wikipedia_{lang}"

        if lang != "en":
            bio_en = await self._fetch_summary(artist_name, lang="en")
            if bio_en:
                return bio_en, "wikipedia_en"

        return "", "none"

    async def get_album_reception(self, album_title: str, artist_name: str, lang: str = "it") -> Tuple[str, list[str]]:
        """
        Cerca informazioni critiche, recensioni e accoglienza dell'album su Wikipedia.
        Ritorna (sintesi, lista_estratti).
        """
        query = f"{album_title} {artist_name}"
        summary = await self._fetch_summary(query, lang=lang)
        if not summary and lang != "en":
            summary = await self._fetch_summary(query, lang="en")

        extracts = []
        if summary:
            # Dividi in frasi significative
            sentences = [s.strip() for s in summary.split(". ") if len(s.strip()) > 30]
            extracts = sentences[:4]

        return summary or "", extracts

    async def _fetch_summary(self, query: str, lang: str = "it") -> Optional[str]:
        """Cerca la voce più pertinente su Wikipedia e ne scarica il riassunto."""
        search_url = f"https://{lang}.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1,
            "srlimit": 1
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(search_url, params=search_params, headers=self.headers)
                if resp.status_code != 200:
                    return None

                data = resp.json()
                search_results = data.get("query", {}).get("search", [])
                if not search_results:
                    return None

                page_title = search_results[0].get("title")
                if not page_title:
                    return None

                # Richiedi il summary tramite REST API di Wikimedia
                encoded_title = urllib.parse.quote(page_title.replace(" ", "_"))
                summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
                summary_resp = await client.get(summary_url, headers=self.headers)
                if summary_resp.status_code == 200:
                    s_data = summary_resp.json()
                    return s_data.get("extract")

                # Fallback API tradizionale
                extract_params = {
                    "action": "query",
                    "prop": "extracts",
                    "exintro": 1,
                    "explaintext": 1,
                    "titles": page_title,
                    "format": "json"
                }
                ext_resp = await client.get(search_url, params=extract_params, headers=self.headers)
                if ext_resp.status_code == 200:
                    ext_data = ext_resp.json()
                    pages = ext_data.get("query", {}).get("pages", {})
                    for p in pages.values():
                        return p.get("extract")

                return None
            except Exception as e:
                logger.error("Errore durante la ricerca Wikipedia per '%s' (%s): %s", query, lang, e)
                return None

wikipedia_service = WikipediaService()
