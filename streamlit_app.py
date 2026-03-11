"""
Streamlit App — Scraping Berita Google News Indonesia
Fitur: pencarian berita, ekstraksi konten, analisis sentimen & rangkuman.
Menggunakan Google Gemini AI (gratis) atau fallback kamus kata.
Deploy ke Streamlit Cloud.
"""

import streamlit as st
import pandas as pd
import time
from io import BytesIO

from scraper import GoogleNewsScraper, BeritaItem
from analyzer import analisis_berita
from gemini_analyzer import analisis_berita_gemini

# ══════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Scraping Berita - Google News Indonesia",
    page_icon="📰",
    layout="wide",
)

# ── Custom CSS ──
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a4f7a, #2a6faa);
        padding: 1.5rem 2rem;
        border-radius: 0.75rem;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-size: 1.6rem; }
    .stat-box { text-align: center; padding: 1rem; }
    .stat-box .num { font-size: 2rem; font-weight: 700; }
    .stat-box .label { font-size: 0.8rem; color: #6c757d; }
    div[data-testid="stExpander"] details summary p { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# Header
# ══════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="main-header">
    <h1>📰 Scraping Berita — Google News Indonesia</h1>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# Sidebar — Search Form
# ══════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("🔍 Pencarian Berita")

    keyword = st.text_input("Kata Kunci", placeholder="Contoh: kebijakan moneter OJK")

    col1, col2 = st.columns(2)
    with col1:
        max_results = st.number_input("Jumlah", min_value=1, max_value=50, value=10)
    with col2:
        period_options = {
            "1 Hari": "1d",
            "7 Hari": "7d",
            "30 Hari": "30d",
            "1 Tahun": "1y",
            "2 Tahun": "2y",
            "3 Tahun": "3y",
            "5 Tahun": "5y",
        }
        period_label = st.selectbox("Periode", list(period_options.keys()), index=1)
        period = period_options[period_label]

    filter_sentimen = st.selectbox(
        "Filter Sentimen",
        ["General (Semua)", "Negatif Saja", "Positif Saja"],
    )

    st.caption(
        "**General:** Tampilkan semua berita.  \n"
        "**Negatif/Positif Saja:** Sistem mencari sampai menemukan jumlah yang diminta."
    )

    btn_search = st.button("🔍 Cari Berita", type="primary", use_container_width=True)

    st.divider()

    # ── Gemini API Key ──
    st.subheader("🤖 AI Analyzer (Opsional)")

    # Cek apakah ada API key di secrets (untuk deploy)
    secret_key = ""
    try:
        secret_key = st.secrets["GEMINI_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass

    gemini_key = st.text_input(
        "Gemini API Key",
        value=secret_key,
        type="password",
        placeholder="Masukkan API key...",
        help="Gratis dari https://aistudio.google.com/apikey",
    )

    if gemini_key:
        st.success("✅ Gemini AI aktif")
    else:
        st.info("💡 Tanpa API key → pakai kamus kata")

# ══════════════════════════════════════════════════════════════════════
# Session State
# ══════════════════════════════════════════════════════════════════════

if "berita_data" not in st.session_state:
    st.session_state.berita_data = []


# ══════════════════════════════════════════════════════════════════════
# Helper Functions
# ══════════════════════════════════════════════════════════════════════

def sentimen_badge(sentimen: str) -> str:
    if sentimen == "POSITIF":
        return "🟢 POSITIF"
    elif sentimen == "NEGATIF":
        return "🔴 NEGATIF"
    elif sentimen == "NETRAL":
        return "🟡 NETRAL"
    return "-"


def create_excel(data: list[dict]) -> bytes:
    """Buat file Excel dari data berita."""
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Berita")
    return output.getvalue()


def create_csv(data: list[dict]) -> str:
    """Buat file CSV dari data berita."""
    df = pd.DataFrame(data)
    return df.to_csv(index=False)


# ══════════════════════════════════════════════════════════════════════
# Search Logic
# ══════════════════════════════════════════════════════════════════════

if btn_search:
    if not keyword or not keyword.strip():
        st.warning("⚠️ Masukkan kata kunci terlebih dahulu.")
    else:
        keyword = keyword.strip()
        is_targeted = filter_sentimen in ("Negatif Saja", "Positif Saja")
        target_sentimen = "NEGATIF" if filter_sentimen == "Negatif Saja" else "POSITIF" if filter_sentimen == "Positif Saja" else None

        # Step 1: Search
        fetch_size = min(max(max_results * 5, 50), 100) if is_targeted else max_results

        with st.spinner("🔍 Mencari berita di Google News..."):
            scraper = GoogleNewsScraper(max_results=fetch_size, period=period)
            search_results = scraper.cari_berita(keyword)

            if not search_results:
                search_results = scraper.cari_berita_google_search(keyword)

        if not search_results:
            st.warning("😔 Tidak ditemukan berita. Coba kata kunci lain atau perluas periode.")
        else:
            # Step 2: Extract & Analyze
            all_berita = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            if is_targeted:
                # ── MODE TARGETED ──
                matched_count = 0
                analyzed_count = 0
                total_pool = len(search_results)

                for sr in search_results:
                    if matched_count >= max_results:
                        break

                    analyzed_count += 1
                    status_text.text(
                        f"Mencari berita {filter_sentimen.lower()}: {matched_count}/{max_results} "
                        f"ditemukan (menganalisis {analyzed_count}/{total_pool})..."
                    )
                    progress_bar.progress(matched_count / max_results if max_results > 0 else 0)

                    # Extract
                    berita = BeritaItem(
                        judul=sr.judul, sumber=sr.sumber,
                        tanggal=sr.tanggal, url=sr.url,
                    )
                    scraper.ekstrak_konten(berita)

                    if berita.status != "OK" or not berita.konten:
                        continue

                    # Analyze (Gemini jika ada key, fallback ke kamus)
                    if gemini_key:
                        hasil = analisis_berita_gemini(berita.judul, berita.konten, keyword=keyword, api_key=gemini_key)
                        time.sleep(4)  # Delay agar tidak kena rate limit Gemini
                    else:
                        hasil = analisis_berita(berita.judul, berita.konten, keyword=keyword)

                    # Filter berdasarkan sentimen target
                    if hasil["sentimen"] != target_sentimen:
                        continue

                    matched_count += 1
                    all_berita.append({
                        "No": matched_count,
                        "Judul": berita.judul,
                        "Sumber": berita.sumber,
                        "Tanggal": berita.tanggal,
                        "URL": berita.url_asli or berita.url,
                        "Status": berita.status,
                        "Sentimen": hasil["sentimen"],
                        "Skor": hasil["skor_sentimen"],
                        "Rangkuman": hasil["rangkuman"],
                        "Konten": berita.konten,
                        "AI": hasil.get("sumber_analisis", "Kamus Kata"),
                    })

                progress_bar.progress(1.0)
                status_text.text("✅ Selesai!")
                time.sleep(0.5)
                status_text.empty()
                progress_bar.empty()

                if matched_count >= max_results:
                    st.success(
                        f"Berhasil menemukan **{matched_count}** berita bersentimen "
                        f"**{filter_sentimen.lower()}** (dari {analyzed_count} artikel yang dianalisis)."
                    )
                else:
                    st.warning(
                        f"Hanya ditemukan **{matched_count}** dari **{max_results}** berita "
                        f"{filter_sentimen.lower()} yang diminta (dari {analyzed_count} artikel yang tersedia). "
                        f"Coba perluas periode atau ubah kata kunci."
                    )

            else:
                # ── MODE GENERAL ──
                total = len(search_results)
                for i, sr in enumerate(search_results):
                    status_text.text(f"Mengekstrak {i + 1}/{total}: {sr.judul[:50]}...")
                    progress_bar.progress((i) / total if total > 0 else 0)

                    berita = BeritaItem(
                        judul=sr.judul, sumber=sr.sumber,
                        tanggal=sr.tanggal, url=sr.url,
                    )
                    scraper.ekstrak_konten(berita)

                    rangkuman = ""
                    sentimen = ""
                    skor = 0.0
                    sumber_ai = "Kamus Kata"
                    if berita.konten and berita.status == "OK":
                        if gemini_key:
                            hasil = analisis_berita_gemini(berita.judul, berita.konten, keyword=keyword, api_key=gemini_key)
                            time.sleep(4)  # Delay agar tidak kena rate limit Gemini
                        else:
                            hasil = analisis_berita(berita.judul, berita.konten, keyword=keyword)
                        rangkuman = hasil["rangkuman"]
                        sentimen = hasil["sentimen"]
                        skor = hasil["skor_sentimen"]
                        sumber_ai = hasil.get("sumber_analisis", "Kamus Kata")

                    all_berita.append({
                        "No": i + 1,
                        "Judul": berita.judul,
                        "Sumber": berita.sumber,
                        "Tanggal": berita.tanggal,
                        "URL": berita.url_asli or berita.url,
                        "Status": berita.status,
                        "Sentimen": sentimen,
                        "Skor": skor,
                        "Rangkuman": rangkuman,
                        "Konten": berita.konten,
                        "AI": sumber_ai,
                    })

                progress_bar.progress(1.0)
                status_text.text("✅ Selesai!")
                time.sleep(0.5)
                status_text.empty()
                progress_bar.empty()

                ok_count = sum(1 for b in all_berita if b["Status"] == "OK")
                st.success(f"Berhasil mengekstrak **{ok_count}/{total}** artikel.")

            # Simpan mode analisis yang digunakan
            mode = "🤖 Gemini AI" if gemini_key else "📖 Kamus Kata"
            st.session_state.berita_data = all_berita
            st.session_state.analisis_mode = mode

# ══════════════════════════════════════════════════════════════════════
# Display Results
# ══════════════════════════════════════════════════════════════════════

data = st.session_state.berita_data

if data:
    # ── Mode indicator ──
    mode = st.session_state.get("analisis_mode", "")
    if mode:
        st.caption(f"Mode analisis: **{mode}**")

    # ── Stats ──
    total = len(data)
    ok = sum(1 for b in data if b["Status"] == "OK")
    positif = sum(1 for b in data if b["Sentimen"] == "POSITIF")
    negatif = sum(1 for b in data if b["Sentimen"] == "NEGATIF")
    netral = sum(1 for b in data if b["Sentimen"] == "NETRAL")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Berita", total)
    c2.metric("Konten Berhasil", ok)
    c3.metric("🟢 Positif", positif)
    c4.metric("🔴 Negatif", negatif)
    c5.metric("🟡 Netral", netral)

    st.divider()

    # ── Download Buttons ──
    export_data = []
    for b in data:
        export_data.append({
            "No": b["No"],
            "Judul": b["Judul"],
            "Sumber": b["Sumber"],
            "Tanggal": b["Tanggal"],
            "URL": b["URL"],
            "Status": b["Status"],
            "Sentimen": b["Sentimen"],
            "Skor Sentimen": b["Skor"],
            "Rangkuman": b["Rangkuman"],
            "Konten": b["Konten"],
        })

    slug = keyword.strip().replace(" ", "_")[:30] if keyword else "hasil"

    col_dl1, col_dl2, _ = st.columns([1, 1, 4])
    with col_dl1:
        st.download_button(
            "📥 Download CSV",
            data=create_csv(export_data),
            file_name=f"berita_{slug}.csv",
            mime="text/csv",
        )
    with col_dl2:
        st.download_button(
            "📥 Download Excel",
            data=create_excel(export_data),
            file_name=f"berita_{slug}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.divider()

    # ── Table ──
    for b in data:
        badge = sentimen_badge(b["Sentimen"])
        status_icon = "✅" if b["Status"] == "OK" else "❌"

        with st.expander(f"**{b['No']}.** {b['Judul']}  —  {b['Sumber']}  |  {status_icon} {badge}"):
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.markdown(f"**Sumber:** {b['Sumber']}")
                st.markdown(f"**Tanggal:** {b['Tanggal']}")
            with col_info2:
                st.markdown(f"**Status:** {b['Status']}")
                st.markdown(f"**Sentimen:** {badge} (skor: {b['Skor']})")
                st.markdown(f"**Analisis:** {b.get('AI', '-')}")

            if b["URL"]:
                st.markdown(f"🔗 [Buka artikel]({b['URL']})")

            if b["Rangkuman"]:
                st.info(f"**📝 Rangkuman:** {b['Rangkuman']}")

            if b["Konten"]:
                st.text_area(
                    "Isi Berita Lengkap",
                    value=b["Konten"],
                    height=250,
                    disabled=True,
                    key=f"konten_{b['No']}",
                )
            else:
                st.caption("_(konten tidak tersedia)_")

else:
    st.info("👈 Masukkan kata kunci di sidebar dan klik **Cari Berita** untuk memulai.")
