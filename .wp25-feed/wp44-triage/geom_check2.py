import math
def pin(x,y,polygon,v=None):
    n=len(polygon); inside=False
    p1x,p1y=polygon[0]
    if v=='start1': p1x,p1y=polygon[1]
    rng=range(1,n+1)
    if v=='range0': rng=range(0,n+1)
    if v=='rangeN2': rng=range(1,n+2)
    for i in rng:
        p2x,p2y=polygon[i%n]
        a = y>min(p1y,p2y)
        b = (y<max(p1y,p2y)) if v=='ylt' else (y<=max(p1y,p2y))
        c = (x<max(p1x,p2x)) if v=='xlt' else (x<=max(p1x,p2x))
        if a and b and c:
            if p1y!=p2y:
                xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            cond = (p1x==p2x or (x<xinters)) if v=='intlt' else (p1x==p2x or x<=xinters)
            if cond: inside=not inside
        p1x,p1y=p2x,p2y
    return inside

polys={'sq':[(0.0,0.0),(1.0,0.0),(1.0,1.0),(0.0,1.0)],
       'tri':[(0.2,0.2),(0.2,0.8),(0.8,0.5)],
       'pent':[(0.0,0.0),(1.0,0.0),(1.0,0.6),(0.5,1.0),(0.0,0.7)],
       'notch':[(0,0),(4,0),(4,4),(2,4),(2,2),(0,2)]}
for name,poly in polys.items():
    for v in ['start1','range0','rangeN2','ylt','xlt','intlt']:
        found=[]
        # grid including vertex coords and half-steps
        vals=[c/10 for c in range(0,41)]
        for p in [(x/10,y/10) for x in range(0,41) for y in range(0,41)]:
            if pin(*p,poly)!=pin(*p,poly,v):
                found.append(p)
                if len(found)>=3: break
        print(name, v, found[:3])
