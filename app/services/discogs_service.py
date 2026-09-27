import logging
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.models.album import (
    MusicianCredit,
    AlbumEdition,
    TrackItem,
    SoundEngineer,
    ProductionDetails,
    CoverArtDetails,
    MarketplacePricing
)

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
        self.last_error = None

    def get_last_error(self) -> Optional[Dict[str, Any]]:
        err = self.last_error
        self.last_error = None
        return err

    def _handle_error_status(self, status_code: int, context: str, response_text: str = ""):
        if status_code == 429:
            self.last_error = {
                "status": 429,
                "detail": "Rate limit di Discogs raggiunto (HTTP 429). Configura la variabile DISCOGS_TOKEN con un token personale gratuito per aumentare il limite."
            }
        elif status_code == 403:
            self.last_error = {
                "status": 403,
                "detail": "Accesso bloccato da Discogs (HTTP 403). I server Discogs richiedono un token personale gratuito (DISCOGS_TOKEN) per le richieste provenienti dal cloud."
            }
        elif status_code == 401:
            self.last_error = {
                "status": 401,
                "detail": "Token Discogs non valido o non autorizzato (HTTP 401)."
            }
        else:
            self.last_error = {
                "status": status_code,
                "detail": f"Errore Discogs ({status_code}) per {context}: {response_text[:200]}"
            }

    async def get_release(self, release_id: int) -> Optional[Dict[str, Any]]:
        """Recupera i dettagli completi di una specifica release da Discogs."""
        url = f"{DISCOGS_BASE_URL}/releases/{release_id}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning("Release Discogs %s non trovata", release_id)
                    return None
                else:
                    logger.error("Errore Discogs release %s: HTTP %s - %s", release_id, response.status_code, response.text)
                    self._handle_error_status(response.status_code, f"release {release_id}", response.text)
                    return None
            except Exception as e:
                logger.error("Eccezione durante la chiamata Discogs release %s: %s", release_id, e)
                self.last_error = {
                    "status": 502,
                    "detail": f"Errore di rete verso Discogs ({type(e).__name__}): {str(e)}"
                }
                return None

    async def get_master(self, master_id: int) -> Optional[Dict[str, Any]]:
        """Recupera i dettagli di un master release da Discogs."""
        url = f"{DISCOGS_BASE_URL}/masters/{master_id}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning("Master Discogs %s non trovato", master_id)
                    return None
                else:
                    logger.error("Errore Discogs master %s: HTTP %s", master_id, response.status_code)
                    self._handle_error_status(response.status_code, f"master {master_id}", response.text)
                    return None
            except Exception as e:
                logger.error("Eccezione durante la chiamata Discogs master %s: %s", master_id, e)
                self.last_error = {
                    "status": 502,
                    "detail": f"Errore di rete verso Discogs ({type(e).__name__}): {str(e)}"
                }
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

    def extract_sound_engineers(self, release_data: Dict[str, Any]) -> List[SoundEngineer]:
        """Estrae i tecnici del suono, ingegneri audio, mix e mastering dai crediti Discogs."""
        engineers_map: Dict[str, List[str]] = {}
        keywords = ["engineer", "recorded by", "mixed by", "mastered by", "sound", "lacquer cut", "audio", "remastered by", "tape"]

        # 1. Controlla extraartists della release
        for extra in release_data.get("extraartists", []):
            name = extra.get("name", "").strip()
            role = extra.get("role", "").strip()
            if not name or not role:
                continue
            role_lower = role.lower()
            if any(k in role_lower for k in keywords):
                clean_name = self._clean_discogs_name(name)
                if clean_name not in engineers_map:
                    engineers_map[clean_name] = []
                if role not in engineers_map[clean_name]:
                    engineers_map[clean_name].append(role)

        # 2. Controlla tracce individuali
        for track in release_data.get("tracklist", []):
            for extra in track.get("extraartists", []):
                name = extra.get("name", "").strip()
                role = extra.get("role", "").strip()
                if not name or not role:
                    continue
                role_lower = role.lower()
                if any(k in role_lower for k in keywords):
                    clean_name = self._clean_discogs_name(name)
                    if clean_name not in engineers_map:
                        engineers_map[clean_name] = []
                    if role not in engineers_map[clean_name]:
                        engineers_map[clean_name].append(role)

        result: List[SoundEngineer] = []
        for name, roles in engineers_map.items():
            result.append(SoundEngineer(name=name, role=", ".join(roles)))
        return result

    def extract_production_details(self, release_data: Dict[str, Any], master_data: Optional[Dict[str, Any]] = None) -> ProductionDetails:
        """Estrae dettagli di produzione (studio, date, produttori, tecnici)."""
        import re

        # Luogo di registrazione da companies (es. "Recorded At") o notes
        recording_location = None
        companies = release_data.get("companies", [])
        for comp in companies:
            entity_type = comp.get("entity_type_name", "").lower()
            if "recorded at" in entity_type or "studio" in entity_type:
                recording_location = comp.get("name")
                break

        notes = release_data.get("notes", "") or (master_data.get("notes", "") if master_data else "")
        if not recording_location and notes:
            rec_match = re.search(r"recorded (?:at|in)\s+([^.,;\n]+)", notes, re.IGNORECASE)
            if rec_match:
                recording_location = rec_match.group(1).strip()

        # Date di registrazione e release
        recording_date = None
        if notes:
            date_match = re.search(r"(?:between|during|in)\s+((?:january|february|march|april|may|june|july|august|september|october|november|december|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|\d{4})[^\n.,;]+)", notes, re.IGNORECASE)
            if date_match:
                recording_date = date_match.group(1).strip()

        release_date = release_data.get("released") or str(release_data.get("year", "")) or (str(master_data.get("year", "")) if master_data else None)

        # Produttori
        producers = []
        for extra in release_data.get("extraartists", []):
            role = extra.get("role", "").lower()
            if "producer" in role or "produced by" in role:
                clean_name = self._clean_discogs_name(extra.get("name", ""))
                if clean_name and clean_name not in producers:
                    producers.append(clean_name)

        sound_engineers = self.extract_sound_engineers(release_data)

        return ProductionDetails(
            recording_location=recording_location,
            recording_date=recording_date,
            release_date=release_date,
            sound_engineers=sound_engineers,
            producers=producers
        )

    def extract_cover_art_details(self, release_data: Dict[str, Any], master_data: Optional[Dict[str, Any]] = None) -> CoverArtDetails:
        """Estrae informazioni sulla copertina, designer, fotografi, illustratori e contenuti fisici della confezione."""
        import re

        designers = []
        photographers = []
        illustrators = []

        photo_keywords = ["photograph", "photo", "shot by"]
        illustr_keywords = ["illustrat", "drawing", "painting", "painted by", "drawn by", "artwork by", "cover art by"]
        design_keywords = ["design", "sleeve", "art direction", "layout", "graphic", "concept"]

        for extra in release_data.get("extraartists", []):
            role = extra.get("role", "").lower()
            clean_name = self._clean_discogs_name(extra.get("name", ""))
            role_orig = extra.get("role", "")
            if not clean_name:
                continue

            item = f"{clean_name} ({role_orig})"

            # Fotografo della copertina
            if any(k in role for k in photo_keywords):
                if item not in photographers:
                    photographers.append(item)
            # Illustratore o pittore
            elif any(k in role for k in illustr_keywords):
                if item not in illustrators:
                    illustrators.append(item)
            # Graphic Designer o Art Director
            elif any(k in role for k in design_keywords):
                if item not in designers:
                    designers.append(item)

        # Parsing note per estrarre fotografo, illustratore o designer se mancanti
        notes = (release_data.get("notes", "") or "") + " " + (master_data.get("notes", "") if master_data else "")
        if notes:
            if not photographers:
                photo_match = re.search(r"(?:photography|photo(?:grapher)?|cover photo)\s+(?:by|:)\s+([^.,;\n\(\)]+)", notes, re.IGNORECASE)
                if photo_match:
                    p_name = photo_match.group(1).strip()
                    if 2 < len(p_name) < 50 and not any(p_name in x for x in photographers):
                        photographers.append(p_name)
            if not illustrators:
                ill_match = re.search(r"(?:illustration|illustrated|drawing|painting)\s+(?:by|:)\s+([^.,;\n\(\)]+)", notes, re.IGNORECASE)
                if ill_match:
                    i_name = ill_match.group(1).strip()
                    if 2 < len(i_name) < 50 and not any(i_name in x for x in illustrators):
                        illustrators.append(i_name)
            if not designers:
                des_match = re.search(r"(?:sleeve|cover design|art direction|artwork|designed)\s+(?:by|:)\s+([^.,;\n\(\)]+)", notes, re.IGNORECASE)
                if des_match:
                    d_name = des_match.group(1).strip()
                    if 2 < len(d_name) < 50 and not any(d_name in x for x in designers):
                        designers.append(d_name)

        # Contenuti fisici della confezione
        packaging_contents = []
        formats = release_data.get("formats", [])
        for f in formats:
            for desc in f.get("descriptions", []):
                d_lower = desc.lower()
                if "gatefold" in d_lower and "Copertina apribile (Gatefold)" not in packaging_contents:
                    packaging_contents.append("Copertina apribile (Gatefold)")
                if "box" in d_lower and "Cofanetto (Box Set)" not in packaging_contents:
                    packaging_contents.append("Cofanetto (Box Set)")
                if "poster" in d_lower and "Poster incluso" not in packaging_contents:
                    packaging_contents.append("Poster incluso")
                if "booklet" in d_lower and "Libretto fotografico" not in packaging_contents:
                    packaging_contents.append("Libretto fotografico")

        notes_lower = notes.lower()
        if "poster" in notes_lower and "Poster incluso" not in packaging_contents:
            packaging_contents.append("Poster incluso")
        if "sticker" in notes_lower and "Adesivi inclusi" not in packaging_contents:
            packaging_contents.append("Adesivi inclusi")
        if "gatefold" in notes_lower and "Copertina apribile (Gatefold)" not in packaging_contents:
            packaging_contents.append("Copertina apribile (Gatefold)")
        if "insert" in notes_lower and "Inserto con testi" not in packaging_contents:
            packaging_contents.append("Inserto con testi")

        return CoverArtDetails(
            designer=", ".join(designers) if designers else None,
            photographer=", ".join(photographers) if photographers else None,
            illustrator=", ".join(illustrators) if illustrators else None,
            description="Artwork ufficiale da catalogo Discogs con elementi iconografici della prima stampa.",
            packaging_contents=packaging_contents
        )

    def extract_marketplace_pricing(self, release_data: Dict[str, Any], master_data: Optional[Dict[str, Any]] = None) -> MarketplacePricing:
        """Estrae statistiche di prezzo dal Marketplace Discogs."""
        lowest = release_data.get("lowest_price")
        num_sale = release_data.get("num_for_sale")

        if lowest is None and master_data:
            lowest = master_data.get("lowest_price")
        if num_sale is None and master_data:
            num_sale = master_data.get("num_for_sale")

        highest_est = None
        price_range_str = None
        if lowest is not None and lowest > 0:
            # Stima di mercato collezionistico: prime stampe e copie mint
            highest_est = round(lowest * 8.5, 2)
            if highest_est < 60:
                highest_est = 60.0
            price_range_str = f"Da {lowest:.2f} € a oltre {highest_est:.2f} € per copie sigillate/prime stampe"
        elif num_sale and num_sale > 0:
            price_range_str = f"Copie disponibili in compravendita: {num_sale}"

        discogs_id = release_data.get("id")
        marketplace_url = f"https://www.discogs.com/sell/release/{discogs_id}" if discogs_id else None

        return MarketplacePricing(
            lowest_price=float(lowest) if lowest is not None else None,
            highest_price_estimate=highest_est,
            currency="EUR",
            num_for_sale=num_sale,
            price_range_formatted=price_range_str,
            marketplace_url=marketplace_url
        )

    @staticmethod
    def _clean_discogs_name(name: str) -> str:
        """Rimuove suffissi numerici di disambiguazione Discogs come 'Artist Name (2)'."""
        import re
        return re.sub(r"\s*\(\d+\)$", "", name).strip()

discogs_service = DiscogsService()
