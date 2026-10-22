import os, sys, numpy as np, rasterio
from rasterio.windows import from_bounds
os.environ["CURL_CA_BUNDLE"]="/root/.ccr/ca-bundle.crt"
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"]="EMPTY_DIR"
url="/vsicurl/https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop/ausantarctic/gebco/GEBCO_2026.tif"
with rasterio.open(url) as src:
    print(src.crs, src.res, src.dtypes, src.overviews(1)[:3])
    W,S_,E,N = -41.15, -21.75, -40.40, -21.05
    win = from_bounds(W,S_,E,N, src.transform)
    a = src.read(1, window=win)
    tr = src.window_transform(win)
    prof = dict(driver="GTiff", width=a.shape[1], height=a.shape[0], count=1, dtype=a.dtype, crs=src.crs, transform=tr, compress="deflate")
    with rasterio.open(sys.argv[1], "w", **prof) as dst: dst.write(a, 1)
    print(a.shape, a.min(), a.max())
