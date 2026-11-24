"""11/24 형: 오더블록 청산 방법 시험 — 지금(파동 고점 절반 익절 + 본전 손절) vs 파동 고점 전부 익절 vs 고정 R 익절. 결과: 모두 여전히 마이너스(−0.06~−0.15R), 통과 없음 → 문제는 청산이 아니라 진입"""
import sys; sys.path.insert(0, '/home/claude/trading-desk/scripts')
import coach as CO, formula_rules as FR, pandas as pd
B = {s: CO.bars(s) for s in CO.SYMS}; F = {s: CO.common(d) for s, d in B.items()}
days = (B["BTC-USD"].index[-1] - B["BTC-USD"].index[0]).days
C = FR.load(); filt = C["ob"]["filters"]; P = C["ob"]["params"]
raw0 = {s: CO.add_time(CO.ob(d, F[s], minrr=P.get("minrr", 0.0), exitm=0.0)) for s, d in B.items()}
D0 = CO.apply_filters(raw0, filt); b = pd.concat(D0.values())
print("지금(절반+본전)", len(b), f"{b.r.mean():+.3f}R", f"승률 {(b.r>0).mean():.0%}", CO.acct(b))
for x in (-1.0, 1.0, 1.5, 2.0, 2.5, 3.0):
    raw = {s: CO.add_time(CO.ob(d, F[s], minrr=P.get("minrr", 0.0), exitm=x)) for s, d in B.items()}
    D1 = CO.apply_filters(raw, filt); r = CO.compare(D0, D1, days, 3); bb = pd.concat(D1.values())
    print(x, f"승률 {(bb.r>0).mean():.0%}", CO.line("x", f"exit {x}", r)["text"])
