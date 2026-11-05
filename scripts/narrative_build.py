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


def daily(C, ks, cols, names, news, cons, earn, O, day, NOW, fetch_prices=None):
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
    # ---- 테마별 추천 종목 (소형주 포함) + 시장 여론 ----
    macro = []
    try:
        macro, picks_all = make_picks(rows, C, ksA, names, news, earn, O, day, fetch_prices)
    except Exception:
        import traceback; traceback.print_exc(); picks_all = {}
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
    dump(OUT / "snap" / f"{day}.json", {"date": day, "score": {r["key"]: r["score"] for r in rows}, "trend": {k: sig[k]["trend"] for k in sig},
                                        "picks": picks_all})
    live = grade(Hh)
    dump(OUT / "live.json", live)
    bf = json.loads((OUT / "backfill.json").read_text()) if (OUT / "backfill.json").exists() else None
    dump(OUT / "latest.json", {"date": day, "made": NOW.strftime("%Y-%m-%d %H:%M"), "parts": {p: {"name": a, "max": b} for p, (a, b) in PARTS.items()},
                               "rows": rows, "live": summarize_live(live),
                               "primary": {c: k for c, k in P.items()}, "macro": macro, "pick_record": pick_record_both(), "market_up": bool(ksA.iloc[-1] > ksA.rolling(200).mean().iloc[-1]), "backfill": (bf or {}).get("summary")})
    print(f"장기 테마 {len(rows)}개 · 1위 {rows[0]['name']}")


# ---------------- 추천 종목 ----------------
def make_picks(rows, C, ksA, names, news, earn, O, day, fetch_prices, per_theme=5, min_mv=1000, min_val=2e9):
    import plan_lib as PLN
    import sentiment as SE
    from narrative_def import PM, PM_MACRO, EN_NAME
    from concurrent.futures import ThreadPoolExecutor
    T = json.loads((OUT / "naver_themes.json").read_text())["themes"]
    mkt_up = bool(ksA.iloc[-1] > ksA.rolling(200).mean().iloc[-1])
    nmap = {n["key"]: n for n in NARRATIVES}
    cand, tnames, mvs = {}, {}, {}
    for r in rows:
        n = nmap[r["key"]]
        cnt = {}
        for t in T:
            if any(k in t["name"] for k in n["themes"]):
                for x in t["stocks"]:
                    c, nm, mv = x[0], x[1], (x[2] if len(x) > 2 else 0)
                    if mv < min_mv or nm.endswith(("우", "우B")) or "스팩" in nm:
                        continue
                    cnt[c] = cnt.get(c, 0) + 1; names.setdefault(c, nm); mvs[c] = mv
                    tnames.setdefault((r["key"], c), []).append(t["name"])
        excl = set(__import__("narrative_def").EXCLUDE.get(r["key"], []))
        cand[r["key"]] = [c for c in sorted(cnt, key=lambda c: (-cnt[c], -mvs[c])) if c not in excl][:30]
    # 지난 추천 종목도 계속 채점하려면 가격이 필요
    old = set()
    for p in sorted((OUT / "snap").glob("*.json"))[-130:]:
        for v in (json.loads(p.read_text()).get("picks") or {}).values():
            old |= {x["code"] for x in v}
    allc = sorted({c for v in cand.values() for c in v} | old)
    start = (C.index[-1] - pd.Timedelta(days=420)).strftime("%Y-%m-%d")
    bars = {c: v for c, v in (fetch_prices(allc, start) if fetch_prices else {}).items() if v}
    print(f"추천 후보 {len(allc)}종목 시세 {len(bars)}", flush=True)
    # 지난 추천 채점용 가격 (최근 160일)
    dump(OUT / "pick_prices.json", {c: bars[c][-160:] for c in old if c in bars})
    with ThreadPoolExecutor(8) as ex:
        det = dict(zip(list(bars), ex.map(SE.naver_detail, list(bars))))
    ks = ksA
    picks_all, out_rows = {}, {}
    for r in rows:
        k, scored = r["key"], []
        for c in cand[k]:
            b = bars.get(c)
            if not b or len(b) < 130:
                continue
            b = b[-130:]
            val = np.mean([x[4] * x[5] for x in b[-20:]])
            if val < min_val:          # 하루 거래대금 20억 미만 제외
                continue
            pl = PLN.analyze(b, mkt_up)
            if not pl:
                continue
            px = b[-1][4]; p63 = b[-64][4]
            d0 = pd.Timestamp(b[-64][0])
            k0 = ks.asof(d0) if hasattr(ks, "asof") else np.nan
            rs3 = (px / p63) / (ks.iloc[-1] / k0) - 1 if k0 and np.isfinite(k0) else np.nan
            d = det.get(c) or {}
            up = d["target"] / px - 1 if d.get("target") else None
            recent = [x for x in d.get("reports", []) if x.get("date") and x["date"] >= (pd.Timestamp(day) - pd.Timedelta(days=45)).strftime("%Y%m%d")]
            scored.append({"code": c, "name": names.get(c, c), "mv": mvs.get(c), "px": px, "rs3": rs3, "plan": pl, "det": d, "up": up,
                           "nrep": len(recent), "purity": len(tnames.get((k, c), [])), "val": val, "themes": tnames.get((k, c), [])[:4]})
        if not scored:
            out_rows[k] = []; continue
        rs_rank = pd.Series({x["code"]: x["rs3"] for x in scored}).rank(pct=True)
        up_rank = pd.Series({x["code"]: (x["up"] if x["up"] is not None else np.nan) for x in scored}).rank(pct=True)
        pu_rank = pd.Series({x["code"]: x["purity"] for x in scored}).rank(pct=True)
        for x in scored:
            pl, d = x["plan"], x["det"]
            sc = 0.0
            sc += (30 if pl["kind"] == "pullback" else 12) if pl["ok"] else 0
            sc += 8 if pl["ok"] and pl["in_zone"] else 0
            sc += 20 * (rs_rank.get(x["code"]) if pd.notna(rs_rank.get(x["code"])) else 0.5)
            sc += 12 * (up_rank.get(x["code"]) if pd.notna(up_rank.get(x["code"])) else 0.4)
            sc += 3 if (d.get("opinion") or 0) >= 4 else 0
            sc += min(10, 3 * x["nrep"])
            sc += 10 * (pu_rank.get(x["code"]) if pd.notna(pu_rank.get(x["code"])) else 0.5)
            f = (d.get("foreign5") or 0) + (d.get("organ5") or 0)
            sc += 7 if f > 0 and (d.get("foreign5") or 0) > 0 and (d.get("organ5") or 0) > 0 else 4 if f > 0 else 0
            x["score"] = sc
        top = sorted(scored, key=lambda x: -x["score"])[:per_theme]
        out_rows[k] = top
        picks_all[k] = [{"code": x["code"], "entry": x["plan"]["entry"], "stop": x["plan"]["stop"], "target": x["plan"]["target"],
                         "kind": x["plan"]["kind"], "ok": x["plan"]["ok"], "score": x["score"]} for x in top]
    # 고른 종목만 커뮤니티·해외 애널리스트·예측시장 (요청 수 줄이기)
    sel = {x["code"]: x for v in out_rows.values() for x in v}
    with ThreadPoolExecutor(6) as ex:
        com = dict(zip(sel, ex.map(SE.community, list(sel))))
    try:
        symmap = {x[0].split(".")[0]: x[0] for x in json.loads((ROOT / "data/symbols.json").read_text())["list"]}
    except Exception:
        symmap = {}
    yh = {}
    for c in sel:
        yh[c] = SE.yahoo(symmap.get(c, c + ".KS")); time.sleep(0.4)
    mkt = {c: ("KOSDAQ" if symmap.get(c, "").endswith(".KQ") else "KOSPI") for c in sel}
    pm_cache = {}
    def pm(q, must, minv=20000):
        if q not in pm_cache:
            pm_cache[q] = SE.polymarket(q, minv, 6)
        return [e for e in pm_cache[q] if any(m in (e["title"] or "") for m in must)]
    for r in rows:
        ev, seen = [], set()
        for q, must in PM.get(r["key"], []):
            for e in pm(q, must):
                if e["title"] not in seen:
                    seen.add(e["title"]); ev.append(e)
        r["markets"] = sorted(ev, key=lambda e: -e["vol"])[:3]
        r["picks"] = []
        for x in out_rows.get(r["key"], []):
            pl, d, cm, y = x["plan"], x["det"], com.get(x["code"]), yh.get(x["code"])
            nm = x["name"]
            co_pm = []
            for ko, en in EN_NAME:
                if nm.startswith(ko):
                    co_pm = pm(en.strip(), [en.strip()], 5000)[:2]; break
            why = []
            why.append(f"테마 연관: 네이버 테마 {x['purity']}개 ({', '.join(t.split('(')[0] for t in x['themes'][:3])})")
            if np.isfinite(x["rs3"]):
                why.append(f"주가: 최근 3개월 코스피200 대비 {x['rs3']*100:+.1f}%p, " + ("상승 추세(종가>60일선, 20일선>60일선)" if pl["trend_ok"] else "아직 추세 전환 전"))
            if x["up"] is not None:
                old_c = d.get("cdate") and (pd.Timestamp(day) - pd.Timestamp(d["cdate"])).days > 90
                why.append(f"증권가: 목표가 평균 {d['target']:,.0f}원 (현재가 대비 {x['up']*100:+.0f}%), 투자의견 {d.get('opinion') or '—'}/5"
                           + (f" — {d['cdate']} 기준이라 오래됐을 수 있어요" if old_c else ""))
            if d.get("reports"):
                rp = d["reports"][0]
                why.append(f"최근 리포트: {rp['broker']} {rp['date'][4:6]}/{rp['date'][6:]} \"{rp['title']}\"" + (f" 외 {x['nrep']-1}건(45일)" if x["nrep"] > 1 else ""))
            if d.get("flow_days"):
                why.append(f"수급(최근 5일): 외국인 {d['foreign5']/1e8:+,.0f}억 · 기관 {d['organ5']/1e8:+,.0f}억")
            if x["mv"] and x["mv"] < 5000:
                why.append(f"주의: 시총 {x['mv']:,}억 소형주 — 하루 변동이 크고 손절이 밀릴 수 있어요")
            r["picks"].append({"code": x["code"], "sym": symmap.get(x["code"], x["code"] + ".KS"), "name": nm, "mv": x["mv"], "px": x["px"], "score": x["score"], "plan": pl, "why": why,
                               "reports": d.get("reports", [])[:3], "consensus": {"target": d.get("target"), "opinion": d.get("opinion"), "up": x["up"], "date": d.get("cdate")},
                               "flows": {"foreign5": d.get("foreign5"), "organ5": d.get("organ5"), "fhold": d.get("fhold")},
                               "yahoo": y, "community": cm, "markets": co_pm, "val": x["val"]})
    macro = []
    try:
        macro = SE.kalshi_macro()
        for q, must in PM_MACRO:
            macro += pm(q, must, 100000)[:1]
    except Exception:
        pass
    return macro, picks_all


def pick_record_both():
    try:
        Hh = json.loads((OUT / "history.json").read_text())
        ks = pd.Series(Hh["ks"], index=Hh["dates"], dtype=float)
        up = (ks > ks.rolling(200).mean()).to_dict()
    except Exception:
        up = {}
    a = pick_record(lambda d: up.get(d, True))
    b = pick_record(None)
    if a is None:
        return None
    a["nofilter"] = {k: b[k] for k in ("n", "done", "win", "avg", "open", "open_avg")} if b else None
    return a


def pick_record(mkt_ok=None):
    """지난 추천을 실제 주문처럼 채점
       매수 구간(눌림): 5거래일 안에 그 가격까지 내려오면 체결(지정가) / 돌파 매수: 5거래일 안에 그 가격을 넘으면 체결
       체결 뒤 손절·목표 중 먼저 닿은 것(같은 날 둘 다면 손절), 최대 60거래일. 같은 종목은 앞의 거래가 끝나기 전 새 추천을 세지 않음"""
    pr = OUT / "pick_prices.json"
    if not pr.exists():
        return None
    PX = json.loads(pr.read_text())
    sig = []
    for p in sorted((OUT / "snap").glob("*.json")):
        S = json.loads(p.read_text())
        for k, v in (S.get("picks") or {}).items():
            for x in v:
                if x.get("ok"):
                    sig.append((S["date"], k, x))
    busy, res, seen = {}, [], set()
    for date, k, x in sorted(sig, key=lambda z: z[0]):
        c = x["code"]
        if mkt_ok is not None and not mkt_ok(date):      # 검증된 규칙: 코스피200이 200일선 위일 때만 매수
            continue
        if (date, c) in seen or (busy.get(c) and busy[c] >= date):
            continue
        seen.add((date, c))
        b = [r for r in PX.get(c, []) if r[0] > date]
        if not b:
            continue
        fill = None
        for j, r in enumerate(b[:5]):
            o, h, l = r[1], r[2], r[3]
            if x["kind"] == "pullback" and l <= x["entry"]:
                if o <= x["stop"]:
                    break
                fill = (j, min(o, x["entry"])); break
            if x["kind"] == "breakout" and h >= x["entry"]:
                if o >= x["target"]:
                    break
                fill = (j, max(o, x["entry"])); break
        if not fill:
            if len(b) >= 5:
                res.append({"date": date, "theme": k, "code": c, "kind": x["kind"], "res": "미체결", "ret": None})
            continue
        j0, e = fill
        out, ex_date = None, None
        for r in b[j0:j0 + 60]:
            if r[3] <= x["stop"]: out = ("손절", min(r[1], x["stop"]) / e - 1 if r[0] != b[j0][0] else x["stop"] / e - 1); ex_date = r[0]; break
            if r[2] >= x["target"]: out = ("목표", x["target"] / e - 1); ex_date = r[0]; break
        last = b[min(len(b), j0 + 60) - 1]
        res.append({"date": date, "theme": k, "code": c, "kind": x["kind"], "res": out[0] if out else "보유 중",
                    "ret": out[1] if out else last[4] / e - 1})
        busy[c] = ex_date or "9999"
    done = [r for r in res if r["res"] in ("손절", "목표")]
    op = [r["ret"] for r in res if r["res"] == "보유 중"]
    return {"n": len([r for r in res if r["res"] != "미체결"]), "nofill": sum(r["res"] == "미체결" for r in res), "done": len(done),
            "win": sum(r["res"] == "목표" for r in done), "avg": float(np.mean([r["ret"] for r in done])) if done else None,
            "open": len(op), "open_avg": float(np.mean(op)) if op else None, "recent": res[-30:]}


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
