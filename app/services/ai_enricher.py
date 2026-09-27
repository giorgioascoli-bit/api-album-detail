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
Sei un illustre musicologo, storico della musica ed enciclopedia vivente.
Genera un dossier monografico autorevole, approfondito ed esaustivo in lingua '{lang}' per l'album musicale:
- Titolo: "{album_title}"
- Artista Principale: "{artist_name}"
- Anno: {year or 'N/D'}
- Generi/Stili: {', '.join(genres) if genres else 'N/D'}

Dati storici e archivistici di partenza:
- Note Discogs originali: {discogs_notes[:2500] if discogs_notes else 'Nessuna'}
- Estratto biografico Wikipedia: {wikipedia_bio[:3000] if wikipedia_bio else 'Nessuno'}
- Profilo archivio Discogs: {discogs_bio[:1200] if discogs_bio else 'Nessuno'}
- Estratto critico Wikipedia: {wikipedia_reception[:2000] if wikipedia_reception else 'Nessuno'}

Genera una risposta JSON rigorosa con i seguenti campi completi e dettagliati:
{{
  "biography": "Biografia enciclopedica approfondita ed estesa dell'artista/band principale in {lang} (4-6 paragrafi ricchi di dettagli: formazione e primi anni, influenze e stile, genesi ed evoluzione musicale fino a questo album, maturità artistica e lascito culturale). Non essere sintetico, fornisci una trattazione completa.",
  "bibliography": [
    "Libro, saggio o biografia autorevole 1 (Autore, 'Titolo', Anno/Editore)",
    "Libro, saggio o monografia autorevole 2",
    "Pubblicazione storica o articolo di riferimento 3"
  ],
  "discogs_notes_translated": "Traduzione fluida, fedele ed elegante in {lang} delle note Discogs fornite sopra (se presenti, altrimenti null).",
  "curiosities": [
    "Curiosità o aneddoto storico 1 sulla registrazione, musicisti o studio",
    "Curiosità 2 su uno specifico brano, testo o campionamento",
    "Curiosità 3 sulla reazione del pubblico, incidenti in studio o stranezze tecniche",
    "Curiosità 4 sull'eredità o dettagli nascosti dell'album"
  ],
  "cover_art_description": "Descrizione approfondita e analisi artistica della copertina: ideazione, concept visivo, simbolismi e particolarità della confezione originale (gatefold, poster, adesivi).",
  "cover_art_photographer": "Nome del fotografo che ha scattato la foto di copertina o i ritratti se noto storicamente (es. 'Don Hunstein', 'Aubrey Powell', o null se non è una fotografia)",
  "cover_art_illustrator": "Nome dell'illustratore o pittore della copertina se l'artwork è un disegno o dipinto (es. 'George Hardie', 'Mati Klarwein', o null se non applicabile)",
  "cover_art_designer": "Nome del graphic designer, studio grafico o art director dell'artwork (es. 'Hipgnosis', 'Storm Thorgerson')",
  "recording_location": "Studio di registrazione principale e città (es. 'Abbey Road Studios, Londra')",
  "recording_date": "Periodo o date storiche delle sessioni di registrazione (es. 'Giugno 1972 – Gennaio 1973')",
  "reviews_summary": "Sintesi critica approfondita: accoglienza della stampa specializzata dell'epoca e moderna (Rolling Stone, NME, Pitchfork, AllMusic), impatto sul pubblico e status storico.",
  "critical_reception": [
    "Punto chiave o giudizio critico 1",
    "Punto chiave o giudizio critico 2",
    "Punto chiave o giudizio critico 3"
  ]
}}
Rispondi ESCLUSIVAMENTE con il JSON valido, senza blocchi di codice markdown o testo introduttivo/conclusivo.
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
