"""후보 매매법 — 모두 '종가 t까지의 정보'로 목표 포지션을 정함"""
import numpy as np, pandas as pd
from lib import *


def s_ma(d, n, short=False):
    up = d.Close > sma(d.Close, n)
    return pd.Series(np.where(up, 1, -1 if short else 0), d.index).where(sma(d.Close, n).notna(), 0)


def s_ema(d, n, short=False):
    up = d.Close > ema(d.Close, n)
    return pd.Series(np.where(up, 1, -1 if short else 0), d.index)


def s_cross(d, f, s, short=False):
    up = sma(d.Close, f) > sma(d.Close, s)
    return pd.Series(np.where(up, 1, -1 if short else 0), d.index).where(sma(d.Close, s).notna(), 0)


def s_tsmom(d, n, short=False):
    m = d.Close / d.Close.shift(n) - 1
    return pd.Series(np.where(m > 0, 1, -1 if short else 0), d.index).where(m.notna(), 0)


def s_vote(d, Ls=(20, 50, 100, 200), short=False):
    v = sum((d.Close > sma(d.Close, L)).astype(float) for L in Ls) / len(Ls)
    if short:
        v = v * 2 - 1
    return v.where(sma(d.Close, max(Ls)).notna(), 0)


def s_donch(d, ne, nx, short=False):
    hi = d.High.rolling(ne).max().shift(1); lo = d.Low.rolling(nx).min().shift(1)
    hi_s = d.High.rolling(nx).max().shift(1); lo_e = d.Low.rolling(ne).min().shift(1)
    c = d.Close.values; out = np.zeros(len(c)); s = 0
    for i in range(len(c)):
        if np.isnan(hi.iloc[i]): continue
        if s == 1 and c[i] < lo.iloc[i]: s = 0
        if s == -1 and c[i] > hi_s.iloc[i]: s = 0
        if s == 0:
            if c[i] > hi.iloc[i]: s = 1
            elif short and c[i] < lo_e.iloc[i]: s = -1
        out[i] = s
    return pd.Series(out, d.index)


def s_supertrend(d, n=10, m=3.0, short=False):
    A = atr(d, n); mid = (d.High + d.Low) / 2
    ub = (mid + m * A).values; lb = (mid - m * A).values; c = d.Close.values
    fu, fl = ub.copy(), lb.copy(); tr = np.ones(len(c))
    for i in range(1, len(c)):
        fu[i] = ub[i] if (ub[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lb[i] if (lb[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
        tr[i] = 1 if c[i] > fu[i - 1] else (-1 if c[i] < fl[i - 1] else tr[i - 1])
    return pd.Series(np.where(tr > 0, 1, -1 if short else 0), d.index)


def s_macd(d, f=12, s=26, g=9, short=False):
    m = ema(d.Close, f) - ema(d.Close, s); sg = ema(m, g)
    return pd.Series(np.where(m > sg, 1, -1 if short else 0), d.index)


def s_pullback(d, trend=200, rn=2, lo=10, exit_ma=5):
    """상승 추세(200일선 위)에서 단기 과매도(RSI2<10) 때 사서 5일선 위로 오면 팔기"""
    c = d.Close; up = c > sma(c, trend); r = rsi(c, rn); ex = c > sma(c, exit_ma)
    out = np.zeros(len(c)); s = 0
    for i in range(len(c)):
        if s and (ex.iloc[i] or not up.iloc[i]): s = 0
        elif not s and up.iloc[i] and r.iloc[i] < lo: s = 1
        out[i] = s
    return pd.Series(out, d.index)


def s_boll_mr(d, n=20, k=2.0):
    """볼린저 밴드 아래 이탈 시 사서 중간선 회복 시 팔기 (평균 회귀)"""
    c = d.Close; m = sma(c, n); sd = c.rolling(n).std()
    out = np.zeros(len(c)); s = 0
    for i in range(len(c)):
        if np.isnan(m.iloc[i]): continue
        if s and c.iloc[i] > m.iloc[i]: s = 0
        elif not s and c.iloc[i] < m.iloc[i] - k * sd.iloc[i]: s = 1
        out[i] = s
    return pd.Series(out, d.index)


def s_boll_bo(d, n=20, k=2.0, short=False):
    """볼린저 밴드 위 돌파 시 사서 중간선 아래로 오면 팔기 (추세 돌파)"""
    c = d.Close; m = sma(c, n); sd = c.rolling(n).std()
    out = np.zeros(len(c)); s = 0
    for i in range(len(c)):
        if np.isnan(m.iloc[i]): continue
        if s == 1 and c.iloc[i] < m.iloc[i]: s = 0
        if s == -1 and c.iloc[i] > m.iloc[i]: s = 0
        if s == 0:
            if c.iloc[i] > m.iloc[i] + k * sd.iloc[i]: s = 1
            elif short and c.iloc[i] < m.iloc[i] - k * sd.iloc[i]: s = -1
        out[i] = s
    return pd.Series(out, d.index)


def vt_size(d, target=0.6, n=20, cap=1.0):
    """변동성 맞춤 크기: target ÷ 최근 n일 변동성, 최대 cap"""
    return (target / realvol(d.Close, n)).clip(upper=cap).fillna(0)
