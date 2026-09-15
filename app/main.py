import os
import logging
from fastapi import FastAPI, Query, Path, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from app.config import settings
from app.models.album import AlbumDetailResponse
from app.services.aggregator_service import aggregator_service
from app.services.ai_enricher import ai_enricher

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("album_detail_api")

app = FastAPI(
    title="Music Album Detail API",
    description="""
API REST per estrarre informazioni dettagliate e arricchite su un album musicale a partire dall'ID di Discogs.

Caratteristiche:
- **Biografia dell'artista/musicista principale** (estratta da Wikipedia e Discogs).
- **Lista dei musicisti partecipanti** con strumenti, ruoli e tracce accreditate.
- **Principali edizioni dell'album** (vinili storici, CD, ristampe rimasterizzate, edizioni Deluxe).
- **Commenti e recensioni** della critica e valutazione della community Discogs.
- **Modulo AI Opzionale** (Google Gemini) per sintesi armonica e traduzione multilingua.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Abilita CORS per l'integrazione da qualsiasi applicazione web/mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/demo", response_class=HTMLResponse, tags=["Demo UI"])
async def demo_ui():
    """Interfaccia web interattiva per esplorare e testare l'API."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Interfaccia non trovata</h1>", status_code=404)

@app.get("/", tags=["Info"])
async def root():
    return {
        "name": "Music Album Detail API",
        "version": "1.0.0",
        "description": "API per estrarre biografia, musicisti, edizioni e commenti di un album da Discogs ID",
        "docs_url": "/docs",
        "demo_url": "/demo",
        "ai_enabled": ai_enricher.is_available()
    }

@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "discogs_token_configured": bool(settings.discogs_token),
        "ai_enricher_configured": ai_enricher.is_available()
    }

@app.get(
    "/api/v1/album/{discogs_id}",
    response_model=AlbumDetailResponse,
    summary="Ottieni dettagli completi sull'album musicale",
    tags=["Album"]
)
async def get_album_details(
    discogs_id: int = Path(..., description="ID Discogs dell'album (Release ID o Master ID)", ge=1, examples=[249504]),
    id_type: str = Query("release", description="Tipo di ID Discogs specificato: 'release' oppure 'master'", pattern="^(release|master)$"),
    lang: str = Query("it", description="Lingua preferita per biografia e recensioni (es. 'it', 'en')"),
    synthesize: bool = Query(True, description="Se True e AI configurata, arricchisce e sintetizza i testi")
):
    """
    Restituisce:
    - **primary_artist**: Informazioni e biografia del musicista o gruppo principale.
    - **musicians**: Musicisti partecipanti, ruoli e strumenti (es. Chitarra, Basso, Batteria, Sintetizzatore).
    - **main_editions**: Principali edizioni pubblicate (vinili, CD, rimasterizzazioni, box set).
    - **reviews_and_comments**: Sintesi critica, estratti di recensioni e punteggio community.
    - **tracklist**: Elenco brani e durata.
    """
    try:
        data = await aggregator_service.get_album_details(
            discogs_id=discogs_id,
            id_type=id_type,
            lang=lang,
            synthesize=synthesize
        )
        return data
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("Errore inatteso nell'elaborazione dell'album %s: %s", discogs_id, e)
        raise HTTPException(status_code=500, detail=f"Errore interno durante il recupero dei dati: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
