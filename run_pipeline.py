#!/usr/bin/env python3
"""
Titik masuk tunggal. Jalankan ini, selesai.

    python run_pipeline.py --obs data/raw/observations.csv \
                           --effort data/raw/effort.csv

Atau tanpa argumen: ambil file terbaru di data/raw/ otomatis.

Alur: baca mentah -> bersihkan -> catat log -> ekspor format ArcGIS.
Data mentah tidak pernah diubah. Semua perbaikan terjadi di kode, supaya
hasil akhir bisa diproduksi ulang dari nol kapan saja.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

import clean
import config
import export


def read_any(path: Path) -> pd.DataFrame:
    """Kobo bisa mengekspor CSV (titik koma/koma), XLSX, atau JSON."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if suffix == ".json":
        return pd.read_json(path)
    # CSV: deteksi pemisah otomatis (Kobo sering pakai ';').
    return pd.read_csv(path, sep=None, engine="python")


def newest(pattern: str) -> Path | None:
    files = sorted(config.RAW_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline pembersihan PLASTI-CARE")
    ap.add_argument("--obs", type=Path, help="file export observasi dari Kobo")
    ap.add_argument("--effort", type=Path, help="file export survey effort")
    args = ap.parse_args()

    for d in (config.RAW_DIR, config.CLEAN_DIR, config.LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    obs_path = args.obs or newest("observations*")
    if not obs_path or not obs_path.exists():
        print(f"ERROR: file observasi tidak ditemukan.\n"
              f"Taruh export Kobo di {config.RAW_DIR}/ dengan nama "
              f"'observations_YYYYMMDD.csv', atau pakai --obs")
        return 1

    print(f"\n[1/4] Baca data mentah: {obs_path.name}")
    df_raw = read_any(obs_path)
    print(f"  {len(df_raw)} baris, {len(df_raw.columns)} kolom")

    print("[2/4] Bersihkan & validasi")
    df_clean, df_log = clean.clean_observations(df_raw)

    effort_path = args.effort or newest("effort*")
    df_effort = None
    if effort_path and effort_path.exists():
        print(f"  baca effort: {effort_path.name}")
        df_effort = clean.clean_effort(read_any(effort_path))
    else:
        print("  PERINGATAN: tidak ada data effort. Heatmap tidak bisa "
              "dikoreksi terhadap cakupan survei.")

    print("[3/4] Tulis log pembersihan")
    log_path = config.LOG_DIR / "cleaning_log.csv"
    df_log.to_csv(log_path, index=False, encoding="utf-8-sig")
    if not df_log.empty:
        print(df_log["rule"].value_counts().to_string())
    print(f"  -> {log_path}")

    print("[4/4] Ekspor untuk ArcGIS")
    outs = [
        export.export_csv(df_clean, config.CLEAN_DIR),
        export.export_geojson(df_clean, config.CLEAN_DIR),
    ]
    outs += export.export_spatial(df_clean, config.CLEAN_DIR)
    for fn in (export.export_effort_summary, export.export_composition):
        p = (fn(df_clean, df_effort, config.CLEAN_DIR)
             if fn is export.export_effort_summary
             else fn(df_clean, config.CLEAN_DIR))
        if p:
            outs.append(p)

    print("\nSELESAI")
    print(f"  masuk   : {len(df_raw)} baris")
    print(f"  lolos   : {len(df_clean)} baris "
          f"({len(df_clean) / max(len(df_raw), 1) * 100:.0f}%)")
    print(f"  dibuang : {len(df_log)} catatan di cleaning_log.csv")
    print(f"  bobot   : total {int(df_clean['weight'].sum())} "
          f"(Population Field untuk Kernel Density)")
    print("\nFile hasil:")
    for p in outs:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
