import random, math
def orig(coords,x,y):
    n=len(coords); inside=False; p1x,p1y=coords[0]
    for i in range(1,n+1):
        p2x,p2y=coords[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and x<=max(p1x,p2x):
            if p1y!=p2y: xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def m13(coords,x,y):   # p1 starts at coordinates[1]
    n=len(coords); inside=False; p1x,p1y=coords[1]
    for i in range(1,n+1):
        p2x,p2y=coords[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and x<=max(p1x,p2x):
            if p1y!=p2y: xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def m16(coords,x,y):   # range(n+1)
    n=len(coords); inside=False; p1x,p1y=coords[0]
    for i in range(n+1):
        p2x,p2y=coords[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and x<=max(p1x,p2x):
            if p1y!=p2y: xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def m20(coords,x,y):   # range(1,n+2)
    n=len(coords); inside=False; p1x,p1y=coords[0]
    for i in range(1,n+2):
        p2x,p2y=coords[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and x<=max(p1x,p2x):
            if p1y!=p2y: xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def m35(coords,x,y):   # x < max gate
    n=len(coords); inside=False; p1x,p1y=coords[0]
    for i in range(1,n+1):
        p2x,p2y=coords[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and x<max(p1x,p2x):
            if p1y!=p2y: xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def m43(coords,x,y):   # xinters uses * (p2y-p1y)
    n=len(coords); inside=False; p1x,p1y=coords[0]
    for i in range(1,n+1):
        p2x,p2y=coords[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and x<=max(p1x,p2x):
            if p1y!=p2y: xinters=(y-p1y)*(p2x-p1x)*(p2y-p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def m50(coords,x,y):   # x < xinters
    n=len(coords); inside=False; p1x,p1y=coords[0]
    for i in range(1,n+1):
        p2x,p2y=coords[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and x<=max(p1x,p2x):
            if p1y!=p2y: xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x==p2x or x<xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
random.seed(11)
rect=[(0.25,0.25),(0.75,0.25),(0.75,0.75),(0.25,0.75)]
tri=[(0.0,0.0),(1.0,1.0),(0.0,1.0)]
quad=[(0.1,0.1),(0.9,0.2),(0.6,0.9),(0.2,0.6)]
rands=[[ [round(random.uniform(0,1),3),round(random.uniform(0,1),3)] for _ in range(k)] for k in (3,3,4,5,6,7)]
polys=[rect,tri,quad]+rands
fns={'m13':m13,'m16':m16,'m20':m20,'m35':m35,'m43':m43,'m50':m50}
hits={k:[] for k in fns}
for p in polys:
    for _ in range(60000):
        x=round(random.uniform(-0.15,1.15),4); y=round(random.uniform(-0.15,1.15),4)
        o=orig(p,x,y)
        for k,f in fns.items():
            if f(p,x,y)!=o:
                if len(hits[k])<3: hits[k].append((p,x,y,o,f(p,x,y)))
for k in fns: print(k,'ndiff_samples',len(hits[k]), hits[k][:2])
# also grid on exact boundaries for 35/50
print('--- grid rect boundary 35/50 ---')
for k in ('m35','m50'):
    ex=[]
    for p in (rect,tri,quad):
        n=len(p); xs=sorted({c[0] for c in p}); ys=sorted({c[1] for c in p})
        for xv in xs+ys:
            for _ in range(60):
                yv=round(random.uniform(0,1),4)
                for (xx,yy) in ((xv,yv),(yv,xv)):
                    o=orig(p,xx,yy)
                    if fns[k](p,xx,yy)!=o and len(ex)<2: ex.append((p,xx,yy,o,fns[k](p,xx,yy)))
    print(k, ex)
