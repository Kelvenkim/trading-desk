"""비트코인 매매법 미션 — 공통 도구
규칙: 신호는 그날 종가까지의 정보만 사용 → 다음 날 수익에 적용 (코인은 24시간이라 종가≈다음 시가)
비용: 포지션 변화량 × COST (한쪽), 숏은 하루 펀딩 FUND
"""
import numpy as np, pandas as pd

COST, FUND = 0.0010, 0.0003   # 한쪽 0.1%(수수료+체결 차이, 보수적), 숏 펀딩 하루 0.03%


def load(sym="BTC-USD"):
    d = pd.read_parquet(f"research/crypto/data/d_{sym}.parquet")
    return d.iloc[:-1]   # 오늘(진행 중) 봉 제외


def sma(x, n): return x.rolling(n).mean()
def ema(x, n): return x.ewm(span=n, adjust=False).mean()


def atr(d, n=14):
    pc = d.Close.shift(1)
    tr = pd.concat([d.High - d.Low, (d.High - pc).abs(), (d.Low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def rsi(c, n=14):
    dlt = c.diff(); up = dlt.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-dlt.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, 1e-12))


def realvol(c, n=20): return np.log(c).diff().rolling(n).std() * np.sqrt(365)


# ---------------- 백테스트 엔진 ----------------
def run_pos(d, pos, cost=COST, fund=FUND):
    """pos: 종가 t에 정한 포지션(−k..k) → t+1 수익. 결과: 일별 수익 시리즈"""
    pos = pos.reindex(d.index).fillna(0).astype(float)
    r = d.Close.pct_change().shift(-1).fillna(0)          # t → t+1
    turn = pos.diff().abs().fillna(pos.abs())
    ret = pos * r - turn * cost - (pos < 0) * (-pos) * fund
    return ret.shift(1).fillna(0)                          # t+1 날짜에 기록


def run_stop(d, sig, stop_atr=None, trail_pct=None, n_atr=20, cost=COST, fund=FUND, size=None):
    """sig: 종가에 정한 목표 방향(−1/0/1). 보유 중 장중 추적 손절(ATR배수 또는 %) → 손절 뒤 같은 방향은 신호가 바뀔 때까지 대기.
    size: 크기 시리즈(변동성 맞춤 등), 없으면 1"""
    o, h, l, c = d.Open.values, d.High.values, d.Low.values, d.Close.values
    A = atr(d, n_atr).values; s_ = sig.reindex(d.index).fillna(0).values
    sz = np.ones(len(c)) if size is None else size.reindex(d.index).fillna(0).values
    ret = np.zeros(len(c)); side = 0; k = 0.0; ext = 0; stop = None; block = 0; prev_sig = 0
    for i in range(1, len(c)):
        # 1) 보유 중 하루 손익 (i-1 종가 → i), 장중 손절
        if side:
            if stop_atr or trail_pct:
                st = stop
                hit = (l[i] <= st) if side > 0 else (h[i] >= st)
                if hit:
                    px = min(o[i], st) if side > 0 else max(o[i], st)
                    ret[i] += k * side * (px / c[i - 1] - 1) - k * cost - (side < 0) * k * fund
                    side = 0; block = sig_side; k = 0
                else:
                    ret[i] += k * side * (c[i] / c[i - 1] - 1) - (side < 0) * k * fund
            else:
                ret[i] += k * side * (c[i] / c[i - 1] - 1) - (side < 0) * k * fund
        # 2) 종가에 신호 처리
        want = int(np.sign(s_[i])); kk = abs(s_[i]) * sz[i]
        if block and want != block: block = 0
        if block == want and want != 0: want_eff = 0
        else: want_eff = want
        if side and want_eff != side:
            ret[i] -= k * cost; side = 0; k = 0
        if want_eff and not side and kk > 0:
            side = want_eff; k = kk; ret[i] -= k * cost; sig_side = side; ext = c[i]
            stop = (c[i] - side * stop_atr * A[i]) if stop_atr else (c[i] * (1 - side * trail_pct) if trail_pct else None)
        elif side and abs(kk - k) / max(k, 1e-9) > 0.25 and size is not None:   # 크기 조정
            ret[i] -= abs(kk - k) * cost; k = kk
        # 3) 추적 손절선 갱신 (종가 기준 최고/최저)
        if side and (stop_atr or trail_pct):
            ext = max(ext, c[i]) if side > 0 else min(ext, c[i])
            ns = (ext - side * stop_atr * A[i]) if stop_atr else ext * (1 - side * trail_pct)
            stop = max(stop, ns) if side > 0 else min(stop, ns)
    return pd.Series(ret, index=d.index)


def stats(ret, label=""):
    ret = ret.dropna()
    eq = (1 + ret).cumprod()
    yrs = len(ret) / 365
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1
    mdd = (eq / eq.cummax() - 1).min()
    sh = ret.mean() / ret.std() * np.sqrt(365) if ret.std() > 0 else 0
    return {"label": label, "total": eq.iloc[-1] - 1, "cagr": cagr, "mdd": mdd, "calmar": cagr / abs(mdd) if mdd < 0 else np.nan,
            "sharpe": sh, "expo": (ret != 0).mean()}


def fmt(s):
    return f"{s['label']:44s} 연 {s['cagr'] * 100:+6.1f}% · 낙폭 {s['mdd'] * 100:5.0f}% · 칼마 {s['calmar']:.2f} · 샤프 {s['sharpe']:.2f} · 누적 {s['total'] * 100:+,.0f}%"
