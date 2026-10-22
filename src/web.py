"""GeoJSON (WGS84) van SO en DO voor de Leaflet-webkaart."""
import json
import os

from shapely.geometry import mapping
from shapely.ops import transform

import haven as H


def _ll(g):
    return transform(lambda x, y, z=None: H.TO_LL.transform(x, y), g)


def write_geojson(so, do, coast, outdir):
    os.makedirs(outdir, exist_ok=True)
    for d in (so, do):
        feats = []
        for it in d.items:
            g = _ll(it["geom"].simplify(0.5))
            feats.append(dict(type="Feature", geometry=mapping(g),
                              properties=dict(laag=it["layer"], label=it["label"], fase=it["phase"],
                                              kleur=H.LAYERS[it["layer"]][1], omschrijving=H.LAYERS[it["layer"]][3])))
        for k, a in d.anchor.items():
            feats.append(dict(type="Feature", geometry=dict(type="Point", coordinates=[round(a["lon"], 7), round(a["lat"], 7)]),
                              properties=dict(laag="ANKER", label=f"{k} {a['naam']}", E=round(a["E"], 1), N=round(a["N"], 1))))
        json.dump(dict(type="FeatureCollection", features=feats), open(os.path.join(outdir, f"{d.code.lower()}.geojson"), "w"))
    json.dump(dict(type="Feature", geometry=mapping(_ll(coast)), properties={}), open(os.path.join(outdir, "kustlijn.geojson"), "w"))
    write_datajs(outdir)


def write_datajs(outdir):
    """Bundel de GeoJSON in data.js zodat index.html ook via dubbelklik (file://) werkt."""
    data = {k: json.load(open(os.path.join(outdir, f"{k}.geojson"))) for k in ("so", "do", "kustlijn")}
    with open(os.path.join(outdir, "data.js"), "w") as f:
        f.write("window.HAVEN = " + json.dumps(data) + ";\n")
