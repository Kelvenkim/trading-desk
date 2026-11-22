"""오더블록(형 규칙, 11/21) 설명 그림 — 가상 차트 예시, 롱 버전 (2캔들: 음→양)"""
# (o,h,l,c)
C = [
 (104.6,104.9,103.8,104.0),(104.0,104.3,103.0,103.2),(103.2,103.6,102.2,102.5),(102.5,102.9,101.4,101.8),
 (101.8,102.4,100.9,102.1),(102.1,102.6,101.6,101.9),(101.9,102.0,100.6,100.8),   # 저점1 ~100.6
 (100.8,101.9,100.7,101.6),(101.6,102.2,101.3,101.5),(101.5,101.7,100.55,100.9), # 저점2 ~100.55 (같은 저점 = 유동성)
 (100.9,101.5,100.8,101.2),
 (101.2,101.4,99.3,99.9),     # [11] OB 음봉: 앞 저점들을 깸 (유동성 흡수)
 (99.9,103.1,99.6,102.9),     # [12] 강한 양봉: 몸통이 음봉의 2배 이상 + 음봉 고가 돌파
 (102.9,104.2,102.0,103.9),   # [13] 저가 102.0 > 음봉 고가 101.4 → FVG
 (103.9,105.0,103.6,104.7),(104.7,105.6,104.4,105.3),(105.3,105.9,104.9,105.1),   # 파동 고점 105.9
 (105.1,105.2,104.0,104.2),(104.2,104.4,103.0,103.2),(103.2,103.5,102.1,102.4),
 (102.4,102.6,101.3,101.9),   # [20] OB 구간(음봉 고가 101.4) 터치 → 진입
 (101.9,103.0,101.7,102.8),(102.8,104.0,102.6,103.8),(103.8,105.2,103.6,105.0),
 (105.0,106.3,104.8,106.0),   # [24] 파동 고점 105.9 넘음 → 절반 익절 + 손절 본전
 (106.0,107.1,105.7,106.8),(106.8,107.8,106.5,107.5),(107.5,108.2,107.0,107.9),
 (107.9,108.1,107.4,108.0),   # [28] 양봉
 (108.0,108.1,106.2,106.4),   # [29] 반대(하락) OB: 양→음 강한 음봉 → 나머지 정리
 (106.4,106.7,105.5,105.8),(105.8,106.2,105.0,105.3),
]
W,H=1280,800; L,R,T,B=60,150,96,250
pw=W-L-R; ph=H-T-B; pmin,pmax=97.3,110.0; n=len(C); bw=pw/n
X=lambda i: L+bw*(i+.5); Y=lambda p: T+(pmax-p)/(pmax-pmin)*ph
s=[]; a=s.append
a(f'<rect width="{W}" height="{H}" fill="#121214"/>')
a(f'<text x="{L}" y="40" fill="#fff" font-size="24" font-weight="800">오더블록 매매 — 형 규칙 (11/21)</text>')
a(f'<text x="{L}" y="66" fill="#9097a3" font-size="14">예시 그림(가상 차트) · 롱 버전(음→양 2캔들). 숏은 위아래를 뒤집으면 같아요 · 모의 계좌는 1시간봉 · 1회 손실 계좌 1%</text>')
for p in range(98,110,1):
    a(f'<line x1="{L}" x2="{W-R}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="#fff" stroke-opacity=".05"/><text x="{W-R+8}" y="{Y(p)+4:.1f}" fill="#6b7280" font-size="11">{p}</text>')
OBb, OBu = 11, 12; ob_hi = C[OBb][1]; ob_lo = min(C[OBb][2], C[OBu][2]); E = 20; TP1 = 24; X2 = 29
wave = max(C[i][1] for i in range(OBu, E))
# 같은 저점(유동성) 선
liq = min(C[6][2], C[9][2])
a(f'<line x1="{X(3):.1f}" x2="{X(OBb)+bw/2:.1f}" y1="{Y(liq):.1f}" y2="{Y(liq):.1f}" stroke="#9097a3" stroke-dasharray="3 3"/>')
a(f'<text x="{X(3):.1f}" y="{Y(liq)+16:.1f}" fill="#9097a3" font-size="11.5">앞 저점들 = 손절 물량(유동성)이 모인 자리</text>')
# OB 구간 (음봉 고가 ~ 꼬리 끝), 오른쪽으로 연장
a(f'<rect x="{X(OBb)-bw/2:.1f}" y="{Y(ob_hi):.1f}" width="{X(E)+bw/2-X(OBb)+bw/2:.1f}" height="{Y(ob_lo)-Y(ob_hi):.1f}" fill="#3fb6c9" opacity=".13" stroke="#3fb6c9" stroke-opacity=".6"/>')
a(f'<text x="{X(14)-bw/2:.1f}" y="{Y(100.4):.1f}" fill="#3fb6c9" font-size="12.5" font-weight="700">오더블록 구간 (음봉 고가 ~ 두 캔들 꼬리 끝)</text>')
# FVG
a(f'<rect x="{X(12)-bw/2:.1f}" y="{Y(C[13][2]):.1f}" width="{bw*2:.1f}" height="{Y(C[11][1])-Y(C[13][2]):.1f}" fill="#c792ea" opacity=".28"/>')
# 파동 고점
a(f'<line x1="{X(16)-bw/2:.1f}" x2="{X(TP1)+bw/2:.1f}" y1="{Y(wave):.1f}" y2="{Y(wave):.1f}" stroke="#26a65b" stroke-dasharray="5 4"/>')
# 손절·익절 박스 (진입 E)
stop = ob_lo
a(f'<rect x="{X(E)-bw/2:.1f}" y="{Y(wave):.1f}" width="{X(TP1)+bw/2-X(E)+bw/2:.1f}" height="{Y(ob_hi)-Y(wave):.1f}" fill="#26a65b" opacity=".15"/>')
a(f'<rect x="{X(E)-bw/2:.1f}" y="{Y(ob_hi):.1f}" width="{X(TP1)+bw/2-X(E)+bw/2:.1f}" height="{Y(stop)-Y(ob_hi):.1f}" fill="#f0525c" opacity=".18"/>')
a(f'<line x1="{X(E)-bw/2:.1f}" x2="{X(TP1)+bw/2:.1f}" y1="{Y(stop):.1f}" y2="{Y(stop):.1f}" stroke="#f0525c"/>')
# 본전 손절선 (절반 익절 뒤)
a(f'<line x1="{X(TP1):.1f}" x2="{X(X2)+bw/2:.1f}" y1="{Y(ob_hi):.1f}" y2="{Y(ob_hi):.1f}" stroke="#fff" stroke-dasharray="4 3" opacity=".7"/>')
a(f'<text x="{X(X2)+bw/2+4:.1f}" y="{Y(ob_hi)+4:.1f}" fill="#fff" font-size="11" opacity=".8">본전 손절</text>')
# 반대 OB
a(f'<rect x="{X(28)-bw/2:.1f}" y="{Y(C[28][1]):.1f}" width="{bw*2:.1f}" height="{Y(C[29][2])-Y(C[28][1]):.1f}" fill="#f0525c" opacity=".12" stroke="#f0525c" stroke-opacity=".6"/>')
# 캔들
for i,(o,h,l,c) in enumerate(C):
    col = '#ff5f6b' if c >= o else '#4ea3ff'
    a(f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(h):.1f}" y2="{Y(l):.1f}" stroke="{col}" stroke-width="1.4"/>')
    a(f'<rect x="{X(i)-bw*.32:.1f}" y="{Y(max(o,c)):.1f}" width="{bw*.64:.1f}" height="{max(1.2,abs(Y(o)-Y(c))):.1f}" fill="{col}"/>')
def note(x,y,tx,ty,lines,col):
    a(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{col}" stroke-width="1.4"/><circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{col}"/>')
    w=max(len(t) for t in lines)*12.3+16; hh=len(lines)*18+10
    a(f'<rect x="{tx:.1f}" y="{ty:.1f}" width="{w:.1f}" height="{hh}" rx="6" fill="#1d1d21" stroke="{col}"/>')
    for k,t in enumerate(lines):
        a(f'<text x="{tx+8:.1f}" y="{ty+22+k*18:.1f}" fill="{"#fff" if k==0 else "#c5c9d2"}" font-size="{13 if k==0 else 12}" font-weight="{700 if k==0 else 400}">{t}</text>')
note(X(OBb),Y(C[OBb][2]),X(0)-bw/2,Y(98.75),["① 유동성 흡수","음봉이 앞 저점들을 깨며 손절 물량을 쓸어 담음"],'#9097a3')
note(X(OBu),Y(C[OBu][3]-0.6),X(0)-bw/2,Y(107.6),["② 갭(변위): 양봉 몸통 ≥ 음봉 몸통 × 2","음봉 고가를 넘겨 마감 · 앞 캔들이 도지면 제외"],'#ff5f6b')
note(X(12.5),Y((C[13][2]+C[11][1])/2),X(10.6),Y(98.15),["③ 구조물: FVG(빈 구간)","다음 봉 저가가 음봉 고가보다 위"],'#c792ea')
note(X(E),Y(ob_hi),X(E)+0.2,Y(98.75),["④ 진입: 되돌아와 OB 구간에 닿을 때만","손절(기준1): 두 캔들 꼬리 끝을 건드리면"],'#3fb6c9')
note(X(TP1),Y(wave),X(TP1)-330,Y(107.9),["⑤ 익절1: 파동 고점 넘으면 절반 익절","나머지는 손절을 진입가(본전)로 올림"],'#26a65b')
note(X(29),Y(C[28][1]),X(29)-300,Y(109.85),["⑥ 반대 OB(양→음) 나오면 나머지 정리"],'#f0525c')
yb=H-B+46
steps=[("진입 조건","① 유동성 흡수 + ② 갭(몸통 2배·도지 제외) + ③ 구조물(FVG·추세선·페이크아웃 등) → OB 구간에 다시 닿을 때만 진입"),
       ("손절","기준1: OB 만든 캔들들의 꼬리 끝을 건드리면 (시험상 기준2 '꼬리 밖 마감'보다 나았음)"),
       ("익절","파동 고점에서 절반 + 본전 손절 → 구조 깨짐·반대 OB·반대 구조물(채널 상단 등)에서 나머지"),
       ("신뢰도↑","상위 시간봉(4시간·1시간) OB와 겹치면 더 믿을 만함 · 매번 매매일지(진입·손절·익절 이유, 피드백)")]
for k,(h,t) in enumerate(steps):
    a(f'<text x="{L}" y="{yb+k*30}" fill="#fff" font-size="15" font-weight="800">{h}</text><text x="{L+86}" y="{yb+k*30}" fill="#c5c9d2" font-size="14.5">{t}</text>')
svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Noto Sans CJK KR, sans-serif">'+''.join(s)+'</svg>'
open('ob.html','w').write(f'<!doctype html><meta charset="utf-8"><body style="margin:0;background:#121214">{svg}</body>')
