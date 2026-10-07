import logging
from typing import Optional, Dict, Any, List
from fastapi import HTTPException

from app.models.album import (
    AlbumDetailResponse,
    PrimaryArtistInfo,
    AlbumReviews,
    MusicianCredit,
    AlbumEdition,
    TrackItem,
    SoundEngineer,
    ProductionDetails,
    CoverArtDetails,
    MarketplacePricing
)
from app.services.discogs_service import discogs_service
from app.services.wikipedia_service import wikipedia_service
from app.services.ai_enricher import ai_enricher
from app.services.translator_service import translator_service
from app.utils.cache import cache
import hashlib

logger = logging.getLogger(__name__)

class AggregatorService:
    async def get_album_details(
        self,
        discogs_id: int,
        id_type: str = "release",
        lang: str = "it",
        synthesize: bool = True,
        gemini_api_key: Optional[str] = None
    ) -> AlbumDetailResponse:
        """
        Aggrega tutti i dettagli di un album musicale:
        - Biografia del musicista principale
        - Musicisti partecipanti e relativi strumenti/ruoli
        - Principali edizioni pubblicate
        - Recensioni e commenti sull'album
        """
        key_suffix = f":{hashlib.md5(gemini_api_key.encode()).hexdigest()[:8]}" if gemini_api_key else ""
        cache_key = f"album:{id_type}:{discogs_id}:{lang}:{synthesize}{key_suffix}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info("Cache hit per %s", cache_key)
            return AlbumDetailResponse(**cached_result)

        # 1. Recupero dati Discogs
        release_data: Optional[Dict[str, Any]] = None
        master_data: Optional[Dict[str, Any]] = None
        master_id: Optional[int] = None

        if id_type.lower() == "master":
            master_id = discogs_id
            master_data = await discogs_service.get_master(master_id)
            if master_data:
                main_release_id = master_data.get("main_release")
                if main_release_id:
                    release_data = await discogs_service.get_release(main_release_id)
                if not release_data:
                    release_data = master_data
            else:
                # Fallback: prova a verificare se è invece un ID di release
                release_data = await discogs_service.get_release(discogs_id)
                if release_data:
                    master_id = release_data.get("master_id")
                    if master_id:
                        master_data = await discogs_service.get_master(master_id)
        else:
            # Default è 'release'
            release_data = await discogs_service.get_release(discogs_id)
            if release_data:
                master_id = release_data.get("master_id")
                if master_id:
                    master_data = await discogs_service.get_master(master_id)
            else:
                # Fallback automatico: se non trovato come release, prova come master!
                master_data = await discogs_service.get_master(discogs_id)
                if master_data:
                    master_id = discogs_id
                    main_release_id = master_data.get("main_release")
                    if main_release_id:
                        release_data = await discogs_service.get_release(main_release_id)
                    if not release_data:
                        release_data = master_data

        if not release_data and not master_data:
            last_err = discogs_service.get_last_error()
            if last_err:
                raise HTTPException(status_code=last_err.get("status", 502), detail=last_err.get("detail"))
            raise HTTPException(
                status_code=404,
                detail=f"Album con ID Discogs {discogs_id} non trovato (verificato sia come Release che come Master)."
            )

        # 2. Informazioni di base dell'album
        album_title = release_data.get("title", "Sconosciuto")
        year = str(release_data.get("year", "")) if release_data.get("year") else None
        if not year and master_data:
            year = str(master_data.get("year", "")) or None

        genres = release_data.get("genres", [])
        styles = release_data.get("styles", [])
        notes = release_data.get("notes", "") or (master_data.get("notes", "") if master_data else "")

        # Copertina
        cover_image = None
        images = release_data.get("images", []) or (master_data.get("images", []) if master_data else [])
        if images and isinstance(images, list) and len(images) > 0:
            cover_image = images[0].get("resource_url") or images[0].get("uri")
        if not cover_image:
            cover_image = release_data.get("thumb") or (master_data.get("thumb") if master_data else None)

        # 3. Artista principale
        artists = release_data.get("artists", [])
        primary_artist_name = "Artista Sconosciuto"
        primary_artist_id = None
        discogs_artist_bio = ""

        if artists and isinstance(artists, list):
            primary_artist_name = discogs_service._clean_discogs_name(artists[0].get("name", "Artista Sconosciuto"))
            primary_artist_id = artists[0].get("id")
            if primary_artist_id:
                artist_info = await discogs_service.get_artist(primary_artist_id)
                if artist_info:
                    discogs_artist_bio = artist_info.get("profile", "")

        # 4. Musicisti e crediti
        musicians = discogs_service.extract_musicians(release_data)

        # 4b. Dettagli di produzione (studio, date, tecnici del suono, produttori)
        production_details = discogs_service.extract_production_details(release_data, master_data)

        # 4c. Dettagli iconografici della copertina e confezione fisica
        cover_art_details = discogs_service.extract_cover_art_details(release_data, master_data)

        # 4d. Statistiche e quotazioni Marketplace Discogs
        marketplace_pricing = discogs_service.extract_marketplace_pricing(release_data, master_data)

        # 5. Principali edizioni
        versions: List[Dict[str, Any]] = []
        if master_id:
            versions = await discogs_service.get_master_versions(master_id, per_page=20)
        main_editions = discogs_service.extract_main_editions(versions, release_data)

        # 6. Tracce
        tracklist = discogs_service.extract_tracks(release_data)

        # 7. Ricerca su Wikipedia (Biografia e Recensioni)
        wiki_res = await wikipedia_service.get_artist_biography(primary_artist_name, lang=lang)
        wiki_bio, bio_source, wiki_url, wiki_title = "", "none", None, None
        if len(wiki_res) >= 4:
            wiki_bio, bio_source, wiki_url, wiki_title = wiki_res[0], wiki_res[1], wiki_res[2], wiki_res[3]
        elif len(wiki_res) >= 2:
            wiki_bio, bio_source = wiki_res[0], wiki_res[1]
        wiki_reception, wiki_extracts = await wikipedia_service.get_album_reception(album_title, primary_artist_name, lang=lang)

        # Rating community Discogs
        community = release_data.get("community", {})
        comm_rating = community.get("rating", {})
        community_score = comm_rating.get("average")
        community_votes = comm_rating.get("count")

        # 8. Arricchimento opzionale con AI (Gemini)
        ai_enriched = False
        final_bio = wiki_bio or discogs_artist_bio or "Biografia non disponibile per questo artista."
        reviews_summary = wiki_reception or notes or f"Album storico di {primary_artist_name} pubblicato nel {year or 'passato'}."
        critical_reception = wiki_extracts
        curiosities: List[str] = []
        bibliography: List[str] = []
        discogs_notes_translated: Optional[str] = None
        translation_source: Optional[str] = None

        if synthesize and ai_enricher.is_available(override_key=gemini_api_key):
            enrichment = await ai_enricher.enrich_album_data(
                artist_name=primary_artist_name,
                album_title=album_title,
                year=year,
                genres=genres + styles,
                musicians=[m.model_dump() for m in musicians],
                wikipedia_bio=wiki_bio,
                discogs_bio=discogs_artist_bio,
                wikipedia_reception=wiki_reception,
                discogs_notes=notes,
                lang=lang,
                api_key=gemini_api_key
            )
            if enrichment:
                final_bio = enrichment.get("biography", final_bio)
                reviews_summary = enrichment.get("reviews_summary", reviews_summary)
                critical_reception = enrichment.get("critical_reception", critical_reception)
                curiosities = enrichment.get("curiosities", [])
                bibliography = enrichment.get("bibliography", [])
                discogs_notes_translated = enrichment.get("discogs_notes_translated")
                if discogs_notes_translated:
                    translation_source = "gemini_ai"

                # Integra luogo e date storiche di registrazione se individuate dall'AI
                if enrichment.get("recording_location") and not production_details.recording_location:
                    production_details.recording_location = enrichment.get("recording_location")
                if enrichment.get("recording_date") and not production_details.recording_date:
                    production_details.recording_date = enrichment.get("recording_date")
                if enrichment.get("cover_art_description"):
                    cover_art_details.description = enrichment.get("cover_art_description")
                if enrichment.get("cover_art_photographer") and not cover_art_details.photographer:
                    cover_art_details.photographer = enrichment.get("cover_art_photographer")
                if enrichment.get("cover_art_illustrator") and not cover_art_details.illustrator:
                    cover_art_details.illustrator = enrichment.get("cover_art_illustrator")
                if enrichment.get("cover_art_designer") and not cover_art_details.designer:
                    cover_art_details.designer = enrichment.get("cover_art_designer")

                ai_enriched = True

        # Traduzione specializzata delle note Discogs con AI / fallback neurale se presenti e non ancora tradotte
        if notes and notes.strip() and not discogs_notes_translated:
            translated_notes, source = await translator_service.translate_text(
                text=notes,
                target_lang=lang,
                gemini_api_key=gemini_api_key
            )
            if translated_notes:
                discogs_notes_translated = translated_notes
                translation_source = source

        # Fallback bibliografia se vuota
        if not bibliography and primary_artist_name != "Artista Sconosciuto":
            bibliography = [
                f"The Rolling Stone Album Guide - Scheda monografica su {primary_artist_name}.",
                f"AllMusic Guide to Jazz & Rock - Profilo storico di {primary_artist_name}.",
                f"Enciclopedia della Musica Rock - Analisi discografica e contesto storico."
            ]

        # Costruisci risposta
        response_model = AlbumDetailResponse(
            discogs_id=discogs_id,
            id_type=id_type,
            master_id=master_id,
            title=album_title,
            release_year=year,
            genres=genres,
            styles=styles,
            cover_image=cover_image,
            primary_artist=PrimaryArtistInfo(
                name=primary_artist_name,
                discogs_id=primary_artist_id,
                biography=final_bio,
                source="gemini_ai" if ai_enriched else bio_source,
                bibliography=bibliography,
                wikipedia_url=wiki_url,
                wikipedia_title=wiki_title
            ),
            musicians=musicians,
            production_details=production_details,
            cover_art_details=cover_art_details,
            marketplace=marketplace_pricing,
            curiosities=curiosities,
            bibliography=bibliography,
            main_editions=main_editions,
            reviews_and_comments=AlbumReviews(
                summary=reviews_summary,
                critical_reception=critical_reception,
                community_score=round(community_score, 2) if community_score else None,
                community_votes=community_votes,
                discogs_notes=notes if notes else None,
                discogs_notes_translated=discogs_notes_translated,
                discogs_notes_translation_source=translation_source
            ),
            tracklist=tracklist,
            ai_enriched=ai_enriched
        )

        # Salva in cache
        cache.set(cache_key, response_model.model_dump())
        return response_model

aggregator_service = AggregatorService()
