import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.discogs_service import discogs_service
from app.services.wikipedia_service import wikipedia_service
from app.services.ai_enricher import ai_enricher
from app.services.translator_service import translator_service
from app.utils.cache import cache

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["docs_url"] == "/docs"
    assert data["demo_url"] == "/demo"
    assert "version" in data
    assert "build" in data

def test_demo_endpoint():
    response = client.get("/demo")
    assert response.status_code == 200
    assert "Music Album Explorer" in response.text
    assert "v1.3.1-dev" in response.text

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "build" in data
    assert "discogs_token_configured" in data
    assert "ai_enricher_configured" in data

def test_discogs_clean_name():
    assert discogs_service._clean_discogs_name("David Gilmour (2)") == "David Gilmour"
    assert discogs_service._clean_discogs_name("Pink Floyd") == "Pink Floyd"

def test_discogs_extract_musicians():
    mock_release = {
        "extraartists": [
            {"name": "David Gilmour (2)", "role": "Lead Guitar, Vocals", "tracks": ""},
            {"name": "Roger Waters", "role": "Bass Guitar", "tracks": ""}
        ],
        "tracklist": [
            {
                "title": "The Great Gig In The Sky",
                "position": "B1",
                "extraartists": [
                    {"name": "Clare Torry", "role": "Vocals", "tracks": ""}
                ]
            }
        ]
    }
    musicians = discogs_service.extract_musicians(mock_release)
    assert len(musicians) == 3
    names = {m.name for m in musicians}
    assert "David Gilmour" in names
    assert "Roger Waters" in names
    assert "Clare Torry" in names

def test_discogs_extract_main_editions():
    current_release = {
        "id": 249504,
        "country": "UK",
        "year": 1973,
        "formats": [{"name": "Vinyl", "descriptions": ["LP", "Album"]}],
        "labels": [{"name": "Harvest"}]
    }
    versions = [
        {"id": 1001, "title": "Dark Side 2011 Remaster", "format": "CD, Remastered", "label": "EMI", "country": "Europe", "released": 2011},
        {"id": 1002, "title": "Dark Side 50th Deluxe Box", "format": "Box Set, Deluxe", "label": "Pink Floyd Records", "country": "US", "released": 2023}
    ]
    editions = discogs_service.extract_main_editions(versions, current_release)
    assert len(editions) == 3
    assert editions[0].id == 249504
    assert editions[1].id == 1001
    assert "Rimasterizzata" in (editions[1].notable_notes or "")

def test_discogs_extract_production_and_engineers():
    mock_release = {
        "extraartists": [
            {"name": "Alan Parsons", "role": "Engineer [Sound]", "tracks": ""},
            {"name": "Chris Thomas", "role": "Mixing Supervisor", "tracks": ""}
        ],
        "companies": [
            {"entity_type_name": "Recorded At", "name": "Abbey Road Studios, London"}
        ],
        "released": "1973-03-01",
        "notes": "Recorded between June 1972 and January 1973."
    }
    engineers = discogs_service.extract_sound_engineers(mock_release)
    assert len(engineers) >= 1
    assert any("Alan Parsons" in e.name for e in engineers)

    prod = discogs_service.extract_production_details(mock_release)
    assert "Abbey Road Studios" in (prod.recording_location or "")
    assert "1973" in (prod.release_date or "")
    assert len(prod.sound_engineers) >= 1

def test_discogs_extract_cover_and_marketplace():
    mock_release = {
        "id": 249504,
        "extraartists": [
            {"name": "Hipgnosis (2)", "role": "Sleeve, Design"},
            {"name": "Aubrey Powell", "role": "Photography By"},
            {"name": "George Hardie", "role": "Illustration"}
        ],
        "formats": [
            {"name": "Vinyl", "descriptions": ["Gatefold", "LP"]}
        ],
        "lowest_price": 14.50,
        "num_for_sale": 180,
        "notes": "Includes 2 posters and 2 stickers."
    }
    cover = discogs_service.extract_cover_art_details(mock_release)
    assert "Hipgnosis" in (cover.designer or "")
    assert "Aubrey Powell" in (cover.photographer or "")
    assert "George Hardie" in (cover.illustrator or "")
    assert any("Gatefold" in c for c in cover.packaging_contents)
    assert any("Poster" in c for c in cover.packaging_contents)

    market = discogs_service.extract_marketplace_pricing(mock_release)
    assert market.lowest_price == 14.50
    assert market.num_for_sale == 180
    assert market.currency == "EUR"
    assert market.highest_price_estimate is not None
    assert "sell/release/249504" in (market.marketplace_url or "")

def test_image_proxy_validation():
    # URL non valido
    res = client.get("/api/v1/album/image-proxy?url=invalid-url")
    assert res.status_code == 400

@pytest.mark.asyncio
async def test_album_endpoint_mocked():
    mock_release = {
        "id": 249504,
        "title": "The Dark Side of the Moon",
        "year": 1973,
        "genres": ["Rock"],
        "styles": ["Prog Rock"],
        "artists": [{"id": 45467, "name": "Pink Floyd"}],
        "extraartists": [
            {"name": "David Gilmour", "role": "Guitar", "tracks": ""},
            {"name": "Alan Parsons", "role": "Engineer", "tracks": ""}
        ],
        "tracklist": [
            {"position": "A1", "title": "Speak to Me", "duration": "1:05"}
        ],
        "master_id": 10362,
        "community": {"rating": {"average": 4.88, "count": 12000}},
        "lowest_price": 19.99,
        "num_for_sale": 45,
        "notes": "Mastered at Abbey Road Studios."
    }

    with patch.object(discogs_service, "get_release", new=AsyncMock(return_value=mock_release)), \
         patch.object(discogs_service, "get_master_versions", new=AsyncMock(return_value=[])), \
         patch.object(discogs_service, "get_artist", new=AsyncMock(return_value={"profile": "Bio Discogs Pink Floyd"})), \
         patch.object(wikipedia_service, "get_artist_biography", new=AsyncMock(return_value=("I Pink Floyd sono una rock band britannica.", "wikipedia_it"))), \
         patch.object(wikipedia_service, "get_album_reception", new=AsyncMock(return_value=("Capolavoro acclamato dalla critica.", ["Votato tra i migliori album di sempre"]))):

        response = client.get("/api/v1/album/249504?id_type=release&lang=it")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Dark Side of the Moon"
        assert data["primary_artist"]["name"] == "Pink Floyd"
        assert "Pink Floyd" in data["primary_artist"]["biography"]
        assert len(data["musicians"]) >= 1
        assert data["musicians"][0]["name"] == "David Gilmour"
        assert len(data["tracklist"]) == 1
        assert data["tracklist"][0]["title"] == "Speak to Me"
        assert data["ai_enriched"] is False
        assert "production_details" in data
        assert len(data["production_details"]["sound_engineers"]) >= 1
        assert "cover_art_details" in data
        assert "marketplace" in data
        assert data["marketplace"]["lowest_price"] == 19.99
        assert "bibliography" in data
        assert len(data["bibliography"]) >= 1

@pytest.mark.asyncio
async def test_ai_enricher_flow():
    # 1. Quando la chiave non è impostata
    with patch.object(ai_enricher, "is_available", return_value=False):
        res = await ai_enricher.enrich_album_data(
            artist_name="Pink Floyd",
            album_title="The Dark Side of the Moon",
            year="1973",
            genres=["Rock"],
            musicians=[],
            wikipedia_bio="",
            discogs_bio="",
            wikipedia_reception="",
            discogs_notes="",
            lang="it"
        )
        assert res is None

    # 2. Quando l'AI è abilitata e risponde con successo
    mock_ai_data = {
        "biography": "Biografia sintetica generata da Gemini.",
        "reviews_summary": "Sintesi critica eccellente generata da Gemini.",
        "critical_reception": ["Capolavoro assoluto", "Pietra miliare del rock"],
        "curiosities": ["Curiosità su Abbey Road", "Curiosità sui suoni del registratore"],
        "bibliography": ["Mason, Nick - Inside Out", "Harris, John - The Dark Side of the Moon"],
        "discogs_notes_translated": "Note storiche tradotte in italiano da Gemini."
    }
    with patch("app.services.aggregator_service.ai_enricher.is_available", return_value=True), \
         patch("app.services.aggregator_service.ai_enricher.enrich_album_data", new=AsyncMock(return_value=mock_ai_data)), \
         patch.object(discogs_service, "get_release", new=AsyncMock(return_value={"id": 999999, "title": "Dark Side", "artists": [{"name": "Pink Floyd"}]})), \
         patch.object(discogs_service, "get_master_versions", new=AsyncMock(return_value=[])), \
         patch.object(discogs_service, "get_artist", new=AsyncMock(return_value={"profile": "Bio"})), \
         patch.object(wikipedia_service, "get_artist_biography", new=AsyncMock(return_value=("Bio Wiki", "wiki"))), \
         patch.object(wikipedia_service, "get_album_reception", new=AsyncMock(return_value=("Rec Wiki", ["Punto"]))):

        response = client.get("/api/v1/album/999999?id_type=release&lang=it&synthesize=true")
        assert response.status_code == 200
        data = response.json()
        assert data["ai_enriched"] is True
        assert data["primary_artist"]["biography"] == "Biografia sintetica generata da Gemini."
        assert data["reviews_and_comments"]["summary"] == "Sintesi critica eccellente generata da Gemini."
        assert "Capolavoro assoluto" in data["reviews_and_comments"]["critical_reception"]
        assert data["reviews_and_comments"]["discogs_notes_translated"] == "Note storiche tradotte in italiano da Gemini."
        assert len(data["curiosities"]) == 2
        assert len(data["bibliography"]) == 2

@pytest.mark.asyncio
async def test_translator_service_gemini():
    with patch.object(ai_enricher, "is_available", return_value=True), \
         patch.object(ai_enricher, "translate_with_gemini", new=AsyncMock(return_value="Registrato agli Abbey Road Studios")):
        translated, source = await translator_service.translate_text("Recorded at Abbey Road Studios", target_lang="it")
        assert translated == "Registrato agli Abbey Road Studios"
        assert source == "gemini_ai"

@pytest.mark.asyncio
async def test_translator_service_fallback():
    with patch.object(ai_enricher, "is_available", return_value=False), \
         patch.object(translator_service, "_translate_neural_mymemory", new=AsyncMock(return_value="Traduzione Neurale Fallback")):
        translated, source = await translator_service.translate_text("Sample English notes", target_lang="it")
        assert translated == "Traduzione Neurale Fallback"
        assert source == "neural_mt"

def test_translate_endpoint():
    with patch.object(translator_service, "translate_text", new=AsyncMock(return_value=("Traduzione di prova", "gemini_ai"))):
        response = client.post(
            "/api/v1/translate",
            json={"text": "Recorded in London", "target_lang": "it"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["translated_text"] == "Traduzione di prova"
        assert data["source"] == "gemini_ai"
        assert data["target_lang"] == "it"

    # Test validazione testo vuoto
    bad_resp = client.post("/api/v1/translate", json={"text": "   ", "target_lang": "it"})
    assert bad_resp.status_code == 400

@pytest.mark.asyncio
async def test_album_endpoint_notes_fallback_translation():
    mock_release = {
        "id": 123456,
        "title": "Abbey Road",
        "artists": [{"id": 1, "name": "The Beatles"}],
        "notes": "Original recording took place in EMI Studios London."
    }
    with patch.object(discogs_service, "get_release", new=AsyncMock(return_value=mock_release)), \
         patch.object(discogs_service, "get_master_versions", new=AsyncMock(return_value=[])), \
         patch.object(discogs_service, "get_artist", new=AsyncMock(return_value={})), \
         patch.object(wikipedia_service, "get_artist_biography", new=AsyncMock(return_value=("Bio", "wiki"))), \
         patch.object(wikipedia_service, "get_album_reception", new=AsyncMock(return_value=("Rec", []))), \
         patch.object(ai_enricher, "is_available", return_value=False), \
         patch.object(translator_service, "translate_text", new=AsyncMock(return_value=("La registrazione originale ebbe luogo negli EMI Studios di Londra.", "neural_mt"))):

        response = client.get("/api/v1/album/123456?id_type=release&lang=it")
        assert data["reviews_and_comments"]["discogs_notes"] == "Original recording took place in EMI Studios London."
        assert data["reviews_and_comments"]["discogs_notes_translated"] == "La registrazione originale ebbe luogo negli EMI Studios di Londra."
        assert data["reviews_and_comments"]["discogs_notes_translation_source"] == "neural_mt"

def test_wikipedia_service_clean_extract():
    sample_raw = """
I Pink Floyd sono una rock band britannica.
== Storia ==
La band si è formata a Londra nel 1965.
=== Gli esordi ===
Primi concerti al club UFO.
== Discografia ==
1967 - The Piper at the Gates of Dawn
== Note ==
1. Riferimento storico.
== Bibliografia ==
Libro di storia del rock.
"""
    cleaned = wikipedia_service._clean_biography_extract(sample_raw)
    assert "I Pink Floyd sono una rock band britannica." in cleaned
    assert "## Storia" in cleaned
    assert "### Gli esordi" in cleaned
    assert "The Piper at the Gates of Dawn" not in cleaned
    assert "Riferimento storico" not in cleaned
    assert "Bibliografia" not in cleaned

@pytest.mark.asyncio
async def test_album_endpoint_includes_wikipedia_url():
    mock_release = {
        "id": 999111,
        "title": "Kind of Blue",
        "artists": [{"id": 23755, "name": "Miles Davis"}]
    }
    wiki_tuple = (
        "Miles Davis è stato un trombettista e compositore statunitense.\n\n## Storia\nIniziò con il bebop.",
        "wikipedia_it",
        "https://it.wikipedia.org/wiki/Miles_Davis",
        "Miles Davis"
    )
    with patch.object(discogs_service, "get_release", new=AsyncMock(return_value=mock_release)), \
         patch.object(discogs_service, "get_master_versions", new=AsyncMock(return_value=[])), \
         patch.object(discogs_service, "get_artist", new=AsyncMock(return_value={})), \
         patch.object(wikipedia_service, "get_artist_biography", new=AsyncMock(return_value=wiki_tuple)), \
         patch.object(wikipedia_service, "get_album_reception", new=AsyncMock(return_value=("Capolavoro modale.", []))), \
         patch.object(ai_enricher, "is_available", return_value=False):

        response = client.get("/api/v1/album/999111?id_type=release&lang=it")
        assert response.status_code == 200
        data = response.json()
        assert data["primary_artist"]["name"] == "Miles Davis"
        assert "Miles Davis" in data["primary_artist"]["biography"]
        assert "## Storia" in data["primary_artist"]["biography"]
        assert data["primary_artist"]["wikipedia_url"] == "https://it.wikipedia.org/wiki/Miles_Davis"
        assert data["primary_artist"]["wikipedia_title"] == "Miles Davis"





