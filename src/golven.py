"""Vereenvoudigde golfdoordringingstoets (diffractie) voor de voorhaven en de bekkens.

Methode: Huygens-Kirchhoff (Rayleigh-Sommerfeld) voor een lineaire golf door een opening:
    phi(P) = (i k / 2) * som_Q phi_in(Q) * H1(1)(k r) * cos(psi) * dl
Eerst door de havenmond (opening tussen de dammen), daarna eventueel door een tweede opening
(ingang hoofdbekken, ingang insteekbekken). Kd = |phi| / |phi_inc|.
Niet meegenomen: refractie, reflectie tegen kades/taluds, golfopwekking in de haven, lange golven.
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


def kd(punten, keten, richting, T=8.0, h=15.0):
    """Kd in 'punten'. keten = lijst openingen [(p1, p2), ...] van buiten naar binnen (EPSG:31984).
    richting = voortplantingsrichting van de inkomende golf (eenheidsvector, wereld)."""
    k = 2 * math.pi / golflengte(T, h)
    ux, uy = richting
    q, dl = _aperture(*keten[0])
    phi = np.exp(1j * k * (q[:, 0] * ux + q[:, 1] * uy))
    ref = phi.copy()
    for i, (p1, p2) in enumerate(keten):
        t = np.subtract(p2, p1) / math.dist(p1, p2)
        nrm = np.array([-t[1], t[0]])
        if nrm[0] * ux + nrm[1] * uy < 0:   # normaal naar de havenzijde laten wijzen
            nrm = -nrm
        if i + 1 < len(keten):
            q2, dl2 = _aperture(*keten[i + 1])
            phi = door_opening(q, phi, dl, nrm, k, q2)
            q, dl = q2, dl2
            # richting voor de volgende normaal: van deze opening naar de volgende
            c1 = np.mean(_aperture(p1, p2, 2)[0], axis=0)
            c2 = np.mean(q, axis=0)
            v = c2 - c1
            ux, uy = v / np.linalg.norm(v)
        else:
            return np.abs(door_opening(q, phi, dl, nrm, k, punten))
    return np.abs(phi)


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


def _centrum(d, label):
    g = [i["geom"] for i in d.items if i["layer"] == "HV-SCHIP" and i["label"] == label][0]
    return (g.centroid.x, g.centroid.y)


def toets(d, T=8.0, h=15.0):
    mond, hb, ins = openingen(d)
    lig = {"Containers C1-C4 (insteek, westzijde)": ([_centrum(d, f"C{i}") for i in range(1, 5)], [mond, hb, ins], "containers"),
           "Graan (noordkade hoofdbekken)": ([_centrum(d, "Graanschip")], [mond, hb], "graan"),
           "RoRo (insteek, vinger 7/8)": ([_centrum(d, "RoRo-schip")], [mond, hb, ins], "RoRo"),
           "LNG (achter zuidelijke dam)": ([_centrum(d, "GASLOG GREECE")], [mond], "LNG")}
    # vergelijking: containerkade aan de oostzijde (voorhaven), punten 30 m buiten de oostrand van vinger 6
    oost = []
    for i in range(4):
        y = 297 + 143 * (i + 0.5) / 4
        x = 792 - 0.5 * (y - 297) + 3.0
        oost.append(d.P(x, y))
    lig["Variant: containerkade oostzijde (voorhaven)"] = (oost, [mond], "containers")
    lng_oud = d.P(905.0, 420.0)
    lig["Variant: LNG-steiger bij de havenmond (oud)"] = ([lng_oud], [mond], "LNG")
    out = {}
    for naam, (pts, keten, soort) in lig.items():
        rij = {}
        for frm in RICHTINGEN:
            az = math.radians(frm + 180)
            rij[frm] = float(kd(pts, keten, (math.sin(az), math.cos(az)), T=T, h=h).max())
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
    for poly, keten in ((vh, [mond]), (hoofd, [mond, hb]), (insteek, [mond, hb, ins])):
        x0, y0, x1, y1 = poly.bounds
        X, Y = np.meshgrid(np.arange(x0, x1 + stap, stap), np.arange(y0, y1 + stap, stap))
        m = contains_xy(poly, X, Y)
        vals = np.full(X.shape, np.nan)
        vals[m] = kd(np.column_stack([X[m], Y[m]]), keten, u, T=T, h=h)
        out.append((X, Y, vals))
    return out
