import numpy as np, json, sys
from pyproj import Transformer
from shapely.geometry import LineString, Point
M="/usr/local/lib/python3.13/dist-packages/mpl_toolkits/basemap_data"
t=Transformer.from_crs(4326,31984,always_xy=True)
dat=open(f"{M}/gshhs_f.dat","rb")
segs=[]
for line in open(f"{M}/gshhsmeta_f.dat"):
    f=line.split()
    lev,npts,s,n,off,nb=int(f[0]),int(f[2]),float(f[3]),float(f[4]),int(f[5]),int(f[6])
    if lev!=1 or s>-21.5 or n<-21.0: continue
    dat.seek(off); a=np.frombuffer(dat.read(nb),dtype=np.float64 if nb==npts*16 else np.float32).reshape(-1,2)
    m=(a[:,0]>-41.2)&(a[:,0]<-40.6)&(a[:,1]>-21.45)&(a[:,1]<-21.0)
    if m.sum(): 
        idx=np.where(m)[0]; segs.append(a[idx.min():idx.max()+1]); print(npts,nb, m.sum())
pts=np.vstack(segs)
x,y=t.transform(pts[:,0],pts[:,1])
g=LineString(list(zip(x,y)))
coast=LineString(json.load(open(f"{sys.argv[1]}/coast.json")))
d=[]
for N0 in range(7642000,7656001,1000):
    # horizontal distance between coastlines at this northing
    from shapely.geometry import LineString as L
    h=L([(285000,N0),(318000,N0)])
    a=g.intersection(h); b=coast.intersection(h)
    def ex(z): 
        z=[p.x for p in getattr(z,'geoms',[z]) if not z.is_empty]
        return max(z) if z else None
    xa,xb=ex(a),ex(b)
    if xa and xb: d.append(xa-xb); print(N0, round(xa), round(xb), round(xa-xb))
print("mean dE GSHHS-S2", np.mean(d), "std", np.std(d))
json.dump(list(g.coords),open(f"{sys.argv[1]}/gshhs.json","w"))
