from wf import *
import pickle, sys
sym=sys.argv[1] if len(sys.argv)>1 else "BTC-USD"
R=pickle.load(open(f"R_{sym}.pkl","rb")); d=load(sym)
first=d.index[0]+pd.Timedelta(days=365*3)     # 처음 3년은 고르기만
years=range(max(2018,first.year+1),2027)
def pick(train_end, crit, family=None, lookback=None):
    best,bv=None,-9e9
    for k,r in R.items():
        if family and not family(k): continue
        rr=r[(r.index<train_end)]
        if lookback: rr=rr[rr.index>=train_end-pd.Timedelta(days=365*lookback)]
        rr=rr[rr.index>=d.index[0]+pd.Timedelta(days=250)]
        s=stats(rr); v={"calmar":s["calmar"],"sharpe":s["sharpe"],"cagr":s["cagr"]}[crit]
        if np.isfinite(v) and v>bv: bv,best=v,k
    return best
def wf(crit="calmar", family=None, lookback=None, verbose=False):
    parts=[];picks=[]
    for y in years:
        t0=pd.Timestamp(f"{y}-01-01"); t1=pd.Timestamp(f"{y+1}-01-01")
        k=pick(t0,crit,family,lookback); picks.append((y,k))
        parts.append(R[k][(R[k].index>=t0)&(R[k].index<t1)])
    oos=pd.concat(parts)
    return oos,picks
bh=run_pos(d,pd.Series(1,d.index),cost=0); t0=pd.Timestamp(f"{years[0]}-01-01")
print(f"[{sym}] 처음 보는 기간(OOS) {years[0]}~2026")
print(fmt(stats(bh[bh.index>=t0],"그냥 보유")))
fams={"모든 후보":None,"묶음 계열만":lambda k:k.startswith("묶음"),"이평 단일만":lambda k:k.startswith("이평") and "+" not in k,
      "200필터 붙은 것만":lambda k:"200필터" in k,"변동성 맞춤 붙은 것만":lambda k:"변동성" in k}
for crit in ("calmar","sharpe"):
    for fn,ff in fams.items():
        oos,picks=wf(crit,ff)
        s=stats(oos,f"{crit}로 고름 · {fn}"); print(fmt(s))
        if fn in("모든 후보",) : print("   해마다 고른 것:", ", ".join(f"{y}:{k}" for y,k in picks))
# 고정 규칙 (미리 정한 것, 고르지 않음)
for k in ["이평50","묶음≥0","묶음≥0.7","묶음≥0+200필터","묶음≥0+200필터+변동성60","묶음≥0.7+200필터","이평50+200필터","선4개투표","선4개투표+200필터+변동성60"]:
    r=R[k]; print(fmt(stats(r[r.index>=t0],"고정: "+k)))
