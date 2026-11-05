"""
Konfigurasi tunggal untuk pipeline PLASTI-CARE.
Semua angka/aturan yang mungkin berubah ada di SINI, bukan tersebar di kode.
Ubah file ini saja kalau area studi, zona UTM, atau ambang kualitas berubah.
"""

from pathlib import Path

# ---------------------------------------------------------------- folder
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"        # export mentah Kobo, JANGAN diedit manual
CLEAN_DIR = BASE_DIR / "data" / "clean"    # hasil bersih, ini yang masuk ArcGIS
LOG_DIR = BASE_DIR / "data" / "logs"       # catatan baris yang dibuang/diubah

# ---------------------------------------------------------------- CRS
CRS_GEOGRAPHIC = "EPSG:4326"   # lat/lon dari GPS HP. Format simpan & GeoJSON.
CRS_PROJECTED = "EPSG:32748"   # UTM 48S (Jakarta/Jabar). Ganti 32749 utk Jateng.

# ---------------------------------------------------------------- batas area studi
# Bounding box kasar (lon_min, lat_min, lon_max, lat_max).
# Ganti dengan batas area studi sebenarnya setelah PM menentukan.
STUDY_BBOX = (106.60, -6.50, 107.00, -6.10)

# Sanity check Indonesia — nangkap lat/lon ketuker atau format salah.
INDONESIA_BBOX = (95.0, -11.0, 141.0, 6.0)

# ---------------------------------------------------------------- aturan kualitas
MAX_GPS_ACCURACY_M = 20        # titik dengan akurasi lebih buruk dibuang
DUPLICATE_RADIUS_M = 5         # jarak dianggap titik yang sama
DUPLICATE_WINDOW_MIN = 5       # selisih waktu dianggap titik yang sama

# ---------------------------------------------------------------- bobot heatmap
# quantity_class -> bobot untuk Kernel Density / Population Field di ArcGIS.
# Non-linear: tumpukan besar jauh lebih berarti daripada segenggam.
QUANTITY_WEIGHT = {1: 1, 2: 3, 3: 8, 4: 20}

# ---------------------------------------------------------------- nilai yang sah
VALID_SITE_TYPE = [
    "riverbank", "market", "roadside", "school",
    "drain", "residential", "other",
]

VALID_PLASTIC_TYPE = [
    "pet_bottle", "sachet", "kresek", "styrofoam", "cup_straw", "other",
]

# ---------------------------------------------------------------- grid analisis
GRID_SIZE_M = 100  # ukuran sel grid untuk normalisasi effort (meter)
