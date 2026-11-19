"""
장기 투자 리서치 — 숫자 갱신 (매일 us-daily에서 실행)
data/us/longterm/*.json 의 회사마다: 시가총액·20일 평균 거래대금·매출 대비 몸값(PS)·가격 위치를 다시 계산하고
우리가 검증한 공식 판정(200일선·이미 많이 오른 자리·덜 오른 자리·12-1 모멘텀·장기 손익비)을 붙여요.
리서치 문장(사실/추정)은 바꾸지 않아요 — 숫자만.
"""
import json, math, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us/longterm"


def rsi(c, n=14):
    import pandas as pd
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return float((100 - 100 / (1 + up / dn)).iloc[-1])


def metrics(t):
    import yfinance as yf
    tk = yf.Ticker(t)
    h = tk.history(period="2y").dropna(subset=["Close"])
    if len(h) < 60:
        return None
    c = h.Close; px = float(c.iloc[-1])
    ma = lambda k: float(c[-k:].mean()) if len(c) >= k else None
    m50, m200 = ma(50), ma(200)
    e12, e26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean(); macd = e12 - e26; sig = macd.ewm(span=9, adjust=False).mean()
    r = rsi(c)
    mom = float(c.iloc[-22] / c.iloc[-253] - 1) if len(c) >= 253 else None     # 12-1 모멘텀: 1년 전 → 1달 전
    info = {}
    try:
        info = tk.info
    except Exception:
        pass
    adv = float((h.Close * h.Volume)[-20:].mean())
    out = {
        "px": round(px, 2), "cur": info.get("currency") or "USD", "day": h.index[-1].strftime("%Y-%m-%d"),
        "mcap": info.get("marketCap"), "adv": round(adv), "ps": info.get("priceToSalesTrailing12Months"),
        "rev": info.get("totalRevenue"), "rev_g": info.get("revenueGrowth"),
        "ma50": round(m50, 2) if m50 else None, "ma200": round(m200, 2) if m200 else None, "rsi": round(r, 1),
        "hi52": round(float(c[-252:].max()), 2), "lo52": round(float(c[-252:].min()), 2), "mom121": mom,
    }
    d50 = px / m50 - 1 if m50 else None
    # 우리가 검증한 공식 판정
    F = []
    if m200:
        F.append({"k": "trend200", "ok": px > m200, "t": f"200일선 {'위' if px > m200 else '아래'} ({(px / m200 - 1) * 100:+.0f}%)",
                  "why": "S&P500 2000~: 200일선 위에서만 보유하면 최대 낙폭 −57% → −26% (수익은 줄어듦)"})
    if d50 is not None:
        hot = d50 > 0.08 and r > 65
        F.append({"k": "overheat", "ok": not hot, "t": "이미 많이 오른 자리 " + ("— 피하기" if hot else "아님"),
                  "why": "주식 5만 건(2015~2026): 50일선 +8%↑ & RSI 65↑ 자리는 평균 +0.07R로 최하위"})
        calm = (0 <= d50 <= 0.05) and r <= 65 and float(macd.iloc[-1] - sig.iloc[-1]) > 0
        F.append({"k": "calm", "ok": calm, "t": "덜 오른 자리(50일선 0~5% 위·RSI≤65·MACD↑) " + ("맞음" if calm else "아님"),
                  "why": "같은 5만 건: 세 조건을 모두 갖춘 자리 +0.19R vs 나머지 +0.14R, 앞·뒤 기간 모두 같음"})
    if mom is not None:
        F.append({"k": "mom", "ok": mom > 0, "t": f"12-1 모멘텀 {mom * 100:+.0f}%",
                  "why": "2016~2026 순위 검증: 12-1 모멘텀 상위가 20일 뒤 평균 +1.65% (참고용)"})
    out["formulas"] = F
    return out


def run(keys=None):
    import time
    for p in sorted(D.glob("*.json")):
        if p.name == "index.json" or (keys and p.stem not in keys):
            continue
        R = json.loads(p.read_text())
        for c in R.get("companies", []):
            try:
                m = metrics(c["t"])
            except Exception as e:
                print("숫자 실패", c["t"], e); m = None
            if m:
                ev = c.get("ev") or {}
                if ev:
                    G, L, pG = ev["g"] - 1, ev["l"] - 1, ev["pg"] / 100
                    m["ev"] = {"G": G, "L": L, "pG": pG, "value": G * pG + L * (1 - pG), "ratio": G / -L if L < 0 else None,
                               "be": -L / (G - L) if G > L else None, "ideal": G >= 3 and L >= -0.5}
                c["m"] = m
            time.sleep(0.3)
        R["metrics_at"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
        p.write_text(json.dumps(R, ensure_ascii=False, indent=1))
        print("장기 리서치 숫자 갱신:", p.stem, sum(1 for c in R["companies"] if c.get("m")), "/", len(R["companies"]))


if __name__ == "__main__":
    run(sys.argv[1:] or None)
