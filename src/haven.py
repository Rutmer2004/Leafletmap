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
    d.add("HV-GOLFBREKER", cl.buffer(45, cap_style="round", join_style="round"), label=name)
    d.add("HV-GEUL-AS", cl, style="dashdot")
    return cl.buffer(45, cap_style="round", join_style="round")


def ship(d, u0, u1, v_quay, side, beam, label, phase=1):
    """Schip aan de kade: side = +1 schip ligt aan +v-zijde van de kadelijn, -1 aan -v-zijde."""
    fender = 5.0
    v0 = v_quay + side * fender
    v1 = v_quay + side * (fender + beam)
    um = (u0 + u1) / 2
    d.add("HV-SCHIP", rect(um - (u1 - u0) / 2, um + (u1 - u0) / 2, v0, v1), label=label, phase=phase)
    return rect(u0, u1, v0, v1)


# --------------------------------------------------------------------------------------
# Hulpelementen gedeeld door SO en DO
# --------------------------------------------------------------------------------------
def berths(d, quay_v, u_from, n, module, side, beam, length, label, phases):
    out = []
    for i in range(n):
        a = u_from - i * module
        b = a - module
        um = (a + b) / 2
        out.append(ship(d, um - length / 2, um + length / 2, quay_v, side, beam,
                        f"{label} {i + 1}", phase=phases[i]))
    return out


# ======================================================================================
# SCHETSONTWERP (SO)
# ======================================================================================
def build_so():
    d = Design("SO")
    mouth_u = 1800.0
    tc = (150.0, 0.0)
    # golfbrekers: koppen met hartlijn op v = +-175 m
    bwn = breakwater(d, [(-60, 1850), (1000, 1850), (1500, 1400), (1750, 700), (1800, 175)], "Noordelijke golfbreker")
    bws = breakwater(d, [(-60, -1100), (1000, -1100), (1500, -800), (1750, -450), (1800, -175)], "Zuidelijke golfbreker")
    # geul: recht tot u = 4.000, daarna knik van 15 graden (naar diep water, aanname)
    knik = (4000.0, 0.0)
    ang = math.radians(15)
    eind = (knik[0] + 8000 * math.cos(ang), knik[1] + 8000 * math.sin(ang))
    as_out = LineString([(mouth_u, 0), knik, eind])
    d.add("HV-GEUL", as_out.buffer(110, cap_style="flat", join_style="mitre"), label="Hoofdgeul 220 m (SO)")
    d.add("HV-GEUL-AS", LineString([(tc[0], 0), (mouth_u, 0)] + list(as_out.coords)[1:]))
    inner = rect(tc[0], mouth_u, -110, 110)
    d.add("HV-GEUL", inner)
    circle = Point(tc).buffer(360, 128)
    d.add("HV-DRAAIKOM", circle, label="Draaikom D 720 m")
    basin = rect(-2300, 0, -225, 225)
    d.add("HV-BAGGER", unary_union([basin, inner, circle, rect(0, tc[0], -225, 225)]), label="Binnenbekken (alles fase 1)")
    # containers: fase 1 aan de landzijde
    d.add("HV-KADE", LineString([(-2100, 225), (-500, 225)]), label="Containerkade 1.600 m")
    for (a, b, ph) in [(-2100, -1300, 1), (-1300, -900, 2), (-900, -500, 3)]:
        d.add("HV-CONTAINER", rect(a, b, 225, 1125), label=f"Containers F{ph}", phase=ph)
    berths(d, 225, -500, 4, 400, -1, BEAM, LOA, "C", [3, 2, 1, 1])
    # graan en RoRo samen op één perceel met kruisende weg
    d.add("HV-GRAAN", rect(-1700, -1100, -825, -225), label="Graan + RoRo gedeeld perceel")
    d.add("HV-RORO", rect(-1100, -500, -825, -225), label=None)
    d.add("HV-KADE", LineString([(-1500, -225), (-1200, -225)]), label="Graankade 300 m")
    d.add("HV-KADE", LineString([(-900, -225), (-600, -225)]), label="RoRo-kade 300 m")
    ship(d, -1464.5, -1235.5, -225, 1, 32.26, "Graanschip")
    ship(d, -860, -640, -225, 1, 37.7, "RoRo-schip")
    # LNG aan de noordzijde, tanks achter containerterrein
    d.add("HV-KADE", LineString([(-60, 1000), (650, 1000)]), label="LNG-steiger")
    ship(d, 504.5, 795.5, 1000, -1, 45.8, "LNG-schip")
    d.add("HV-LNG", rect(-560, -60, 1250, 1750), label="LNG-tanks")
    for k in range(3):
        d.add("HV-LNG", Point(-460 + 150 * k, 1500).buffer(45, 64))
    d.add("HV-CENTRALE", rect(-1700, -700, 1250, 1700), label="Centrale")
    # wegen/spoor
    d.add("HV-WEG", LineString([(-2650, -900), (-2650, 1200), (-60, 1200)]))
    d.add("HV-WEG", LineString([(-2650, -875), (-500, -875)]))
    d.add("HV-WEG", LineString([(-1100, -875), (-1100, -260)]), label="Weg door perceel")
    d.add("HV-SPOOR", LineString([(-2700, -900), (-2700, 1160), (-500, 1160)]))
    d.add("HV-RESERVE", rect(-2700, -1700, -825, -225), label="Reserve")
    # bespreekpunten markeren
    d.notes = dict(mouth_u=mouth_u, tc=tc, bwn=bwn, bws=bws, circle=circle, basin=basin, knik=knik, eind=eind)
    # maatvoering
    d.dim((-2100, 225), (-500, 225), 120, "containerkade 4 x 400 = 1.600 m")
    d.dim((-2300, -225), (-2300, 225), 150, "450 m")
    d.dim((-1500, -225), (-1200, -225), -110, "300 m")
    d.dim((-900, -225), (-600, -225), -110, "300 m")
    d.dim((-2100, 1125), (-2100, 225), 150, "900 m")
    d.dim((mouth_u, 175), (mouth_u, -175), 250, "350 m hart-hart")
    d.dim((knik[0], -110), (knik[0], 110), 300, "220 m")
    for k, nm, u, v in [("A1", "Kustpunt havenas", 0, 0), ("A2", "Middelpunt draaikom", *tc),
                        ("A3", "Midden havenmond", mouth_u, 0), ("A4", "Geulknik", *knik),
                        ("A5", "Eindpunt geul (voorlopig)", *eind)]:
        d.anchor_pt(k, nm, u, v)
    return d


# ======================================================================================
# DEFINITIEF ONTWERP (DO)
# ======================================================================================
def build_do():
    d = Design("DO")
    mouth_u = 2150.0
    tc = (450.0, 0.0)
    ch_end = mouth_u + 10000.0  # voorlopig: aansluiting op -18,2 m MLWS te verifiëren
    tug_u = mouth_u + 1500.0
    bwn = breakwater(d, [(-60, 1350), (1150, 1350), (1700, 1080), (2030, 640), (2150, 220)], "Noordelijke golfbreker")
    bws = breakwater(d, [(-60, -1650), (1150, -1650), (1700, -1330), (2030, -770), (2150, -220)], "Zuidelijke golfbreker")
    # geul en draaikom
    outer = rect(mouth_u, ch_end, -110, 110)
    inner = rect(tc[0], mouth_u, -110, 110)
    d.add("HV-GEUL", outer, label="Hoofdgeul 220 m, -18,20 m MLWS")
    d.add("HV-GEUL", inner)
    d.add("HV-GEUL-AS", LineString([(tc[0], 0), (ch_end, 0)]))
    circle = Point(tc).buffer(360, 128)
    d.add("HV-DRAAIKOM", circle, label="Vrije draaikom D 720 m")
    # LNG: steiger aan lijzijde zuidelijke golfbreker
    lng_env = rect(670, 1070, -1215, -1100)
    lng_route = LineString([tc, (870, -1050)]).buffer(150, cap_style="round")
    lng_pocket = rect(600, 1150, -1310, -1040)
    voorhaven = unary_union([inner, circle, rect(0, tc[0], -225, 225), lng_route, lng_pocket])
    d.add("HV-BAGGER", voorhaven, label="Voorhaven + LNG-insteek")
    # binnenbekken per fase (uitbreiding landinwaarts aan het doodlopende eind)
    basin_ph = [(-1600, 0, 1), (-1800, -1600, 2), (-2350, -1800, 3)]
    for a, b, ph in basin_ph:
        d.add("HV-BAGGER", rect(a, b, -225, 225), label=f"Binnenbekken F{ph}", phase=ph)
    basin = rect(-2350, 0, -225, 225)
    # containerterminal: fase 1 bij de ingang
    for a, b, ph, lab in [(-550, -1350, 1, "F1 2025: 2 lp, 800 m, 72 ha"),
                          (-1350, -1750, 2, "F2 2035: +1 lp, 108 ha"),
                          (-1750, -2150, 3, "F3 2045: +1 lp, 144 ha")]:
        d.add("HV-CONTAINER", rect(a, b, 225, 1125), label=lab, phase=ph)
        d.add("HV-KADE", LineString([(a, 225), (b, 225)]), phase=ph)
    berths(d, 225, -550, 4, 400, -1, BEAM, LOA, "C", [1, 1, 2, 3])
    # graan en RoRo, ieder eigen perceel en eigen inrit
    d.add("HV-GRAAN", rect(-1650, -1150, -825, -225), label="Graan 30 ha")
    d.add("HV-KADE", LineString([(-1500, -225), (-1200, -225)]), label="Graankade 300 m")
    ship(d, -1464.5, -1235.5, -225, 1, 32.26, "Graanschip")
    d.add("HV-GRAAN", rect(-1600, -1400, -700, -420), label=None)  # silo/opslag
    d.add("HV-LEIDING", LineString([(-1350, -225), (-1350, -420)]), style="dashed")  # transportband
    d.add("HV-RORO", rect(-1100, -600, -825, -225), label="RoRo 30 ha")
    d.add("HV-KADE", LineString([(-950, -225), (-650, -225)]), label="RoRo-kade 300 m")
    ship(d, -910, -690, -225, 1, 37.7, "RoRo-schip")
    d.add("HV-RORO", rect(-820, -780, -260, -225), label=None)  # ramp
    # havendiensten bij de ingang (zuid), reserve (noord)
    d.add("HV-HAVENDIENST", rect(-550, -60, -825, -225), label="Havendiensten/sleepboten")
    d.add("HV-KADE", LineString([(-450, -225), (-150, -225)]))
    d.add("HV-RESERVE", rect(-550, -60, 225, 1125), label="Reserve logistiek")
    d.add("HV-RESERVE", rect(-2750, -2150, 225, 1125), label="Railterminal/truckparking")
    d.add("HV-RESERVE", rect(-2750, -1700, -825, -225), label="Reserve fase 4")
    # LNG-zone en centrale
    d.add("HV-KADE", LineString([(-60, -1250), (870, -1250)]), label="LNG-steiger")
    d.add("HV-KADE", rect(820, 920, -1290, -1215))
    ship(d, 724.5, 1015.5, -1215, 1, 45.8, "GASLOG GREECE")
    d.add("HV-SCHIP", lng_env, label=None)
    for du in (700, 790, 950, 1040):
        d.add("HV-KADE", Point(du, -1225).buffer(10))
    d.add("HV-LNG", rect(-560, -60, -1500, -1000), label="LNG-tanks + hervergassing")
    tanks = [Point(-460 + 150 * k, -1130).buffer(45, 64) for k in range(3)]
    for t in tanks:
        d.add("HV-LNG", t)
    d.add("HV-LNG", Point(-460, -1290).buffer(45, 64), style="dashed", label=None)  # optie 4e tank
    d.add("HV-LNG", rect(-370, -90, -1460, -1360), label=None)  # hervergassing
    d.add("HV-CENTRALE", rect(-1650, -660, -1500, -1000), label="Centrale + utilities")
    # leidingen
    d.add("HV-LEIDING", LineString([(870, -1250), (-60, -1250)]), style="dashed")
    d.add("HV-LEIDING", LineString([(-370, -1410), (-660, -1410)]), style="dashed")
    d.add("HV-LEIDING", LineString([(-1650, -1450), (-2850, -1450)]), style="dashed")  # gasnet
    d.add("HV-LEIDING", LineString([(-1000, -1000), (-1000, -950), (-40, -950), (60, -950)]), style="dotted")  # koelwater inlaat
    d.add("HV-LEIDING", LineString([(-1200, -1500), (-1200, -1800), (300, -1800)]), style="dotted")  # koelwater uitlaat
    # weg en spoor achter de percelen
    d.add("HV-WEG", LineString([(-2800, -1600), (-2800, 1200), (-60, 1200)]))
    d.add("HV-WEG", LineString([(-2800, -875), (-60, -875)]))
    d.add("HV-WEG", LineString([(-3600, 0), (-2800, 0)]))
    d.add("HV-SPOOR", LineString([(-3600, 60), (-2850, 60), (-2850, 1150), (-600, 1150)]))
    d.add("HV-SPOOR", LineString([(-2850, -900), (-1150, -900)]))
    for gu, gv in [(-950, 1200), (-1550, 1200), (-1950, 1200), (-1400, -875), (-850, -875),
                   (-300, -875), (-310, -1000), (-1150, -1000)]:
        d.add("HV-WEG", Point(gu, gv).buffer(18), label=None)  # terminalpoorten
    # fasegrenzen
    for uu, t in [(-1350, "F1 | F2"), (-1750, "F2 | F3")]:
        d.add("HV-FASEGRENS", LineString([(uu, -225), (uu, 1125)]), label=t)
    d.add("HV-SLEEPBOOT", Point(tug_u, 0).buffer(60), label="Sleepbootkoppelpunt")
    d.notes = dict(mouth_u=mouth_u, tc=tc, bwn=bwn, bws=bws, circle=circle, basin=basin,
                   ch_end=ch_end, tug_u=tug_u, lng_env=lng_env, tanks=tanks, voorhaven=voorhaven)
    # maatvoering
    d.dim((-550, 225), (-2150, 225), -40, "containerkade 4 x 400 = 1.600 m (F1 800 / F2 1.200 / F3 1.600)")
    d.dim((-2350, -225), (-2350, 225), 160, "450 m")
    d.dim((-2150, 1125), (-2150, 225), 250, "900 m")
    d.dim((-1500, -225), (-1200, -225), 120, "300 m")
    d.dim((-950, -225), (-650, -225), 120, "300 m")
    d.dim((-1650, -825), (-1150, -825), 160, "500 m")
    d.dim((-1100, -825), (-600, -825), 160, "500 m")
    d.dim((-1650, -825), (-1650, -225), -120, "600 m")
    d.dim((mouth_u + 400, -110), (mouth_u + 400, 110), 180, "220 m")
    d.dim((mouth_u, 175), (mouth_u, -175), 420, "350 m vrij")
    d.dim((670, -1100), (1070, -1100), 130, "400 m")
    d.dim((mouth_u, 0), (tc[0], 0), 470, "1.700 m = 5,1 LOA")
    d.dim((tug_u, 0), (mouth_u, 0), 260, "1.500 m")
    for k, nm, u, v in [("A1", "Kustpunt havenas (waterlijn)", 0, 0),
                        ("A2", "Middelpunt vrije draaikom", *tc),
                        ("A3", "Midden havenmond", mouth_u, 0),
                        ("A4", "Sleepbootkoppelpunt", tug_u, 0),
                        ("A5", "Eindpunt geul (voorlopig)", ch_end, 0),
                        ("A6", "Wortel noordelijke golfbreker", -60, 1350),
                        ("A7", "Wortel zuidelijke golfbreker", -60, -1650),
                        ("A8", "Containerkade begin (F1)", -550, 225),
                        ("A9", "Containerkade eind (F3)", -2150, 225),
                        ("A10", "Midden LNG-ligplaats", 870, -1190),
                        ("A11", "Eind binnenbekken", -2350, 0)]:
        d.anchor_pt(k, nm, u, v)
    return d


# ======================================================================================
# Metingen en controles
# ======================================================================================
def area_ha(layer, d, phase_max=9, label_prefix=None):
    gs = [i["local"] for i in d.items if i["layer"] == layer and i["phase"] <= phase_max
          and (label_prefix is None or (i["label"] or "").startswith(label_prefix))]
    return unary_union(gs).area / 1e4 if gs else 0.0


def measure(d):
    n = d.notes
    m = {}
    m["havenmond_vrij_m"] = n["bwn"].distance(n["bws"])
    circ = n["circle"]
    m["draaikom_diameter_m"] = 720.0
    ships = unary_union([i["local"] for i in d.items if i["layer"] == "HV-SCHIP"])
    solid = unary_union([n["bwn"], n["bws"]] + [i["local"] for i in d.items if i["layer"] == "HV-KADE"])
    land = unary_union([i["local"] for i in d.items if i["layer"] in
                        ("HV-CONTAINER", "HV-GRAAN", "HV-RORO", "HV-HAVENDIENST", "HV-RESERVE", "HV-LNG", "HV-CENTRALE")])
    m["draaikom_vrij_van_schepen_m"] = circ.distance(ships)
    m["draaikom_vrij_van_kades_dammen_m"] = circ.distance(solid)
    m["draaikom_overlap_land_m2"] = circ.intersection(land).area
    m["draaikom_overlap_land_m2"] += circ.difference(unary_union([n["basin"], rect(0, 5000, -5000, 5000)])).area
    m["stopweg_mond_draaikom_m"] = n["mouth_u"] - n["tc"][0]
    m["stopweg_in_LOA"] = m["stopweg_mond_draaikom_m"] / LOA
    if d.code == "DO":
        m["geullengte_buiten_mond_m"] = n["ch_end"] - n["mouth_u"]
        m["geullengte_totaal_vanaf_draaikom_m"] = n["ch_end"] - n["tc"][0]
        m["lng_ligplaats_tot_draaikom_m"] = n["lng_env"].distance(circ)
        m["lng_tank_tot_roro_m"] = unary_union(n["tanks"]).distance(rect(-1100, -600, -825, -225))
        m["sleepboot_buiten_mond_m"] = n["tug_u"] - n["mouth_u"]
        # bebouwing aan de kust ten zuiden: N 7.646.300 (uit luchtfoto)
        tanks_w = to_world(unary_union(n["tanks"]))
        m["lng_tank_tot_kustbebouwing_zuid_m"] = tanks_w.bounds[1] - 7646300.0
        m["geul_buiten_m2"] = 220 * m["geullengte_buiten_mond_m"]
    else:
        knik, eind = n["knik"], n["eind"]
        m["geullengte_buiten_mond_m"] = LineString([(n["mouth_u"], 0), knik, eind]).length
    m["containerkade_m"] = {ph: sum(i["local"].length for i in d.items if i["layer"] == "HV-KADE"
                                    and i["phase"] <= ph and abs(i["local"].bounds[1] - 225) < 1
                                    and i["local"].geom_type == "LineString") for ph in (1, 2, 3)}
    if d.code == "SO":
        m["containerkade_m"] = {1: 800.0, 2: 1200.0, 3: 1600.0}
    m["container_ha"] = {ph: area_ha("HV-CONTAINER", d, ph) for ph in (1, 2, 3)}
    m["graan_ha"] = area_ha("HV-GRAAN", d, label_prefix="Graan")
    m["roro_ha"] = area_ha("HV-RORO", d, label_prefix="RoRo") if d.code == "DO" else area_ha("HV-RORO", d)
    m["lng_zone_ha"] = rect(-560, -60, -1500, -1000).area / 1e4
    m["centrale_ha"] = area_ha("HV-CENTRALE", d)
    m["havendienst_ha"] = area_ha("HV-HAVENDIENST", d)
    m["reserve_ha"] = area_ha("HV-RESERVE", d)
    bag = [i for i in d.items if i["layer"] == "HV-BAGGER"]
    m["binnenbekken_m2"] = {ph: unary_union([i["local"] for i in bag if (i["label"] or "").startswith("Binnenbekken")
                                             and i["phase"] <= ph]).area for ph in (1, 2, 3)}
    m["voorhaven_bagger_m2"] = unary_union([i["local"] for i in bag if not (i["label"] or "").startswith("Binnenbekken")]).area
    m["havenbekken_totaal_m2"] = unary_union([i["local"] for i in bag]).area
    m["vrije_breedte_binnenbekken_m"] = 450 - (5 + BEAM) - (5 + 37.7)
    terr = ["HV-CONTAINER", "HV-GRAAN", "HV-RORO", "HV-HAVENDIENST", "HV-LNG", "HV-CENTRALE"]
    m["terreinophoging_m2"] = unary_union([i["local"] for i in d.items if i["layer"] in terr]).area
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
    print(json.dumps(dict(SO=so.m, DO=do.m), indent=1, default=str))


if __name__ == "__main__":
    main()
