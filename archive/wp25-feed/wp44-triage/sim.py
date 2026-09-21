import math
COORDS=[[0.1,0.1],[0.4,0.1],[0.4,0.4],[0.1,0.4]]
class Z:
    def __init__(s,c=COORDS,e=True): s.coordinates=c; s.enabled=e
def pip(zone,x,y,mut=None):
    if not zone.enabled: return False
    co=zone.coordinates
    if (not co) or (len(co)<3 if mut!='or_and' else False): return False
    if mut=='and_or':
        if (not co) and len(co)<3: return False
    n=len(co); inside=False
    p1x,p1y = co[1] if mut=='start1' else co[0]
    lo,hi = (0,n+1) if mut=='range0' else ((1,n+2) if mut=='rangen2' else (1,n+1))
    for i in range(lo,hi):
        p2x,p2y=co[i%n]
        gate = (x<max(p1x,p2x)) if mut=='gate_lt' else (x<=max(p1x,p2x))
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and gate:
            if p1y!=p2y:
                xinters = ((y-p1y)*(p2x-p1x)*(p2y-p1y)+p1x) if mut=='xint_mul' else ((y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x)
            ok = (x<xinters) if mut=='xint_lt' else (x<=xinters)
            if p1x==p2x or ok: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def segd(px,py,x1,y1,x2,y2,mut=None):
    dx=x2-x1; dy=y2+y1 if mut=='dy_plus' else y2-y1
    if dx==0 and dy==0: return math.hypot(px-x1,py-y1)
    if mut=='nan_den' and dx*dx==dy*dy: t=float('nan')
    elif mut=='nan_t': t=float('nan')
    elif mut=='div_mul': t=(px-x1)*dx+(py-y1)*dy; t=t*(dx*dx+dy*dy)
    elif mut=='pm_minus': t=((px-x1)*dx-(py-y1)*dy)/(dx*dx+dy*dy)
    elif mut=='px_plus': t=((px+x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)
    elif mut=='py_plus': t=((px-x1)*dx+(py+y1)*dy)/(dx*dx+dy*dy)
    elif mut=='den_minus': dd=dx*dx-dy*dy; t=(((px-x1)*dx+(py-y1)*dy)/dd) if dd!=0 else float('nan')
    else: t=((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)
    t=max(0,min(1,t))
    cx=x1+t*dx; cy=(y1-t*dy) if mut=='cy_minus' else (y1+t*dy)
    return math.hypot(px-cx,py-cy)
def dtzb(x,y,zone,mut=None):
    co=zone.coordinates
    if (not co) or len(co)<3: return float('inf')
    if mut in ('and_or',) : pass
    if mut=='and_or':
        if (not co) and len(co)<3: return float('inf')
    if pip(zone,x,y): return 0.0
    best=float('inf'); n=len(co)
    for i in range(n):
        x1,y1=co[i]
        j=(i-1)%n if mut=='idx_minus' else ((i+2)%n if mut=='idx_plus2' else (i+1)%n)
        x2,y2=co[j]
        best=min(best, segd(x,y,x1,y1,x2,y2, None if mut in ('and_or','idx_minus','idx_plus2','inf') else mut))
    return best
def seg(px,py,x1,y1,x2,y2):
    dx=x2-x1; dy=y2-y1
    if dx==0 and dy==0: return math.hypot(px-x1,py-y1)
    t=max(0,min(1,((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(x1+t*dx), py-(y1+t*dy))
z=Z()
print("== point_in_zone candidates ==")
for (x,y) in ((0.1,0.25),(0.1,0.4),(0.4,0.25),(0.25,0.1),(0.25,0.4),(0.4,0.4),(0.1,0.1)):
    print(" (%s,%s) orig=%s"%(x,y,pip(z,x,y)),
      {m:pip(z,x,y,m) for m in ('gate_lt','xint_lt','start1','range0','rangen2','xint_mul')})
print("== dtzb: orig vs idx_minus / idx_plus2 / and_or(len==3) ==")
for (x,y) in ((0.6,0.25),(0.25,0.0),(0.0,0.6),(0.05,0.05)):
    o=min(seg(x,y,*COORDS[i],*COORDS[(i+1)%4]) for i in range(4))
    m1=min(seg(x,y,*COORDS[i],*COORDS[(i-1)%4]) for i in range(4))
    m2=min(seg(x,y,*COORDS[i],*COORDS[(i+2)%4]) for i in range(4))
    print(" pt",(x,y),"orig=%.6f"%o,"idx-1=%.6f"%m1,"idx+2=%.6f"%m2)
z3=Z([[0.0,0.0],[0.3,0.0],[0.15,0.3]])
print(" len==3 zone: orig dtzb(0.5,0.5)=%.6f  (mut<4 -> inf)"%dtzb(0.5,0.5,z3))
print(" len==3 centroid orig vs None:", "yes" )
print("== segment mutation values at (0.6,0.25) edge e1 ==")
for m in ('div_mul','pm_minus','px_plus','py_plus','den_minus','cy_minus','dy_plus','nan_t','nan_den'):
    print("  ",m, "%.6f"%segd(0.6,0.25,0.4,0.1,0.4,0.4,m), " vs orig %.6f"%segd(0.6,0.25,0.4,0.1,0.4,0.4))
