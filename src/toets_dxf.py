"""Golftoets op een (in Civil 3D aangepaste) DXF.

Gebruik:
    python3 src/toets_dxf.py CAD/Haven_DO.dxf

Leest uit de DXF:
  HV-TOETS-OPENING-1-MOND, -2-HOOFDBEKKEN, -3-INSTEEK     openingen van zee naar binnen (lijn tussen de wanden)
  HV-TOETS-WAND-<VH|HB|INS>-<KADE|OPEN|TALUD>             reflecterende wanden (lijnen of polylijnen)
  HV-TOETS-LIGPLAATS-<CONTAINERS|GRAAN|RORO|LNG>          hartlijn van elk afgemeerd schip
  HV-VOORHAVEN, HV-BAGGER, HV-GEUL (gesloten polylijnen)   het water (gestippelde reservevlakken tellen niet mee)
Het waterdeel van een ligplaats (voorhaven, hoofdbekken of insteek) wordt bepaald uit de ligging t.o.v. de openingen.

Schrijft naast de DXF:
  <naam>_golftoets.pdf            tabel per ligplaats en kleurenkaart van de golfhoogte (twee golfrichtingen)
  <naam>_met_golftoets.dxf        kopie van de DXF met golfhoogte-contouren op lagen HV-GOLF-HS-<richting>
"""
import math
import os
import sys

import ezdxf
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import split, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golven  # noqa: E402

NIVEAUS = [0.3, 0.5, 1.0, 1.5, 2.0]
KLEUR = {0.3: 3, 0.5: 4, 1.0: 2, 1.5: 30, 2.0: 1}
RICHTINGEN_KAART = (112.5, 45.0)
SOORT = {"CONTAINERS": "containers", "GRAAN": "graan", "RORO": "RoRo", "LNG": "LNG"}


def _lijnen(msp, laag):
    out = []
    for e in msp.query(f'LINE[layer=="{laag}"]'):
        out.append([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)])
    for e in msp.query(f'LWPOLYLINE[layer=="{laag}"]'):
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        if e.closed:
            pts.append(pts[0])
        out.append(pts)
    return out


def _segmenten(lijnen):
    return [(a, b) for pts in lijnen for a, b in zip(pts[:-1], pts[1:]) if math.dist(a, b) > 0.1]


def _vlakken(msp, lagen):
    out = []
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer not in lagen or not e.closed:
            continue
        if e.dxf.get("linetype", "BYLAYER").upper() in ("DASHED", "DOT"):
            continue   # reserve / toekomstig
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        if len(pts) >= 3:
            g = Polygon(pts).buffer(0)
            if g.area > 1:
                out.append(g)
    return unary_union(out)


def model_uit_dxf(pad):
    doc = ezdxf.readfile(pad)
    msp = doc.modelspace()
    lagen = [l.dxf.name for l in doc.layers]
    openingen = []
    for nr, naam in ((1, "MOND"), (2, "HOOFDBEKKEN"), (3, "INSTEEK")):
        segs = _segmenten(_lijnen(msp, f"HV-TOETS-OPENING-{nr}-{naam}"))
        if not segs:
            raise SystemExit(f"Laag HV-TOETS-OPENING-{nr}-{naam} ontbreekt of is leeg.")
        openingen.append(max(segs, key=lambda s: math.dist(*s)))
    wanden = {"VH": [], "HB": [], "INS": []}
    for laag in lagen:
        if laag.startswith("HV-TOETS-WAND-"):
            _, _, _, regio, soort = laag.split("-", 4)
            cr = golven.WANDTYPE[soort]
            wanden[regio] += [(a, b, cr) for a, b in _segmenten(_lijnen(msp, laag))]

    # water opdelen met de openingen: voorhaven, hoofdbekken, insteek
    water = _vlakken(msp, {"HV-VOORHAVEN", "HV-BAGGER", "HV-GEUL"})
    stukken = [water]
    mids = [((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2) for p1, p2 in openingen]
    for i, (p1, p2) in enumerate(openingen):
        L = math.dist(p1, p2)
        u = ((p2[0] - p1[0]) / L, (p2[1] - p1[1]) / L)
        n = (-u[1], u[0])
        # snijlijn 3 m naar binnen schuiven (de rand van een vlak kan precies op de opening liggen)
        doel = mids[i + 1] if i + 1 < len(mids) else (2 * mids[i][0] - mids[i - 1][0], 2 * mids[i][1] - mids[i - 1][1])
        if (doel[0] - mids[i][0]) * n[0] + (doel[1] - mids[i][1]) * n[1] < 0:
            n = (-n[0], -n[1])
        o = 3.0
        snij = LineString([(p1[0] - u[0] * 80 + n[0] * o, p1[1] - u[1] * 80 + n[1] * o),
                           (p2[0] + u[0] * 80 + n[0] * o, p2[1] + u[1] * 80 + n[1] * o)])
        nieuw = []
        for s in stukken:
            for g in getattr(s, "geoms", [s]):
                nieuw += list(split(g, snij).geoms)
        stukken = nieuw

    def stuk_bij(p):
        q = Point(p)
        bev = [s for s in stukken if s.buffer(0.5).contains(q)]
        return bev[0] if bev else None

    def proeven(p1, p2, afstand=40.0):
        m = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        L = math.dist(p1, p2)
        n = (-(p2[1] - p1[1]) / L, (p2[0] - p1[0]) / L)
        return m, (m[0] + n[0] * afstand, m[1] + n[1] * afstand), (m[0] - n[0] * afstand, m[1] - n[1] * afstand)

    m1, a1, b1 = proeven(*openingen[0])
    m2, a2, b2 = proeven(*openingen[1])
    m3, a3, b3 = proeven(*openingen[2])
    vh = stuk_bij(min((a1, b1), key=lambda q: math.dist(q, m2)))       # binnenkant havenmond
    hb = stuk_bij(min((a2, b2), key=lambda q: math.dist(q, m3)))       # binnenkant ingang hoofdbekken
    ins_kand = [stuk_bij(q) for q in (a3, b3)]
    ins = next((s for s in ins_kand if s is not None and (hb is None or not s.equals(hb))), None)
    waterdelen = {"VH": vh, "HB": hb, "INS": ins}

    def regio_van(pts):
        mid = LineString(pts).interpolate(0.5, normalized=True)
        best = min(((r, g.distance(mid)) for r, g in waterdelen.items() if g is not None), key=lambda t: t[1])
        return best[0]

    groepen = {}
    for laag in lagen:
        if not laag.startswith("HV-TOETS-LIGPLAATS-"):
            continue
        soort = SOORT.get(laag.rsplit("-", 1)[-1])
        if soort is None:
            continue
        for pts in _lijnen(msp, laag):
            ls = LineString(pts)
            n = 3 if soort == "containers" else 5
            punten = [(q.x, q.y) for q in (ls.interpolate(t, normalized=True) for t in np.linspace(0.0, 1.0, n))]
            regio = regio_van(pts)
            groepen.setdefault((soort, regio), []).extend(punten)
    lig = [dict(naam=f"{soort} ({golven.REGIO_NAAM[regio]})", soort=soort, regio=regio, punten=pts)
           for (soort, regio), pts in sorted(groepen.items())]
    if not lig:
        raise SystemExit("Geen ligplaatsen gevonden op lagen HV-TOETS-LIGPLAATS-*.")
    return dict(openingen=openingen, wanden=wanden, ligplaatsen=lig, water=waterdelen), doc


def contouren(model, richting, stap=30.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    velden = golven.kd_regios_model(model, richting, stap=stap)
    fig, ax = plt.subplots()
    lijnen = []
    for X, Y, K in velden:
        if np.isfinite(K).sum() < 4:
            continue
        cs = ax.contour(X, Y, K * golven.HS_BUITEN, levels=NIVEAUS)
        for niveau, segs in zip(cs.levels, cs.allsegs):
            lijnen += [(float(niveau), s) for s in segs if len(s) > 2]
    plt.close(fig)
    return velden, lijnen


def rapport_pdf(pad, model, uitslag, velden_per_richting, bron=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4))
    levels = [0, 0.1, 0.3, 0.5, 1.0, 1.5, 2.0, 3.5]
    cmap = plt.get_cmap("RdYlGn_r")
    for k, (richting, velden) in enumerate(velden_per_richting.items()):
        ax = fig.add_axes([0.02 + k * 0.335, 0.05, 0.325, 0.85])
        for g in model["water"].values():
            if g is None:
                continue
            for p in getattr(g, "geoms", [g]):
                x, y = p.exterior.xy
                ax.fill(x, y, color="#cfe3f3", lw=0)
        cf = None
        for X, Y, K in velden:
            if np.isfinite(K).sum() >= 4:
                cf = ax.contourf(X, Y, K * golven.HS_BUITEN, levels=levels, cmap=cmap, alpha=0.85, extend="max")
        for regio, ws in model["wanden"].items():
            for a, b, cr in ws:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="black", lw=1.6 if cr > 0.8 else 0.8)
        for a, b in model["openingen"]:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#d00000", lw=1.2, ls="--")
        for lp in model["ligplaatsen"]:
            xy = np.array(lp["punten"])
            ax.plot(xy[:, 0], xy[:, 1], "o", ms=2.5, color="#1b4332")
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"Golven uit {richting:g} gr (Hs buiten {golven.HS_BUITEN:g} m, T 8 s)".replace(".", ","), fontsize=9)
        if cf is not None and k == 0:
            cax = fig.add_axes([0.70, 0.88, 0.27, 0.02])
            fig.colorbar(cf, cax=cax, orientation="horizontal").set_label("Hs in de haven (m)", fontsize=8)
    tx = fig.add_axes([0.70, 0.05, 0.28, 0.78])
    tx.axis("off")
    regels = ["Toets per ligplaats (maatgevende richting NO-ZZO)", ""]
    for naam, v in uitslag.items():
        regels.append(f"{naam}: Hs {v['hs']:.2f} m (grens {v['grens']:.1f} m) - "
                      f"{'voldoet' if v['voldoet'] else 'VOLDOET NIET'}".replace(".", ","))
    regels += ["", "Methode: diffractie door havenmond, ingang hoofdbekken en ingang insteek",
               "(Huygens-Kirchhoff) + eerste-orde reflectie (spiegelbronnen, energiesom).",
               "Cr: kademuur 0,9; open kade op palen 0,45; stortsteen/talud 0,4.",
               "Indicatief; geen refractie, hogere-orde reflectie of lange golven."]
    tx.text(0, 1, "\n".join(regels), va="top", fontsize=8.5, family="DejaVu Sans")
    fig.text(0.02, 0.955, f"Golftoets op {bron}", fontsize=13, weight="bold")
    with PdfPages(pad) as pdf:
        pdf.savefig(fig)
    plt.close(fig)


def main(pad):
    model, doc = model_uit_dxf(pad)
    print("Waterdelen:", {r: (round(g.area / 1e4, 1) if g is not None else None) for r, g in model["water"].items()}, "ha")
    uitslag = golven.toets_model(model)
    for naam, v in uitslag.items():
        print(f"  {naam:38s} Kd {v['kd_max']:.2f}  Hs {v['hs']:.2f} m  grens {v['grens']:.1f} m  "
              f"{'voldoet' if v['voldoet'] else 'VOLDOET NIET'}")
    stam = os.path.splitext(pad)[0]
    velden = {}
    msp = doc.modelspace()
    for richting in RICHTINGEN_KAART:
        v, lijnen = contouren(model, richting)
        velden[richting] = v
        for niveau, seg in lijnen:
            laag = f"HV-GOLF-HS-{str(richting).replace('.', '_')}"
            if laag not in doc.layers:
                doc.layers.add(laag, color=7).description = (f"Golfhoogte-contouren Hs (m) voor golven uit {richting} gr; "
                                                             "uitkomst src/toets_dxf.py")
            msp.add_lwpolyline([tuple(p) for p in seg], dxfattribs={"layer": laag, "color": KLEUR[niveau]})
            mid = seg[len(seg) // 2]
            msp.add_text(f"{niveau:g} m".replace(".", ","), height=12,
                         dxfattribs={"layer": laag, "color": KLEUR[niveau]}).set_placement((mid[0], mid[1]))
    rapport_pdf(stam + "_golftoets.pdf", model, uitslag, velden, bron=os.path.basename(pad))
    doc.saveas(stam + "_met_golftoets.dxf")
    print("Geschreven:", stam + "_golftoets.pdf", "en", stam + "_met_golftoets.dxf")
    return uitslag


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
