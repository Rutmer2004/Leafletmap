"""Vereenvoudigde golfdoordringingstoets (diffractie) voor de voorhaven en de bekkens.

Methode: Huygens-Kirchhoff (Rayleigh-Sommerfeld) voor een lineaire golf door een opening:
    phi(P) = (i k / 2) * som_Q phi_in(Q) * H1(1)(k r) * cos(psi) * dl
Eerst door de havenmond (opening tussen de dammen), daarna eventueel door een tweede opening
(ingang hoofdbekken, ingang insteekbekken). Kd = |phi| / |phi_inc|.
Reflectie (eerste orde) via spiegelbronnen: de opening wordt gespiegeld in elke wand (dam, talud, kademuur) en
draagt bij met reflectiecoëfficiënt Cr (verticale kade 0,9; stortsteen/talud 0,4), alleen als het spiegelpunt
op de wand ligt. Niet meegenomen: refractie, hogere-orde reflecties, golfopwekking in de haven, lange golven.
Uitkomst is daarom een eerste vergelijking van varianten, geen vervanging van een numeriek golfmodel.
"""
import math

import numpy as np
from scipy.special import hankel1

G = 9.81


def golflengte(T, h):
    """Dispersierelatie (iteratief)."""
    L0 = G * T * T / (2 * math.pi)
    L = L0
    for _ in range(100):
        L = L0 * math.tanh(2 * math.pi * h / L)
    return L


def _aperture(p1, p2, n=240):
    t = np.linspace(0, 1, n)
    q = np.outer(1 - t, p1) + np.outer(t, p2)
    dl = math.dist(p1, p2) / (n - 1)
    return q, dl


def door_opening(q_src, phi_src, dl, normaal, k, punten):
    """Velden in 'punten' na een opening met bekende waarden phi_src in q_src."""
    P = np.atleast_2d(np.asarray(punten, float))
    d = P[:, None, :] - q_src[None, :, :]
    r = np.hypot(d[..., 0], d[..., 1])
    r = np.maximum(r, 1e-6)
    cos = (d[..., 0] * normaal[0] + d[..., 1] * normaal[1]) / r
    cos = np.clip(cos, 0, None)  # alleen naar voren (havenzijde)
    return (1j * k / 2) * np.sum(phi_src[None, :] * hankel1(1, k * r) * cos * dl, axis=1)


def _spiegel(P, a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = (b - a) / np.linalg.norm(b - a)
    v = P - a
    proj = a + np.outer(v @ t, t) if P.ndim == 2 else a + (v @ t) * t
    return 2 * proj - P


def _op_wand(P, Q, a, b):
    """Snijdt het lijnstuk P-Q (per punt P, één Q) de wand a-b?"""
    a, b, Q = np.asarray(a, float), np.asarray(b, float), np.asarray(Q, float)
    d1 = P - Q
    d2 = b - a
    den = d1[:, 0] * d2[1] - d1[:, 1] * d2[0]
    den = np.where(np.abs(den) < 1e-9, 1e-9, den)
    w = Q - a
    t = (w[0] * d2[1] - w[1] * d2[0]) / den * -1
    u = (w[0] * d1[:, 1] - w[1] * d1[:, 0]) / den * -1
    return (t > 0) & (t < 1) & (u >= 0) & (u <= 1)


def _velden(q, phi, dl, nrm, k, punten, wanden):
    """Direct veld + per wand het gereflecteerde veld (eerste orde) in 'punten' (complexe lijsten)."""
    P = np.atleast_2d(np.asarray(punten, float))
    out = [door_opening(q, phi, dl, nrm, k, P)]
    a0 = None
    for a, b, cr in wanden or []:
        a0 = np.asarray(a, float)
        qs = _spiegel(q, a, b)
        ns = _spiegel(np.array([nrm]) + a0, a, b)[0] - _spiegel(np.array([[0.0, 0.0]]) + a0, a, b)[0]
        geldig = _op_wand(P, qs.mean(axis=0), a, b)
        f = np.zeros(len(P), complex)
        if geldig.any():
            f[geldig] = cr * door_opening(qs, phi, dl, ns, k, P[geldig])
            out.append(f)
    return out


def kd(punten, keten, richting, T=8.0, h=15.0, wanden=None):
    """Kd in 'punten'. keten = lijst openingen [(p1, p2), ...] van buiten naar binnen (EPSG:31984).
    richting = voortplantingsrichting van de inkomende golf (eenheidsvector, wereld).
    wanden = per opening een lijst (p1, p2, Cr) van reflecterende wanden achter die opening (of None).
    Het directe veld en elk gereflecteerd veld worden apart door de keten gevoerd; in de punten wordt
    de energie opgeteld: Kd = sqrt(som |phi_i|^2) (gebruikelijk bij reflectie, geen toevallige interferentie)."""
    wanden = wanden or [None] * len(keten)
    k = 2 * math.pi / golflengte(T, h)
    ux, uy = richting
    q, dl = _aperture(*keten[0])
    velden = [np.exp(1j * k * (q[:, 0] * ux + q[:, 1] * uy))]
    for i, (p1, p2) in enumerate(keten):
        t = np.subtract(p2, p1) / math.dist(p1, p2)
        nrm = np.array([-t[1], t[0]])
        if nrm[0] * ux + nrm[1] * uy < 0:   # normaal naar de havenzijde laten wijzen
            nrm = -nrm
        doel = _aperture(*keten[i + 1])[0] if i + 1 < len(keten) else punten
        nieuw = []
        for j, phi in enumerate(velden):
            fs = _velden(q, phi, dl, nrm, k, doel, wanden[i] if j == 0 else None)  # alleen eerste orde
            nieuw += fs
        velden = nieuw
        if i + 1 < len(keten):
            q2, dl2 = _aperture(*keten[i + 1])
            c1 = np.mean(_aperture(p1, p2, 2)[0], axis=0)
            v = np.mean(q2, axis=0) - c1
            ux, uy = v / np.linalg.norm(v)
            q, dl = q2, dl2
    return np.sqrt(sum(np.abs(f) ** 2 for f in velden))


# indicatieve grenzen voor laden/lossen (significante golfhoogte aan de ligplaats, dwars/schuin)
# bron: gangbare waarden uit PIANC (1995) / handboeken (o.a. Thoresen, Port Designer's Handbook); te verifiëren
GRENS_HS = {"containers": 0.5, "RoRo": 0.3, "graan": 1.0, "LNG": 1.0}


RICHTINGEN = (45.0, 67.5, 90.0, 112.5, 135.0, 157.5)   # golven uit NO .. ZZO (graden t.o.v. noord)
HS_BUITEN = 2.5   # bovenkant bandbreedte Deel 1 (1,5 - 2,5 m), T = 7 - 9 s


def openingen(d):
    """Havenmond (binnenkanten dammen), ingang hoofdbekken en ingang insteekbekken in EPSG:31984."""
    n = d.notes
    s = 10.035
    M, T = n["M"], n["T"]
    L = math.hypot(M[0] - T[0], M[1] - T[1])
    nv = (-(M[1] - T[1]) / L, (M[0] - T[0]) / L)
    bw = 45 / s
    hn, hs = n["hn"], n["hs"]
    mond = (d.P(hn[0] + nv[0] * bw, hn[1] + nv[1] * bw), d.P(hs[0] - nv[0] * bw, hs[1] - nv[1] * bw))
    hb = (d.P(815, 256), d.P(792, 297))
    ins = (d.P(630, 293), d.P(692.5, 293))
    return mond, hb, ins


CR_KADE, CR_TALUD, CR_OPEN = 0.9, 0.4, 0.45   # verticale kade, stortsteen/talud, open kade op palen


def wanden(d):
    """Reflecterende wanden per waterdeel (wereld): voorhaven, hoofdbekken, insteek."""
    P = d.P
    vh = []
    for i in d.items:   # binnenkant dammen (hartlijnen), stortsteen
        if i["layer"] == "HV-GEUL-AS" and i.get("style") == "dashdot":
            c = list(i["geom"].coords)
            vh += [(c[j], c[j + 1], CR_TALUD) for j in range(len(c) - 1)]
    vh += [(P(792, 297), P(720.5, 440), CR_TALUD),          # oostzijde vinger 6 (talud)
           (P(840, 212), P(832, 240), CR_TALUD), (P(832, 240), P(815, 256), CR_TALUD)]
    hb = [(P(700, 256), P(760, 256), CR_OPEN),              # graankade: open kade op palen boven golfdempend talud
          (P(760, 256), P(805, 256), CR_OPEN),              # havendienstkade, ook open (golfdempend)
          (P(625, 256), P(700, 256), CR_TALUD),
          (P(692, 297), P(792, 297), CR_TALUD)]             # kop vinger 6
    ins = [(P(692, 297), P(620.5, 440), CR_KADE),           # containerkade
           (P(630, 293), P(556.5, 440), CR_KADE)]           # oostzijde vinger 7/8 (RoRo-kade en verlengde)
    return vh, hb, ins


def _centrum(d, label):
    g = [i["geom"] for i in d.items if i["layer"] == "HV-SCHIP" and i["label"] == label][0]
    return (g.centroid.x, g.centroid.y)


def _langs(d, label, n=5):
    """n punten op de hartlijn van het schip (over de hele lengte)."""
    g = [i["geom"] for i in d.items if i["layer"] == "HV-SCHIP" and i["label"] == label][0]
    c = list(g.minimum_rotated_rectangle.exterior.coords)[:4]
    e = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    a, b = max(e[:2], key=lambda s: math.dist(*s))
    (ax, ay), (bx, by) = a, b
    m = (g.centroid.x, g.centroid.y)
    L = math.dist(a, b)
    ux, uy = (bx - ax) / L, (by - ay) / L
    return [(m[0] + ux * t, m[1] + uy * t) for t in np.linspace(-0.45 * L, 0.45 * L, n)]


def toets(d, T=8.0, h=15.0, reflectie=True):
    mond, hb, ins = openingen(d)
    w_vh, w_hb, w_ins = wanden(d) if reflectie else (None, None, None)
    W = {1: [w_vh], 2: [w_vh, w_hb], 3: [w_vh, w_hb, w_ins]}
    lig = {"Containers C1-C4 (insteek, westzijde)": ([p for i in range(1, 5) for p in _langs(d, f"C{i}", 3)], [mond, hb, ins],
                                                      "containers"),
           "Graan (open kade, noordkade hoofdbekken)": (_langs(d, "Graanschip"), [mond, hb], "graan"),
           "RoRo (insteek, vinger 7/8)": (_langs(d, "RoRo-schip"), [mond, hb, ins], "RoRo"),
           "LNG (achter zuidelijke dam)": (_langs(d, "GASLOG GREECE"), [mond], "LNG")}
    # vergelijking: containerkade aan de oostzijde (voorhaven), punten 30 m buiten de oostrand van vinger 6
    oost = []
    for i in range(4):
        y = 297 + 143 * (i + 0.5) / 4
        x = 792 - 0.5 * (y - 297) + 3.0
        oost += [d.P(x - 0.5 * dy, y + dy) for dy in (-12, 0, 12)]
    lig["Variant: containerkade oostzijde (voorhaven)"] = (oost, [mond], "containers")
    lig["Variant: LNG-steiger bij de havenmond (SO)"] = ([d.P(905.0 + 0.36 * t, 420.0 - t) for t in (-12, -6, 0, 6, 12)], [mond], "LNG")
    out = {}
    for naam, (pts, keten, soort) in lig.items():
        rij = {}
        for frm in RICHTINGEN:
            az = math.radians(frm + 180)
            rij[frm] = float(kd(pts, keten, (math.sin(az), math.cos(az)), T=T, h=h, wanden=W[len(keten)]).max())
        kmax = max(rij.values())
        out[naam] = dict(kd=rij, kd_max=kmax, hs=kmax * HS_BUITEN, grens=GRENS_HS[soort],
                         voldoet=kmax * HS_BUITEN <= GRENS_HS[soort])
    return out


def kd_veld(d, polygon, richting_van=90.0, stap=40.0, T=8.0, h=15.0):
    """Kd op een raster binnen 'polygon' (wereld) voor golven uit 'richting_van', alleen door de havenmond."""
    mond, _, _ = openingen(d)
    x0, y0, x1, y1 = polygon.bounds
    xs = np.arange(x0, x1, stap)
    ys = np.arange(y0, y1, stap)
    X, Y = np.meshgrid(xs, ys)
    from shapely import contains_xy
    m = contains_xy(polygon, X, Y)
    az = math.radians(richting_van + 180)
    vals = np.full(X.shape, np.nan)
    pts = np.column_stack([X[m], Y[m]])
    vals[m] = kd(pts, [mond], (math.sin(az), math.cos(az)), T=T, h=h)
    return X, Y, vals


def kd_regios(d, richting_van, stap=40.0, T=8.0, h=15.0):
    """Kd-veld per waterdeel met de juiste reeks openingen: voorhaven (mond), hoofdbekken (mond + ingang),
    insteekbekkens (mond + ingang + insteek). Geeft lijst (X, Y, Kd) per regio."""
    from shapely import contains_xy
    from shapely.ops import unary_union
    mond, hb, ins = openingen(d)
    w_vh, w_hb, w_ins = wanden(d)
    def geoms(pred):
        return unary_union([i["geom"] for i in d.items if pred(i)])
    vh = geoms(lambda i: i.get("tag") in ("voorhaven_water", "voorhaven"))
    hoofd = geoms(lambda i: i["layer"] == "HV-BAGGER" and (i["label"] or "").startswith("Hoofdbekken"))
    insteek = geoms(lambda i: i["layer"] == "HV-BAGGER" and i.get("tag") == "bekken" and i["phase"] <= 3
                    and not (i["label"] or "").startswith("Hoofdbekken"))
    hoofd = hoofd.difference(vh)
    insteek = insteek.difference(unary_union([vh, hoofd]))
    az = math.radians(richting_van + 180)
    u = (math.sin(az), math.cos(az))
    out = []
    for poly, keten, w in ((vh, [mond], [w_vh]), (hoofd, [mond, hb], [w_vh, w_hb]), (insteek, [mond, hb, ins], [w_vh, w_hb, w_ins])):
        x0, y0, x1, y1 = poly.bounds
        X, Y = np.meshgrid(np.arange(x0, x1 + stap, stap), np.arange(y0, y1 + stap, stap))
        m = contains_xy(poly, X, Y)
        vals = np.full(X.shape, np.nan)
        vals[m] = kd(np.column_stack([X[m], Y[m]]), keten, u, T=T, h=h, wanden=w)
        out.append((X, Y, vals))
    return out
