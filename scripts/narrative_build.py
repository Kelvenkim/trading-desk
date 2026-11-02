"""
장기 테마(내러티브) — 매일 계산(daily) + 과거 검증(backfill)

출력 data/narrative/
  latest.json   오늘 테마 점수·근거·종목
  history.json  테마 지수 전체 기록 (차트·내 판단 채점용)
  snap/날짜.json 그날 테마 점수 (나중에 3·6·12개월 채점)
  live.json     실제 운영 채점
  backfill.json 과거 검증 결과

점수(100): 주가 추세 30 · 확산 20 · 관심(뉴스량) 15 · 정책 뉴스 15 · 증권가 목표가 여력 10 · 실적 10
  모두 16개 테마 안에서 순위로 매김(0~1) → 배점 곱함. 자료가 없는 항목은 중간(0.5)
"""
import json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import narrative_lib as NL
from narrative_def import NARRATIVES, POLICY_WORDS

OUT = ROOT / "data/narrative"
H = (63, 126, 252)          # 3·6·12개월(거래일)
PARTS = {"trend": ("주가 추세", 30), "breadth": ("확산", 20), "buzz": ("관심", 15), "policy": ("정책 뉴스", 15),
         "target": ("목표가 여력", 10), "earn": ("실적", 10)}


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        o = float(o)
        return None if not np.isfinite(o) else round(o, 4)
    if isinstance(o, np.integer):
        return int(o)
    return o


def dump(p, o):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean(o), ensure_ascii=False, separators=(",", ":")))


def rel(idx, ks, n):
    if idx is None or len(idx) <= n:
        return np.nan
    return float(np.log(idx.iloc[-1] / idx.iloc[-1 - n]) - np.log(ks.iloc[-1] / ks.iloc[-1 - n]))


def pct_rank(d):
    """{key: 값} → {key: 0~1 순위}, 값 없으면 0.5"""
    s = pd.Series(d, dtype=float)
    r = s.rank(pct=True)
    return {k: (float(r[k]) if pd.notna(s[k]) else 0.5) for k in d}


def refresh_themes():
    p = OUT / "naver_themes.json"
    try:
        made = json.loads(p.read_text()).get("made", "2000-01-01")
    except Exception:
        made = "2000-01-01"
    if (pd.Timestamp.today() - pd.Timestamp(made)).days >= 7:
        try:
            import narrative_themes
            narrative_themes.main()
        except Exception as e:
            print("테마 목록 갱신 실패(이전 목록 사용):", e)


def daily(C, ks, cols, names, news, cons, earn, O, day, NOW):
    refresh_themes()
    M, P = NL.members(cols)
    ksA = ks.reindex(C.index).ffill()
    last = C.index[-1]
    m60 = C.rolling(60).mean().iloc[-1]
    sig, info = {}, {}
    for n in NARRATIVES:
        k, mem = n["key"], M[n["key"]]
        idx = NL.theme_index(C, mem)
        words = n.get("words", [])
        heads, nnews = [], 0
        for c in mem:
            nw = news.get(c) or {}
            nnews += nw.get("n", 0) or 0
            for it in nw.get("all", []):
                pol = any(w in it["t"] for w in POLICY_WORDS)
                biz = any(w in it["t"] for w in words)
                if pol or biz:
                    heads.append({"t": it["t"], "u": it["u"], "d": it["d"], "o": it.get("o"), "s": it["s"], "code": c, "name": names.get(c, c), "pol": pol})
        seen, uniq = set(), []
        for h in sorted(heads, key=lambda x: x["d"], reverse=True):
            if h["t"] in seen:
                continue
            seen.add(h["t"]); uniq.append(h)
        npol = sum(1 for h in uniq if h["pol"])
        ups = [cons[c]["target"] / C.loc[last, c] - 1 for c in mem if cons.get(c) and cons[c].get("target") and pd.notna(C.loc[last, c])]
        ups = [u for u in ups if -0.6 < u < 2]
        er = [float(earn[c]) for c in mem if earn is not None and c in earn.index and pd.notna(earn[c])]
        above = [bool(C.loc[last, c] > m60[c]) for c in mem if pd.notna(m60.get(c)) and pd.notna(C.loc[last, c])]
        r1, r3, r6, r12 = (rel(idx, ksA, w) for w in (21, 63, 126, 252))
        sig[k] = {"trend": np.nanmean([r3, r6]) if np.isfinite([r3, r6]).any() else np.nan,
                  "breadth": np.mean(above) if above else np.nan,
                  "buzz": nnews / max(1, len(mem)) ** 0.5,      # 종목 수가 많은 테마가 무조건 이기지 않게
                  "policy": npol / max(1, len(mem)) ** 0.5,
                  "target": np.median(ups) if len(ups) >= 2 else np.nan,
                  "earn": np.mean(er) if len(er) >= 2 else np.nan}
        stocks = []
        for c in mem:
            i3 = C[c].iloc[-64] if len(C) > 64 else np.nan
            stocks.append({"code": c, "name": names.get(c, c), "mkt": None, "close": C.loc[last, c],
                           "r3": C.loc[last, c] / i3 - 1 if pd.notna(i3) else None,
                           "ours": float(O.loc[c, "total"]) if c in O.index else None, "grade": O.loc[c, "grade"] if c in O.index else None,
                           "up": (cons[c]["target"] / C.loc[last, c] - 1) if cons.get(c) and cons[c].get("target") else None,
                           "primary": P.get(c) == k})
        info[k] = {"r1": r1, "r3": r3, "r6": r6, "r12": r12, "n": len(mem), "above": (sum(above), len(above)),
                   "news": nnews, "npol": npol, "heads": uniq[:8], "ups": (float(np.median(ups)) if ups else None, len(ups)),
                   "earn": (sum(1 for x in er if x > 0), len(er)), "stocks": stocks, "idx": idx}
    R = {p: pct_rank({k: sig[k][p] for k in sig}) for p in PARTS}
    rows = []
    for n in NARRATIVES:
        k, I = n["key"], info[n["key"]]
        parts = {p: R[p][k] * PARTS[p][1] for p in PARTS}
        total = sum(parts.values())
        st = ("강해지는 중" if I["r1"] > 0 and I["r3"] > 0 else "숨 고르기" if I["r3"] > 0 else
              "바닥에서 반등" if I["r1"] > 0 else "약함") if np.isfinite([I["r1"], I["r3"]]).all() else "자료 부족"
        ev = []
        if np.isfinite(I["r3"]):
            ev.append(f"테마 종목 평균이 코스피200보다 3개월 {I['r3']*100:+.1f}%p, 6개월 {I['r6']*100:+.1f}%p")
        if I["above"][1]:
            ev.append(f"{I['above'][1]}종목 중 {I['above'][0]}개가 60일선 위 (상승 추세)")
        if I["ups"][0] is not None:
            ev.append(f"증권사 목표가가 현재가보다 평균 {I['ups'][0]*100:+.0f}% ({I['ups'][1]}종목)")
        if I["earn"][1]:
            ev.append(f"최근 실적 영업이익·매출이 늘어난 종목 {I['earn'][0]}/{I['earn'][1]}개")
        ev.append(f"최근 3일 관련 기사 {I['news']}건, 그중 정책 관련 {I['npol']}건")
        rows.append({"key": k, "name": n["name"], "story": n["story"], "score": total, "parts": parts, "status": st,
                     "r1": I["r1"], "r3": I["r3"], "r6": I["r6"], "r12": I["r12"], "evidence": ev, "heads": I["heads"],
                     "stocks": I["stocks"], "n": I["n"]})
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    # ---- 지수 기록 이어 붙이기 ----
    hp = OUT / "history.json"
    Hh = json.loads(hp.read_text()) if hp.exists() else {"dates": [], "ks": [], "idx": {}}
    dates = [d.strftime("%Y-%m-%d") for d in C.index]
    lastd = Hh["dates"][-1] if Hh["dates"] else None
    new = [i for i, d in enumerate(dates) if lastd is None or d > lastd]
    if new:
        base_i = new[0] - 1 if lastd else None
        for k in [n["key"] for n in NARRATIVES]:
            s = info[k]["idx"]
            arr = Hh["idx"].setdefault(k, [None] * len(Hh["dates"]))
            prev = arr[-1] if arr and arr[-1] is not None else 100.0
            for i in new:
                if s is None or (base_i is None and i == new[0]):
                    arr.append(prev if s is None else float(s.iloc[i]))
                else:
                    j = i - 1
                    g = float(s.iloc[i] / s.iloc[j]) if s is not None and s.iloc[j] else 1.0
                    prev = (arr[-1] if arr[-1] is not None else 100.0) * g
                    arr.append(prev)
        kprev = Hh["ks"][-1] if Hh["ks"] else None
        for i in new:
            Hh["ks"].append(float(ksA.iloc[i]))
        Hh["dates"] += [dates[i] for i in new]
        dump(hp, Hh)

    # ---- 기록·채점 ----
    dump(OUT / "snap" / f"{day}.json", {"date": day, "score": {r["key"]: r["score"] for r in rows}, "trend": {k: sig[k]["trend"] for k in sig}})
    live = grade(Hh)
    dump(OUT / "live.json", live)
    bf = json.loads((OUT / "backfill.json").read_text()) if (OUT / "backfill.json").exists() else None
    dump(OUT / "latest.json", {"date": day, "made": NOW.strftime("%Y-%m-%d %H:%M"), "parts": {p: {"name": a, "max": b} for p, (a, b) in PARTS.items()},
                               "rows": rows, "live": summarize_live(live),
                               "primary": {c: k for c, k in P.items()}, "backfill": (bf or {}).get("summary")})
    print(f"장기 테마 {len(rows)}개 · 1위 {rows[0]['name']}")


def grade(Hh):
    pos = {d: i for i, d in enumerate(Hh["dates"])}
    out = []
    for p in sorted((OUT / "snap").glob("*.json")):
        S = json.loads(p.read_text())
        i = pos.get(S["date"])
        if i is None:
            continue
        for h in H:
            if i + h >= len(Hh["dates"]):
                continue
            ret = {k: Hh["idx"][k][i + h] / Hh["idx"][k][i] - 1 for k in S["score"] if Hh["idx"].get(k) and Hh["idx"][k][i]}
            ksr = Hh["ks"][i + h] / Hh["ks"][i] - 1
            top = sorted(S["score"], key=lambda k: -S["score"][k])[:3]
            out.append({"date": S["date"], "h": h, "top": top, "top_ret": float(np.mean([ret[k] for k in top if k in ret])),
                        "all_ret": float(np.mean(list(ret.values()))), "ks": ksr})
    return out


def summarize_live(live):
    s = {}
    for h in H:
        R = [r for r in live if r["h"] == h]
        s[str(h)] = {"n": len(R), "ex": float(np.mean([r["top_ret"] - r["all_ret"] for r in R])) if R else None,
                     "beat": float(np.mean([r["top_ret"] > r["all_ret"] for r in R])) if R else None}
    return s


# ---------------- 과거 검증 ----------------
def backfill():
    """현재 테마 구성으로 2014~ 테마 지수 + '주가 추세' 신호만 검증 (뉴스·정책·목표가는 과거 자료 없음)"""
    import rank_lib as L
    J = json.loads((ROOT / "research/rank/data/prices300.json").read_text())
    cal = sorted(J["ks200"].keys())
    C, Hh_, V = L.wide(J["stocks"], cal)
    codes = list(J["stocks"].keys())
    M, P = NL.members(codes)
    ks = pd.Series(J["ks200"]); ks.index = pd.to_datetime(ks.index); ks = ks.reindex(C.index).ffill()
    idx = {n["key"]: NL.theme_index(C, M[n["key"]]) for n in NARRATIVES}
    D = pd.DataFrame(idx)
    hist = {"dates": [d.strftime("%Y-%m-%d") for d in C.index], "ks": ks.round(2).tolist(),
            "idx": {k: D[k].round(3).tolist() for k in D}, "seeded": "과거 구간은 현재 테마 구성으로 거꾸로 계산"}
    dump(OUT / "history.json", hist)
    lr = np.log(D).sub(np.log(ks), axis=0)
    trend = ((lr - lr.shift(63)) + (lr - lr.shift(126))) / 2
    res = []
    for i in range(260, len(C) - 21, 21):
        t = trend.iloc[i].dropna()
        if len(t) < 8:
            continue
        top = t.sort_values(ascending=False).index[:3]
        bot = t.sort_values().index[:3]
        row = {"date": C.index[i].strftime("%Y-%m-%d"), "top": list(top)}
        for h in H:
            if i + h < len(C):
                fr = D.iloc[i + h] / D.iloc[i] - 1
                row[f"top{h}"] = float(fr[top].mean()); row[f"bot{h}"] = float(fr[bot].mean())
                row[f"all{h}"] = float(fr[t.index].mean()); row[f"ks{h}"] = float(ks.iloc[i + h] / ks.iloc[i] - 1)
        res.append(row)
    R = pd.DataFrame(res)
    summ = {"from": R["date"].iloc[0], "to": R["date"].iloc[-1], "n": len(R),
            "note": "지금의 테마 구성·종목으로 과거를 계산해서, 지금 잘나가는 이야기를 미리 알고 고른 효과가 섞여 있어요. '주가 추세' 신호만 검증 가능(뉴스·정책·목표가는 과거 자료 없음)."}
    for h in H:
        g = R.dropna(subset=[f"top{h}"])
        e = g[f"top{h}"] - g[f"all{h}"]
        summ[str(h)] = {"n": len(g), "top_vs_all": float(e.mean()), "beat": float((e > 0).mean()),
                        "bot_vs_all": float((g[f"bot{h}"] - g[f"all{h}"]).mean()), "top_vs_ks": float((g[f"top{h}"] - g[f"ks{h}"]).mean())}
    dump(OUT / "backfill.json", {"summary": summ, "rows": res})
    print(json.dumps(clean(summ), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    backfill()
