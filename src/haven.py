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
    "HV-VOORHAVEN": (151, "#1d5c9e", 0.45, "Voorhaven binnen de dammen (strandwal ontgraven)"),
    "HV-BAGGER": (5, "#123f7a", 0.72, "Gebaggerd tot -18,20 m MLWS (voorlopig)"),
    "HV-GEUL": (5, "#4cc9f0", None, "Geul 220 m bodembreedte"),
    "HV-GEUL-AS": (1, "#ffffff", None, "Vaarwegas"),
    "HV-DRAAIKOM": (2, "#ffd60a", None, "Vrije draaikom D = 720 m"),
    "HV-HAVENMOND": (2, "#ffd60a", None, "Havenmond vrij 350 m"),
    "HV-GOLFBREKER": (8, "#adb5bd", 1.0, "Golfbreker (footprint 90 m, voorlopig)"),
    "HV-KADE": (7, "#ffffff", None, "Kade / steiger"),
    "HV-SCHIP": (3, "#80ffdb", 0.35, "Scheepsenveloppe aan ligplaats"),
    "HV-CONTAINER": (30, "#f77f00", 0.55, "Containerterminal"),
    "HV-GRAAN": (50, "#ffd166", 0.55, "Graanterminal"),
    "HV-RORO": (110, "#06d6a0", 0.55, "RoRo / voertuigenterminal"),
    "HV-LNG": (1, "#ef233c", 0.55, "LNG-steiger, tanks en hervergassing"),
    "HV-CENTRALE": (200, "#c77dff", 0.55, "Centrale + utilities (reservering)"),
    "HV-HAVENDIENST": (150, "#4ea8de", 0.55, "Havendiensten, sleepboten, loodsen"),
    "HV-RESERVE": (9, "#dee2e6", 0.40, "Reserveterrein / latere uitbreiding"),
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
    "HV-D-VERKEER": (9, "#e9ecef", 0.25, "Detail: apron, rijstroken, stackzone"),
    "HV-D-STACK": (32, "#8d5a2b", 0.85, "Detail: stackblokken containers (RTG)"),
    "HV-D-REEFER": (140, "#00b4d8", 0.85, "Detail: reefervakken"),
    "HV-D-LEEG": (250, "#adb5bd", 0.85, "Detail: lege containers"),
    "HV-D-KRAAN": (7, "#ffffff", 0.9, "Detail: kranen, kraanbanen, laadarmen"),
    "HV-D-GEBOUW": (8, "#495057", 0.9, "Detail: gebouwen"),
    "HV-D-OPSLAG": (51, "#f1faee", 0.85, "Detail: silo's, tanks, opslag"),
    "HV-D-PARKEER": (112, "#2d6a4f", 0.7, "Detail: parkeervakken"),
    "HV-D-INSTALLATIE": (211, "#7b2cbf", 0.85, "Detail: installaties en dolphins"),
}


class Design:
    def __init__(self, code, tf=None):
        self.code = code
        self.tf = tf or to_world  # lokale ontwerpcoördinaten -> EPSG:31984
        self.center = None
        self.version = "1.0"
        self.detail_views = []
        self.scale = 10000
        self.info = {}
        self.items = []  # dicts: layer, geom (wereld), label, phase, style
        self.dims = []  # (p1, p2, offset_m, tekst)  in wereldcoördinaten
        self.notes = []
        self.anchor = {}
        self.m = {}  # maatstaat

    def add(self, layer, g_local, label=None, phase=1, **kw):
        g = self.tf(g_local)
        self.items.append(dict(layer=layer, geom=g, local=g_local, label=label, phase=phase, **kw))
        return g

    def P(self, u, v):
        q = self.tf(Point(u, v))
        return (q.x, q.y)

    def dim(self, p1, p2, off, text):
        self.dims.append((self.P(*p1), self.P(*p2), off, text))

    def anchor_pt(self, key, name, u, v):
        e, n = self.P(u, v)
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
def nl0(x):
    return f"{x:,.0f}".replace(",", ".")


def build_so():
    return build_do_render(so=True)


def build_do():
    return build_do_render()


# ======================================================================================
# DEFINITIEF ONTWERP: overgetrokken van de Porto Central-render (Referentie/Porto_Central_render.png)
#   De render (1133 x 559 px, noord ongeveer boven) is in pixelcoördinaten overgetrokken en
#   met één gelijkvormigheidstransformatie op de echte kust gezet:
#     schaal  RENDER_S m/pixel (containervinger = 144 ha en containerkade = 1.600 m)
#     draaiing zo dat de kustlijn van de render op de waterlijn van 3-7-2026 valt
#     ankerpunt render (812,5; 275) = A1 op de kust (E 297.135, N 7.650.000)
#   Vingers en insteekbekkens lopen evenwijdig aan de kust (helling dx/dy = -0,5 in de render).
# ======================================================================================
RENDER_FILE = "Porto_Central_render.png"
RENDER_SIZE = (1133, 559)
RENDER_S = 10.035
RENDER_ANCHOR = ((812.5, 275.0), (297135.0, 7650000.0))
# Geullengte buiten de mond (voorlopig). Porto Central meldt een toegang van ca. 26 km tot ca. -25 m; bij een
# vergelijkbare helling van de kustbodem ligt de -18,2 m-lijn rond 18 km. Na inlezen van de bathymetrie bijstellen.
GEUL_LENGTE_M = 18000.0


def render_coast_x(y):
    """Oorspronkelijke kustlijn in de render (strand noord bij (860,180), zuid bij (700,500))."""
    return 860.0 - 0.5 * (y - 180.0)


def render_affine(phi_deg, s=RENDER_S):
    c, sn = math.cos(math.radians(phi_deg)), math.sin(math.radians(phi_deg))
    a, b, d_, e = s * c, s * sn, s * sn, -s * c
    (x0, y0), (E0, N0) = RENDER_ANCHOR
    return [a, b, d_, e, E0 - (a * x0 + b * y0), N0 - (d_ * x0 + e * y0)]


def fit_render_rotation(coast):
    """Draaiing (graden, tegen de klok in) waarbij de renderkust het best op de echte kust valt."""
    best = None
    for k in range(-40, 121):
        phi = k / 10.0
        A = render_affine(phi)
        pts = [Point(A[0] * render_coast_x(y) + A[1] * y + A[4], A[2] * render_coast_x(y) + A[3] * y + A[5])
               for y in range(190, 486, 5)]
        err = float(np.mean([p.distance(coast) for p in pts]))
        if best is None or err < best[1]:
            best = (phi, err)
    return best


def _slant(x_top, y_top, y):
    return x_top - 0.5 * (y - y_top)


def _para(x_left_top, x_right_top, y0, y1):
    """Parallellogram tussen twee schuine lijnen (helling -0,5) van y0 tot y1."""
    return Polygon([(_slant(x_left_top, y0, y0), y0), (_slant(x_right_top, y0, y0), y0),
                    (_slant(x_right_top, y0, y1), y1), (_slant(x_left_top, y0, y1), y1)])


def _ship_along(p0, p1, side, beam_m, label, d, phase=1, length_m=None):
    """Scheepsenveloppe langs een kade p0->p1 (render-px); side +1 = links van de looprichting (beeld)."""
    s = RENDER_S
    x0, y0 = p0
    x1, y1 = p1
    L = math.hypot(x1 - x0, y1 - y0)
    tx, ty = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = ty * side, -tx * side  # loodrecht, links van de looprichting in beeldcoördinaten (y omlaag)
    if length_m:
        mid = ((x0 + x1) / 2, (y0 + y1) / 2)
        h = length_m / s / 2
        x0, y0, x1, y1 = mid[0] - tx * h, mid[1] - ty * h, mid[0] + tx * h, mid[1] + ty * h
    o0, o1 = 5.0 / s, (5.0 + beam_m) / s
    g = Polygon([(x0 + nx * o0, y0 + ny * o0), (x1 + nx * o0, y1 + ny * o0),
                 (x1 + nx * o1, y1 + ny * o1), (x0 + nx * o1, y0 + ny * o1)])
    d.add("HV-SCHIP", g, label=label, phase=phase, tag="schip")
    return g


def build_do_render(coast=None, so=False):
    """Haven naar de Porto Central-render (vingers en insteekbekkens), alleen met de functies uit de opdracht.

    DO: containerkade aan de voorhavenzijde van vinger 6 (geen bocht naar een insteek voor schepen van 334 m);
        graan aan de noordkade en RoRo op vinger 7/8, met een draaikom binnenhaven D 460 m (2 x LOA graan/RoRo)
        op de kruising hoofdbekken / insteekbekken (op de plaats van de -16 m-cirkel in de render).
    SO: eerste schets met de bespreekpunten, o.a. containerkade in het insteekbekken (bocht voor 334 m niet haalbaar).
    """
    if coast is None:
        coast = LineString(json.load(open(os.path.join(OND, "coast.json"))))
    phi, err = fit_render_rotation(coast)
    A = render_affine(phi)
    d = Design("SO" if so else "DO", tf=lambda g: affinity.affine_transform(g, A))
    d.version = "4.0" if so else "6.0"
    d.info = dict(render_schaal_m_per_px=RENDER_S, render_draaiing_graden=phi, render_kustfit_gem_afwijking_m=err,
                  render_affine=A, render_anker=RENDER_ANCHOR)
    s = RENDER_S
    GEUL = GEUL_LENGTE_M

    # --- havenmond (14), draaikom en golfbrekers (11) -------------------------------------------
    T = (815.0, 312.0) if so else (845.0, 320.0)
    M = (990.0, 370.0) if so else (1007.0, 376.0)
    L = math.hypot(M[0] - T[0], M[1] - T[1])
    dv = ((M[0] - T[0]) / L, (M[1] - T[1]) / L)
    nv = (-dv[1], dv[0])
    half = (175.0 if so else 175.0 + 45.0) / s
    hn = (M[0] - nv[0] * half, M[1] - nv[1] * half)
    hs = (M[0] + nv[0] * half, M[1] + nv[1] * half)
    bw = 45.0 / s

    def dam(pts, name):
        cl = LineString(pts)
        fp = cl.buffer(bw, cap_style="round", join_style="round")
        d.add("HV-GOLFBREKER", fp, label=name, tag="dam")
        d.add("HV-GEUL-AS", cl, style="dashdot")
        return fp

    noord = [(835, 186), (860, 183), (887, 190), (924, 204), (960, 226), (985, 249)]
    zuid = [(690, 482), (742, 477), (878, 470)]
    if so:
        noord += [(995, 278), (999, 312), hn]
        zuid += [(905, 460), (928, 441), (948, 419), (966, 401), hs]
    else:
        noord += [(1000, 280), (1010, 318), hn]
        zuid += [(912, 462), (942, 445), (966, 425), (986, 408), hs]
    bwn = dam(noord, "Noordelijke golfbreker")
    bws = dam(zuid, "Zuidelijke golfbreker")

    # --- toegangsgeul en sleepboten --------------------------------------------------------------
    knik = None
    if so:
        knik = (M[0] + dv[0] * 2200 / s, M[1] + dv[1] * 2200 / s)
        a2 = math.atan2(dv[1], dv[0]) - math.radians(15)
        eind = (knik[0] + math.cos(a2) * (GEUL - 2200) / s, knik[1] + math.sin(a2) * (GEUL - 2200) / s)
        geul = LineString([M, knik, eind]).buffer(110 / s, cap_style="flat", join_style="mitre")
    else:
        eind = (M[0] + dv[0] * GEUL / s, M[1] + dv[1] * GEUL / s)
        geul = LineString([M, eind]).buffer(110 / s, cap_style="flat")
    d.add("HV-GEUL", geul, label="Hoofdgeul 220 m, -18,20 m MLWS")
    inner = LineString([T, M]).buffer(110 / s, cap_style="flat")
    d.add("HV-GEUL", inner)
    d.add("HV-GEUL-AS", LineString([T, M] + ([knik] if knik else []) + [eind]))
    circle = Point(T).buffer(360 / s, 128)
    d.add("HV-DRAAIKOM", circle, label="Vrije draaikom D 720 m")
    tug = (M[0] + dv[0] * 1500 / s, M[1] + dv[1] * 1500 / s)
    if not so:
        d.add("HV-SLEEPBOOT", Point(tug).buffer(60 / s), label="Sleepbootkoppelpunt")

    # --- vingers en bekkens zoals de render ----------------------------------------------------------
    Y_MB0, Y_MB1 = 256.0, 293.0          # hoofdbekken
    Y_TOP, Y_BOT = 297.0, 440.0          # vingers
    f6 = _para(692, 792, Y_TOP, Y_BOT)   # containervinger (6)
    f78 = _para(521, 630, Y_MB1, Y_BOT)  # tweede vinger (7/8)
    slip1 = Polygon([(630, Y_MB1), (_slant(692, Y_TOP, Y_MB1), Y_MB1), (_slant(692, Y_TOP, Y_BOT), Y_BOT),
                     (_slant(630, Y_MB1, Y_BOT), Y_BOT)])
    slip2 = _para(476, 521, Y_MB1, Y_BOT)
    toegang = unary_union([LineString([(800, 275), T]).buffer(200 / s, cap_style="flat"), box(780, Y_MB0, 812, Y_MB1)])

    voorhaven = Polygon([(792, Y_TOP), (_slant(792, Y_TOP, Y_BOT), Y_BOT), (712, 446), (700, 474)] + zuid[1:] +
                        list(reversed(noord[1:])) + [(840, 212), (832, 240), (815, Y_MB0), (805, Y_MB0), (805, Y_MB1)]
                        ).buffer(0).difference(unary_union([bwn, bws]))
    d.add("HV-VOORHAVEN", voorhaven, label="Voorhaven", tag="voorhaven_water")
    lng_berth = (896.0, 414.0)
    lng_route = LineString([T, lng_berth]).buffer(150 / s, cap_style="round")
    d.add("HV-BAGGER", unary_union([inner, circle, toegang, lng_route]), label="Voorhaven + toegang", tag="voorhaven")

    TB = (665.0, 285.0)                     # draaikom binnenhaven (-16 m-cirkel in de render)
    circle_b = Point(TB).buffer(230 / s, 96)
    if so:
        d.add("HV-BAGGER", box(476, Y_MB0, 805, Y_MB1), label="Hoofdbekken", tag="bekken")
        d.add("HV-BAGGER", slip1, label="Insteekbekken containers", tag="bekken")
        d.add("HV-BAGGER", slip2, label="Insteekbekken 2", tag="bekken")
    else:
        d.add("HV-BAGGER", unary_union([box(625, Y_MB0, 805, Y_MB1), circle_b]), label="Hoofdbekken", tag="bekken")
        d.add("HV-DRAAIKOM", circle_b, label="Draaikom binnenhaven D 460 m")
        d.add("HV-BAGGER", slip1.intersection(box(0, Y_MB1, 2000, 352)), label="Insteek RoRo", tag="bekken")
        d.add("HV-BAGGER", slip1.intersection(box(0, 352, 2000, Y_BOT)), label="Reserve insteek (na 2045)", phase=4,
              style="dashed", tag="reserve_water")
        d.add("HV-BAGGER", box(476, Y_MB0, 625, Y_MB1), label="Reserve hoofdbekken (na 2045)", phase=4, style="dashed",
              tag="reserve_water")
        d.add("HV-BAGGER", slip2, label="Reserve insteek 2 (na 2045)", phase=4, style="dashed", tag="reserve_water")

    # --- containerterminal (vinger 6) ------------------------------------------------------------------
    lab = {1: "F1 2025: 2 lp, 800 m, 72 ha", 2: "F2 2035: +1 lp, 108 ha", 3: "F3 2045: +1 lp, 144 ha"}
    if so:
        yc, order, bph = [Y_TOP, 332.75, 368.5, Y_BOT], (3, 2, 1), [3, 2, 1, 1]
        k0, k1, side = (692.0, Y_TOP), (_slant(692, Y_TOP, Y_BOT), Y_BOT), -1      # westzijde, in de insteek
    else:
        yc, order, bph = [Y_TOP, 368.5, 404.25, Y_BOT], (1, 2, 3), [1, 1, 2, 3]
        k0, k1, side = (792.0, Y_TOP), (_slant(792, Y_TOP, Y_BOT), Y_BOT), 1       # oostzijde, aan de voorhaven
        for k, ph in enumerate(order):
            pocket = _para(792, 830, Y_TOP, Y_BOT).intersection(box(0, yc[k], 2000, yc[k + 1]))
            d.add("HV-BAGGER", pocket, label="Ligplaatsen containers" if ph == 1 else None, phase=ph, tag="bekken")
    for k, ph in enumerate(order):
        d.add("HV-CONTAINER", f6.intersection(box(0, yc[k], 2000, yc[k + 1])), label=lab[ph], phase=ph, tag="cyard")
    seg = [(k0[0] + (k1[0] - k0[0]) * t / 4, k0[1] + (k1[1] - k0[1]) * t / 4) for t in range(5)]
    for i, ph in enumerate(bph):
        d.add("HV-KADE", LineString([seg[i], seg[i + 1]]), phase=ph, tag="ckade")
        _ship_along(seg[i], seg[i + 1], side, BEAM, f"C{i + 1}", d, phase=ph, length_m=LOA)
    if not so:
        for ph, yy in ((2, 368.5), (3, 404.25)):
            d.add("HV-FASEGRENS", LineString([(_slant(692, Y_TOP, yy), yy), (_slant(830, Y_TOP, yy), yy)]),
                  label="F1 | F2" if ph == 2 else "F2 | F3")

    # --- graan (noordkade), RoRo (vinger 7/8), havendienst ---------------------------------------------
    if so:
        d.add("HV-GRAAN", Polygon([(652, 199), (835, 199), (840, 212), (832, 240), (815, Y_MB0), (652, Y_MB0)]),
              label="Graan + RoRo gedeeld perceel", tag="graan_plot")
        r0, r1 = (780.0, Y_MB0), (810.0, Y_MB0)
        d.add("HV-KADE", LineString([r0, r1]), label="RoRo-kade 300 m")
        _ship_along(r1, r0, 1, 37.7, "RoRo-schip", d, length_m=219.9)
        d.add("HV-WEG", LineString([(763, 190), (763, Y_MB0 - 2)]), label="Weg door perceel")
        d.add("HV-RESERVE", f78, label="Uitbreiding (na 2045)")
    else:
        roro = _para(580, 630, Y_MB1, 353)
        d.add("HV-RORO", roro, label="RoRo 30 ha", tag="roro_plot")
        r0, r1 = (_slant(630, Y_MB1, 310), 310.0), (_slant(630, Y_MB1, 336.7), 336.7)
        d.add("HV-KADE", LineString([r0, r1]), label="RoRo-kade 300 m")
        _ship_along(r0, r1, 1, 37.7, "RoRo-schip", d, length_m=219.9)
        rm = ((r0[0] + r1[0]) / 2, (r0[1] + r1[1]) / 2)  # ramp (hekramp) midden aan de kade, landinwaarts
        d.add("HV-RORO", Polygon([(rm[0] - 1.3, rm[1] - 2.2), (rm[0] + 0.9, rm[1] + 2.2), (rm[0] - 3.4, rm[1] + 3.6),
                                  (rm[0] - 5.6, rm[1] - 0.8)]), label="ramp")
        d.add("HV-WEG", LineString(roro.buffer(-60 / s).exterior.coords), style="dashed", label="rijcircuit RoRo")
        d.add("HV-RORO", box(_slant(580, Y_MB1, 345) + 1, 343, _slant(580, Y_MB1, 345) + 9, 350), label="inspectie")
        d.add("HV-RESERVE", f78.difference(roro), label="Uitbreiding eigen terminals (na 2045)")
        d.add("HV-GRAAN", box(705, 199, 758, Y_MB0), label="Graan 30 ha", tag="graan_plot")
        d.add("HV-GRAAN", box(715, 205, 745, 230))  # silo's
        d.add("HV-LEIDING", LineString([(731, 230), (731, Y_MB0)]), style="dashed")
        d.add("HV-HAVENDIENST", Polygon([(758, 199), (835, 199), (840, 212), (832, 240), (815, Y_MB0), (758, Y_MB0)]),
              label="Havendienst/sleepboten", tag="havendienst")
        d.add("HV-KADE", LineString([(775, Y_MB0), (805, Y_MB0)]))
    d.add("HV-KADE", LineString([(716, Y_MB0), (746, Y_MB0)]), label="Graankade 300 m")
    _ship_along((746, Y_MB0), (716, Y_MB0), 1, 32.26, "Graanschip", d, length_m=229)

    # --- zuidrand (9): LNG-zone en centrale ---------------------------------------------------------
    Y_T0, Y_T1 = 450.0, 486.0
    d.add("HV-LNG", box(612, Y_T0, 700, Y_T1), label="LNG-tanks + hervergassing", tag="lng_zone")
    tanks = [Point(626 + 15 * k, 456 if so else 474).buffer(45 / s, 64) for k in range(3)]
    for t in tanks:
        d.add("HV-LNG", t, tag="tank")
    if not so:
        d.add("HV-LNG", Point(671, 474).buffer(45 / s, 64), style="dashed")  # optie 4e tank (N-1)
        d.add("HV-LNG", box(622, 454, 690, 461))  # hervergassing
    d.add("HV-CENTRALE", box(480, Y_T0, 600, Y_T1), label="Centrale + utilities", tag="centrale")

    j0, j1 = (884.0, 467.0), (902.0, 418.0)
    d.add("HV-KADE", LineString([j0, j1]), label="LNG-steiger")
    jl = math.hypot(j1[0] - j0[0], j1[1] - j0[1])
    jt = ((j1[0] - j0[0]) / jl, (j1[1] - j0[1]) / jl)
    d.add("HV-KADE", Point(j1).buffer(40 / s, cap_style="square"))
    b0 = (j1[0] - jt[0] * 200 / s, j1[1] - jt[1] * 200 / s)
    b1 = (j1[0] + jt[0] * 200 / s, j1[1] + jt[1] * 200 / s)
    _ship_along(b0, b1, 1, 45.8, "GASLOG GREECE", d, length_m=290.9)
    nx, ny = jt[1], -jt[0]
    o = 120.0 / s
    lng_env = Polygon([b0, b1, (b1[0] + nx * o, b1[1] + ny * o), (b0[0] + nx * o, b0[1] + ny * o)])
    d.add("HV-SCHIP", lng_env, tag="lng_env")

    # --- detaillering terminals (alleen DO) ------------------------------------------------------------
    if not so:
        add_terminal_details(d, f6, roro, j0, j1, b0, b1, jt)

    # --- leidingen, wegen en spoor (ringweg zoals de render) ---------------------------------------------
    d.add("HV-LEIDING", LineString([j0, (878, 474), (742, 481), (700, 474), (690, 468)]), style="dashed")
    d.add("HV-LEIDING", LineString([(622, 458), (600, 458)]), style="dashed")
    d.add("HV-LEIDING", LineString([(480, 482), (300, 482)]), style="dashed")  # gasnet
    if not so:
        d.add("HV-LEIDING", LineString([(840, 400), (725, 446), (600, 452)]), style="dotted")  # koelwater in
        d.add("HV-LEIDING", LineString([(535, Y_T1), (535, 500), (740, 500), (760, 495)]), style="dotted")  # koelwater uit
    d.add("HV-WEG", LineString([(300, 300), (430, 300)]), label="Aansluiting regionaal net")
    d.add("HV-WEG", LineString([(430, 190), (845, 190)]), label="Noordweg")
    d.add("HV-WEG", LineString([(430, 190), (430, 444), (712, 444)]), label="Ringweg")
    d.add("HV-WEG", LineString([(_slant(521, Y_MB1, Y_BOT) + 4, 444), (_slant(580, Y_MB1, 353) - 3, 353)]), style="dashed")
    d.add("HV-SPOOR", LineString([(300, 306), (424, 306), (424, 196), (760, 196)]))
    d.add("HV-SPOOR", LineString([(424, 306), (424, 448), (650, 448), (655, 440)]))
    for g in [(731, 199), (795, 199), (660, 444), (650, 450), (540, 450), (_slant(521, Y_MB1, Y_BOT) + 4, 444)]:
        d.add("HV-WEG", Point(g).buffer(18 / s))  # poorten

    vrij = (Y_MB1 - Y_MB0) * s - (5 + 32.26)
    inb = (-dv[0], -dv[1])
    bocht_hb = math.degrees(math.acos(max(-1, min(1, -inb[0]))))
    sl = (-0.5 / math.hypot(0.5, 1), 1 / math.hypot(0.5, 1))
    bocht_insteek = math.degrees(math.acos(-sl[0]))
    ships_all = [i["local"] for i in d.items if i["layer"] == "HV-SCHIP"]
    d.notes = dict(M=M, T=T, hn=hn, hs=hs, stop=L * s, knik=knik, tug=tug, eind=eind, geul_lengte=GEUL,
                   bwn=bwn, bws=bws, circle=circle, lng_env=lng_env, tanks=tanks,
                   vrije_breedte=vrij, breedte_insteek=62 * s * math.cos(math.atan(0.5)),
                   breedte_hoofdbekken=(Y_MB1 - Y_MB0) * s, bocht_hoofdbekken=bocht_hb,
                   bocht_insteek=bocht_insteek,
                   draaikom_binnen_vrij_m=None if so else circle_b.distance(unary_union(ships_all)) * s)

    # --- maatvoering (offsets in m) -------------------------------------------------------------------
    d.dim(seg[0], seg[4], 170 if not so else -170, "containerkade 4 x 400 = 1.600 m")
    d.dim((692, Y_BOT), (792, Y_BOT), -80, f"{nl0(100 * s * math.cos(math.atan(0.5)))} m")
    d.dim((716, Y_MB0), (746, Y_MB0), -90, "300 m")
    d.dim(r0, r1, (-110 if not so else 90), "300 m")
    d.dim((705, 199), (758, 199), 70, "530 m")
    d.dim((600, Y_MB0), (600, Y_MB1), 120, f"{nl0((Y_MB1 - Y_MB0) * s)} m")
    d.dim((_slant(630, Y_MB1, 330), 330), (_slant(692, Y_TOP, 330), 330), -60,
          f"{nl0(62 * s * math.cos(math.atan(0.5)))} m")
    d.dim(b0, b1, -70, "400 m")
    cw = 110 / s
    pm = (M[0] + dv[0] * 50, M[1] + dv[1] * 50)
    d.dim((pm[0] - nv[0] * cw, pm[1] - nv[1] * cw), (pm[0] + nv[0] * cw, pm[1] + nv[1] * cw), 200, "220 m")
    if so:
        d.dim(hn, hs, 300, "350 m hart-hart")
    else:
        d.dim(tug, M, 260, "1.500 m")
        d.dim((hn[0] + nv[0] * bw, hn[1] + nv[1] * bw), (hs[0] - nv[0] * bw, hs[1] - nv[1] * bw), 300, "350 m vrij")
        d.dim((TB[0] - 230 / s, TB[1]), (TB[0] + 230 / s, TB[1]), 0.1, "D 460 m")
    d.dim(M, T, -380, f"{nl0(L * s)} m = {L * s / LOA:.1f} LOA".replace(".", ","))

    pts = [("A1", "Referentiepunt kust (render 812,5 / 275)", RENDER_ANCHOR[0]),
           ("A2", "Middelpunt vrije draaikom", T), ("A3", "Midden havenmond", M),
           ("A4", "Geulknik" if so else "Sleepbootkoppelpunt", knik if so else tug),
           ("A5", "Eindpunt geul (voorlopig)", eind),
           ("A6", "Wortel noordelijke golfbreker", noord[0]), ("A7", "Wortel zuidelijke golfbreker", zuid[0]),
           ("A8", "Containerkade noordeinde", seg[0]), ("A9", "Containerkade zuideinde", seg[4]),
           ("A10", "LNG-steigerkop", j1), ("A11", "Graankade midden", (731, Y_MB0)),
           ("A12", "RoRo-kade midden", ((r0[0] + r1[0]) / 2, (r0[1] + r1[1]) / 2))]
    if not so:
        pts.append(("A13", "Middelpunt draaikom binnenhaven", TB))
    for k, nm, p in pts:
        d.anchor_pt(k, nm, *p)
    d.notes["markup_pos"] = [(M[0], M[1], 300), (T[0], T[1], 450), (1035, 385, 250), (650, 452, 350), (745, 225, 420),
                             (668, 300, 380), (650, 400, 330)]
    d.center = d.P(700, 335)
    d.scale = 12500
    return d


# ======================================================================================
# Detaillering van de terminals (DO-06 t/m DO-08)
#   Alle maten in meters; de containerterminal is uitgewerkt in een eigen raster langs de kade:
#   a = langs de kade vanaf de noordkop, b = loodrecht landinwaarts vanaf de kadelijn.
# ======================================================================================
DET = {}


def add_terminal_details(d, f6, roro, j0, j1, b0, b1, jt):
    s = RENDER_S
    det = {}

    # ---------------- containerterminal (vinger 6) ----------------
    Q0 = (792.0, 297.0)
    t = (-1 / math.sqrt(5), 2 / math.sqrt(5))     # langs de kade, naar het zuiden
    n = (-2 / math.sqrt(5), -1 / math.sqrt(5))    # loodrecht landinwaarts
    QL, DEP = 1604.0, 897.0                       # kadelengte en diepte vinger (m)

    def F(a, b):
        return (Q0[0] + (a * t[0] + b * n[0]) / s, Q0[1] + (a * t[1] + b * n[1]) / s)

    def Fs(ap, b):  # scheve coördinaat: a' = a - 0,5 b (volgt de noord- en zuidrand van de vinger)
        return F(ap + 0.5 * b, b)

    def poly(pts, shear=True):
        return Polygon([Fs(*p) if shear else F(*p) for p in pts])

    def phase_of(g):
        y = g.centroid.y
        return 1 if y < 368.5 else (2 if y < 404.25 else 3)

    # apron en kraanbaan
    d.add("HV-D-VERKEER", poly([(0, 0), (QL, 0), (QL, 60), (0, 60)]), dlabel="kade-apron 60 m")
    for bb in (3.0, 33.5):
        d.add("HV-D-KRAAN", LineString([Fs(0, bb), Fs(QL, bb)]), dlabel="kraanbaan (spoorwijdte 30,5 m)" if bb == 3 else None)
    # STS-kranen: 3/4/5 per schip -> 6/12/20 in operatie (rekenboek Containers r19)
    nk = {1: 0, 2: 0, 3: 0}
    for i in range(4):
        for j in range(5):
            ph = 1 if (i < 2 and j < 3) else (2 if (i < 3 and j < 4) else 3)
            a = 400 * i + 60 + 70 * j
            g = poly([(a - 13.5, -50), (a + 13.5, -50), (a + 13.5, 40), (a - 13.5, 40)], shear=False)
            d.add("HV-D-KRAAN", g, phase=ph, dlabel=f"STS {sum(nk.values()) + 1}" if j == 0 else None)
            nk[ph] += 1
    det["sts_per_fase"] = {1: nk[1], 2: nk[1] + nk[2], 3: nk[1] + nk[2] + nk[3]}

    # stackblokken (RTG): blok 24 m breed, rijpad 12 m, blokken 300 m lang met dwarspaden van 25 m
    B_START, B_END = 90.0, 798.0
    blocks, area = [], 0.0
    b_row = B_START
    row = 0
    while b_row + 24 <= B_END + 1e-6:
        ap = 30.0
        while ap < QL - 30:
            ae = min(ap + 300, QL - 30)
            g = poly([(ap, b_row), (ae, b_row), (ae, b_row + 24), (ap, b_row + 24)]).intersection(f6)
            kind = "reefer" if (row >= 17 and ap < 340) else ("leeg" if (row >= 17 and ap > 1300) else "stack")
            ph = phase_of(g)
            lay = {"stack": "HV-D-STACK", "reefer": "HV-D-REEFER", "leeg": "HV-D-LEEG"}[kind]
            lab = {"stack": None, "reefer": "reefer", "leeg": "lege containers"}[kind]
            d.add(lay, g, phase=ph, dlabel=lab if (ap == 30.0 or kind != "stack") and row in (17, 18) else None)
            blocks.append((g, ph))
            ap = ae + 25
        b_row += 36
        row += 1
    zone = poly([(0, B_START), (QL, B_START), (QL, B_END), (0, B_END)]).intersection(f6)
    d.add("HV-D-VERKEER", zone, style="dashed", dlabel=None)
    det["stack_bruto_m2"] = zone.area * s * s
    det["stack_blokken_m2"] = sum(g.area for g, _ in blocks) * s * s
    det["teu_grondslots"] = det["stack_bruto_m2"] / 28.0          # rekenboek Invoer D30: 28 m2 per TEU-grondslot
    det["teu_grondslots_per_fase"] = {}
    for ph in (1, 2, 3):
        zph = zone.intersection(box(0, 0, 2000, [368.5, 404.25, 440.0][ph - 1]))
        det["teu_grondslots_per_fase"][ph] = zph.area * s * s / 28.0

    # railterminal, wisselstrook vrachtauto's, randweg
    for bb in (808, 816, 824, 832):
        d.add("HV-SPOOR", LineString([Fs(150, bb), Fs(1450, bb)]), dlabel="railterminal 4 sporen x 1.300 m" if bb == 808 else None)
    d.add("HV-D-KRAAN", poly([(150, 800), (1450, 800), (1450, 840), (150, 840)]), style="dashed", dlabel="RMG-kraanbaan")
    d.add("HV-SPOOR", LineString([Fs(1450, 820), Fs(1560, 845), (650.0, 448.0)]))
    d.add("HV-D-VERKEER", poly([(150, 845), (1440, 845), (1440, 870), (150, 870)]), dlabel="overslag vrachtauto's")
    d.add("HV-WEG", LineString([Fs(0, 885), Fs(QL, 885)]), style="dashed")
    # gebouwen en gate
    d.add("HV-D-GEBOUW", poly([(10, 805), (60, 805), (60, 845), (10, 845)]), dlabel="kantoor terminal")
    d.add("HV-D-GEBOUW", poly([(70, 805), (140, 805), (140, 885), (70, 885)]), dlabel="werkplaats")
    d.add("HV-D-GEBOUW", poly([(1500, 820), (1560, 820), (1560, 880), (1500, 880)]), dlabel="gate (12 rijstroken)")
    d.add("HV-D-GEBOUW", poly([(1565, 830), (1590, 830), (1590, 870), (1565, 870)]), dlabel="douane/scan")
    d.add("HV-D-PARKEER", poly([(1460, 800), (1495, 800), (1495, 890), (1460, 890)]), dlabel="truckparking")
    det["railterminal_m"] = 1300.0

    # ---------------- graanterminal (droge bulk) ----------------
    sil = []
    for row_y in (221.0, 228.5):
        for k in range(4):
            g = Point(712 + 4.2 * k, row_y).buffer(1.5, 48)
            sil.append(g)
            d.add("HV-D-OPSLAG", g, dlabel="silo's 8 x D 30 m, H 40 m" if (k == 0 and row_y == 221.0) else None)
    d.add("HV-D-OPSLAG", box(735, 212, 752, 236), dlabel="vlakke opslag")
    d.add("HV-D-KRAAN", box(718.5, 250.5, 722.5, 254.5), dlabel="shiploader 1")
    d.add("HV-D-KRAAN", box(739.5, 250.5, 743.5, 254.5), dlabel="shiploader 2")
    d.add("HV-D-KRAAN", LineString([(717, 252.5), (745, 252.5)]))
    d.add("HV-D-INSTALLATIE", LineString([(726, 230), (726, 245), (720.5, 250.5)]), dlabel="transportband")
    d.add("HV-D-INSTALLATIE", LineString([(726, 245), (741.5, 250.5)]))
    d.add("HV-D-GEBOUW", box(709, 203.5, 720, 208.5), dlabel="ontvangst vrachtauto")
    d.add("HV-D-GEBOUW", box(724, 201.5, 733, 206.5), dlabel="ontvangst spoor")
    d.add("HV-SPOOR", LineString([(722, 196), (724, 201.5), (733, 201.5), (735, 196)]))
    d.add("HV-D-GEBOUW", box(748, 201.5, 756, 206.5), dlabel="kantoor/weegbrug")
    vol = 8 * math.pi * 15 ** 2 * 40
    det["graan_silo_m3"] = vol
    det["graan_silo_ton"] = vol * 0.75

    # ---------------- RoRo ----------------
    inner = roro.buffer(-60 / s)
    strips = []
    bx0, by0, bx1, by1 = inner.bounds
    y = by0 + 1.0
    while y + 5 <= by1:
        g = box(bx0 - 50, y, bx1 + 50, y + 5).intersection(inner.buffer(-1.0))
        if not g.is_empty:
            strips.append(g)
            d.add("HV-D-PARKEER", g, dlabel="parkeervakken" if not strips[:-1] else None)
        y += 6.5
    park = sum(g.area for g in strips) * s * s
    det["roro_parkeer_m2"] = park
    det["roro_auto_capaciteit"] = park / 12.5   # 2,5 x 5,0 m per auto in de parkeerstroken
    d.add("HV-D-GEBOUW", box(_slant(580, 293, 300) + 3, 296, _slant(580, 293, 300) + 11, 302), dlabel="kantoor RoRo")

    # ---------------- havendienst ----------------
    d.add("HV-D-GEBOUW", box(762, 203, 778, 212), dlabel="havenkantoor / VTS")
    d.add("HV-D-GEBOUW", Point(826, 214).buffer(1.2), dlabel="VTS-toren")
    d.add("HV-D-GEBOUW", box(782, 241, 798, 251), dlabel="loodsen + sleepdienst")
    d.add("HV-D-GEBOUW", box(762, 241, 775, 251), dlabel="brandweer")
    for k in range(3):
        d.add("HV-SCHIP", box(778 + 9 * k, 256.6, 781 + 9 * k, 257.8), dlabel="sleepboten" if k == 0 else None)

    # ---------------- LNG-terminal ----------------
    for k, x in enumerate((626, 641, 656)):
        d.add("HV-D-OPSLAG", box(x - 6, 468, x + 6, 480), style="dashed", dlabel="tankput" if k == 0 else None)
        d.add("HV-D-OPSLAG", Point(x, 474).buffer(4.5, 64), dlabel="LNG-tank 180.000 m3 (full containment)" if k == 0 else None)
    for k in range(4):
        d.add("HV-D-INSTALLATIE", box(624 + 7 * k, 454.5, 629 + 7 * k, 458), dlabel="hervergassing 4 x 33%" if k == 0 else None)
    d.add("HV-D-INSTALLATIE", box(654, 454.5, 662, 458), dlabel="BOG-compressor")
    d.add("HV-D-INSTALLATIE", box(665, 454.5, 672, 458), dlabel="meetstation")
    d.add("HV-D-GEBOUW", box(676, 454, 686, 460), dlabel="controlekamer")
    d.add("HV-D-INSTALLATIE", Point(693, 480).buffer(0.8), dlabel="fakkel")
    # steiger: laadarmen, breasting- en meerdolphins
    nx, ny = jt[1], -jt[0]
    for k in range(3):
        p = (j1[0] + jt[0] * (k - 1) * 1.2, j1[1] + jt[1] * (k - 1) * 1.2)
        d.add("HV-D-KRAAN", LineString([p, (p[0] + nx * 1.6, p[1] + ny * 1.6)]), dlabel="laadarmen 3x" if k == 0 else None)
    for off in (-12, -6, 6, 12):
        p = (j1[0] + jt[0] * off + nx * 0.6, j1[1] + jt[1] * off + ny * 0.6)
        d.add("HV-D-INSTALLATIE", Point(p).buffer(0.9), dlabel="breasting dolphins" if off == -12 else None)
    for off in (-20, -16, 16, 20):
        p = (j1[0] + jt[0] * off + nx * 4.5, j1[1] + jt[1] * off + ny * 4.5)
        d.add("HV-D-INSTALLATIE", Point(p).buffer(0.7), dlabel="meerdolphins" if off == -20 else None)
    d.add("HV-D-INSTALLATIE", LineString([j0, j1]), dlabel="pijpleidingbrug")

    # ---------------- centrale ----------------
    for k in range(4):
        x0 = 487 + 17 * k
        d.add("HV-D-INSTALLATIE", box(x0, 456, x0 + 15, 466), dlabel="STEG-eenheid 4 x ca. 565 MW" if k == 0 else None)
        d.add("HV-D-INSTALLATIE", Point(x0 + 12.5, 459).buffer(0.8))
    d.add("HV-D-INSTALLATIE", box(558, 455, 590, 469), dlabel="hoogspanningsstation")
    d.add("HV-D-INSTALLATIE", box(592, 474, 598, 481), dlabel="gasontvangst")
    d.add("HV-D-GEBOUW", box(486, 474, 500, 482), dlabel="kantoor centrale")
    d.add("HV-D-GEBOUW", box(505, 474, 520, 482), dlabel="waterbehandeling")
    d.add("HV-D-GEBOUW", box(590, 451, 598, 455), dlabel="koelwaterpompen")
    d.add("HV-LEIDING", LineString([(574, 455), (574, 446), (400, 446)]), style="dashed", dlabel="kabel naar hoogspanningsnet")
    det["centrale_eenheden_mw"] = 4 * 565
    d.detail_views = [
        ("06", "Containerterminal", d.P(706, 368.5), 5000),
        ("07", "Graan, RoRo en havendienst", d.P(700, 266), 6000),
        ("08", "LNG-terminal en centrale", d.P(690, 448), 8000),
    ]
    DET.clear()
    DET.update(det)
    d.info["detail"] = det


# ======================================================================================
# Metingen en controles
# ======================================================================================
def _u(d, pred):
    gs = [i["geom"] for i in d.items if pred(i)]
    return unary_union(gs) if gs else Polygon()


def measure(d):
    n = d.notes
    m = {}
    tag = lambda t, ph=3: (lambda i: i.get("tag") == t and i["phase"] <= ph)
    W = d.tf
    circ = W(n["circle"])
    n = dict(n, bwn=W(n["bwn"]), bws=W(n["bws"]), lng_env=W(n["lng_env"]), tanks=[W(t) for t in n["tanks"]])
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
    m["geullengte_buiten_mond_m"] = n.get("geul_lengte", GEUL_LENGTE_M)
    m["geullengte_totaal_vanaf_draaikom_m"] = m["geullengte_buiten_mond_m"] + n["stop"]
    m["geul_buiten_m2"] = 220 * m["geullengte_buiten_mond_m"]
    m["sleepboot_buiten_mond_m"] = 1500.0
    m["lng_ligplaats_tot_draaikom_m"] = n["lng_env"].distance(circ)
    m["lng_tank_tot_containerterrein_m"] = unary_union(n["tanks"]).distance(_u(d, tag("cyard")))
    tanks_w = unary_union(n["tanks"])
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
    m["vrije_breedte_binnenbekken_m"] = n.get("vrije_breedte", 450 - 5 - 37.7)
    m["breedte_insteek_m"] = n.get("breedte_insteek", 450.0)
    m["bocht_geul_hoofdbekken_graden"] = n.get("bocht_hoofdbekken")
    m["bocht_hoofdbekken_insteek_graden"] = n.get("bocht_insteek")
    m["draaikom_binnen_vrij_van_schepen_m"] = n.get("draaikom_binnen_vrij_m")
    m["breedte_hoofdbekken_m"] = n.get("breedte_hoofdbekken", 450.0)
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

    data = dict(SO=dict(m=so.m, anker=so.anchor), DO=dict(m=do.m, anker=do.anchor, info=do.info), georef=geo,
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
