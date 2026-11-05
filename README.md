# PLASTI-CARE — Pipeline Pembersihan Data (Kobo → ArcGIS)

Mengubah export mentah KoboToolbox menjadi dataset titik yang siap dipakai
untuk Kernel Density (heatmap) di ArcGIS Pro.

## Struktur

```
plasticare_pipeline/
├── config.py            # SEMUA angka & aturan yang bisa berubah ada di sini
├── schema.py            # pemetaan nama kolom: Kobo → internal → ArcGIS
├── clean.py             # 7 aturan kualitas + normalisasi koordinat
├── export.py            # tulis CSV / GeoJSON / GPKG / Shapefile
├── run_pipeline.py      # titik masuk tunggal
├── make_sample_data.py  # data dummy untuk uji coba sebelum data siswa masuk
└── data/
    ├── raw/             # export Kobo, JANGAN diedit manual
    ├── clean/           # output untuk ArcGIS
    └── logs/            # cleaning_log.csv — jejak tiap baris yang dibuang
```

**Aturan arsitektur:** data hanya mengalir ke depan. Perbaikan dilakukan di
`clean.py` atau `config.py`, bukan dengan mengedit file mentah. Dengan begitu
setiap angka di peta akhir bisa diproduksi ulang dari nol.

## Cara pakai

```bash
pip install pandas                 # minimum
pip install geopandas              # opsional, untuk output Shapefile/GPKG

python make_sample_data.py         # bikin data dummy (sekali, untuk latihan)
python run_pipeline.py             # ambil file terbaru di data/raw/

# atau tunjuk file spesifik:
python run_pipeline.py --obs data/raw/observations_20261110.csv \
                       --effort data/raw/effort_20261110.csv
```

Di Google Colab: upload folder ini, `%cd plasticare_pipeline`, lalu
`!python run_pipeline.py`.

## Langkah pertama yang WAJIB: sesuaikan `schema.py`

Nama kolom export Kobo tergantung desain form. Buka satu file export asli,
lihat nama kolomnya, lalu tambahkan ke `KOBO_TO_INTERNAL`. Kalau ada kolom
wajib yang belum terpetakan, pipeline berhenti dengan pesan jelas yang
menyebut kolom apa yang kurang — bukan error misterius.

Kolom wajib: `obs_id`, `lat`, `lon`, `quantity_class`.

## 7 aturan kualitas (`clean.py`)

| Kode | Aturan | Tindakan |
|---|---|---|
| — | Format DMS (`6°21'18" S`) | dikonversi ke desimal |
| — | lat/lon tertukar | ditukar balik otomatis |
| R1 | koordinat kosong | dibuang |
| R2 | di luar bounding box Indonesia | dibuang |
| R3 | akurasi GPS > 20 m | dibuang |
| R4 | di luar area studi | dibuang |
| R5 | `quantity_class` bukan 1–4 | dibuang |
| R6 | `site_type` tidak ada di daftar | diubah ke `other` |
| R7 | duplikat (≤5 m dan ≤5 menit) | salah satu dibuang |

Semua tindakan tercatat di `data/logs/cleaning_log.csv` beserta alasannya.

## Output

| File | Untuk apa |
|---|---|
| `plasticare_points.csv` | ArcGIS Pro: **XY Table To Point** |
| `plasticare_points.geojson` | drag & drop ke ArcGIS Pro / ArcGIS Online |
| `plasticare.gpkg` | GeoPackage, nama kolom panjang aman |
| `shapefile/plasticare_points_utm48s.shp` | sudah direproyeksi ke UTM 48S |
| `zone_effort_normalized.csv` | sampah per jam survei per zona |
| `composition_site_x_plastic.csv` | jenis plastik × tipe lokasi |

**Kolom `weight`** adalah kuncinya: `quantity_class` 1/2/3/4 dipetakan ke bobot
1/3/8/20. Pakai kolom ini sebagai *Population Field* di Kernel Density, supaya
satu tumpukan besar tidak dihitung sama dengan satu bungkus.

## Langkah di ArcGIS Pro

1. **Masukkan data**
   Jalur CSV: *Geoprocessing* → `XY Table To Point`. Input `plasticare_points.csv`,
   X Field = `lon`, Y Field = `lat`, Coordinate System = **WGS 1984 (EPSG:4326)**.
   Jalur cepat: drag `plasticare_points.geojson` langsung ke peta.

2. **Reproyeksi ke meter** (lewati kalau pakai shapefile UTM yang sudah jadi)
   `Project` → Output Coordinate System = **WGS 1984 UTM Zone 48S (EPSG:32748)**.
   Tanpa ini, radius Kernel Density dihitung dalam derajat dan hasilnya salah.

3. **Heatmap**
   `Spatial Analyst` → `Kernel Density`.
   Input = layer hasil proyeksi. **Population field = `weight`**.
   Output cell size = 10 m. Search radius = 50–100 m. Area units = Square Kilometers.

4. **Peta versi jujur (normalisasi effort)**
   `Generate Tessellation` (bentuk hexagon, 100 m) → `Summarize Within` dengan
   titik sampah (jumlahkan `weight`) → join `zone_effort_normalized.csv` →
   hitung field `weight / survey_hours`. Simbolkan kolom itu, bukan jumlah mentah.

5. **Hotspot statistik** (opsional, kalau titik sudah banyak)
   `Optimized Hot Spot Analysis` pada hasil tessellation, Analysis Field =
   bobot ternormalisasi.

## Peringatan yang harus diingat saat presentasi

Heatmap mentah sebagian menggambarkan **ke mana siswa berjalan**, bukan hanya
di mana sampah menumpuk. Dari data dummy: zona `RW01` punya titik terbanyak
(30 titik), tapi setelah dibagi jam survei, `RIVER_1` dan `SCHOOL_A` justru dua
kali lebih padat. Selalu tampilkan kedua peta berdampingan.
