# Program Ticketing — Simulasi Distribusi Beban Teknisi

Implementasi program dari logika & kriteria di file Excel
**`Simulasi_Workload_Ticketing_revisi.xlsx`** (Capstone Project — Tugas 1).
Program ini mereplikasi tiga skenario aturan distribusi beban kerja teknisi
(S1/S2/S3) **persis sama** dengan Excel — terbukti oleh 42 titik validasi
otomatis — sekaligus menambahkan **S4 Redistribution** yang di Excel ditandai
"belum diimplementasikan".

## Apa yang direplikasi dari Excel

| Sheet Excel | Padanan di program |
|---|---|
| `Parameter` | `ticketing/models.py` → `Parameters` (bobot prioritas, Shift Start, busy penalty 1.000.000) |
| `Teknisi` | `ticketing/models.py` → `Technician` |
| `Input_Tiket` | `ticketing/models.py` → `Ticket` + dataset `data/tickets.json` |
| `Sim_S1/S2/S3` | `ticketing/engine.py` + `ticketing/scenarios.py` (kolom A–AH) |
| `Ringkasan` | `ticketing/metrics.py` → `compute_loads()` |
| `Skenario` | `ticketing/metrics.py` → `compute_indicators()` (Gap, Jain's, StdDev, waiting) |
| `Catatan_Revisi` | Setiap catatan diterapkan (lihat tabel di bawah) |

### Logika inti (formula sheet `Sim_*`)

Untuk setiap tiket (urut Timestamp), tiap teknisi dihitung **skor**:

```
Available (free_at <= arrival) : S1 → 0 | S2 → Σ menit | S3 → Σ (menit × bobot)
Busy      (free_at >  arrival) : skor = 1.000.000 + sisa menit   (busy penalty)
```

Pilih skor minimum, **tie-breaker Technician ID terkecil**; Start = MAX(arrival,
free_at); Fallback jika semua Busy = **Earliest Estimated Finish**.

### Catatan_Revisi yang diterapkan

| # | Catatan | Implementasi |
|---|---|---|
| 1 | S1 hanya menilai teknisi Available (beban aktif selalu 0 → praktis pilih ID) | `ScoreFunction.active_workload` mengembalikan 0 — S1 sengaja dipertahankan sebagai bukti bias |
| 2 | Start = MAX(waktu masuk, waktu teknisi bebas) | `engine.py`: `start = max(arrival, free_at[chosen])` |
| 3 | Sheet harus berbasis formula, bukan nilai statis | Program recompute penuh dari dataset JSON |
| 4 | Priority Weight harus terhubung ke Parameter | `Ticket.__post_init__` lookup via `Parameters.priority_weights` |
| 5 | S2 & S3 harus dihitung penuh | Semua indikator dihitung di `metrics.py` |
| 6 | Detail Case terpisah dari Category | Field `Ticket.detail` vs `Ticket.category` |
| 7 | Tiket internal (Technician Request) | Field `related_id`, `requested_by`; prefix `TK-`; kasus unik memakai `is_root_case` |
| 8 | ID digenerate otomatis (counter per prefix) | `TicketIdGenerator` — mencegah bentrok input bersamaan |
| 9 | S4 butuh definisi tiket Queued | `run_s4()` — lihat "Skenario S4" di bawah |
| 10 | Belum dimodelkan: kompetensi, jam kerja, durasi acak | Di luar cakupan (sesuai catatan Excel) |

## Cara menjalankan

```bash
pip install -r requirements.txt

# CLI — semua skenario + indikator
python -m ticketing run --scenario all

# Detail assignment per tiket untuk satu skenario
python -m ticketing run --scenario S2 --detail

# Validasi otomatis terhadap file Excel asli
python -m ticketing compare-excel "path/Simulasi_Workload_Ticketing_revisi.xlsx"

# Web app (buka http://127.0.0.1:5000)
python -m ticketing.web

# Kelola tiket
python -m ticketing tickets list
python -m ticketing tickets add --type user --category Network --priority High \
    --duration 45 --detail "WiFi mati" --time "2026-09-23 14:00"

# Format output lain
python -m ticketing run --format json
python -m ticketing run --format xlsx --out hasil.xlsx
```

## Deploy online (biar kelompok & dosen bisa coba)

Ada **dua bagian** yang bisa dideploy terpisah — keduanya gratis:

| Bagian | Isi | Host | Waktu deploy |
|---|---|---|---|
| **Mockup multi-role** | 62 halaman statis di `mockup/` (login, dashboard pelapor/teknisi/admin, simulasi, detail tiket) | Netlify / GitHub Pages / Vercel | ~2 menit, tanpa konfigurasi |
| **Web app Flask** | Server asli: simulasi + form tambah tiket + API | Render / Railway / Fly.io | ~5 menit, lewat `wsgi.py` |

### A. Tunnel lokal — cara tercepat untuk demo (rekomendasi)

Tunnel mengekspos server Flask di komputermu ke internet **tanpa meng-upload
apa pun**, jadi yang online selalu memakai data lokal terbaru. Mulai server,
lalu tunnel:

```bash
# Terminal 1 — server Flask
python -m ticketing.web --host 127.0.0.1 --port 5000

# Terminal 2 — tunnel (pilih satu)
npx cloudflared@latest tunnel --url http://localhost:5000     # ← rekomendasi
```

Cloudflare mencetak URL publik di output, mis.
`https://xxx-yyy-zzz.trycloudflare.com`. Buka `/mockup/login.html` di URL itu
untuk masuk ke mockup multi-role.

**Kenapa Cloudflare, bukan ngrok:** ngrok free tier (pernah) menunjukkan
sertifikat kedaluwarsa di edge-nya (diverifikasi langsung: `google.com` &
`cloudflare.com` valid, `ngrok.com` gagal — masalah sisi provider, bukan
aplikasi), memunculkan halaman peringatan "Visit Site" tiap domain baru, dan
sering kena rate limit setelah banyak request. Cloudflare Tunnel memakai QUIC,
tidak ada halaman peringatan, dan auto-reconnect setelah jaringan restart.

Akun demo login cepat: `admin`, `t01`, `pelapor`.

**Batasan:** URL acak dan sementara — berubah tiap tunnel baru dan berhenti
saat Terminal 2 ditutup.

### B. Mockup statis permanen (hosting gratis, URL tetap)

Mockup murni statis: semua path relatif, tidak ada panggilan server, jadi tidak
butuh build step apa pun. Cocok kalau butuh URL yang **tidak berubah** untuk
dosen.

**Opsi 1 — drag & drop, tanpa GitHub ( tercepat ):**

1. Buka <https://app.netlify.com/drop>
2. Drag **folder `mockup/`** (bukan folder proyek) ke kotak ungu
3. Selesai — URL online langsung dapat, mis.
   `https://ticketing-mockup.netlify.app`

**Opsi 2 — lewat GitHub (auto re-deploy tiap push):**

1. Push proyek ke GitHub (`.gitignore` sudah ada)
2. Netlify: *Add new site → Import an existing project → pilih repo*
3. Isi: **Build command** kosong, **Publish directory** = `mockup`
4. Deploy site — konfigurasi di `netlify.toml` sudah ada

Buka URL → langsung mendarat di `login.html` (lewat `index.html` yang
mengalihkan).

### C. Web app Flask permanen (server asli, fitur lengkap)

File pendukung sudah disiapkan:

- `wsgi.py` — entry point WSGI, port dari env `PORT`
- `requirements.txt` — sudah termasuk `gunicorn`
- `render.yaml` — blueprint Render untuk deploy satu klik

**Langkah (Render, gratis):**

1. Push proyek ke GitHub
2. Render: *New → Blueprint* → pilih repo (baca `render.yaml` otomatis)
3. Tunggu build (~1 menit), dapat URL `https://ticketing-sim.onrender.com`

atau manual di PaaS mana pun yang mendukung Python:

```bash
pip install -r requirements.txt
gunicorn wsgi:app --workers 2 --threads 4 --timeout 60
```

**Catatan free tier:** web service Render *tidak bisa diakses sementara* setelah
15 menit tanpa request, butuh ~30-50 detik untuk "bangun" kembali. Kalau perlu
selalu aktif untuk presentasi dosen, gunakan starter tier ($7/bln) atau bangunkan
manual sebelum demo.

### Perbandingan data: online == lokal

Mockup & web app mengambil angka dari sumber yang sama (mesin simulasi +
`data/tickets.json`), sehingga angka di online **identik** dengan lokal. Jangan
edit file hasil mockup langsung — jalankan ulang generator:

```bash
python mockup/build_mockup.py     # re-generate 62 halaman dari mesin
```

## Hasil untuk dataset 22 tiket (sama persis dengan Excel)

| Skenario | Aturan | Max | Min | Gap | Jain's | Gap Berbobot |
|---|---|---|---|---|---|---|
| S1 Baseline | Lowest Active Workload | 4:05 | 2:05 | **120 mnt** | 0,9250 | 350 |
| S2 Cumulative | Lowest Cumulative Workload | 3:25 | 3:00 | **25 mnt** | 0,9975 | 190 |
| S3 Priority-aware | Lowest Cumulative Weighted | 3:45 | 2:55 | **50 mnt** | 0,9894 | **100** |
| S4 Redistribution | Highest → Lowest *(usulan)* | 3:30 | 3:00 | **30 mnt** | 0,9958 | 200 |

- Skenario Gap menit terkecil: **S2** (penurunan 79,2% vs S1 — sesuai sheet Skenario)
- Skenario Gap berbobot terkecil: **S3** (penurunan 71,4% vs S1)

### Skenario S4 (Redistribution: Highest → Lowest)

Di Excel, S4 ditandai **"BELUM diimplementasikan"** karena belum ada definisi
tiket *queued*. Di program ini S4 diimplementasikan sebagai **usulan**:

1. Tiket yang tiba saat **semua teknisi Busy** berstatus `Queued` — tidak
   langsung diberikan ke earliest-finish.
2. Saat sebuah teknisi bebas, tiket `Queued` dengan prioritas tertinggi
   diserahkan kepada teknisi bebas dengan **beban kumulatif terendah**
   (inti "Highest → Lowest": beban yang menumpuk di teknisi sibuk dialihkan ke
   teknisi paling ringan).

Hasil: Gap turun dari 120 (S1) menjadi 30 menit. **Catatan: ini usulan yang
perlu validasi dosen**, sama seperti indikator pemerataan dan bobot prioritas.

## Struktur proyek

```
ticketing/
├── models.py        Ticket, Technician, Parameters, Assignment
├── engine.py        Mesin assignment (replikasi formula Sim_*)
├── scenarios.py     S1/S2/S3 + S4 (event-driven)
├── metrics.py       Indikator pemerataan (Gap, Jain's, StdDev, waiting)
├── seed.py          Load/save dataset, generator ID otomatis
├── simulation.py    Fasad: load → run → indikator
├── report.py        Tabel teks + ekspor CSV/XLSX
├── cli.py           `python -m ticketing`
└── web/             Flask app + chart SVG
data/tickets.json    Dataset (4 teknisi + 22 tiket + parameter)
tests/               81 test — validasi terhadap Excel
```

## Validasi

```bash
python -m pytest tests/ -q          # 81 test
python -m ticketing compare-excel   # 42 titik cek vs Excel (toleransi 1e-6)
```

Test mencakup: baris-per-baris sheet `Sim_S1/S2/S3` (teknisi, status, start,
finish, waiting, skor per teknisi, beban kumulatif, Free At), indikator sheet
`Skenario`, agregat sheet `Ringkasan`, generator ID, CLI, dan struktur chart.

## Asumsi & batasan

Sesuai `Catatan_Revisi` #9 dan #10 di Excel, hal-hal berikut **belum
dimodelkan** dan masuk pengembangan tahap berikutnya:

- Kompetensi teknisi per kategori
- Jam kerja / istirahat (Shift Start sekarang asumsi 08:00)
- Durasi acak / ketidakpastian
- Initial Status teknisi (sheet `Teknisi` kolom C) belum dipakai
- Data hanya 1 hari (22 tiket) — hasil belum bisa digeneralisasi
- Bobot prioritas Low=1 / Medium=2 / High=3 **masih asumsi**, butuh validasi dosen
