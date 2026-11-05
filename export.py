"""
Lapisan 5: ekspor ke format yang langsung dimakan ArcGIS.

Tiga output, sengaja redundan karena tiap format punya kelebihan:
1. CSV  -> ArcGIS Pro: "XY Table To Point". Paling fleksibel, nama kolom bebas.
2. GeoJSON -> drag & drop ke ArcGIS Pro / ArcGIS Online. Sudah bergeometri.
3. Shapefile / GeoPackage (kalau geopandas tersedia) -> format klasik ArcGIS.

Catatan penting soal Shapefile: nama kolom maksimal 10 karakter dan tipe teks
maksimal 254 karakter. Itu sebabnya ada pemetaan INTERNAL_TO_ARCGIS di schema.py
— lebih baik kita yang menentukan nama pendeknya daripada dipotong otomatis.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import config
import schema


# ======================================================== CSV untuk XY Table To Point
def export_csv(df: pd.DataFrame, out_dir: Path) -> Path:
    cols = [c for c in schema.EXPORT_COLUMNS if c in df.columns]
    path = out_dir / "plasticare_points.csv"
    df[cols].to_csv(path, index=False, encoding="utf-8-sig")  # BOM biar Excel aman
    return path


# ======================================================== GeoJSON (tanpa geopandas)
def export_geojson(df: pd.DataFrame, out_dir: Path) -> Path:
    """GeoJSON ditulis manual: jalan di tablet/Colab tanpa install apa pun."""
    cols = [c for c in schema.EXPORT_COLUMNS if c in df.columns]
    features = []
    for rec in df[cols].to_dict("records"):
        lon, lat = rec.pop("lon"), rec.pop("lat")
        props = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": props,
        })

    fc = {
        "type": "FeatureCollection",
        "name": "plasticare_points",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    path = out_dir / "plasticare_points.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    return path


# ======================================================== Shapefile / GeoPackage
def export_spatial(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    """Butuh geopandas. Kalau tidak ada, dilewati dengan pesan — bukan error."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError:
        print("  geopandas tidak tersedia -> Shapefile/GPKG dilewati "
              "(CSV & GeoJSON sudah cukup untuk ArcGIS)")
        return []

    cols = [c for c in schema.EXPORT_COLUMNS if c in df.columns]
    gdf = gpd.GeoDataFrame(
        df[cols].copy(),
        geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
        crs=config.CRS_GEOGRAPHIC,
    )

    written = []

    # GeoPackage: nama kolom panjang aman, satu file, format modern.
    gpkg = out_dir / "plasticare.gpkg"
    gdf.to_file(gpkg, layer="points", driver="GPKG")
    written.append(gpkg)

    # Shapefile: nama kolom dipendekkan dulu + reproyeksi ke UTM supaya
    # Kernel Density di ArcGIS langsung bekerja dalam satuan meter.
    shp_dir = out_dir / "shapefile"
    shp_dir.mkdir(exist_ok=True)
    short = gdf.rename(columns=schema.INTERNAL_TO_ARCGIS)
    for c in short.columns:
        if short[c].dtype == object and c != "geometry":
            short[c] = short[c].astype(str).str.slice(0, 254)
    shp = shp_dir / "plasticare_points_utm48s.shp"
    short.to_crs(config.CRS_PROJECTED).to_file(shp, driver="ESRI Shapefile")
    written.append(shp)

    return written


# ======================================================== tabel agregat
def export_effort_summary(df_points: pd.DataFrame, df_effort: pd.DataFrame,
                          out_dir: Path) -> Path | None:
    """
    Tabel inti untuk peta versi jujur: sampah per jam survei per zona.

    Tanpa ini, heatmap cuma menunjukkan di mana siswa berjalan.
    """
    if df_effort is None or df_effort.empty or "zone_id" not in df_points.columns:
        print("  data effort tidak ada -> ringkasan normalisasi dilewati")
        return None

    trash = df_points.groupby("zone_id").agg(
        n_points=("obs_id", "count"),
        total_weight=("weight", "sum"),
    )
    effort = df_effort.groupby("zone_id").agg(
        survey_min=("duration_min", "sum"),
        n_sessions=("effort_id", "count"),
    )

    # outer join: zona yang disurvei tapi nol sampah TETAP muncul (nilai 0).
    out = effort.join(trash, how="outer").fillna(0)
    out["survey_hours"] = out["survey_min"] / 60
    out["points_per_hour"] = (out["n_points"] / out["survey_hours"]).round(2)
    out["weight_per_hour"] = (out["total_weight"] / out["survey_hours"]).round(2)
    out = out.replace([float("inf")], 0).reset_index()

    path = out_dir / "zone_effort_normalized.csv"
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_composition(df: pd.DataFrame, out_dir: Path) -> Path | None:
    """Komposisi jenis plastik per tipe lokasi — bahan rekomendasi kebijakan."""
    if "plastic_type" not in df.columns or "site_type" not in df.columns:
        return None

    rows = []
    for _, r in df.iterrows():
        for p in str(r["plastic_type"]).replace(";", " ").replace(",", " ").split():
            rows.append({"site_type": r["site_type"], "plastic_type": p,
                         "weight": r["weight"]})
    if not rows:
        return None

    long = pd.DataFrame(rows)
    pivot = long.pivot_table(index="site_type", columns="plastic_type",
                             values="weight", aggfunc="sum", fill_value=0)
    path = out_dir / "composition_site_x_plastic.csv"
    pivot.to_csv(path, encoding="utf-8-sig")
    return path
