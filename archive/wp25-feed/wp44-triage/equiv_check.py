import random
def pip(coords, x, y, start=0, stop_off=1, xgate_le=True, xint_div=True, xint_le=True):
    n=len(coords); inside=False
    p1x,p1y = coords[start]
    for i in range(1, n+stop_off+1):
        p2x,p2y = coords[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and ((x<=max(p1x,p2x)) if xgate_le else (x<max(p1x,p2x))):
            if p1y!=p2y:
                xinters = ((y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x) if xint_div else ((y-p1y)*(p2x-p1x)*(p2y-p1y)+p1x)
            if p1x==p2x or ((x<=xinters) if xint_le else (x<xinters)):
                inside = not inside
        p1x,p1y=p2x,p2y
    return inside
random.seed(7)
rect=[(0.25,0.25),(0.75,0.25),(0.75,0.75),(0.25,0.75)]
tri=[(0.0,0.0),(1.0,1.0),(0.0,1.0)]
quad=[(0.1,0.1),(0.9,0.2),(0.6,0.9),(0.2,0.6)]
rands=[[tuple(round(random.uniform(0,1),3) for _ in range(2)) for _ in range(k)] for k in (3,4,5,6,4)]
VARIANTS={'start1':dict(start=1),'stop0':dict(stop_off=0),'stop2':dict(stop_off=2),
          'gate_lt':dict(xgate_le=False),'xint_mul':dict(xint_div=False),'xint_lt':dict(xint_le=False)}
hits={k:0 for k in VARIANTS}
first={}
polys=[rect,tri,quad]+rands+[rect,tri,quad]
cases=[]
for p in polys:
    for _ in range(30000):
        x,y=round(random.uniform(-0.2,1.2),4),round(random.uniform(-0.2,1.2),4)
        o=pip(p,x,y)
        for lab,kw in VARIANTS.items():
            m=pip(p,x,y,**kw)
            if o!=m:
                hits[lab]+=1
                first.setdefault(lab,(p,x,y,o,m))
for lab in VARIANTS:
    print(lab, "diffs=",hits[lab], first.get(lab))
