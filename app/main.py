import os
import logging
from typing import Optional
from fastapi import FastAPI, Query, Path, HTTPException, Request, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
import httpx

from app.config import settings
from app.models.album import AlbumDetailResponse
from app.services.aggregator_service import aggregator_service
from app.services.ai_enricher import ai_enricher
from app.services.translator_service import translator_service

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("album_detail_api")

APP_VERSION = "1.3.0-dev"
BUILD_ID = "2026.09.27.03"

app = FastAPI(
    title="Music Album Detail API",
    description="""
API REST per estrarre informazioni dettagliate e arricchite su un album musicale a partire dall'ID di Discogs.

Caratteristiche:
- **Biografia dell'artista/musicista principale** (estratta da Wikipedia e Discogs).
- **Lista dei musicisti partecipanti** con strumenti, ruoli e tracce accreditate.
- **Dettagli tecnici e produzione** (luogo di registrazione, date, ingegneri audio).
- **Copertina, packaging fisico e crediti dedicati** (fotografo, illustratore, designer).
- **Quotazioni di mercato Discogs** (prezzo minimo, stima max e copie in vendita).
- **Curiosità e aneddoti** storici sulla registrazione dell'album.
- **Traduzione con AI delle note d'archivio Discogs** (con Gemini AI e fallback neurale resiliente).
- **Modulo AI Opzionale** (Google Gemini) per sintesi monografica ed enciclopedica.
    """,
    version=APP_VERSION,
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
        "version": APP_VERSION,
        "build": BUILD_ID,
        "environment": "development",
        "description": "API per estrarre biografia, musicisti, edizioni, copertina e commenti di un album da Discogs ID",
        "docs_url": "/docs",
        "demo_url": "/demo",
        "ai_enabled": ai_enricher.is_available()
    }

@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "build": BUILD_ID,
        "discogs_token_configured": bool(settings.discogs_token),
        "ai_enricher_configured": ai_enricher.is_available()
    }

@app.get("/api/v1/album/image-proxy", tags=["Album"])
async def proxy_image(url: str = Query(..., description="URL dell'immagine di copertina")):
    """Proxy per servire immagini di copertina aggirando blocchi di terze parti o referrer policy dei browser."""
    if not url.startswith("https://") and not url.startswith("http://"):
        raise HTTPException(status_code=400, detail="URL non valido")
    try:
        headers = {
            "User-Agent": settings.discogs_user_agent or "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                media_type = resp.headers.get("content-type", "image/jpeg")
                return Response(content=resp.content, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})
            raise HTTPException(status_code=resp.status_code, detail="Impossibile recuperare l'immagine remota")
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.warning("Errore proxy immagine per %s: %s", url, e)
        raise HTTPException(status_code=502, detail=f"Errore proxy immagine: {e}")

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
    synthesize: bool = Query(True, description="Se True e AI configurata, arricchisce e sintetizza i testi"),
    gemini_key: Optional[str] = Query(None, description="Chiave API Google Gemini opzionale per arricchimento e traduzione AI"),
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key", description="Chiave API Gemini passata via header HTTP")
):
    """
    Restituisce:
    - **primary_artist**: Informazioni e biografia del musicista o gruppo principale.
    - **musicians**: Musicisti partecipanti, ruoli e strumenti (es. Chitarra, Basso, Batteria, Sintetizzatore).
    - **main_editions**: Principali edizioni pubblicate (vinili, CD, rimasterizzazioni, box set).
    - **reviews_and_comments**: Sintesi critica, estratti di recensioni, punteggio community e note tradotte con AI.
    - **tracklist**: Elenco brani e durata.
    """
    try:
        active_gemini_key = (gemini_key or x_gemini_key or "").strip() or None
        data = await aggregator_service.get_album_details(
            discogs_id=discogs_id,
            id_type=id_type,
            lang=lang,
            synthesize=synthesize,
            gemini_api_key=active_gemini_key
        )
        return data
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("Errore inatteso nell'elaborazione dell'album %s: %s", discogs_id, e)
        raise HTTPException(status_code=500, detail=f"Errore interno durante il recupero dei dati: {str(e)}")

@app.post("/api/v1/translate", tags=["Translation"])
async def translate_text_endpoint(
    text: str = Body(..., embed=True, description="Testo da tradurre (es. note storiche Discogs)"),
    target_lang: str = Body("it", embed=True, description="Lingua target della traduzione"),
    gemini_key: Optional[str] = Body(None, embed=True, description="Chiave API Gemini opzionale"),
    x_gemini_key: Optional[str] = Header(None, alias="X-Gemini-Key")
):
    """
    Traduce un testo con Google Gemini AI (se chiave presente) o con motore neurale fallback resiliente.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Il campo 'text' non può essere vuoto")
    
    active_key = (gemini_key or x_gemini_key or "").strip() or None
    translated, source = await translator_service.translate_text(
        text=clean_text,
        target_lang=target_lang,
        gemini_api_key=active_key
    )
    if not translated:
        raise HTTPException(status_code=502, detail="Impossibile completare la traduzione del testo")

    return {
        "original_text": clean_text,
        "translated_text": translated,
        "target_lang": target_lang,
        "source": source
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
