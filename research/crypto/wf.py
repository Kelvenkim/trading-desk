from ens import *
import itertools, pickle
def candidates(d):
    """(이름, 일별수익) — 모든 후보를 한 번에 계산 (신호는 과거만 쓰므로 미리 계산해도 됨)"""
    C={}
    E=s_ens(d); f200=(d.Close>sma(d.Close,200)).astype(float)
    for n in (20,30,50,75,100,150,200): C[f"이평{n}"]=s_ma(d,n)
    for n in (20,50,100): C[f"EMA{n}"]=s_ema(d,n)
    for n in (30,60,90): C[f"모멘텀{n}"]=s_tsmom(d,n)
    C["MACD"]=s_macd(d); C["돈치안20/10"]=s_donch(d,20,10); C["선4개투표"]=s_vote(d)
    for th in (0,0.5,0.6,0.7,0.8,0.9):
        C[f"묶음≥{th}"]=E if th==0 else (E>=th).astype(float)
    base=dict(C)
    for k,v in base.items(): C[k+"+200필터"]=v*f200
    out={}
    for k,v in C.items():
        for tv in (None,0.6,0.8):
            pos=v if tv is None else v*vt_size(d,tv)
            out[k+("" if tv is None else f"+변동성{int(tv*100)}")]=run_pos(d,pos)
    return out
def calmar(r):
    s=stats(r); return s["calmar"] if np.isfinite(s["calmar"]) else -9
if __name__=="__main__":
    import sys
    sym=sys.argv[1] if len(sys.argv)>1 else "BTC-USD"
    d=load(sym); R=candidates(d); pickle.dump(R,open(f"R_{sym}.pkl","wb"))
    print(sym,len(R),"후보")
