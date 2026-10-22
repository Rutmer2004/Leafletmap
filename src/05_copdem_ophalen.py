import os, sys, numpy as np, rasterio
from rasterio.windows import from_bounds
os.environ["CURL_CA_BUNDLE"]="/root/.ccr/ca-bundle.crt"
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"]="EMPTY_DIR"
t="Copernicus_DSM_COG_10_S22_00_W041_00_DEM"
url=f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{t}/{t}.tif"
with rasterio.open(url) as src:
    print(src.crs, src.res, src.bounds)
    win=from_bounds(-40.9999,-21.32,-40.85,-21.18, src.transform).round_offsets().round_lengths()
    a=src.read(1, window=win); tr=src.window_transform(win)
    prof=dict(driver="GTiff",width=a.shape[1],height=a.shape[0],count=1,dtype=a.dtype,crs=src.crs,transform=tr,compress="deflate")
    with rasterio.open(sys.argv[1],"w",**prof) as d: d.write(a,1)
    print(a.shape, float(a.min()), float(a.max()))
