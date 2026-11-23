"""하루 크게 오른 기업 — 나중에도 크게 오를 확률이 높나? (11/23 형) · 한국(시총 300억~10조)·미국 둘 다
사건: 하루 종가 상승률 ≥ 기준(한국 +15%, 미국 +10%)
보는 것:
  ① 다시 크게 오를 확률: 사건 뒤 20일·60일 안에 또 기준 이상 오르는 날이 있나 vs 아무 날이나 고른 경우(기본 확률)
  ② 사건 다음 날 시가에 사서 1·5·20·60일 들고 있으면 (같은 날 전체 종목 평균을 뺀 초과 수익)
  ③ 이동평균선 배열(5·20·60·120일): 정배열(5>20>60>120) / 역배열(5<20<60<120) / 섞임
  ④ 거래량 배수(20일 평균 대비) · 상승 크기 구간
python research/kr2/bigrise.py kr|us"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def load(mk):
    D = {}
    if mk == "us":
        J = json.loads((ROOT / "research/us/data/prices.json").read_text())
        for t, rows in J.items():
            if t.startswith("^"):
                continue
            d = pd.DataFrame(rows, columns=["d", "o", "h", "l", "c", "v"]).set_index("d"); d.index = pd.to_datetime(d.index); D[t] = d
    else:
        for f in (Path(__file__).parent / "data").glob("day_*.json"):
            rows = json.loads(f.read_text())
            if len(rows) < 150:
                continue
            d = pd.DataFrame(rows, columns=["d", "o", "h", "l", "c", "v", "fr"]).set_index("d"); d.index = pd.to_datetime(d.index); D[f.stem[4:]] = d
    return D


def panel(D):
    C = pd.DataFrame({k: d.c for k, d in D.items()}).sort_index()
    O = pd.DataFrame({k: d.o for k, d in D.items()}).reindex(C.index)
    V = pd.DataFrame({k: d.v for k, d in D.items()}).reindex(C.index)
    return O, C, V


def run(mk):
    thr = 0.15 if mk == "kr" else 0.10
    cost = 0.0025 if mk == "kr" else 0.001
    D = load(mk); O, C, V = panel(D)
    O = O.where(O > 0); C = C.where(C > 0)                      # 거래정지일 0 가격 제거
    r = C.pct_change(fill_method=None)
    lim = 0.305 if mk == "kr" else 9
    bad = (r.abs() > lim).astype(float)                          # 한국 하루 ±30% 제한을 넘는 건 액면분할·병합 등 자료 오류로 보고 제외
    ev = (r >= thr) & (r <= lim) & (C.shift(1) > 0)
    # 기본 확률: 아무 날이나 → 다음 20·60일 안에 사건
    fut = {n: ev[::-1].rolling(n, min_periods=1).max()[::-1].shift(-1) for n in (20, 60)}
    m5, m20, m60, m120 = (C.rolling(n).mean() for n in (5, 20, 60, 120))
    align = np.where((m5 > m20) & (m20 > m60) & (m60 > m120), "정배열", np.where((m5 < m20) & (m20 < m60) & (m60 < m120), "역배열", "섞임"))
    align = pd.DataFrame(align, index=C.index, columns=C.columns)
    vr = V / V.rolling(20).mean().shift(1)
    o1 = O.shift(-1)
    fw = {n: (C.shift(-n) / o1 - 1).where(bad[::-1].rolling(n, min_periods=1).max()[::-1].shift(-1) == 0) for n in (1, 5, 20, 60)}
    mkt = {n: fw[n].mean(axis=1) for n in fw}
    rows = []
    ii, jj = np.where(ev.values)
    for i, j in zip(ii, jj):
        if i < 120 or i + 61 >= len(C):
            continue
        t = C.index[i]; c_ = C.columns[j]
        rows.append(dict(t=t, code=c_, r=r.iat[i, j], al=align.iat[i, j], vr=vr.iat[i, j],
                         re20=fut[20].iat[i, j], re60=fut[60].iat[i, j],
                         **{f"f{n}": fw[n].iat[i, j] for n in fw}, **{f"x{n}": fw[n].iat[i, j] - mkt[n].iat[i] for n in fw}))
    E = pd.DataFrame(rows).dropna(subset=["f1", "f60"])
    base20, base60 = np.nanmean(fut[20].values[120:-61]), np.nanmean(fut[60].values[120:-61])
    nm = {"kr": "한국 (시총 300억~10조, 2015~)", "us": "미국 (S&P500+나스닥100 562종목, 2015~)"}[mk]
    print(f"\n===== {nm} · 하루 +{thr:.0%} 이상 사건 {len(E)}번 · 종목 {C.shape[1]}개")
    print(f"① 다시 크게 오를 확률: 사건 뒤 20일 안 {E.re20.mean():.1%} (아무 날 {base20:.1%}) · 60일 안 {E.re60.mean():.1%} (아무 날 {base60:.1%}) → {E.re60.mean() / base60:.1f}배")
    def line(lab, X):
        if len(X) < 20:
            return
        print(f"  {lab:<16} {len(X):>5}번 · 60일 안 재급등 {X.re60.mean():.0%} · 다음 날 시가 매수 → 1일 {X.x1.mean() * 100:+.2f}% · 5일 {X.x5.mean() * 100:+.2f}% · 20일 {X.x20.mean() * 100:+.2f}% "
              f"(중앙 {X.f20.median() * 100:+.1f}%, 오른 비율 {(X.f20 > 0).mean():.0%}) · 60일 {X.x60.mean() * 100:+.2f}%")
    print("② 사건 다음 날 시가 매수 (시장 평균 뺀 초과 수익, 비용 전)")
    line("전체", E)
    h = E.t.min() + (E.t.max() - E.t.min()) / 2
    line("  앞 절반 기간", E[E.t < h]); line("  뒤 절반 기간", E[E.t >= h])
    print("③ 이동평균선 배열 (사건 날 종가 기준)")
    for a in ("정배열", "섞임", "역배열"):
        line(a, E[E.al == a])
    print("④ 거래량 배수 · 상승 크기")
    for lo, hi in ((0, 3), (3, 6), (6, 12), (12, 1e9)):
        line(f"거래량 {lo}~{hi if hi < 1e9 else ''}배", E[(E.vr >= lo) & (E.vr < hi)])
    for lo, hi in ((thr, 0.2), (0.2, 0.29), (0.29, 1)):
        line(f"상승 {lo:.0%}~{hi:.0%}" if hi < 1 else f"상승 {lo:.0%}↑(상한가 근처)", E[(E.r >= lo) & (E.r < hi)])
    E.to_pickle(Path(__file__).parent / f"data/events_{mk}.pkl")
    return E


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "us")
