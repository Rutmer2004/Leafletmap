"""Bestaand bodemmodel (maaiveld + zeebodem) in EPSG:31984, hoogten t.o.v. MLWS.

Bronnen:
  zee  GEBCO 2026 (15", ca. 450 m), via Source Cooperative (ausantarctic/gebco), t.o.v. gemiddeld zeeniveau
  land Copernicus DEM GLO-30 (30 m), AWS Open Data, t.o.v. EGM2008 (ca. gemiddeld zeeniveau)
Aanname: MLWS ligt MSL_MLWS m onder gemiddeld zeeniveau (springtij, getijslag ca. 1,4 m); koppeling met DHN nog te verifiëren.

Gebruik:  python3 src/bodem.py <gebco.tif> <copdem.tif>   -> CAD/Ondergrond/bestaand_bodem_MLWS_EPSG31984.tif
"""
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RASTER = os.path.join(ROOT, "CAD", "Ondergrond", "bestaand_bodem_MLWS_EPSG31984.tif")
MSL_MLWS = 0.7
BBOX = (286000.0, 7610000.0, 350000.0, 7660000.0)  # W, S, E, N
RES = 30.0
_CACHE = {}


def build(gebco, copdem, out=RASTER):
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject
    W, S, E, N = BBOX
    nx, ny = int((E - W) / RES), int((N - S) / RES)
    tr = from_origin(W, N, RES, RES)
    sea = np.full((ny, nx), np.nan, dtype="float32")
    land = np.full((ny, nx), np.nan, dtype="float32")
    with rasterio.open(gebco) as g:
        reproject(rasterio.band(g, 1), sea, dst_transform=tr, dst_crs="EPSG:31984", resampling=Resampling.bilinear,
                  dst_nodata=np.nan)
    with rasterio.open(copdem) as c:
        reproject(rasterio.band(c, 1), land, dst_transform=tr, dst_crs="EPSG:31984", resampling=Resampling.bilinear,
                  src_nodata=-32767, dst_nodata=np.nan)
    z = np.where(np.isfinite(land) & (land > 0.3), land, np.minimum(sea, -0.5))
    z = np.where(np.isfinite(z), z, sea) + MSL_MLWS          # MSL -> MLWS
    with rasterio.open(out, "w", driver="GTiff", width=nx, height=ny, count=1, dtype="float32", crs="EPSG:31984",
                       transform=tr, nodata=np.nan, compress="deflate") as d:
        d.write(z.astype("float32"), 1)
    return out


def _load():
    if "z" not in _CACHE:
        import rasterio
        if not os.path.exists(RASTER):
            return None
        with rasterio.open(RASTER) as r:
            _CACHE["z"] = r.read(1)
            _CACHE["tr"] = r.transform
    return _CACHE["z"], _CACHE["tr"]


def available():
    return _load() is not None


def z_at(x, y):
    """Hoogte t.o.v. MLWS (m, positief omhoog) op punt (x, y), bilineair."""
    z, tr = _load()
    c = (x - tr.c) / tr.a - 0.5
    r = (y - tr.f) / tr.e - 0.5
    c0, r0 = int(math.floor(c)), int(math.floor(r))
    fc, fr = c - c0, r - r0
    v = z[r0:r0 + 2, c0:c0 + 2]
    if v.shape != (2, 2):
        return float("nan")
    return float((v[0, 0] * (1 - fc) + v[0, 1] * fc) * (1 - fr) + (v[1, 0] * (1 - fc) + v[1, 1] * fc) * fr)


def profiel(start, richting, lengte=40000.0, stap=250.0, breedte=1000.0):
    """Gemiddelde hoogte (MLWS) over een strook van +-breedte langs een as."""
    ux, uy = richting
    nx, ny = -uy, ux
    out = []
    for i in range(int(lengte / stap) + 1):
        s = i * stap
        vals = [z_at(start[0] + ux * s + nx * o, start[1] + uy * s + ny * o) for o in np.linspace(-breedte, breedte, 5)]
        out.append((s, float(np.nanmean(vals))))
    return np.array(out)


def drempel_afstand(start, richting, diepte, venster=2000.0, max_lengte=40000.0):
    """Kleinste afstand vanaf 'start' waarna de (over 'venster' gemiddelde) natuurlijke diepte overal >= 'diepte' is."""
    p = profiel(start, richting, max_lengte)
    w = max(1, int(venster / (p[1, 0] - p[0, 0])))
    sm = np.convolve(p[:, 1], np.ones(w) / w, mode="same")
    ok = -sm >= diepte
    for i in range(len(ok)):
        if ok[i:-w // 2 or None].all():
            return float(p[i, 0]), p
    return float(max_lengte), p


def profiel_route(pts, stap=250.0, breedte=1000.0):
    """Als profiel(), maar langs een polylijn (geul met bocht): (afstand langs de route, gemiddelde hoogte)."""
    from shapely.geometry import LineString
    ls = LineString(pts)
    out = []
    for s in np.arange(0, ls.length + 1e-6, stap):
        p, q = ls.interpolate(s), ls.interpolate(min(ls.length, s + 1.0))
        if s + 1.0 > ls.length:
            p, q = ls.interpolate(s - 1.0), ls.interpolate(s)
        L = math.hypot(q.x - p.x, q.y - p.y)
        nx, ny = -(q.y - p.y) / L, (q.x - p.x) / L
        c = ls.interpolate(s)
        vals = [z_at(c.x + nx * o, c.y + ny * o) for o in np.linspace(-breedte, breedte, 5)]
        out.append((float(s), float(np.nanmean(vals))))
    return np.array(out)


def drempel_route(pts, diepte, venster=2000.0):
    """Eerste afstand langs de route waarna de natuurlijke diepte (over 'venster' gemiddeld) tot het einde >= 'diepte' is."""
    p = profiel_route(pts)
    w = max(1, int(venster / (p[1, 0] - p[0, 0])))
    sm = np.convolve(p[:, 1], np.ones(w) / w, mode="same")
    ok = -sm >= diepte
    for i in range(len(ok)):
        if ok[i:-w // 2 or None].all():
            return float(p[i, 0])
    return float(p[-1, 0])


def volume(geom, ontwerpdiepte):
    """Celmethode: V = som A x max(0, ontwerpdiepte - bestaande diepte); geeft (volume m3, oppervlak m2, gem. bestaande diepte)."""
    from rasterio.features import geometry_mask
    z, tr = _load()
    m = ~geometry_mask([geom.__geo_interface__], out_shape=z.shape, transform=tr, all_touched=False)
    zz = z[m]
    zz = zz[np.isfinite(zz)]
    if zz.size == 0:
        return 0.0, 0.0, float("nan")
    a = abs(tr.a * tr.e)
    d = -zz
    return float(np.sum(np.maximum(0, ontwerpdiepte - d)) * a), float(zz.size * a), float(np.mean(d))


def ophoging(geom, bovenkant, zetting):
    from rasterio.features import geometry_mask
    z, tr = _load()
    m = ~geometry_mask([geom.__geo_interface__], out_shape=z.shape, transform=tr)
    zz = z[m]
    zz = zz[np.isfinite(zz)]
    a = abs(tr.a * tr.e)
    return float(np.sum(np.maximum(0, bovenkant - zz + zetting)) * a), float(zz.size * a), float(np.mean(zz))


def dieptelijnen(niveaus=(-5.0, -10.0, -15.0, -18.2, -20.0), glad=2.0):
    """Dieptelijnen (t.o.v. MLWS) als lijst (niveau, LineString) in EPSG:31984."""
    from scipy.ndimage import gaussian_filter
    from shapely.geometry import LineString
    from skimage import measure
    z, tr = _load()
    zs = gaussian_filter(np.nan_to_num(z, nan=0.0), glad)
    out = []
    for lv in niveaus:
        for c in measure.find_contours(zs, lv):
            if len(c) < 20:
                continue
            pts = [(tr.c + (col + 0.5) * tr.a, tr.f + (row + 0.5) * tr.e) for row, col in c]
            ls = LineString(pts).simplify(15)
            if ls.length > 1500:
                out.append((lv, ls))
    return out


def afgraving(geom, bovenkant):
    """Volume boven 'bovenkant' (m3) binnen geom: land dat op ontwerppeil moet worden gebracht."""
    from rasterio.features import geometry_mask
    z, tr = _load()
    m = ~geometry_mask([geom.__geo_interface__], out_shape=z.shape, transform=tr)
    zz = z[m]
    zz = zz[np.isfinite(zz)]
    return float(np.sum(np.maximum(0, zz - bovenkant)) * abs(tr.a * tr.e))


def grondwerk(d, maaiveld=5.0, zetting=0.5):
    """Bagger- en grondverzetvolumes per vak met de celmethode (rapport par. 12.1)."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    n = d.notes
    geteld = None
    vakken = []

    def vak(naam, geom, diepte, zone):
        nonlocal geteld
        g = geom if geteld is None else geom.difference(geteld)
        if g.is_empty or g.area < 1:
            return
        geteld = g if geteld is None else unary_union([geteld, g])
        v, a, dm = volume(g, diepte)
        v18, _, _ = volume(g, 18.2)
        vakken.append(dict(vak=naam, zone=zone, diepte=diepte, oppervlak=a, bestaande_diepte=dm, volume=v, volume_18=v18))

    for i in d.items:
        if i["layer"] == "HV-BAGGER" and i["phase"] <= 3:
            vak(i["label"] or "bekken", i["geom"], i.get("diepte", 18.2), 1)
    from shapely.ops import substring
    route = LineString(n.get("geul_route") or [d.P(*n["M"]), d.P(*n["eind"])])
    l15 = n.get("geul_15") or route.length / 2
    geul = unary_union([i["geom"] for i in d.items if i["layer"] == "HV-GEUL" and i.get("tag") == "geul_buiten"])
    if not geul.is_empty:
        knip = substring(route, l15, route.length).buffer(400, cap_style="flat")
        vak("Geul tot DHN -15 m", geul.difference(knip), 18.2, 2)
        vak("Geul voorbij DHN -15 m", geul.intersection(knip), 18.2, 3)
    for i in d.items:
        if i["layer"] == "HV-GEUL":
            vak("Geul (overig)", i["geom"], 18.2, 2)
    terr = unary_union([i["geom"] for i in d.items if i.get("tag") in
                        ("cyard", "graan_plot", "roro_plot", "lng_zone", "centrale", "havendienst")])
    vul, a_t, h_t = ophoging(terr, maaiveld, zetting)
    out = dict(vakken=vakken, maaiveld=maaiveld, zetting=zetting, terrein_m2=a_t, terrein_gem_hoogte=h_t,
               ophoging_m3=vul, afgraving_m3=afgraving(terr, maaiveld))
    for z in (1, 2, 3):
        vz = [v for v in vakken if v["zone"] == z]
        A = sum(v["oppervlak"] for v in vz)
        out[f"zone{z}"] = dict(oppervlak=A, volume=sum(v["volume"] for v in vz),
                               bestaande_diepte=(sum(v["oppervlak"] * v["bestaande_diepte"] for v in vz) / A) if A else None)
    out["totaal_bagger_m3"] = sum(v["volume"] for v in vakken)
    out["besparing_dieptezones_m3"] = sum(v["volume_18"] - v["volume"] for v in vakken)
    return out


if __name__ == "__main__":
    print(build(sys.argv[1], sys.argv[2]))
