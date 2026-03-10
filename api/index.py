"""
API Flask untuk Web Scraping Berita (tanpa AI).
Deploy ke Vercel sebagai serverless function.
Jalankan lokal: python api/index.py
"""

import os
import sys
from urllib.parse import urlparse

from flask import Flask, request, jsonify, send_from_directory

# Tambah parent directory agar bisa import scraper.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import GoogleNewsScraper, BeritaItem
from analyzer import analisis_berita

app = Flask(__name__)

PUBLIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public"
)


@app.route("/")
def index():
    """Serve frontend HTML."""
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.route("/api/search", methods=["POST"])
def search_news():
    """Cari berita berdasarkan keyword dari Google News."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body harus berupa JSON"}), 400

    keyword = str(data.get("keyword", "")).strip()
    if not keyword or len(keyword) > 200:
        return jsonify({"error": "Keyword tidak valid (1-200 karakter)"}), 400

    try:
        max_results = min(max(int(data.get("max_results", 10)), 1), 100)
    except (ValueError, TypeError):
        max_results = 10

    period = str(data.get("period", "7d"))
    valid_periods = {"1d", "7d", "30d", "1y", "2y", "3y", "5y"}
    if period not in valid_periods:
        period = "7d"

    scraper = GoogleNewsScraper(max_results=max_results, period=period)
    berita_list = scraper.cari_berita(keyword)

    # Fallback ke Google Search jika Google News kosong
    if not berita_list:
        berita_list = scraper.cari_berita_google_search(keyword)

    results = [
        {
            "judul": b.judul,
            "sumber": b.sumber,
            "tanggal": b.tanggal,
            "url": b.url,
        }
        for b in berita_list
    ]

    return jsonify({"results": results, "count": len(results)})


@app.route("/api/extract", methods=["POST"])
def extract_content():
    """Ekstrak konten dari satu URL artikel."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body harus berupa JSON"}), 400

    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify({"error": "URL harus diisi"}), 400

    # Validasi URL — hanya izinkan http/https untuk mencegah SSRF
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return jsonify({"error": "URL harus menggunakan http atau https"}), 400

    judul = str(data.get("judul", ""))
    sumber = str(data.get("sumber", ""))
    tanggal = str(data.get("tanggal", ""))

    keyword = str(data.get("keyword", ""))

    scraper = GoogleNewsScraper()
    berita = BeritaItem(judul=judul, sumber=sumber, tanggal=tanggal, url=url)
    scraper.ekstrak_konten(berita)

    # Analisis rangkuman & sentimen jika konten berhasil diekstrak
    rangkuman = ""
    sentimen = ""
    skor_sentimen = 0.0
    if berita.konten and berita.status == "OK":
        hasil = analisis_berita(berita.judul, berita.konten, keyword=keyword)
        rangkuman = hasil["rangkuman"]
        sentimen = hasil["sentimen"]
        skor_sentimen = hasil["skor_sentimen"]

    return jsonify(
        {
            "judul": berita.judul,
            "sumber": berita.sumber,
            "tanggal": berita.tanggal,
            "url": berita.url,
            "url_asli": berita.url_asli,
            "konten": berita.konten,
            "status": berita.status,
            "rangkuman": rangkuman,
            "sentimen": sentimen,
            "skor_sentimen": skor_sentimen,
        }
    )


# Untuk development lokal
if __name__ == "__main__":
    app.run(debug=True, port=5000)
