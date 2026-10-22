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

import haven as H

PW, PH = 841.0, 594.0
MAP = (15.0, 15.0, 620.0, 564.0)  # x, y, b, h in mm
PANEL_X = 642.0
HALO = [pe.withStroke(linewidth=2.2, foreground="black")]
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
    bg.add_patch(Rectangle((8, 8), PW - 16, PH - 16, fill=False, lw=1.2))
    bg.add_patch(Rectangle((PANEL_X - 3, 8), PW - PANEL_X - 5, PH - 16, fill=False, lw=0.8))
    return f, bg


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
    ax.imshow(img()[r0:r1, c0:c1], extent=(W + c0 * 10, W + c1 * 10, N - r1 * 10, N - r0 * 10),
              interpolation="bilinear", zorder=0)
    ax.add_patch(Rectangle((W, S), E - W, N - S, color="white", alpha=0.10, zorder=0.5))
    ax.set_xticks([])
    ax.set_yticks([])
    return ax


def grid(ax, step, fs=6):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    for x in np.arange(math.ceil(x0 / step) * step, x1, step):
        ax.axvline(x, color="white", lw=0.35, alpha=0.6, zorder=1)
        ax.text(x, y1, f"E {nl(x)}", fontsize=fs, ha="center", va="top", color="white", path_effects=HALO, zorder=20)
        ax.text(x, y0, f"E {nl(x)}", fontsize=fs, ha="center", va="bottom", color="white", path_effects=HALO, zorder=20)
    for y in np.arange(math.ceil(y0 / step) * step, y1, step):
        ax.axhline(y, color="white", lw=0.35, alpha=0.6, zorder=1)
        ax.text(x0, y, f" N {nl(y)}", fontsize=fs, ha="left", va="center", color="white", path_effects=HALO, zorder=20)
        ax.text(x1, y, f"N {nl(y)} ", fontsize=fs, ha="right", va="center", color="white", path_effects=HALO, zorder=20)


def north_scale(ax, scale, bar_m):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    sx, sy = (x1 - x0), (y1 - y0)
    # noordpijl rechtsboven
    nx, ny = x1 - 0.05 * sx, y1 - 0.12 * sy
    L = 0.06 * sy
    ax.add_patch(MPoly([(nx, ny + L), (nx + L * 0.28, ny), (nx, ny + L * 0.25), (nx - L * 0.28, ny)],
                       closed=True, fc="white", ec="black", lw=0.8, zorder=30))
    ax.text(nx, ny + L * 1.08, "N", ha="center", va="bottom", fontsize=14, weight="bold", color="white",
            path_effects=HALO, zorder=30)
    ax.text(nx, ny - L * 0.15, "grid-noord", ha="center", va="top", fontsize=6, color="white", path_effects=HALO, zorder=30)
    # schaalstok linksonder
    bx, by = x0 + 0.04 * sx, y0 + 0.035 * sy
    h = 0.008 * sy
    ax.add_patch(Rectangle((bx - 0.01 * sx, by - 2.6 * h), bar_m + 0.02 * sx, 7 * h, fc="white", alpha=0.85, zorder=29))
    for i in range(5):
        ax.add_patch(Rectangle((bx + i * bar_m / 5, by), bar_m / 5, h, fc="black" if i % 2 == 0 else "white",
                               ec="black", lw=0.6, zorder=30))
    for i, t in [(0, "0"), (5, f"{nl(bar_m)} m")]:
        ax.text(bx + i * bar_m / 5, by + 1.4 * h, t, ha="center", va="bottom", fontsize=7, zorder=31)
    ax.text(bx + bar_m / 2, by - 0.6 * h, f"schaal 1:{nl(scale)} (A1)", ha="center", va="top", fontsize=7, zorder=31)


def poly_xy(g):
    out = []
    if g.geom_type == "Polygon":
        out.append(np.array(g.exterior.coords))
    elif g.geom_type == "MultiPolygon":
        for p in g.geoms:
            out.append(np.array(p.exterior.coords))
    return out


def draw_design(ax, d, labels=True, phase=None, fs=6.5, anchors=True, dims=True, detail=False):
    order = ["HV-VOORHAVEN", "HV-BAGGER", "HV-RESERVE", "HV-CONTAINER", "HV-GRAAN", "HV-RORO", "HV-HAVENDIENST", "HV-CENTRALE",
             "HV-LNG", "HV-D-VERKEER", "HV-D-PARKEER", "HV-D-STACK", "HV-D-REEFER", "HV-D-LEEG", "HV-D-OPSLAG",
             "HV-D-INSTALLATIE", "HV-D-GEBOUW", "HV-GEUL", "HV-GOLFBREKER", "HV-SCHIP", "HV-DRAAIKOM", "HV-KADE",
             "HV-D-KRAAN", "HV-WEG", "HV-SPOOR", "HV-LEIDING", "HV-FASEGRENS", "HV-GEUL-AS", "HV-SLEEPBOOT", "HV-ANKERPUNT"]
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
                    ax.plot(g.x, g.y, marker="+", ms=9, mew=1.6, color="red", zorder=40)
                    ax.text(g.x, g.y, f" {it['label']}", color="white", fontsize=fs, va="bottom",
                            path_effects=[pe.withStroke(linewidth=2, foreground="red")], zorder=40, clip_on=True)
                continue
            lsty = ls_map.get(it.get("style"), "-")
            if g.geom_type in ("Polygon", "MultiPolygon"):
                for xy in poly_xy(g):
                    if lay == "HV-BAGGER" and it.get("style") == "dashed" and not future:
                        ax.add_patch(MPoly(xy, closed=True, fc=col, alpha=0.6, ec="none", zorder=2 + z))
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec="white", lw=0.8, ls=(0, (4, 3)), zorder=2 + z))
                        continue
                    if future or it.get("style") == "dashed":
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=1.0, ls=(0, (4, 3)), zorder=2 + z))
                        continue
                    if lay == "HV-RESERVE":
                        ax.add_patch(MPoly(xy, closed=True, fc=col, alpha=fill, ec="none", zorder=2 + z))
                        ax.add_patch(MPoly(xy, closed=True, fc="none", ec="#6c757d", lw=0.6, hatch="//", zorder=2 + z))
                    elif lay == "HV-DRAAIKOM":
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=1.6, ls=(0, (6, 3)), zorder=2 + z))
                    elif lay == "HV-GEUL":
                        ax.add_patch(MPoly(xy, closed=True, fc=col, alpha=0.18, ec="none", zorder=2 + z))
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=1.0, ls=(0, (6, 2)), zorder=2 + z))
                    elif fill:
                        ax.add_patch(MPoly(xy, closed=True, fc=col, alpha=fill, ec=col, lw=0.9, ls=lsty, zorder=2 + z))
                        if fill < 1:
                            ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=0.9, ls=lsty, zorder=2 + z))
                    else:
                        ax.add_patch(MPoly(xy, closed=True, fill=False, ec=col, lw=0.9, ls=lsty, zorder=2 + z))
            elif g.geom_type == "LineString":
                xy = np.array(g.coords)
                lw = {"HV-KADE": 2.2, "HV-WEG": 1.8, "HV-SPOOR": 1.2, "HV-FASEGRENS": 1.4, "HV-GEUL-AS": 0.6,
                      "HV-D-KRAAN": 0.7, "HV-D-INSTALLATIE": 0.9}.get(lay, 1.0)
                if lay == "HV-SPOOR" and detail is False and it.get("dlabel"):
                    lw = 0.6
                if lay == "HV-SPOOR":
                    ax.plot(xy[:, 0], xy[:, 1], color="white", lw=2.4, zorder=2 + z, alpha=0.0 if future else 1)
                    ax.plot(xy[:, 0], xy[:, 1], color="black", lw=1.2, ls=(0, (3, 3)), zorder=2 + z, alpha=0.4 if future else 1)
                    continue
                if lay == "HV-GEUL-AS":
                    lsty = (0, (10, 3, 2, 3))
                if lay == "HV-FASEGRENS":
                    lsty = (0, (6, 2))
                ax.plot(xy[:, 0], xy[:, 1], color=col, lw=lw, ls=(0, (4, 3)) if future else lsty, zorder=2 + z,
                        alpha=0.6 if future else 1)
            if detail and it.get("dlabel") and not future:
                c = g.representative_point() if g.geom_type != "LineString" else g.interpolate(0.5, normalized=True)
                ax.text(c.x, c.y, it["dlabel"], fontsize=fs * 0.9, ha="center", va="center", color="white",
                        path_effects=HALO, zorder=55, clip_on=True)
            if labels and it["label"] and lay not in ("HV-GEUL-AS",) and not future:
                c = g.representative_point() if g.geom_type != "LineString" else g.interpolate(0.5, normalized=True)
                if lay == "HV-SLEEPBOOT":
                    c = Point(g.centroid.x, g.centroid.y + 180)
                rot = 0
                if g.geom_type == "LineString":
                    (x0, y0), (x1, y1) = g.coords[0], g.coords[-1]
                    rot = math.degrees(math.atan2(y1 - y0, x1 - x0))
                    rot = rot + 180 if (rot > 90 or rot < -90) else rot
                    c = Point(c.x - 60 * math.sin(math.radians(rot)), c.y + 60 * math.cos(math.radians(rot)))
                ax.text(c.x, c.y, it["label"], fontsize=fs, ha="center", va="center", rotation=rot, color="white",
                        path_effects=HALO, zorder=50, clip_on=True)
    if dims:
        for p1, p2, off, text in d.dims:
            dim(ax, p1, p2, off, text, fs)


def dim(ax, p1, p2, off, text, fs=6.5):
    p1, p2 = np.array(p1), np.array(p2)
    t = (p2 - p1) / np.linalg.norm(p2 - p1)
    nrm = np.array([-t[1], t[0]])
    a, b = p1 + nrm * off, p2 + nrm * off
    kw = dict(color="white", lw=0.8, zorder=45)
    ax.plot([p1[0], a[0] + nrm[0] * 15 * np.sign(off)], [p1[1], a[1] + nrm[1] * 15 * np.sign(off)], **kw)
    ax.plot([p2[0], b[0] + nrm[0] * 15 * np.sign(off)], [p2[1], b[1] + nrm[1] * 15 * np.sign(off)], **kw)
    ax.annotate("", xy=a, xytext=b, arrowprops=dict(arrowstyle="<|-|>", color="white", lw=0.9, mutation_scale=7), zorder=45)
    rot = math.degrees(math.atan2(t[1], t[0]))
    rot = rot + 180 if (rot > 90 or rot < -90) else rot
    m = (a + b) / 2 + nrm * 30 * np.sign(off if off else 1)
    ax.text(m[0], m[1], text, fontsize=fs, rotation=rot, ha="center", va="center", color="#ffd60a",
            path_effects=HALO, zorder=46, clip_on=True)


def legend(bg, y_top, d, fs=7.2):
    bg.text(PANEL_X + 2, y_top, "LEGENDA", fontsize=9, weight="bold", va="top")
    y = y_top - 7
    skip = {"HV-ONDERGROND", "HV-TEKST", "HV-RASTER", "HV-MAAT", "HV-GEUL-AS"}
    if d.code == "SO":
        skip |= {"HV-SLEEPBOOT", "HV-CONFLICT"}
    else:
        skip |= {"HV-CONFLICT"}
    used = {i["layer"] for i in d.items} | {"HV-KUSTLIJN", "HV-HAVENMOND", "HV-ZOEKGEBIED"}
    for name, (aci, col, fill, desc) in H.LAYERS.items():
        if name in skip or name not in used:
            continue
        x = PANEL_X + 3
        if name in ("HV-KADE", "HV-WEG", "HV-LEIDING", "HV-FASEGRENS", "HV-KUSTLIJN", "HV-ZOEKGEBIED"):
            ls = {"HV-LEIDING": (0, (5, 3)), "HV-FASEGRENS": (0, (6, 2)), "HV-ZOEKGEBIED": (0, (6, 3))}.get(name, "-")
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


def title_block(bg, d, blad, naam, schaal, extra=None):
    x0, y0, w = PANEL_X - 3, 8, PW - PANEL_X - 5
    rows = [
        ("Project", "Havenontwerp Porto Central, Presidente Kennedy (ES) - Groep 1"),
        ("Module", "Atelier De Haven A | NHL Stenden Civiele Techniek"),
        ("Bladnaam", naam),
        ("Status", "SCHETSONTWERP (SO)" if d.code == "SO" else "DEFINITIEF ONTWERP (DO)"),
        ("Blad / versie", f"{blad}  |  versie {d.version}  |  {DATE}"),
        ("Schaal", f"{schaal} op A1 (841 x 594 mm)"),
        ("Stelsel", "SIRGAS 2000 / UTM zone 24S  EPSG:31984  eenheid m"),
        ("Hoogtedatum", "diepten in m t.o.v. MLWS, voorlopig; MLWS-DHN te verifiëren"),
        ("Kaartbron", "Copernicus Sentinel-2 L2A (ESA), 03-07-2026, 10 m"),
        ("", "tegels 24KTB/24KUB, AWS Open Data COG; geraadpleegd " + DATE),
        ("Kustlijn", "waterlijn 03-07-2026 uit NDWI (geen MLWS-lijn)"),
        ("Peildatum", "geen peiling ingelezen; bathymetrie en peildatum nog toe te voegen"),
    ]
    if extra:
        rows += extra
    h = 5.2 * len(rows) + 6
    bg.add_patch(Rectangle((x0, y0), w, h, fill=False, lw=0.8))
    y = y0 + h - 4
    for k, v in rows:
        big = k == "Status"
        bg.text(x0 + 2, y, k, fontsize=6.5, va="center", color="#555")
        bg.text(x0 + 26, y, v, fontsize=9 if big else 6.8, va="center", weight="bold" if big or k == "Bladnaam" else None,
                color=("#c1121f" if d.code == "SO" else "#1b4332") if big else "black")
        y -= 5.2
    return y0 + h


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
    tx, ty = off(pts[1], 9000)
    ax.text(tx, ty - 1200, "Zoekgebied locatie B (indicatief)\nkuststrook tussen de bronpunten,\n4 km landinwaarts tot 12 km zeewaarts",
            color="#ff4fd8", fontsize=8, ha="center", va="top", path_effects=HALO, zorder=50)
    for name, p in list(geo.items())[:2]:
        ax.plot(p["E"], p["N"], "o", ms=8, mfc="none", mec="#ff4fd8", mew=2, zorder=40)
        ax.text(p["E"] - 300, p["N"], f"{name}\n{p['lat']:.6f}, {p['lon']:.6f}\nE {nl(p['E'], 1)}  N {nl(p['N'], 1)}",
                fontsize=7, ha="right", va="center", color="white", path_effects=HALO, zorder=50)
    xy = np.array(coast.coords)
    ax.plot(xy[:, 0], xy[:, 1], color="#00e5ff", lw=0.8, zorder=6)
    draw_design(ax, d, labels=False, fs=6, dims=False)
    for k, a in d.anchor.items():
        if k in ("A1", "A3", "A4", "A5"):
            ax.text(a["E"], a["N"] - 350, f"{k} {a['naam']}", fontsize=7, color="white", ha="center", va="top",
                    path_effects=HALO, zorder=50, rotation=0, clip_on=True)
    for (x, y, t) in [(296000, 7645900, "kustbebouwing\nN ≈ 7.646.300"), (295800, 7652600, "Porto Central-terrein\nPresidente Kennedy (ES)"),
                      (293800, 7645000, "rivier + mangrove/wetland\n(vermijden)")]:
        ax.text(x, y, t, fontsize=7, color="#ffd60a", ha="right", path_effects=HALO, zorder=50)
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
    masterplan_inset(bg, 92, render=d.code == "DO")
    title_block(bg, d, f"{d.code}-01", "Overzicht zoekgebied en havenligging", "1:50.000")
    pdf.savefig(f)
    plt.close(f)


def sheet_layout(pdf, d, phase_note=None, markup=None, blad="02", naam="Havenindeling"):
    f, bg = fig_new()
    center = d.center or H.P(-400, 50)
    ax = map_axes(f, MAP, center, d.scale)
    grid(ax, 1000)
    draw_design(ax, d, fs=6.2 if d.scale <= 10000 else 5.6)
    north_scale(ax, d.scale, 1000)
    if markup:
        for nr, (u, v, r, txt) in enumerate(markup, 1):
            x, y = d.P(u, v)
            ax.add_patch(plt.Circle((x, y), r, fill=False, ec="red", lw=2.2, zorder=60))
            ax.text(x + r * 0.75, y + r * 0.75, str(nr), fontsize=11, weight="bold", color="white",
                    bbox=dict(boxstyle="circle", fc="red", ec="white"), zorder=61, clip_on=True)
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
        if phase_note:
            lines += phase_note
        y = text_block(bg, y - 3, lines, fs=6.3, lh=3.8)
    masterplan_inset(bg, 92, render=d.code == "DO")
    title_block(bg, d, f"{d.code}-{blad}", naam, f"1:{nl(d.scale)}")
    pdf.savefig(f)
    plt.close(f)


def sheet_detail(pdf, d, blad, naam, center, scale, lines):
    f, bg = fig_new()
    ax = map_axes(f, MAP, center, scale)
    grid(ax, 500)
    draw_design(ax, d, fs=6.6, anchors=False, dims=False, detail=True)
    north_scale(ax, scale, 500)
    y = legend(bg, PH - 14, d, fs=6.2)
    text_block(bg, y - 3, lines, fs=6.6, lh=4.0)
    title_block(bg, d, f"{d.code}-{blad}", naam, f"1:{nl(scale)}")
    pdf.savefig(f)
    plt.close(f)


def detail_lines(d, blad):
    t = d.info.get("detail", {})
    o = t.get("overslag", {})
    if blad == "06":
        sl = t["teu_grondslots_per_fase"]
        return ["**Overslagketen containers",
                "schip -> STS-kraan -> terminaltrekker -> RTG-stack",
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
                "**RoRo (import): schip -> ramp -> opstelzone -> PDI",
                "   -> parkeervak -> laadstraat autotransporters",
                f"Lossen 6.500 auto's / 150 per u = {nl(o['roro_lostijd_uur'], 1)} u; ca. {o['roro_chauffeurs']} chauffeurs",
                f"Parkeervakken ca. {nl(t['roro_auto_capaciteit'])} auto's (piek 7.479)",
                f"Autotransporters (8 auto's): ca. {nl(o['roro_transporters_per_dag'])} per piekdag",
                "Havendienst: VTS, loodsen, 3 sleepboten, brandweer"]
    return ["**LNG: schip -> laadarmen -> cryogene leiding",
            "   -> tanks -> hervergassing -> centrale / gasnet",
            f"Lossen 156.600 m3 / 10.000 m3/u + 8 u = {nl(o['lng_lostijd_uur'], 1)} u per call",
            "3 laadarmen (2 vloeistof, 1 dampretour); losleiding",
            "   en dampretour langs de zuidelijke dam (ca. 2 km)",
            "Tanks 3 x 180.000 m3 in tankput, ruimte 4e tank",
            f"Send-out gemiddeld {nl(o['lng_sendout_m3_per_uur'])} m3 LNG/u; hervergassing 4 x 33%",
            "Fakkel, BOG-compressor, meetstation, controlekamer",
            "   (veiligheidsafstanden volgen uit de QRA)",
            f"Centrale: 4 STEG-eenheden ca. 565 MW = {nl(t['centrale_eenheden_mw'])} MW",
            "   (rekenvoorbeeld 2.256 MW), hoogspanningsstation,",
            "   koelwaterpompen, gasontvangst"]


def sheet_phases(pdf, d):
    f, bg = fig_new()
    center = d.center or H.P(-400, 50)
    panels = [(15, 302, 305, 277), (325, 302, 305, 277), (15, 15, 305, 277)]
    for (x, y, w, h), ph, jr in zip(panels, (1, 2, 3), (2025, 2035, 2045)):
        ax = map_axes(f, (x, y, w, h), center, 2 * d.scale)
        draw_design(ax, d, labels=False, phase=ph, anchors=False, dims=False)
        ax.text(0.02, 0.97, f"Fase {ph}  -  {jr}", transform=ax.transAxes, fontsize=13, weight="bold", va="top",
                color="white", path_effects=HALO)
        ax.text(0.02, 0.90, ["2 containerligplaatsen, 800 m kade, 72 ha", "3 containerligplaatsen, 1.200 m kade, 108 ha",
                             "4 containerligplaatsen, 1.600 m kade, 144 ha"][ph - 1],
                transform=ax.transAxes, fontsize=8, va="top", color="white", path_effects=HALO)
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
    x0, y0 = 330, 285
    cw = [70, 52, 52, 52]
    bg.text(x0, y0 + 2, "Fasering (rekenboek Containers / Overige terminals)", fontsize=10, weight="bold")
    for r, row in enumerate(rows):
        xx = x0
        for c, txt in enumerate(row):
            bg.add_patch(Rectangle((xx, y0 - 9 * (r + 1)), cw[c], 9, fill=r == 0, fc="#e9ecef", ec="black", lw=0.4))
            bg.text(xx + 1.5, y0 - 9 * (r + 1) + 4.5, txt, fontsize=7, va="center", weight="bold" if r == 0 else None)
            xx += cw[c]
    text_block(bg, y0 - 9 * len(rows) - 8, [
        "De containerkade aan de voorhaven groeit zuidwaarts; baggeren en kadebouw voor",
        "F2/F3 gebeuren aan het zuideinde, buiten de vaarroute naar C1/C2 en de draaikom.",
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
        ("Geullengte buiten mond", f"{nl(m['geullengte_buiten_mond_m'])} m", "Nautiek D31 (ingevuld)", "VOORLOPIG"),
        ("Vrije draaikom", "D 720 m", "Nautiek D28 = 720", "vrij getoetst"),
        ("  afstand tot schepen/kades", f"{nl(m['draaikom_vrij_van_schepen_m'])} / {nl(m['draaikom_vrij_van_kades_dammen_m'])} m", "> 0", "voldoet"),
        ("Havenmond vrij (footprints)", f"{nl(m['havenmond_vrij_m'])} m", "Nautiek D29 = 350", "voldoet"),
        ("Stopweg mond - draaikom", f"{nl(m['stopweg_mond_draaikom_m'])} m", "5 LOA = 1.670 m", "voldoet"),
        ("Sleepbootkoppelpunt", f"{nl(m['sleepboot_buiten_mond_m'])} m buiten mond", "rapport par. 5.1", "ingetekend"),
        ("Containerkade F1/F2/F3", " / ".join(nl(m['containerkade_m'][p]) for p in (1, 2, 3)) + " m", "800/1.200/1.600", "gelijk"),
        ("Containerterrein F1/F2/F3", " / ".join(nl(m['container_ha'][p], 1) for p in (1, 2, 3)) + " ha", "72/108/144 (vraag 40,8/67,9/135,9)", "gelijk"),
        ("Graankade / terrein", f"300 m / {nl(m['graan_ha'], 1)} ha", "300 m / 30 ha (vraag 5,1)", "gelijk"),
        ("RoRo-kade / terrein", f"300 m / {nl(m['roro_ha'], 1)} ha", "300 m / 30 ha (vraag 26,9)", "gelijk"),
        ("LNG-ligplaatsenvelop", "400 m", "ca. 400 m", "dolphins indicatief"),
        ("LNG-envelop tot draaikom", f"{nl(m['lng_ligplaats_tot_draaikom_m'])} m", "vrij", "QRA volgt"),
        ("LNG-zone (3 tanks + optie 4e)", f"{nl(m['lng_zone_ha'], 1)} ha", "3 x 180.000 m3", "N-1 open"),
        ("Centrale + utilities", f"{nl(m['centrale_ha'], 1)} ha", "geen vast oppervlak", "reservering"),
        ("Vrije breedte binnenbekken", f"{nl(m['vrije_breedte_binnenbekken_m'])} m", ">= 220 m", "voldoet"),
        ("Havenbekken baggervak (zone 1)", f"{nl(m['havenbekken_totaal_m2'] / 1e4, 1)} ha", "Grondwerk C6", "ingevuld"),
        ("Geul buiten mond (zone 2+3)", f"{nl(m['geul_buiten_m2'] / 1e4, 1)} ha", "Grondwerk C7+C8", "split op -15 m DHN open"),
        ("Terreinophoging", f"{nl(m['terreinophoging_m2'] / 1e4, 1)} ha", "Grondwerk D21", "ingevuld"),
    ]
    y = table(bg, 15, PH - 22, ("Onderdeel", "Gemeten in DO-tekening", "Rekenboek", "Status"), [78, 75, 92, 58], rows,
              title="Maatstaat DO - tekening tegen rekenboek")
    an = [(k, a["naam"], nl(a["E"], 1), nl(a["N"], 1), f"{a['lat']:.6f}", f"{a['lon']:.6f}") for k, a in d.anchor.items()]
    y = table(bg, 15, y - 14, ("Punt", "Omschrijving", "E (m)", "N (m)", "Lat", "Lon"), [16, 92, 40, 44, 55, 56], an,
              title="Ontwerpankerpunten - EPSG:31984 (E/N) en WGS84 (lat/lon)")
    text_block(bg, y - 6, [
        "Geometrie overgetrokken van de Porto Central-render (Referentie/Porto_Central_render.png), pixel (x, y omlaag):",
        f"schaal {nl(d.info['render_schaal_m_per_px'], 3)} m/px, draaiing {nl(d.info['render_draaiing_graden'], 1)} gr; render (812,5; 275) = A1. "
        f"Kustfit: gemiddeld {nl(d.info['render_kustfit_gem_afwijking_m'])} m.",
        "E = a x + b y + c;  N = d x + e y + f  met a..f in Maatstaat/maatstaat.json (render_affine).",
        "Alle maten in de DXF staan direct in projectcoördinaten; er is geen lokale verschuiving meer nodig.",
    ], fs=8.4, lh=5.2, x=15)
    # georeferentie
    ga, gs = geo["_afstand"], geo["_gshhs"]
    rows = [(n, f"{p['lat']:.6f}, {p['lon']:.6f}", nl(p["E"], 1), nl(p["N"], 1), f"{nl(p['afstand_tot_waterlijn_m'])} m")
            for n, p in list(geo.items())[:2]]
    y2 = table(bg, 340, PH - 22, ("Bronpunt case", "WGS84", "E", "N", "tot waterlijn"), [78, 72, 46, 50, 46], rows,
               title="Georeferentie - bronpunten en controles")
    rows = [(nl(r["N"]), nl(r["E_s2"]), nl(r["E_gshhs"]), nl(r["dE"])) for r in gs["rijen"]]
    y2 = table(bg, 340, y2 - 12, ("N (m)", "E waterlijn S2", "E kust GSHHS", "dE (m)"), [52, 60, 60, 40], rows, rh=6.2,
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
    text_block(bg, y2 - 6, lines, fs=8.4, lh=5.2, x=340)
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
    """Vormreferentie: uitsnede Porto Central-masterplan 2016 p. 9 (SO) of de render (DO) in het rechterpaneel."""
    path = os.path.join(H.ROOT, "Referentie", "Porto_Central_render.png" if render else "Porto_Central_masterplan_2016_p9_uitsnede.png")
    if not os.path.exists(path):
        return y_bottom
    im = np.asarray(Image.open(path).convert("RGB"))
    w = width or (PW - PANEL_X - 8)
    h = w * im.shape[0] / im.shape[1]
    bg.imshow(im, extent=(PANEL_X + 1, PANEL_X + 1 + w, y_bottom, y_bottom + h), zorder=5)
    bg.set_xlim(0, PW)
    bg.set_ylim(0, PH)
    bg.text(PANEL_X + 1, y_bottom + h + 2, "Referentie: Porto Central render (overgetrokken voor het DO)" if render
            else "Vormreferentie: Porto Central masterplan 2016, p. 9 (ANTT)", fontsize=7, weight="bold")
    bg.text(PANEL_X + 1, y_bottom - 2, "Overgenomen: 11/14 dammen | vingers en insteken | 6 containers | 10 graan | 7/8 RoRo\n"
            "9 tankpark (LNG + centrale) | 18 LNG-steiger.  Weggelaten (niet in opdracht): 2, 3, 5, 12, 1", fontsize=5.8, va="top")
    return y_bottom + h


def make_pdf(d, path, coast, geo):
    os.makedirs(os.path.dirname(path), exist_ok=True)
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
        "- draaikom binnenhaven D 460 m op de -16 m-cirkel;",
        "- containerkade aan de oostzijde van vinger 6:",
        "  bereikbaar vanuit de draaikom zonder bocht;",
        "- maten volgen het rekenboek.",
        "In de DXF staat de render op laag HV-REFERENTIE",
        "(uit); aanzetten om zelf verder over te trekken.",
    ], fs=6.6, lh=4.0)
    title_block(bg, d, f"{d.code}-05", "Overtrek Porto Central-render op luchtfoto", f"1:{nl(d.scale)}")
    pdf.savefig(f)
    plt.close(f)
