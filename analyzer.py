"""
Modul analisis berita TANPA AI.
- Rangkuman: ekstraktif (kalimat paling relevan berdasarkan frekuensi kata)
- Sentimen: berbasis kamus kata & pola kontekstual bahasa Indonesia
  Perspektif analisis:
  1. POV Institusi/Perusahaan: apakah berita merugikan atau menguntungkan reputasi
  2. POV Publik/Rakyat: bagaimana masyarakat memandang institusi dari berita ini
"""

import re
import math
from collections import Counter


# ══════════════════════════════════════════════════════════════════════
# Kamus kata sentimen bahasa Indonesia (diperluas & kontekstual)
# ══════════════════════════════════════════════════════════════════════

# --- NEGATIF: merugikan reputasi institusi, membuat publik kecewa/tidak percaya ---
KATA_NEGATIF = {
    # === Hukum, kriminal, pelanggaran ===
    "korupsi", "koruptor", "suap", "menyuap", "penyuapan",
    "penipuan", "penipu", "tipu", "menipu", "ditipu",
    "kriminal", "pidana", "tersangka", "terdakwa", "terpidana",
    "ditangkap", "ditahan", "dipenjara", "penjara", "tahanan",
    "pencucian", "illegal", "ilegal", "melanggar", "pelanggaran",
    "manipulasi", "memanipulasi", "dimanipulasi",
    "pemalsuan", "memalsukan", "palsu", "dipalsukan",
    "bodong", "gelap", "haram", "terlarang",
    "gratifikasi", "skandal", "kongkalikong", "kolusi", "nepotisme",
    "mafia", "kartel", "sindikat", "komplotan",

    # === Kegagalan institusi & pengawasan ===
    "gagal", "kegagalan", "lalai", "kelalaian", "abai", "mengabaikan",
    "lengah", "kelengahan", "luput", "kecolongan", "kebobolan",
    "lemah", "kelemahan", "buruk", "memburuk", "terburuk",
    "bobrok", "amburadul", "berantakan", "kacau", "semrawut",
    "lambat", "terlambat", "lamban", "berlarut",
    "tidak kompeten", "inkompeten", "tidak profesional",
    "tidak transparan", "tertutup", "menutup-nutupi",

    # === Kerugian finansial ===
    "rugi", "kerugian", "merugi", "dirugikan", "merugikan",
    "bangkrut", "kebangkrutan", "pailit", "kepailitan",
    "jatuh", "anjlok", "ambruk", "terjun", "terpuruk",
    "turun", "menurun", "penurunan", "merosot", "kemerosotan",
    "defisit", "resesi", "kontraksi", "stagnan", "stagnasi",
    "macet", "bermasalah", "default", "kolaps", "runtuh",
    "likuidasi", "dilikuidasi", "moratorium",
    "utang", "terlilit", "membengkak",
    "inflasi", "hiperinflasi", "devaluasi", "depresiasi",

    # === Keluhan publik & ketidakpuasan rakyat ===
    "keluhan", "mengeluh", "protes", "memprotes",
    "demo", "demonstrasi", "unjuk rasa", "aksi massa",
    "menolak", "penolakan", "ditolak", "keberatan",
    "kecewa", "mengecewakan", "kekecewaan",
    "marah", "kemarahan", "murka", "geram",
    "korban", "menderita", "penderitaan", "sengsara",
    "dirugikan", "dizalimi", "diperas", "dieksploitasi",
    "tidak adil", "ketidakadilan", "diskriminasi",
    "tidak puas", "ketidakpuasan",
    "kritik", "mengkritik", "dikritik", "kecaman", "mengecam",
    "kontroversi", "kontroversial", "polemik", "perdebatan",
    "gugatan", "menggugat", "digugat", "tuntutan", "menuntut",

    # === Ancaman & dampak buruk bagi publik ===
    "ancaman", "mengancam", "terancam",
    "bahaya", "berbahaya", "membahayakan",
    "darurat", "waspada", "awas",
    "sanksi", "hukuman", "denda", "didenda",
    "blacklist", "diblokir", "dicabut", "pencabutan",
    "pembatalan", "dibatalkan", "dibekukan", "pembekuan",
    "peringatan", "teguran", "ditegur", "somasi",

    # === Fraud & malpraktik ===
    "fraud", "malpraktik", "penyalahgunaan", "menyalahgunakan",
    "penyimpangan", "menyimpang", "penyelewengan", "menyeleweng",
    "sengketa", "perselisihan", "konflik", "perseteruan",
    "restrukturisasi", "kredit macet", "gagal bayar",

    # === Dampak buruk bagi masyarakat ===
    "bencana", "kecelakaan", "kerusakan", "kehancuran",
    "krisis", "masalah", "hambatan", "kendala", "gangguan",
    "gejolak", "volatilitas", "ketidakpastian", "instabilitas",
    "tekanan", "tertekan", "terjepit", "terhimpit",
    "risiko", "berisiko", "rentan", "kerentanan",
    "PHK", "pemutusan", "pengangguran", "dipecat",
    "kemiskinan", "miskin", "melarat",
    "tertunda", "penundaan", "mangkrak", "terbengkalai",
    "melemah", "pelemahan",
    "memburuk", "perburukan", "terparah",
    "pecah", "perpecahan", "cerai",
}

# --- POSITIF: menguntungkan reputasi institusi, membuat publik percaya/puas ---
KATA_POSITIF = {
    # === Pencapaian & keberhasilan institusi ===
    "berhasil", "keberhasilan", "sukses", "kesuksesan",
    "prestasi", "berprestasi", "pencapaian", "tercapai", "mencapai",
    "melampaui", "melebihi", "rekor", "tertinggi",
    "terbaik", "unggul", "keunggulan", "unggulan",
    "juara", "menang", "kemenangan", "memenangkan",
    "penghargaan", "meraih", "diraih",
    "apresiasi", "diapresiasi", "mengapresiasi",
    "pujian", "dipuji", "memuji", "membanggakan",

    # === Pertumbuhan & peningkatan ===
    "naik", "kenaikan", "meningkat", "peningkatan", "melonjak",
    "tumbuh", "pertumbuhan",
    "menguat", "penguatan", "membaik", "perbaikan",
    "pulih", "pemulihan", "bangkit", "kebangkitan",
    "surplus", "laba", "keuntungan", "untung", "profit",
    "menguntungkan", "diuntungkan",
    "ekspansi", "berekspansi", "memperluas", "perluasan",

    # === Inovasi & kemajuan ===
    "inovasi", "inovatif", "berinovasi",
    "terobosan", "transformasi", "bertransformasi",
    "digitalisasi", "modernisasi",
    "canggih", "mutakhir", "terdepan",
    "efisien", "efisiensi", "menghemat", "penghematan",
    "produktif", "produktivitas",
    "optimal", "optimalisasi", "mengoptimalkan",

    # === Perlindungan & pelayanan publik ===
    "melindungi", "perlindungan", "dilindungi",
    "melayani", "pelayanan", "layanan",
    "memudahkan", "kemudahan", "mempermudah",
    "menyejahterakan", "kesejahteraan", "sejahtera",
    "memberdayakan", "pemberdayaan",
    "edukasi", "mengedukasi", "literasi",
    "inklusif", "inklusi", "merangkul",

    # === Kepercayaan & stabilitas ===
    "aman", "keamanan", "mengamankan",
    "stabil", "stabilitas", "menstabilkan",
    "terjaga", "terjamin", "menjamin", "jaminan",
    "kepastian", "pasti", "terpercaya",
    "transparan", "transparansi", "keterbukaan",
    "akuntabel", "akuntabilitas",
    "percaya", "kepercayaan", "dipercaya", "tepercaya",
    "optimis", "optimisme", "keyakinan",

    # === Kerja sama & dukungan ===
    "kolaborasi", "berkolaborasi", "sinergi", "bersinergi",
    "kerja sama", "bekerja sama", "bermitra", "kemitraan",
    "mendukung", "dukungan", "didukung",
    "bantuan", "membantu", "dibantu",
    "kontribusi", "berkontribusi",
    "investasi", "investor", "pendanaan", "pembiayaan",
    "kucuran", "mengucurkan", "menyalurkan", "penyaluran",

    # === Tindakan tegas yang positif dari institusi ===
    "menindak", "menindaklanjuti", "tindakan tegas",
    "memberantas", "pemberantasan",
    "mengawasi", "pengawasan", "memperketat", "pengetatan",
    "menertibkan", "penertiban", "mendisiplinkan",
    "memblokir", "membekukan", "mencegah", "pencegahan",
    "menyelamatkan", "penyelamatan", "mengamankan",

    # === Sentimen umum positif ===
    "bagus", "hebat", "cemerlang", "gemilang",
    "mantap", "solid", "kokoh", "kuat", "tangguh",
    "prospek", "peluang", "potensi",
    "manfaat", "bermanfaat",
    "makmur", "kemakmuran",
    "harmonis", "kondusif", "mendukung",
}

# ══════════════════════════════════════════════════════════════════════
# Pola kontekstual: frasa multi-kata yang menentukan sentimen lebih kuat
# Setiap item: (pola regex, bobot)
# ══════════════════════════════════════════════════════════════════════

# Frasa yang NEGATIF bagi reputasi institusi di mata publik
FRASA_NEGATIF = [
    # Kegagalan pengawasan / kelalaian institusi
    (r"gagal\s+(mengawasi|melindungi|menangani|mencegah|menindak)", 5),
    (r"lalai\s+(dalam|mengawasi|menangani)", 5),
    (r"tidak\s+(mampu|bisa|sanggup)\s+(mengawasi|melindungi|menangani|mencegah)", 5),
    (r"lemah(nya)?\s+(pengawasan|penegakan|penanganan|regulasi)", 5),
    (r"abai\s+(terhadap|dalam|atas)", 4),
    (r"kecolongan|kebobolan", 4),
    # Kerugian publik / nasabah / rakyat
    (r"(nasabah|masyarakat|rakyat|konsumen|investor|publik)\s+(dirugikan|rugi|korban|menderita|kecewa|mengeluh|marah|protes)", 6),
    (r"(merugikan|membahayakan|mengancam|mengorbankan)\s+(nasabah|masyarakat|rakyat|konsumen|investor|publik)", 6),
    (r"kerugian\s+(nasabah|masyarakat|rakyat|konsumen|investor|negara)", 6),
    (r"korban\s+(penipuan|investasi bodong|pinjol|fraud)", 5),
    # Skandal melibatkan institusi
    (r"(dugaan|indikasi|terbukti|terlibat)\s+(korupsi|suap|penipuan|fraud|manipulasi|penyalahgunaan|pelanggaran|skandal)", 5),
    (r"(diduga|terbukti|terindikasi)\s+(korupsi|curang|melanggar|menyalahgunakan)", 5),
    # Tuntutan / gugatan terhadap institusi
    (r"(digugat|dituntut|dilaporkan|disomasi|diadukan)\s", 4),
    (r"(gugatan|tuntutan|laporan|aduan)\s+(terhadap|kepada|ke)\s", 4),
    # Penurunan kepercayaan publik
    (r"(kehilangan|hilang|menurun|turun|merosot)(nya)?\s+(kepercayaan|kredibilitas|integritas)", 6),
    (r"(tidak|kurang|hilang)\s+(percaya|dipercaya|kredibel)", 5),
    (r"(mempertanyakan|meragukan|meragukan)\s+(kinerja|kompetensi|kredibilitas|integritas)", 5),
    # Hukuman / sanksi terhadap institusi
    (r"(dijatuhi|menerima|dikenai|dikenakan)\s+(sanksi|hukuman|denda|teguran|peringatan)", 4),
    # PHK dan pengangguran
    (r"(PHK|pemutusan\s+hubungan\s+kerja|mem-PHK|di-PHK)", 4),
    (r"(ribuan|ratusan|puluhan|banyak)\s+(karyawan|pekerja|buruh)\s+(dipecat|di-PHK|dirumahkan)", 5),
]

# Frasa yang POSITIF bagi reputasi institusi di mata publik
FRASA_POSITIF = [
    # Tindakan tegas institusi yang melindungi publik
    (r"(berhasil|mampu|sukses)\s+\w*\s*(mengawasi|melindungi|menangani|mencegah|menindak|memberantas|menyelamatkan)", 5),
    (r"(menindak\s+tegas|bertindak\s+tegas)", 5),
    (r"(berhasil|sukses)\s+\w*\s*(membongkar|mengungkap|menangkap|memblokir|membekukan|menghentikan)", 5),
    (r"(memblokir|membekukan|mencabut\s+izin)\s+.{0,60}(ilegal|bodong|nakal|bermasalah|melanggar|fraud|penipuan|menipu)", 6),
    (r"(mencabut\s+izin|membekukan|memblokir).{0,40}(perlindungan|melindungi|demi|untuk)", 5),
    (r"pencabutan\s+izin.{0,40}(melindungi|perlindungan|demi|bentuk)", 5),
    # Perlindungan & manfaat bagi publik
    (r"(melindungi|mengamankan|menyelamatkan)\s+.{0,30}(nasabah|masyarakat|rakyat|konsumen|investor|dana|aset)", 6),
    (r"(nasabah|masyarakat|rakyat|konsumen|investor|publik)\s+.{0,20}(dilindungi|terselamatkan|diuntungkan|terbantu)", 6),
    (r"(manfaat|keuntungan|kemudahan)\s+(bagi|untuk|kepada)\s+.{0,20}(nasabah|masyarakat|rakyat|konsumen|publik)", 5),
    (r"(perlindungan|bentuk perlindungan)\s+(terhadap|bagi|untuk|kepada)\s+.{0,20}(nasabah|masyarakat|rakyat|konsumen|publik)", 6),
    (r"(pengawasan|penindakan)\s+(yang\s+)?(ketat|tegas)", 5),
    # Pertumbuhan & pencapaian
    (r"(mencatatkan|membukukan|meraih|mencapai)\s+(pertumbuhan|kenaikan|laba|keuntungan|prestasi|penghargaan|rekor)", 5),
    (r"(tumbuh|naik|meningkat|melonjak)\s+\d+", 4),
    (r"(kinerja|performa)\s+(positif|baik|solid|cemerlang|memuaskan|menggembirakan)", 5),
    # Kepercayaan publik meningkat
    (r"(meningkat|tumbuh|naik|bertambah)(nya|kan)?\s+(kepercayaan|kredibilitas)", 6),
    (r"(dipercaya|terpercaya|kredibel)\s+(oleh|di\s+mata)\s+(publik|masyarakat|rakyat|dunia)", 5),
    # Inovasi & terobosan
    (r"(meluncurkan|memperkenalkan|meresmikan)\s+(layanan|program|fitur|kebijakan|produk)\s+(baru|inovatif|digital)", 4),
    (r"(terobosan|inovasi|transformasi)\s+(baru|digital|teknologi)", 4),
    # Penghargaan
    (r"(meraih|mendapat|menerima|memenangkan)\s+(penghargaan|award|predikat|sertifikasi)", 5),
]

# Kata-kata umum yang tidak bermakna (stopwords) — untuk rangkuman
STOPWORDS = {
    "dan", "atau", "yang", "di", "ke", "dari", "untuk", "dengan",
    "pada", "ini", "itu", "adalah", "akan", "telah", "sudah",
    "bisa", "dapat", "juga", "serta", "oleh", "dalam", "sebagai",
    "tidak", "belum", "bukan", "namun", "tetapi", "tapi", "sedangkan",
    "karena", "sehingga", "agar", "supaya", "jika", "bila", "apabila",
    "bahwa", "maka", "lalu", "kemudian", "selain", "antara", "seperti",
    "secara", "lebih", "sangat", "paling", "hanya", "masih", "ada",
    "tersebut", "mereka", "kita", "kami", "saya", "ia", "dia",
    "hal", "para", "nya", "atas", "bawah", "lain", "setiap", "semua",
    "beberapa", "sejumlah", "berbagai", "melalui", "terhadap", "hingga",
    "sampai", "tentang", "mengenai", "yakni", "yaitu", "maupun",
    "rata", "per", "tahun", "bulan", "hari", "waktu",
    "kata", "ujar", "ucap", "tutur", "ungkap", "jelasnya",
    "menurutnya", "katanya", "tambahnya", "lanjutnya",
}


def _tokenize(text: str) -> list[str]:
    """Pecah teks menjadi kata-kata lowercase."""
    return re.findall(r"[a-zA-Z\u00C0-\u024F]+", text.lower())


def _split_kalimat(text: str) -> list[str]:
    """Pecah teks menjadi kalimat-kalimat."""
    # Split berdasarkan titik, tanda seru, tanda tanya, atau newline
    kalimat_list = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    # Filter kalimat terlalu pendek (< 20 karakter) atau terlalu panjang
    return [k.strip() for k in kalimat_list if len(k.strip()) >= 20]


# ══════════════════════════════════════════════════════════════════════
# Rangkuman Ekstraktif
# ══════════════════════════════════════════════════════════════════════

def rangkum_teks(teks: str, jumlah_kalimat: int = 3) -> str:
    """
    Buat rangkuman ekstraktif dari teks.
    Memilih kalimat paling penting berdasarkan frekuensi kata.

    Args:
        teks: Teks artikel lengkap.
        jumlah_kalimat: Jumlah kalimat dalam rangkuman.

    Returns:
        Rangkuman berupa string.
    """
    if not teks or len(teks.strip()) < 50:
        return ""

    kalimat_list = _split_kalimat(teks)
    if not kalimat_list:
        return ""

    if len(kalimat_list) <= jumlah_kalimat:
        return " ".join(kalimat_list)

    # Hitung frekuensi kata (tanpa stopwords)
    semua_kata = _tokenize(teks)
    kata_bermakna = [k for k in semua_kata if k not in STOPWORDS and len(k) > 2]
    frekuensi = Counter(kata_bermakna)

    # Normalkan frekuensi
    max_freq = max(frekuensi.values()) if frekuensi else 1

    # Skor tiap kalimat
    skor_kalimat = []
    for idx, kalimat in enumerate(kalimat_list):
        kata_dalam_kalimat = _tokenize(kalimat)
        kata_bermakna_kalimat = [k for k in kata_dalam_kalimat if k in frekuensi]

        if not kata_bermakna_kalimat:
            skor = 0.0
        else:
            skor = sum(frekuensi[k] / max_freq for k in kata_bermakna_kalimat)
            # Normalkan berdasarkan panjang kalimat (hindari bias ke kalimat panjang)
            skor /= math.log2(len(kata_dalam_kalimat) + 1)

        # Bonus sedikit untuk kalimat di awal artikel (biasanya lebih penting)
        if idx == 0:
            skor *= 1.3
        elif idx == 1:
            skor *= 1.1

        skor_kalimat.append((idx, skor, kalimat))

    # Pilih kalimat dengan skor tertinggi
    top = sorted(skor_kalimat, key=lambda x: x[1], reverse=True)[:jumlah_kalimat]
    # Urutkan kembali berdasarkan posisi asli agar rangkuman runtut
    top.sort(key=lambda x: x[0])

    return " ".join(k[2] for k in top)


# ══════════════════════════════════════════════════════════════════════
# Analisis Sentimen Kontekstual (POV Institusi + POV Publik)
# ══════════════════════════════════════════════════════════════════════

def _hitung_skor_frasa(teks: str, frasa_list: list) -> float:
    """Hitung skor sentimen dari pola frasa kontekstual."""
    skor = 0.0
    for pola, bobot in frasa_list:
        matches = re.findall(pola, teks, re.IGNORECASE)
        skor += len(matches) * bobot
    return skor


def _cek_negasi(teks: str, kata: str) -> bool:
    """Cek apakah kata didahului oleh kata negasi (tidak, bukan, belum, tanpa)."""
    pola = rf"(tidak|bukan|belum|tanpa|jangan|tak)\s+(?:\w+\s+){{0,2}}{re.escape(kata)}"
    return bool(re.search(pola, teks, re.IGNORECASE))


def analisis_sentimen(teks: str, judul: str = "", keyword: str = "") -> tuple[str, float]:
    """
    Analisis sentimen berbasis kamus kata + pola kontekstual.

    Perspektif analisis:
    1. POV Institusi: berita merugikan/menguntungkan reputasi institusi target
    2. POV Publik: bagaimana masyarakat memandang institusi/tema berita

    Contoh konteks penting:
    - "OJK berhasil menindak perusahaan penipu" → POSITIF (OJK melindungi publik)
    - "OJK gagal mengawasi bank bermasalah" → NEGATIF (OJK lalai)
    - "OJK temukan dugaan korupsi di bank X" → POSITIF (OJK aktif mengawasi)

    Args:
        teks: Teks artikel.
        judul: Judul artikel (diberi bobot lebih tinggi).
        keyword: Kata kunci institusi target.

    Returns:
        Tuple (sentimen: 'POSITIF'|'NEGATIF'|'NETRAL', skor: float -1.0 s/d 1.0).
    """
    if not teks:
        return "NETRAL", 0.0

    teks_lower = teks.lower()
    judul_lower = judul.lower()
    keyword_lower = keyword.lower().strip()

    # ── 1) Skor dari pola frasa kontekstual (paling akurat) ──
    # Frasa dievaluasi pada keseluruhan teks
    teks_full = f"{judul_lower} {teks_lower}"
    skor_frasa_pos = _hitung_skor_frasa(teks_full, FRASA_POSITIF)
    skor_frasa_neg = _hitung_skor_frasa(teks_full, FRASA_NEGATIF)

    # ── 2) Skor dari kata tunggal ──
    # Judul diberi bobot 3x karena paling mencerminkan isi berita
    kata_judul = _tokenize(judul_lower)
    kata_konten = _tokenize(teks_lower)

    skor_kata_pos = 0.0
    skor_kata_neg = 0.0

    # Hitung dari judul (bobot 3x)
    for kata in kata_judul:
        if kata in KATA_POSITIF and not _cek_negasi(judul_lower, kata):
            skor_kata_pos += 3.0
        elif kata in KATA_NEGATIF and not _cek_negasi(judul_lower, kata):
            skor_kata_neg += 3.0

    # Hitung dari konten (bobot 1x)
    for kata in kata_konten:
        if kata in KATA_POSITIF and not _cek_negasi(teks_lower, kata):
            skor_kata_pos += 1.0
        elif kata in KATA_NEGATIF and not _cek_negasi(teks_lower, kata):
            skor_kata_neg += 1.0

    # Negasi membalik sentimen
    for kata in kata_judul + kata_konten:
        bobot = 3.0 if kata in kata_judul else 1.0
        if kata in KATA_POSITIF and _cek_negasi(teks_full, kata):
            skor_kata_pos -= bobot
            skor_kata_neg += bobot * 0.5
        elif kata in KATA_NEGATIF and _cek_negasi(teks_full, kata):
            skor_kata_neg -= bobot
            skor_kata_pos += bobot * 0.5

    skor_kata_pos = max(skor_kata_pos, 0)
    skor_kata_neg = max(skor_kata_neg, 0)

    # ── 3) Konteks institusi target ──
    # Jika keyword disebut bersama aksi positif/negatif, perkuat sinyal
    skor_konteks = 0.0
    if keyword_lower:
        # Cari kalimat-kalimat yang menyebut keyword
        kalimat_list = re.split(r"[.!?\n]+", teks_full)
        for kalimat in kalimat_list:
            if keyword_lower not in kalimat:
                continue
            # Hitung sentimen per kalimat yang menyebut keyword
            kata_kalimat = _tokenize(kalimat)
            pos_k = sum(1 for k in kata_kalimat if k in KATA_POSITIF)
            neg_k = sum(1 for k in kata_kalimat if k in KATA_NEGATIF)
            # Frasa kontekstual dalam kalimat keyword
            pos_k += _hitung_skor_frasa(kalimat, FRASA_POSITIF) * 0.5
            neg_k += _hitung_skor_frasa(kalimat, FRASA_NEGATIF) * 0.5
            skor_konteks += (pos_k - neg_k) * 2.0  # Bobot ekstra

    # ── 4) Gabungkan semua skor ──
    total_pos = skor_frasa_pos + skor_kata_pos + max(skor_konteks, 0)
    total_neg = skor_frasa_neg + skor_kata_neg + abs(min(skor_konteks, 0))

    total = total_pos + total_neg
    if total == 0:
        return "NETRAL", 0.0

    skor = (total_pos - total_neg) / total  # Range: -1.0 sampai 1.0

    # Threshold sentimen
    if skor > 0.08:
        return "POSITIF", round(skor, 2)
    elif skor < -0.08:
        return "NEGATIF", round(skor, 2)
    else:
        return "NETRAL", round(skor, 2)


def analisis_berita(judul: str, konten: str, keyword: str = "") -> dict:
    """
    Analisis lengkap satu berita: rangkuman + sentimen.

    Args:
        judul: Judul berita.
        konten: Isi berita lengkap.
        keyword: Kata kunci pencarian (institusi target).

    Returns:
        Dict dengan keys: rangkuman, sentimen, skor_sentimen
    """
    rangkuman = rangkum_teks(konten, jumlah_kalimat=3)
    sentimen, skor = analisis_sentimen(konten, judul=judul, keyword=keyword)

    return {
        "rangkuman": rangkuman,
        "sentimen": sentimen,
        "skor_sentimen": skor,
    }
