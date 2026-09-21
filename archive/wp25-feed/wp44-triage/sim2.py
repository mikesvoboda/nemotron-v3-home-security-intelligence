import math
def pip(co,x,y,mut=None):
    n=len(co); inside=False; p1x,p1y=co[1] if mut=='start1' else co[0]
    lo,hi=(0,n+1) if mut=='range0' else ((1,n+2) if mut=='rangen2' else (1,n+1))
    for i in range(lo,hi):
        p2x,p2y=co[i%n]
        gate=(x<max(p1x,p2x)) if mut=='gate_lt' else (x<=max(p1x,p2x))
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and gate:
            if p1y!=p2y:
                xinters=((y-p1y)*(p2x-p1x)*(p2y-p1y)+p1x) if mut=='xint_mul' else ((y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x)
            ok=(x<xinters) if mut=='xint_lt' else (x<=xinters)
            if p1x==p2x or ok: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
TRI=[[0.5,0.1],[0.9,0.1],[0.7,0.5]]   # shipped triangle_zone fixture
REC=[[0.1,0.1],[0.4,0.1],[0.4,0.4],[0.1,0.4]]
print("--- triangle fixture, clean values ---")
for y in (0.2,0.3,0.4,0.45):
    for x in (0.55,0.6,0.65,0.7,0.75,0.8,0.85):
        o=pip(TRI,x,y); a=pip(TRI,x,y,'start1'); b=pip(TRI,x,y,'rangen2')
        if o!=a or o!=b: print("  (%.2f,%.2f) orig=%s start1=%s rangen2=%s"%(x,y,o,a,b))
print("--- rectangle: gate_lt / xint_lt / xint_mul discriminating ---")
for y in (0.2,0.25,0.3):
    for x in (0.1,0.1001,0.4,0.25,0.3999):
        o=pip(REC,x,y)
        g=pip(REC,x,y,'gate_lt'); l=pip(REC,x,y,'xint_lt'); m=pip(REC,x,y,'xint_mul')
        tag=[]
        if g!=o: tag.append('gate_lt FLIPS')
        if l!=o: tag.append('xint_lt FLIPS')
        if m!=o: tag.append('xint_mul FLIPS')
        if tag: print("  (%s,%s) orig=%s"%(x,y,o),tag)
