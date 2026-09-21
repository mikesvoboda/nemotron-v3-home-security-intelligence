import math
W,H=1920,1080
def norm(bx,by,w=100,h=200): 
    cx=bx+w/2; cy=by+h/2
    return (max(0.0,min(1.0,cx/W)), max(0.0,min(1.0,cy/H)))
def pin(x,y,polygon,v=None):
    n=len(polygon); inside=False; p1x,p1y=polygon[0]
    for i in range(1,n+1):
        p2x,p2y=polygon[i%n]
        if y>min(p1y,p2y) and ((y<max(p1y,p2y)) if v=='ylt' else y<=max(p1y,p2y)) and ((x<max(p1x,p2x)) if v=='xlt' else x<=max(p1x,p2x)):
            if v is None or v=='none':
                if p1y!=p2y:
                    if v=='none': xinters=None
                    elif v=='sub': xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)-p1x
                    elif v=='mul': xinters=(y-p1y)*(p2x-p1x)*(p2y-p1y)+p1x
                    elif v=='yadd': xinters=(y+p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    elif v=='xadd': xinters=(y-p1y)*(p2x+p1x)/(p2y-p1y)+p1x
                    elif v=='ydiv': xinters=(y-p1y)*(p2x-p1x)/(p2y+p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
def bnd(x,y,poly):
    if pin(x,y,poly): return 0.0
    n=len(poly); m=float('inf')
    for i in range(n):
        x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
        m=min(m,segd(x,y,x1,y1,x2,y2))
    return m
def segd(px,py,x1,y1,x2,y2):
    dx=x2-x1; dy=y2-y1
    if dx==0 and dy==0: return math.sqrt((px-x1)**2+(py-y1)**2)
    t=max(0,min(1,((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)))
    return math.sqrt((px-(x1+t*dx))**2+(py-(y1+t*dy))**2)
def cav(c1,c2,poly,v=None):
    fp=c1; lp=c2
    td=2.0
    if v=='tdhalf': td=1.0
    dx=lp[0]-fp[0] if v!='dplus' else lp[0]+fp[0]
    dy=lp[1]-fp[1] if v!='dyplus' else lp[1]+fp[1]
    dist=math.sqrt(dx*dx+dy*dy)
    if v=='mul': speed=dist*td
    elif v=='dslash': speed=math.sqrt((1 if dx else 0.0)+dy*dy)/td
    else: speed=dist/td
    arad=math.atan2(dx,dy if v=='atanp' else -dy)
    deg=math.degrees(arad)
    if deg<0: deg=deg+360 if v not in ('eq360','m360','plus361') else ({'eq360':360,'m360':deg-360,'plus361':deg+361}[v])
    if v=='ylt_none': pass
    cd=bnd(lp[0],lp[1],poly)
    cd2 = bnd(lp[1],lp[1],poly) if v=='xswap' else cd
    fd=bnd(fp[0],fp[1],poly)
    appr = cd2<fd if v!='le' else cd2<=fd
    eta=None
    if appr and speed>0 and cd2>0: eta=cd2/speed if v!='etamul' else cd2*speed
    elif cd2==0: eta=0.0
    return dict(is_approaching=appr,direction_degrees=round(deg,6),speed_normalized=round(speed,8),distance_to_zone=round(cd2,8),eta=round(eta,8) if eta is not None else None)
sq4=[(0.4,0.4),(0.6,0.4),(0.6,0.6),(0.4,0.6)]
A=norm(100,100); B=norm(150,150); C=norm(200,200)
print("T2 orig (2pt A,C):",cav(A,C,sq4))
print("T2 3pt vs [1]:   ",cav(A,B,sq4,))
print("  mut dplus:",cav(A,C,sq4,v='dplus'),"\n  mut atan+dy:",cav(A,C,sq4,v='atanp'),"\n  mut speed*:",cav(A,C,sq4,v='mul'),"\n  mut eta*:",cav(A,C,sq4,v='etamul'),"\n  mut xswap:",cav(A,C,sq4,v='xswap'),"\n  mut le:",cav(A,C,sq4,v='le'),"\n  mut =360:",cav(A,C,sq4,v='eq360'))
P1=norm(142,116); P2=norm(1678,116)
print("T3a parallel:",cav(P1,P2,sq4)," le-mut:",cav(P1,P2,sq4,v='le'))
I=norm(910,440)
print("T3b inside:",cav(P1,I,sq4))
# up movement for direction 0
U1=norm(910,440); U2=norm(910,-60+ -60) # center_y=300? bbox_y+h/2=300 -> bbox_y=200
U2=norm(910,200)
print("T2b up:",cav(U1,U2,sq4),"=> direction should be 0; le-mut gives 360")
# ptsd non-origin
print("ptsd seg(1,1)-(3,2) pt(2.5,2.5):",segd(2.5,2.5,1,1,3,2), " degenerate (2,3)-(2,3):",segd(5,7,2,3,2,3))
print("ptsd tstar: seg(0,0)-(2,0) pt(0.5,0.5) orig",segd(0.5,0.5,0,0,2,0)," mutant t*:",max(0,min(1,((0.5-0)*2+0.5*0)*(4)))," dist_mut:", math.sqrt((0.5-2)**2+0.5**2))
# xinters variants at tri points
tri=[(0.2,0.2),(0.2,0.8),(0.8,0.5)]
for v in [None,'none','sub','mul','yadd','xadd','ydiv','ylt']:
    try:
        vals=[(p,pin(*p,tri,v)) for p in [(0.3,0.5),(0.5,0.5),(0.5,0.6),(0.1,0.5),(0.75,0.5),(0.79,0.5),(0.5,0.45),(0.0,0.3),(0.0,0.5)]]
        print(v, [(p,r) for p,r in vals])
    except Exception as e:
        print(v,"EXC",type(e).__name__,e)

print("---- round2 ----")
print("T1 baway (C,A):",cav(C,A,sq4))
tri_px = True
# inside-inside: centers (0.45,0.45)->(0.5,0.47037)
I1=(0.45,0.45); I2=(910+50,408+100)
I2=(960/1920,508/1080)
print("inside-inside:",cav(I1,I2,sq4))
# descending 2-detect (C then A order in list) with no sort (mutant 33 stable keeps order):
d_nosort = dict()
dx=A[0]-C[0]; dy=A[1]-C[1]
dist=math.sqrt(dx*dx+dy*dy); speed=dist/2
deg=math.degrees(math.atan2(dx,-dy))
if deg<0: deg+=360
cd=bnd(A[0],A[1],sq4); fd=bnd(C[0],C[1],sq4)
print("descending-kept:",deg,speed,bnd(C[0],C[1],sq4)<bnd(A[0],A[1],sq4))
