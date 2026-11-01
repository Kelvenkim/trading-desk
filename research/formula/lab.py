"""
'1년에 많이 버는 공식' 찾기 — 일봉 20년+ · 워크포워드 검증

자산 (원화 기준, 배당 포함 근사)
  KS200 = 코스피200, KQ = 코스닥, SPX = S&P500(원화), NDX = 나스닥100(원화)
노출 L의 하루 수익 (선물형 레버리지·인버스 ETF 근사, 실제 KODEX 레버리지로 보정함)
  r = L·(가격수익 + 배당/252 − 금리/252) + 원화금리/252 − 보수/252
  보수: |L|≤1이면 0.15%, 그 이상 0.64% (연), 현금(L=0)은 원화금리 − 0.3%
매매 비용: 노출 변화 1당 0.08% (수수료+슬리피지, ETF는 매도세 없음)
신호: t일 종가로 계산 → t+1일 종가에 매매 → t+2일 수익부터 반영 (하루 늦게, 보수적)

공식 후보
  A. 추세 + 레버리지   : 종가 > N일 평균이면 L배, 아니면 현금 또는 인버스
  B. 추세 점수         : (종가>N일선, N일선 상승, 6개월 수익>0) 맞는 개수만큼 비중
  C. 변동성 맞춤       : 추세일 때 목표변동성 ÷ 최근 변동성 만큼 (최대 2배)
  D. 지수 갈아타기     : 매달 말 M개월 수익 1~2등 지수를 L배로, 절대 모멘텀 음수면 현금
  E. 조합             : D + 매일 추세 이탈 시 현금 + 변동성 맞춤 (최대 2배)
검증: 2006~2026 매년, '그 전 해까지의 데이터'로만 공식·설정을 골라 그 해에 적용 (워크포워드)
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "results"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- 데이터
KR_RATE = {1996: 12, 1997: 13, 1998: 7.0, 1999: 4.75, 2000: 5.0, 2001: 4.5, 2002: 4.2, 2003: 3.9, 2004: 3.6, 2005: 3.4,
           2006: 4.2, 2007: 4.8, 2008: 4.8, 2009: 2.0, 2010: 2.2, 2011: 3.1, 2012: 3.0, 2013: 2.6, 2014: 2.4, 2015: 1.6,
           2016: 1.3, 2017: 1.3, 2018: 1.6, 2019: 1.6, 2020: 0.6, 2021: 0.7, 2022: 2.0, 2023: 3.5, 2024: 3.4, 2025: 2.6, 2026: 2.5}
DIV = {"KS200": 1.8, "KQ": 0.5, "SPX": 1.8, "NDX": 0.8}


def load():
    kr = pd.read_csv(D / "kr_index.csv", index_col=0, parse_dates=True)
    us = pd.read_csv(D / "us_index.csv", index_col=0, parse_dates=True)
    ir = pd.read_csv(D / "us_rate.csv", index_col=0, parse_dates=True)["IRX"]
    px = pd.DataFrame({"KS200": kr["KS200"], "KQ": kr["KQ11"]})
    # 미국 지수는 원화로 환산 (환율 없는 날은 직전 값), 한국 거래일 기준으로 맞춤
    usd = us[["^GSPC", "^NDX"]].ffill()
    fx = us["KRW=X"].ffill()
    usk = usd.mul(fx, axis=0).rename(columns={"^GSPC": "SPX", "^NDX": "NDX"})
    px = px.join(usk.reindex(px.index, method="ffill"))
    px = px[px.index >= "1996-07-01"]
    usr = ir.reindex(px.index, method="ffill").fillna(3.0)
    krr = pd.Series([KR_RATE.get(d.year, 2.5) for d in px.index], index=px.index)
    return px, krr / 100, usr / 100


PX, KRR, USR = load()
RET = PX.pct_change()
DATES = PX.index
N = len(DATES)


def asset_ret(a, L):
    """자산 a를 노출 L(배열 가능)로 들고 있을 때의 하루 수익 (비용 제외)."""
    p = RET[a].fillna(0).values
    rate = (USR if a in ("SPX", "NDX") else KRR).values
    kr = KRR.values
    L = np.asarray(L, dtype=float)
    fee = np.where(np.abs(L) > 1, 0.0064, np.where(L == 0, 0.003, 0.0015))
    return L * (p + DIV[a] / 100 / 252 - rate / 252) + kr / 252 - fee / 252


def run_weights(W, cost=0.0008):
    """W: DataFrame(날짜×자산) 목표 노출 (신호 기준 날짜). 하루 늦게 체결해 수익 계산."""
    W = W.reindex(DATES).fillna(0)
    held = W.shift(2).fillna(0)        # t일 신호 → t+1 종가 매매 → t+2 수익
    traded = W.shift(1).fillna(0)
    r = np.zeros(N)
    tot = held.sum(axis=1).values
    for a in W.columns:
        L = held[a].values
        if not np.any(L):
            continue
        p = RET[a].fillna(0).values
        rate = (USR if a in ("SPX", "NDX") else KRR).values
        # 실제 KODEX 레버리지·인버스 기록보다 모형이 불리하게 나오도록 맞춘 연 비용
        fee = np.where(L > 1, 0.0175, np.where(L < 0, 0.0110, 0.0015))
        r += L * (p + DIV[a] / 100 / 252 - rate / 252) - np.where(L != 0, fee, 0) / 252
    # 원화 현금 이자: 레버리지 ETF도 담보로 이자를 받으므로 총 투자원금 기준으로 한 번만 더함
    r += KRR.values / 252 - np.where(tot == 0, 0.003, 0) / 252
    # 여러 자산에 나눠 레버리지를 쓸 때(개별 자산은 1배 이하) 레버리지 부분 보수
    single_lev = (held.abs() > 1).any(axis=1).values
    tot_abs = held.abs().sum(axis=1).values
    r -= np.where(~single_lev, np.maximum(tot_abs - 1, 0) * 0.016, 0) / 252
    turn = traded.diff().abs().sum(axis=1).fillna(0).values
    r -= turn * cost
    return pd.Series(r, index=DATES)


# ---------------------------------------------------------------- 신호 재료
def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


VOL = {n: RET.rolling(n, min_periods=n).std() * np.sqrt(252) for n in (20, 60)}
MOM = {m: PX / PX.shift(21 * m) - 1 for m in (1, 3, 6, 9, 12)}
MONTH_END = pd.Series(DATES.to_period("M"), index=DATES)
IS_ME = (MONTH_END != MONTH_END.shift(-1)).values


def fam_trend(a, n, lon, loff):
    s = PX[a]
    on = (s > sma(s, n)).astype(float)
    on[sma(s, n).isna()] = np.nan
    w = on * lon + (1 - on) * loff
    return pd.DataFrame({a: w.fillna(0)})


def fam_score(a, n, lmax):
    s = PX[a]
    m = sma(s, n)
    votes = (s > m).astype(int) + (m > m.shift(20)).astype(int) + (MOM[6][a] > 0).astype(int)
    w = votes / 3 * lmax
    w[m.isna() | MOM[6][a].isna()] = 0
    return pd.DataFrame({a: w})


def fam_vol(a, n, target, vwin, lmax=2.0):
    s = PX[a]
    on = (s > sma(s, n)).astype(float)
    w = (target / VOL[vwin][a]).clip(0, lmax) * on
    w[sma(s, n).isna() | VOL[vwin][a].isna()] = 0
    return pd.DataFrame({a: w})


def fam_rot(univ, m, k, lev, absf):
    mom = MOM[m][univ] if m != "mix" else (MOM[1][univ] + MOM[3][univ] + MOM[6][univ] + MOM[12][univ]) / 4
    W = pd.DataFrame(0.0, index=DATES, columns=univ)
    cur = np.zeros(len(univ))
    rows = []
    mv = mom.values
    above = (PX[univ] > sma(PX[univ], 200)).values
    for i in range(N):
        if IS_ME[i] and not np.isnan(mv[i]).all():
            sc = np.where(np.isnan(mv[i]), -9, mv[i])
            order = np.argsort(-sc)[:k]
            cur = np.zeros(len(univ))
            for j in order:
                ok = sc[j] > 0 and (above[i, j] if absf == "sma200" else True)
                if ok:
                    cur[j] = lev / k
        rows.append(cur.copy())
    return pd.DataFrame(rows, index=DATES, columns=univ)


def fam_combo(univ, m, n, target, k=1):
    base = fam_rot(univ, m, k, 1.0, "none")
    out = base.copy()
    for a in univ:
        on = (PX[a] > sma(PX[a], n)).astype(float).fillna(0)
        scale = (target / VOL[20][a]).clip(0, 2.0).fillna(0)
        out[a] = (base[a] > 0) * on * scale / k
    return out


ALL4 = ["KS200", "KQ", "SPX", "NDX"]


def base_ret(W):
    """비용 전 대략 수익 (변동성 추정용, 체결 지연 반영)."""
    return (W.shift(2).fillna(0) * RET[W.columns].fillna(0)).sum(axis=1)


def vol_scale(W, target, cap=2.0, win=60):
    rb = base_ret(W)
    v = rb.rolling(win, min_periods=win).std() * np.sqrt(252)
    sc = (target / v).clip(0, cap).fillna(0)
    return W.mul(sc, axis=0)


def monthly(W):
    """월말에만 비중을 바꾸고 그 사이엔 유지."""
    Wm = W.where(pd.Series(IS_ME, index=DATES), np.nan)
    return Wm.ffill().fillna(0)


def fam_gtaa(univ, n, target):
    """Faber(2007): 자산마다 1/k, 월말 종가가 n일선 위일 때만 보유. target이면 전체 변동성 맞춤."""
    on = pd.DataFrame({a: (PX[a] > sma(PX[a], n)) & PX[a].notna() for a in univ}).astype(float)
    W = monthly(on / len(univ))
    return vol_scale(W, target) if target else W


def fam_ivol(univ, target, trend):
    """변동성 균형(60일 변동성 역수 비중), 월말 리밸런싱, 목표 변동성으로 전체 크기 조절."""
    iv = 1 / VOL[60][univ]
    if trend:
        iv = iv * (PX[univ] > sma(PX[univ], 200)).astype(float)
    W = iv.div(iv.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    W = monthly(W)
    return vol_scale(W, target) if target else W


# ---------------------------------------------------------------- 후보 목록
def candidates():
    C = []
    for a in ["KS200", "NDX", "SPX"]:
        for n in [50, 100, 150, 200, 250]:
            for lon in [1.0, 1.5, 2.0]:
                for loff in [0.0, -1.0]:
                    C.append((f"A 추세 {a} {n}일선 ON {lon}배 OFF {'인버스' if loff else '현금'}", "A", lambda a=a, n=n, lon=lon, loff=loff: fam_trend(a, n, lon, loff)))
            for lmax in [1.0, 2.0]:
                C.append((f"B 추세점수 {a} {n}일 최대 {lmax}배", "B", lambda a=a, n=n, lmax=lmax: fam_score(a, n, lmax)))
        for n in [100, 200]:
            for t in [0.15, 0.20, 0.25, 0.30]:
                for vw in [20, 60]:
                    C.append((f"C 변동성맞춤 {a} {n}일선 목표 {int(t*100)}% ({vw}일 변동성)", "C", lambda a=a, n=n, t=t, vw=vw: fam_vol(a, n, t, vw)))
    for univ in [["KS200", "KQ"], ["KS200", "KQ", "SPX", "NDX"]]:
        u = "+".join(univ)
        for m in [3, 6, 12, "mix"]:
            for k in [1, 2]:
                if k > len(univ) - 1 and len(univ) == 2 and k == 2:
                    continue
                for lev in [1.0, 1.5, 2.0]:
                    for absf in ["none", "sma200"]:
                        C.append((f"D 갈아타기 [{u}] {m}개월 상위{k} {lev}배 필터:{absf}", "D", lambda univ=univ, m=m, k=k, lev=lev, absf=absf: fam_rot(univ, m, k, lev, absf)))
        for m in [3, 6, 12, "mix"]:
            for n in [100, 200]:
                for t in [0.15, 0.20, 0.25, 0.30]:
                    C.append((f"E 조합 [{u}] {m}개월 1등 + {n}일선 + 목표변동성 {int(t*100)}%", "E", lambda univ=univ, m=m, n=n, t=t: fam_combo(univ, m, n, t)))
    for univ in [["KS200", "KQ", "SPX", "NDX"], ["KS200", "SPX", "NDX"]]:
        u = "+".join(univ)
        for n in [150, 200]:
            for t in [0, 0.12, 0.15, 0.20]:
                C.append((f"F 자산별 추세필터 [{u}] {n}일선{' 목표변동성 ' + str(int(t*100)) + '%' if t else ''}", "F", lambda univ=univ, n=n, t=t: fam_gtaa(univ, n, t)))
        for t in [0, 0.12, 0.15, 0.20]:
            for tr in [False, True]:
                C.append((f"G 변동성균형 [{u}]{' +200일선' if tr else ''}{' 목표변동성 ' + str(int(t*100)) + '%' if t else ''}", "G", lambda univ=univ, t=t, tr=tr: fam_ivol(univ, t, tr)))
    return C


# ---------------------------------------------------------------- 성과
def metrics(r):
    r = r.dropna()
    if len(r) < 20:
        return {}
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    dd = eq / eq.cummax() - 1
    return {"cagr": eq.iloc[-1] ** (1 / yrs) - 1, "mdd": dd.min(), "sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0,
            "vol": r.std() * np.sqrt(252), "total": eq.iloc[-1] - 1}


def yearly(r):
    return (1 + r).groupby(r.index.year).prod() - 1


if __name__ == "__main__":
    import sys, time
    t0 = time.time()
    C = candidates()
    print("후보", len(C))
    R = {}
    for name, fam, fn in C:
        W = fn()
        R[name] = run_weights(W)
    R = pd.DataFrame(R)
    R.to_pickle(OUT / "cand_returns.pkl")
    json.dump({n: f for n, f, _ in C}, open(OUT / "cand_family.json", "w"), ensure_ascii=False)
    # 기준: 그냥 보유 (1배)
    B = pd.DataFrame({f"보유 {a}": run_weights(pd.DataFrame({a: pd.Series(1.0, index=DATES).where(PX[a].notna(), 0)})) for a in ["KS200", "KQ", "SPX", "NDX"]})
    B["보유 4개 균등"] = run_weights(pd.DataFrame({a: pd.Series(0.25, index=DATES).where(PX[a].notna(), 0) for a in ["KS200", "KQ", "SPX", "NDX"]}))
    B["보유 코스피200 2배"] = run_weights(pd.DataFrame({"KS200": pd.Series(2.0, index=DATES)}))
    B.to_pickle(OUT / "bench_returns.pkl")
    print(f"계산 {time.time() - t0:.0f}s")
