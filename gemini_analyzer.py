"""
Modul analisis berita menggunakan Google Gemini API.
- Rangkuman: AI-generated summary
- Sentimen: AI-based sentiment analysis (POSITIF / NEGATIF / NETRAL)
Fallback ke analisis berbasis kamus jika Gemini gagal atau API key kosong.
"""

import json
import re
import requests

# Import fallback analyzer (kamus kata)
from analyzer import analisis_berita as analisis_fallback

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _parse_json_response(text: str) -> dict | None:
    """Parse JSON dari response Gemini, handle markdown code blocks."""
    # Coba extract JSON dari code block ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)

    # Coba parse langsung
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Coba cari object JSON di dalam teks
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def analisis_berita_gemini(
    judul: str,
    konten: str,
    keyword: str = "",
    api_key: str = "",
) -> dict:
    """
    Analisis berita menggunakan Google Gemini API.
    Fallback ke analisis kamus jika Gemini gagal.

    Args:
        judul: Judul berita.
        konten: Isi berita lengkap.
        keyword: Kata kunci pencarian (institusi target).
        api_key: Google Gemini API key.

    Returns:
        Dict dengan keys: rangkuman, sentimen, skor_sentimen
    """
    if not api_key or not konten:
        hasil = analisis_fallback(judul, konten, keyword=keyword)
        hasil["sumber_analisis"] = "Kamus Kata"
        return hasil

    try:
        # Potong konten jika terlalu panjang (hemat token)
        konten_potong = konten[:4000] if len(konten) > 4000 else konten

        prompt = f"""Analisis berita berikut dan berikan output dalam format JSON.

Judul: {judul}
Kata Kunci Institusi: {keyword or '(tidak ada)'}

Isi Berita:
{konten_potong}

Instruksi:
1. Buat rangkuman singkat (2-3 kalimat) dalam Bahasa Indonesia
2. Tentukan sentimen dari KEDUA perspektif:
   - POV Institusi/Perusahaan ({keyword or 'subjek berita'}): apakah berita ini merugikan atau menguntungkan reputasi mereka
   - POV Publik/Rakyat: bagaimana masyarakat memandang berita ini
3. Konteks penting:
   - Jika institusi MENINDAK pihak lain yang nakal (misal mencabut izin perusahaan penipu) = POSITIF (melindungi publik)
   - Jika institusi GAGAL/LALAI dalam tugasnya = NEGATIF
   - Jika berita netral/informatif tanpa dampak reputasi = NETRAL
4. Berikan skor sentimen: angka desimal dari -1.0 (sangat negatif) sampai 1.0 (sangat positif)

Format output (JSON saja, tanpa penjelasan tambahan):
{{"rangkuman": "...", "sentimen": "POSITIF/NEGATIF/NETRAL", "skor_sentimen": 0.0}}"""

        # Panggil Gemini REST API langsung (tanpa SDK, lebih reliable)
        resp = requests.post(
            f"{GEMINI_API_URL}?key={api_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if resp.status_code != 200:
            hasil = analisis_fallback(judul, konten, keyword=keyword)
            hasil["sumber_analisis"] = f"Kamus Kata (Gemini HTTP {resp.status_code})"
            return hasil

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = _parse_json_response(text)

        if result:
            sentimen = str(result.get("sentimen", "NETRAL")).upper().strip()
            if sentimen not in ("POSITIF", "NEGATIF", "NETRAL"):
                sentimen = "NETRAL"

            try:
                skor = float(result.get("skor_sentimen", 0.0))
                skor = max(-1.0, min(1.0, skor))
            except (ValueError, TypeError):
                skor = 0.0

            return {
                "rangkuman": str(result.get("rangkuman", "")),
                "sentimen": sentimen,
                "skor_sentimen": round(skor, 2),
                "sumber_analisis": "Gemini AI",
            }

        # JSON parse gagal, fallback
        hasil = analisis_fallback(judul, konten, keyword=keyword)
        hasil["sumber_analisis"] = "Kamus Kata (Gemini gagal parse)"
        return hasil

    except Exception as e:
        # Gemini error (rate limit, network, dll), fallback ke kamus
        hasil = analisis_fallback(judul, konten, keyword=keyword)
        hasil["sumber_analisis"] = f"Kamus Kata ({type(e).__name__}: {str(e)[:80]})"
        return hasil
