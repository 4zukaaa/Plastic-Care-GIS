"""
Lapisan 3: bersihkan & validasi.

Prinsip: setiap baris yang dibuang atau diubah DICATAT dengan alasannya.
Tidak ada baris yang hilang tanpa jejak — ini yang bikin angka di peta akhir
bisa dipertanggungjawabkan di depan PM atau Dinas.
"""

from __future__ import annotations

import math
import re

import pandas as pd

import config
import schema


# ======================================================== util
def _log(rows: list, obs_id, rule: str, reason: str, action: str):
    rows.append({"obs_id": obs_id, "rule": rule, "reason": reason, "action": action})


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Jarak dua titik dalam meter. Cukup akurat untuk skala <1 km."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ======================================================== langkah 1: mapping kolom
def map_columns(df: pd.DataFrame, mapping: dict, required: list) -> pd.DataFrame:
    """Ubah nama kolom Kobo -> internal. Berhenti kalau kolom wajib hilang."""
    # Buang prefix grup Kobo: "group_lokasi/gps_point_latitude" -> "gps_point_latitude"
    df = df.rename(columns=lambda c: c.split("/")[-1].strip())
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})

    # Buang kolom duplikat hasil mapping (mis. dua varian nama lat).
    df = df.loc[:, ~df.columns.duplicated()]

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Kolom wajib tidak ditemukan setelah mapping: {missing}\n"
            f"Kolom yang ada: {sorted(df.columns)}\n"
            f"-> Tambahkan nama kolom aslinya ke mapping di schema.py"
        )
    return df


# ======================================================== langkah 2: normalisasi koordinat
_DMS_RE = re.compile(
    r"""(\d+(?:\.\d+)?)\s*[°d]\s*(\d+(?:\.\d+)?)\s*['m]\s*
        (\d+(?:\.\d+)?)?\s*["s]?\s*([NSEWnsew])""",
    re.VERBOSE,
)


def dms_to_dd(value) -> float | None:
    """Ubah 6°21'36\" S jadi -6.36. Return None kalau bukan format DMS."""
    if not isinstance(value, str):
        return None
    m = _DMS_RE.search(value)
    if not m:
        return None
    deg, minute, sec, hemi = m.groups()
    dd = float(deg) + float(minute) / 60 + float(sec or 0) / 3600
    return -dd if hemi.upper() in ("S", "W") else dd


def normalize_coords(df: pd.DataFrame, log_rows: list) -> pd.DataFrame:
    """Pastikan lat/lon berupa desimal. Tangani DMS dan lat/lon ketuker."""
    for col in ("lat", "lon"):
        numeric = pd.to_numeric(df[col], errors="coerce")
        # Baris yang gagal jadi angka: coba baca sebagai DMS.
        need_dms = numeric.isna() & df[col].notna()
        if need_dms.any():
            numeric.loc[need_dms] = df.loc[need_dms, col].map(dms_to_dd)
            for oid in df.loc[need_dms, "obs_id"]:
                _log(log_rows, oid, "coord_format", "format DMS", "dikonversi ke desimal")
        df[col] = numeric

    # Deteksi lat/lon ketuker: lat di luar rentang Indonesia tapi lon masuk.
    lon_min, lat_min, lon_max, lat_max = config.INDONESIA_BBOX
    swapped = (
        df["lat"].between(lon_min, lon_max)
        & ~df["lat"].between(lat_min, lat_max)
        & df["lon"].between(lat_min, lat_max)
    )
    if swapped.any():
        for oid in df.loc[swapped, "obs_id"]:
            _log(log_rows, oid, "coord_swapped", "lat/lon tertukar", "ditukar balik")
        df.loc[swapped, ["lat", "lon"]] = df.loc[swapped, ["lon", "lat"]].values

    return df


# ======================================================== langkah 3: aturan kualitas
def apply_quality_rules(df: pd.DataFrame, log_rows: list) -> pd.DataFrame:
    n_before = len(df)

    # R1 koordinat kosong -------------------------------------------------
    bad = df["lat"].isna() | df["lon"].isna()
    for oid in df.loc[bad, "obs_id"]:
        _log(log_rows, oid, "R1_no_coords", "lat/lon kosong", "dibuang")
    df = df[~bad]

    # R2 di luar bbox Indonesia (format salah total) ----------------------
    lon_min, lat_min, lon_max, lat_max = config.INDONESIA_BBOX
    bad = ~(df["lat"].between(lat_min, lat_max) & df["lon"].between(lon_min, lon_max))
    for oid in df.loc[bad, "obs_id"]:
        _log(log_rows, oid, "R2_outside_id", "koordinat di luar Indonesia", "dibuang")
    df = df[~bad]

    # R3 akurasi GPS buruk ------------------------------------------------
    if "gps_accuracy_m" in df.columns:
        acc = pd.to_numeric(df["gps_accuracy_m"], errors="coerce")
        bad = acc > config.MAX_GPS_ACCURACY_M
        for oid, a in zip(df.loc[bad, "obs_id"], acc[bad]):
            _log(log_rows, oid, "R3_gps_accuracy", f"akurasi {a:.0f} m", "dibuang")
        df = df[~bad]
        df["gps_accuracy_m"] = acc[~bad] if len(df) else acc

    # R4 di luar area studi -----------------------------------------------
    lon_min, lat_min, lon_max, lat_max = config.STUDY_BBOX
    bad = ~(df["lat"].between(lat_min, lat_max) & df["lon"].between(lon_min, lon_max))
    for oid in df.loc[bad, "obs_id"]:
        _log(log_rows, oid, "R4_outside_study", "di luar area studi", "dibuang")
    df = df[~bad]

    # R5 quantity_class tidak sah -----------------------------------------
    qty = pd.to_numeric(df["quantity_class"], errors="coerce")
    bad = ~qty.isin(list(config.QUANTITY_WEIGHT))
    for oid, q in zip(df.loc[bad, "obs_id"], qty[bad]):
        _log(log_rows, oid, "R5_quantity", f"quantity_class={q}", "dibuang")
    df = df[~bad]
    df["quantity_class"] = qty[~bad].astype(int) if len(df) else qty

    # R6 site_type / plastic_type tidak sah -> jadi "other" (tidak dibuang)
    if "site_type" in df.columns:
        bad = ~df["site_type"].isin(config.VALID_SITE_TYPE) & df["site_type"].notna()
        for oid, v in zip(df.loc[bad, "obs_id"], df.loc[bad, "site_type"]):
            _log(log_rows, oid, "R6_site_type", f"nilai '{v}'", "diubah ke 'other'")
        df.loc[bad, "site_type"] = "other"

    if "plastic_type" in df.columns:
        df["plastic_type"] = df["plastic_type"].fillna("other").astype(str)

    # R7 duplikat spasial-temporal ----------------------------------------
    df = _drop_duplicates(df, log_rows)

    print(f"  aturan kualitas: {n_before} -> {len(df)} baris")
    return df.reset_index(drop=True)


def _drop_duplicates(df: pd.DataFrame, log_rows: list) -> pd.DataFrame:
    """Titik sama (<=5 m, <=5 menit) dari surveyor berbeda = satu kejadian."""
    if "timestamp" not in df.columns or df.empty:
        return df

    ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.assign(_ts=ts).sort_values("_ts")
    keep, anchors = [], []  # anchors: (lat, lon, ts)

    for idx, row in df.iterrows():
        dup_of = None
        for a_lat, a_lon, a_ts, a_id in anchors:
            if pd.notna(row["_ts"]) and pd.notna(a_ts):
                gap = abs((row["_ts"] - a_ts).total_seconds()) / 60
                if gap > config.DUPLICATE_WINDOW_MIN:
                    continue
            if _haversine_m(row["lat"], row["lon"], a_lat, a_lon) <= config.DUPLICATE_RADIUS_M:
                dup_of = a_id
                break
        if dup_of is None:
            keep.append(idx)
            anchors.append((row["lat"], row["lon"], row["_ts"], row["obs_id"]))
        else:
            _log(log_rows, row["obs_id"], "R7_duplicate",
                 f"duplikat dari {dup_of}", "dibuang")

    return df.loc[keep].drop(columns="_ts")


# ======================================================== langkah 4: kolom turunan
def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Kolom yang dipakai langsung oleh ArcGIS."""
    # weight = Population Field untuk Kernel Density.
    df["weight"] = df["quantity_class"].map(config.QUANTITY_WEIGHT)

    # Kolom bantu analisis komposisi.
    if "plastic_type" in df.columns:
        df["n_plastic_types"] = (
            df["plastic_type"].astype(str).str.split(r"[\s,;]+").map(len)
        )
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df["survey_date"] = ts.dt.strftime("%Y-%m-%d")
    return df


# ======================================================== orkestrasi
def clean_observations(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Masuk: DataFrame mentah Kobo. Keluar: (data bersih, log pembersihan)."""
    log_rows: list = []
    df = map_columns(df_raw.copy(), schema.KOBO_TO_INTERNAL, schema.REQUIRED_INTERNAL)
    df = normalize_coords(df, log_rows)
    df = apply_quality_rules(df, log_rows)
    df = add_derived(df)
    return df, pd.DataFrame(log_rows)


def clean_effort(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Tabel effort: ringan, cuma butuh nama kolom seragam + durasi numerik."""
    df = map_columns(df_raw.copy(), schema.EFFORT_KOBO_TO_INTERNAL, schema.EFFORT_REQUIRED)
    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce")
    return df.dropna(subset=["duration_min"])
