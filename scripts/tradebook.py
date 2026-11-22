"""
매매 기록지 (11/22 형: 매일 보고서에 그날 매매한 기록·매매일지·피드백까지 넣어서 하루에 일어난 모든 일을 보고서로 보게)
report_pdf.py가 보고서 맨 뒤에 자동으로 붙임 → 보고서를 쓰는 Claude가 빠뜨릴 수 없음
기간: 지난 보고서 이후 ~ 지금 (data/us/reports/tradebook_state.json, 처음엔 24시간·화요일은 주말 포함 72시간)
담는 것: 모든 계좌 성적표 · 계좌별 산 것/판 것(가격·이유·결과 R·피드백) · 진입 안 한 자리와 이유 · 공식 점검이 바꾼 것 · 확실한 자리 데이터
"""
import html, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us"
STATE = D / "reports/tradebook_state.json"
KST = timezone(timedelta(hours=9))
e = lambda x: html.escape(str(x if x is not None else ""))
NM = {"BTC-USD": "비트코인", "ETH-USD": "이더리움", "SOL-USD": "솔라나"}


def j(p):
    try:
        return json.loads((D / p).read_text())
    except Exception:
        return None


def ts(x):
    if not x:
        return None
    try:
        t = pd.Timestamp(str(x).replace(" ", "T"))
        return (t.tz_localize("UTC") if t.tzinfo is None else t).tz_convert("UTC")
    except Exception:
        return None


def kst(t):
    t = ts(t)
    if t is None:
        return "—"
    if t.hour == 0 and t.minute == 0 and t.second == 0:                 # 날짜만 있는 기록
        return t.strftime("%m/%d")
    return t.tz_convert(KST).strftime("%m/%d %H:%M")


def pct(v, d=1):
    return "—" if v is None else f"{v * 100:+.{d}f}%"


def cls(v):
    return "" if v is None else "up" if v > 0 else "down" if v < 0 else ""


def window(now=None, save=False):
    now = now or datetime.now(timezone.utc)
    try:
        last = ts(json.loads(STATE.read_text())["last"])
    except Exception:
        last = None
    if last is None or (now - last.to_pydatetime()) > timedelta(days=5):
        last = pd.Timestamp(now - timedelta(days=3 if now.astimezone(KST).weekday() == 1 else 1))
    if save:
        STATE.parent.mkdir(parents=True, exist_ok=True); STATE.write_text(json.dumps({"last": now.isoformat(timespec="minutes")}))
    return last, pd.Timestamp(now)


def inwin(t, a, b):
    t = ts(t)
    if t is None:
        return False
    if len(str(t.time())) and t.hour == 0 and t.minute == 0 and t.second == 0:      # 날짜만 있는 기록(일봉 계좌) → 날짜로 비교
        return a.normalize() <= t <= b
    return a <= t <= b


# ---- 계좌 목록: (이름, [(칸 이름, 파일)], 종류) ----
ACCTS = [
    ("주식 (스윙)", [("", "ai_paper.json")], "stock"),
    ("데이트레이딩", [("", "day_desk.json")], "day"),
    ("코인 (AMD·오더블록·50일선 3칸)", [("AMD", "coin_amd.json"), ("오더블록", "coin_ob.json"), ("50일선", "crypto_part_coin.json")], "coin"),
    ("코인 10배 (AMD·오더블록·50일선 3칸)", [("AMD", "lev10.json"), ("오더블록", "lev10_ob.json"), ("50일선", "crypto_part_lev.json")], "coin"),
    ("코인 10배 단타 (추세 눌림)", [("", "trend10.json")], "coin"),
    ("코인 오더블록", [("", "ob_paper.json")], "coin"),
    ("코인 AMD", [("", "amd_paper.json")], "coin"),
    ("코인 50일선", [("", "crypto_paper.json")], "coin"),
    ("코인 10배 50일선", [("", "crypto_lev.json")], "coin"),
]
BASE0 = {"crypto_part_coin.json": 3592.50, "crypto_part_lev.json": 3845.05}


def eq_of(S, f):
    if S is None:
        return None
    if f == "day_desk.json":
        return S["eq"][-1][1] if S.get("eq") else None
    return S.get("eq_now", S.get("cash"))


def eq_at(S, t):
    """기간 시작 시점 평가액 (eq 기록에서 가장 가까운 앞 값)"""
    best = None
    for x in (S or {}).get("eq", []):
        tt = ts(x[0])
        if tt is not None and tt <= t:
            best = x[1]
    return best


def events(S, f, tag, a, b):
    """칸 하나의 산 것·판 것·진입 안 한 자리"""
    ev, skips = [], []
    pre = f"[{tag}] " if tag else ""
    for J in (S.get("journal") or []):                                   # AMD·오더블록 일지
        if not isinstance(J, dict) or "in_at" not in J:
            continue
        nm = NM.get(J.get("sym"), J.get("sym"))
        if inwin(J.get("in_at"), a, b):
            ev.append(dict(t=J["in_at"], kind="산 것", sym=nm, side=J.get("side"), px=J.get("fill"),
                           res=f"손절 {J.get('stop')} · 목표 {J.get('target')}", why=pre + " / ".join(J.get("why_in") or []), fb=[]))
        if J.get("exit") is not None and inwin(J.get("out_at"), a, b):
            ev.append(dict(t=J["out_at"], kind="판 것", sym=nm, side=J.get("side"), px=J.get("exit"), R=J.get("R"), usd=J.get("pnl"),
                           why=pre + (J.get("why_out") or ""), fb=J.get("feedback") or []))
    for T in (S.get("trades") or []):                                    # 주식·추세·50일선 기록
        sym = T.get("sym") or ("BTC-USD" if "crypto_lev" in f or "part_lev" in f else "")
        nm = NM.get(sym, sym); side = "숏" if T.get("side", 1) < 0 else "롱"
        if inwin(T.get("in"), a, b) and f != "ai_paper.json":
            ev.append(dict(t=T["in"], kind="산 것", sym=nm, side=side, px=T.get("entry"), why=pre + (T.get("entry_why") or ""), fb=[]))
        if inwin(T.get("out"), a, b):
            ev.append(dict(t=T["out"], kind="판 것", sym=nm, side=side, px=T.get("exit", T.get("px")), R=T.get("R"), pl=T.get("pl", T.get("acct")), usd=T.get("usd"),
                           why=pre + (T.get("why") or "") + (f" · 산 이유: {T['entry_why']}" if T.get("entry_why") and f == "ai_paper.json" else ""), fb=[]))
    pos = S.get("pos")                                                    # 기간 안에 새로 들어간 보유
    if isinstance(pos, dict) and pos and "side" in pos and "since" in pos:  # 10배 50일선 (포지션 하나)
        pos = {"BTC-USD": pos}
    if isinstance(pos, dict):
        for sym, p in pos.items():
            if isinstance(p, dict) and inwin(p.get("at") or p.get("since"), a, b) and not any(x["kind"] == "산 것" and x["sym"] == NM.get(sym, sym) for x in ev):
                ev.append(dict(t=p.get("at") or p.get("since"), kind="산 것 (보유 중)", sym=NM.get(sym, sym), side="숏" if p.get("side", 1) < 0 else "롱",
                               px=p.get("fill", p.get("entry")), res=f"손절 {round(p['stop'], 2) if p.get('stop') else '—'}", why=pre + (p.get("why") or ""), fb=[]))
    elif isinstance(pos, list):
        for p in pos:
            if inwin(p.get("since"), a, b):
                ev.append(dict(t=p["since"], kind="산 것 (보유 중)", sym=p.get("name") or p.get("sym"), side="숏" if p.get("side", 1) < 0 else "롱",
                               px=p.get("entry", p.get("avg")), why=pre + (p.get("why") or ("50일선 " + ("아래 → 숏" if p.get("side", 1) < 0 else "위 → 롱"))), fb=[]))
    for s in (S.get("skips") or []):
        if inwin(s.get("at"), a, b):
            skips.append(dict(t=s["at"], sym=NM.get(s.get("sym"), s.get("sym")), side=s.get("side"), why=pre + (s.get("why") or "")))
    for m in (S.get("chat") or []):                                       # 대화방에서 '진입 안 함·대기 취소'
        if inwin(m.get("at"), a, b) and any(k in m.get("text", "") for k in ("진입 안 함", "대기 취소", "대기 안 함", "취소 —")):
            skips.append(dict(t=m["at"], sym="", side="", why=pre + m["text"]))
    return ev, skips


def build_html(a=None, b=None):
    if a is None:
        a, b = window()
    out = [f"<p class='sm'>기간: {kst(a)} ~ {kst(b)} (한국 시간) · 모든 계좌 · 가상 돈</p>"]
    # 1) 계좌 성적표
    rows = ""
    allev = []
    for name, parts, kind in ACCTS:
        Ss = [(tag, f, j(f)) for tag, f in parts]
        if not any(S for _, _, S in Ss):
            rows += f"<tr><td>{e(name)}</td><td colspan=4 class='muted'>아직 시작 전</td></tr>"; continue
        eq = sum(eq_of(S, f) or 0 for _, f, S in Ss if S)
        e0 = sum((eq_at(S, a) or (eq_of(S, f) or 0)) for _, f, S in Ss if S)
        base = 10000.0
        evs, sks = [], []
        for tag, f, S in Ss:
            if S:
                x, y = events(S, f, tag, a, b); evs += x; sks += y
        evs.sort(key=lambda x: str(ts(x["t"]))); sks.sort(key=lambda x: str(ts(x["t"])))
        allev.append((name, evs, sks))
        done = [x for x in evs if x["kind"] == "판 것"]
        rows += (f"<tr><td>{e(name)}</td><td class='num'>${eq:,.0f}</td><td class='num {cls(eq / base - 1)}'>{pct(eq / base - 1, 2)}</td>"
                 f"<td class='num {cls(eq / e0 - 1 if e0 else None)}'>{pct(eq / e0 - 1 if e0 else None, 2)}</td><td class='num'>산 것 {sum(1 for x in evs if x['kind'] != '판 것')} · 판 것 {len(done)}</td></tr>")
    out.append("<table><tr><th>계좌</th><th class='num'>지금</th><th class='num'>시작 대비</th><th class='num'>이번 기간</th><th class='num'>이번 기간 매매</th></tr>" + rows + "</table>")
    # 2) 계좌별 기록지
    for name, evs, sks in allev:
        if not evs and not sks:
            continue
        h = f"<h3>{e(name)}</h3><table><tr><th>시각</th><th>구분</th><th>종목</th><th class='num'>가격</th><th class='num'>결과</th><th>이유</th></tr>"
        for x in evs:
            res = (f"{x['R']:+.2f}R" if x.get("R") is not None else pct(x.get("pl"))) if x["kind"] == "판 것" else (x.get("res") or "")
            c = cls(x.get("R") if x.get("R") is not None else x.get("pl")) if x["kind"] == "판 것" else ""
            px = x.get("px"); pxs = "—" if px is None else (f"{px:,.2f}" if px < 1000 else f"{px:,.0f}")
            h += (f"<tr class='avoid'><td class='sm'>{kst(x['t'])}</td><td>{e(x['kind'])}</td><td><b>{e(x['sym'])}</b> {e(x.get('side') or '')}</td><td class='num'>{pxs}</td>"
                  f"<td class='num {c}'>{e(res)}{' · $' + format(x['usd'], ',.0f') if x.get('usd') is not None else ''}</td><td class='sm'>{e(x['why'])}"
                  + ("".join(f"<div class='fb'>💬 {e(fb)}</div>" for fb in x.get("fb") or []) if x.get("fb") else "") + "</td></tr>")
        h += "</table>" if evs else "</table><p class='sm'>산 것·판 것 없음</p>"
        if sks:
            h += f"<div class='cap'>진입 안 한 자리 {len(sks)}개</div><ul class='sm'>" + "".join(f"<li>{kst(s['t'])} {e(s['sym'])} {e(s['side'])} — {e(s['why'])}</li>" for s in sks[-15:]) + "</ul>"
        out.append(h)
    if not any(evs or sks for _, evs, sks in allev):
        out.append("<p>이번 기간엔 어느 계좌도 사고판 게 없어요.</p>")
    # 3) 공식 점검이 바꾼 것 + 확실한 자리 데이터
    K = j("coach.json") or {}
    ch = [x for x in K.get("log", []) if inwin(x.get("at"), a, b)]
    out.append("<h3>공식 점검이 바꾼 것</h3>" + ("<ul class='sm'>" + "".join(
        f"<li>{kst(x['at'])} · {e((K.get('rooms', {}).get(x['formula']) or {}).get('name', x['formula']))} · {'뺌' if x['kind'] == 'remove' else '숫자 바꿈' if x['kind'] == 'param' else '추가'}: <b>{e(x['change'])}</b> "
        f"(2년 시험 거래당 {x['R'][0]:+.2f}R → {x['R'][1]:+.2f}R, 수익÷낙폭 {x['ratio'][0]} → {x['ratio'][1]})</li>" for x in ch) + "</ul>" if ch else "<p class='sm'>이번 기간엔 바뀐 것 없음</p>"))
    Ed = j("edge.json") or {}
    if Ed.get("formulas"):
        out.append("<h3>확실한 자리 데이터 (비중 조절·우리만의 그래프용)</h3><ul class='sm'>" + "".join(
            f"<li>{e(v['name'])}: 실제 기록 {v.get('live_n', 0)}번 쌓임 (30번↑부터 비교)"
            + (f" · 확신 점수 시험(뒤 1년): 상위 1/3 {v['test']['grp'].get('상위 1/3', {}).get('R', 0):+.2f}R / 하위 1/3 {v['test']['grp'].get('하위 1/3', {}).get('R', 0):+.2f}R {'✅' if v['test']['ok'] else '✗'}" if v.get("test") else "")
            + "</li>" for v in Ed["formulas"].values()) + "</ul>")
    return "".join(out)


CSS = ".fb { margin-top: 3px; color: #c9ccff; font-size: 8.4px; }"

if __name__ == "__main__":
    a, b = window()
    print(a, b)
    print(build_html(a, b)[:3000])
