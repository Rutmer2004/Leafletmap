import os, numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.transform import from_origin
os.environ["CURL_CA_BUNDLE"]="/root/.ccr/ca-bundle.crt"
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"]="EMPTY_DIR"
B="/vsicurl/https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/24/K"
date="20260703"
W,S_,E,N=284000,7632000,318000,7666000
res=10
nx,ny=(E-W)//res,(N-S_)//res
outdir=os.sys.argv[1]
def grab(band, dtype):
    acc=np.zeros(((3 if band=="TCI" else 1),ny,nx),dtype=dtype)
    for t in ["TB","UB"]:
        url=f"{B}/{t}/2026/7/S2B_24K{t}_{date}_0_L2A/{band}.tif"
        with rasterio.open(url) as src:
            print(t,band,src.crs,src.bounds)
            b=src.bounds
            w0,s0,e0,n0=max(W,b.left),max(S_,b.bottom),min(E,b.right),min(N,b.top)
            win=from_bounds(w0,s0,e0,n0,src.transform)
            arr=src.read(window=win, out_shape=(src.count,int(round((n0-s0)/res)),int(round((e0-w0)/res))))
            c0=int(round((w0-W)/res)); r0=int(round((N-n0)/res))
            sub=acc[:,r0:r0+arr.shape[1],c0:c0+arr.shape[2]]
            m=(arr.sum(0)>0) if arr.shape[0]>1 else arr[0]>0
            sub[:,m]=arr[:,m]
    return acc
tci=grab("TCI",np.uint8)
b03=grab("B03",np.uint16)[0]; b08=grab("B08",np.uint16)[0]
prof=dict(driver="GTiff",width=nx,height=ny,crs="EPSG:31984",transform=from_origin(W,N,res,res),compress="deflate")
with rasterio.open(f"{outdir}/S2_20260703_TCI_EPSG31984.tif","w",count=3,dtype="uint8",photometric="RGB",**prof) as d: d.write(tci)
np.save(f"{outdir}/b03.npy",b03); np.save(f"{outdir}/b08.npy",b08)
print("ok",tci.shape)
