import geopandas as gpd
try:
    # Shapely 2.x
    from shapely.validation import make_valid
except ImportError:
    # Shapely 1.8.x fallback
    from shapely import make_valid
from shapely.geometry import Polygon, MultiPolygon

csb_file = "GeoFiles/CSB/CSB_AZ.shp"
gdf = gpd.read_file(csb_file)

print("Source CRS:", gdf.crs)
print("Initial valid vs invalid:\n", gdf.is_valid.value_counts(dropna=False))

# Reproject for area if CRS is geographic
if gdf.crs is None:
    raise ValueError("Input has no CRS. Assign or define before processing.")
if gdf.crs.is_geographic:
    gdf = gdf.to_crs(5070)
    print("Reprojected to EPSG:5070 for area-safe operations.")

# Repair geometries
gdf["geometry"] = gdf.geometry.apply(make_valid)

print("Post make_valid invalid count:", (~gdf.geometry.is_valid).sum())

# Remove empty
gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]

def extract_polygonal(geom):
    if geom is None:
        return None
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if geom.geom_type == "GeometryCollection":
        polys = [p for p in geom.geoms if isinstance(p, (Polygon, MultiPolygon))]
        if not polys:
            return None
        # Preserve separate parts instead of dissolving: wrap in MultiPolygon if needed
        if len(polys) == 1:
            return polys[0]
        # Avoid dissolving; union_all would merge touching parts
        return MultiPolygon([p for poly in polys for p in (poly.geoms if isinstance(poly, MultiPolygon) else [poly])])
    return None

gdf["geometry"] = gdf.geometry.apply(extract_polygonal)
gdf = gdf[gdf.geometry.notna()]

# Area filter (units now m² after reprojection)
area_threshold_m2 = 1.0
gdf["area_m2"] = gdf.geometry.area
gdf = gdf[gdf.area_m2 >= area_threshold_m2]

# Explode multipart geometries to clean parts, then dissolve back to unique CSBID
gdf = gdf.explode(index_parts=False, ignore_index=True)

# Optional final validity repair after explode
if (~gdf.geometry.is_valid).any():
    gdf["geometry"] = gdf.geometry.apply(make_valid)

# Drop zero-area artifacts again (rare)
gdf = gdf[gdf.geometry.area > 0]

# Remove exact duplicates
gdf["__wkb__"] = gdf.geometry.apply(lambda geom: geom.wkb)
gdf = gdf.drop_duplicates(subset="__wkb__").drop(columns="__wkb__")

# Dissolve back to one geometry per CSBID (preserve attributes)
non_geom_cols = [c for c in gdf.columns if c != "geometry"]
agg = {c: "first" for c in non_geom_cols if c != "CSBID"}
gdf = gdf.dissolve(by="CSBID", as_index=False, aggfunc=agg)

gdf = gdf.reset_index(drop=True)
# Drop area_m2 if not needed
gdf = gdf.drop(columns="area_m2")

print("Final geometry types:\n", gdf.geometry.geom_type.value_counts())
print("Final invalid geometries:", (~gdf.geometry.is_valid).sum())
print("Empty geometries:", gdf.geometry.is_empty.sum())
print("Total features:", len(gdf))

out_file = "GeoFiles/CSB/CSB_AZ_cleaned.shp"
print("Columns:", gdf.columns.tolist())
gdf.to_file(out_file)
print("Saved:", out_file)
