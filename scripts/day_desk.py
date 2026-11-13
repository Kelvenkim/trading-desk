"""
데이트레이딩 계좌 — 밤마다(장 마감 뒤) 실행
  1) 중계 서버(/day)에서 상태를 받아 data/us/day_desk.json 으로 저장 (사이트·보고서용 기록)
  2) 감시 종목 갱신: 전 종목 일봉 점수(AI 데스크 dscore)에서 추세 좋고 거래대금 큰 30개 + 대형주 → data/us/day_params.json
  3) 스스로 발전: 금요일(또는 7일마다) 신호별·시간대별 성적 → 표본 15건↑인 것만 가중치·기준점 조정 (한 번에 조금씩, 범위 안)
     조정 내용은 params.history 와 대화방(Logger·Analyst)에 남김. Claude가 아침 보고 때 확인
"""
import json, sys, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us"
PF = D / "day_params.json"
CORE = ["SPY", "QQQ", "NVDA", "AMD", "AVGO", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "TSLA"]
DEF = {"v": 1, "risk_pct": 0.005, "max_trades": 5, "max_pos": 3, "cost": 0.0015, "min_score": 0.6,
       "w": {"orb": 0.25, "vwap": 0.20, "rs": 0.20, "rv": 0.20, "mom": 0.15}, "on": {"orb": True, "vwap": True, "rs": True},
       "start_min": 585, "end_min": 900, "flat_min": 950, "halt_spy": -0.02, "rv_min": 1.2, "bias": {}, "history": []}
MIN_N = 15


def fetch_state():
    proxy = json.loads((ROOT / "data/config.json").read_text())["proxy"].rstrip("/")
    req = urllib.request.Request(proxy + "/day", headers={"Origin": "https://kelvenkim.github.io", "User-Agent": "trading-desk"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")
    except Exception as e:
        print("데이 상태 못 받음:", e)
        return None


def stats(trades, key):
    g = {}
    for t in trades:
        ks = t.get("sig") or [] if key == "sig" else [("오전" if t.get("min_in", 600) < 660 else "점심" if t.get("min_in", 600) < 840 else "오후")]
        for k in ks:
            g.setdefault(k, []).append(t)
    out = {}
    for k, v in g.items():
        R = [x.get("R", 0) for x in v]
        out[k] = {"n": len(v), "win": sum(r > 0 for r in R) / len(v), "avgR": sum(R) / len(v), "pl": sum(x["pl"] for x in v) / len(v)}
    return out


def main(force=False):
    P = {**DEF, **(json.loads(PF.read_text()) if PF.exists() else {})}
    S = fetch_state()
    if S and S.get("eq"):
        (D / "day_desk.json").write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    # 감시 종목: AI 데스크 일봉 점수 상위 + 대형주 (거래대금 $1억↑)
    try:
        A = json.loads((D / "ai_paper_state.json").read_text()); ds = A.get("dscore", {})
        # 데이트레이딩엔 '추세 괜찮고(점수 0.6↑) + 하루 거래대금 $3억↑ + 하루 변동이 큰' 종목이 맞음
        cand = [(t, v) for t, v in ds.items() if v[0] >= 0.6 and v[5] >= 300 and v[2]]
        top = [t for t, v in sorted(cand, key=lambda kv: -(kv[1][3] / kv[1][2]) * kv[1][0])][:30]
        P["watch"] = list(dict.fromkeys(CORE + top))[:40]
        P["adv"] = {t: ds[t][5] * 1e6 for t in P["watch"] if t in ds}
    except Exception as e:
        print("감시 종목 갱신 실패:", e)
    # 스스로 발전 (주 1회)
    tr = (S or {}).get("trades", [])
    today = date.today()
    last = P.get("review")
    changes = []
    if force or today.weekday() == 4 or not last or (today - date.fromisoformat(last)).days >= 7:
        P["review"] = today.isoformat()
        sg, tm = stats(tr, "sig"), stats(tr, "time")
        allR = sum(t.get("R", 0) for t in tr) / len(tr) if tr else 0
        for k, x in sg.items():
            if x["n"] < MIN_N or k not in P["w"]:
                continue
            old = P["w"][k]
            if x["avgR"] < -0.1 and x["avgR"] < allR:
                new = max(0.05, round(old - 0.05, 2))
            elif x["avgR"] > 0.15 and x["avgR"] > allR:
                new = min(0.40, round(old + 0.05, 2))
            else:
                continue
            if new != old:
                P["w"][k] = new; changes.append(f"신호 '{k}' 가중치 {old:.2f}→{new:.2f} ({x['n']}건, 평균 {x['avgR']:+.2f}R, 승률 {x['win']:.0%})")
            if x["n"] >= 2 * MIN_N and x["avgR"] < -0.3 and P["on"].get(k):
                P["on"][k] = False; changes.append(f"신호 '{k}' 끔 ({x['n']}건 평균 {x['avgR']:+.2f}R로 계속 손실)")
        if len(tr) >= 2 * MIN_N:
            old = P["min_score"]
            new = min(0.8, round(old + 0.02, 2)) if allR < 0 else max(0.5, round(old - 0.02, 2)) if allR > 0.2 else old
            if new != old:
                P["min_score"] = new; changes.append(f"진입 기준점 {old:.2f}→{new:.2f} (전체 {len(tr)}건 평균 {allR:+.2f}R)")
        late = tm.get("오후")
        if late and late["n"] >= MIN_N and late["avgR"] < -0.2 and P["end_min"] > 780:
            changes.append(f"오후 진입 마감 {P['end_min'] // 60}:{P['end_min'] % 60:02d}→13:00 (오후 {late['n']}건 평균 {late['avgR']:+.2f}R)")
            P["end_min"] = 780
        P["last_stats"] = {"sig": sg, "time": tm, "n": len(tr), "avgR": allR}
        if changes:
            P["v"] = P.get("v", 1) + 1
            P.setdefault("history", []).append({"day": today.isoformat(), "v": P["v"], "changes": changes})
    PF.write_text(json.dumps(P, ensure_ascii=False, indent=1))
    print("데이 설정 v", P.get("v"), "감시", len(P.get("watch", [])), "조정", changes or "없음")
    return changes


if __name__ == "__main__":
    main(force="--force" in sys.argv)
