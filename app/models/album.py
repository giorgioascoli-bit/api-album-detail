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

class PrimaryArtistInfo(BaseModel):
    name: str = Field(..., description="Nome dell'artista o band principale")
    discogs_id: Optional[int] = Field(None, description="Discogs Artist ID")
    biography: str = Field(..., description="Biografia dettagliata dell'artista/band principale")
    source: str = Field("discogs+wikipedia", description="Fonte principale della biografia")

class AlbumReviews(BaseModel):
    summary: str = Field(..., description="Sintesi delle recensioni e dell'accoglienza critica dell'album")
    critical_reception: List[str] = Field(default_factory=list, description="Estratti o punti chiave della critica e accoglienza")
    community_score: Optional[float] = Field(None, description="Valutazione media della community Discogs (su 5)")
    community_votes: Optional[int] = Field(None, description="Numero di voti registrati su Discogs")
    discogs_notes: Optional[str] = Field(None, description="Note storiche/critiche presenti nella scheda dell'album")

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
    main_editions: List[AlbumEdition] = Field(default_factory=list, description="Principali edizioni pubblicate dell'album")
    reviews_and_comments: AlbumReviews = Field(..., description="Commenti, accoglienza critica e recensioni sull'album")
    tracklist: List[TrackItem] = Field(default_factory=list, description="Lista dei brani dell'album")

    ai_enriched: bool = Field(False, description="Indica se i testi e la sintesi sono stati arricchiti con il modulo AI")
