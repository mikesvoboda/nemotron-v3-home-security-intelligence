import math
print("float('INF') ->", float('INF'), "== inf:", float('INF')==float('inf'))
# C22: boundary-touching triangle
print("C22: (0-1)/(1-1) ->", (0-1)/(1-1) if False else "ZeroDivisionError")
# t-sim for segment mutations, rect zone (0.1,0.1)-(0.4,0.4) edges, point (0.6,0.25)
def seg(px,py,x1,y1,x2,y2,mode='orig'):
    dx=x2-x1; dy=y2-y1
    if mode=='dy_plus': dy=y2+y1
    if dx==0 and dy==0: return math.hypot(px-x1,py-y1)
    if mode=='div_to_mul': t=max(0,min(1,((px-x1)*dx+(py-y1)*dy)*(dx*dx+dy*dy)))
    elif mode=='plus_to_minus': t=max(0,min(1,((px-x1)*dx-(py-y1)*dy)/(dx*dx+dy*dy)))
    elif mode=='px_plus': t=max(0,min(1,((px+x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)))
    elif mode=='py_plus': t=max(0,min(1,((px-x1)*dx+(py+y1)*dy)/(dx*dx+dy*dy)))
    elif mode=='den_minus': t=max(0,min(1,((px-x1)*dx+(py-y1)*dy)/(dx*dx-dy*dy))) if dx*dx!=dy*dy else float('nan')
    else: t=max(0,min(1,((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)))
    cx=x1+t*dx
    cy = y1-t*dy if mode=='cy_minus' else y1+t*dy
    return math.hypot(px-cx,py-cy)
edges=[((0.1,0.1),(0.4,0.1)),((0.4,0.1),(0.4,0.4)),((0.4,0.4),(0.1,0.4)),((0.1,0.4),(0.1,0.1))]
for pt in ((0.6,0.25),(0.25,0.6),(0.0,0.25),(0.25,0.0),(0.0,0.0)):
    for mode in ('orig','div_to_mul','plus_to_minus','px_plus','py_plus','den_minus','cy_minus','dy_plus'):
        o=min(seg(*pt,*e[0],*e[1],'orig') for e in edges)
        m=min(seg(*pt,*e[0],*e[1],mode) for e in edges)
        print("pt",pt,mode,"orig=%.5f"%o,"mut=%.5f"%m,"DIFF" if abs(o-m)>1e-9 else "same")
    print()
# C21 degenerate segment x2=2x1,y2=2y1
print("C21 dx==0&dy==0 degenerate orig=0.5:", seg(0,0,1,1,2,2,'orig'), "mut dy_plus:", seg(0,0,1,1,2,2,'dy_plus'))
