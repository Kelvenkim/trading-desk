"""하루 손익 표 (11/28 형: 노션 캘린더에 매일 얼마 벌었는지) — 한국 날짜 기준
미국 주식 계좌(eq 날짜 = 뉴욕 장 날짜) → 그 장이 끝난 한국 날짜(+1일)에 기록, 코인 계좌(UTC 시각) → 한국 날짜 하루 끝(24:00) 값
달러 계좌 10개(각 $10,000 시작, 시작 전엔 $10,000로 봄) + 한국 계좌 2개(원)는 따로
python scripts/daily_pnl.py [시작 YYYY-MM-DD] → data/us/daily_pnl.json"""
import json, sys
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
USD = {"주식": (["data/us/ai_paper.json"], "us"), "AI 에이전트": (["data/us/agent_paper.json"], "us"), "데이트레이딩": (["data/us/day_desk.json"], "us"),
       "코인": (["data/us/coin_amd.json", "data/us/coin_ob.json", "data/us/crypto_part_coin.json"], "coin"),
       "코인 10배": (["data/us/lev10.json", "data/us/lev10_ob.json", "data/us/crypto_part_lev.json"], "coin"),
       "코인 10배 단타": (["data/us/trend10.json"], "coin"), "코인 오더블록": (["data/us/ob_paper.json"], "coin"), "코인 AMD": (["data/us/amd_paper.json"], "coin"),
       "코인 50일선": (["data/us/crypto_paper.json"], "coin"), "코인 10배 50일선": (["data/us/crypto_lev.json"], "coin")}
KRW = {"한국 주식": "data/kr/kr_paper.json", "한국 주식 필터 없음": "data/kr/kr_all.json"}


def kst_day(stamp, kind):
    s = str(stamp)
    if kind == "us":
        return (date.fromisoformat(s[:10]) + timedelta(days=1)).isoformat()
    if len(s) <= 10:
        return s
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(KST).date().isoformat()


def series(files, kind, base):
    tot = {}
    for f in files:
        try:
            eq = json.loads((ROOT / f).read_text()).get("eq") or []
        except Exception:
            continue
        last = {}
        for d, v in eq:
            last[kst_day(d, kind)] = v                    # 같은 날 여러 값이면 마지막(하루 끝) 값
        tot[f] = last
    return tot


def main(start="2026-11-23"):
    today = datetime.now(KST).date()
    days = [(date.fromisoformat(start) + timedelta(days=i)).isoformat() for i in range((today - date.fromisoformat(start)).days + 1)]
    prev_day = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    rows = []
    acc_val = {}
    for name, (files, kind) in USD.items():
        S = series(files, kind, 10000)
        vals = {}
        for f, last in S.items():
            base = 10000.0 / len(files)
            ks = sorted(last)
            v = None
            for d in [prev_day] + days:
                cand = [k for k in ks if k <= d]
                v = last[cand[-1]] if cand else base
                vals.setdefault(d, 0.0); vals[d] += v
        acc_val[name] = vals
    kr = {}
    for name, f in KRW.items():
        try:
            S = json.loads((ROOT / f).read_text())
            last = {str(d)[:10]: v for d, v in S.get("eq") or []}
            ks = sorted(last)
            kr[name] = {d: (last[[k for k in ks if k <= d][-1]] if [k for k in ks if k <= d] else 10_000_000.0) for d in [prev_day] + days}
        except Exception:
            pass
    for i, d in enumerate(days):
        p = prev_day if i == 0 else days[i - 1]
        per = {n: round(acc_val[n][d] - acc_val[n][p], 2) for n in acc_val}
        total = sum(acc_val[n][d] for n in acc_val)
        rows.append({"date": d, "pnl": round(sum(per.values()), 2), "total": round(total, 2), "ret_total": round(total / (10000 * len(acc_val)) - 1, 5),
                     "per": per, "best": max(per, key=per.get), "worst": min(per, key=per.get),
                     "kr_pnl": round(sum(kr[n][d] - kr[n][p] for n in kr)) if kr else None,
                     "us_open": (date.fromisoformat(d) - timedelta(days=1)).weekday() < 5})
    out = {"made": datetime.now(KST).isoformat(timespec="minutes"), "accounts": list(acc_val), "start_total": 10000 * len(acc_val), "rows": rows}
    (ROOT / "data/us/daily_pnl.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for r in rows:
        print(r["date"], f"{r['pnl']:+.2f}", f"{r['ret_total']:+.2%}", r["best"], r["worst"], r["kr_pnl"])


if __name__ == "__main__":
    main(*(sys.argv[1:2] or []))
