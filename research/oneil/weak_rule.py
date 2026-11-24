"""11/24 형 질문 뒤: '약세장 규칙(S&P 200일선 아래면 크기 절반·하루 1개)이 손실을 실제로 줄였나' + '200일선을 다시 넘으면 빨리 다시 투자하는 게 나은가'
desk_bt.py 'A 지금 주식 계좌(근사)'에서 그 부분만 바꿔 10년 비교"""
src = open("desk_bt.py").read().split('if __name__ == "__main__":')[0]
SIZE = '(1 if up_mkt else 0.5)'
NMAX = 'nmax = 2 if spv[i] > spx200[i] else 1'
STOPCHK = '''            if l_ <= p["stop"]:
                x = min(o_, p["stop"]) if i > p["d0"] else p["stop"]; why = "손절" if not p["be"] else "본전"'''
assert SIZE in src and NMAX in src and STOPCHK in src
V = {
 "지금 (약세: 크기 절반·하루 1개)": src,
 "약세 규칙 없음 (항상 크기 그대로·하루 2개)": src.replace(SIZE, "1").replace(NMAX, "nmax = 2"),
 "약세면 새로 안 삼": src.replace(NMAX, 'nmax = 2 if spv[i] > spx200[i] else 0'),
 "지금 + 약세장 +1R 전량 익절 (사이트 규칙)": src.replace(STOPCHK, STOPCHK + '''
            elif (not up_mkt) and h_ >= p["e"] * (1 + p["sp"]):
                x = max(o_, p["e"] * (1 + p["sp"])); why = "약세 +1R"'''),
 "지금 + 200일선 다시 넘으면 10일간 하루 3개·크기 그대로": src.replace(NMAX, '''rec = any(spv[i - k] > spx200[i - k] and spv[i - k - 1] <= spx200[i - k - 1] for k in range(0, 10))
        nmax = (3 if rec else 2) if spv[i] > spx200[i] else 1'''),
}
for nm, s in V.items():
    g = {}; exec(s, g); E, T = g["run"]("A"); g["summary"](nm, E, T)
    import pandas as pd
    sp = g["spv"]; s200 = g["spx200"]; idx = g["C"].index
    weak = pd.Series(sp < s200, index=idx).reindex(E.index).fillna(False)
    r = E.pct_change().fillna(0)
    print(f"    └ S&P 200일선 아래 기간 수익 {((1 + r[weak]).prod() - 1):+.1%} · 위 기간 {((1 + r[~weak]).prod() - 1):+.1%}")
