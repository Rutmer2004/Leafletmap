"""Teksten en maatvoering per blad: welke teksten er komen en waar (zonder overlap, nooit op de kop).

Wordt gebruikt door sheets.py (PDF) en cad.py (DXF-layouts en modelspace), zodat beide hetzelfde laten zien.
"""
import math
import textwrap

from shapely.geometry import LineString, Polygon, box

from labels import HOOGTE, Plaatser, leesbare_hoek, tekstmaat

MAP = (30.0, 30.0, 591.0, 544.0)    # hoofdviewport van layout A1_841x594 uit Template_NHL_Stenden_v1.dwt (mm)
OVERZICHT = (643.0, 130.6, 180.0, 125.0)   # overzichtsviewport (locatiekaart)
LEGENDA = (631.0, 282.0, 189.6, 297.0)     # legendavak
LOGO = (781.0, 17.5, 44.0, 38.6)           # NHL-logo in het titelblok (afbeelding)
OVERZICHT_SCHAAL = 200000

HOOFDVLAK = {"HV-CONTAINER", "HV-GRAAN", "HV-RORO", "HV-HAVENDIENST", "HV-LNG", "HV-CENTRALE", "HV-RESERVE",
             "HV-VOORHAVEN", "HV-GOLFBREKER", "HV-GEUL"}
ALLEEN_DETAIL = {"ramp", "inspectie", "rijcircuit RoRo"}
KORT = {
    "Voorhaven + toegang  -18,20": "-18,20",
    "LNG-vaarweg  -16,20": "LNG-vaarweg -16,20",
    "Hoofdbekken  -18,20": "Hoofdbekken -18,20",
    "Insteekbekken containers  -18,20": "Insteekbekken -18,20",
    "RoRo  -13,70": "-13,70",
    "Insteek F2": None, "Insteek F3": None,
    "Hoofdgeul 220 m, -18,20 m MLWS": "Hoofdgeul 220 m, -18,20 MLWS",
    "veiligheidszone 250 m LNG-ligplaats": "veiligheidszone 250 m",
    "veiligheidszone 250 m LNG-tanks": "veiligheidszone 250 m",
    "nautische controlezone 500 m": "controlezone 500 m",
    "Uitbreiding eigen terminals (na 2045)": "Uitbreiding na 2045",
    "Reserve hoofdbekken (na 2045)": "Reserve na 2045",
    "Reserve insteek 2 (na 2045)": "Reserve na 2045",
    "Graankade 300 m (open kade op palen)": "Graankade 300 m (open kade)",
}


def ombreken(t, n=22):
    if "\n" in t or len(t) <= n + 4:
        return t
    return "\n".join(textwrap.wrap(t, n))


def spec(it, soort):
    """(tekst, laag, prioriteit) voor een ontwerpobject, of None. soort: 'plan', 'detail', 'overzicht', 'geul'."""
    lay, lab = it["layer"], it.get("label")
    if soort == "detail" and it.get("dlabel"):
        return ombreken(it["dlabel"], 20), "T18", 3
    if not lab:
        return None
    lab = KORT.get(lab, lab)
    if lab is None:
        return None
    if lay == "HV-DIEPTELIJN":
        return (lab, "T18", 8) if soort in ("overzicht", "geul") else None
    if soort in ("overzicht", "geul"):
        return None
    if lab in ALLEEN_DETAIL:
        return (lab, "T18", 6) if soort == "detail" else None
    if lay == "HV-ANKERPUNT":
        return None          # ankerpunten alleen in de tabel op DO-04 (ligging ligt vast in de coördinaten)
    if lay == "HV-SCHIP":
        return (lab, "T18", 7) if soort == "detail" and len(lab) <= 3 else None
    if lay == "HV-GEUL-AS":
        return None
    if lay in ("HV-VEILIGHEID", "HV-FASEGRENS"):
        return lab, "T18", 7
    if lay in ("HV-KADE", "HV-BAGGER", "HV-SLEEPBOOT", "HV-WEG"):
        return ombreken(lab), "T18", 5
    if lay == "HV-DRAAIKOM":
        return ombreken(lab, 20), "T18", 4
    if lay in HOOFDVLAK:
        return ombreken(lab), ("T25" if soort == "plan" else "T18"), 2
    return ombreken(lab), "T18", 6


def maatlijn(pl, p1, p2, off, tekst, laag="T18"):
    """Maatlijn op papier; de tekst ligt evenwijdig aan de maatlijn en is altijd leesbaar."""
    a, b = pl.p(*p1), pl.p(*p2)
    L = math.dist(a, b)
    if L < 1e-6:
        return None
    t = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    n = (-t[1], t[0])
    o = off / pl.s
    A = (a[0] + n[0] * o, a[1] + n[1] * o)
    B = (b[0] + n[0] * o, b[1] + n[1] * o)
    rot = leesbare_hoek(math.degrees(math.atan2(t[1], t[0])))
    h = HOOGTE[laag]
    w, hh = tekstmaat(tekst, h)
    sg = 1 if off >= 0 else -1
    m = ((A[0] + B[0]) / 2 + n[0] * sg * (hh / 2 + 1.2), (A[1] + B[1]) / 2 + n[1] * sg * (hh / 2 + 1.2))
    r = math.radians(rot)
    ux, uy, vx, vy = math.cos(r), math.sin(r), -math.sin(r), math.cos(r)
    hw, hh2 = w / 2 + 1.0, hh / 2 + 0.8
    vak = Polygon([(m[0] + ux * sx * hw + vx * sy * hh2, m[1] + uy * sx * hw + vy * sy * hh2)
                   for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    return dict(a=a, b=b, A=A, B=B, n=n, sg=sg, tekst=tekst, pos=m, rot=rot, h=h, laag=laag, vak=vak,
                past=L > w + 6)


def annoteer(d, center, scale, rect, soort, phase=None, extra=(), dims=True, gereserveerd=(), noord=True, schaalstok=True):
    """Bepaal teksten en maatvoering voor één kaartvenster. Geeft dict met plaatser, labels en maatlijnen."""
    pl = Plaatser(center, scale, rect)
    x, y, bb, hh = rect
    pl.venster = box(x + 9, y + 7, x + bb - 4, y + hh - 9)     # rand vrij voor coördinaatteksten
    if noord:
        pl.reserveer(noordvak(rect))
    if schaalstok:
        pl.reserveer(schaalvak(rect))
    for g in gereserveerd:
        pl.reserveer(g)
    maat = []
    if dims:
        for p1, p2, off, tekst in d.dims:
            m = maatlijn(pl, p1, p2, off, tekst)
            if m is None or not pl.venster.contains(m["vak"]):
                continue
            if any(m["vak"].intersects(z) for z in pl.bezet):
                continue
            pl.reserveer(m["vak"])
            pl.reserveer(LineString([m["A"], m["B"]]).buffer(0.3))
            maat.append(m)
    verzoeken = []
    for it in d.items:
        if phase is not None and it["phase"] > phase:
            continue
        if soort == "detail" and it["phase"] > 3 and it["layer"] not in ("HV-RESERVE",):
            continue
        s = spec(it, soort)
        if s is None:
            continue
        tekst, laag, prio = s
        g = it["geom"]
        verzoeken.append((prio, -pl.naar_papier(g).area if g.geom_type.endswith("Polygon") else 0, tekst, g, laag))
    for e in extra:
        tekst, g, laag, prio = e[:4]
        verzoeken.append((prio, 0, tekst, g, laag))
    verzoeken.sort(key=lambda v: (v[0], v[1]))
    gezien = set()
    labels = []
    for prio, _, tekst, g, laag in verzoeken:
        sleutel = (tekst, round(g.centroid.x, -1), round(g.centroid.y, -1))
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        p = pl.plaats(tekst, g, laag=laag, verplicht=prio <= 1)
        if p:
            labels.append(p)
    return dict(plaatser=pl, labels=labels, maat=maat, center=center, scale=scale, rect=rect, vervallen=list(pl.vervallen))


def noordvak(rect):
    x, y, b, h = rect
    return box(x + b - 30, y + h - 46, x + b - 6, y + h - 8)


def schaalvak(rect):
    x, y, b, h = rect
    return box(x + b - 118, y + 6, x + b - 6, y + 26)


def voor_ontwerp(d):
    """Teksten voor het havenplan (02) en de detailbladen, gedeeld door PDF en DXF."""
    d.ann = {"02": annoteer(d, d.center, d.scale, MAP, "plan")}
    for blad, naam, center, scale in d.detail_views:
        d.ann[blad] = annoteer(d, center, scale, MAP, "detail", dims=False)
    return d.ann
