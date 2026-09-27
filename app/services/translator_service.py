import logging
import hashlib
from typing import Optional, Tuple
import httpx

from app.services.ai_enricher import ai_enricher
from app.utils.cache import cache

logger = logging.getLogger(__name__)

MYMEMORY_API_URL = "https://api.mymemory.translated.net/get"

class TranslatorService:
    """
    Servizio di traduzione specializzato per note storiche ed archivistiche musicali.
    Strategia:
    1. Primaria: Google Gemini AI (se chiave configurata o passata dal client),
       con prompt musicologico specializzato che preserva codici matrice, formati e nomi propri.
    2. Fallback: Motore Neurale Machine Translation (MyMemory) con suddivisione in chunk.
    """

    def __init__(self):
        pass

    async def translate_text(
        self,
        text: str,
        target_lang: str = "it",
        gemini_api_key: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Traduce il testo nella lingua richiesta.
        Restituisce una tupla (testo_tradotto, sorgente) dove sorgente è 'gemini_ai' o 'neural_mt'.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            return None, None

        # Verifica cache
        text_hash = hashlib.md5(f"{clean_text[:500]}:{target_lang}:{gemini_api_key or ''}".encode("utf-8")).hexdigest()
        cache_key = f"trans:{target_lang}:{text_hash}"
        cached = cache.get(cache_key)
        if cached:
            return cached.get("text"), cached.get("source")

        # 1. Tentativo primario: Gemini AI
        if ai_enricher.is_available(override_key=gemini_api_key):
            try:
                ai_translation = await ai_enricher.translate_with_gemini(
                    text=clean_text,
                    target_lang=target_lang,
                    api_key=gemini_api_key
                )
                if ai_translation and ai_translation.strip():
                    result = (ai_translation.strip(), "gemini_ai")
                    cache.set(cache_key, {"text": result[0], "source": result[1]})
                    return result
            except Exception as e:
                logger.warning("Tentativo di traduzione con Gemini fallito, passaggio al fallback: %s", e)

        # 2. Fallback neurale (MyMemory MT chunked)
        try:
            neural_translation = await self._translate_neural_mymemory(clean_text, target_lang=target_lang)
            if neural_translation and neural_translation.strip():
                result = (neural_translation.strip(), "neural_mt")
                cache.set(cache_key, {"text": result[0], "source": result[1]})
                return result
        except Exception as e:
            logger.error("Errore anche durante il fallback neurale di traduzione: %s", e)

        return None, None

    async def _translate_neural_mymemory(self, text: str, target_lang: str = "it") -> Optional[str]:
        """
        Traduce un testo lungo suddividendolo in blocchi logici (paragrafi o frasi)
        compatibili con i limiti della REST API MyMemory MT.
        """
        # Se lingua target è identica o testo brevissimo
        if target_lang == "en":
            return text

        # Suddivisione in paragrafi
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            return None

        chunks: list[str] = []
        current_chunk = ""

        for p in paragraphs:
            if len(current_chunk) + len(p) + 1 < 450:
                current_chunk = f"{current_chunk}\n{p}" if current_chunk else p
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # Se un singolo paragrafo supera 450 caratteri, spezzalo per frasi
                if len(p) > 450:
                    sentences = p.split(". ")
                    sub_chunk = ""
                    for s in sentences:
                        s_dot = s if s.endswith(".") else f"{s}."
                        if len(sub_chunk) + len(s_dot) + 1 < 450:
                            sub_chunk = f"{sub_chunk} {s_dot}" if sub_chunk else s_dot
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk)
                            sub_chunk = s_dot
                    if sub_chunk:
                        chunks.append(sub_chunk)
                    current_chunk = ""
                else:
                    current_chunk = p

        if current_chunk:
            chunks.append(current_chunk)

        translated_chunks: list[str] = []
        langpair = f"en|{target_lang}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            for chunk in chunks:
                try:
                    params = {
                        "q": chunk,
                        "langpair": langpair
                    }
                    resp = await client.get(MYMEMORY_API_URL, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        resp_data = data.get("responseData", {})
                        translated = resp_data.get("translatedText")
                        if translated and "MYMEMORY WARNING" not in translated.upper():
                            translated_chunks.append(translated)
                        else:
                            translated_chunks.append(chunk)
                    else:
                        translated_chunks.append(chunk)
                except Exception as chunk_err:
                    logger.warning("Errore traduzione chunk neurale: %s", chunk_err)
                    translated_chunks.append(chunk)

        if translated_chunks:
            return "\n\n".join(translated_chunks)
        return None

translator_service = TranslatorService()
