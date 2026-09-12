import json
import logging
from typing import Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

class AIEnricherService:
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model or "gemini-2.5-flash"

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def enrich_album_data(
        self,
        artist_name: str,
        album_title: str,
        year: Optional[str],
        genres: list[str],
        musicians: list[dict],
        wikipedia_bio: str,
        discogs_bio: str,
        wikipedia_reception: str,
        discogs_notes: str,
        lang: str = "it"
    ) -> Optional[Dict[str, Any]]:
        """
        Sintetizza e arricchisce la biografia e le recensioni critiche dell'album usando Gemini AI.
        Restituisce un dizionario con 'biography', 'reviews_summary', 'critical_reception' o None in caso di errore.
        """
        if not self.is_available():
            return None

        prompt = f"""
Sei un autorevole musicologo ed enciclopedia musicale.
Devi generare un'analisi dettagliata e completa in lingua '{lang}' per l'album musicale:
Titolo: "{album_title}"
Artista Principale: "{artist_name}"
Anno: {year or 'N/D'}
Generi/Stili: {', '.join(genres) if genres else 'N/D'}

Dati raccolti sul web e archivi:
- Note Discogs: {discogs_notes[:1000] if discogs_notes else 'Nessuna'}
- Biografia Wikipedia grezza: {wikipedia_bio[:1200] if wikipedia_bio else 'Nessuna'}
- Profilo Discogs: {discogs_bio[:800] if discogs_bio else 'Nessuno'}
- Estratto ricezione critica Wikipedia: {wikipedia_reception[:1500] if wikipedia_reception else 'Nessuno'}

Genera una risposta JSON rigorosa con questa esatta struttura:
{{
  "biography": "Biografia approfondita, fluida e accurata dell'artista/musicista principale in {lang} (2-4 paragrafi che coprono carriera, stile, impatto e contesto in cui si inserisce questo album).",
  "reviews_summary": "Sintesi critica dell'album: come è stato accolto dalla critica (es. Rolling Stone, Pitchfork, AllMusic, stampa dell'epoca), impatto culturale e consenso generale.",
  "critical_reception": [
    "Punto o citazione chiave 1 sulla ricezione dell'album",
    "Punto o citazione chiave 2 sulla produzione, arrangiamenti o testi",
    "Punto o citazione chiave 3 sull'eredità e status storico del disco"
  ]
}}
Rispondi ESCLUSIVAMENTE con il JSON, senza blocchi di markdown o testo aggiuntivo.
"""
        url = GEMINI_API_URL.format(model=self.model)
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                response = await client.post(
                    f"{url}?key={self.api_key}",
                    headers=headers,
                    json=payload
                )
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "").strip()
                            # Rimuovi eventuali ```json se presenti
                            if raw_text.startswith("```"):
                                lines = raw_text.splitlines()
                                if lines[0].startswith("```"):
                                    lines = lines[1:]
                                if lines and lines[-1].startswith("```"):
                                    lines = lines[:-1]
                                raw_text = "\n".join(lines).strip()
                            return json.loads(raw_text)
                else:
                    logger.error("Errore chiamata Gemini AI: HTTP %s - %s", response.status_code, response.text)
                    return None
            except Exception as e:
                logger.error("Eccezione durante l'arricchimento AI: %s", e)
                return None

ai_enricher = AIEnricherService()
