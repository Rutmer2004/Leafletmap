"""LandXML 1.2 voor Civil 3D: geulas als Alignment en de ontwerpbodem als TIN-oppervlak per dieptezone
(-18,20 containers/graan/geul, -16,20 LNG-vaarweg, -13,70 RoRo; m MLWS).

In Civil 3D: Insert > Import LandXML. Daarna kan een bathymetrie-oppervlak tegen 'Ontwerpbodem_DO'
vergeleken worden (Volumes Dashboard) voor de baggervolumes.
"""
import math
from datetime import date
from xml.sax.saxutils import escape

import shapely
from shapely.geometry import LineString
from shapely.ops import unary_union

import haven as H

Z_BODEM = -18.20


def _polys(g):
    return list(g.geoms) if g.geom_type == "MultiPolygon" else [g]


def write_landxml(d, path):
    n = d.notes
    # vaarroute van geuleinde via havenmond naar de draaikom
    route = [d.P(*n["eind"]), d.P(*n["M"]), d.P(*n["T"])]
    lines, sta = [], 0.0
    for a, b in zip(route[:-1], route[1:]):
        lng = math.dist(a, b)
        lines.append(f'<Line staStart="{sta:.3f}" length="{lng:.3f}"><Start>{a[1]:.3f} {a[0]:.3f}</Start>'
                     f'<End>{b[1]:.3f} {b[0]:.3f}</End></Line>')
        sta += lng

    # één TIN-oppervlak per ontwerpdiepte (dieptezones: -18,20 / -16,20 / -13,70 m MLWS)
    zones = {}
    for i in d.items:
        if (i["layer"] == "HV-BAGGER" and i["phase"] <= 3) or i["layer"] == "HV-GEUL":
            zones.setdefault(i.get("diepte", -Z_BODEM), []).append(i["geom"])
    geteld = None
    surfaces = []
    for diepte in sorted(zones, reverse=True):
        water = unary_union(zones[diepte]).buffer(0)
        if geteld is not None:
            water = water.difference(geteld)
        geteld = water if geteld is None else unary_union([geteld, water])
        pts, idx, faces = [], {}, []

        def pid(x, y):
            k = (round(x, 3), round(y, 3))
            if k not in idx:
                pts.append(k)
                idx[k] = len(pts)
            return idx[k]

        for poly in _polys(water.simplify(0.5)):
            if poly.geom_type != "Polygon" or poly.area < 1:
                continue
            tri = shapely.constrained_delaunay_triangles(poly)
            for t in tri.geoms:
                c = list(t.exterior.coords)[:3]
                faces.append(tuple(pid(x, y) for x, y in c))
        surfaces.append((diepte, pts, faces, water.area))

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" version="1.2" '
        f'date="{date(2026, 10, 22).isoformat()}" time="12:00:00">',
        '<Units><Metric areaUnit="squareMeter" linearUnit="meter" volumeUnit="cubicMeter" temperatureUnit="celsius" '
        'pressureUnit="milliBars" angularUnit="decimal degrees" directionUnit="decimal degrees"/></Units>',
        '<CoordinateSystem name="SIRGAS 2000 / UTM zone 24S" epsgCode="31984" horizontalDatum="SIRGAS2000" '
        'verticalDatum="MLWS (voorlopig)"/>',
        f'<Project name="{escape("Havenontwerp Groep 1 - " + H.LOCATIE)}"/>',
        '<Application name="src/landxml.py" manufacturer="Groep 1"/>',
        f'<Alignments name="Geul"><Alignment name="Hoofdgeul_{d.code}" length="{sta:.3f}" staStart="0" '
        f'desc="As toegangsgeul 220 m, van geuleinde via havenmond naar draaikom"><CoordGeom>{"".join(lines)}</CoordGeom>'
        '</Alignment></Alignments>',
        '<Surfaces>',
    ]
    for diepte, pts, faces, _ in surfaces:
        z = -diepte
        out.append(f'<Surface name="Ontwerpbodem_{d.code}_{f"{z:.2f}".replace(".", "_")}" '
                   f'desc="Gebaggerde vlakken op {z:.2f} m MLWS (voorlopig)"><Definition surfType="TIN"><Pnts>')
        out += [f'<P id="{i}">{y:.3f} {x:.3f} {z:.3f}</P>' for i, (x, y) in enumerate(pts, 1)]
        out.append("</Pnts><Faces>")
        out += [f"<F>{a} {b} {c}</F>" for a, b, c in faces]
        out.append("</Faces></Definition></Surface>")
    out.append("</Surfaces></LandXML>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return dict(route_m=sta, oppervlakken={f"{-z:.2f}": dict(punten=len(p), driehoeken=len(f), oppervlak_m2=a)
                                          for z, p, f, a in surfaces})
