"""Havenontwerp Groep 1 - schetsontwerp (SO) en definitief ontwerp (DO).

Eén bron voor alle geometrie: het ontwerp wordt in een lokaal havenstelsel (u, v)
gedefinieerd en met één vaste transformatie naar SIRGAS 2000 / UTM 24S (EPSG:31984)
omgezet. Daaruit volgen de DXF-tekeningen, de PDF-bladen, de GeoJSON voor de webkaart
en de maatstaat (JSON), zodat tekening, maatstaat en rekenboek dezelfde getallen gebruiken.

Gebruik:  python3 src/haven.py   (vanuit de root van de repository)
"""
import json
import math
import os
import sys

import numpy as np
from pyproj import Geod, Transformer
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OND = os.path.join(ROOT, "CAD", "Ondergrond")
IMG = "S2_20260703_TCI_EPSG31984.jpg"
IMG_BOUNDS = (284000.0, 7632000.0, 318000.0, 7666000.0)  # W, S, E, N (10 m pixels)

# --------------------------------------------------------------------------------------
# Lokaal havenstelsel
#   O    = kustlijn (waterlijn 3-7-2026) op de havenas, door het Porto Central-terrein
#          (Presidente Kennedy, Espírito Santo; bouwterrein fase 1 zichtbaar op de luchtfoto)
#   u    = zeewaarts langs de havenas, azimut 110 graden (loodrecht op de kust)
#   v    = langs de kust, azimut 20 graden (positief naar het noorden)
# --------------------------------------------------------------------------------------
O = (297135.0, 7650000.0)
AZ_U = 110.0
LOCATIE = "Porto Central, Presidente Kennedy - Espírito Santo, 29350-000, Brazilië"
EU = (math.sin(math.radians(AZ_U)), math.cos(math.radians(AZ_U)))
EV = (math.sin(math.radians(AZ_U - 90)), math.cos(math.radians(AZ_U - 90)))

TO_LL = Transformer.from_crs(31984, 4326, always_xy=True)
GEOD = Geod(ellps="GRS80")

LOA, BEAM, DRAFT = 334.0, 48.2, 14.5
REF_POINTS = {
    "São Francisco de Itabapoana": (-21.309884, -40.957744),
    "Rio Marobá / Barra de Boa Vista": (-21.190796, -40.926339),
}


def P(u, v):
    return (O[0] + u * EU[0] + v * EV[0], O[1] + u * EU[1] + v * EV[1])


def to_world(g):
    """Shapely-geometrie van (u, v) naar (E, N)."""
    a, b = EU[0], EV[0]
    d, e = EU[1], EV[1]
    return affinity.affine_transform(g, [a, b, d, e, O[0], O[1]])


def rect(u0, u1, v0, v1):
    return box(min(u0, u1), min(v0, v1), max(u0, u1), max(v0, v1))


def ll(e, n):
    lon, lat = TO_LL.transform(e, n)
    return lat, lon


# --------------------------------------------------------------------------------------
# Lagen: naam -> (ACI-kleur DXF, matplotlib-kleur, vulling, omschrijving)
# --------------------------------------------------------------------------------------
LAYERS = {
    "HV-ONDERGROND": (8, "#000000", None, "Luchtfoto Sentinel-2 3-7-2026"),
    "HV-KUSTLIJN": (4, "#00e5ff", None, "Waterlijn 3-7-2026 (NDWI, geen MLWS-lijn)"),
    "HV-ZOEKGEBIED": (6, "#ff4fd8", None, "Zoekgebied locatie B (indicatief)"),
    "HV-BAGGER": (5, "#3a86ff", 0.30, "Gebaggerd tot -18,20 m MLWS (voorlopig)"),
    "HV-GEUL": (5, "#4cc9f0", None, "Geul 220 m bodembreedte"),
    "HV-GEUL-AS": (1, "#ffffff", None, "Vaarwegas"),
    "HV-DRAAIKOM": (2, "#ffd60a", None, "Vrije draaikom D = 720 m"),
    "HV-HAVENMOND": (2, "#ffd60a", None, "Havenmond vrij 350 m"),
    "HV-GOLFBREKER": (8, "#adb5bd", 1.0, "Golfbreker (footprint 90 m, voorlopig)"),
    "HV-KADE": (7, "#ffffff", None, "Kade / steiger"),
    "HV-SCHIP": (3, "#80ffdb", 0.35, "Scheepsenveloppe aan ligplaats"),
    "HV-CONTAINER": (30, "#f77f00", 0.40, "Containerterminal"),
    "HV-GRAAN": (50, "#ffd166", 0.45, "Graanterminal"),
    "HV-RORO": (110, "#06d6a0", 0.40, "RoRo / voertuigenterminal"),
    "HV-LNG": (1, "#ef233c", 0.45, "LNG-steiger, tanks en hervergassing"),
    "HV-CENTRALE": (200, "#c77dff", 0.40, "Centrale + utilities (reservering)"),
    "HV-HAVENDIENST": (150, "#4ea8de", 0.40, "Havendiensten, sleepboten, loodsen"),
    "HV-RESERVE": (9, "#dee2e6", 0.18, "Reserveterrein / latere uitbreiding"),
    "HV-WEG": (7, "#f8f9fa", None, "Hoofdweg + terminalinritten"),
    "HV-SPOOR": (8, "#212529", None, "Spoor"),
    "HV-LEIDING": (1, "#ff006e", None, "LNG/gasleiding, koelwater (indicatief)"),
    "HV-FASEGRENS": (6, "#ff4fd8", None, "Fasegrens 2025 / 2035 / 2045"),
    "HV-SLEEPBOOT": (2, "#ffd60a", None, "Sleepbootkoppelpunt"),
    "HV-ANKERPUNT": (1, "#ff0000", None, "Ontwerpankerpunt (E/N in maatstaat)"),
    "HV-CONFLICT": (1, "#ff0000", None, "Conflict / bespreekpunt"),
    "HV-MAAT": (7, "#ffffff", None, "Maatvoering"),
    "HV-TEKST": (7, "#ffffff", None, "Tekst"),
    "HV-RASTER": (8, "#ffffff", None, "Coördinatenraster"),
}


class Design:
    def __init__(self, code):
        self.code = code
        self.items = []  # dicts: layer, geom (wereld), label, phase, style
        self.dims = []  # (p1, p2, offset_m, tekst)  in wereldcoördinaten
        self.notes = []
        self.anchor = {}
        self.m = {}  # maatstaat

    def add(self, layer, g_local, label=None, phase=1, **kw):
        g = to_world(g_local)
        self.items.append(dict(layer=layer, geom=g, local=g_local, label=label, phase=phase, **kw))
        return g

    def dim(self, p1, p2, off, text):
        self.dims.append((P(*p1), P(*p2), off, text))

    def anchor_pt(self, key, name, u, v):
        e, n = P(u, v)
        lat, lon = ll(e, n)
        self.anchor[key] = dict(naam=name, u=u, v=v, E=e, N=n, lat=lat, lon=lon)
        self.add("HV-ANKERPUNT", Point(u, v), label=key)


def breakwater(d, pts, name):
    cl = LineString(pts)
    fp = cl.buffer(45, cap_style="round", join_style="round")
    d.add("HV-GOLFBREKER", fp, label=name, tag="dam")
    d.add("HV-GEUL-AS", cl, style="dashdot")
    return fp


def ship_v(d, u_quay, v0, v1, side, beam, label, phase=1):
    """Schip langs een kade evenwijdig aan de v-as (kadelijn u = u_quay); side +1 = schip aan de +u-zijde."""
    a, b = u_quay + side * 5.0, u_quay + side * (5.0 + beam)
    g = rect(a, b, v0, v1)
    d.add("HV-SCHIP", g, label=label, phase=phase, tag="schip")
    return g


def ship_u(d, v_quay, u0, u1, side, beam, label, phase=1):
    """Schip langs een kade evenwijdig aan de u-as (kadelijn v = v_quay); side +1 = schip aan de +v-zijde."""
    a, b = v_quay + side * 5.0, v_quay + side * (5.0 + beam)
    g = rect(u0, u1, a, b)
    d.add("HV-SCHIP", g, label=label, phase=phase, tag="schip")
    return g


def add_pt(a, b, s=1.0):
    return (a[0] + s * b[0], a[1] + s * b[1])


# ======================================================================================
# Ontwerp naar het Porto Central-masterplan (2016, p. 9)
#   - twee gebogen golfbrekers, havenmond naar het oost-zuidoosten (11, 14)
#   - hoofdbekken langs de noordzijde landinwaarts, graan aan de noordkade (10)
#   - containerterminal als brede vinger met kade direct aan de voorhaven (6)
#   - insteekbekken en tweede terminalvinger daarachter (7/8)
#   - tank- en energiezone langs de zuidrand (9), LNG-steiger bij de zuidelijke dam (18)
# SO = eerste schets met de bespreekpunten; DO = verwerkte versie.
# ======================================================================================
def build(code):
    so = code == "SO"
    d = Design(code)
    ang = math.radians(13.0)  # havenmond/geul 13 graden zuidelijker dan de havenas (masterplan: ingang naar OZO)
    dv = (math.cos(ang), -math.sin(ang))
    nv = (math.sin(ang), math.cos(ang))
    T = (100.0, 100.0) if so else (300.0, 100.0)
    stop = 1650.0 if so else 1700.0
    M = add_pt(T, dv, stop)
    half = 175.0 if so else 220.0  # SO: 350 m tussen damhartlijnen; DO: 350 m vrij tussen footprints
    hn, hs = add_pt(M, nv, half), add_pt(M, nv, -half)

    # --- golfbrekers (11) ---------------------------------------------------------------
    bwn = breakwater(d, [(-50, 1900), (900, 1900), (hn[0] - 450, 1650), (hn[0] - 60, 900), hn], "Noordelijke golfbreker")
    bws = breakwater(d, [(-200, -1850), (900, -1850), (hs[0] - 400, -1600), (hs[0] - 120, -1100), hs], "Zuidelijke golfbreker")

    # --- toegangsgeul (14) en draaikom -------------------------------------------------------
    if so:
        knik = add_pt(M, dv, 2200)
        a2 = ang - math.radians(15)
        eind = add_pt(knik, (math.cos(a2), -math.sin(a2)), 8000)
        axis_out = LineString([M, knik, eind])
    else:
        eind = add_pt(M, dv, 10000)
        knik = None
        axis_out = LineString([M, eind])
    d.add("HV-GEUL", axis_out.buffer(110, cap_style="flat", join_style="mitre"), label="Hoofdgeul 220 m, -18,20 m MLWS")
    inner = LineString([T, M]).buffer(110, cap_style="flat")
    d.add("HV-GEUL", inner)
    d.add("HV-GEUL-AS", LineString([T, M] + list(axis_out.coords)[1:]))
    circle = Point(T).buffer(360, 128)
    d.add("HV-DRAAIKOM", circle, label="Vrije draaikom D 720 m")
    tug = add_pt(M, dv, 1500)
    if not so:
        d.add("HV-SLEEPBOOT", Point(tug).buffer(60), label="Sleepbootkoppelpunt")

    # --- LNG-steiger (18) aan de lijzijde van de zuidelijke dam --------------------------------
    d.add("HV-KADE", LineString([(-200, -1330), (720, -1330)]), label="LNG-steiger")
    d.add("HV-KADE", rect(670, 770, -1370, -1295))
    lng_ship = ship_u(d, -1295, 574.5, 865.5, 1, 45.8, "GASLOG GREECE")
    lng_env = rect(520, 920, -1295, -1180)
    d.add("HV-SCHIP", lng_env, tag="lng_env")
    for du in (550, 630, 810, 890):
        d.add("HV-KADE", Point(du, -1305).buffer(10))
    lng_route = unary_union([LineString([T, (720, -1150)]).buffer(150, cap_style="round"), rect(450, 990, -1380, -1130)])

    # --- water: voorhaven, containerbekken, hoofdbekken, insteekbekken -----------------------
    d.add("HV-BAGGER", unary_union([inner, circle, lng_route]), label="Voorhaven + LNG-insteek", tag="voorhaven")
    if so:
        d.add("HV-BAGGER", rect(-200, 450, -1100, 1150), label="Containerbekken", tag="bekken")
        d.add("HV-BAGGER", rect(-2600, -200, 700, 1150), label="Hoofdbekken (alles fase 1)", tag="bekken")
        d.add("HV-BAGGER", rect(-1550, -1100, -1050, 700), label="Insteekbekken", tag="bekken")
    else:
        for v0, v1, ph in [(-300, 1150, 1), (-700, -300, 2), (-1100, -700, 3)]:
            d.add("HV-BAGGER", rect(-200, 450, v0, v1), label=f"Containerbekken F{ph}" if ph > 1 else "Containerbekken", phase=ph, tag="bekken")
        d.add("HV-BAGGER", rect(-1600, -200, 700, 1150), label="Hoofdbekken", tag="bekken")
        d.add("HV-BAGGER", rect(-2600, -1600, 700, 1150), label="Reserve hoofdbekken (fase 4)", phase=4, style="dashed", tag="reserve_water")
        d.add("HV-BAGGER", rect(-1550, -1100, 100, 700), label="Insteekbekken", tag="bekken")
        d.add("HV-BAGGER", rect(-1550, -1100, -1050, 100), label="Reserve insteek (fase 4)", phase=4, style="dashed", tag="reserve_water")

    # --- containerterminal (6): vinger met kade aan de voorhaven -----------------------------
    if so:
        parts = [(-1050, -250, 1), (-250, 150, 2), (150, 550, 3)]
        bph = [3, 2, 1, 1]
    else:
        parts = [(-250, 550, 1), (-650, -250, 2), (-1050, -650, 3)]
        bph = [1, 1, 2, 3]
    tot = {1: "F1 2025: 2 lp, 800 m, 72 ha", 2: "F2 2035: +1 lp, 108 ha", 3: "F3 2045: +1 lp, 144 ha"}
    for v0, v1, ph in parts:
        d.add("HV-CONTAINER", rect(-1100, -200, v0, v1), label=tot[ph], phase=ph, tag="cyard")
        d.add("HV-KADE", LineString([(-200, v1), (-200, v0)]), phase=ph, tag="ckade")
    for i in range(4):
        vt = 550 - 400 * i
        vm = vt - 200
        ship_v(d, -200, vm - LOA / 2, vm + LOA / 2, 1, BEAM, f"C{i + 1}", phase=bph[i])
    if not so:
        d.add("HV-KADE", LineString([(-1100, 650), (-1100, -1000)]), style="dashed", phase=4, label="reserve kade westzijde (fase 4)")
        for uu, t in [(-250, "F1 | F2"), (-650, "F2 | F3")]:
            d.add("HV-FASEGRENS", LineString([(-1100, uu), (450, uu)]), label=t)

    # --- graan (10) en RoRo (8) ----------------------------------------------------------------
    if so:
        d.add("HV-GRAAN", rect(-1700, -600, 1150, 1750), label="Graan + RoRo gedeeld perceel", tag="graan_plot")
        d.add("HV-KADE", LineString([(-1000, 1150), (-700, 1150)]), label="Graankade 300 m")
        d.add("HV-KADE", LineString([(-1550, 1150), (-1250, 1150)]), label="RoRo-kade 300 m")
        ship_u(d, 1150, -964.5, -735.5, -1, 32.26, "Graanschip")
        ship_u(d, 1150, -1510, -1290, -1, 37.7, "RoRo-schip")
        d.add("HV-RESERVE", rect(-2600, -1700, 1150, 1750), label="Reserve")
        d.add("HV-RESERVE", rect(-2600, -1550, -1050, 700), label="Reserve")
    else:
        d.add("HV-GRAAN", rect(-1100, -600, 1150, 1750), label="Graan 30 ha", tag="graan_plot")
        d.add("HV-KADE", LineString([(-1000, 1150), (-700, 1150)]), label="Graankade 300 m")
        ship_u(d, 1150, -964.5, -735.5, -1, 32.26, "Graanschip")
        d.add("HV-GRAAN", rect(-1050, -800, 1350, 1600))  # silo's/opslag
        d.add("HV-LEIDING", LineString([(-850, 1150), (-850, 1350)]), style="dashed")  # transportband
        d.add("HV-RORO", rect(-2050, -1550, 100, 700), label="RoRo 30 ha", tag="roro_plot")
        d.add("HV-KADE", LineString([(-1550, 250), (-1550, 550)]), label="RoRo-kade 300 m")
        ship_v(d, -1550, 290, 510, 1, 37.7, "RoRo-schip")
        d.add("HV-RORO", rect(-1550, -1515, 380, 420))  # ramp
        d.add("HV-RESERVE", rect(-2050, -1550, -1050, 100), label="Reserve stukgoed/supply (7/8)")
        d.add("HV-RESERVE", rect(-2600, -2050, -1050, 700), label="Reserve bedrijven (12)")
        d.add("HV-RESERVE", rect(-2600, -1200, 1150, 1750), label="Reserve industrie (3)")
        d.add("HV-HAVENDIENST", rect(-500, -60, 1150, 1500), label="Havendiensten/sleepboten (17)", tag="havendienst")
        d.add("HV-KADE", LineString([(-450, 1150), (-150, 1150)]))

    # --- LNG-zone en centrale (9) langs de zuidrand -----------------------------------------------
    if so:
        lz = rect(-800, -200, -1500, -1100)
        tanks = [Point(-700 + 150 * k, -1200).buffer(45, 64) for k in range(3)]
        cz = rect(-1900, -850, -1500, -1100)
    else:
        lz = rect(-800, -200, -1700, -1200)
        tanks = [Point(-700 + 150 * k, -1560).buffer(45, 64) for k in range(3)]
        cz = rect(-1900, -850, -1700, -1200)
    d.add("HV-LNG", lz, label="LNG-tanks + hervergassing", tag="lng_zone")
    for t in tanks:
        d.add("HV-LNG", t, tag="tank")
    if not so:
        d.add("HV-LNG", Point(-250, -1560).buffer(45, 64), style="dashed")  # optie 4e tank (N-1)
        d.add("HV-LNG", rect(-700, -300, -1440, -1360))  # hervergassing
    d.add("HV-CENTRALE", cz, label="Centrale + utilities", tag="centrale")

    # --- leidingen, wegen en spoor ------------------------------------------------------------------
    d.add("HV-LEIDING", LineString([(720, -1330), (-200, -1330)]), style="dashed")
    if not so:
        d.add("HV-LEIDING", LineString([(-700, -1400), (-850, -1400)]), style="dashed")
        d.add("HV-LEIDING", LineString([(-1900, -1650), (-2750, -1650)]), style="dashed")  # gasnet
        d.add("HV-LEIDING", LineString([(300, -1080), (-200, -1180), (-850, -1180)]), style="dotted")  # koelwater in
        d.add("HV-LEIDING", LineString([(-1400, -1700), (-1400, -1980), (400, -1980)]), style="dotted")  # koelwater uit
        d.add("HV-WEG", LineString([(-2750, -1750), (-2750, 1800), (-280, 1800), (-280, 1500)]))
        d.add("HV-WEG", LineString([(-2750, -1125), (-200, -1125)]))
        d.add("HV-WEG", LineString([(-2750, 400), (-2050, 400)]))
        d.add("HV-WEG", LineString([(-3600, 0), (-2750, 0)]))
        d.add("HV-WEG", LineString([(-1080, -1125), (-1080, 540)]), style="dashed")  # terminalweg west
        d.add("HV-SPOOR", LineString([(-3600, 60), (-2800, 60), (-2800, 1760), (-850, 1760)]))
        d.add("HV-SPOOR", LineString([(-2800, 60), (-2800, -1090), (-1050, -1090), (-1050, -1000)]))
        for gu, gv in [(-650, -1125), (-850, 1800), (-2050, 400), (-500, -1160), (-1400, -1160), (-280, 1520)]:
            d.add("HV-WEG", Point(gu, gv).buffer(18))  # terminalpoorten
    else:
        d.add("HV-WEG", LineString([(-2700, -1550), (-2700, 1800), (-600, 1800)]))
        d.add("HV-WEG", LineString([(-2700, -1050), (-200, -1050)]))
        d.add("HV-WEG", LineString([(-1150, 1800), (-1150, 1180)]), label="Weg door perceel")
        d.add("HV-SPOOR", LineString([(-2750, -1550), (-2750, 1760), (-600, 1760)]))

    d.notes = dict(M=M, T=T, hn=hn, hs=hs, dv=dv, nv=nv, stop=stop, tug=tug, eind=eind, knik=knik,
                   bwn=bwn, bws=bws, circle=circle, lng_env=lng_env, tanks=tanks)

    # --- maatvoering ----------------------------------------------------------------------------------
    d.dim((-200, 550), (-200, -1050), -170, "containerkade 4 x 400 = 1.600 m")
    d.dim((-1100, -1050), (-200, -1050), -60, "900 m")
    d.dim((-1600, 700), (-1600, 1150), 120, "450 m")
    d.dim((-1550, 100), (-1100, 100), -80, "450 m")
    d.dim((-1000, 1150), (-700, 1150), 90, "300 m")
    if not so:
        d.dim((-1100, 1750), (-600, 1750), 70, "500 m")
        d.dim((-1100, 1150), (-1100, 1750), 70, "600 m")
        d.dim((-1550, 250), (-1550, 550), 110, "300 m")
        d.dim((-2050, 100), (-1550, 100), -70, "500 m")
        d.dim((-2050, 100), (-2050, 700), 80, "600 m")
        d.dim((520, -1180), (920, -1180), 70, "400 m")
        d.dim(add_pt(M, dv, 1500), M, 260, "1.500 m")
    d.dim(add_pt(add_pt(M, dv, 500), nv, -110), add_pt(add_pt(M, dv, 500), nv, 110), 200, "220 m")
    if so:
        d.dim(hs, hn, 260, "350 m hart-hart")
    else:
        d.dim(add_pt(hs, nv, 45), add_pt(hn, nv, -45), 300, "350 m vrij")
    d.dim(M, T, 420, f"{nl0(stop)} m = {stop / LOA:.1f} LOA".replace(".", ","))

    pts = [("A1", "Kustpunt havenas (waterlijn)", (0, 0)), ("A2", "Middelpunt vrije draaikom", T),
           ("A3", "Midden havenmond", M)]
    if so:
        pts += [("A4", "Geulknik", knik), ("A5", "Eindpunt geul (voorlopig)", eind)]
    else:
        pts += [("A4", "Sleepbootkoppelpunt", tug), ("A5", "Eindpunt geul (voorlopig)", eind),
                ("A6", "Wortel noordelijke golfbreker", (-50, 1900)), ("A7", "Wortel zuidelijke golfbreker", (-200, -1850)),
                ("A8", "Containerkade noordeinde (F1)", (-200, 550)), ("A9", "Containerkade zuideinde (F3)", (-200, -1050)),
                ("A10", "Midden LNG-ligplaats", (720, -1270)), ("A11", "Graankade midden", (-850, 1150)),
                ("A12", "RoRo-kade midden", (-1550, 400))]
    for k, nm, (u, v) in pts:
        d.anchor_pt(k, nm, u, v)
    return d


def nl0(x):
    return f"{x:,.0f}".replace(",", ".")


def build_so():
    return build("SO")


def build_do():
    return build("DO")


# ======================================================================================
# Metingen en controles
# ======================================================================================
def _u(d, pred):
    gs = [i["local"] for i in d.items if pred(i)]
    return unary_union(gs) if gs else Polygon()


def measure(d):
    n = d.notes
    m = {}
    tag = lambda t, ph=3: (lambda i: i.get("tag") == t and i["phase"] <= ph)
    circ = n["circle"]
    ships = _u(d, lambda i: i["layer"] == "HV-SCHIP")
    solid = unary_union([n["bwn"], n["bws"], _u(d, lambda i: i["layer"] == "HV-KADE" and i["phase"] <= 3)])
    land = _u(d, lambda i: i["layer"] in ("HV-CONTAINER", "HV-GRAAN", "HV-RORO", "HV-HAVENDIENST", "HV-LNG", "HV-CENTRALE"))
    m["havenmond_vrij_m"] = n["bwn"].distance(n["bws"])
    m["draaikom_diameter_m"] = 720.0
    m["draaikom_vrij_van_schepen_m"] = circ.distance(ships)
    m["draaikom_overlap_schepen_m2"] = circ.intersection(ships).area
    m["draaikom_vrij_van_kades_dammen_m"] = circ.distance(solid)
    m["draaikom_overlap_land_m2"] = circ.intersection(land).area
    m["stopweg_mond_draaikom_m"] = n["stop"]
    m["stopweg_in_LOA"] = n["stop"] / LOA
    m["geullengte_buiten_mond_m"] = 10000.0 if n["knik"] is None else 2200.0 + 8000.0
    m["geullengte_totaal_vanaf_draaikom_m"] = m["geullengte_buiten_mond_m"] + n["stop"]
    m["geul_buiten_m2"] = 220 * m["geullengte_buiten_mond_m"]
    m["sleepboot_buiten_mond_m"] = 1500.0
    m["lng_ligplaats_tot_draaikom_m"] = n["lng_env"].distance(circ)
    m["lng_tank_tot_containerterrein_m"] = unary_union(n["tanks"]).distance(_u(d, tag("cyard")))
    tanks_w = to_world(unary_union(n["tanks"]))
    m["lng_tank_tot_kustbebouwing_zuid_m"] = tanks_w.bounds[1] - 7646300.0  # bebouwing aan de kust, luchtfoto
    m["containerkade_m"] = {ph: _u(d, tag("ckade", ph)).length for ph in (1, 2, 3)}
    m["container_ha"] = {ph: _u(d, tag("cyard", ph)).area / 1e4 for ph in (1, 2, 3)}
    m["graan_ha"] = _u(d, tag("graan_plot")).area / 1e4
    m["roro_ha"] = _u(d, tag("roro_plot")).area / 1e4 if d.code == "DO" else m["graan_ha"]
    m["lng_zone_ha"] = _u(d, tag("lng_zone")).area / 1e4
    m["centrale_ha"] = _u(d, tag("centrale")).area / 1e4
    m["havendienst_ha"] = _u(d, tag("havendienst")).area / 1e4
    m["reserve_ha"] = _u(d, lambda i: i["layer"] == "HV-RESERVE").area / 1e4
    m["binnenbekken_m2"] = {ph: _u(d, tag("bekken", ph)).area for ph in (1, 2, 3)}
    m["voorhaven_bagger_m2"] = _u(d, tag("voorhaven")).difference(_u(d, tag("bekken"))).area
    m["havenbekken_totaal_m2"] = _u(d, lambda i: i["layer"] == "HV-BAGGER" and i["phase"] <= 3).area
    m["reserve_water_m2"] = _u(d, lambda i: i.get("tag") == "reserve_water").area
    m["vrije_breedte_binnenbekken_m"] = 450 - 5 - 37.7  # insteekbekken met RoRo-schip; hoofdbekken 412,7 m
    terr = ("cyard", "graan_plot", "roro_plot", "lng_zone", "centrale", "havendienst")
    m["terreinophoging_m2"] = _u(d, lambda i: i.get("tag") in terr).area
    d.m = m
    return m


def georef_checks(coast):
    out = {}
    for name, (lat, lon) in REF_POINTS.items():
        e, n = Transformer.from_crs(4326, 31984, always_xy=True).transform(lon, lat)
        out[name] = dict(lat=lat, lon=lon, E=e, N=n, afstand_tot_waterlijn_m=Point(e, n).distance(coast))
    (la1, lo1), (la2, lo2) = REF_POINTS.values()
    az, _, geo = GEOD.inv(lo1, la1, lo2, la2)
    a = list(out.values())
    grid = math.hypot(a[1]["E"] - a[0]["E"], a[1]["N"] - a[0]["N"])
    from pyproj import Proj
    f = Proj("EPSG:31984").get_factors(-40.94, -21.25)
    out["_afstand"] = dict(geodetisch_m=geo, grid_m=grid, verschil_m=grid - geo, schaalfactor=f.meridional_scale,
                           meridiaanconvergentie_graden=f.meridian_convergence)
    return out


# ======================================================================================
# Uitvoer
# ======================================================================================
def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cad
    import landxml
    import sheets
    import web

    coast = LineString(json.load(open(os.path.join(OND, "coast.json"))))
    gshhs = LineString(json.load(open(os.path.join(OND, "gshhs.json"))))
    so, do = build_so(), build_do()
    for d in (so, do):
        measure(d)
    geo = georef_checks(coast)
    # GSHHS-vergelijking (onafhankelijke kustlijn)
    diffs = []
    for n0 in range(7642000, 7656001, 1000):
        h = LineString([(285000, n0), (318000, n0)])
        xa = [p.x for p in getattr(gshhs.intersection(h), "geoms", [gshhs.intersection(h)]) if not p.is_empty]
        xb = [p.x for p in getattr(coast.intersection(h), "geoms", [coast.intersection(h)]) if not p.is_empty]
        if xa and xb:
            diffs.append(dict(N=n0, E_gshhs=max(xa), E_s2=max(xb), dE=max(xa) - max(xb)))
    geo["_gshhs"] = dict(rijen=diffs, gemiddeld_m=float(np.mean([r["dE"] for r in diffs])),
                         std_m=float(np.std([r["dE"] for r in diffs])))
    # kustlijnoriëntatie bij de haven
    P_ = np.array([p for p in coast.coords if 7648800 < p[1] < 7651300 and p[0] > 295500])
    k = np.polyfit(P_[:, 1], P_[:, 0], 1)[0]
    geo["_kust_azimut_graden"] = math.degrees(math.atan(k))

    data = dict(SO=dict(m=so.m, anker=so.anchor), DO=dict(m=do.m, anker=do.anchor), georef=geo,
                lokaal=dict(O=O, azimut_u=AZ_U))
    os.makedirs(os.path.join(ROOT, "Maatstaat"), exist_ok=True)
    json.dump(data, open(os.path.join(ROOT, "Maatstaat", "maatstaat.json"), "w"), indent=1, default=str, ensure_ascii=False)

    cad.write_dxf(so, os.path.join(ROOT, "CAD", "Haven_SO.dxf"), coast)
    cad.write_dxf(do, os.path.join(ROOT, "CAD", "Haven_DO.dxf"), coast)
    sheets.make_pdf(so, os.path.join(ROOT, "PDF", "Haven_SO.pdf"), coast, geo)
    sheets.make_pdf(do, os.path.join(ROOT, "PDF", "Haven_DO.pdf"), coast, geo)
    web.write_geojson(so, do, coast, os.path.join(ROOT, "webkaart"))
    data["landxml"] = landxml.write_landxml(do, os.path.join(ROOT, "CAD", "Haven_DO_geul_ontwerpbodem.xml"))
    json.dump(data, open(os.path.join(ROOT, "Maatstaat", "maatstaat.json"), "w"), indent=1, default=str, ensure_ascii=False)
    print(json.dumps(dict(SO=so.m, DO=do.m), indent=1, default=str))


if __name__ == "__main__":
    main()
