"""DXF-uitvoer (AutoCAD 2018-formaat) in SIRGAS 2000 / UTM 24S, eenheid meter."""
import math
import os

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment

import haven as H

TXT = 30.0  # teksthoogte in m (= 3 mm op 1:10.000)


def _rings(g):
    if g.geom_type == "Polygon":
        return [list(g.exterior.coords)] + [list(r.coords) for r in g.interiors]
    if g.geom_type == "MultiPolygon":
        return [r for p in g.geoms for r in _rings(p)]
    return []


def write_dxf(d, path, coast):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.M
    doc.header["$INSUNITS"] = 6
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LTSCALE"] = 10.0
    for name, (aci, _, _, desc) in H.LAYERS.items():
        lay = doc.layers.add(name, color=aci)
        lay.description = desc
    doc.layers.get("HV-ONDERGROND").lock()
    msp = doc.modelspace()

    # ondergrond als gerefereerd rasterbeeld (relatief pad naast de DXF)
    w, s, e, n = H.IMG_BOUNDS
    img_def = doc.add_image_def(filename=".\\Ondergrond\\" + H.IMG, size_in_pixel=(3400, 3400))
    msp.add_image(img_def, insert=(w, s), size_in_units=(e - w, n - s), rotation=0,
                  dxfattribs={"layer": "HV-ONDERGROND"})
    msp.add_lwpolyline(list(coast.coords), dxfattribs={"layer": "HV-KUSTLIJN"})

    style = {"dashed": "DASHED", "dotted": "DOT", "dashdot": "DASHDOT"}
    for it in d.items:
        g, lay = it["geom"], it["layer"]
        at = {"layer": lay}
        if it.get("style"):
            at["linetype"] = style[it["style"]]
        if g.geom_type in ("Polygon", "MultiPolygon"):
            for r in _rings(g):
                msp.add_lwpolyline(r, close=True, dxfattribs=at)
            if H.LAYERS[lay][2] and lay not in ("HV-BAGGER",):
                hatch = msp.add_hatch(color=H.LAYERS[lay][0], dxfattribs={"layer": lay})
                hatch.set_pattern_fill("ANSI31", scale=40.0) if lay == "HV-RESERVE" else hatch.set_solid_fill()
                if lay != "HV-RESERVE":
                    hatch.transparency = 0.6
                for i, r in enumerate(_rings(g)):
                    hatch.paths.add_polyline_path(r[:-1], is_closed=True, flags=1 if i == 0 else 0)
        elif g.geom_type == "LineString":
            msp.add_lwpolyline(list(g.coords), dxfattribs=at)
        elif g.geom_type == "Point":
            msp.add_circle((g.x, g.y), 25, dxfattribs=at)
            msp.add_line((g.x - 40, g.y), (g.x + 40, g.y), dxfattribs=at)
            msp.add_line((g.x, g.y - 40), (g.x, g.y + 40), dxfattribs=at)
        if it["label"]:
            c = g.representative_point() if g.geom_type != "LineString" else g.interpolate(0.5, normalized=True)
            ang = 0.0
            if g.geom_type == "LineString":
                (x0, y0), (x1, y1) = g.coords[0], g.coords[-1]
                ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
                if ang > 90 or ang < -90:
                    ang += 180
            if g.geom_type == "Point":
                c = type(g)(g.x + 50, g.y + 50)
            msp.add_text(it["label"], height=TXT, rotation=ang, dxfattribs={"layer": "HV-TEKST"}) \
                .set_placement((c.x, c.y), align=TextEntityAlignment.MIDDLE_CENTER if g.geom_type != "Point" else TextEntityAlignment.BOTTOM_LEFT)

    # maatvoering als echte DIMENSION-entiteiten
    ds = doc.dimstyles.new("HV_10000")
    ds.dxf.dimtxt = 25
    ds.dxf.dimasz = 25
    ds.dxf.dimexe = 10
    ds.dxf.dimexo = 10
    ds.dxf.dimgap = 8
    ds.dxf.dimdec = 0
    ds.dxf.dimtad = 1
    for p1, p2, off, text in d.dims:
        dim = msp.add_aligned_dim(p1=p1, p2=p2, distance=off, dimstyle="HV_10000", text=text,
                                  dxfattribs={"layer": "HV-MAAT"})
        dim.render()

    # ankerpunten met coördinaat
    for k, a in d.anchor.items():
        msp.add_text(f"{k} E {a['E']:.1f}  N {a['N']:.1f}", height=20, dxfattribs={"layer": "HV-ANKERPUNT"}) \
            .set_placement((a["E"] + 50, a["N"] - 40), align=TextEntityAlignment.TOP_LEFT)

    # coördinatenraster 1 km
    for x in range(286000, 318001, 1000):
        msp.add_line((x, 7634000), (x, 7664000), dxfattribs={"layer": "HV-RASTER"})
    for y in range(7634000, 7664001, 1000):
        msp.add_line((286000, y), (318000, y), dxfattribs={"layer": "HV-RASTER"})
    doc.layers.get("HV-RASTER").off()

    _layout(doc, d)
    doc.set_modelspace_vport(height=7000, center=H.P(-200, -100))
    doc.saveas(path)


def _layout(doc, d):
    """Papieren A1-blad 1:10.000 met viewport, kader, titelblok en legenda."""
    lay = doc.layouts.new(f"{d.code}-02 A1 1-10000")
    lay.page_setup(size=(841, 594), margins=(0, 0, 0, 0), units="mm")
    cx, cy = H.P(-250, -150)
    lay.add_viewport(center=(325, 297), size=(620, 574), view_center_point=(cx, cy), view_height=5740)
    lay.add_lwpolyline([(10, 10), (831, 10), (831, 584), (10, 584)], close=True)
    lay.add_lwpolyline([(640, 10), (640, 584)])
    y = 570
    title = "SCHETSONTWERP (SO)" if d.code == "SO" else "DEFINITIEF ONTWERP (DO)"
    for t, h in [("Havenontwerp Groep 1 - Atelier De Haven A", 6), (title, 8),
                 (f"Blad {d.code}-02  Havenindeling  |  versie {'1.0' if d.code == 'SO' else '2.0'}  |  22-10-2026", 4),
                 ("Schaal 1:10.000 (A1)  |  noordpijl = grid-noord (verschil met ware noord 0,70 gr)", 3.5),
                 ("Stelsel: SIRGAS 2000 / UTM zone 24S, EPSG:31984, eenheid m", 3.5),
                 ("Hoogte/diepte: m t.o.v. MLWS (voorlopig; koppeling MLWS-DHN nog te verifiëren)", 3.5),
                 ("Kaartbron: Copernicus Sentinel-2 L2A, opname 03-07-2026, 10 m", 3.5),
                 ("Online ondergrond toevoegen: GEOMAPIMAGE (Map Aerial)", 3.5)]:
        lay.add_text(t, height=h).set_placement((648, y), align=TextEntityAlignment.TOP_LEFT)
        y -= h + 5
    y -= 6
    lay.add_text("LEGENDA", height=5).set_placement((648, y), align=TextEntityAlignment.TOP_LEFT)
    y -= 11
    for name, (aci, _, fill, desc) in H.LAYERS.items():
        if name in ("HV-ONDERGROND", "HV-TEKST", "HV-RASTER", "HV-MAAT"):
            continue
        lay.add_lwpolyline([(648, y), (662, y), (662, y - 6), (648, y - 6)], close=True, dxfattribs={"color": aci})
        if fill:
            h = lay.add_hatch(color=aci)
            h.paths.add_polyline_path([(648, y), (662, y), (662, y - 6), (648, y - 6)])
        lay.add_text(desc, height=3.2).set_placement((666, y - 3), align=TextEntityAlignment.MIDDLE_LEFT)
        y -= 9
    # noordpijl
    lay.add_lwpolyline([(600, 540), (606, 520), (600, 525), (594, 520)], close=True)
    lay.add_text("N", height=8).set_placement((600, 545), align=TextEntityAlignment.BOTTOM_CENTER)
    # schaalstok 0-1000 m = 100 mm
    for i in range(5):
        lay.add_lwpolyline([(30 + i * 20, 25), (50 + i * 20, 25), (50 + i * 20, 29), (30 + i * 20, 29)], close=True)
    lay.add_text("0", height=3).set_placement((30, 31), align=TextEntityAlignment.BOTTOM_CENTER)
    lay.add_text("1.000 m", height=3).set_placement((130, 31), align=TextEntityAlignment.BOTTOM_CENTER)
