"""
Modul scraper berita dari Google News.
Menggunakan Google News RSS + DuckDuckGo untuk resolve URL + newspaper3k/BS4 untuk ekstraksi konten.
Compatible dengan Streamlit Cloud (tidak bergantung pada HTTP resolve ke Google News).
"""

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, quote_plus
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from newspaper import Article

# DuckDuckGo search untuk resolve URL
try:
    from ddgs import DDGS
    _HAS_DDGS = True
except ImportError:
    _HAS_DDGS = False

# googlenewsdecoder sebagai opsi pertama (bisa gagal di cloud)
try:
    from googlenewsdecoder import new_decoderv1
    _HAS_DECODER = True
except ImportError:
    _HAS_DECODER = False

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

# Mapping periode ke parameter Google News RSS
_PERIOD_MAP = {
    "1h": "1h", "1d": "1d", "7d": "7d", "30d": "30d",
    "1y": "1y", "1m": "30d", "6m": "180d", "12m": "1y",
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


# ══════════════════════════════════════════════════════════════════════
# URL Resolution
# ══════════════════════════════════════════════════════════════════════

def _resolve_via_decoder(url: str) -> str | None:
    """Coba resolve Google News URL pakai googlenewsdecoder (butuh HTTP ke Google)."""
    if not _HAS_DECODER:
        return None
    try:
        decoded = new_decoderv1(url, interval=2)
        if decoded and decoded.get("decoded_url"):
            logger.info(f"URL decoded via googlenewsdecoder: {decoded['decoded_url']}")
            return decoded["decoded_url"]
    except Exception as e:
        logger.debug(f"googlenewsdecoder gagal: {e}")
    return None


def _resolve_via_ddgs(judul: str, sumber: str) -> str | None:
    """Cari URL asli artikel via DuckDuckGo berdasarkan judul + sumber."""
    if not _HAS_DDGS:
        return None
    try:
        # Bersihkan judul dari nama sumber di akhir (format: "Judul - Sumber")
        clean_title = re.sub(r'\s*[-–|]\s*[^-–|]+$', '', judul).strip()
        query = f"{clean_title} {sumber}" if sumber else clean_title
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=3))
        for r in results:
            href = r.get("href", "")
            domain = urlparse(href).netloc.lower().replace("www.", "")
            # Skip social media dan Google sendiri
            skip = {"youtube.com", "facebook.com", "twitter.com", "instagram.com",
                    "tiktok.com", "linkedin.com", "wikipedia.org", "google.com"}
            if any(s in domain for s in skip):
                continue
            # Kalau sumber cocok, langsung return
            if sumber and sumber.lower().replace(" ", "") in domain.replace(".", ""):
                logger.info(f"URL found via DDG (exact match): {href}")
                return href
        # Kalau tidak ada exact match, return result pertama yang bukan skip
        for r in results:
            href = r.get("href", "")
            domain = urlparse(href).netloc.lower()
            if not any(s in domain for s in skip):
                logger.info(f"URL found via DDG (first result): {href}")
                return href
    except Exception as e:
        logger.debug(f"DuckDuckGo search gagal: {e}")
    return None


def _resolve_via_redirect(url: str) -> str | None:
    """Fallback: follow HTTP redirect dari Google News URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if "news.google.com" not in resp.url:
            return resp.url
    except Exception as e:
        logger.debug(f"Redirect follow gagal: {e}")
    return None


def _resolve_google_news_url(url: str, judul: str = "", sumber: str = "") -> str:
    """
    Resolve URL Google News ke URL asli artikel.
    Urutan:
    1. googlenewsdecoder (tercepat jika berhasil)
    2. DuckDuckGo search by title (paling reliable di cloud)
    3. HTTP redirect follow (fallback terakhir)
    """
    if not url or "news.google.com" not in url:
        return url

    # Method 1: googlenewsdecoder
    resolved = _resolve_via_decoder(url)
    if resolved:
        return resolved

    # Method 2: DuckDuckGo search by title + source
    if judul:
        resolved = _resolve_via_ddgs(judul, sumber)
        if resolved:
            return resolved

    # Method 3: HTTP redirect
    resolved = _resolve_via_redirect(url)
    if resolved:
        return resolved

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
    """Scraper berita dari Google News Indonesia via RSS feed."""

    _SKIP_DOMAINS = {
        "youtube.com", "facebook.com", "twitter.com", "instagram.com",
        "tiktok.com", "linkedin.com", "wikipedia.org", "google.com",
    }

    _RSS_BASE = "https://news.google.com/rss/search"

    def __init__(self, max_results: int = 10, period: str = "7d"):
        self.max_results = max_results
        self.period = _PERIOD_MAP.get(period, period)

    def cari_berita(self, keyword: str) -> list[BeritaItem]:
        """
        Cari berita via Google News RSS feed (tanpa library GNews).
        Tidak perlu resolve URL — hanya ambil metadata.
        """
        logger.info(f"Mencari berita dengan keyword: '{keyword}'")
        query = quote_plus(keyword)
        rss_url = (
            f"{self._RSS_BASE}?q={query}+when:{self.period}"
            f"&hl=id&gl=ID&ceid=ID:id"
        )

        try:
            resp = requests.get(rss_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Gagal fetch RSS: {e}")
            return self._fallback_ddgs_search(keyword)

        try:
            root = ElementTree.fromstring(resp.content)
        except ElementTree.ParseError as e:
            logger.error(f"Gagal parse RSS XML: {e}")
            return self._fallback_ddgs_search(keyword)

        berita_list = []
        for item in root.findall(".//item"):
            if len(berita_list) >= self.max_results:
                break

            title_el = item.find("title")
            link_el = item.find("link")
            pub_date_el = item.find("pubDate")
            source_el = item.find("source")

            judul = title_el.text.strip() if title_el is not None and title_el.text else ""
            url = link_el.text.strip() if link_el is not None and link_el.text else ""
            tanggal = pub_date_el.text.strip() if pub_date_el is not None and pub_date_el.text else ""
            sumber = source_el.text.strip() if source_el is not None and source_el.text else ""

            # Bersihkan judul: "Judul artikel - Sumber" -> ambil sumber jika belum ada
            if not sumber and " - " in judul:
                sumber = judul.rsplit(" - ", 1)[-1].strip()

            berita = BeritaItem(
                judul=judul,
                sumber=sumber,
                tanggal=tanggal,
                url=url,
            )
            berita_list.append(berita)

        logger.info(f"RSS: ditemukan {len(berita_list)} berita")

        if not berita_list:
            return self._fallback_ddgs_search(keyword)

        return berita_list

    def _fallback_ddgs_search(self, keyword: str) -> list[BeritaItem]:
        """Fallback: cari berita via DuckDuckGo jika RSS gagal."""
        if not _HAS_DDGS:
            logger.warning("DuckDuckGo search tidak tersedia")
            return []

        logger.info(f"Fallback ke DuckDuckGo search untuk: '{keyword}'")
        try:
            ddgs = DDGS()
            results = list(ddgs.news(keyword, max_results=self.max_results))
        except Exception as e:
            logger.error(f"DuckDuckGo news search gagal: {e}")
            return []

        berita_list = []
        for r in results:
            domain = urlparse(r.get("url", "")).netloc.lower().replace("www.", "")
            if any(skip in domain for skip in self._SKIP_DOMAINS):
                continue

            berita = BeritaItem(
                judul=r.get("title", ""),
                sumber=r.get("source", domain),
                tanggal=r.get("date", ""),
                url=r.get("url", ""),
                url_asli=r.get("url", ""),
            )
            berita_list.append(berita)

        logger.info(f"DuckDuckGo: ditemukan {len(berita_list)} berita")
        return berita_list

    def cari_berita_google_search(self, keyword: str) -> list[BeritaItem]:
        """Fallback tambahan: cari via DuckDuckGo text search."""
        return self._fallback_ddgs_search(keyword)

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
            url_asli = _resolve_google_news_url(berita.url, judul=berita.judul, sumber=berita.sumber)
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
