# Guida all'Integrazione API per Replit
## Music Album Detail API (Google Cloud Run)

Questa guida fornisce istruzioni passo-passo, schemi dati e snippet di codice pronti per integrare la **Music Album Detail API** all'interno di un'applicazione in sviluppo su **Replit** (Python, Node.js/TypeScript o Frontend JavaScript).

---

## 1. Dettagli di Connessione

- **Base URL di Produzione**:
  ```text
  https://api-album-detail-142838642223.europe-west1.run.app
  ```
- **Documentazione Interattiva (Swagger)**:
  `https://api-album-detail-142838642223.europe-west1.run.app/docs`
- **Micro-sito Demo Esplorativo**:
  `https://api-album-detail-142838642223.europe-west1.run.app/demo`
- **Health Check**:
  `GET https://api-album-detail-142838642223.europe-west1.run.app/api/v1/health`

---

## 2. Configurazione dell'Ambiente su Replit

Nel tuo progetto Replit, apri il pannello **Tools -> Secrets** (o modifica il file `.env`) e aggiungi le seguenti variabili:

```env
ALBUM_API_BASE_URL=https://api-album-detail-142838642223.europe-west1.run.app
# OPZIONALE: Se possiedi una chiave Google Gemini e desideri traduzioni e dossier avanzati con AI
GEMINI_API_KEY=AIzaSy...
```

> **Nota:** La traduzione delle note e il recupero dei dati funzionano automaticamente anche senza `GEMINI_API_KEY`, grazie al motore di fallback neurale integrato nel backend.

---

## 3. Riepilogo Endpoint Principali

### A. Dettaglio Completo Album
Estrae biografia approfondita, musicisti, luogo/date di studio, tecnici del suono, crediti copertina (fotografo/illustratore), prezzi marketplace, curiosità, tracklist e note bilingue tradotte.

- **Metodo**: `GET`
- **Path**: `/api/v1/album/{discogs_id}`
- **Parametri Query**:
  - `discogs_id` *(int, obbligatorio nel path)*: ID Discogs dell'album (es. `10362`).
  - `id_type` *(string, opzionale, default: `"release"`)*: `"master"` per album complessivo o `"release"` per una specifica stampa. **Consigliato: `"master"`**.
  - `lang` *(string, opzionale, default: `"it"`)*: Lingua per biografia e recensioni (`"it"`, `"en"`, `"es"`, `"fr"`, `"de"`).
  - `synthesize` *(bool, opzionale, default: `true`)*: Abilita arricchimento e sintesi critica.
  - `gemini_key` *(string, opzionale)*: Chiave Gemini API personale (in alternativa si può usare l'header `X-Gemini-Key`).

### B. Traduzione Testi Indipendente
Traduce istantaneamente qualsiasi testo musicale/discografico con Gemini AI o motore neurale resiliente.

- **Metodo**: `POST`
- **Path**: `/api/v1/translate`
- **Headers**: `Content-Type: application/json`, opzionale `X-Gemini-Key: <key>`
- **Payload**:
  ```json
  {
    "text": "Recorded at Abbey Road Studios, London between June 1972 and January 1973.",
    "target_lang": "it",
    "gemini_key": null
  }
  ```

### C. Proxy Immagini Copertina
Supera eventuali blocchi di *hotlinking*, ad-blocker o policy referrer del browser sulle immagini Discogs.

- **Metodo**: `GET`
- **Path**: `/api/v1/album/image-proxy?url={encoded_image_url}`

---

## 4. Struttura del Payload JSON di Risposta

Quando chiami `GET /api/v1/album/{discogs_id}`, ricevi una risposta strutturata:

```json
{
  "discogs_id": 10362,
  "id_type": "master",
  "master_id": 10362,
  "title": "The Dark Side Of The Moon",
  "release_year": "1973",
  "genres": ["Rock"],
  "styles": ["Prog Rock", "Psychedelic Rock"],
  "cover_image": "https://i.discogs.com/...",

  "primary_artist": {
    "name": "Pink Floyd",
    "discogs_id": 45467,
    "biography": "Biografia approfondita ed estesa dell'artista...",
    "source": "wikipedia_it",
    "bibliography": [
      "Nick Mason, 'Inside Out: A Personal History of Pink Floyd', 2004",
      "John Harris, 'The Dark Side of the Moon: The Making of the Pink Floyd Masterpiece', 2005"
    ]
  },

  "musicians": [
    {
      "name": "David Gilmour",
      "role": "Vocals, Guitars, VCS3 Synthesizer",
      "tracks": null
    },
    {
      "name": "Roger Waters",
      "role": "Bass Guitar, Vocals, VCS3 Synthesizer",
      "tracks": null
    }
  ],

  "production_details": {
    "recording_location": "Abbey Road Studios, London",
    "recording_date": "Giugno 1972 – Gennaio 1973",
    "release_date": "1973-03-01",
    "sound_engineers": [
      { "name": "Alan Parsons", "role": "Engineer [Sound]" },
      { "name": "Peter James", "role": "Assistant Engineer" }
    ],
    "producers": ["Pink Floyd"]
  },

  "cover_art_details": {
    "designer": "Hipgnosis, Storm Thorgerson",
    "photographer": "Aubrey Powell",
    "illustrator": "George Hardie",
    "description": "Celebre prisma che scompone un fascio di luce bianca nei colori dello spettro visibile.",
    "packaging_contents": ["Gatefold", "Poster", "Stickers"]
  },

  "marketplace": {
    "lowest_price": 18.50,
    "highest_price_estimate": 450.00,
    "currency": "EUR",
    "num_for_sale": 1842,
    "price_range_formatted": "Da 18,50 € fino a oltre 450,00 € per copie da collezione",
    "marketplace_url": "https://www.discogs.com/sell/master/10362"
  },

  "curiosities": [
    "I battiti cardiaci che aprono e chiudono il disco furono registrati usando una grancassa imbottita.",
    "La voce recitante 'There is no dark side in the moon really' è del custode degli Abbey Road Studios, Gerry O'Driscoll."
  ],

  "reviews_and_comments": {
    "summary": "Pietra miliare assoluta della storia del rock...",
    "critical_reception": ["Capolavoro del rock progressivo", "Oltre 45 milioni di copie vendute nel mondo"],
    "community_score": 4.88,
    "community_votes": 35400,
    "discogs_notes": "Recorded at Abbey Road Studios, London between June 1972 and January 1973...",
    "discogs_notes_translated": "Registrato agli Abbey Road Studios di Londra tra il giugno 1972 e il gennaio 1973...",
    "discogs_notes_translation_source": "neural_mt"
  },

  "tracklist": [
    { "position": "A1", "title": "Speak to Me", "duration": "1:05" },
    { "position": "A2", "title": "Breathe (In the Air)", "duration": "2:49" }
  ],

  "ai_enriched": false
}
```

---

## 5. Codice di Esempio Pronto per Replit

### Esempio 1: Python (con `httpx` o `requests`)

Se stai creando una web app con **FastAPI**, **Flask**, **Streamlit** o uno script backend Python su Replit:

```python
import os
import httpx

API_BASE_URL = os.getenv("ALBUM_API_BASE_URL", "https://api-album-detail-142838642223.europe-west1.run.app")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

def get_album(discogs_id: int, id_type: str = "master", lang: str = "it"):
    """Recupera la scheda dettagliata dell'album da Discogs."""
    url = f"{API_BASE_URL}/api/v1/album/{discogs_id}"
    params = {
        "id_type": id_type,
        "lang": lang,
        "synthesize": "true"
    }
    headers = {}
    if GEMINI_KEY:
        headers["X-Gemini-Key"] = GEMINI_KEY

    with httpx.Client(timeout=25.0) as client:
        response = client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

# Esempio d'uso:
if __name__ == "__main__":
    # Test con Pink Floyd - The Dark Side of the Moon (Master ID 10362)
    album = get_album(10362, id_type="master")
    
    print(f"🎵 {album['title']} ({album.get('release_year')})")
    print(f"👤 Artista: {album['primary_artist']['name']}")
    print(f"📍 Studio: {album['production_details'].get('recording_location')}")
    print(f"🏷️ Prezzi: {album['marketplace'].get('price_range_formatted')}")
    print(f"🇮🇹 Note Discogs Tradotte:\n{album['reviews_and_comments'].get('discogs_notes_translated')}")
```

---

### Esempio 2: Node.js / Express / Next.js (TypeScript/JavaScript)

Nel tuo server o API route Replit:

```javascript
import fetch from "node-fetch"; // O fetch nativo di Node 18+

const API_BASE_URL = process.env.ALBUM_API_BASE_URL || "https://api-album-detail-142838642223.europe-west1.run.app";
const GEMINI_KEY = process.env.GEMINI_API_KEY;

export async function fetchAlbumDetails(discogsId, idType = "master", lang = "it") {
  const url = new URL(`${API_BASE_URL}/api/v1/album/${discogsId}`);
  url.searchParams.set("id_type", idType);
  url.searchParams.set("lang", lang);
  url.searchParams.set("synthesize", "true");

  const headers = {};
  if (GEMINI_KEY) {
    headers["X-Gemini-Key"] = GEMINI_KEY;
  }

  const response = await fetch(url.toString(), { headers });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Errore API [${response.status}]: ${errorText}`);
  }

  return await response.json();
}
```

---

### Esempio 3: Frontend Client-Side (React, Vue, o Vanilla JS)

Se hai un frontend web ospitato in Replit:

```javascript
const API_BASE = "https://api-album-detail-142838642223.europe-west1.run.app";

async function loadAlbum(discogsId) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/album/${discogsId}?id_type=master&lang=it`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    console.log("Album caricato:", data);
    
    // Per gestire l'immagine di copertina in sicurezza:
    const coverUrl = data.cover_image;
    const coverImg = document.getElementById("myAlbumCover");
    coverImg.src = coverUrl;
    coverImg.referrerPolicy = "no-referrer";
    
    // Fallback automatico sul proxy del backend se bloccata:
    coverImg.onerror = () => {
      coverImg.src = `${API_BASE}/api/v1/album/image-proxy?url=${encodeURIComponent(coverUrl)}`;
    };

    // Mostra le note tradotte
    const notesEl = document.getElementById("albumNotes");
    notesEl.textContent = data.reviews_and_comments.discogs_notes_translated || data.reviews_and_comments.discogs_notes;

  } catch (err) {
    console.error("Errore caricamento:", err);
  }
}
```

---

## 6. Preset Discogs ID Verificati per il Testing Rapido

| Artista & Titolo | Discogs ID | Tipo ID | Note |
|---|---|---|---|
| **Pink Floyd** – *The Dark Side of the Moon* | `10362` | `master` | Include note, registrazioni Abbey Road, packaging completo |
| **Miles Davis** – *Kind of Blue* | `5460` *(o `13842`)* | `master` | Include crediti jazz estesi, musicisti, storia |
| **Queen** – *A Night at the Opera* | `5863` | `master` | Note copertina apribile opaca, crediti Roy Thomas Baker |
| **Michael Jackson** – *Thriller* | `8883` | `master` | Quincy Jones, crediti completi e quotazioni Discogs |
| **Radiohead** – *OK Computer* | `21491` | `master` | Produzione Nigel Godrich, artwork Donwood |

---

## 7. Domande Frequenti & Troubleshooting

1. **Ricevo errore CORS?**
   L'API su Cloud Run ha già i middleware **CORS abilitati per tutte le origini (`*`)**, quindi puoi effettuare chiamate `fetch()` direttamente dal browser o dal frontend di Replit.
2. **Come visualizzare l'immagine di copertina senza errori 403?**
   I server CDN di Discogs bloccano le richieste con header `Referer` non autorizzati. Nei tag `<img>`, imposta sempre `referrerpolicy="no-referrer"`. In caso di errore, usa il proxy `/api/v1/album/image-proxy?url=...`.
3. **Come mostrare il tab bilingue per le note?**
   Nel JSON ricevi sia `discogs_notes` (in lingua originale, solitamente inglese) sia `discogs_notes_translated` (traduzione italiana). Puoi predisporre due pulsanti per alternare il testo visualizzato dall'utente.
