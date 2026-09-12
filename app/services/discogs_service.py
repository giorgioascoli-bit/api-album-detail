import logging
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.models.album import MusicianCredit, AlbumEdition, TrackItem

logger = logging.getLogger(__name__)

DISCOGS_BASE_URL = "https://api.discogs.com"

class DiscogsService:
    def __init__(self):
        self.headers = {
            "User-Agent": settings.discogs_user_agent,
            "Accept": "application/json",
        }
        if settings.discogs_token:
            self.headers["Authorization"] = f"Discogs token={settings.discogs_token}"

    async def get_release(self, release_id: int) -> Optional[Dict[str, Any]]:
        """Recupera i dettagli completi di una specifica release da Discogs."""
        url = f"{DISCOGS_BASE_URL}/releases/{release_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning("Release Discogs %s non trovata", release_id)
                    return None
                else:
                    logger.error("Errore Discogs release %s: HTTP %s - %s", release_id, response.status_code, response.text)
                    return None
            except Exception as e:
                logger.error("Eccezione durante la chiamata Discogs release %s: %s", release_id, e)
                return None

    async def get_master(self, master_id: int) -> Optional[Dict[str, Any]]:
        """Recupera i dettagli di un master release da Discogs."""
        url = f"{DISCOGS_BASE_URL}/masters/{master_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning("Master Discogs %s non trovato", master_id)
                    return None
                else:
                    logger.error("Errore Discogs master %s: HTTP %s", master_id, response.status_code)
                    return None
            except Exception as e:
                logger.error("Eccezione durante la chiamata Discogs master %s: %s", master_id, e)
                return None

    async def get_master_versions(self, master_id: int, per_page: int = 25) -> List[Dict[str, Any]]:
        """Recupera le versioni/edizioni disponibili per un master release."""
        url = f"{DISCOGS_BASE_URL}/masters/{master_id}/versions"
        params = {"page": 1, "per_page": per_page}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("versions", [])
                return []
            except Exception as e:
                logger.error("Eccezione recupero versioni master %s: %s", master_id, e)
                return []

    async def get_artist(self, artist_id: int) -> Optional[Dict[str, Any]]:
        """Recupera informazioni e profilo dell'artista da Discogs."""
        url = f"{DISCOGS_BASE_URL}/artists/{artist_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                return None
            except Exception as e:
                logger.error("Eccezione recupero artista Discogs %s: %s", artist_id, e)
                return None

    def extract_musicians(self, release_data: Dict[str, Any]) -> List[MusicianCredit]:
        """Estrae e unifica i crediti dei musicisti partecipanti sia a livello di album che di singola traccia."""
        musicians_map: Dict[str, Dict[str, Any]] = {}

        # 1. Crediti a livello di album (extraartists)
        for extra in release_data.get("extraartists", []):
            name = extra.get("name", "").strip()
            role = extra.get("role", "").strip()
            tracks = extra.get("tracks", "").strip()
            if not name:
                continue

            # Pulisci il nome Discogs (es. "David Gilmour (2)" -> "David Gilmour")
            clean_name = self._clean_discogs_name(name)
            if clean_name not in musicians_map:
                musicians_map[clean_name] = {"name": clean_name, "roles": set(), "tracks": set()}
            if role:
                musicians_map[clean_name]["roles"].add(role)
            if tracks:
                musicians_map[clean_name]["tracks"].add(tracks)

        # 2. Crediti a livello di traccia
        for track in release_data.get("tracklist", []):
            tr_title = track.get("title", "")
            for extra in track.get("extraartists", []):
                name = extra.get("name", "").strip()
                role = extra.get("role", "").strip()
                if not name:
                    continue
                clean_name = self._clean_discogs_name(name)
                if clean_name not in musicians_map:
                    musicians_map[clean_name] = {"name": clean_name, "roles": set(), "tracks": set()}
                if role:
                    musicians_map[clean_name]["roles"].add(role)
                if tr_title:
                    musicians_map[clean_name]["tracks"].add(tr_title)

        result: List[MusicianCredit] = []
        for info in musicians_map.values():
            roles_str = ", ".join(sorted(info["roles"])) if info["roles"] else "Musician / Contributor"
            tracks_str = ", ".join(sorted(info["tracks"])) if info["tracks"] else None
            result.append(MusicianCredit(
                name=info["name"],
                role=roles_str,
                tracks=tracks_str
            ))

        return result

    def extract_main_editions(self, versions: List[Dict[str, Any]], current_release: Dict[str, Any]) -> List[AlbumEdition]:
        """Seleziona e categorizza le edizioni storiche e principali dell'album."""
        editions: List[AlbumEdition] = []
        seen_keys = set()

        # Includi prima l'edizione corrente
        curr_id = current_release.get("id")
        curr_format = ", ".join([f.get("name", "") + " " + " ".join(f.get("descriptions", [])) for f in current_release.get("formats", [])]).strip()
        curr_label = ", ".join([l.get("name", "") for l in current_release.get("labels", [])]).strip()
        curr_year = str(current_release.get("year", ""))
        curr_country = current_release.get("country", "")

        if curr_id:
            editions.append(AlbumEdition(
                id=curr_id,
                title=f"Edizione corrente ({curr_country} {curr_year})",
                format=curr_format or "Standard",
                label=curr_label or None,
                country=curr_country or None,
                year=curr_year or None,
                notable_notes="Copia richiesta nella query"
            ))
            seen_keys.add(curr_id)

        # Seleziona da versions una varietà rappresentativa: prima stampa, edizioni rimasterizzate, CD, vinile, etc.
        for v in versions:
            v_id = v.get("id")
            if not v_id or v_id in seen_keys:
                continue

            v_format = v.get("format", "")
            v_label = v.get("label", "")
            v_country = v.get("country", "")
            v_year = str(v.get("released", ""))
            v_title = v.get("title", "")

            # Evidenzia note speciali (es. Remaster, Deluxe, First Press)
            notes_parts = []
            if "remaster" in v_format.lower() or "remaster" in v_title.lower():
                notes_parts.append("Edizione Rimasterizzata")
            if "deluxe" in v_format.lower() or "deluxe" in v_title.lower():
                notes_parts.append("Deluxe Edition")
            if "box" in v_format.lower():
                notes_parts.append("Box Set")

            editions.append(AlbumEdition(
                id=v_id,
                title=v_title or f"Edizione {v_country} ({v_year})",
                format=v_format,
                label=v_label or None,
                country=v_country or None,
                year=v_year or None,
                notable_notes="; ".join(notes_parts) if notes_parts else None
            ))
            seen_keys.add(v_id)

            # Mantieni fino a 8 edizioni principali per non saturare la risposta
            if len(editions) >= 8:
                break

        return editions

    def extract_tracks(self, release_data: Dict[str, Any]) -> List[TrackItem]:
        tracks: List[TrackItem] = []
        for t in release_data.get("tracklist", []):
            pos = t.get("position", "")
            title = t.get("title", "")
            duration = t.get("duration", "")
            if title:
                tracks.append(TrackItem(position=pos or "-", title=title, duration=duration or None))
        return tracks

    @staticmethod
    def _clean_discogs_name(name: str) -> str:
        """Rimuove suffissi numerici di disambiguazione Discogs come 'Artist Name (2)'."""
        import re
        return re.sub(r"\s*\(\d+\)$", "", name).strip()

discogs_service = DiscogsService()
