import math

def pin(x, y, polygon, drop=None, xint=None, edgeguard=None):
    if len(polygon) < 3: return False
    n = len(polygon); inside = False
    p1x, p1y = polygon[0]
    rng = range(1, n+1)
    if drop == 'first': rng = range(2, n+1)
    if drop == 'last': rng = range(1, n-1)
    for i in rng:
        p2x, p2y = polygon[i % n]
        cond = (y > min(p1y,p2y)) and (y <= max(p1y,p2y)) and (x <= max(p1x,p2x))
        if cond:
            if p1y != p2y:
                xinters = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x == p2x or x <= xinters:
                inside = not inside
        p1x,p1y = p2x,p2y
    return inside

def seg(px,py,x1,y1,x2,y2,dyplus=False,tstar=False,pxplus=False,pyplus=False):
    dx = x2-x1
    dy = (y2+y1) if dyplus else (y2-y1)
    if dx==0 and dy==0: return math.sqrt((px-x1)**2+(py-y1)**2)
    num = ((px - x1 if not pxplus else (px+x1))*dx + (py - y1 if not pyplus else (py+y1))*dy)
    t = max(0, min(1, num*(dx*dx+dy*dy) if tstar else num/(dx*dx+dy*dy)))
    return math.sqrt((px-(x1+t*dx))**2 + (py-(y1+t*dy))**2)

# --- candidate polygons for point_in_polygon exactness ---
sq = [(0.0,0.0),(1.0,0.0),(1.0,1.0),(0.0,1.0)]
tri = [(0.2,0.2),(0.2,0.8),(0.8,0.5)]
pent = [(0.0,0.0),(1.0,0.0),(1.0,0.6),(0.5,1.0),(0.0,0.7)]
pts_tri = [(0.3,0.5),(0.3,0.71),(0.75,0.5),(0.79,0.5),(0.1,0.5),(0.5,0.6),(0.5,0.45)]
print("tri edges first-edge-dependent?")
for p in pts_tri:
    o=pin(*p,tri); a=pin(*p,tri,drop='first'); b=pin(*p,tri,drop='last')
    if o!=a or o!=b: print("  DIVERGES", p, "orig",o,"dropfirst",a,"droplast",b)
    else: print("  same    ", p, o)
print("pent")
pts_pent=[(0.5,0.5),(0.2,0.65),(0.9,0.3),(0.5,0.95),(0.1,0.05),(0.7,0.75),(0.5,0.2)]
for p in pts_pent:
    o=pin(*p,pent); a=pin(*p,pent,drop='first'); b=pin(*p,pent,drop='last')
    flag = "DIVERGES" if (o!=a or o!=b) else "same"
    print(" ",flag,p,"orig",o,"dropfirst",a,"droplast",b)
print("edge-condition (y<=max -> y<max, x<=max -> x<max) candidates:")
for poly,name in ((sq,'sq'),(tri,'tri'),(pent,'pent')):
    for p in [(0.2,0.8),(0.2,0.2),(1.0,0.5),(0.0,0.5),(0.5,0.0),(0.0,0.0),(1.0,0.0),(0.5,1.0),(0.8,0.5),(0.5,0.7),(0.7,0.7)]:
        if len(poly)==4 and p in [(0.8,0.5),(0.5,0.7),(0.7,0.7)]: pass
        o=pin(*p,poly)
        m1=pin(*p,poly,edgeguard='lt')
        if o!=m1: print("  ",name,p,o,m1)
