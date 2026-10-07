import logging
import re
from typing import Optional, Dict, Any, Tuple
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

TERMINAL_WIKI_SECTIONS = [
    r"\n==\s*Discografia\s*==",
    r"\n==\s*Discography\s*==",
    r"\n==\s*Note\s*==",
    r"\n==\s*Notes\s*==",
    r"\n==\s*References\s*==",
    r"\n==\s*Bibliografia\s*==",
    r"\n==\s*Bibliography\s*==",
    r"\n==\s*Voci correlate\s*==",
    r"\n==\s*See also\s*==",
    r"\n==\s*Altri progetti\s*==",
    r"\n==\s*Collegamenti esterni\s*==",
    r"\n==\s*External links\s*==",
    r"\n==\s*Tournée\s*==",
    r"\n==\s*Tour\s*==",
    r"\n==\s*Premi e riconoscimenti\s*==",
    r"\n==\s*Awards and nominations\s*=="
]

class WikipediaService:
    def __init__(self):
        self.headers = {
            "User-Agent": "AlbumDetailApp/1.0 (https://github.com/giorgioascoli-bit/api-album-detail; contact@example.com)",
            "Accept": "application/json"
        }

    async def get_artist_biography(
        self, artist_name: str, lang: str = "it"
    ) -> Tuple[str, str, Optional[str], Optional[str]]:
        """
        Cerca la biografia approfondita dell'artista su Wikipedia.
        Tenta prima nella lingua richiesta (es. 'it'), con fallback su 'en'.
        Ritorna una tupla: (biografia, fonte, wikipedia_url, wikipedia_title).
        """
        bio, wiki_url, wiki_title = await self._fetch_comprehensive_biography(artist_name, lang=lang)
        if bio:
            return bio, f"wikipedia_{lang}", wiki_url, wiki_title

        if lang != "en":
            bio_en, wiki_url_en, wiki_title_en = await self._fetch_comprehensive_biography(artist_name, lang="en")
            if bio_en:
                return bio_en, "wikipedia_en", wiki_url_en, wiki_title_en

        return "", "none", None, None

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
            sentences = [s.strip() for s in summary.split(". ") if len(s.strip()) > 30]
            extracts = sentences[:4]

        return summary or "", extracts

    async def _fetch_comprehensive_biography(
        self, artist_name: str, lang: str = "it"
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Cerca la voce più pertinente su Wikipedia ed estrae una trattazione biografica estesa,
        comprensiva delle sezioni storiche, artistiche ed evolutive (fino a 16.000 caratteri),
        insieme al link canonico ufficiale alla pagina completa.
        """
        search_url = f"https://{lang}.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": artist_name,
            "format": "json",
            "utf8": 1,
            "srlimit": 1
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(search_url, params=search_params, headers=self.headers)
                if resp.status_code != 200:
                    return None, None, None

                data = resp.json()
                search_results = data.get("query", {}).get("search", [])
                if not search_results:
                    return None, None, None

                page_title = search_results[0].get("title")
                if not page_title:
                    return None, None, None

                # Query per estratto completo con prop=extracts|info e inprop=url (senza exintro per includere tutta la carriera)
                extract_params = {
                    "action": "query",
                    "prop": "extracts|info",
                    "inprop": "url",
                    "explaintext": 1,
                    "titles": page_title,
                    "format": "json"
                }
                ext_resp = await client.get(search_url, params=extract_params, headers=self.headers)
                if ext_resp.status_code == 200:
                    ext_data = ext_resp.json()
                    pages = ext_data.get("query", {}).get("pages", {})
                    for p in pages.values():
                        raw_extract = p.get("extract", "")
                        canonical_url = p.get("canonicalurl") or p.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(page_title.replace(' ', '_'))}"
                        canonical_title = p.get("title", page_title)

                        if raw_extract and len(raw_extract.strip()) > 50:
                            cleaned_bio = self._clean_biography_extract(raw_extract, max_chars=16000)
                            return cleaned_bio, canonical_url, canonical_title

                # Fallback REST API
                encoded_title = urllib.parse.quote(page_title.replace(" ", "_"))
                summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
                summary_resp = await client.get(summary_url, headers=self.headers)
                if summary_resp.status_code == 200:
                    s_data = summary_resp.json()
                    bio = s_data.get("extract")
                    wiki_url = s_data.get("content_urls", {}).get("desktop", {}).get("page") or f"https://{lang}.wikipedia.org/wiki/{encoded_title}"
                    return bio, wiki_url, page_title

                return None, None, None
            except Exception as e:
                logger.error("Errore durante il recupero della biografia Wikipedia per '%s' (%s): %s", artist_name, lang, e)
                return None, None, None

    def _clean_biography_extract(self, raw_text: str, max_chars: int = 16000) -> str:
        """
        Pulisce il testo enciclopedico di Wikipedia:
        - Tronca all'inizio di sezioni accessorie non biografiche (Discografia, Note, Bibliografia, Collegamenti esterni).
        - Converte le intestazioni == Sezione == in formato Markdown leggibile ## Sezione.
        - Tronca a max_chars preservando l'ultimo paragrafo o frase completa.
        """
        cut_idx = len(raw_text)
        for pat in TERMINAL_WIKI_SECTIONS:
            m = re.search(pat, raw_text, re.IGNORECASE)
            if m and m.start() < cut_idx:
                cut_idx = m.start()

        cleaned = raw_text[:cut_idx].strip()

        # Se supera max_chars, tronca al paragrafo o periodo più vicino
        if len(cleaned) > max_chars:
            cutoff = cleaned[:max_chars].rfind("\n\n")
            if cutoff < max_chars // 2:
                cutoff = cleaned[:max_chars].rfind(". ")
            if cutoff > 0:
                cleaned = cleaned[:cutoff + 1].strip()
            else:
                cleaned = cleaned[:max_chars].strip()

        # Converte intestazioni Wikipedia in Markdown standard
        cleaned = re.sub(r"\n====+\s*(.*?)\s*====+", r"\n\n#### \1\n", cleaned)
        cleaned = re.sub(r"\n===\s*(.*?)\s*===", r"\n\n### \1\n", cleaned)
        cleaned = re.sub(r"\n==\s*(.*?)\s*==", r"\n\n## \1\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    async def _fetch_summary(self, query: str, lang: str = "it") -> Optional[str]:
        """Cerca la voce più pertinente su Wikipedia e ne scarica il riassunto dell'introduzione."""
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

                extract_params = {
                    "action": "query",
                    "prop": "extracts",
                    "exintro": 1,
                    "explaintext": 1,
                    "exchars": 4000,
                    "titles": page_title,
                    "format": "json"
                }
                ext_resp = await client.get(search_url, params=extract_params, headers=self.headers)
                if ext_resp.status_code == 200:
                    ext_data = ext_resp.json()
                    pages = ext_data.get("query", {}).get("pages", {})
                    for p in pages.values():
                        ext = p.get("extract")
                        if ext and len(ext.strip()) > 50:
                            return ext.strip()

                # Fallback REST API
                encoded_title = urllib.parse.quote(page_title.replace(" ", "_"))
                summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
                summary_resp = await client.get(summary_url, headers=self.headers)
                if summary_resp.status_code == 200:
                    s_data = summary_resp.json()
                    return s_data.get("extract")

                return None
            except Exception as e:
                logger.error("Errore durante la ricerca riassunto Wikipedia per '%s' (%s): %s", query, lang, e)
                return None

wikipedia_service = WikipediaService()
