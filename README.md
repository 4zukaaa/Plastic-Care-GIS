# PLASTI-CARE — Pipeline Data & Analisis Hotspot Statistik

Mengubah export mentah KoboToolbox menjadi tiga produk analisis:

| Produk | Pertanyaan yang dijawab | Metode |
|---|---|---|
| Plastic Waste Distribution Map | Di mana saja sampah ditemukan? | sebaran titik |
| Plastic Waste Density Map | Di mana konsentrasinya tinggi? | Weighted KDE |
| **Statistical Hotspot Map** | **Apakah clustering itu signifikan secara statistik?** | **Getis-Ord Gi\*** |

Ketiganya menjawab pertanyaan berbeda. KDE menunjukkan konsentrasi; Gi\* menguji
apakah konsentrasi itu bukan kebetulan.

---

## Struktur

```
plasticare_pipeline/
├── config.py             # SEMUA parameter yang bisa berubah ada di sini
├── schema.py             # pemetaan nama kolom: Kobo → internal → ArcGIS
├── clean.py              # 7 aturan kualitas + normalisasi koordinat
├── hotspot.py            # agregasi grid heksagon + Getis-Ord Gi* + FDR
├── export.py             # tulis CSV / GeoJSON / GPKG / Shapefile
├── run_pipeline.py       # titik masuk tunggal
├── validate_gi_star.py   # verifikasi rumus Gi* terhadap PySAL/esda
├── make_sample_data.py   # data dummy untuk uji coba
├── docs/img/             # gambar acuan untuk README (sumber: literatur)
└── data/
    ├── raw/              # export Kobo, JANGAN diedit manual
    ├── clean/            # output untuk ArcGIS
    └── logs/             # cleaning_log.csv — jejak tiap baris yang dibuang
```

**Aturan arsitektur:** data hanya mengalir ke depan. Perbaikan dilakukan di
`clean.py` atau `config.py`, bukan dengan mengedit file mentah. Setiap angka di
peta akhir bisa diproduksi ulang dari nol dengan satu perintah.

## Cara pakai

```bash
pip install pandas numpy            # minimum
pip install geopandas pyproj        # dianjurkan: Shapefile/GPKG + UTM resmi
pip install esda libpysal           # opsional: verifikasi rumus Gi*

python make_sample_data.py          # data dummy (sekali, untuk latihan)
python run_pipeline.py              # bersihkan + ekspor + Gi*
python run_pipeline.py --sensitivity  # + uji kepekaan parameter
python validate_gi_star.py          # buktikan rumus Gi* benar
```

Opsi lain:

```bash
--obs FILE --effort FILE     # tunjuk file export tertentu
--grid 150 --distance 200    # timpa ukuran grid & ambang jarak
--value-field n_points       # pakai jumlah observasi, bukan bobot
--no-hotspot                 # lewati Gi*
```

Di Google Colab: upload folder ini, `%cd plasticare_pipeline`, lalu
`!python run_pipeline.py`.

---

# TEORI: Getis-Ord Gi\*

## 1. Apa yang diuji

Dikembangkan oleh Arthur Getis dan J. Keith Ord:

> Getis, A., & Ord, J. K. (1992). *The Analysis of Spatial Association by Use of
> Distance Statistics.* Geographical Analysis, 24(3), 189–206.
> [doi:10.1111/j.1538-4632.1992.tb00261.x](https://doi.org/10.1111/j.1538-4632.1992.tb00261.x)

Pertanyaannya bukan "di mana sampah paling banyak", tapi:

> Apakah ada wilayah bernilai tinggi yang **dikelilingi** wilayah bernilai tinggi
> juga, dan apakah pola itu cukup kuat untuk disebut signifikan secara statistik?

| Kategori | Interpretasi |
|---|---|
| Hotspot | nilai tinggi dikelilingi nilai tinggi |
| Coldspot | nilai rendah dikelilingi nilai rendah |
| Not Significant | tidak ada bukti clustering yang cukup |

**Konsekuensi metodologis yang harus dipegang:** satu sel dengan sampah sangat
banyak belum tentu hotspot. Kalau tetangganya bersih, itu outlier terisolasi,
bukan hotspot. Inilah perbedaan mendasar antara peta konsentrasi (KDE) dan
analisis hotspot statistik (Gi\*). Jangan samakan keduanya saat presentasi.

![Perbandingan Getis-Ord Gi* dan Local Moran's I pada grid heksagon](docs/img/gi-star-vs-local-moran.jpg)

*Gi\* (kiri) hanya mengenal tiga keluaran: hotspot, coldspot, tidak signifikan —
sel diklasifikasikan bersama lingkungannya. Local Moran's I (kanan) memecah
lebih jauh dan menandai **outlier spasial**: sel bernilai rendah di tengah
kerumunan tinggi (low-high, biru muda) dan sel bernilai tinggi di tengah
kerumunan rendah (high-low, oranye).*

Perhatikan sel oranye di gambar kanan. Di Gi\* sel itu ikut terserap menjadi
bagian coldspot; padahal untuk PLASTI-CARE sel seperti itu justru menarik — satu
titik pembuangan liar di area yang bersih. **Gi\* tidak dirancang menemukannya.**
Kalau nanti pertanyaan penelitian berkembang ke "di mana anomali pembuangan
liar", metodenya bukan Gi\* melainkan Local Moran's I (`esda.Moran_Local`).
Untuk sekarang pertanyaan kita adalah kawasan terkonsentrasi, jadi Gi\* tepat.

## 2. Rumus

$$
G_i^{*}=
\frac{
\sum_{j=1}^{n}w_{ij}x_j-\bar X\sum_{j=1}^{n}w_{ij}
}{
S\sqrt{\dfrac{n\sum_{j=1}^{n}w_{ij}^{2}-\left(\sum_{j=1}^{n}w_{ij}\right)^{2}}{n-1}}
}
$$

dengan

$$
\bar X=\frac{1}{n}\sum_{j=1}^{n}x_j
\qquad\qquad
S=\sqrt{\frac{\sum_{j=1}^{n}x_j^{2}}{n}-\bar X^{2}}
$$

| Simbol | Pengertian | Di kode |
|---|---|---|
| $G_i^{*}$ | statistik hotspot pada sel ke-$i$ | `gi_z` |
| $x_j$ | nilai variabel pada sel ke-$j$ | `gi_value` |
| $w_{ij}$ | bobot hubungan spasial sel $i$ dan $j$ | `spatial_weights()` |
| $n$ | jumlah seluruh sel | `meta["n_cells"]` |
| $\bar X$ | rata-rata nilai seluruh sel | `xbar` |
| $S$ | standar deviasi populasi seluruh sel | `s` |

Keluaran $G_i^{*}$ **sudah berupa z-score** — tidak perlu distandardisasi lagi.
Implementasinya ada di `hotspot.getis_ord_gi_star()`, ditulis baris per baris
mengikuti rumus di atas supaya bisa diperiksa, bukan memanggil fungsi kotak hitam.

![Nilai Gi* mentah dibandingkan z-score](docs/img/gi-star-value-vs-zscore.jpg)

*Dua peta dari data yang sama. Kiri: nilai Gi mentah (0,005–0,086) — nyaris
seluruh wilayah tampak berwarna, dan pembacanya tidak tahu mana yang berarti.
Kanan: z-score dengan ambang statistik (±1,645 dan ±2,576) — hanya segelintir
wilayah yang lolos uji.*

Ini alasan kenapa yang disimbolkan adalah `gi_z` / `gi_bin`, **bukan** nilai Gi
mentah. Peta kiri terlihat lebih "ramai" dan menggoda untuk dipakai karena
seolah banyak temuan, tapi warnanya hanya mencerminkan besaran, bukan
signifikansi. Kalau lo pakai peta seperti itu di laporan, lo mengklaim jauh
lebih banyak daripada yang didukung data.

Tanda bintang pada Gi\* berarti **sel $i$ ikut dihitung sebagai tetangganya
sendiri**, jadi $w_{ii}=1$. Ini yang membedakannya dari Gi biasa.

## 3. Spatial Weight Matrix ($w_{ij}$)

Komponen paling menentukan hasil. Matriks ini menyatakan seberapa kuat hubungan
dua sel berdasarkan kedekatan spasialnya:

| | A | B | C | D |
|---|---|---|---|---|
| **A** | 1 | 1 | 0 | 0 |
| **B** | 1 | 1 | 1 | 0 |
| **C** | 0 | 1 | 1 | 1 |
| **D** | 0 | 0 | 1 | 1 |

Empat pendekatan membangunnya:

| Skema | Cara kerja | Di `config.py` |
|---|---|---|
| **Fixed Distance Band** | tetangga = dalam radius tertentu, bobot biner 1/0 | `GI_WEIGHT_SCHEME = "fixed"` |
| **Inverse Distance** | $w_{ij}=1/d_{ij}$, makin dekat makin besar pengaruhnya | `"idw"` |
| **Inverse Distance Squared** | $w_{ij}=1/d_{ij}^{2}$, pengaruh turun lebih cepat | `"idw2"` |
| Contiguity | tetangga = sel yang batasnya bersinggungan | setara `"fixed"` dengan ambang = `GRID_SIZE_M` pada grid heksagon |

Pada grid heksagon beraturan, Contiguity dan Fixed Distance Band menyatu: enam
tetangga langsung sebuah heksagon semuanya berjarak tepat `GRID_SIZE_M` dari
pusatnya. Jadi mengatur `GI_DISTANCE_THRESHOLD_M = GRID_SIZE_M` memberi
ketetanggaan ordo-1, dan `1.8 × GRID_SIZE_M` memberi ordo-2.

Matriks ini **tidak dibakukan baris** (row-standardized), sesuai konvensi Gi\*.

## 4. Interpretasi hasil

| Z-score | Tingkat kepercayaan | Interpretasi | `gi_bin` |
|---|---|---|---|
| ≥ 2,58 | 99% | hotspot sangat signifikan | +3 |
| ≥ 1,96 | 95% | hotspot signifikan | +2 |
| ≥ 1,65 | 90% | hotspot signifikan pada 90% | +1 |
| −1,65 … 1,65 | — | tidak signifikan | 0 |
| ≤ −1,65 | 90% | coldspot | −1 |
| ≤ −1,96 | 95% | coldspot signifikan | −2 |
| ≤ −2,58 | 99% | coldspot sangat signifikan | −3 |

![Contoh peta Gi* dengan skema warna dan legenda baku](docs/img/gi-star-legend-standard.jpg)

*Tujuh kelas `gi_bin` yang dihasilkan pipeline, dipetakan dengan konvensi baku:
gradasi merah untuk hotspot (makin gelap makin tinggi kepercayaannya), kuning
pucat untuk tidak signifikan, gradasi biru untuk coldspot. Inilah bentuk akhir
yang kita tuju untuk peta hotspot PLASTI-CARE.*

Tiru struktur legendanya persis: tujuh kelas, tingkat kepercayaan ditulis
eksplisit. Pembaca non-teknis (Dinas, warga) bisa membaca "99% Confidence" tanpa
perlu paham z-score, sementara reviewer teknis tetap bisa menelusurinya ke
kolom `gi_z` dan `gi_p`.

p-value dua arah dihitung tanpa scipy, lewat fungsi error komplementer:

$$
p = \operatorname{erfc}\!\left(\frac{|z|}{\sqrt{2}}\right)
$$

Contoh pembacaan. Sel dengan $Z = 3{,}12$ dan $p = 0{,}0018$: terdapat clustering
nilai tinggi yang signifikan pada tingkat kepercayaan 99%, jadi sel itu
dikategorikan hotspot. **Yang tidak boleh disimpulkan:** bahwa sel itu sumber
pencemaran terbesar. Gi\* menguji pola spasial dari variabel yang kita pilih,
bukan kausalitas.

### Koreksi False Discovery Rate

Menguji 500 sel pada $\alpha = 0{,}05$ menghasilkan sekitar 25 sel "signifikan"
murni karena kebetulan — ini masalah *multiple testing*. Pipeline menerapkan
koreksi Benjamini-Hochberg: p diurutkan naik, lalu dicari $k$ terbesar yang
memenuhi

$$
p_{(k)} \le \frac{k}{n}\alpha
$$

dan $p_{(k)}$ itu menjadi ambang signifikansi yang baru, lebih ketat dari
$\alpha$ mentah. Diatur lewat `GI_FDR_CORRECTION = True`, ambang hasilnya
dicatat di `hotspot_gi_star_metadata.json`.

Pada data dummy, ambang 90% turun dari 0,10 menjadi **0,0017** setelah koreksi —
hampir 60 kali lebih ketat. Tanpa FDR, laporan akan mengklaim hotspot yang tidak
tahan uji.

## 5. Dari titik X,Y menjadi hotspot: empat tahap

Gi\* tidak bisa langsung memakan koordinat. Titik harus diubah dulu menjadi unit
analisis spasial yang punya nilai numerik.

### Tahap 1 — Spatial Aggregation

$$
X_i=\sum_{j=1}^{m}q_j
$$

$X_i$ = total nilai sampah pada sel $i$; $q_j$ = nilai observasi $j$; $m$ =
jumlah observasi dalam sel itu. Fungsi: `hotspot.aggregate_to_grid()`.

Grid heksagon dipilih, bukan fishnet kotak, karena keenam tetangga sebuah
heksagon berjarak sama dari pusatnya — pada kotak, tetangga diagonal 1,41 kali
lebih jauh daripada tetangga sisi, sehingga ketetanggaan jadi tidak isotropik.
Penetapan titik ke sel memakai pembulatan koordinat kubik (axial → cube rounding).

| Grid ID | n observasi | total weight |
|---|---|---|
| H00012 | 12 | 45 |
| H00013 | 8 | 30 |
| H00014 | 2 | 5 |
| H00015 | 15 | 72 |

**Sel bernilai nol WAJIB ikut.** Gi\* membandingkan setiap sel dengan rata-rata
seluruh sel, jadi membuang sel kosong akan menggeser $\bar X$ ke atas dan
menghasilkan hotspot palsu. Tapi ada syaratnya: hanya sel yang **benar-benar
tercakup survei**. Sel yang tidak pernah didatangi siswa bukan "nol sampah", itu
"tidak diketahui" — kalau diikutkan, dia muncul sebagai coldspot palsu. Pipeline
menyaringnya lewat `GI_COVERAGE_BUFFER_M`: sel dipertahankan hanya kalau
pusatnya berada dalam jarak itu dari observasi terdekat.

### Tahap 2 — Spatial Relationship

$$
W=[w_{ij}]
$$

Fungsi: `hotspot.spatial_weights()`.

### Tahap 3 — Getis-Ord Gi\*

Fungsi: `hotspot.getis_ord_gi_star()` → `gi_z`, lalu `p_two_tailed()` → `gi_p`.

### Tahap 4 — Statistical Classification

Fungsi: `hotspot.classify()` → `gi_bin` (−3…+3) dan `gi_class`
("Hotspot 99%", "Coldspot 95%", "Not Significant").

## 6. Data yang dibutuhkan dari KoboToolbox

Koordinat X dan Y saja **cukup untuk menentukan lokasi, tapi belum cukup untuk
Gi\***. Gi\* butuh variabel numerik yang dianalisis.

### Minimum

| Field | Peran |
|---|---|
| `obs_id` | identitas unik observasi |
| `latitude` (Y) | posisi utara-selatan |
| `longitude` (X) | posisi timur-barat |
| `quantity_class` | tingkat kuantitas sampah → sumber $x_j$ |

### Sangat direkomendasikan

| Field | Fungsi | Wajib untuk Gi\*? |
|---|---|---|
| `plastic_type` | analisis komposisi | tidak |
| `site_type` | menjelaskan *mengapa* hotspot terbentuk | tidak |
| `timestamp` | deteksi duplikat, perbandingan waktu | tidak |
| `surveyor_id` | telusur masalah kualitas | tidak |
| `zone_id` | normalisasi effort | tidak |
| `gps_accuracy` | filter koordinat buruk | tidak, tapi menentukan validitas |
| `survey_duration` | normalisasi terhadap cakupan survei | tidak, tapi menentukan tafsir |
| `route_length` | normalisasi per kilometer rute | tidak |

Tidak semuanya masuk rumus Gi\*. Tapi tanpa `gps_accuracy`, `survey_duration` dan
`zone_id`, hasil Gi\* tidak bisa dipertanggungjawabkan — kita tak bisa membedakan
hotspot sampah dari hotspot aktivitas survei.

## 7. Keputusan metodologis: variabel mana yang dianalisis

Dua pendekatan, dan keputusan ini harus eksplisit di laporan.

**A. Number of Plastic Waste** — $X_i$ = jumlah observasi pada sel $i$.
Cocok kalau setiap objek sampah bisa dihitung konsisten.
→ `GI_VALUE_FIELD = "n_points"`

**B. Weighted Plastic Waste** — $X_i=\sum_j w_j$ dengan bobot per kelas kuantitas.
Cocok kalau kita ingin membedakan sedikit sampah dari tumpukan besar.
→ `GI_VALUE_FIELD = "total_weight"` *(default)*

Pemetaan bobot di `config.QUANTITY_WEIGHT`:

| quantity_class | deskripsi lapangan | bobot |
|---|---|---|
| 1 | segenggam | 1 |
| 2 | ±1 kantong | 3 |
| 3 | tumpukan < 1 m² | 8 |
| 4 | tumpukan > 1 m² | 20 |

**Bobot ini belum terkalibrasi.** Angka 1/3/8/20 adalah asumsi non-linear yang
masuk akal, bukan hasil pengukuran. Supaya bisa dipertahankan, pipeline
menjalankan **kedua** pendekatan dan melaporkan kesepakatannya lewat indeks
Jaccard pada himpunan sel hotspot (`hotspot_value_field_comparison.csv`).

Pada data dummy, Jaccard = **0,43** — artinya pilihan bobot **mengubah hampir
separuh kesimpulan**. Dua konsekuensi langsung:

1. Laporkan kedua peta, jangan hanya yang mendukung narasi.
2. Kalibrasi bobot di lapangan: timbang 10–20 tumpukan per kelas kuantitas,
   ambil mediannya, masukkan ke `QUANTITY_WEIGHT`. Setelah itu bobotnya punya
   dasar pengukuran dan pendekatan B bisa dipakai sebagai hasil utama.

Sampai kalibrasi itu ada, pakai `n_points` sebagai baseline dan `total_weight`
sebagai skenario pembanding.

## 8. Parameter awal

| Parameter | Nilai awal | Di `config.py` |
|---|---|---|
| Input CRS | EPSG:4326 | `CRS_GEOGRAPHIC` |
| Projected CRS | EPSG:32748 (UTM 48S) | `CRS_PROJECTED` |
| Grid type | Hexagon | `GRID_TYPE` |
| Grid size | 100 m | `GRID_SIZE_M` |
| Spatial relationship | Fixed Distance Band | `GI_WEIGHT_SCHEME` |
| Distance threshold | 150 m | `GI_DISTANCE_THRESHOLD_M` |
| Input field | total_weight | `GI_VALUE_FIELD` |
| Confidence level | 90%, 95%, 99% | `GI_ALPHA_LEVELS` |
| FDR correction | aktif | `GI_FDR_CORRECTION` |
| Coverage buffer | 150 m | `GI_COVERAGE_BUFFER_M` |

Semua angka ini **parameter eksperimen, bukan standar universal.**

## 9. Uji sensitivitas — ini yang membuat hasil bisa dipertanggungjawabkan

```bash
python run_pipeline.py --sensitivity
```

Output pada data dummy (121 titik):

| grid (m) | ambang (m) | n sel | rata-rata tetangga | hotspot | % signifikan | sel terisolasi |
|---|---|---|---|---|---|---|
| 50 | 150 | 1978 | 26,7 | 40 | 2,0 | 0 |
| **100** | **150** | **498** | **5,7** | **16** | **3,2** | **0** |
| 150 | 200 | 220 | 5,2 | 9 | 4,1 | 0 |
| 200 | 200 | 125 | 2,2 | 3 | 2,4 | **23** |

Cara membacanya:

- **Jumlah hotspot absolut tidak stabil** (3 sampai 54 sel) — jangan laporkan
  "ada 16 hotspot" sebagai temuan. Itu artefak ukuran grid.
- **Proporsi sel signifikan stabil** di 1–4% di semua konfigurasi. Ini yang
  layak dilaporkan: polanya konsisten, bukan angkanya.
- **Yang benar-benar temuan** adalah *lokasi* sel yang tetap hotspot di berbagai
  konfigurasi. Itu hotspot yang kokoh.
- Kolom `sel terisolasi` adalah lampu merah: pada grid 200 m, 23 sel tidak punya
  tetangga sama sekali, sehingga Gi\*-nya tidak bermakna. Aturannya
  `GI_DISTANCE_THRESHOLD_M` harus **lebih besar** dari `GRID_SIZE_M`.

Lampirkan tabel ini di laporan. Kalau reviewer bertanya "kenapa grid 100 meter?",
jawabannya bukan selera, tapi tabel ini.

## 10. Verifikasi implementasi

Rumus Gi\* ditulis sendiri dengan numpy, bukan memanggil PySAL — supaya tiap
komponennya terlihat dan jalan di Colab tanpa dependensi berat. Risikonya jelas:
bagaimana membuktikan rumusnya benar?

```bash
pip install esda libpysal && python validate_gi_star.py
```

Skrip ini membandingkan z-score pipeline dengan
`esda.G_Local(star=True, transform="B")` — referensi standar dalam literatur —
pada tiga ambang jarak. Hasil pada data dummy:

```
ambang  100 m | selisih maks |z| = 1.78e-15 | COCOK
ambang  150 m | selisih maks |z| = 1.78e-15 | COCOK
ambang  200 m | selisih maks |z| = 1.78e-15 | COCOK
```

Selisih 10⁻¹⁵ adalah batas presisi floating-point, bukan perbedaan metode.
Sertakan output ini di lampiran metodologi.

## 11. Library yang relevan

| Library | Fungsi | Dipakai pipeline? |
|---|---|---|
| pandas | pengolahan tabel | wajib |
| numpy | operasi matriks bobot | wajib |
| [GeoPandas](https://geopandas.org/) | data spasial, tulis GPKG/SHP | dianjurkan |
| pyproj | reproyeksi UTM resmi | dianjurkan |
| Shapely | geometri heksagon | ikut geopandas |
| [PySAL](https://pysal.org/) / libpysal | matriks bobot spasial | opsional (verifikasi) |
| [esda](https://pysal.org/esda/) | Gi\* referensi | opsional (verifikasi) |

Tanpa geopandas dan pyproj pipeline tetap jalan: koordinat diproyeksikan dengan
aproksimasi equirectangular lokal (galat <0,1% untuk area beberapa km) dan output
berupa CSV + GeoJSON. Cukup untuk latihan di tablet, **tapi untuk laporan akhir
pasang pyproj** supaya proyeksi UTM-nya resmi.

---

# ALUR KERJA

## Langkah pertama yang WAJIB: sesuaikan `schema.py`

Nama kolom export Kobo tergantung desain form. Buka satu file export asli, lihat
nama kolomnya, lalu tambahkan ke `KOBO_TO_INTERNAL`. Kalau ada kolom wajib yang
belum terpetakan, pipeline berhenti dengan pesan yang menyebut kolom apa yang
kurang — bukan error misterius 50 baris kemudian.

Kolom wajib: `obs_id`, `lat`, `lon`, `quantity_class`.

Tiga lapis nama kolom (Kobo → internal → ArcGIS) ada karena Shapefile hanya
menerima **maksimal 10 karakter** per nama kolom. Lebih dari itu dipotong
otomatis menjadi `plastic_ty`, `plastic__1`, dan seterusnya.

## 7 aturan kualitas (`clean.py`)

| Kode | Aturan | Tindakan |
|---|---|---|
| — | format DMS (`6°21'18" S`) | dikonversi ke desimal |
| — | lat/lon tertukar | ditukar balik otomatis |
| R1 | koordinat kosong | dibuang |
| R2 | di luar bounding box Indonesia | dibuang |
| R3 | akurasi GPS > 20 m | dibuang |
| R4 | di luar area studi | dibuang |
| R5 | `quantity_class` bukan 1–4 | dibuang |
| R6 | `site_type` tidak ada di daftar | diubah ke `other` |
| R7 | duplikat (≤5 m dan ≤5 menit) | salah satu dibuang |

Semua tindakan tercatat di `data/logs/cleaning_log.csv` beserta alasannya. Ini
yang membuat lo bisa menjawab "kok datanya 121, siswa kan mengumpulkan 127?"

## Output

| File | Untuk apa |
|---|---|
| `plasticare_points.csv` | ArcGIS Pro: **XY Table To Point** |
| `plasticare_points.geojson` | drag & drop ke ArcGIS Pro / ArcGIS Online |
| `plasticare.gpkg` | GeoPackage: layer `points` + layer `hotspot_gi_star` |
| `shapefile/plasticare_points_utm48s.shp` | titik, sudah direproyeksi UTM 48S |
| **`hotspot_gi_star.csv`** | hasil Gi\* per sel: `gi_z`, `gi_p`, `gi_bin`, `gi_class` |
| **`hotspot_gi_star.geojson`** | poligon heksagon siap disimbolkan |
| **`hotspot_gi_star_metadata.json`** | parameter yang dipakai + ambang FDR |
| `hotspot_value_field_comparison.csv` | pendekatan A vs B + Jaccard |
| `hotspot_sensitivity.csv` | tabel uji sensitivitas |
| `zone_effort_normalized.csv` | sampah per jam survei per zona |
| `composition_site_x_plastic.csv` | jenis plastik × tipe lokasi |

**Kolom `weight`** pada file titik adalah *Population Field* untuk Kernel Density.
**Kolom `gi_bin`** pada file heksagon adalah yang disimbolkan untuk peta hotspot.

## Langkah di ArcGIS Pro

### A. Peta sebaran titik

*Geoprocessing* → `XY Table To Point`. Input `plasticare_points.csv`,
X Field = `lon`, Y Field = `lat`, Coordinate System = **WGS 1984 (EPSG:4326)**.
Jalur cepat: drag `plasticare_points.geojson` ke peta.

### B. Peta kerapatan (Weighted KDE)

1. `Project` → Output Coordinate System = **WGS 1984 UTM Zone 48S (EPSG:32748)**.
   Tanpa ini, radius KDE dihitung dalam derajat dan hasilnya salah. Lewati kalau
   memakai shapefile UTM yang sudah jadi.
2. `Spatial Analyst` → `Kernel Density`. Input = layer hasil proyeksi.
   **Population field = `weight`**. Output cell size = 10 m.
   Search radius = 50–100 m. Area units = Square Kilometers.

### C. Peta hotspot statistik (Gi\*) — hasil pipeline

Pipeline sudah menghitung Gi\* lengkap dengan FDR, jadi di ArcGIS tinggal
menyimbolkan:

1. Tambahkan layer `hotspot_gi_star` dari `plasticare.gpkg`, atau drag
   `hotspot_gi_star.geojson`.
2. *Symbology* → **Unique Values** pada field `gi_bin`, dengan skema baku:

   | gi_bin | warna | label |
   |---|---|---|
   | +3 | merah tua | Hotspot 99% |
   | +2 | merah | Hotspot 95% |
   | +1 | merah muda | Hotspot 90% |
   | 0 | abu-abu / transparan | Not Significant |
   | −1 | biru muda | Coldspot 90% |
   | −2 | biru | Coldspot 95% |
   | −3 | biru tua | Coldspot 99% |

3. Di legenda, tulis parameternya: ukuran grid, ambang jarak, variabel input,
   dan status koreksi FDR. Ambil dari `hotspot_gi_star_metadata.json`.

**Jangan mengarang skema warna sendiri.** Contoh kesalahan yang nyata terjadi di
publikasi:

![Peta Gi* dengan skema warna yang menyesatkan](docs/img/gi-star-legend-pitfall.jpg)

*Di peta ini merah berarti **coldspot** 99% dan hijau berarti **hotspot** 99% —
kebalikan dari konvensi. Pembaca yang melirik sekilas akan menyimpulkan persis
berlawanan dengan isi datanya.*

Merah dipahami universal sebagai "tinggi/panas/bahaya" dan biru sebagai
"rendah/dingin". Melawan konvensi itu tidak membuat peta lebih orisinal, cuma
membuatnya salah dibaca. Dua aturan dari contoh ini: **merah selalu hotspot,
biru selalu coldspot**, dan hindari merah–hijau berdampingan karena sekitar 8%
laki-laki mengalami buta warna merah-hijau. Peta ini juga menunjukkan Gi\* bisa
disimbolkan sebagai titik, bukan hanya poligon — relevan kalau nanti lo mau
menampilkan hasil per titik observasi, bukan per heksagon.

### D. Verifikasi silang dengan ArcGIS (dianjurkan)

Jalankan `Hot Spot Analysis (Getis-Ord Gi*)` ArcGIS pada layer heksagon yang
sama: Input Field = `gi_value`, Conceptualization = `FIXED_DISTANCE_BAND`,
Distance Band = nilai `GI_DISTANCE_THRESHOLD_M`, Apply False Discovery Rate
Correction = dicentang. Hasilnya harus cocok dengan kolom `gi_z` pipeline. Dua
alat independen yang sepakat adalah bukti metodologis terkuat yang bisa lo bawa
ke sidang atau rapat Dinas.

### E. Normalisasi effort (peta versi jujur)

`Generate Tessellation` (hexagon, 100 m) → `Summarize Within` dengan titik
sampah → join `zone_effort_normalized.csv` → hitung field `weight / survey_hours`.
Simbolkan kolom itu, bukan jumlah mentah.

---

## Tiga peringatan untuk presentasi

**1. Hotspot ≠ titik paling banyak sampah.** Hotspot adalah clustering nilai
tinggi yang signifikan secara statistik. Satu tumpukan besar yang dikelilingi
area bersih bukan hotspot.

**2. Heatmap mentah sebagian menggambarkan ke mana siswa berjalan.** Dari data
dummy: zona `RW01` punya titik terbanyak (30), tapi setelah dibagi jam survei,
`RIVER_1` dan `SCHOOL_A` dua kali lebih padat. Selalu tampilkan kedua peta
berdampingan.

**3. Jumlah hotspot bergantung pada ukuran grid.** Yang layak diklaim adalah
lokasi yang konsisten muncul sebagai hotspot di berbagai konfigurasi parameter,
bukan jumlah selnya.

---

## Catatan sumber gambar

Empat gambar di `docs/img/` adalah materi acuan dari literatur dan bahan ajar
pihak lain, dipakai di sini sebatas alat bantu penjelasan internal tim:

| Berkas | Isi | Status |
|---|---|---|
| `gi-star-vs-local-moran.jpg` | Gi\* vs Local Moran's I pada grid heksagon | materi acuan |
| `gi-star-value-vs-zscore.jpg` | nilai Gi mentah vs z-score | materi acuan |
| `gi-star-legend-standard.jpg` | contoh peta Gi\* tingkat distrik, legenda baku | materi acuan |
| `gi-star-legend-pitfall.jpg` | contoh skema warna yang menyesatkan | materi acuan |

**Sebelum masuk laporan, skripsi, atau publikasi:** lacak sumber asli tiap
gambar dan cantumkan sitasi lengkapnya, atau ganti dengan gambar hasil peta
PLASTI-CARE sendiri. Begitu pipeline berjalan di data asli, ketiga gambar
pertama sebetulnya bisa direproduksi dari data lo sendiri — dan itu jauh lebih
kuat daripada meminjam ilustrasi orang lain.
