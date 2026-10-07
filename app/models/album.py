from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class MusicianCredit(BaseModel):
    name: str = Field(..., description="Nome del musicista o collaboratore")
    role: str = Field(..., description="Ruolo o strumento (es. Lead Guitar, Vocals, Producer)")
    tracks: Optional[str] = Field(None, description="Tracce specifiche in cui ha partecipato, se specificato")

class AlbumEdition(BaseModel):
    id: int = Field(..., description="Discogs Release ID dell'edizione")
    title: str = Field(..., description="Titolo o descrizione dell'edizione")
    format: str = Field(..., description="Formato (es. Vinyl, LP, CD, Box Set, Cassette)")
    label: Optional[str] = Field(None, description="Etichetta discografica")
    country: Optional[str] = Field(None, description="Paese di pubblicazione")
    year: Optional[str] = Field(None, description="Anno di pubblicazione di questa edizione")
    notable_notes: Optional[str] = Field(None, description="Note di rilievo (es. Prima stampa, Remastered, Deluxe)")

class SoundEngineer(BaseModel):
    name: str = Field(..., description="Nome del tecnico del suono / ingegnere audio")
    role: str = Field(..., description="Ruolo specifico (es. Sound Engineer, Mixed By, Mastered By, Lacquer Cut By)")

class ProductionDetails(BaseModel):
    recording_location: Optional[str] = Field(None, description="Luogo o studio di registrazione (es. Abbey Road Studios, Londra)")
    recording_date: Optional[str] = Field(None, description="Data o periodo di registrazione delle sessioni")
    release_date: Optional[str] = Field(None, description="Data ufficiale di pubblicazione")
    sound_engineers: List[SoundEngineer] = Field(default_factory=list, description="Tecnici del suono, ingegneri audio, mix e mastering")
    producers: List[str] = Field(default_factory=list, description="Produttori dell'album")

class CoverArtDetails(BaseModel):
    designer: Optional[str] = Field(None, description="Graphic designer, studio creativo o art direction (es. Hipgnosis, Storm Thorgerson)")
    photographer: Optional[str] = Field(None, description="Fotografo della copertina o dei ritratti interni (es. Aubrey Powell, Don Hunstein)")
    illustrator: Optional[str] = Field(None, description="Illustratore, pittore o artista visivo (es. George Hardie, Mati Klarwein)")
    description: Optional[str] = Field(None, description="Descrizione iconografica dell'artwork, copertina anteriore, posteriore e gatefold")
    packaging_contents: List[str] = Field(default_factory=list, description="Elementi fisici inclusi nella confezione (es. Copertina Gatefold, Poster, Adesivi, Libretto)")

class MarketplacePricing(BaseModel):
    lowest_price: Optional[float] = Field(None, description="Prezzo minimo attuale registrato su Discogs Marketplace")
    highest_price_estimate: Optional[float] = Field(None, description="Stima prezzo massimo per copie rare, sigillate o prime stampe mint")
    currency: str = Field("EUR", description="Valuta di riferimento (default EUR)")
    num_for_sale: Optional[int] = Field(None, description="Numero di copie attualmente in vendita nel marketplace Discogs")
    price_range_formatted: Optional[str] = Field(None, description="Fascia di prezzo leggibile (es. 'Da 18,50 € fino a oltre 350 € per copie da collezione')")
    marketplace_url: Optional[str] = Field(None, description="Link diretto alla pagina di acquisto sul marketplace Discogs")

class PrimaryArtistInfo(BaseModel):
    name: str = Field(..., description="Nome dell'artista o band principale")
    discogs_id: Optional[int] = Field(None, description="Discogs Artist ID")
    biography: str = Field(..., description="Biografia approfondita ed enciclopedica dell'artista/band")
    source: str = Field("discogs+wikipedia", description="Fonte principale della biografia")
    bibliography: List[str] = Field(default_factory=list, description="Bibliografia, saggi, monografie e letture consigliate sull'artista")
    wikipedia_url: Optional[str] = Field(None, description="Link diretto alla pagina Wikipedia ufficiale dell'artista")
    wikipedia_title: Optional[str] = Field(None, description="Titolo esatto della voce enciclopedica su Wikipedia")

class AlbumReviews(BaseModel):
    summary: str = Field(..., description="Sintesi delle recensioni e dell'accoglienza critica dell'album")
    critical_reception: List[str] = Field(default_factory=list, description="Estratti o punti chiave della critica e accoglienza")
    community_score: Optional[float] = Field(None, description="Valutazione media della community Discogs (su 5)")
    community_votes: Optional[int] = Field(None, description="Numero di voti registrati su Discogs")
    discogs_notes: Optional[str] = Field(None, description="Note storiche/critiche originali presenti nella scheda Discogs (in inglese)")
    discogs_notes_translated: Optional[str] = Field(None, description="Traduzione in italiano delle note storiche di Discogs generata con AI")
    discogs_notes_translation_source: Optional[str] = Field(None, description="Fonte della traduzione delle note ('gemini_ai' o 'neural_mt')")

class TrackItem(BaseModel):
    position: str = Field(..., description="Numero o posizione della traccia (es. A1, 1)")
    title: str = Field(..., description="Titolo del brano")
    duration: Optional[str] = Field(None, description="Durata del brano")

class AlbumDetailResponse(BaseModel):
    discogs_id: int = Field(..., description="ID Discogs richiesto")
    id_type: str = Field(..., description="Tipo di ID elaborato ('release' o 'master')")
    master_id: Optional[int] = Field(None, description="Discogs Master ID associato")
    title: str = Field(..., description="Titolo dell'album")
    release_year: Optional[str] = Field(None, description="Anno di pubblicazione originale")
    genres: List[str] = Field(default_factory=list, description="Generi musicali")
    styles: List[str] = Field(default_factory=list, description="Stili musicali")
    cover_image: Optional[str] = Field(None, description="URL dell'immagine di copertina")
    
    primary_artist: PrimaryArtistInfo = Field(..., description="Informazioni e biografia del musicista o gruppo principale")
    musicians: List[MusicianCredit] = Field(default_factory=list, description="Musicisti partecipanti e rispettivi ruoli/strumenti")
    production_details: ProductionDetails = Field(default_factory=ProductionDetails, description="Dettagli di produzione: studio, date, tecnici del suono e produttori")
    cover_art_details: CoverArtDetails = Field(default_factory=CoverArtDetails, description="Dettagli iconografici della copertina e confezione fisica")
    marketplace: MarketplacePricing = Field(default_factory=MarketplacePricing, description="Prezzi minimi/massimi e statistiche del marketplace Discogs")
    curiosities: List[str] = Field(default_factory=list, description="Curiosità, aneddoti e retroscena sull'album")
    bibliography: List[str] = Field(default_factory=list, description="Bibliografia, testi e saggi di riferimento sull'opera e sull'artista")
    main_editions: List[AlbumEdition] = Field(default_factory=list, description="Principali edizioni pubblicate dell'album")
    reviews_and_comments: AlbumReviews = Field(..., description="Commenti, accoglienza critica e recensioni sull'album")
    tracklist: List[TrackItem] = Field(default_factory=list, description="Lista dei brani dell'album")

    ai_enriched: bool = Field(False, description="Indica se i testi e la sintesi sono stati arricchiti con il modulo AI")
