from strats import *
def s_ens(d, short=False):
    """추세 신호 묶음: 이평20·50·100, EMA20·50, 모멘텀30·60·90, MACD, 돈치안20/10 — 켜진 비율만큼 보유"""
    parts=[s_ma(d,20),s_ma(d,50),s_ma(d,100),s_ema(d,20),s_ema(d,50),s_tsmom(d,30),s_tsmom(d,60),s_tsmom(d,90),s_macd(d),s_donch(d,20,10)]
    v=sum(parts)/len(parts)
    return v*2-1 if short else v
