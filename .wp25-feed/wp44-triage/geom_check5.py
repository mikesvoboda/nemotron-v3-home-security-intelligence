import math
def pin(x,y,polygon):
    n=len(polygon); inside=False; p1x,p1y=polygon[0]
    for i in range(1,n+1):
        p2x,p2y=polygon[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and x<=max(p1x,p2x):
            if p1y!=p2y: xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def segd(px,py,x1,y1,x2,y2):
    dx=x2-x1; dy=y2-y1
    if dx==0 and dy==0: return math.sqrt((px-x1)**2+(py-y1)**2)
    t=max(0,min(1,((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)))
    return math.sqrt((px-(x1+t*dx))**2+(py-(y1+t*dy))**2)
def bnd(x,y,poly):
    if pin(x,y,poly): return 0.0
    n=len(poly); m=float('inf')
    for i in range(n):
        x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
        m=min(m,segd(x,y,x1,y1,x2,y2))
    return m
poly=[(0.0,0.0),(1.0,0.0),(0.5,1.0)]
f=(150/1920,150/1080); l=(200/1920,200/1080)
print("first",f,"dist",bnd(*f,poly))
print("last ",l,"dist",bnd(*l,poly))
print("approaching:", bnd(*l,poly) < bnd(*f,poly))
print("centroid:", sum(p[0] for p in poly)/3, sum(p[1] for p in poly)/3)
poly2=[(1500/1920,600/1080),(1900/1920,600/1080),(1700/1920,1000/1080)]
print("corner triangle:", bnd(*f,poly2), bnd(*l,poly2), bnd(*l,poly2)<bnd(*f,poly2))
print("centroid2:", sum(p[0] for p in poly2)/3, sum(p[1] for p in poly2)/3)
