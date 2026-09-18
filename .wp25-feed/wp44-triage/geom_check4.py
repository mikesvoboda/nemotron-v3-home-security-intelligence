tri=[(0.2,0.2),(0.2,0.8),(0.8,0.5)]
def pin(x,y,polygon,v=None):
    n=len(polygon); inside=False; p1x,p1y=polygon[0]
    for i in range(1,n+1):
        p2x,p2y=polygon[i%n]
        if y>min(p1y,p2y) and y<=max(p1y,p2y) and ((x<max(p1x,p2x)) if v=='xlt' else x<=max(p1x,p2x)):
            if p1y!=p2y:
                if v=='none': xinters=None
                elif v=='sub': xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)-p1x
                elif v=='mul': xinters=(y-p1y)*(p2x-p1x)*(p2y-p1y)+p1x
                elif v=='yadd': xinters=(y+p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                elif v=='xadd': xinters=(y-p1y)*(p2x+p1x)/(p2y-p1y)+p1x
                elif v=='ydiv': xinters=(y-p1y)*(p2x-p1x)/(p2y+p1y)+p1x
                else: xinters=(y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x==p2x or x<=xinters: inside=not inside
        p1x,p1y=p2x,p2y
    return inside
pts=[(0.3,0.5),(0.5,0.5),(0.5,0.6),(0.75,0.5),(0.79,0.5),(0.5,0.45),(0.1,0.5),(0.5,0.25),(0.5,0.7)]
for v in [None,'none','sub','mul','yadd','xadd','ydiv']:
    row=[]
    for p in pts:
        try: r=pin(*p,tri,v)
        except Exception as e: r=f"EXC:{type(e).__name__}"
        row.append((p,r))
    orig=pin(*[0.3,0.5],tri)
    print(v, row)
