# 📰 Web Scraping Berita — Google News Indonesia

Dashboard untuk mencari berita dari **Google News Indonesia** dan mengekstrak konten artikel secara otomatis. **Tanpa AI** — bisa di-deploy ke **Vercel** secara gratis.

## Fitur

- 🔍 Pencarian berita berdasarkan keyword dari Google News
- 📄 Ekstraksi otomatis isi artikel dari setiap link
- 📊 Dashboard interaktif (HTML/CSS/JS + Flask API)
- 📥 Download hasil ke CSV / Excel
- 🚀 Siap deploy ke Vercel

## Prasyarat

- **Python 3.10+** — [Download](https://www.python.org/downloads/)

## Instalasi & Jalankan Lokal

```bash
pip install -r requirements.txt
python api/index.py
```

Buka browser di `http://localhost:5000`.

## Deploy ke Vercel

### 1. Install Vercel CLI

```bash
npm install -g vercel
```

### 2. Login & Deploy

```bash
vercel login
vercel
```

Atau hubungkan repository GitHub ke Vercel Dashboard di https://vercel.com.

## Struktur File

```
WebScrappingNegWOAI/
├── api/
│   └── index.py          # Flask API (serverless function di Vercel)
├── public/
│   └── index.html        # Frontend HTML/CSS/JS
├── scraper.py            # Modul scraping Google News + ekstraksi konten
├── vercel.json           # Konfigurasi Vercel
├── requirements.txt      # Dependencies Python
└── README.md             # Dokumentasi ini
```

## Cara Penggunaan

1. Masukkan **kata kunci** (misal: "kebijakan moneter OJK")
2. Atur jumlah berita dan periode pencarian
3. Klik **Cari & Ekstrak Berita**
4. Lihat hasil di tabel dan klik untuk melihat detail
5. **Download** hasil ke CSV atau Excel

## Catatan Penting

- Vercel memiliki timeout **10 detik** per request (tier gratis). Jika artikel lambat diekstrak, mungkin timeout.
- Beberapa situs memblokir scraping — ini normal, artikel tersebut akan bertanda "Gagal".
- File `app.py` dan `summarizer.py` adalah versi lama (Streamlit + AI) dan bisa dihapus.

## Troubleshooting

- **Berita tidak ditemukan** — Coba kata kunci yang lebih umum atau perbesar periode pencarian.
- **Konten kosong** — Beberapa situs memblokir scraping. Ini normal.
- **Timeout di Vercel** — Upgrade ke Vercel Pro (60 detik timeout) atau kurangi jumlah berita.
