"""
Kontrak data: nama kolom Kobo -> nama kolom internal -> nama kolom ArcGIS.

Kenapa tiga lapis?
- Kobo bikin nama kolom panjang & bergrup (mis. "group_lokasi/gps_point_latitude").
- Kode internal pakai nama pendek yang enak dibaca.
- Shapefile HANYA boleh 10 karakter per nama kolom; lebih dari itu dipotong
  otomatis oleh driver dan jadi kacau. Jadi dipetakan eksplisit di sini.
"""

# ------------------------------------------------- Kobo -> internal
# Kiri: kemungkinan nama kolom di export Kobo (tambahkan sesuai form aslimu).
# Kanan: nama internal yang dipakai seluruh pipeline.
KOBO_TO_INTERNAL = {
    "_uuid": "obs_id",
    "_id": "kobo_id",
    "_submission_time": "timestamp",
    "today": "survey_date",
    "surveyor_id": "surveyor_id",
    "zone_id": "zone_id",
    "site_type": "site_type",
    "plastic_type": "plastic_type",
    "quantity_class": "quantity_class",
    "notes": "notes",
    # Geopoint Kobo biasanya pecah jadi 4 kolom berikut:
    "_geolocation_latitude": "lat",
    "_geolocation_longitude": "lon",
    "gps_point_latitude": "lat",
    "gps_point_longitude": "lon",
    "gps_point_precision": "gps_accuracy_m",
    "_gps_point_precision": "gps_accuracy_m",
    # Varian lain yang sering muncul:
    "location_latitude": "lat",
    "location_longitude": "lon",
    "location_precision": "gps_accuracy_m",
    "_attachments": "photo",
    "photo_URL": "photo",
}

# Kolom wajib ada setelah mapping. Kalau tidak ada, pipeline berhenti dengan
# pesan jelas, bukan error aneh 50 baris kemudian.
REQUIRED_INTERNAL = ["obs_id", "lat", "lon", "quantity_class"]

# Kolom yang ikut diekspor, dalam urutan ini.
EXPORT_COLUMNS = [
    "obs_id", "timestamp", "surveyor_id", "zone_id",
    "site_type", "plastic_type", "quantity_class", "weight",
    "lat", "lon", "gps_accuracy_m", "notes",
]

# ------------------------------------------------- internal -> ArcGIS (<=10 char)
INTERNAL_TO_ARCGIS = {
    "obs_id": "obs_id",
    "timestamp": "obs_time",
    "surveyor_id": "srv_id",
    "zone_id": "zone_id",
    "site_type": "site_type",
    "plastic_type": "plas_type",
    "quantity_class": "qty_cls",
    "weight": "weight",
    "lat": "lat",
    "lon": "lon",
    "gps_accuracy_m": "gps_acc",
    "notes": "notes",
}

# ------------------------------------------------- tabel survey effort
EFFORT_KOBO_TO_INTERNAL = {
    "_uuid": "effort_id",
    "surveyor_id": "surveyor_id",
    "zone_id": "zone_id",
    "survey_date": "survey_date",
    "today": "survey_date",
    "duration_min": "duration_min",
    "route_note": "route_note",
}

EFFORT_REQUIRED = ["effort_id", "surveyor_id", "zone_id", "duration_min"]
