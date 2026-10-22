"""PDF-bladen A1 (841 x 594 mm) met luchtfoto-ondergrond, raster, legenda en titelblok."""
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyArrow, Patch, Polygon as MPoly, Rectangle
from matplotlib.lines import Line2D
from PIL import Image
from shapely.geometry import LineString, Point

import annotatie as A
import haven as H
from labels import HOOGTE

PW, PH = 841.0, 594.0
MAP = A.MAP                      # kaartvenster binnen het A1-kader van het NHL-template (x, y, b, h in mm)
PANEL_X = 647.0                  # rechterkolom (boven titelblok en wijzigingsblok)
KOLOM_ONDER = 178.0              # onderkant vrije ruimte in de rechterkolom
TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Referentie",
                        "NHL_template_onderdelen.dxf")
TXT = "#111111"
_BLAD = {"nr": 0, "van": 0}
HALO = [pe.withStroke(linewidth=2.4, foreground="white")]
HALO_W = [pe.withStroke(linewidth=2.0, foreground="white")]
DATE = "22-10-2026"
_IMG = None


def nl(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def img():
    global _IMG
    if _IMG is None:
        a = np.asarray(Image.open(os.path.join(H.OND, H.IMG))).astype(float) / 255.0
        a = np.clip(a * 1.55, 0, 1) ** 0.9
        _IMG = a
    return _IMG


def fig_new():
    f = plt.figure(figsize=(PW / 25.4, PH / 25.4))
    bg = f.add_axes([0, 0, 1, 1])
    bg.set_xlim(0, PW)
    bg.set_ylim(0, PH)
    bg.axis("off")
    return f, bg


def top_axes(f):
    """Bovenste laag in papiermillimeters voor teksten, maatvoering, noordpijl en schaalstok."""
    if not hasattr(f, "_top"):
        t = f.add_axes([0, 0, 1, 1], zorder=30)
        t.set_xlim(0, PW)
        t.set_ylim(0, PH)
        t.axis("off")
        t.patch.set_alpha(0)
        f._top = t
    return f._top


def fs_pt(h):
    """Lettergrootte (pt) bij hoofdletterhoogte h (mm)."""
    return h / 0.72 * 72 / 25.4


def ax_rect(ax):
    b = ax.get_position().bounds
    return (b[0] * PW, b[1] * PH, b[2] * PW, b[3] * PH)


def ax_view(ax):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    r = ax_rect(ax)
    return ((x0 + x1) / 2, (y0 + y1) / 2), (x1 - x0) / r[2] * 1000.0


def map_axes(f, rect_mm, center, scale):
    x, y, w, h = rect_mm
    ax = f.add_axes([x / PW, y / PH, w / PW, h / PH])
    sx, sy = w * scale / 1000.0, h * scale / 1000.0
    ax.set_xlim(center[0] - sx / 2, center[0] + sx / 2)
    ax.set_ylim(center[1] - sy / 2, center[1] + sy / 2)
    ax.set_aspect("equal")
    W, S, E, N = H.IMG_BOUNDS
    x0, x1 = center[0] - sx / 2 - 200, center[0] + sx / 2 + 200
    y0, y1 = center[1] - sy / 2 - 200, center[1] + sy / 2 + 200
    c0, c1 = max(0, int((x0 - W) // 10)), min(3400, int((x1 - W) // 10) + 1)
    r0, r1 = max(0, int((N - y1) // 10)), min(3400, int((N - y0) // 10) + 1)
    if c1 > c0 and r1 > r0:
        ax.imshow(img()[r0:r1, c0:c1], extent=(W + c0 * 10, W + c1 * 10, N - r1 * 10, N - r0 * 10),
                  interpolation="bilinear", zorder=0)
    ax.add_patch(Rectangle((W, S), E - W, N - S, color="white", alpha=0.28, zorder=0.5))   # rustiger ondergrond
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.6)
    return ax


def grid(ax, step, fs=None):
    """Coördinatenraster; waarden alleen langs de linker- en bovenrand (horizontaal, buiten de kaartinhoud)."""
    f = ax.figure
    top = top_axes(f)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    rx, ry, rb, rh = ax_rect(ax)
    k = fs_pt(HOOGTE["T18"])
    nv = A.noordvak((rx, ry, rb, rh))
    for x in np.arange(math.ceil(x0 / step) * step, x1, step):
        ax.axvline(x, color="white", lw=0.4, alpha=0.7, zorder=1)
        px = rx + (x - x0) / (x1 - x0) * rb
        if px < rx + 14 or px > rx + rb - 34:
            continue
        top.text(px, ry + rh - 1.5, f"{nl(x)}", fontsize=k, ha="center", va="top", color=TXT, path_effects=HALO)
    for y in np.arange(math.ceil(y0 / step) * step, y1, step):
        ax.axhline(y, color="white", lw=0.4, alpha=0.7, zorder=1)
        py = ry + (y - y0) / (y1 - y0) * rh
        if py < ry + 8 or py > ry + rh - 8:
            continue
        top.text(rx + 1.5, py, f"{nl(y)}", fontsize=k, ha="left", va="center", rotation=90, color=TXT,
                 path_effects=HALO)


def north_scale(ax, scale, bar_m):
    """Noordpijl rechtsboven en schaalstok rechtsonder in het kaartvenster (papiercoördinaten)."""
    top = top_axes(ax.figure)
    rect = ax_rect(ax)
    nb = A.noordvak(rect).bounds
    cx, cy = (nb[0] + nb[2]) / 2, nb[1] + 8
    L = 18.0
    top.add_patch(MPoly([(cx, cy + L), (cx + 5, cy), (cx, cy + 4), (cx - 5, cy)], closed=True, fc=TXT, ec=TXT, lw=0.6))
    top.text(cx, cy + L + 1.5, "N", ha="center", va="bottom", fontsize=fs_pt(5.0), weight="bold", color=TXT,
             path_effects=HALO)
    top.text(cx, cy - 1.5, "grid-noord", ha="center", va="top", fontsize=fs_pt(1.8), color=TXT, path_effects=HALO)
    sb = A.schaalvak(rect).bounds
    blen = bar_m / scale * 1000.0
    bx, by = sb[2] - 6 - blen, sb[1] + 8
    top.add_patch(Rectangle((bx - 4, sb[1] + 1), blen + 8, sb[3] - sb[1] - 2, fc="white", alpha=0.9, ec="none"))
    for i in range(5):
        top.add_patch(Rectangle((bx + i * blen / 5, by), blen / 5, 2.0, fc=TXT if i % 2 == 0 else "white", ec=TXT, lw=0.5))
    k = fs_pt(HOOGTE["T18"])
    top.text(bx, by + 3.2, "0", ha="center", va="bottom", fontsize=k, color=TXT)
    top.text(bx + blen, by + 3.2, f"{nl(bar_m)} m", ha="center", va="bottom", fontsize=k, color=TXT)
    top.text(bx + blen / 2, by - 1.6, f"schaal 1:{nl(scale)} (A1)", ha="center", va="top", fontsize=k, color=TXT)


def poly_xy(g):
    out = []
    if g.geom_type == "Polygon":
        out.append(np.array(g.exterior.coords))
    elif g.geom_type == "MultiPolygon":
        for p in g.geoms:
            out.append(np.array(p.exterior.coords))
    return out


def draw_design(ax, d, labels=True, phase=None, fs=6.5, anchors=True, dims=True, detail=False):
    """Tekent alleen de geometrie; teksten en maatvoering volgen via annoteer()/teken_ann()."""
    order = ["HV-DIEPTELIJN", "HV-VOORHAVEN", "HV-BAGGER", "HV-RESERVE", "HV-CONTAINER", "HV-GRAAN", "HV-RORO", "HV-HAVENDIENST",
             "HV-CENTRALE", "HV-LNG", "HV-D-VERKEER", "HV-D-PARKEER", "HV-D-STACK", "HV-D-REEFER", "HV-D-LEEG", "HV-D-OPSLAG",
             "HV-D-INSTALLATIE", "HV-D-GEBOUW", "HV-GEUL", "HV-GOLFBREKER", "HV-SCHIP", "HV-DRAAIKOM", "HV-KADE",
             "HV-D-KRAAN", "HV-WEG", "HV-SPOOR", "HV-LEIDING", "HV-VEILIGHEID", "HV-FASEGRENS", "HV-GEUL-AS", "HV-SLEEPBOOT",
             "HV-ANKERPUNT"]
    ls_map = {"dashed": (0, (5, 3)), "dotted": (0, (1, 2)), "dashdot": (0, (8, 3, 2, 3))}
    for z, lay in enumerate(order):
        aci, col, fill, _ = H.LAYERS[lay]
        for it in d.items:
            if it["layer"] != lay:
                continue
            g = it["geom"]
            future = phase is not None and it["phase"] > phase
            if lay == "HV-ANKERPUNT":
                if anchors:
                    ax.plot(g.x, g.y, marker="+", ms=7, mew=1.2, color="#d00000", zorder=40)
                continue
            if lay == "HV-DIEPTELIJN":
                xy = np.array(g.coords)
                ax.plot(xy[:, 0], xy[:, 1], color=col, lw=0.6, alpha=0.8, zorder=1.5)
                continue
            if not detail and lay.startswith("HV-D-"):
                continue
            lsty = ls_map.get(it.get("style"), "-")
            if g.geom_type in ("Polygon", "MultiPolygon"):
                for xy in poly_xy(g):
                    if lay == "HV-BAGGER" and it.get("style") == "dashed" and not future:
                        ax.add_patch(MPoly(xy, closed=True, fc=col, alpha=0.5, ec="none", zorder=2 + z))
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec="white", lw=0.7, ls=(0, (4, 3)), zorder=2 + z))
                        continue
                    if future or it.get("style") == "dashed":
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=0.9, ls=(0, (4, 3)), zorder=2 + z))
                        continue
                    if lay == "HV-RESERVE":
                        ax.add_patch(MPoly(xy, closed=True, fc=col, alpha=fill, ec="none", zorder=2 + z))
                        ax.add_patch(MPoly(xy, closed=True, fc="none", ec="#6c757d", lw=0.5, hatch="//", zorder=2 + z))
                    elif lay == "HV-DRAAIKOM":
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=1.4, ls=(0, (6, 3)), zorder=2 + z))
                    elif lay == "HV-GEUL":
                        ax.add_patch(MPoly(xy, closed=True, fc=col, alpha=0.18, ec="none", zorder=2 + z))
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=0.9, ls=(0, (6, 2)), zorder=2 + z))
                    elif fill:
                        ax.add_patch(MPoly(xy, closed=True, fc=col, alpha=fill * 0.85, ec=col, lw=0.8, ls=lsty, zorder=2 + z))
                    else:
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=0.8, ls=lsty, zorder=2 + z))
            elif g.geom_type == "LineString":
                xy = np.array(g.coords)
                lw = {"HV-KADE": 2.0, "HV-WEG": 1.6, "HV-SPOOR": 1.1, "HV-FASEGRENS": 1.2, "HV-GEUL-AS": 0.5,
                      "HV-D-KRAAN": 0.7, "HV-D-INSTALLATIE": 0.9, "HV-VEILIGHEID": 1.1}.get(lay, 0.9)
                if lay == "HV-SPOOR" and detail is False and it.get("dlabel"):
                    lw = 0.6
                if lay == "HV-SPOOR":
                    ax.plot(xy[:, 0], xy[:, 1], color="white", lw=2.2, zorder=2 + z, alpha=0.0 if future else 1)
                    ax.plot(xy[:, 0], xy[:, 1], color="black", lw=1.1, ls=(0, (3, 3)), zorder=2 + z, alpha=0.4 if future else 1)
                    continue
                if lay == "HV-GEUL-AS":
                    lsty = (0, (10, 3, 2, 3))
                if lay == "HV-FASEGRENS":
                    lsty = (0, (6, 2))
                ax.plot(xy[:, 0], xy[:, 1], color=col, lw=lw, ls=(0, (4, 3)) if future else lsty, zorder=2 + z,
                        alpha=0.6 if future else 1)


def teken_ann(f, ann):
    """Maatvoering en teksten (papiermm) uit annoteer() op het blad zetten."""
    top = top_axes(f)
    for m in ann["maat"]:
        a, b, Aa, Bb, n, sg = m["a"], m["b"], m["A"], m["B"], m["n"], m["sg"]
        for p, q in ((a, Aa), (b, Bb)):
            e = (q[0] + n[0] * 1.5 * sg, q[1] + n[1] * 1.5 * sg)
            top.plot([p[0] + n[0] * 1.0 * sg, e[0]], [p[1] + n[1] * 1.0 * sg, e[1]], color=TXT, lw=0.45)
        top.annotate("", xy=Aa, xytext=Bb, arrowprops=dict(arrowstyle="<|-|>", color=TXT, lw=0.6, mutation_scale=6))
        top.text(m["pos"][0], m["pos"][1], m["tekst"], fontsize=fs_pt(m["h"]), rotation=m["rot"], rotation_mode="anchor",
                 ha="center", va="center", color=TXT, path_effects=HALO)
    for p in ann["labels"]:
        if p.verwijs:
            (ax0, ay0), (ax1, ay1) = p.verwijs
            top.plot([ax0, ax1], [ay0, ay1], color=TXT, lw=0.45)
            top.plot([ax0], [ay0], marker="o", ms=1.6, color=TXT)
        top.text(p.x, p.y, p.tekst, fontsize=fs_pt(p.h), ha="center", va="center", color=TXT,
                 weight="bold" if p.laag in ("T35", "T50") else None, path_effects=HALO, linespacing=1.2)


def dim(ax, p1, p2, off, text, fs=6.5):
    """Vervallen: maatvoering loopt via annotatie.maatlijn() en teken_ann()."""
    return None


def legend(bg, y_top, d, fs=7.2, detail=False):
    bg.text(PANEL_X + 2, y_top, "LEGENDA", fontsize=9, weight="bold", va="top")
    y = y_top - 7
    skip = {"HV-ONDERGROND", "HV-TEKST", "HV-RASTER", "HV-MAAT", "HV-GEUL-AS"}
    if d.code == "SO":
        skip |= {"HV-SLEEPBOOT", "HV-CONFLICT"}
    else:
        skip |= {"HV-CONFLICT"}
    used = {i["layer"] for i in d.items if detail or not i["layer"].startswith("HV-D-")} | {"HV-KUSTLIJN", "HV-HAVENMOND",
                                                                                            "HV-ZOEKGEBIED"}
    for name, (aci, col, fill, desc) in H.LAYERS.items():
        if name in skip or name not in used:
            continue
        x = PANEL_X + 3
        if name in ("HV-KADE", "HV-WEG", "HV-LEIDING", "HV-FASEGRENS", "HV-KUSTLIJN", "HV-ZOEKGEBIED", "HV-VEILIGHEID",
                    "HV-DIEPTELIJN"):
            ls = {"HV-LEIDING": (0, (5, 3)), "HV-FASEGRENS": (0, (6, 2)), "HV-ZOEKGEBIED": (0, (6, 3)),
                  "HV-VEILIGHEID": (0, (5, 3))}.get(name, "-")
            bg.add_line(Line2D([x, x + 12], [y - 2, y - 2], color=col if name != "HV-WEG" else "#888", lw=2, ls=ls))
        elif name == "HV-SPOOR":
            bg.add_line(Line2D([x, x + 12], [y - 2, y - 2], color="black", lw=1.4, ls=(0, (3, 3))))
        elif name in ("HV-ANKERPUNT",):
            bg.plot(x + 6, y - 2, marker="+", color="red", ms=8, mew=1.5)
        elif name in ("HV-DRAAIKOM", "HV-HAVENMOND", "HV-SLEEPBOOT"):
            bg.add_patch(Rectangle((x, y - 4), 12, 4, fill=False, ec="#c9a400", lw=1.4, ls=(0, (3, 2))))
        elif name == "HV-RESERVE":
            bg.add_patch(Rectangle((x, y - 4), 12, 4, fc="#dee2e6", ec="#6c757d", hatch="//", lw=0.6))
        elif name == "HV-GEUL":
            bg.add_patch(Rectangle((x, y - 4), 12, 4, fc=col, alpha=0.35, ec="#0096c7", lw=1, ls=(0, (4, 2))))
        else:
            bg.add_patch(Rectangle((x, y - 4), 12, 4, fc=col, alpha=max(fill or 0.0, 0.5), ec="black", lw=0.4))
        bg.text(x + 15, y - 2, desc, fontsize=fs, va="center")
        y -= 5.6
    return y


VERSIES = {
    "DO": [("01", "v5.0: vorm Porto Central-render, alleen functies uit de opdracht"),
           ("02", "v6.1: terminals uitgewerkt (DO-06 t/m DO-08), overslagproces"),
           ("03", "v7.0: golftoets, dieptezones, bodemmodel GEBCO, LNG-veiligheidszones"),
           ("04", "v8.0: geul met bocht, zwaaiplaats 2 x LOA, golftoets met reflectie"),
           ("05", "v8.1: NHL-template, teksten zonder overlap, rustiger tekenbeeld")],
    "SO": [("01", "v4.0: schetsontwerp op de Porto Central-render met bespreekpunten"),
           ("02", "v4.1: NHL-template, teksten zonder overlap, rustiger tekenbeeld")],
}


def titelblok_waarden(d, blad, naam, schaal, nr, van):
    import textwrap
    regels = textwrap.wrap(f"{blad} {naam}", 33) or [blad]
    status = "Schetsontwerp (SO)" if d.code == "SO" else "Definitief ontwerp (DO)"
    sit2 = " ".join(regels[1:]) if len(regels) > 1 else status
    return {"OPDRACHTGEVER": "NHL Stenden", "PROJECTNAAM1": "Havenontwerp Porto Central",
            "PROJECTNAAM2": "Presidente Kennedy (ES), Brazilië", "SITUATIE1": regels[0],
            "SITUATIE2": sit2[:33],
            "SCHAAL": schaal, "STATUS": d.code, "FORMAAT": "A1", "PROJECTKNR": "Groep 1",
            "TEKNR": f"HAVEN-{blad}", "BLADNR": f"{nr} van {van}", "VERSIE": d.version, "GETEKEND": "Groep 1",
            "GECONTROLEERD": "-", "VRIJGAVE": "-", "STATUS_GR": ""}


def wijziging_waarden(d):
    w = {}
    for i, (_, t) in enumerate(VERSIES[d.code], 1):
        w[f"WIJZIGINGEN{i}"] = t
        w[f"DATUM{i}"] = DATE
    for i in range(len(VERSIES[d.code]) + 1, 8):
        w[f"WIJZIGINGEN{i}"] = ""
        w[f"DATUM{i}"] = ""
    return w


_TPL = None


def template_doc():
    global _TPL
    if _TPL is None:
        import ezdxf
        _TPL = ezdxf.readfile(TEMPLATE)
    return _TPL


def title_block(bg, d, blad, naam, schaal, extra=None):
    """A1-kader, titelblok en wijzigingsblok uit het NHL-template + algemene gegevens in de rechterkolom."""
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    _BLAD["nr"] += 1
    doc = template_doc()
    msp = doc.modelspace()
    for e in list(msp):
        msp.delete_entity(e)
    kader = msp.add_blockref("SAL-TEKENBLAD_A1-SO", (0, 0))
    tb = msp.add_blockref("TITELBLOK_BUREAUSCHMIDT", (831, 10))
    tb.add_auto_attribs(titelblok_waarden(d, blad, naam, schaal, _BLAD["nr"], _BLAD["van"]))
    wb = msp.add_blockref("WIJZIGINGSBLOK_BUREAUSCHMIDT", (643, 95.8))
    wb.add_auto_attribs(wijziging_waarden(d))
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK)
    Frontend(RenderContext(doc), MatplotlibBackend(bg, adjust_figure=False), config=cfg).draw_entities([kader, tb, wb])
    bg.set_xlim(0, PW)
    bg.set_ylim(0, PH)
    bg.set_aspect("auto")
    bg.axis("off")
    rows = [
        "**Algemene gegevens",
        "Stelsel: SIRGAS 2000 / UTM zone 24S (EPSG:31984), eenheid m",
        "Hoogte: m t.o.v. MLWS (voorlopig; MLWS = MSL - 0,7 m)",
        "Luchtfoto: Copernicus Sentinel-2 L2A, 03-07-2026, 10 m",
        "Bathymetrie: GEBCO 2026 + Copernicus DEM; geen peiling",
        f"Atelier De Haven A, NHL Stenden | {DATE} | schaal {schaal}",
    ] + [f"{k}: {v}" for k, v in (extra or [])]
    text_block(bg, 137.0 + 4.0 * len(rows) + 3, rows, fs=fs_pt(1.8), lh=4.0)
    return 140.0


def text_block(bg, y, lines, fs=6.8, lh=4.2, title=None, x=None):
    x = PANEL_X + 2 if x is None else x
    if title:
        bg.text(x, y, title, fontsize=9, weight="bold", va="top")
        y -= 6.5
    for ln in lines:
        bold = ln.startswith("**")
        bg.text(x, y, ln.strip("*"), fontsize=fs, va="top", weight="bold" if bold else None)
        y -= lh
    return y


# --------------------------------------------------------------------------------------
# Bladen
# --------------------------------------------------------------------------------------
def sheet_overview(pdf, d, coast, geo):
    f, bg = fig_new()
    center = (302800.0, 7648200.0)
    ax = map_axes(f, MAP, center, 50000)
    grid(ax, 2000)
    # zoekgebied: kuststrook tussen de twee bronpunten
    pts = list(geo.values())[:2]
    eu, ev = H.EU, H.EV
    def off(p, u):
        return (p["E"] + u * eu[0], p["N"] + u * eu[1])
    zone = [off(pts[0], -4000), off(pts[0], 12000), off(pts[1], 12000), off(pts[1], -4000)]
    ax.add_patch(MPoly(zone, closed=True, fill=False, ec="#ff4fd8", lw=1.8, ls=(0, (6, 3)), zorder=5))
    from shapely.geometry import Point as SP, Polygon as SPoly
    extra = [("Zoekgebied locatie B (indicatief)", SPoly(zone).exterior, "T25", 3)]
    for name, p in list(geo.items())[:2]:
        ax.plot(p["E"], p["N"], "o", ms=7, mfc="none", mec="#ff4fd8", mew=1.6, zorder=40)
        extra.append((f"{name}\nE {nl(p['E'], 1)}  N {nl(p['N'], 1)}", SP(p["E"], p["N"]), "T18", 2))
    xy = np.array(coast.coords)
    ax.plot(xy[:, 0], xy[:, 1], color="#00e5ff", lw=0.8, zorder=6)
    draw_design(ax, d, anchors=False)
    for k, nm in (("A1", "A1 kustpunt"), ("A3", "A3 havenmond"), ("A5", "A5 einde geul")):
        a_ = d.anchor[k]
        ax.plot(a_["E"], a_["N"], marker="+", ms=7, mew=1.2, color="#d00000", zorder=40)
        extra.append((nm, SP(a_["E"], a_["N"]), "T18", 4))
    for (x, y, t) in [(296000, 7646300, "kustbebouwing"), (295800, 7652600, "Porto Central-terrein"),
                      (293800, 7645000, "rivier en wetland (vermijden)")]:
        extra.append((t, SP(x, y), "T18", 5))
    extra.append(("Haven (DO)" if d.code == "DO" else "Haven (SO)", SP(*d.center), "T25", 1))
    teken_ann(f, A.annoteer(d, center, 50000, MAP, "overzicht", extra=extra, dims=False))
    north_scale(ax, 50000, 5000)
    legend_y = legend(bg, PH - 14, d, fs=6.6)
    a1 = d.anchor["A1"]
    gs = geo["_gshhs"]
    ga = geo["_afstand"]
    lines = [
        "**Havenligging (vastgesteld)",
        "Porto Central, Presidente Kennedy - ES, 29350-000",
        f"Havenas haaks op de kust: azimut {H.AZ_U:.0f} gr (kust {geo['_kust_azimut_graden']:.1f} gr).",
        f"A1 kustpunt: E {nl(a1['E'], 1)}  N {nl(a1['N'], 1)}",
        f"   = {a1['lat']:.6f}, {a1['lon']:.6f} (WGS84)",
        "Havenas door het bouwterrein fase 1 aan het strand",
        "(lichte rechthoek op de luchtfoto 03-07-2026);",
        "bekkens landinwaarts op het kale Porto Central-terrein.",
        "**Georeferentiecontrole",
        f"GSHHS-kust vs. S2-waterlijn: gem. {nl(gs['gemiddeld_m'], 0)} m, sd {nl(gs['std_m'], 0)} m",
        f"   ({len(gs['rijen'])} profielen, N 7.642-7.656 km)",
        f"Bekende afstand bronpunten: {nl(ga['geodetisch_m'], 1)} m geodetisch,",
        f"   {nl(ga['grid_m'], 1)} m in grid (k = {ga['schaalfactor']:.5f})",
        f"Noordrichting: convergentie {ga['meridiaanconvergentie_graden']:.2f} gr",
    ]
    text_block(bg, legend_y - 3, lines, fs=6.6, lh=3.9)
    title_block(bg, d, f"{d.code}-01", "Overzicht zoekgebied en havenligging", "1:50.000")
    pdf.savefig(f)
    plt.close(f)


def sheet_layout(pdf, d, phase_note=None, markup=None, blad="02", naam="Havenindeling"):
    f, bg = fig_new()
    center = d.center or H.P(-400, 50)
    ax = map_axes(f, MAP, center, d.scale)
    grid(ax, 1000)
    draw_design(ax, d)
    north_scale(ax, d.scale, 1000)
    ann = d.ann["02"] if not markup else None
    if markup:
        from shapely.geometry import box as sbox
        res = []
        top = top_axes(f)
        for nr, (u, v, r, txt) in enumerate(markup, 1):
            x, y = d.P(u, v)
            ax.add_patch(plt.Circle((x, y), r, fill=False, ec="red", lw=2.0, zorder=60))
            px, py = MAP[0] + MAP[2] / 2 + (x + r * 0.75 - center[0]) / d.scale * 1000, \
                MAP[1] + MAP[3] / 2 + (y + r * 0.75 - center[1]) / d.scale * 1000
            top.text(px, py, str(nr), fontsize=fs_pt(3.5), weight="bold", color="white", ha="center", va="center",
                     bbox=dict(boxstyle="circle", fc="red", ec="white"))
            res.append(sbox(px - 5, py - 5, px + 5, py + 5))
        ann = A.annoteer(d, center, d.scale, MAP, "plan", gereserveerd=res)
    teken_ann(f, ann)
    y = legend(bg, PH - 14, d, fs=6.6)
    m = d.m
    if markup:
        lines = ["**Bespreekpunten SO (zie rode markering)"] + [f"{i}. {t[3]}" for i, t in enumerate(markup, 1)]
        y = text_block(bg, y - 3, lines, fs=6.1, lh=3.6)
    else:
        lines = [
            "**Hoofdmaten (gemeten in tekening)",
            f"Geul bodembreedte 220 m, bodem -18,20 m MLWS (voorlopig)",
            f"Geul buiten de mond: {nl(m['geullengte_buiten_mond_m'])} m (voorlopig)",
            f"Havenmond vrij tussen dammen: {nl(m['havenmond_vrij_m'])} m",
            f"Draaikom D 720 m; vrij van schepen {nl(m['draaikom_vrij_van_schepen_m'])} m",
            f"Stopweg mond-draaikom {nl(m['stopweg_mond_draaikom_m'])} m = {nl(m['stopweg_in_LOA'], 1)} LOA",
            f"Containerkade {nl(m['containerkade_m'][1])} / {nl(m['containerkade_m'][2])} / {nl(m['containerkade_m'][3])} m",
            f"Containerterrein {nl(m['container_ha'][1], 1)} / {nl(m['container_ha'][2], 1)} / {nl(m['container_ha'][3], 1)} ha",
            f"Graan {nl(m['graan_ha'], 1)} ha, RoRo {nl(m['roro_ha'], 1)} ha, kades 300 m",
            f"LNG-zone {nl(m['lng_zone_ha'], 1)} ha; centrale (reservering) {nl(m['centrale_ha'], 1)} ha",
            f"Vrije breedte binnenbekken {nl(m['vrije_breedte_binnenbekken_m'])} m",
        ]
        if d.code == "DO":
            g = d.info.get("golftoets", {})
            ok = all(v["voldoet"] for k, v in g.items() if not k.startswith("Variant"))
            lines = [
                "**Hoofdmaten (gemeten in tekening)",
                f"Geul 220 m breed (bocht 260 m), {nl(m['geullengte_buiten_mond_m'], 0)} m buiten de mond:",
                "   2,5 km recht, bocht R 3.400 m naar 145 gr, dan recht tot",
                "   natuurlijk -18,2 m (GEBCO); rechtdoor was 35 km, zie DO-10",
                "Dieptezones (diepgang + 3,7 m): containers/graan/geul -18,20;",
                "   LNG-vaarweg en -ligplaats -16,20; RoRo -13,70 m MLWS",
                f"Havenmond vrij {nl(m['havenmond_vrij_m'])} m; stopweg {nl(m['stopweg_mond_draaikom_m'])} m = {nl(m['stopweg_in_LOA'], 1)} LOA",
                f"Draaikom voorhaven D 720 m, vrij van schepen {nl(m['draaikom_vrij_van_schepen_m'])} m",
                f"Zwaaiplaats binnenhaven D {nl(m['zwaaiplaats_D_m'])} m (2 x LOA container),",
                f"   {nl(m['zwaaiplaats_vrij_van_schepen_m'])} m vrij van schepen, {nl(m['zwaaiplaats_vrij_van_land_m'])} m van de oever",
                "Containerkade westzijde vinger 6 (in de insteek, beschut):",
                f"   {nl(m['containerkade_m'][1])} / {nl(m['containerkade_m'][2])} / {nl(m['containerkade_m'][3])} m; terrein "
                f"{nl(m['container_ha'][1], 1)} / {nl(m['container_ha'][2], 1)} / {nl(m['container_ha'][3], 1)} ha",
                f"Graan {nl(m['graan_ha'], 1)} ha, RoRo {nl(m['roro_ha'], 1)} ha, kades 300 m",
                f"LNG-zone {nl(m['lng_zone_ha'], 1)} ha; steiger achter de zuidelijke dam;",
                "   tanks zuidelijk: 250 m-zone 227 m buiten containerterrein",
                "Graan- en havendienstkade: open kade op palen (golfdempend)",
                "   veiligheidszone 250 m, nautische controlezone 500 m",
                f"Golftoets: {'alle ligplaatsen voldoen' if ok else 'niet alle ligplaatsen voldoen'} (zie DO-09)",
            ]
        if phase_note:
            lines += phase_note
        y = text_block(bg, y - 3, lines, fs=6.3, lh=3.8)
    title_block(bg, d, f"{d.code}-{blad}", naam, f"1:{nl(d.scale)}")
    pdf.savefig(f)
    plt.close(f)


def sheet_detail(pdf, d, blad, naam, center, scale, lines):
    f, bg = fig_new()
    ax = map_axes(f, MAP, center, scale)
    grid(ax, 500)
    draw_design(ax, d, anchors=False, detail=True)
    north_scale(ax, scale, 500)
    teken_ann(f, d.ann[blad])
    y = legend(bg, PH - 14, d, fs=6.2, detail=True)
    text_block(bg, y - 3, lines, fs=6.6, lh=4.0)
    title_block(bg, d, f"{d.code}-{blad}", naam, f"1:{nl(scale)}")
    pdf.savefig(f)
    plt.close(f)


def _hs(d, prefix):
    return next(v["hs"] for k, v in d.info.get("golftoets", {}).items() if k.startswith(prefix))


def detail_lines(d, blad):
    t = d.info.get("detail", {})
    o = t.get("overslag", {})
    if blad == "06":
        sl = t["teu_grondslots_per_fase"]
        return ["**Overslagketen containers",
                "schip -> STS-kraan -> terminaltrekker -> RTG-stack",
                f"Kade aan de westzijde van vinger 6 (insteek): Hs {nl(_hs(d, 'Containers'), 2)} m",
                "   -> vrachtauto (gate) of trein (RMG-railterminal)",
                f"Kade: 5 STS x 30 box/u = {nl(o['kade_boxen_per_uur_per_schip'])} box/u per schip; apron 60 m",
                f"STS-kranen F1/F2/F3: {t['sts_per_fase'][1]} / {t['sts_per_fase'][2]} / {t['sts_per_fase'][3]} (6 / 12 / 20)",
                f"Stack: TEU-grondslots {nl(sl[1])} / {nl(sl[2])} / {nl(sl[3])}",
                "   benodigd 12.133 / 20.222 / 40.444 (28 m2/slot)",
                "**Landzijde 2045 (aannamen: 70% weg, 30% spoor)",
                f"Piekuur {nl(o['truckbezoeken_piekuur'])} truckbezoeken (10% van piekdag)",
                f"   -> {o['gate_rijstroken_per_richting']} rijstroken per richting nodig; getekend",
                f"   {o['gate_rijstroken_per_richting'] + 1} in + {o['gate_rijstroken_per_richting'] + 1} uit (60 trucks/u/rijstrook)",
                f"Pre-gate buffer 30 min = {o['buffer_plaatsen']} trucks = {nl(o['buffer_ha'], 1)} ha;",
                f"   getekend {nl(t['pregate_ha'], 1)} ha aan de ringweg",
                f"Spoor: {nl(o['treinen_per_dag'], 1)} treinen/piekdag; 5 sporen x 1.300 m =",
                f"   10 treinposities x 4 = {nl(o['treincapaciteit_per_dag'])} treinen/dag (6 u per trein)",
                "Reefer- en legecontainervakken aan de landzijde"]
    if blad == "07":
        return ["**Graan (export): weg/spoor -> stortput -> silo ->",
                "   transportband -> shiploader -> schip",
                f"Piekdag oogst {nl(o['graan_piekdag_t'])} t (15% van jaar in een maand)",
                f"   50% per vrachtauto = {nl(o['graan_trucks_per_dag'])} trucks/dag;",
                f"   wachtplaats 4 u = {o['graan_wachtplaatsen']} trucks (getekend {o['graan_wachtplaatsen'] + 4})",
                f"   50% per spoor = {nl(o['graan_treinen_per_week'], 1)} treinen/week van {nl(o['graan_trein_lengte_m'])} m",
                "   -> 2 opstelsporen x 1.400 m langs de noordweg",
                f"Silo's {nl(t['graan_silo_ton'])} t (piek 154.100 t); 2 shiploaders",
                "Graankade als open kade op palen boven een golfdempend",
                f"   talud (Cr 0,45): Hs {nl(_hs(d, 'Graan'), 2)} m <= 1,0 m",
                "**RoRo (import): schip -> ramp -> opstelzone -> PDI",
                f"   ligplaats 400 m dieper in de insteek: Hs {nl(_hs(d, 'RoRo'), 2)} m <= 0,3 m",
                "   -> parkeervak -> laadstraat autotransporters",
                f"Lossen 6.500 auto's / 150 per u = {nl(o['roro_lostijd_uur'], 1)} u; ca. {o['roro_chauffeurs']} chauffeurs",
                f"Parkeervakken ca. {nl(t['roro_auto_capaciteit'])} auto's (piek 7.479)",
                f"Autotransporters (8 auto's): ca. {nl(o['roro_transporters_per_dag'])} per piekdag",
                "Havendienst: VTS, loodsen, 3 sleepboten, brandweer"]
    km = nl(t.get("lng_leiding_m", 0) / 1000, 1)
    return ["**LNG: schip -> laadarmen -> cryogene leiding",
            "   -> tanks -> hervergassing -> centrale / gasnet",
            f"Lossen 156.600 m3 / 10.000 m3/u + 8 u = {nl(o['lng_lostijd_uur'], 1)} u per call",
            f"Steiger achter de zuidelijke dam (Hs {nl(_hs(d, 'LNG'), 2)} m <= 1,0 m);",
            "   ligplaats -16,20 m MLWS (diepgang 12,5 + 3,7 m)",
            f"3 laadarmen; losleiding + dampretour ca. {km} km",
            "   (tanks zuidelijk in de zone: 250 m-zone blijft",
            "   227 m buiten het containerterrein)",
            "Tanks 3 x 180.000 m3 in tankput, ruimte 4e tank",
            "**Veiligheid (indicatief, QRA volgt)",
            "250 m veiligheidszone rond schip/steiger en tanks;",
            "   500 m nautische controlezone; geen andere",
            "   schepen of gebouwen binnen de 250 m-zones",
            f"Send-out gemiddeld {nl(o['lng_sendout_m3_per_uur'])} m3 LNG/u; hervergassing 4 x 33%",
            "Fakkel, BOG-compressor, meetstation, controlekamer",
            f"Centrale: 4 STEG-eenheden ca. 565 MW = {nl(t['centrale_eenheden_mw'])} MW",
            "   (rekenvoorbeeld 2.256 MW), hoogspanningsstation,",
            "   koelwaterpompen, gasontvangst"]


def sheet_phases(pdf, d):
    f, bg = fig_new()
    center = d.center or H.P(-400, 50)
    panels = [(20, 297, 311, 287), (332, 297, 311, 287), (20, 10, 311, 287)]
    for (x, y, w, h), ph, jr in zip(panels, (1, 2, 3), (2025, 2035, 2045)):
        ax = map_axes(f, (x, y, w, h), center, 2 * d.scale)
        draw_design(ax, d, phase=ph, anchors=False)
        ax.text(0.02, 0.97, f"Fase {ph}  -  {jr}", transform=ax.transAxes, fontsize=13, weight="bold", va="top",
                color=TXT, path_effects=HALO)
        ax.text(0.02, 0.90, ["2 containerligplaatsen, 800 m kade, 72 ha", "3 containerligplaatsen, 1.200 m kade, 108 ha",
                             "4 containerligplaatsen, 1.600 m kade, 144 ha"][ph - 1],
                transform=ax.transAxes, fontsize=8, va="top", color=TXT, path_effects=HALO)
        north_scale(ax, 2 * d.scale, 2000)
    rows = [("Onderdeel", "Fase 1 - 2025", "Fase 2 - 2035", "Fase 3 - 2045"),
            ("Containerligplaatsen", "2 (C1-C2)", "3 (+C3)", "4 (+C4)"),
            ("Containerkade", "800 m", "1.200 m", "1.600 m"),
            ("Containerterrein", "72 ha", "108 ha", "144 ha"),
            ("Rekenvraag terrein", "40,8 ha", "67,9 ha", "135,9 ha"),
            ("Kranen per schip / totaal", "3 / 6", "4 / 12", "5 / 20"),
            ("Kadebezetting", "60,0%", "51,3%", "63,1%"),
            ("Bekkens gebaggerd", "hoofd-, insteek-, containerb. N", "+ containerbekken midden", "+ containerbekken zuid"),
            ("Graan / RoRo", "1 lp, 30 ha elk", "equipment +", "pieken toetsen"),
            ("LNG", "steiger + 3 tanks", "doorzet 6 mln m3", "8 mln m3; N-1 besluit"),
            ("Centrale", "eindcapaciteit", "-", "-"),
            ("Golfbrekers + geul", "volledig", "onderhoud", "onderhoud")]
    x0, y0 = 340, 280
    cw = [66, 52, 52, 52]
    bg.text(x0, y0 + 2, "Fasering (rekenboek Containers / Overige terminals)", fontsize=10, weight="bold")
    for r, row in enumerate(rows):
        xx = x0
        for c, txt in enumerate(row):
            bg.add_patch(Rectangle((xx, y0 - 9 * (r + 1)), cw[c], 9, fill=r == 0, fc="#e9ecef", ec="black", lw=0.4))
            bg.text(xx + 1.5, y0 - 9 * (r + 1) + 4.5, txt, fontsize=7, va="center", weight="bold" if r == 0 else None)
            xx += cw[c]
    text_block(bg, y0 - 9 * len(rows) - 8, [
        "De containerkade ligt aan de westzijde van vinger 6 in het insteekbekken (beschut, DO-09)",
        "en groeit zuidwaarts; baggeren en kadebouw voor F2/F3 gebeuren aan het zuideinde van",
        "de insteek, achter de schepen aan C1/C2 en buiten de zwaaiplaats.",
        "Toekomstige onderdelen zijn gestippeld; alleen functies uit de opdracht zijn getekend.",
        "Golfbrekers, geul, draaikom, LNG-steiger en leidingcorridors worden in F1 op",
        "eindmaat aangelegd (latere uitbreiding is onevenredig duur, rapport par. 10).",
    ], fs=7.2, lh=4.4, x=x0)
    y = legend(bg, PH - 14, d, fs=6.6)
    title_block(bg, d, f"{d.code}-03", "Fasering 2025 - 2035 - 2045", f"1:{nl(2 * d.scale)}")
    pdf.savefig(f)
    plt.close(f)


def table(bg, x0, y0, cols, cw, rows, fs=8.2, rh=7.0, title=None):
    if title:
        bg.text(x0, y0 + 3, title, fontsize=10, weight="bold")
    for r, row in enumerate([cols] + rows):
        xx = x0
        for c, txt in enumerate(row):
            bg.add_patch(Rectangle((xx, y0 - rh * (r + 1)), cw[c], rh, fill=r == 0, fc="#e9ecef", ec="black", lw=0.35))
            bg.text(xx + 1.2, y0 - rh * (r + 1) + rh / 2, str(txt), fontsize=fs, va="center", weight="bold" if r == 0 else None)
            xx += cw[c]
    return y0 - rh * (len(rows) + 1)


def sheet_tables(pdf, d, geo):
    f, bg = fig_new()
    m = d.m
    rows = [
        ("Hoofdgeul bodembreedte", "220 m", "Nautiek D20 = 220", "rekenuitkomst"),
        ("Bodemhoogte geul/bekken", "-18,20 m MLWS", "Nautiek D25 = 18,20", "voorlopig"),
        ("Geullengte buiten mond", f"{nl(m['geullengte_buiten_mond_m'])} m", "Nautiek D31 (GEBCO 2026)", "geen peiling"),
        ("Dieptezone LNG / RoRo", "-16,20 / -13,70 m MLWS", "diepgang 12,5 / 10,0 + 3,7", "bespaart bagger"),
        ("Vrije draaikom voorhaven", "D 720 m", "Nautiek D28 = 720", "vrij getoetst"),
        ("Zwaaiplaats binnenhaven", f"D {nl(m['zwaaiplaats_D_m'])} m", "2 x LOA = 668 m", "vrij getoetst"),
        ("  afstand tot schepen/kades", f"{nl(m['draaikom_vrij_van_schepen_m'])} / {nl(m['draaikom_vrij_van_kades_dammen_m'])} m", "> 0", "voldoet"),
        ("Havenmond vrij (footprints)", f"{nl(m['havenmond_vrij_m'])} m", "Nautiek D29 = 350", "voldoet"),
        ("Stopweg mond - draaikom", f"{nl(m['stopweg_mond_draaikom_m'])} m", "5 LOA = 1.670 m", "voldoet"),
        ("Sleepbootkoppelpunt", f"{nl(m['sleepboot_buiten_mond_m'])} m buiten mond", "rapport par. 5.1", "ingetekend"),
        ("Containerkade F1/F2/F3", " / ".join(nl(m['containerkade_m'][p]) for p in (1, 2, 3)) + " m", "800/1.200/1.600", "gelijk"),
        ("Containerterrein F1/F2/F3", " / ".join(nl(m['container_ha'][p], 1) for p in (1, 2, 3)) + " ha", "72/108/144 (vraag 40,8/67,9/135,9)", "gelijk"),
        ("Graankade / terrein", f"300 m / {nl(m['graan_ha'], 1)} ha", "300 m / 30 ha (vraag 5,1)", "gelijk"),
        ("RoRo-kade / terrein", f"300 m / {nl(m['roro_ha'], 1)} ha", "300 m / 30 ha (vraag 26,9)", "gelijk"),
        ("LNG-ligplaatsenvelop", "400 m", "ca. 400 m", "dolphins indicatief"),
        ("LNG-envelop tot draaikom", f"{nl(m['lng_ligplaats_tot_draaikom_m'])} m", "> 250 m zone", "voldoet"),
        ("Schepen/gebouwen in LNG-zone", f"{len(m['vz_schepen_in_250m'])} / {len(m['vz_gebouwen_in_zones'])}", "0 (250 m)", "QRA volgt"),
        ("LNG-zone (3 tanks + optie 4e)", f"{nl(m['lng_zone_ha'], 1)} ha", "3 x 180.000 m3", "N-1 open"),
        ("Centrale + utilities", f"{nl(m['centrale_ha'], 1)} ha", "geen vast oppervlak", "reservering"),
        ("Vrije breedte binnenbekken", f"{nl(m['vrije_breedte_binnenbekken_m'])} m", ">= 220 m", "voldoet"),
        ("Havenbekken baggervak (zone 1)", f"{nl(m['havenbekken_totaal_m2'] / 1e4, 1)} ha", "Grondwerk C6", "ingevuld"),
        ("Geul buiten mond (zone 2+3)", f"{nl(m['geul_buiten_m2'] / 1e4, 1)} ha", "Grondwerk C7+C8", "split op -15 m"),
        ("Terreinophoging", f"{nl(m['terreinophoging_m2'] / 1e4, 1)} ha", "Grondwerk D21", "ingevuld"),
    ]
    gw = d.info.get("grondwerk")
    if gw:
        rows += [("Baggervolume zone 1/2/3", " / ".join(nl(gw[f'zone{z}']['volume'] / 1e6, 1) for z in (1, 2, 3)) + " mln m3",
                  "celmethode GEBCO/DEM", "indicatief"),
                 ("Besparing dieptezones", f"{nl(gw['besparing_dieptezones_m3'] / 1e6, 2)} mln m3", "t.o.v. overal -18,20", "")]
    y = table(bg, 26, PH - 24, ("Onderdeel", "Gemeten in DO-tekening", "Rekenboek", "Status"), [78, 75, 92, 58], rows,
              title="Maatstaat DO - tekening tegen rekenboek")
    an = [(k, a["naam"], nl(a["E"], 1), nl(a["N"], 1), f"{a['lat']:.6f}", f"{a['lon']:.6f}") for k, a in d.anchor.items()]
    y = table(bg, 26, y - 14, ("Punt", "Omschrijving", "E (m)", "N (m)", "Lat", "Lon"), [16, 92, 40, 44, 55, 56], an,
              title="Ontwerpankerpunten - EPSG:31984 (E/N) en WGS84 (lat/lon)")
    text_block(bg, y - 6, [
        "Geometrie overgetrokken van de Porto Central-render (Referentie/Porto_Central_render.png), pixel (x, y omlaag):",
        f"schaal {nl(d.info['render_schaal_m_per_px'], 3)} m/px, draaiing {nl(d.info['render_draaiing_graden'], 1)} gr; render (812,5; 275) = A1. "
        f"Kustfit: gemiddeld {nl(d.info['render_kustfit_gem_afwijking_m'])} m.",
        "E = a x + b y + c;  N = d x + e y + f  met a..f in Maatstaat/maatstaat.json (render_affine).",
        "Alle maten in de DXF staan direct in projectcoördinaten; er is geen lokale verschuiving meer nodig.",
    ], fs=8.4, lh=5.2, x=26)
    # georeferentie
    ga, gs = geo["_afstand"], geo["_gshhs"]
    rows = [(n, f"{p['lat']:.6f}, {p['lon']:.6f}", nl(p["E"], 1), nl(p["N"], 1), f"{nl(p['afstand_tot_waterlijn_m'])} m")
            for n, p in list(geo.items())[:2]]
    y2 = table(bg, 345, PH - 24, ("Bronpunt case", "WGS84", "E", "N", "tot waterlijn"), [78, 72, 46, 50, 46], rows,
               title="Georeferentie - bronpunten en controles")
    rows = [(nl(r["N"]), nl(r["E_s2"]), nl(r["E_gshhs"]), nl(r["dE"])) for r in gs["rijen"]]
    y2 = table(bg, 345, y2 - 12, ("N (m)", "E waterlijn S2", "E kust GSHHS", "dE (m)"), [52, 60, 60, 40], rows, rh=6.2,
               title="Kustlijncontrole: Sentinel-2 tegen onafhankelijke GSHHS-kust (full)")
    lines = [
        f"Gemiddelde dE {nl(gs['gemiddeld_m'], 1)} m, sd {nl(gs['std_m'], 1)} m: geen systematische verschuiving.",
        "GSHHS heeft een nauwkeurigheid van orde 50-100 m; de spreiding past daarbij.",
        f"Bekende afstand bronpunten: geodetisch {nl(ga['geodetisch_m'], 1)} m, grid {nl(ga['grid_m'], 1)} m,",
        f"verschil {nl(ga['verschil_m'], 2)} m = schaalfactor k {ga['schaalfactor']:.6f} (UTM, verwacht).",
        f"Noordrichting: meridiaanconvergentie {ga['meridiaanconvergentie_graden']:.2f} gr; blad is grid-noord.",
        "Bronresolutie 10 m (1 pixel). Sentinel-2 L2A wordt geleverd in WGS84/UTM 24S",
        "(EPSG:32724); verschil met SIRGAS 2000 is < 0,1 m en verwaarloosbaar.",
        "**In Civil 3D nog te doen: drie herkenningspunten tegen Map Aerial",
        "(GEOMAPIMAGE) meten en de afwijking in de maatstaat invullen.",
    ]
    text_block(bg, y2 - 6, lines, fs=8.4, lh=5.2, x=345)
    title_block(bg, d, f"{d.code}-04", "Maatstaat, ankerpunten en georeferentie", "n.v.t.")
    pdf.savefig(f)
    plt.close(f)


def so_markup(d):
    m = d.m
    pos = d.notes["markup_pos"]
    texts = [
        f"Havenmond {nl(m['havenmond_vrij_m'])} m vrij tussen dammen (350 m hart-hart gemeten)",
        f"Draaikom overlapt de containervinger ({nl(m['draaikom_overlap_land_m2'] / 1e4, 1)} ha)",
        "Geen sleepbootkoppelpunt; geul knikt 15 gr op 2,2 km buiten de mond",
        f"LNG-tanks op {nl(m['lng_tank_tot_containerterrein_m'])} m van het containerterrein",
        "Graan + RoRo op één perceel aan de noordkade; weg kruist het terrein",
        f"Containerschip 334 m moet {nl(m['bocht_hoofdbekken_insteek_graden'])} gr draaien van hoofdbekken (370 m) naar insteek: niet haalbaar",
        "Containers F1 aan het zuideinde; geen draaikom binnen voor graan/RoRo; alles in F1 baggeren",
    ]
    return [(x, y, r, t) for (x, y, r), t in zip(pos, texts)]


def masterplan_inset(bg, y_bottom, width=None, render=False):
    """Niet meer gebruikt op de plattegronden (rustiger blad); de render staat op DO-05."""
    return y_bottom


def make_pdf(d, path, coast, geo):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _BLAD["nr"] = 0
    _BLAD["van"] = 3 if d.code == "SO" else (4 + bool(d.info.get("render_affine")) + len(d.detail_views)
                                              + bool(d.info.get("golftoets")) + bool(d.info.get("grondwerk")))
    if not hasattr(d, "ann"):
        A.voor_ontwerp(d)
    with PdfPages(path) as pdf:
        sheet_overview(pdf, d, coast, geo)
        if d.code == "SO":
            sheet_layout(pdf, d, phase_note=["**Fasen (globaal)", "F1 = zuideinde containervinger, F2/F3 richting hoofdbekken (zie DO)"])
            sheet_layout(pdf, d, markup=so_markup(d), blad="03", naam="Bespreking SO - bespreekpunten")
        else:
            sheet_layout(pdf, d)
            sheet_phases(pdf, d)
            sheet_tables(pdf, d, geo)
            if d.info.get("render_affine"):
                sheet_overlay(pdf, d)
            for blad, naam, center, scale in d.detail_views:
                sheet_detail(pdf, d, blad, naam, center, scale, detail_lines(d, blad))
            if d.info.get("golftoets"):
                sheet_golf(pdf, d)
            if d.info.get("grondwerk"):
                sheet_geul(pdf, d)
        info = pdf.infodict()
        info["Title"] = f"Haven_{d.code} - Havenontwerp Groep 1"
        info["Author"] = "Groep 1 - Atelier De Haven A"
    compress_pdf(path)


def compress_pdf(path, quality=85):
    """Rasterbeelden in de PDF als JPEG opslaan (matplotlib schrijft ze verliesvrij)."""
    try:
        import pikepdf
        from pikepdf import Name, PdfImage
    except ImportError:
        return
    import io
    pdf = pikepdf.open(path, allow_overwriting_input=True)
    for page in pdf.pages:
        for name, raw in page.images.items():
            if Name.SMask in raw:
                continue
            im = PdfImage(raw).as_pil_image().convert("RGB")
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=quality, optimize=True)
            raw.write(buf.getvalue(), filter=Name.DCTDecode)
            raw.ColorSpace = Name.DeviceRGB
            raw.BitsPerComponent = 8
            for k in (Name.DecodeParms,):
                if k in raw:
                    del raw[k]
    pdf.save(path, compress_streams=True)


def sheet_overlay(pdf, d):
    """DO-05: de render van Porto Central half doorzichtig op de luchtfoto, met de DO-contouren erop."""
    from matplotlib.transforms import Affine2D
    f, bg = fig_new()
    ax = map_axes(f, MAP, d.center, d.scale)
    grid(ax, 1000)
    A = d.info["render_affine"]
    im = np.asarray(Image.open(os.path.join(H.ROOT, "Referentie", H.RENDER_FILE)).convert("RGB"))
    tr = Affine2D(np.array([[A[0], A[1], A[4]], [A[2], A[3], A[5]], [0, 0, 1]])) + ax.transData
    ax.imshow(im, extent=(0, im.shape[1], im.shape[0], 0), transform=tr, alpha=0.72, zorder=1, interpolation="bilinear")
    for it in d.items:
        g = it["geom"]
        if g.geom_type in ("Polygon", "MultiPolygon") and it["layer"] not in ("HV-SCHIP", "HV-ANKERPUNT"):
            for xy in poly_xy(g):
                ax.add_patch(MPoly(xy, closed=True, fill=False, ec=H.LAYERS[it["layer"]][1], lw=1.0, zorder=10))
        elif g.geom_type == "LineString" and it["layer"] in ("HV-KADE", "HV-GEUL-AS"):
            xy = np.array(g.coords)
            ax.plot(xy[:, 0], xy[:, 1], color="white", lw=1.0, zorder=10)
    north_scale(ax, d.scale, 1000)
    y = legend(bg, PH - 14, d, fs=6.6)
    text_block(bg, y - 3, [
        "**Controle overtrek",
        "De render is op schaal en op de echte kust gelegd:",
        f"schaal {nl(d.info['render_schaal_m_per_px'], 3)} m per pixel, draaiing {nl(d.info['render_draaiing_graden'], 1)} gr;",
        f"kustlijn render tegen waterlijn: gem. {nl(d.info['render_kustfit_gem_afwijking_m'])} m.",
        "Gekleurde lijnen = definitief ontwerp (DO).",
        "Afwijkingen van de render zijn bewust:",
        "- havenmond 350 m vrij (render ca. 640 m);",
        "- alleen functies uit de opdracht: erts, werf,",
        "  industrie en olie weggelaten;",
        "- zwaaiplaats binnenhaven D 670 m (2 x LOA);",
        "- containerkade aan de westzijde van vinger 6, in",
        "  de insteek: beschut tegen golven (DO-09);",
        "- LNG-steiger achter de zuidelijke dam, tanks",
        "  zuidelijk in de LNG-zone;",
        "- geul buigt na 2,5 km af naar 145 gr (DO-10);",
        "- maten volgen het rekenboek.",
        "In de DXF staat de render op laag HV-REFERENTIE",
        "(uit); aanzetten om zelf verder over te trekken.",
    ], fs=6.6, lh=4.0)
    title_block(bg, d, f"{d.code}-05", "Overtrek Porto Central-render op luchtfoto", f"1:{nl(d.scale)}")
    pdf.savefig(f)
    plt.close(f)


def sheet_golf(pdf, d):
    """DO-09: golfdoordringing (diffractie) voor de twee maatgevende golfrichtingen + toetstabel."""
    import golven
    f, bg = fig_new()
    g = d.info["golftoets"]
    panels = [((20, 299, 623, 285), 112.5), ((20, 10, 623, 285), 45.0)]
    levels = [0, 0.1, 0.3, 0.5, 1.0, 1.5, 2.0, 3.5]
    cmap = plt.get_cmap("RdYlGn_r")
    for rect, frm in panels:
        ax = map_axes(f, rect, d.center, 14000)
        grid(ax, 1000)
        for X, Y, kd in golven.kd_regios(d, frm, stap=30.0):
            ax.contourf(X, Y, kd * golven.HS_BUITEN, levels=levels, cmap=cmap, alpha=0.7, zorder=25, extend="max")
        draw_design(ax, d, anchors=False)
        az = math.radians(frm + 180)
        x1, y1 = ax.get_xlim()[1], ax.get_ylim()[1]
        sx = x1 - ax.get_xlim()[0]
        ax.add_patch(FancyArrow(x1 - 0.12 * sx - math.sin(az) * 700, y1 - 0.45 * (y1 - ax.get_ylim()[0]) - math.cos(az) * 700,
                                math.sin(az) * 700, math.cos(az) * 700, width=60, head_width=200, head_length=200,
                                fc="white", ec="black", zorder=60))
        ax.text(0.02, 0.96, f"Golven uit {'OZO' if frm > 100 else 'NO'} ({nl(frm, 1)} gr), Hs buiten {nl(golven.HS_BUITEN, 1)} m, T 8 s"
                f"  -  maatgevend voor {'graan, RoRo en containers' if frm > 100 else 'LNG'}",
                transform=ax.transAxes, fontsize=11, weight="bold", va="top", color=TXT, path_effects=HALO)
        north_scale(ax, 14000, 1000)
    # kleurenschaal
    y = PH - 14
    bg.text(PANEL_X + 2, y, "Hs aan de ligplaats (m) = Kd x Hs buiten", fontsize=9, weight="bold", va="top")
    y -= 9
    for i in range(len(levels) - 1):
        c = cmap((i + 0.5) / (len(levels) - 1))
        bg.add_patch(Rectangle((PANEL_X + 3 + i * 24, y - 5), 24, 5, fc=c, alpha=0.75, ec="black", lw=0.3))
        bg.text(PANEL_X + 3 + i * 24, y - 7, nl(levels[i], 1), fontsize=6.5, va="top", ha="center")
    y -= 16
    rows = []
    for naam, v in g.items():
        rows.append((naam.replace("Variant: ", "Var.: ")[:38], nl(v["kd_max"], 2), nl(v["hs"], 2), nl(v["grens"], 1),
                     "voldoet" if v["voldoet"] else "VOLDOET NIET"))
    y = table(bg, PANEL_X + 1, y, ("Ligplaats", "Kd max", "Hs (m)", "grens", "toets"), [76, 18, 18, 16, 25], rows,
              fs=6.4, rh=6.0, title="Toets per ligplaats (maatgevende richting NO-ZZO)")
    text_block(bg, y - 4, [
        "**Methode",
        "Diffractie door opeenvolgende openingen (Huygens-",
        "Kirchhoff): havenmond -> ingang hoofdbekken -> insteek,",
        "plus reflectie (1e orde, spiegelbronnen) tegen dammen,",
        "taluds en kades; energie opgeteld. Cr: verticale kade",
        "0,9; open kade op palen 0,45; stortsteen/talud 0,4.",
        "Golfrichtingen 45-157,5 gr (NO-ZZO), T 8 s, h 15 m;",
        "Hs buiten 2,5 m = bovenkant bandbreedte Deel 1.",
        "Getoetst op 3-5 punten over de hele scheepslengte.",
        "Grenzen (indicatief, PIANC/handboeken, dwarsgolven):",
        "containers 0,5 m, RoRo 0,3 m, graan 1,0 m, LNG 1,0 m.",
        "Niet meegenomen: refractie, hogere-orde reflectie,",
        "lange golven: numeriek model (SWAN/Boussinesq) volgt.",
        "**Gevolgen voor het ontwerp",
        "- containers aan de westzijde van vinger 6 (insteek);",
        "- graan- en havendienstkade als open kade op palen;",
        "- RoRo-ligplaats 400 m dieper in de insteek;",
        "- LNG-steiger op de gunstigste plek langs de dam;",
        "- graan en LNG krijgen golven vrijwel langs het schip",
        "  (gunstiger dan de getoetste dwarsgrens).",
    ], fs=6.5, lh=3.9)
    title_block(bg, d, f"{d.code}-09", "Golftoets ligplaatsen (diffractie + reflectie)", "1:14.000")
    pdf.savefig(f)
    plt.close(f)


GEUL_RECHT = 2500.0


def sheet_geul(pdf, d):
    """DO-10: bestaande bodem (GEBCO + DEM), toegangsgeul met dieptezones en lengteprofiel + grondwerk."""
    import bodem
    from matplotlib.colors import LinearSegmentedColormap
    f, bg = fig_new()
    z, tr = bodem._load()
    W, S, E, N = bodem.BBOX
    scale = 75000
    rect = (20, 300, 623, 284)
    ax = f.add_axes([rect[0] / PW, rect[1] / PH, rect[2] / PW, rect[3] / PH])
    sx, sy = rect[2] * scale / 1000, rect[3] * scale / 1000
    rw = d.notes["geul_route"]
    cx, cy = (rw[0][0] + rw[-1][0]) / 2 + 2500, (rw[0][1] + rw[-1][1]) / 2
    ax.set_xlim(cx - sx / 2, cx + sx / 2)
    ax.set_ylim(cy - sy / 2, cy + sy / 2)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor("#08306b")
    sea = LinearSegmentedColormap.from_list("zee", ["#08306b", "#2171b5", "#6baed6", "#c6dbef"])
    zs = np.ma.masked_invalid(np.where(z < 0, z, np.nan))
    im = ax.imshow(zs, extent=(W, E, S, N), cmap=sea, vmin=-25, vmax=0, zorder=0, interpolation="bilinear")
    from matplotlib.colors import ListedColormap
    zl = np.ma.masked_invalid(np.where(z >= 0, 1.0, np.nan))
    ax.imshow(zl, extent=(W, E, S, N), cmap=ListedColormap(["#d9cfae"]), zorder=0, interpolation="nearest")
    grid(ax, 5000)
    draw_design(ax, d, anchors=False)
    n = d.notes
    route = LineString(rw)
    extra = []
    var = d.info.get("geul_variant_recht")
    if var:
        xy = np.array(var["route"])
        ax.plot(xy[:, 0], xy[:, 1], color="#ff8fab", lw=1.4, ls=(0, (6, 3)), zorder=30)
        extra.append((f"afgevallen variant rechtdoor:\n{nl(var['lengte'] / 1000)} km, {nl(var['volume'] / 1e6, 1)} mln m3",
                      LineString(var["route"]), "T18", 3))
    for l, t in ((0, "havenmond"), (GEUL_RECHT, "begin bocht\nR 3.400 m"),
                 (n["geul_15"], f"natuurlijk -15 m\n({nl(n['geul_15'] / 1000, 1)} km)"),
                 (n["geul_lengte"], f"natuurlijk -18,2 m\n= geuleinde ({nl(n['geul_lengte'] / 1000, 1)} km)")):
        q = route.interpolate(l)
        p = (q.x, q.y)
        ax.plot(*p, "o", ms=5, mfc="#ffd60a", mec="black", zorder=60)
        extra.append((t, Point(*p), "T18", 2))
    ax.text(0.02, 0.96, "Bestaande bodem t.o.v. MLWS (GEBCO 2026 + Copernicus DEM) met toegangsgeul",
            transform=ax.transAxes, fontsize=11, weight="bold", va="top", color=TXT, path_effects=HALO)
    north_scale(ax, scale, 5000)
    from shapely.geometry import box as sbox
    teken_ann(f, A.annoteer(d, (cx, cy), scale, rect, "geul", extra=extra, dims=False,
                            gereserveerd=[sbox(rect[0], rect[1] + rect[3] - 16, rect[0] + 300, rect[1] + rect[3])]))
    cb = f.add_axes([400 / PW, 312 / PH, 200 / PW, 5 / PH])
    f.colorbar(im, cax=cb, orientation="horizontal").set_label("diepte t.o.v. MLWS (m)", fontsize=7)
    cb.tick_params(labelsize=6.5)
    # lengteprofiel
    pr = np.array(d.info["geulprofiel"])
    ap = f.add_axes([30 / PW, 40 / PH, 595 / PW, 230 / PH])
    km = pr[:, 0] / 1000
    ap.fill_between(km, pr[:, 1], -18.2, where=pr[:, 1] > -18.2, color="#e76f51", alpha=0.55, label="te baggeren (tot -18,20)")
    ap.plot(km, pr[:, 1], color="#08306b", lw=1.6, label="bestaande bodem (gem. over 2 km breedte)")
    ap.axhline(-18.2, color="#c1121f", lw=1.4, ls="--", label="ontwerpbodem geul -18,20 m MLWS")
    ap.axhline(-15.0, color="#6c757d", lw=0.8, ls=":")
    ap.axvline(n["geul_15"] / 1000, color="#6c757d", lw=0.8, ls=":")
    ap.axvline(n["geul_lengte"] / 1000, color="#c1121f", lw=0.8)
    ap.text(n["geul_15"] / 1000 + 0.3, -3, "zone 2 | zone 3\n(-15 m)", fontsize=8, va="top")
    ap.text(n["geul_lengte"] / 1000 + 0.3, -3, "geuleinde", fontsize=8, va="top", color="#c1121f")
    ap.set_xlim(0, 40)
    ap.set_xticks(range(0, 41, 5))
    ap.set_ylim(-25, 2)
    ap.set_xlabel("afstand vanaf havenmond langs de geulas (km)", fontsize=9)
    ap.set_ylabel("hoogte t.o.v. MLWS (m)", fontsize=9)
    ap.grid(alpha=0.3)
    ap.legend(loc="lower left", fontsize=8)
    ap.set_title("Lengteprofiel langs de geulas (met bocht), verticaal sterk overdreven", fontsize=10, loc="left")
    if var:
        pv = np.array(var["profiel"])
        ap.plot(pv[:, 0] / 1000, pv[:, 1], color="#ff8fab", lw=1.0, ls="--", label="variant rechtdoor (bestaande bodem)")
        ap.legend(loc="lower left", fontsize=8)
    # grondwerk
    gw = d.info["grondwerk"]
    rows = [(v["vak"].replace("  ", " ")[:30], nl(-v["diepte"], 2), nl(v["oppervlak"] / 1e4, 1), nl(-v["bestaande_diepte"], 1),
             nl(v["volume"] / 1e6, 2)) for v in gw["vakken"]]
    rows.append(("Totaal baggeren", "", nl(sum(v["oppervlak"] for v in gw["vakken"]) / 1e4, 1), "", nl(gw["totaal_bagger_m3"] / 1e6, 1)))
    y = table(bg, PANEL_X + 1, PH - 20, ("Vak", "bodem", "ha", "nu (gem.)", "mln m3"), [62, 18, 18, 20, 20], rows,
              fs=6.2, rh=5.8, title="Baggervolumes per vak (celmethode 30 m)")
    text_block(bg, y - 4, [
        f"Besparing door dieptezones t.o.v. overal -18,20: {nl(gw['besparing_dieptezones_m3'] / 1e6, 2)} mln m3",
        "   (LNG-vaarweg -16,20 en RoRo-ligplaats -13,70).",
        f"Terrein {nl(gw['terrein_m2'] / 1e4)} ha op +{nl(gw['maaiveld'], 1)} m MLWS: maaiveld nu gem. +{nl(gw['terrein_gem_hoogte'], 1)} m;",
        f"   afgraving {nl(gw['afgraving_m3'] / 1e6, 1)} mln m3, ophoging {nl(gw['ophoging_m3'] / 1e6, 2)} mln m3",
        f"   (zetting {nl(gw['zetting'], 1)} m). Let op: DEM = oppervlak incl.",
        "   begroeiing, werkelijk maaiveld ligt lager.",
        "**Bronnen en aannamen",
        "GEBCO 2026 (15'', ca. 450 m), Source Cooperative;",
        "Copernicus DEM GLO-30 (AWS Open Data);",
        "MLWS = MSL - 0,7 m (aanname, getijslag ca. 1,4 m).",
        "Geuleinde waar de natuurlijke bodem, gemiddeld over",
        "2 km, overal dieper is dan -18,20 m. Bij GEBCO-",
        "resolutie +-1 m onzekerheid: lengte kan enkele km",
        "verschuiven. Multibeampeiling vóór uitvoering nodig.",
        "**Tracékeuze",
        "Richtingen 94-164 gr vanaf de mond doorgerekend: naar",
        "het ZO is het veel eerder diep. Gekozen: 2,5 km recht",
        "(sleepboten, inloop mond), bocht R 3.400 m (ca. 10 LOA,",
        "verbreed tot 260 m), dan 145 gr tot natuurlijk -18,2 m.",
        f"Rechtdoor: {nl(var['lengte'] / 1000, 1)} km, {nl(var['volume'] / 1e6, 1)} mln m3; met bocht: "
        f"{nl(n['geul_lengte'] / 1000, 1)} km, {nl(d.info['geul_gekozen_volume'] / 1e6, 1)} mln m3." if var else "",
        "Haven 1 km verder in zee: bespaart ca. "
        f"{nl(d.info['verder_in_zee']['bagger_eerste_km'] / 1e6, 1)} mln m3 geul,",
        f"   kost ca. {nl(d.info['verder_in_zee']['dam_steen_per_km'] / 1e6, 2)} mln m3 extra stortsteen (2 dammen):",
        "   ongeveer kostenneutraal, daarom niet gedaan.",
    ], fs=6.3, lh=3.8)
    title_block(bg, d, f"{d.code}-10", "Toegangsgeul, bodemprofiel en grondwerk", "1:75.000")
    pdf.savefig(f)
    plt.close(f)
