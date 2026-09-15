# Music Album Detail API 🎵

Un'API REST moderna e veloce, sviluppata con **FastAPI (Python)**, che consente a qualsiasi applicazione (web, mobile, backend) di ottenere un dossier informativo completo su un album musicale partendo dal suo **Discogs ID** (Release ID o Master ID).

---

## 🌟 Funzionalità Principali

1. **Biografia del Musicista o Band Principale**:
   - Ricercata automaticamente sul web tramite **Wikipedia** (in italiano o lingua specificata) e **Discogs**.
2. **Nome e Ruolo dei Musicisti Partecipanti**:
   - Estrazione analitica da Discogs di tutti i crediti (`extraartists` sia dell'album sia per singola traccia), indicando strumenti suonati (es. *Lead Guitar, Bass, Drums, Synthesizer, Vocals*) e ruoli tecnici.
3. **Principali Edizioni dell'Album**:
   - Analisi intelligente delle diverse edizioni storiche del disco: prime stampe originali in vinile, ristampe in CD, edizioni rimasterizzate e cofanetti Deluxe.
4. **Commenti e Recensioni Critiche sull'Album**:
   - Sintesi delle recensioni storiche e accoglienza critica da Wikipedia e dalla stampa specializzata, arricchita con la media voto e numero di valutazioni della community Discogs.
5. **Modulo AI Opzionale (Google Gemini)**:
   - Se configurata una chiave `GEMINI_API_KEY`, l'API sintetizza i dati grezzi raccolti in rete in una prosa enciclopedica fluida, ricca e autorevole in italiano.
   - **Fallback automatico**: Se non è configurata alcuna chiave AI, l'API funziona al 100% in modo autonomo e gratuito sfruttando direttamente i dati estratti da Discogs e Wikipedia.
6. **Cache ad Alte Prestazioni**:
   - Cache in-memory con TTL configurabile per prevenire rate-limits e garantire tempi di risposta istantanei sulle query ripetute.

---

## 🚀 Guida Rapida

### 1. Prerequisiti
- Python 3.10+ (o Docker)
- (Opzionale) Token personale Discogs gratuito
- (Opzionale) Google Gemini API Key gratuita

### 2. Installazione Locale

```bash
# Clona o apri la cartella del progetto
cd "api album detail"

# Crea e attiva l'ambiente virtuale
python3 -m venv .venv
source .venv/bin/activate  # Su Linux/macOS
# .venv\Scripts\activate   # Su Windows

# Installa le dipendenze
pip install -r requirements.txt
```

### 3. Configurazione Variabili d'Ambiente

Copia il file di esempio `.env.example` in `.env`:
```bash
cp .env.example .env
```

Modifica `.env` secondo le tue preferenze:
```env
PORT=8000
HOST=0.0.0.0

# (Consigliato) Ottieni un token personale gratuito su:
# https://www.discogs.com/settings/developers
DISCOGS_TOKEN=tuo_token_discogs_qui

# (Opzionale) Per la sintesi AI, ottieni una chiave gratuita su:
# https://aistudio.google.com/
GEMINI_API_KEY=tua_gemini_api_key_qui
GEMINI_MODEL=gemini-2.5-flash

# TTL della cache in secondi (es. 86400 = 24 ore)
CACHE_TTL_SECONDS=86400
```

### 4. Avvio dell'API

```bash
# Avvio con uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Una volta avviato, l'interfaccia interattiva Swagger sarà disponibile su:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## 🐳 Avvio con Docker

Se preferisci usare Docker e Docker Compose:

```bash
docker compose up --build
```

---

## 📡 Riferimento Endpoint API

### 1. `GET /api/v1/album/{discogs_id}`

Recupera tutte le informazioni dettagliate dell'album.

#### Parametri:
| Parametro | Tipo | In | Default | Descrizione |
|---|---|---|---|---|
| `discogs_id` | integer | path | **richiesto** | ID Discogs dell'album (Release ID o Master ID) |
| `id_type` | string | query | `release` | Tipo di ID (`release` oppure `master`) |
| `lang` | string | query | `it` | Lingua per biografia e commenti (`it`, `en`, etc.) |
| `synthesize` | boolean | query | `true` | Se abilitare l'arricchimento e sintesi AI (se configurata) |

#### Esempio di richiesta `curl`:
```bash
curl -X 'GET' \
  'http://localhost:8000/api/v1/album/249504?id_type=release&lang=it' \
  -H 'accept: application/json'
```

#### Esempio di Risposta JSON:
```json
{
  "discogs_id": 249504,
  "id_type": "release",
  "master_id": 10362,
  "title": "The Dark Side of the Moon",
  "release_year": "1973",
  "genres": ["Rock"],
  "styles": ["Psychedelic Rock", "Prog Rock"],
  "cover_image": "https://i.discogs.com/...",
  "primary_artist": {
    "name": "Pink Floyd",
    "discogs_id": 45467,
    "biography": "I Pink Floyd sono stati un gruppo rock britannico fondato a Londra nel 1965. Riconosciuti come una delle band più importanti e influenti nella storia della musica moderna...",
    "source": "wikipedia_it"
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
    },
    {
      "name": "Richard Wright",
      "role": "Keyboards, Vocals, VCS3 Synthesizer",
      "tracks": null
    },
    {
      "name": "Nick Mason",
      "role": "Percussion, Tape Effects",
      "tracks": null
    },
    {
      "name": "Clare Torry",
      "role": "Vocals",
      "tracks": "The Great Gig In The Sky"
    },
    {
      "name": "Dick Parry",
      "role": "Saxophone",
      "tracks": "Money, Us And Them"
    }
  ],
  "main_editions": [
    {
      "id": 249504,
      "title": "Edizione corrente (UK 1973)",
      "format": "Vinyl LP, Album, Gatefold",
      "label": "Harvest",
      "country": "UK",
      "year": "1973",
      "notable_notes": "Copia richiesta nella query"
    },
    {
      "id": 1873013,
      "title": "The Dark Side Of The Moon",
      "format": "CD, Album, Remastered",
      "label": "EMI",
      "country": "Europe",
      "year": "2011",
      "notable_notes": "Edizione Rimasterizzata"
    }
  ],
  "reviews_and_comments": {
    "summary": "The Dark Side of the Moon è considerato uno degli album migliori e più influenti della storia del rock. Ha ricevuto unanime acclamo universale dalla critica musicale per la sua ambiziosa architettura sonora, le innovazioni tecnologiche e la profondità dei temi trattati.",
    "critical_reception": [
      "Rolling Stone e AllMusic lo hanno definito un punto di svolta assoluto nella produzione sonora.",
      "È rimasto nella classifica Billboard 200 per oltre 950 settimane."
    ],
    "community_score": 4.88,
    "community_votes": 15420,
    "discogs_notes": "Recorded at Abbey Road Studios, London between June 1972 and January 1973."
  },
  "tracklist": [
    { "position": "A1", "title": "Speak to Me", "duration": "1:08" },
    { "position": "A2", "title": "Breathe (In the Air)", "duration": "2:48" },
    { "position": "B1", "title": "Money", "duration": "6:22" }
  ],
  "ai_enriched": false
}
```

---

### 2. `GET /api/v1/health`

Verifica lo stato del server e dei servizi esterni configurati:
```bash
curl http://localhost:8000/api/v1/health
```

---

## 💻 Esempi di Integrazione per Altre Applicazioni

### In Python (usando `httpx` o `requests`)

```python
import httpx

def get_album_info(discogs_id: int):
    url = f"http://localhost:8000/api/v1/album/{discogs_id}"
    params = {"lang": "it", "id_type": "release"}
    
    response = httpx.get(url, params=params)
    response.raise_for_status()
    
    album = response.json()
    print(f"Titolo: {album['title']}")
    print(f"Artista: {album['primary_artist']['name']}")
    print("\nMusicisti partecipanti:")
    for m in album['musicians']:
        print(f"- {m['name']}: {m['role']}")
        
    return album
```

### In JavaScript / TypeScript (Node.js o Frontend)

```javascript
async function fetchAlbumDetails(discogsId) {
  const response = await fetch(`http://localhost:8000/api/v1/album/${discogsId}?lang=it`);
  if (!response.ok) {
    throw new Error(`Errore: ${response.statusText}`);
  }
  const albumData = await response.json();
  console.log("Biografia:", albumData.primary_artist.biography);
  console.log("Edizioni:", albumData.main_editions);
  return albumData;
}
```

---

## 🧪 Esecuzione dei Test

Per eseguire la suite di test automatizzati con `pytest`:

```bash
# Con l'ambiente virtuale attivo:
pytest tests/ -v
```

---

## ☁️ Deploy su Google Cloud Run (CI/CD con GitHub Actions)

Il repository include una pipeline di **GitHub Actions** pronta all'uso ([.github/workflows/deploy.yml](.github/workflows/deploy.yml)) che esegue automaticamente la suite di test e distribuisce l'applicazione su **Google Cloud Run** a ogni `push` sul ramo `main`.

### 1. Configurazione Rapida del Service Account su Google Cloud

Apri [Google Cloud Shell](https://shell.cloud.google.com/?show=terminal) nel tuo browser ed esegui:

```bash
# Scarica ed esegui lo script di configurazione automatica
curl -sSL https://raw.githubusercontent.com/giorgioascoli-bit/api-album-detail/main/scripts/setup_gcp_sa.sh | bash
```

Lo script abiliterà le API necessarie (Cloud Run, Cloud Build, Artifact Registry), creerà il Service Account dedicato con i ruoli minimi indispensabili e genererà la chiave JSON.

### 2. Aggiungi i Secret su GitHub

Nel tuo repository GitHub, vai su **Settings** > **Secrets and variables** > **Actions** > **New repository secret** e inserisci:

1. `GCP_PROJECT_ID`: l'ID del tuo progetto Google Cloud.
2. `GCP_SA_KEY`: l'intero contenuto del file JSON generato dallo script al punto 1.
3. *(Opzionale)* `DISCOGS_TOKEN`: il tuo token di Discogs.
4. *(Opzionale)* `GEMINI_API_KEY`: la tua chiave Google Gemini.

### 3. Deploy Automatico

Ad ogni commit e push su `main`, GitHub Actions:
1. Eseguirà l'intera suite di test con `pytest`.
2. Se i test hanno successo, compilerà l'immagine Docker ed effettuerà il deploy su Google Cloud Run (regione `europe-west1`).
3. L'API sarà immediatamente attiva, sicura in HTTPS e pronta per essere interrogata.

