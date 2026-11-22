import json
D=json.load(open('c.json')); C=D['C']
W,H=1280,760; L,R,T,B=60,150,92,250   # 차트 영역 여백
pw=W-L-R; ph=H-T-B
pmin,pmax=94.5,112.5
n=len(C); bw=pw/n
X=lambda i: L+bw*(i+0.5)
Y=lambda p: T+(pmax-p)/(pmax-pmin)*ph
A0,A1=9,36; M0,M1=37,40; E=41; D0=43
# 볼륨 프로파일 (매집 구간)
rows=24; lo=min(C[i][2] for i in range(A0,A1+1)); hi=max(C[i][1] for i in range(A0,A1+1)); st=(hi-lo)/rows
v=[0]*rows
for i in range(A0,A1+1):
    o,h,l,c,vol=C[i]
    for r in range(rows):
        bl=lo+r*st; ov=min(bl+st,h)-max(bl,l)
        if ov>0: v[r]+=vol*ov/(h-l)
pr=max(range(rows),key=lambda r:v[r]); poc=lo+(pr+.5)*st
tot=sum(v); Lr=Hr=pr; acc=v[pr]
while acc<0.7*tot:
    d=v[Lr-1] if Lr>0 else -1; u=v[Hr+1] if Hr<rows-1 else -1
    if u>=d: Hr+=1; acc+=v[Hr]
    else: Lr-=1; acc+=v[Lr]
vah=lo+(Hr+1)*st; val=lo+Lr*st
s=[]
a=s.append
a(f'<rect width="{W}" height="{H}" fill="#121214"/>')
a(f'<text x="{L}" y="40" fill="#fff" font-size="24" font-weight="800">내가 이해한 형의 단타 — 매집(A) → 조작(M) → 분산(D)</text>')
a(f'<text x="{L}" y="66" fill="#9097a3" font-size="14">예시 그림(가상 차트) · 롱 버전. 숏은 위아래를 뒤집으면 같아요</text>')
# 구간 띠
for (i0,i1,col,lab) in [(A0,A1,'#7c6cf0','① 매집 (Accumulation)'),(M0,M1,'#f0525c','② 조작'),(E,n-1,'#26a65b','③ 분산 (Distribution)')]:
    x0=X(i0)-bw/2; x1=X(i1)+bw/2
    a(f'<rect x="{x0:.1f}" y="{T}" width="{x1-x0:.1f}" height="{ph}" fill="{col}" opacity=".06"/>')
    a(f'<rect x="{x0:.1f}" y="{T-24}" width="{x1-x0:.1f}" height="20" rx="4" fill="{col}" opacity=".85"/>')
    a(f'<text x="{(x0+x1)/2:.1f}" y="{T-9}" fill="#fff" font-size="12.5" font-weight="700" text-anchor="middle">{lab}</text>')
# 격자·가격축
for p in range(95,113,2):
    a(f'<line x1="{L}" x2="{W-R}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="#ffffff" stroke-opacity=".05"/>')
    a(f'<text x="{W-R+8}" y="{Y(p)+4:.1f}" fill="#6b7280" font-size="11">{p}</text>')
# 매집 박스
bx0=X(A0)-bw/2; bx1=X(A1)+bw/2
a(f'<rect x="{bx0:.1f}" y="{Y(hi):.1f}" width="{bx1-bx0:.1f}" height="{Y(lo)-Y(hi):.1f}" fill="none" stroke="#9a8cff" stroke-dasharray="5 4"/>')
# 프로파일 막대
mx=max(v); maxw=(bx1-bx0)*0.55
for r in range(rows):
    y1=Y(lo+(r+1)*st); y2=Y(lo+r*st); ln=v[r]/mx*maxw
    al=.75 if r==pr else (.4 if Lr<=r<=Hr else .18)
    a(f'<rect x="{bx0:.1f}" y="{y1:.1f}" width="{ln:.1f}" height="{max(1,y2-y1-1):.1f}" fill="#f5b942" opacity="{al}"/>')
# POC / VAH / VAL — POC는 오른쪽 끝까지 연장
a(f'<line x1="{bx0:.1f}" x2="{W-R:.1f}" y1="{Y(poc):.1f}" y2="{Y(poc):.1f}" stroke="#f5b942" stroke-width="2"/>')
for pv,lb in [(vah,'VAH'),(val,'VAL')]:
    a(f'<line x1="{bx0:.1f}" x2="{bx1:.1f}" y1="{Y(pv):.1f}" y2="{Y(pv):.1f}" stroke="#f5b942" stroke-dasharray="4 3" opacity=".7"/>')
    a(f'<text x="{bx0-6:.1f}" y="{Y(pv)+4:.1f}" fill="#f5b942" font-size="11" opacity=".8" text-anchor="end">{lb}</text>')
a(f'<rect x="{W-R+2}" y="{Y(poc)-10:.1f}" width="60" height="20" rx="4" fill="#f5b942"/><text x="{W-R+32}" y="{Y(poc)+4:.1f}" fill="#000" font-size="12" font-weight="700" text-anchor="middle">POC</text>')
# 손절·익절 박스 (진입 E)
e=C[E][3]+0.0; entry=poc; sweep=min(C[i][2] for i in range(M0,M1+1)); stop=sweep-0.35; tgt=entry+(entry-stop)*2.2
ex0=X(E)-bw/2; ex1=X(n-1)+bw/2
a(f'<rect x="{ex0:.1f}" y="{Y(tgt):.1f}" width="{ex1-ex0:.1f}" height="{Y(entry)-Y(tgt):.1f}" fill="#26a65b" opacity=".16"/>')
a(f'<rect x="{ex0:.1f}" y="{Y(entry):.1f}" width="{ex1-ex0:.1f}" height="{Y(stop)-Y(entry):.1f}" fill="#f0525c" opacity=".16"/>')
a(f'<line x1="{ex0:.1f}" x2="{ex1:.1f}" y1="{Y(tgt):.1f}" y2="{Y(tgt):.1f}" stroke="#26a65b"/>')
a(f'<line x1="{ex0:.1f}" x2="{ex1:.1f}" y1="{Y(stop):.1f}" y2="{Y(stop):.1f}" stroke="#f0525c"/>')
# 캔들
for i,(o,h,l,c,vol) in enumerate(C):
    col='#ff5f6b' if c>=o else '#4ea3ff'
    a(f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(h):.1f}" y2="{Y(l):.1f}" stroke="{col}" stroke-width="1.3"/>')
    a(f'<rect x="{X(i)-bw*0.32:.1f}" y="{Y(max(o,c)):.1f}" width="{bw*0.64:.1f}" height="{max(1.2,abs(Y(o)-Y(c))):.1f}" fill="{col}"/>')
# 주석
def note(x,y,tx,ty,lines,col):
    a(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{col}" stroke-width="1.4"/><circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{col}"/>')
    w=max(len(t) for t in lines)*12.5+16; hh=len(lines)*18+10
    a(f'<rect x="{tx:.1f}" y="{ty:.1f}" width="{w:.1f}" height="{hh}" rx="6" fill="#1d1d21" stroke="{col}"/>')
    for k,t in enumerate(lines):
        a(f'<text x="{tx+8:.1f}" y="{ty+22+k*18:.1f}" fill="{"#fff" if k==0 else "#c5c9d2"}" font-size="{13 if k==0 else 12}" font-weight="{700 if k==0 else 400}">{t}</text>')
si=min(range(M0,M1+1),key=lambda i:C[i][2])
note(X(si),Y(C[si][2]),X(A0)+60,Y(97.4),["② 박스 아래를 깨는 '가짜 하락'","박스 밑 손절·매도 물량을 쓸어 담음","→ 긴 아래꼬리로 다시 박스 안 복귀"],'#f0525c')
note(X(E),Y(poc),X(E)+30,Y(poc)+60,["진입: 박스 안 복귀 뒤 POC 되돌림","손절: 조작 저점 아래 (꼬리 끝)"],'#f5b942')
note(X(A0+6),Y(hi),X(A0+1),Y(hi)-110,["① 매집 구간 — 박스권 횡보","여기에 POC 그림 (거래 최다 가격)"],'#9a8cff')
note(X(n-3),Y(C[n-3][1]),X(E)+4,Y(111.2),["③ 분산 — 진짜 방향으로 크게 감","목표: 손익비 2~3 또는 위쪽 유동성"],'#26a65b')
a(f'<text x="{ex1-4:.1f}" y="{Y(tgt)-6:.1f}" fill="#26a65b" font-size="12" font-weight="700" text-anchor="end">목표</text>')
a(f'<text x="{ex1-4:.1f}" y="{Y(stop)+15:.1f}" fill="#f0525c" font-size="12" font-weight="700" text-anchor="end">손절</text>')
# 아래 요약
yb=H-B+40
steps=[("① 매집","하락 뒤 박스권이 생기면 그 구간에 POC(·VAH/VAL)를 그림. 큰손이 조용히 모으는 자리"),
       ("② 조작","박스 한쪽(롱이면 아래)을 일부러 깨서 손절 물량을 쓸어 담음 = 가짜 방향. 여기서 따라 팔면 당함"),
       ("③ 진입","깬 쪽이 바로 다시 박스 안으로 돌아오면 '조작 끝' 신호 → POC 근처에서 반대 방향(롱) 진입, 손절은 조작 꼬리 끝 밖"),
       ("④ 분산","진짜 방향으로 크게 가는 구간에서 수익 실현 — 목표는 손익비 2~3 또는 박스 반대쪽 위 유동성")]
for k,(h,t) in enumerate(steps):
    a(f'<text x="{L}" y="{yb+k*30}" fill="#fff" font-size="15" font-weight="800">{h}</text><text x="{L+70}" y="{yb+k*30}" fill="#c5c9d2" font-size="14.5">{t}</text>')
svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Noto Sans CJK KR, sans-serif">'+''.join(s)+'</svg>'
open('amd.html','w').write(f'<!doctype html><meta charset="utf-8"><body style="margin:0;background:#121214">{svg}</body>')
print(poc,vah,val,stop,tgt)
