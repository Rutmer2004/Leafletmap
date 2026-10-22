"""Tekstplaatsing zonder overlap, in papiermillimeters (A1).

Elke tekst wordt horizontaal gezet (nooit op de kop) en krijgt een vrije plek: eerst binnen het eigen vlak,
dan langs de lijn of rond het punt, en anders met een verwijslijn naar een vrije plek in de buurt.
Lukt dat niet, dan vervalt de tekst (alleen voor teksten met lage prioriteit).
Dezelfde plaatsing wordt gebruikt voor de PDF (matplotlib) en voor de DXF-layouts (paperspace).

Teksthoogtes volgens NLCS: T18 = 1,8 mm, T25 = 2,5 mm, T35 = 3,5 mm (hoofdletterhoogte op papier).
"""
import math
from functools import lru_cache

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polylabel

HOOGTE = {"T18": 1.8, "T25": 2.5, "T35": 3.5, "T50": 5.0}
MARGE = 1.2   # vrije ruimte rond elke tekst (mm)


@lru_cache(maxsize=4096)
def tekstmaat(tekst, h):
    """(breedte, hoogte) in mm van een tekst met hoofdletterhoogte h (matplotlib-lettertype, conservatief)."""
    from matplotlib.textpath import TextPath
    em = h / 0.72
    regels = tekst.split("\n")
    b = max((TextPath((0, 0), r or " ", size=em).get_extents().width for r in regels), default=0.0)
    return b, h + (len(regels) - 1) * 1.667 * h


class Plaatsing:
    __slots__ = ("tekst", "x", "y", "h", "b", "hoogte", "verwijs", "laag", "rot", "stijl")

    def __init__(self, tekst, x, y, h, b, hoogte, verwijs=None, laag="T25", rot=0.0, stijl=None):
        self.tekst, self.x, self.y, self.h, self.b, self.hoogte = tekst, x, y, h, b, hoogte
        self.verwijs, self.laag, self.rot, self.stijl = verwijs, laag, rot, stijl


class Plaatser:
    def __init__(self, center, scale, rect):
        """center = wereldmidden van het kaartvenster, scale = schaalgetal, rect = (x, y, b, h) in mm op het blad."""
        self.cx, self.cy = center
        self.s = scale / 1000.0          # m per mm
        self.rx, self.ry, self.rb, self.rh = rect
        self.venster = box(self.rx + 4, self.ry + 4, self.rx + self.rb - 4, self.ry + self.rh - 4)
        self.bezet = []                  # shapely-vakken die vrij moeten blijven
        self.tekstvakken = []            # alleen de geplaatste teksten (voor verwijslijnen)
        self.geplaatst = []
        self.vervallen = []

    # --- coördinaten ---------------------------------------------------------------------------
    def p(self, x, y):
        return (self.rx + self.rb / 2 + (x - self.cx) / self.s, self.ry + self.rh / 2 + (y - self.cy) / self.s)

    def w(self, px, py):
        return (self.cx + (px - self.rx - self.rb / 2) * self.s, self.cy + (py - self.ry - self.rh / 2) * self.s)

    def naar_papier(self, g):
        from shapely import affinity
        a = 1 / self.s
        return affinity.affine_transform(g, [a, 0, 0, a, self.rx + self.rb / 2 - self.cx * a, self.ry + self.rh / 2 - self.cy * a])

    # --- bezetting -----------------------------------------------------------------------------
    def reserveer(self, g):
        """Papiervak (mm) dat vrij moet blijven: noordpijl, schaalstok, maatteksten, kaarttitel."""
        self.bezet.append(g)

    def reserveer_wereld(self, g, buffer_mm=0.0):
        self.bezet.append(self.naar_papier(g).buffer(buffer_mm))

    def _vrij(self, vak, binnen=None):
        if not self.venster.contains(vak):
            return False
        if binnen is not None and not binnen.contains(vak):
            return False
        return not any(vak.intersects(b) for b in self.bezet)

    # --- plaatsen ------------------------------------------------------------------------------
    def plaats(self, tekst, geom, laag="T25", soort=None, verplicht=False, stijl=None):
        """geom in wereldcoördinaten. Geeft een Plaatsing terug of None (vervallen)."""
        h = HOOGTE[laag]
        b, hh = tekstmaat(tekst, h)
        g = self.naar_papier(geom)
        if g.is_empty or not g.intersects(self.venster):
            return None
        soort = soort or {"Polygon": "vlak", "MultiPolygon": "vlak", "LineString": "lijn",
                          "MultiLineString": "lijn", "Point": "punt"}.get(g.geom_type, "punt")
        gz = g.intersection(self.venster) if soort != "punt" else g

        def vak(x, y):
            return box(x - b / 2 - MARGE, y - hh / 2 - MARGE, x + b / 2 + MARGE, y + hh / 2 + MARGE)

        kandidaten = []
        if soort == "vlak":
            poly = max(getattr(gz, "geoms", [gz]), key=lambda q: q.area) if not gz.is_empty else None
            if poly is not None and poly.geom_type == "Polygon" and poly.area > 0:
                try:
                    c = polylabel(poly, tolerance=0.5)
                except Exception:
                    c = poly.representative_point()
                kandidaten.append(((c.x, c.y), poly))
                x0, y0, x1, y1 = poly.bounds
                st = max(2.0, hh * 1.5)
                pts = []
                yy = y0 + st / 2
                while yy < y1:
                    xx = x0 + st / 2
                    while xx < x1:
                        if poly.contains(Point(xx, yy)):
                            pts.append((math.hypot(xx - c.x, yy - c.y), (xx, yy)))
                        xx += st
                    yy += st
                kandidaten += [(q, poly) for _, q in sorted(pts)[:400]]
                anker = (c.x, c.y)
            else:
                anker = (gz.centroid.x, gz.centroid.y) if not gz.is_empty else None
        elif soort == "lijn":
            ln = max(getattr(gz, "geoms", [gz]), key=lambda q: q.length) if not gz.is_empty else None
            anker = None
            if ln is not None and ln.length > 0:
                q = ln.interpolate(0.5, normalized=True)
                anker = (q.x, q.y)
                for f in (0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82):
                    q = ln.interpolate(f, normalized=True)
                    for dx, dy in ((0, hh / 2 + 1.6), (0, -hh / 2 - 1.6), (b / 2 + 1.6, 0), (-b / 2 - 1.6, 0)):
                        kandidaten.append(((q.x + dx, q.y + dy), None))
        else:
            c = g.centroid
            anker = (c.x, c.y)
            for dx, dy in ((b / 2 + 2.5, 0), (-b / 2 - 2.5, 0), (0, hh / 2 + 2.5), (0, -hh / 2 - 2.5),
                           (b / 2 + 2.5, hh / 2 + 2), (-b / 2 - 2.5, hh / 2 + 2), (b / 2 + 2.5, -hh / 2 - 2),
                           (-b / 2 - 2.5, -hh / 2 - 2)):
                kandidaten.append(((c.x + dx, c.y + dy), None))
        if anker is None:
            return None

        # 1) volledig binnen het eigen vlak / direct naast lijn of punt
        for (x, y), binnen in kandidaten:
            v = vak(x, y)
            if self._vrij(v, binnen):
                return self._zet(tekst, x, y, h, b, hh, v, None, laag, stijl)
        # 2) met verwijslijn naar een vrije plek in de buurt
        pa = Point(anker)
        for r in (8, 13, 19, 26, 34, 44, 56, 70):
            for k in range(24):
                a = 2 * math.pi * k / 24 + 0.2
                x, y = anker[0] + math.cos(a) * (r + b / 2), anker[1] + math.sin(a) * (r + hh / 2)
                v = vak(x, y)
                if not self._vrij(v):
                    continue
                rand = v.exterior.interpolate(v.exterior.project(pa))
                lijn = LineString([anker, (rand.x, rand.y)])
                # verwijslijn mag geen andere tekst doorsnijden (vakken die het ankerpunt zelf bevatten tellen niet)
                if any(lijn.intersects(t) and not t.contains(pa) for t in self.tekstvakken):
                    continue
                return self._zet(tekst, x, y, h, b, hh, v, [anker, (rand.x, rand.y)], laag, stijl)
        if verplicht:
            x, y = anker
            v = vak(x, y)
            return self._zet(tekst, x, y, h, b, hh, v, None, laag, stijl)
        self.vervallen.append(tekst)
        return None

    def _zet(self, tekst, x, y, h, b, hh, v, verwijs, laag, stijl):
        self.bezet.append(v)
        self.tekstvakken.append(v)
        if verwijs:
            self.bezet.append(LineString(verwijs).buffer(0.4))
        pl = Plaatsing(tekst, x, y, h, b, hh, verwijs, laag, 0.0, stijl)
        self.geplaatst.append(pl)
        return pl


def leesbare_hoek(graden):
    """Hoek in (-90, 90]: tekst nooit op de kop."""
    a = (graden + 180.0) % 360.0 - 180.0
    if a > 90:
        a -= 180
    elif a <= -90:
        a += 180
    return a
