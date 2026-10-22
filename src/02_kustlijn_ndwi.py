import numpy as np, json, sys
from skimage import measure, morphology, filters
d=sys.argv[1]
g=np.load(f"{d}/b03.npy").astype(float); n=np.load(f"{d}/b08.npy").astype(float)
ndwi=(g-n)/(g+n+1e-6)
ndwi=filters.gaussian(ndwi,1)
water=ndwi>0.0
# keep sea = largest water component touching east edge
lab=measure.label(water)
sea_id=np.bincount(lab[:, -1][lab[:, -1]>0]).argmax()
sea=morphology.remove_small_holes(lab==sea_id, 5000)
W,N,res=284000,7666000,10
cs=measure.find_contours(sea.astype(float),0.5)
c=max(cs,key=len)
pts=[(W+(col+0.5)*res, N-(row+0.5)*res) for row,col in c]
# keep only within frame interior
from shapely.geometry import LineString
ls=LineString(pts).simplify(5)
json.dump(list(ls.coords),open(f"{d}/coast.json","w"))
print(len(ls.coords), ls.length)
# local orientation 7646-7651
P=np.array([p for p in ls.coords if 7646000<p[1]<7651000 and p[0]>295000])
A=np.polyfit(P[:,1],P[:,0],1); print("dE/dN",A, "bearing deg", np.degrees(np.arctan(A[0])))
for N0 in [7646000,7646500,7647000,7647500,7648000,7648300,7648500,7649000,7649500,7650000,7651000]:
    q=P[np.argmin(abs(P[:,1]-N0))]; print(N0,q)
