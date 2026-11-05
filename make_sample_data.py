#!/usr/bin/env python3
"""
Bikin data dummy yang MENIRU export Kobo, termasuk 6 jenis data kotor:
akurasi GPS buruk, lat/lon ketuker, format DMS, di luar area studi,
quantity_class ngaco, dan duplikat dua siswa di titik yang sama.

Tujuannya: lo bisa menguji pipeline hari ini, sebelum data siswa masuk.
Jalankan: python make_sample_data.py
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

import config

random.seed(7)
RAW = config.RAW_DIR
RAW.mkdir(parents=True, exist_ok=True)

SITES = ["riverbank", "market", "roadside", "school", "drain", "residential"]
PLASTICS = ["pet_bottle", "sachet", "kresek", "styrofoam", "cup_straw"]
ZONES = ["RW01", "RW02", "RW03", "SCHOOL_A", "RIVER_1"]

# Pusat hotspot buatan supaya heatmap kelihatan ada polanya saat diuji.
HOTSPOTS = [(-6.3550, 106.8200), (-6.3700, 106.8350), (-6.3620, 106.8100)]

rows, t0 = [], datetime(2026, 11, 3, 8, 0)

for i in range(120):
    hlat, hlon = random.choice(HOTSPOTS)
    lat = round(hlat + random.gauss(0, 0.0035), 6)
    lon = round(hlon + random.gauss(0, 0.0035), 6)
    rows.append({
        "_uuid": f"obs-{i:04d}",
        "_submission_time": (t0 + timedelta(minutes=7 * i)).isoformat(),
        "surveyor_id": f"S{random.randint(1, 8):02d}",
        "zone_id": random.choice(ZONES),
        "group_lokasi/gps_point_latitude": lat,
        "group_lokasi/gps_point_longitude": lon,
        "group_lokasi/gps_point_precision": round(random.uniform(3, 14), 1),
        "site_type": random.choice(SITES),
        "plastic_type": " ".join(random.sample(PLASTICS, random.randint(1, 3))),
        "quantity_class": random.choices([1, 2, 3, 4], weights=[4, 3, 2, 1])[0],
        "notes": "",
    })

base = dict(rows[0])


def dirty(**kw):
    r = dict(base)
    r.update(kw)
    rows.append(r)


# 1. akurasi GPS buruk -> harus dibuang (R3)
dirty(_uuid="bad-gps", **{"group_lokasi/gps_point_precision": 45.0})
# 2. lat/lon ketuker -> harus ditukar balik otomatis
dirty(_uuid="swapped", **{"group_lokasi/gps_point_latitude": 106.8200,
                          "group_lokasi/gps_point_longitude": -6.3550})
# 3. format DMS -> harus dikonversi
dirty(_uuid="dms-fmt", **{"group_lokasi/gps_point_latitude": "6°21'18\" S",
                          "group_lokasi/gps_point_longitude": "106°49'12\" E"})
# 4. di luar area studi (Surabaya) -> dibuang (R4)
dirty(_uuid="far-away", **{"group_lokasi/gps_point_latitude": -7.2575,
                           "group_lokasi/gps_point_longitude": 112.7521})
# 5. quantity_class ngaco -> dibuang (R5)
dirty(_uuid="bad-qty", quantity_class=9)
# 6. site_type tidak ada di daftar -> diubah jadi "other" (R6)
dirty(_uuid="bad-site", site_type="pinggir kali banget")
# 7. duplikat: siswa lain, titik & waktu sama -> salah satu dibuang (R7)
dirty(_uuid="dup-pair", surveyor_id="S09")

pd.DataFrame(rows).to_csv(RAW / "observations_20261105.csv", index=False)

# Tabel effort: zona RIVER_1 sengaja disurvei singkat, RW01 lama.
# Nanti terlihat bedanya antara heatmap mentah vs normalisasi per jam.
effort = [
    {"_uuid": f"eff-{i:03d}", "surveyor_id": f"S{random.randint(1, 8):02d}",
     "zone_id": z, "survey_date": "2026-11-03",
     "duration_min": random.choice(dur), "route_note": f"rute {z}"}
    for z, dur in [("RW01", [90, 120]), ("RW02", [60, 75]), ("RW03", [45, 60]),
                   ("SCHOOL_A", [30, 45]), ("RIVER_1", [20, 25])]
    for i in range(4)
]
pd.DataFrame(effort).to_csv(RAW / "effort_20261105.csv", index=False)

print(f"Dibuat di {RAW}:")
print(f"  observations_20261105.csv  ({len(rows)} baris, 7 kasus kotor)")
print(f"  effort_20261105.csv        ({len(effort)} sesi survei)")
