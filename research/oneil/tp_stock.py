"""주식에서도 익절선이 없는 게 나을까? (11/22 형 질문) — desk_bt.py 'A 지금 주식 계좌(근사)'에서 익절만 바꿔 비교
지금: 목표 2.5R 익절 · +1R 본전 손절 · 5일째 −0.5R 조기 정리 (사이트 실제 계좌는 +15%부터 고점 −8% 추적도 있음)"""
import re
src = open("desk_bt.py").read().split('if __name__ == "__main__":')[0]
src = src.replace('h_ >= p["e"] * (1 + 2.5 * p["sp"])', 'TP and h_ >= p["e"] * (1 + TP * p["sp"])').replace('max(o_, p["e"] * (1 + 2.5 * p["sp"]))', 'max(o_, p["e"] * (1 + TP * p["sp"]))')
src = src.replace('''            if l_ <= p["stop"]:''', '''            p["hi"] = max(p["hi"], h_)
            if TRAIL and p["hi"] >= p["e"] * 1.15:
                p["stop"] = max(p["stop"], p["hi"] * (1 - TRAIL))
            if l_ <= p["stop"]:''')
g = {}
for nm, tp, tr in [("지금: 2.5R 익절", 2.5, 0), ("2.5R 익절 + 15%부터 추적 8% (사이트 규칙)", 2.5, 0.08), ("익절 없음 · 본전 손절만", 0, 0),
                   ("익절 없음 + 15%부터 추적 8%", 0, 0.08), ("익절 없음 + 15%부터 추적 15%", 0, 0.15), ("4R 익절", 4, 0), ("1.5R 익절", 1.5, 0)]:
    g = {"TP": tp, "TRAIL": tr}; exec(src, g)
    E, T = g["run"]("A"); g["summary"](nm, E, T)
