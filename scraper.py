"""
Modul scraper berita dari Google News.
Menggunakan GNews + requests + BeautifulSoup + newspaper3k untuk ekstraksi konten.
Menangani redirect URL Google News dan fallback ke Google Search jika tidak ditemukan.
"""

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from gnews import GNews
from googlesearch import search as google_search
from newspaper import Article
from googlenewsdecoder import new_decoderv1

logger = logging.getLogger(__name__)

# Header browser agar tidak diblokir situs berita
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class BeritaItem:
    """Representasi satu berita."""
    judul: str = ""
    sumber: str = ""
    tanggal: str = ""
    url: str = ""
    url_asli: str = ""  # URL asli setelah resolve redirect
    konten: str = ""
    rangkuman: str = ""
    sentimen: str = ""  # Positif / Negatif / Netral
    status: str = "OK"


def _resolve_google_news_url(url: str) -> str:
    """
    Resolve URL redirect Google News ke URL asli artikel.
    Menggunakan googlenewsdecoder untuk decode URL encoded Google News.
    """
    if not url:
        return url

    # Cek apakah ini URL Google News
    if "news.google.com" not in url:
        return url

    try:
        # Gunakan googlenewsdecoder untuk decode URL
        decoded = new_decoderv1(url, interval=5)
        if decoded and decoded.get("decoded_url"):
            logger.info(f"URL decoded: {decoded['decoded_url']}")
            return decoded["decoded_url"]
    except Exception as e:
        logger.warning(f"googlenewsdecoder gagal: {e}")

    # Fallback: coba follow redirect biasa
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if "news.google.com" not in resp.url:
            return resp.url
    except Exception as e:
        logger.warning(f"Redirect follow gagal: {e}")

    return url


def _ekstrak_dengan_newspaper(url: str) -> tuple[str, str]:
    """
    Ekstrak konten menggunakan newspaper3k.
    Returns: (judul, konten)
    """
    try:
        article = Article(url, language="id")
        article.download()
        article.parse()
        return article.title or "", article.text or ""
    except Exception as e:
        logger.debug(f"newspaper3k gagal untuk {url}: {e}")
        return "", ""


def _ekstrak_dengan_requests(url: str) -> tuple[str, str]:
    """
    Fallback: Ekstrak konten menggunakan requests + BeautifulSoup.
    Lebih robust karena menggunakan User-Agent yang benar.
    Returns: (judul, konten)
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        # Deteksi encoding yang benar
        if resp.encoding and resp.encoding.lower() != "utf-8":
            resp.encoding = resp.apparent_encoding

        soup = BeautifulSoup(resp.text, "html.parser")

        # Ambil judul
        judul = ""
        title_tag = soup.find("title")
        if title_tag:
            judul = title_tag.get_text(strip=True)

        # Hapus elemen yang tidak relevan
        for tag in soup.find_all(
            ["script", "style", "nav", "header", "footer", "aside",
             "iframe", "noscript", "form", "button", "svg"]
        ):
            tag.decompose()

        # Cari konten artikel — coba berbagai selector umum
        konten = ""
        # Selector prioritas untuk situs berita Indonesia
        selectors = [
            {"name": "article"},
            {"attrs": {"class": re.compile(r"article|content|body|story|entry|post|detail", re.I)}},
            {"attrs": {"id": re.compile(r"article|content|body|story|entry|post|detail", re.I)}},
            {"attrs": {"itemprop": "articleBody"}},
            {"attrs": {"role": "article"}},
        ]

        for selector in selectors:
            artikel_element = soup.find(**selector)
            if artikel_element:
                # Ambil semua paragraf dari dalam elemen artikel
                paragraphs = artikel_element.find_all("p")
                if paragraphs:
                    konten = "\n\n".join(
                        p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
                    )
                else:
                    konten = artikel_element.get_text(separator="\n", strip=True)
                if len(konten) > 100:
                    break

        # Fallback: ambil semua paragraf di halaman
        if len(konten) < 100:
            all_paragraphs = soup.find_all("p")
            texts = [p.get_text(strip=True) for p in all_paragraphs if len(p.get_text(strip=True)) > 40]
            if texts:
                konten = "\n\n".join(texts)

        return judul, konten

    except Exception as e:
        logger.debug(f"requests+BS4 gagal untuk {url}: {e}")
        return "", ""


class GoogleNewsScraper:
    """Scraper berita dari Google News Indonesia."""

    # Domain yang bukan artikel berita (skip saat Google Search)
    _SKIP_DOMAINS = {
        "youtube.com", "facebook.com", "twitter.com", "instagram.com",
        "tiktok.com", "linkedin.com", "wikipedia.org", "google.com",
    }

    def __init__(self, max_results: int = 10, period: str = "7d"):
        """
        Args:
            max_results: Jumlah maksimal berita yang dicari.
            period: Periode pencarian ('1d', '7d', '30d', '1y').
        """
        self.max_results = max_results
        self.period = period
        self.google_news = GNews(
            language="id",
            country="ID",
            period=period,
            max_results=max_results,
        )

    def cari_berita(self, keyword: str) -> list[BeritaItem]:
        """
        Cari berita berdasarkan keyword.

        Args:
            keyword: Kata kunci pencarian.

        Returns:
            List BeritaItem dengan judul, sumber, tanggal, url.
        """
        logger.info(f"Mencari berita dengan keyword: '{keyword}'")
        try:
            hasil = self.google_news.get_news(keyword)
        except Exception as e:
            logger.error(f"Gagal mencari berita: {e}")
            return []

        berita_list = []
        for item in hasil:
            berita = BeritaItem(
                judul=item.get("title", ""),
                sumber=item.get("publisher", {}).get("title", "")
                if isinstance(item.get("publisher"), dict)
                else str(item.get("publisher", "")),
                tanggal=str(item.get("published date", "")),
                url=item.get("url", ""),
            )
            berita_list.append(berita)

        logger.info(f"Ditemukan {len(berita_list)} berita")
        return berita_list

    def cari_berita_google_search(self, keyword: str) -> list[BeritaItem]:
        """
        Fallback: Cari berita via Google Search biasa.
        Digunakan saat Google News tidak menemukan hasil.

        Args:
            keyword: Kata kunci pencarian.

        Returns:
            List BeritaItem dari hasil Google Search.
        """
        logger.info(f"Fallback ke Google Search untuk: '{keyword}'")
        query = f"{keyword} berita"

        try:
            results = list(google_search(
                query,
                num_results=self.max_results * 2,  # Ambil lebih banyak, nanti difilter
                lang="id",
                sleep_interval=1,
            ))
        except Exception as e:
            logger.error(f"Google Search gagal: {e}")
            return []

        berita_list = []
        for url in results:
            # Skip URL non-artikel
            domain = urlparse(url).netloc.lower().replace("www.", "")
            if any(skip in domain for skip in self._SKIP_DOMAINS):
                continue

            berita = BeritaItem(
                judul="",
                sumber=domain,
                tanggal="",
                url=url,
                url_asli=url,
            )
            berita_list.append(berita)

            if len(berita_list) >= self.max_results:
                break

        logger.info(f"Google Search: ditemukan {len(berita_list)} URL artikel")
        return berita_list

    def ekstrak_konten(self, berita: BeritaItem) -> BeritaItem:
        """
        Ekstrak isi lengkap artikel dari URL.
        1. Resolve redirect Google News → URL asli
        2. Coba newspaper3k dulu
        3. Fallback ke requests + BeautifulSoup

        Args:
            berita: BeritaItem yang sudah memiliki URL.

        Returns:
            BeritaItem dengan konten terisi.
        """
        if not berita.url:
            berita.status = "Tidak ada URL"
            return berita

        try:
            # Step 1: Resolve Google News redirect URL
            url_asli = _resolve_google_news_url(berita.url)
            berita.url_asli = url_asli
            logger.info(f"URL asli: {url_asli}")

            # Step 2: Coba newspaper3k (biasanya lebih bersih hasilnya)
            judul_np, konten_np = _ekstrak_dengan_newspaper(url_asli)

            if konten_np and len(konten_np) > 100:
                berita.konten = konten_np
                if judul_np and len(judul_np) > len(berita.judul):
                    berita.judul = judul_np
                berita.status = "OK"
                return berita

            # Step 3: Fallback ke requests + BeautifulSoup
            logger.info(f"Fallback ke BS4 untuk {url_asli}")
            judul_bs, konten_bs = _ekstrak_dengan_requests(url_asli)

            if konten_bs and len(konten_bs) > 50:
                berita.konten = konten_bs
                if judul_bs and not berita.judul:
                    berita.judul = judul_bs
                berita.status = "OK"
                return berita

            # Kedua metode gagal
            berita.status = "Konten kosong"

        except Exception as e:
            logger.warning(f"Gagal ekstrak konten dari {berita.url}: {e}")
            berita.status = f"Gagal: {str(e)[:80]}"

        return berita

    def cari_dan_ekstrak(
        self, keyword: str, progress_callback=None
    ) -> list[BeritaItem]:
        """
        Cari berita dan langsung ekstrak kontennya.

        Args:
            keyword: Kata kunci pencarian.
            progress_callback: Callable(current, total) untuk update progress.

        Returns:
            List BeritaItem lengkap dengan konten.
        """
        berita_list = self.cari_berita(keyword)
        total = len(berita_list)

        for i, berita in enumerate(berita_list):
            if progress_callback:
                progress_callback(i, total)

            self.ekstrak_konten(berita)

            # Delay kecil agar tidak terblokir
            time.sleep(0.5)

        if progress_callback:
            progress_callback(total, total)

        return berita_list
