import os
import math
import pandas as pd
from tqdm import tqdm

from osgeo import ogr, osr, gdal

# Make GDAL a bit more explicit & traditional lon/lat ordering
gdal.UseExceptions()
os.environ.setdefault("OGR_CT_FORCE_TRADITIONAL_GIS_ORDER", "YES")

GDB_PATH   = r"F:\work\data\hydrolakes\HydroLAKES_polys_v10.gdb"
LAYER_NAME = "HydroLAKES_polys_v10"
CSV_PATH   = r"E:\publications\noori_5\data\final_clean_2\lakescci_v210.csv"
OUT_PATH   = r"E:\publications\noori_5\data\final_clean_2\matches.csv"

KEEP_COLS = ["id", "short_name", "lat_cntral", "lon_cntral"]

# Primary tiny bbox half-size (degrees). ~1e-4 deg ≈ 11 m at equator.
EPS_PRIMARY = 1e-4
# Secondary (fallback) bbox half-size (degrees). ~5e-4 deg ≈ 55 m.
EPS_FALLBACK = 5e-4

def open_fgdb_layer(gdb_path, layer_name):
    if not os.path.isdir(gdb_path) or not gdb_path.lower().endswith(".gdb"):
        raise RuntimeError(f"Not a valid File Geodatabase directory: {gdb_path}")

    ds = ogr.Open(gdb_path, 0)  # read-only
    if ds is None:
        raise RuntimeError(f"Could not open FGDB: {gdb_path}")

    lyr = ds.GetLayerByName(layer_name)
    if lyr is None:
        raise RuntimeError(f"Could not find layer '{layer_name}' in FGDB: {gdb_path}")
    return ds, lyr

def get_field_name_case_insensitive(layer, target_name):
    """Return the actual field name in the layer that case-insensitively matches target_name."""
    defn = layer.GetLayerDefn()
    lc_target = target_name.lower()
    for i in range(defn.GetFieldCount()):
        nm = defn.GetFieldDefn(i).GetName()
        if nm.lower() == lc_target:
            return nm
    return None

def build_point(lon, lat, srs):
    pt = ogr.Geometry(ogr.wkbPoint)
    pt.AddPoint(float(lon), float(lat))
    pt.AssignSpatialReference(srs)
    return pt

def bbox_filter(layer, x, y, half_size_deg):
    """Apply a small-rectangle spatial filter around the point."""
    layer.SetSpatialFilterRect(x - half_size_deg, y - half_size_deg, x + half_size_deg, y + half_size_deg)
    layer.ResetReading()

def main():
    # Load input CSV
    df = pd.read_csv(CSV_PATH, low_memory=False)
    missing = [c for c in KEEP_COLS if c not in df.columns]
    if missing:
        raise RuntimeError(f"CSV is missing required columns: {missing}")

    # Open HydroLAKES layer
    ds, lyr = open_fgdb_layer(GDB_PATH, LAYER_NAME)

    # WGS84 for points
    srs_points = osr.SpatialReference()
    srs_points.ImportFromEPSG(4326)

    # Layer SRS (should be EPSG:4326 per your metadata)
    srs_layer = lyr.GetSpatialRef() or srs_points.Clone()
    need_tx = not srs_layer.IsSame(srs_points)
    coord_tx = osr.CoordinateTransformation(srs_points, srs_layer) if need_tx else None

    # Resolve exact Hylak_id field name (case-insensitive)
    hylak_field = get_field_name_case_insensitive(lyr, "Hylak_id")
    if hylak_field is None:
        raise RuntimeError("Could not find a field named 'Hylak_id' (any case) in HydroLAKES layer.")

    results = []
    matched = 0
    unmatched = 0

    for row in tqdm(df.itertuples(index=False), total=len(df), desc="Matching points to HydroLAKES"):
        try:
            pid        = getattr(row, "id")
            short_name = getattr(row, "short_name")
            lat_c      = float(getattr(row, "lat_cntral"))
            lon_c      = float(getattr(row, "lon_cntral"))
        except Exception:
            results.append((getattr(row, "id", None),
                            getattr(row, "short_name", None),
                            float('nan'), float('nan'), None))
            unmatched += 1
            continue

        # Build point in EPSG:4326, transform if needed
        pt = build_point(lon_c, lat_c, srs_points)
        if need_tx:
            pt.Transform(coord_tx)
        x = pt.GetX()
        y = pt.GetY()

        # 1) primary small bbox filter
        bbox_filter(lyr, x, y, EPS_PRIMARY)

        hylak_id_val = None
        found = False

        # Iterate candidates; use Intersects to include boundary cases
        for feat in lyr:
            geom = feat.GetGeometryRef()
            if geom is None:
                continue
            if geom.Intersects(pt):  # robust: includes Contains & boundary touches
                hylak_id_val = feat.GetField(hylak_field)
                found = True
                break

        if not found:
            # 2) fallback with a slightly larger bbox for indexing precision / tiny offsets
            bbox_filter(lyr, x, y, EPS_FALLBACK)
            for feat in lyr:
                geom = feat.GetGeometryRef()
                if geom is None:
                    continue
                if geom.Intersects(pt):
                    hylak_id_val = feat.GetField(hylak_field)
                    found = True
                    break

        # Clear filter for next loop (good hygiene)
        lyr.SetSpatialFilter(None)

        if found and hylak_id_val is not None:
            matched += 1
        else:
            unmatched += 1
            hylak_id_val = None

        results.append((pid, short_name, lat_c, lon_c, hylak_id_val))

    out_df = pd.DataFrame(results, columns=KEEP_COLS + ["Hylak_id"])
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out_df.to_csv(OUT_PATH, index=False)

    print(f"Done. Wrote: {OUT_PATH}")
    print(f"Matched: {matched}   Unmatched: {unmatched} (total: {len(df)})")

if __name__ == "__main__":
    main()
