"""주식 AI 데스크 — 형 규칙 (11/22) 설명 그림. 가상 차트 예시"""
import math, random
random.seed(3)
W, H = 1280, 900
L, R, T = 60, 150, 96
pmin, pmax = 40, 200
ph = 360; vh = 90; rsh = 90
n = 120; pw = W - L - R; bw = pw / n
X = lambda i: L + bw * (i + .5)
Y = lambda p: T + (math.log(pmax) - math.log(p)) / (math.log(pmax) - math.log(pmin)) * ph
# 가격 경로: 하락 → 바닥(0~25) → 2.5배 상승(25~70) → 손잡이 박스(70~88) → 거래량 돌파(89) → 상승(89~108) → RS 꺾임·50일선 이탈 매도(110~)
path = []
p = 70; lvl = 100
for i in range(n):
    if i < 12: p *= 0.975
    elif i < 28: p *= 1 + random.uniform(-0.012, 0.012)
    elif i < 70: p *= 1.022 + random.uniform(-0.01, 0.01); lvl = p
    elif i < 89: p = lvl * (0.95 + 0.03 * math.sin(i / 3)) + random.uniform(-1.5, 1.5)
    elif i < 106: p *= 1.018 + random.uniform(-0.008, 0.01)
    else: p *= 0.985 + random.uniform(-0.006, 0.004)
    path.append(p)
C = []
for i, c in enumerate(path):
    o = path[i - 1] if i else c
    hi = max(o, c) * (1 + random.uniform(0.003, 0.012)); lo = min(o, c) * (1 - random.uniform(0.003, 0.012))
    v = 1.0 + random.uniform(-0.25, 0.25)
    if i == 89: v = 2.4
    if 70 <= i < 89: v *= 0.75
    C.append((o, hi, lo, c, v))
ma = [sum(x[3] for x in C[max(0, i - 19):i + 1]) / len(C[max(0, i - 19):i + 1]) for i in range(n)]   # 그림용 50일선
rs = [min(99, max(5, 30 + i * 0.9 + random.uniform(-3, 3))) if i < 106 else max(5, 95 - (i - 105) * 3) for i in range(n)]
s = []; a = s.append
a(f'<rect width="{W}" height="{H}" fill="#121214"/>')
a(f'<text x="{L}" y="40" fill="#fff" font-size="24" font-weight="800">주식 AI 데스크 — 형 규칙 (11/22)</text>')
a(f'<text x="{L}" y="66" fill="#9097a3" font-size="14">예시 그림(가상 차트) · 신고점 돌파 + 거래량 + 상대강도 + 바닥 대비 2~3배 · 시험: 2015~2026 미국 518종목</text>')
for p in (50, 75, 100, 150, 200):
    a(f'<line x1="{L}" x2="{W-R}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="#fff" stroke-opacity=".05"/><text x="{W-R+8}" y="{Y(p)+4:.1f}" fill="#6b7280" font-size="11">{p}</text>')
# 구간 띠
for i0, i1, col, lab in [(12, 27, "#7c6cf0", "① 바닥 다지기"), (28, 69, "#26a65b", "② 2~3배 상승 (주도주)"), (70, 88, "#9097a3", "③ 쉬어가는 박스"), (89, 105, "#f5b942", "④ 신고점 돌파 → 보유"), (106, 119, "#f0525c", "⑤ 매도")]:
    x0, x1 = X(i0) - bw / 2, X(i1) + bw / 2
    a(f'<rect x="{x0:.1f}" y="{T-26}" width="{x1-x0:.1f}" height="20" rx="4" fill="{col}" opacity=".85"/><text x="{(x0+x1)/2:.1f}" y="{T-11}" fill="#fff" font-size="12" font-weight="700" text-anchor="middle">{lab}</text>')
# 52주 고점 선
hi_box = max(x[1] for x in C[60:89])
a(f'<line x1="{X(60):.1f}" x2="{X(92):.1f}" y1="{Y(hi_box):.1f}" y2="{Y(hi_box):.1f}" stroke="#f5b942" stroke-dasharray="5 4"/><text x="{X(60):.1f}" y="{Y(hi_box)-6:.1f}" fill="#f5b942" font-size="11.5">52주 신고점</text>')
low2 = min(x[2] for x in C[:40])
a(f'<line x1="{X(10):.1f}" x2="{X(40):.1f}" y1="{Y(low2):.1f}" y2="{Y(low2):.1f}" stroke="#7c6cf0" stroke-dasharray="4 3"/><text x="{X(10):.1f}" y="{Y(low2)+16:.1f}" fill="#9a8cff" font-size="11.5">2년 최저가(바닥)</text>')
# 캔들 + 50일선
for i, (o, h, l, c, v) in enumerate(C):
    col = "#ff5f6b" if c >= o else "#4ea3ff"
    a(f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(h):.1f}" y2="{Y(l):.1f}" stroke="{col}"/><rect x="{X(i)-bw*.3:.1f}" y="{Y(max(o,c)):.1f}" width="{bw*.6:.1f}" height="{max(1,abs(Y(o)-Y(c))):.1f}" fill="{col}"/>')
a('<polyline fill="none" stroke="#7aa2ff" stroke-width="1.5" points="' + " ".join(f"{X(i):.1f},{Y(m):.1f}" for i, m in enumerate(ma) if i > 15) + '"/>')
a(f'<text x="{X(116):.1f}" y="{Y(ma[116])+18:.1f}" fill="#7aa2ff" font-size="11.5" text-anchor="end">50일선</text>')
# 매수·매도 화살표
a(f'<text x="{X(90):.1f}" y="{Y(C[90][2])+22:.1f}" fill="#ff5f6b" font-size="20" text-anchor="middle">▲</text><text x="{X(90):.1f}" y="{Y(C[90][2])+40:.1f}" fill="#ff5f6b" font-size="12" font-weight="700" text-anchor="middle">매수</text>')
si = next(i for i in range(106, n) if C[i][3] < ma[i])
a(f'<text x="{X(si):.1f}" y="{Y(C[si][1])-10:.1f}" fill="#4ea3ff" font-size="20" text-anchor="middle">▼</text><text x="{X(si):.1f}" y="{Y(C[si][1])-32:.1f}" fill="#4ea3ff" font-size="12" font-weight="700" text-anchor="middle">매도</text>')
# 거래량 패널
vt = T + ph + 24; vmax = 2.6
a(f'<text x="{L}" y="{vt-6}" fill="#9097a3" font-size="12">거래량 (점선 = 50일 평균 × 1.5)</text>')
for i, x in enumerate(C):
    hgt = x[4] / vmax * vh; col = "#f5b942" if i == 89 else ("#ff5f6b" if x[3] >= x[0] else "#4ea3ff")
    a(f'<rect x="{X(i)-bw*.3:.1f}" y="{vt+vh-hgt:.1f}" width="{bw*.6:.1f}" height="{hgt:.1f}" fill="{col}" opacity="{1 if i == 89 else .45}"/>')
a(f'<line x1="{L}" x2="{W-R}" y1="{vt+vh-1.5/vmax*vh:.1f}" y2="{vt+vh-1.5/vmax*vh:.1f}" stroke="#f5b942" stroke-dasharray="4 3"/>')
# RS 패널
rt = vt + vh + 30
a(f'<text x="{L}" y="{rt-6}" fill="#9097a3" font-size="12">상대강도 RS (0~99, 전체 종목 중 순위)</text>')
ry = lambda v: rt + rsh - v / 99 * rsh
for lv, col in ((80, "#26a65b"), (70, "#f0525c")):
    a(f'<line x1="{L}" x2="{W-R}" y1="{ry(lv):.1f}" y2="{ry(lv):.1f}" stroke="{col}" stroke-dasharray="4 3"/><text x="{W-R+8}" y="{ry(lv)+4:.1f}" fill="{col}" font-size="11">{lv}</text>')
a('<polyline fill="none" stroke="#c792ea" stroke-width="2" points="' + " ".join(f"{X(i):.1f},{ry(v):.1f}" for i, v in enumerate(rs)) + '"/>')
# 주석
def note(x, y, tx, ty, lines, col):
    a(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="{col}" stroke-width="1.3"/><circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{col}"/>')
    w = max(len(t) for t in lines) * 12.2 + 16; hh = len(lines) * 18 + 10
    a(f'<rect x="{tx:.1f}" y="{ty:.1f}" width="{w:.1f}" height="{hh}" rx="6" fill="#1d1d21" stroke="{col}"/>')
    for k, t in enumerate(lines):
        a(f'<text x="{tx+8:.1f}" y="{ty+22+k*18:.1f}" fill="{"#fff" if k == 0 else "#c5c9d2"}" font-size="{13 if k == 0 else 12}" font-weight="{700 if k == 0 else 400}">{t}</text>')
note(X(89), vt + vh - 2.4 / vmax * vh, X(66), vt - 70, ["신고점 돌파일 거래량 ≥ 평균 × 1.5", "아래면 무의미한 돌파 → 안 삼"], "#f5b942")
note(X(55), Y(C[55][3]), X(2), Y(190), ["바닥 대비 2~3배 오른 주도주 가점", "시험: 2~3배 구간 +1.67% (1.5배 미만 +1.14%)"], "#26a65b")
note(X(80), ry(rs[80]), X(30), rt + rsh + 14, ["RS 80 이상만 신규 매수", "RS 95↑ 돌파는 21%가 1년 안 2배"], "#c792ea")
note(X(si), ry(rs[si]), X(si) - 420, rt + rsh + 14, ["RS 70 아래 + 50일선 아래 마감 → 매도"], "#f0525c")
yb = rt + rsh + 80
steps = [("시장 확인", "다우가 고점 근처인데 등락주선(오른 종목 수 − 내린 종목 수 누적)이 밀리면 '불일치' 경고 → 신규 매수 조심"),
         ("기관 보유", "형 기준 1~20%가 좋은 기업 (너무 많이 보유하면 악재 때 한꺼번에 빠짐) — 지금 미국 대형주는 대부분 60~90%라 표시만"),
         ("시험 결과", "거래량 1.5배 + RS 80↑ 돌파: 1,354번 평균 +2.56% (돌파 전체 +1.21%) · 바닥 2~3배까지 더하면 466번 +3.29%")]
for k, (h, t) in enumerate(steps):
    a(f'<text x="{L}" y="{yb+k*28}" fill="#fff" font-size="14.5" font-weight="800">{h}</text><text x="{L+80}" y="{yb+k*28}" fill="#c5c9d2" font-size="13.5">{t}</text>')
svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Noto Sans CJK KR, sans-serif">' + "".join(s) + '</svg>'
open("oneil.html", "w").write(f'<!doctype html><meta charset="utf-8"><body style="margin:0;background:#121214">{svg}</body>')
