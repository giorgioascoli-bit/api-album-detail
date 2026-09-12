import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.discogs_service import discogs_service
from app.services.wikipedia_service import wikipedia_service
from app.services.ai_enricher import ai_enricher
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

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
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
            {"name": "David Gilmour", "role": "Guitar", "tracks": ""}
        ],
        "tracklist": [
            {"position": "A1", "title": "Speak to Me", "duration": "1:05"}
        ],
        "master_id": 10362,
        "community": {"rating": {"average": 4.88, "count": 12000}}
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
        "critical_reception": ["Capolavoro assoluto", "Pietra miliare del rock"]
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


