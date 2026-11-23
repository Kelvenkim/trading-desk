"""개인·외국인·기관 매매에 따라 주가가 어떻게 움직이나 (11/23 형) — 한국 시총 300억~10조, 최근 약 1.5년
자료: 네이버 증권 종목별 투자자 순매수(주식 수, 장 마감 뒤 확정치). 순매수 ÷ 그날 거래량 = 그 투자자가 거래에서 차지한 순매수 비중
  ① 그날 누가 샀나 → 다음 날 시가에 사서 1·5·20일 (같은 날 전체 평균 뺀 초과 수익)
  ② 외국인·기관이 같이 산 날 / 개인만 산 날
  ③ 며칠 연속 순매수
  ④ 하루 +15% 급등 날 누가 샀나 → 그 뒤
  미국은 이런 투자자별 일일 자료가 공개되지 않음 (기관 보유는 분기 13F, 공매도 잔고는 한 달 두 번 뿐)"""
import json
from pathlib import Path
import numpy as np, pandas as pd

H = Path(__file__).parent / "data"
F, I, P, O, C, V = {}, {}, {}, {}, {}, {}
for f in H.glob("trend_*.json"):
    code = f.stem[6:]; rows = json.loads(f.read_text())
    dp = H / f"day_{code}.json"
    if len(rows) < 120 or not dp.exists():
        continue
    t = pd.DataFrame(rows, columns=["d", "ind", "frg", "org", "c", "v"]).drop_duplicates("d").set_index("d"); t.index = pd.to_datetime(t.index)
    d = pd.DataFrame(json.loads(dp.read_text()), columns=["d", "o", "h", "l", "c", "v", "fr"]).set_index("d"); d.index = pd.to_datetime(d.index)
    d = d[d.index >= t.index.min()]
    vv = d.v.replace(0, np.nan)
    F[code] = t.frg.reindex(d.index) / vv; I[code] = t.org.reindex(d.index) / vv; P[code] = t.ind.reindex(d.index) / vv
    O[code], C[code], V[code] = d.o, d.c, d.v
F, I, P, O, C = (pd.DataFrame(x).sort_index() for x in (F, I, P, O, C))
O = O.where(O > 0); C = C.where(C > 0)                          # 거래정지일 0 가격 제거
bad = (C.pct_change(fill_method=None).abs() > 0.305).astype(float)   # 액면분할 등 자료 오류
print(f"종목 {C.shape[1]} · 기간 {C.index.min():%Y-%m-%d} ~ {C.index.max():%Y-%m-%d}")
o1 = O.shift(-1); r = C.pct_change(fill_method=None)
fw = {n: (C.shift(-n) / o1 - 1).where(bad[::-1].rolling(n, min_periods=1).max()[::-1].shift(-1) == 0) for n in (1, 5, 20)}
ex = {n: fw[n].sub(fw[n].mean(axis=1), axis=0) for n in fw}

def show(lab, M):
    M = M & fw[20].notna()
    n = int(M.values.sum())
    if n < 100:
        return
    vals = {k: np.nanmean(ex[k].values[M.values]) * 100 for k in ex}
    win = np.nanmean((fw[5].values[M.values] > 0))
    print(f"  {lab:<34} {n:>7}번 · 다음 날 시가 매수 → 1일 {vals[1]:+.2f}% · 5일 {vals[5]:+.2f}% · 20일 {vals[20]:+.2f}% (시장 대비) · 5일 오른 비율 {win:.0%}")

print("① 그날 순매수 비중 (거래량 대비) 크기별")
for nm, X in (("외국인", F), ("기관", I), ("개인", P)):
    q = X.rank(axis=1, pct=True)
    show(f"{nm} 순매수 상위 10%", q >= 0.9); show(f"{nm} 순매도 상위 10%", q <= 0.1)
print("② 같이 산 날")
show("외국인·기관 둘 다 순매수 (개인 순매도)", (F > 0.05) & (I > 0.05) & (P < 0))
show("개인만 크게 순매수 (외국인·기관 순매도)", (P > 0.1) & (F < 0) & (I < 0))
print("③ 연속 순매수")
for nm, X in (("외국인", F), ("기관", I)):
    b = (X > 0).astype(float)
    for k in (3, 5):
        show(f"{nm} {k}일 연속 순매수", b.rolling(k).sum() >= k)
print("④ 하루 +15% 급등 날 누가 샀나")
big = (r >= 0.15) & (r <= 0.305)
show("급등 전체", big)
show("급등 + 외국인·기관 순매수", big & (F + I > 0.02))
show("급등 + 개인이 주로 삼 (외국인·기관 순매도)", big & (F + I < -0.02))
