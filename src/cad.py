"""DXF-uitvoer (AutoCAD 2018-formaat) in SIRGAS 2000 / UTM 24S, eenheid meter."""
import math
import os

import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment

import annotatie as Ann
import haven as H

TXT = 30.0  # teksthoogte in m voor ankerpuntcoördinaten in modelspace
TEMPLATE = os.path.join(H.ROOT, "Referentie", "NHL_template_onderdelen.dxf")
STIJL = "NLCS-ISO"


def arceerkleur(laag):
    """(ACI, RGB) voor de arcering van een laag: dezelfde kleur als op de PDF-bladen (plot niet zwart)."""
    aci, hexkleur, _, _ = H.LAYERS[laag]
    if laag == "HV-RESERVE":
        hexkleur = "#6c757d"
    h = hexkleur.lstrip("#")
    return aci, (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rings(g):
    if g.geom_type == "Polygon":
        return [list(g.exterior.coords)] + [list(r.coords) for r in g.interiors]
    if g.geom_type == "MultiPolygon":
        return [r for p in g.geoms for r in _rings(p)]
    return []


_UIT = [".", {}]


def write_dxf(d, path, coast):
    _UIT[0], _UIT[1] = os.path.dirname(path) or ".", {}
    doc = ezdxf.new("R2018", setup=True)
    _template(doc)
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

    # render van Porto Central als gerefereerde overtrek-ondergrond (laag HV-REFERENTIE, standaard uit)
    if d.info.get("render_affine"):
        import shutil
        A = d.info["render_affine"]
        w_px, h_px = H.RENDER_SIZE
        src = os.path.join(H.ROOT, "Referentie", H.RENDER_FILE)
        dst = os.path.join(os.path.dirname(path), "Ondergrond", H.RENDER_FILE)
        shutil.copyfile(src, dst)
        with open(dst[:-4] + ".pgw", "w") as f:  # world file (A, D, B, E, C, F) voor Map 3D / QGIS
            f.write(f"{A[0]}\n{A[2]}\n{A[1]}\n{A[3]}\n{A[4] + 0.5 * A[0] + 0.5 * A[1]}\n{A[5] + 0.5 * A[2] + 0.5 * A[3]}\n")
        lay = doc.layers.add("HV-REFERENTIE", color=8)
        lay.description = "Porto Central render, overgetrokken voor het DO"
        lay.off()
        rdef = doc.add_image_def(filename=".\\Ondergrond\\" + H.RENDER_FILE, size_in_pixel=(w_px, h_px))
        ins = (A[1] * h_px + A[4], A[3] * h_px + A[5])  # pixel (0, hoogte) = linksonder
        msp.add_image(rdef, insert=ins, size_in_units=(w_px * H.RENDER_S, h_px * H.RENDER_S),
                      rotation=d.info["render_draaiing_graden"], dxfattribs={"layer": "HV-REFERENTIE"})

    style = {"dashed": "DASHED", "dotted": "DOT", "dashdot": "DASHDOT"}
    from shapely.geometry import box as sbox
    beeld = sbox(*[H.IMG_BOUNDS[i] for i in (0, 1, 2, 3)])
    for it in d.items:
        g, lay = it["geom"], it["layer"]
        if lay == "HV-ANKERPUNT":
            continue          # ankerpunten alleen in de maatstaat (DO-04)
        if lay == "HV-DIEPTELIJN":
            g = g.intersection(beeld)   # afknippen op de luchtfoto
            if g.is_empty:
                continue
            for part in getattr(g, "geoms", [g]):
                if part.geom_type == "LineString":
                    msp.add_lwpolyline(list(part.coords), dxfattribs={"layer": lay})
            continue
        at = {"layer": lay}
        if it.get("style"):
            at["linetype"] = style[it["style"]]
        if g.geom_type in ("Polygon", "MultiPolygon"):
            for r in _rings(g):
                msp.add_lwpolyline(r, close=True, dxfattribs=at)
            if H.LAYERS[lay][2] and lay not in ("HV-BAGGER",):
                hatch = msp.add_hatch(color=H.LAYERS[lay][0], dxfattribs={"layer": lay})
                aci, rgb = arceerkleur(lay)
                if lay == "HV-RESERVE":
                    hatch.set_pattern_fill("ANSI31", color=aci, scale=40.0)
                else:
                    hatch.set_solid_fill(color=aci, rgb=rgb)   # let op: set_solid_fill() zet anders kleur 7
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

    # teksten en maatvoering: dezelfde plaatsing als op de PDF-bladen, per blad op een eigen laag
    _teksten_model(doc, msp, d)
    if d.code == "DO":
        toets_lagen(doc, msp, d)

    # coördinatenraster 1 km
    for x in range(286000, 318001, 1000):
        msp.add_line((x, 7634000), (x, 7664000), dxfattribs={"layer": "HV-RASTER"})
    for y in range(7634000, 7664001, 1000):
        msp.add_line((286000, y), (318000, y), dxfattribs={"layer": "HV-RASTER"})
    doc.layers.get("HV-RASTER").off()

    _layout(doc, d, "02", "Havenindeling", d.center, d.scale)
    for blad, naam, center, scale in d.detail_views:
        _layout(doc, d, blad, naam, center, scale)
    if "Layout1" in doc.layouts.names() and len(doc.layouts) > 2:
        doc.layouts.delete("Layout1")
    doc.set_modelspace_vport(height=7000, center=H.P(-200, -100))
    _ongebruikte_lagen_weg(doc)
    doc.saveas(path)


def _ongebruikte_lagen_weg(doc):
    """Template-lagen die niet gebruikt worden verwijderen (houdt de lagenlijst overzichtelijk)."""
    gebruikt = {"0", "Defpoints"}
    for lay in doc.layouts:
        for e in lay:
            gebruikt.add(e.dxf.get("layer", "0"))
            for a in getattr(e, "attribs", []):
                gebruikt.add(a.dxf.get("layer", "0"))
    for b in doc.blocks:
        for e in b:
            gebruikt.add(e.dxf.get("layer", "0"))
    gebruikt |= set(H.LAYERS)
    for l in list(doc.layers):
        if l.dxf.name not in gebruikt and not l.dxf.name.startswith(("HV-", "X-XX-AL-T")):
            doc.layers.remove(l.dxf.name)


TOETS_KLEUR = {"OPENING": 6, "WAND": 30, "LIGPLAATS": 4}
TOETS_UITLEG = (
    "Invoer golftoets (src/toets_dxf.py). Verschuif deze lijnen mee als je dammen, kades of ligplaatsen aanpast. "
    "OPENING-1/2/3 = havenmond, ingang hoofdbekken, ingang insteek (tussen de wanden, van zee naar binnen). "
    "WAND-<VH|HB|INS>-<KADE|OPEN|TALUD> = reflecterende wand in voorhaven/hoofdbekken/insteek; "
    "Cr kademuur 0,9, open kade op palen 0,45, stortsteen/talud 0,4. "
    "LIGPLAATS-<CONTAINERS|GRAAN|RORO|LNG> = hartlijn van het afgemeerde schip.")


def toets_lagen(doc, msp, d):
    """Invoerlijnen voor de golftoets in modelspace (lagen HV-TOETS-*), zodat de toets op een aangepaste DXF kan."""
    import golven
    m = golven.model_uit_ontwerp(d)

    def laag(naam, soort):
        if naam not in doc.layers:
            doc.layers.add(naam, color=TOETS_KLEUR[soort]).description = TOETS_UITLEG
        return naam

    for nr, (opening, (p1, p2)) in enumerate(zip(("MOND", "HOOFDBEKKEN", "INSTEEK"), m["openingen"]), 1):
        msp.add_line(p1, p2, dxfattribs={"layer": laag(f"HV-TOETS-OPENING-{nr}-{opening}", "OPENING")})
    type_van = {v: k for k, v in golven.WANDTYPE.items()}
    for regio, ws in m["wanden"].items():
        for p1, p2, cr in ws:
            msp.add_line(p1, p2, dxfattribs={"layer": laag(f"HV-TOETS-WAND-{regio}-{type_van[cr]}", "WAND")})
    for lp in m["ligplaatsen"]:
        if lp.get("variant"):
            continue
        for a, b in lp["lijnen"]:
            msp.add_line(a, b, dxfattribs={"layer": laag(f"HV-TOETS-LIGPLAATS-{lp['soort'].upper()}", "LIGPLAATS")})


def _template(doc):
    """Blokken uit Template_NHL_Stenden_v1.dwt (layout A1_841x594): tekenblad, titelblok, wijzigingsblok,
    onderschrift en overzichtskader; tekststijlen NLCS-ISO en BS."""
    from ezdxf.addons import Importer
    src = ezdxf.readfile(TEMPLATE)
    imp = Importer(src, doc)
    imp.import_blocks(["SAL-TEKENBLAD_A1-SO", "TITELBLOK_NHL", "WIJZIGINGSBLOK_NHL", "SAL-VERWIJZING_ONDERSCHRIFT-SO",
                       "NHL_OVERZICHT"])
    imp.import_tables("styles", ["NLCS-ISO", "BS"])
    imp.finalize()
    std = doc.styles.get("Standard").dxf.handle
    for _, ml in doc.mleader_styles:
        ml.dxf.text_style_handle = std
    for naam, kleur in (("X-XX-AL-T18", 7), ("X-XX-AL-T25", 7), ("X-XX-AL-T35", 7), ("X-XX-AL-VERWIJZING-S", 7),
                        ("X-XX-AL-TEKENBLAD-S", 7), ("X-XX-AL-TEKENBLAD_TITELBLOK-G", 7), ("X-XX-AL-TEKENBLAD_VIEWPORT-G", 7),
                        ("X-XX-AL-TEKENBLAD_VIEWPORT_OVERZICHT-G", 7), ("X-XX-AL-TEKENBLAD_LEGENDA-S", 7),
                        ("X-XX-AL-TEKENBLAD_SCHAALBALK-S", 7), ("X-XX-AL-ORIENTATIE-G", 7), ("X-XX-AL-LOGO", 7)):
        if naam not in doc.layers:
            doc.layers.add(naam, color=kleur)
    for naam in ("X-XX-AL-TEKENBLAD_VIEWPORT-G", "X-XX-AL-TEKENBLAD_VIEWPORT_OVERZICHT-G"):
        doc.layers.get(naam).dxf.plot = 0   # viewportranden niet plotten


def _tekstlaag(doc, blad):
    naam = f"HV-TEKST-{blad}"
    if naam not in doc.layers:
        doc.layers.add(naam, color=7).description = f"Teksten en maatvoering voor blad {blad} (geplaatst zonder overlap)"
    return naam


def _teksten_model(doc, msp, d):
    """Teksten, verwijslijnen en maatvoering uit annotatie.voor_ontwerp() in modelspace (wereldcoördinaten)."""
    ann = getattr(d, "ann", None) or Ann.voor_ontwerp(d)
    for blad, a in ann.items():
        if blad != "02":
            continue          # detailteksten staan in de layout van het detailblad (paperspace)
        lay = _tekstlaag(doc, blad)
        pl, f = a["plaatser"], a["scale"] / 1000.0
        for m in a["maat"]:
            P = [pl.w(*q) for q in (m["a"], m["A"], m["b"], m["B"])]
            n, sg = m["n"], m["sg"]
            for p0, p1 in ((P[0], P[1]), (P[2], P[3])):
                e = (p1[0] + n[0] * 1.5 * sg * f, p1[1] + n[1] * 1.5 * sg * f)
                s0 = (p0[0] + n[0] * 1.0 * sg * f, p0[1] + n[1] * 1.0 * sg * f)
                msp.add_line(s0, e, dxfattribs={"layer": lay})
            msp.add_line(P[1], P[3], dxfattribs={"layer": lay})
            ux, uy = (P[3][0] - P[1][0]), (P[3][1] - P[1][1])
            L = math.hypot(ux, uy)
            ux, uy = ux / L, uy / L
            k = 2.0 * f
            for q, sgn in ((P[1], 1), (P[3], -1)):   # pijlpunten
                tip = q
                base = (q[0] + ux * k * sgn, q[1] + uy * k * sgn)
                msp.add_solid([tip, (base[0] - uy * k * 0.25, base[1] + ux * k * 0.25),
                               (base[0] + uy * k * 0.25, base[1] - ux * k * 0.25)], dxfattribs={"layer": lay})
            c = pl.w(*m["pos"])
            msp.add_text(m["tekst"], height=m["h"] * f, rotation=m["rot"], dxfattribs={"layer": lay, "style": STIJL}) \
                .set_placement(c, align=TextEntityAlignment.MIDDLE_CENTER)
        for p in a["labels"]:
            c = pl.w(p.x, p.y)
            if "\n" in p.tekst:
                mt = msp.add_mtext(p.tekst.replace("\n", "\\P"), dxfattribs={"layer": lay, "style": STIJL,
                                                                            "char_height": p.h * f})
                mt.set_location(c, attachment_point=5)
            else:
                msp.add_text(p.tekst, height=p.h * f, dxfattribs={"layer": lay, "style": STIJL}) \
                    .set_placement(c, align=TextEntityAlignment.MIDDLE_CENTER)
            if p.verwijs:
                q0, q1 = pl.w(*p.verwijs[0]), pl.w(*p.verwijs[1])
                msp.add_line(q0, q1, dxfattribs={"layer": lay})
                msp.add_circle(q0, 0.5 * f, dxfattribs={"layer": lay})


def _papier_teksten(lay, a):
    """Teksten, verwijslijnen en maatvoering van een blad direct in de layout (papiermm)."""
    for m in a["maat"]:
        lay.add_line(m["A"], m["B"], dxfattribs={"layer": "X-XX-AL-T18"})
        lay.add_text(m["tekst"], height=m["h"], rotation=m["rot"], dxfattribs={"layer": "X-XX-AL-T18", "style": STIJL}) \
            .set_placement(m["pos"], align=TextEntityAlignment.MIDDLE_CENTER)
    for p in a["labels"]:
        laag = f"X-XX-AL-{p.laag}"
        if "\n" in p.tekst:
            mt = lay.add_mtext(p.tekst.replace("\n", "\\P"), dxfattribs={"layer": laag, "style": STIJL, "char_height": p.h})
            mt.set_location((p.x, p.y), attachment_point=5)
        else:
            lay.add_text(p.tekst, height=p.h, dxfattribs={"layer": laag, "style": STIJL}) \
                .set_placement((p.x, p.y), align=TextEntityAlignment.MIDDLE_CENTER)
        if p.verwijs:
            lay.add_line(p.verwijs[0], p.verwijs[1], dxfattribs={"layer": "X-XX-AL-VERWIJZING-S"})
            lay.add_circle(p.verwijs[0], 0.5, dxfattribs={"layer": "X-XX-AL-VERWIJZING-S"})


def _layout(doc, d, blad, naam, center, scale):
    """A1-blad volgens layout A1_841x594 van Template_NHL_Stenden_v1.dwt."""
    import shutil
    import sheets as S
    van = 3 if d.code == "SO" else 10
    lay = doc.layouts.new(f"{d.code}-{blad} {naam} 1-{scale}".replace(",", ""))
    lay.page_setup(size=(841, 594), margins=(0, 0, 0, 0), units="mm")
    schaal = f"1:{scale:,}".replace(",", ".")
    lay.add_blockref("SAL-TEKENBLAD_A1-SO", (0, 0), dxfattribs={"layer": "X-XX-AL-TEKENBLAD-S"})
    tb = lay.add_blockref("TITELBLOK_NHL", (831, 10), dxfattribs={"layer": "X-XX-AL-TEKENBLAD_TITELBLOK-G"})
    tb.add_auto_attribs(S.titelblok_waarden(d, f"{d.code}-{blad}", naam, schaal, int(blad), van))
    wb = lay.add_blockref("WIJZIGINGSBLOK_NHL", (643, 100.6), dxfattribs={"layer": "X-XX-AL-TEKENBLAD_TITELBLOK-G"})
    wb.add_auto_attribs(S.wijziging_waarden(d))
    on = lay.add_blockref("SAL-VERWIJZING_ONDERSCHRIFT-SO", (30, 18.8), dxfattribs={"layer": "X-XX-AL-VERWIJZING-S"})
    on.add_auto_attribs({"OMSCHRIJVING": naam, "SCHAAL": f"{scale:,}".replace(",", ".")})
    ov = lay.add_blockref("NHL_OVERZICHT", (643, 125.6), dxfattribs={"layer": "X-XX-AL-TEKENBLAD_LEGENDA-S"})
    ov.add_auto_attribs({"OVERZICHT": "Overzicht", "SCHAAL": f"{Ann.OVERZICHT_SCHAAL:,}".replace(",", ".")})
    # NHL-logo als afbeelding (het logo in het template is een OLE-object)
    logo_src = os.path.join(H.ROOT, "Referentie", "nhl_logo.png")
    if os.path.exists(logo_src):
        dst = os.path.join(_UIT[0], "Ondergrond", "nhl_logo.png")
        if not os.path.exists(dst):
            shutil.copyfile(logo_src, dst)
        if "nhl_logo" not in _UIT[1]:
            _UIT[1]["nhl_logo"] = doc.add_image_def(filename=".\\Ondergrond\\nhl_logo.png", size_in_pixel=(1366, 1200))
        x, y, w, h = Ann.LOGO
        lay.add_image(_UIT[1]["nhl_logo"], insert=(x, y), size_in_units=(w, h), rotation=0,
                      dxfattribs={"layer": "X-XX-AL-LOGO"})
    # hoofdviewport en overzichtsviewport
    x, y, b, h = Ann.MAP
    bevroren = [l.dxf.name for l in doc.layers
                if (l.dxf.name.startswith("HV-TEKST-") and l.dxf.name != f"HV-TEKST-{blad}")
                or l.dxf.name in ("HV-RASTER", "HV-TEKST", "HV-MAAT", "HV-D-TEKST")
                or l.dxf.name.startswith(("HV-TOETS-", "HV-GOLF-"))
                or (blad == "02" and l.dxf.name.startswith("HV-D-"))]
    vp = lay.add_viewport(center=(x + b / 2, y + h / 2), size=(b, h), view_center_point=center,
                          view_height=h * scale / 1000, dxfattribs={"layer": "X-XX-AL-TEKENBLAD_VIEWPORT-G"})
    vp.frozen_layers = bevroren
    ox, oy, ob, oh = Ann.OVERZICHT
    oc = (d.center[0] + 6000, d.center[1] - 3000)
    vo = lay.add_viewport(center=(ox + ob / 2, oy + oh / 2), size=(ob, oh), view_center_point=oc,
                          view_height=oh * Ann.OVERZICHT_SCHAAL / 1000,
                          dxfattribs={"layer": "X-XX-AL-TEKENBLAD_VIEWPORT_OVERZICHT-G"})
    vo.frozen_layers = [l.dxf.name for l in doc.layers if l.dxf.name.startswith(("HV-TEKST", "HV-D-", "HV-TOETS-", "HV-GOLF-",
                                                                                  "HV-DIEPTELIJN", "HV-RASTER"))]
    f = 1000 / Ann.OVERZICHT_SCHAAL     # uitsnede van dit blad als rode rechthoek in het overzicht
    bw, bh = b * scale / 1000, h * scale / 1000
    px = lambda X, Y: (ox + ob / 2 + (X - oc[0]) * f, oy + oh / 2 + (Y - oc[1]) * f)
    hoek = [px(center[0] - bw / 2, center[1] - bh / 2), px(center[0] + bw / 2, center[1] - bh / 2),
            px(center[0] + bw / 2, center[1] + bh / 2), px(center[0] - bw / 2, center[1] + bh / 2)]
    lay.add_lwpolyline(hoek, close=True, dxfattribs={"layer": "X-XX-AL-TEKENBLAD_LEGENDA-S", "color": 1})
    # teksten van detailbladen in de layout zelf
    a = getattr(d, "ann", {}).get(blad)
    if a is not None and blad != "02":
        _papier_teksten(lay, a)
    # noordpijl en schaalstok
    nb = Ann.noordvak(Ann.MAP).bounds
    cx, cy = (nb[0] + nb[2]) / 2, nb[1] + 8
    lay.add_lwpolyline([(cx, cy + 18), (cx + 5, cy), (cx, cy + 4), (cx - 5, cy)], close=True,
                       dxfattribs={"layer": "X-XX-AL-ORIENTATIE-G"})
    lay.add_solid([(cx, cy + 18), (cx + 5, cy), (cx - 5, cy), (cx, cy + 4)], dxfattribs={"layer": "X-XX-AL-ORIENTATIE-G"})
    lay.add_text("N", height=5, dxfattribs={"layer": "X-XX-AL-ORIENTATIE-G", "style": STIJL}) \
        .set_placement((cx, cy + 19.5), align=TextEntityAlignment.BOTTOM_CENTER)
    sb = Ann.schaalvak(Ann.MAP).bounds
    bar_m = 1000 if scale >= 10000 else 500
    blen = bar_m / scale * 1000
    bx, by = sb[2] - 6 - blen, sb[1] + 8
    for i in range(5):
        pts = [(bx + i * blen / 5, by), (bx + (i + 1) * blen / 5, by), (bx + (i + 1) * blen / 5, by + 2), (bx + i * blen / 5, by + 2)]
        lay.add_lwpolyline(pts, close=True, dxfattribs={"layer": "X-XX-AL-TEKENBLAD_SCHAALBALK-S"})
        if i % 2 == 0:
            lay.add_solid([pts[0], pts[1], pts[3], pts[2]], dxfattribs={"layer": "X-XX-AL-TEKENBLAD_SCHAALBALK-S"})
    for t, qx, qy, al in (("0", bx, by + 3, TextEntityAlignment.BOTTOM_CENTER),
                          (f"{bar_m:,} m".replace(",", "."), bx + blen, by + 3, TextEntityAlignment.BOTTOM_CENTER)):
        lay.add_text(t, height=1.8, dxfattribs={"layer": "X-XX-AL-T18", "style": STIJL}).set_placement((qx, qy), align=al)
    # legenda en algemene gegevens
    lx, ly, lb, lh = Ann.LEGENDA
    yy = ly + lh - 2
    lay.add_text("LEGENDA", height=3.5, dxfattribs={"layer": "X-XX-AL-T35", "style": STIJL}) \
        .set_placement((lx + 2, yy), align=TextEntityAlignment.TOP_LEFT)
    yy -= 9
    used = {i["layer"] for i in d.items if blad != "02" or not i["layer"].startswith("HV-D-")}
    for name, (aci, _, fill, desc) in H.LAYERS.items():
        if name not in used or name in ("HV-ONDERGROND", "HV-TEKST", "HV-RASTER", "HV-MAAT", "HV-GEUL-AS", "HV-ANKERPUNT"):
            continue
        box_ = [(lx + 3, yy), (lx + 15, yy), (lx + 15, yy - 4), (lx + 3, yy - 4)]
        lay.add_lwpolyline(box_, close=True, dxfattribs={"color": aci, "layer": "X-XX-AL-TEKENBLAD_LEGENDA-S"})
        if fill:
            hh = lay.add_hatch(color=aci, dxfattribs={"layer": "X-XX-AL-TEKENBLAD_LEGENDA-S"})
            hh.set_solid_fill(color=aci, rgb=arceerkleur(name)[1])
            hh.paths.add_polyline_path(box_)
        lay.add_text(desc, height=1.8, dxfattribs={"layer": "X-XX-AL-TEKENBLAD_LEGENDA-S", "style": STIJL}) \
            .set_placement((lx + 18, yy - 2), align=TextEntityAlignment.MIDDLE_LEFT)
        yy -= 5.6
    for i, t in enumerate(["Algemene gegevens",
                           "Stelsel: SIRGAS 2000 / UTM zone 24S (EPSG:31984), eenheid m",
                           "Hoogte: m t.o.v. MLWS (voorlopig; MLWS = MSL - 0,7 m)",
                           "Luchtfoto: Copernicus Sentinel-2 L2A, 03-07-2026 (Ondergrond/)",
                           "Bathymetrie: GEBCO 2026 + Copernicus DEM; geen peiling"]):
        lay.add_text(t, height=1.8, dxfattribs={"layer": "X-XX-AL-T18", "style": STIJL}) \
            .set_placement((lx + 2, 279 - i * 3.8), align=TextEntityAlignment.TOP_LEFT)


