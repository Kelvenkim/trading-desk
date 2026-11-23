"""
매매 차트 (11/22 형: "언제 어디서 왜 샀는지 모르니까, 매매하면 우리 공식 그림처럼 '여기서 오더블록이 나와서 매수' 식으로 보여줘")
코인 계좌의 모든 매매마다 1시간봉(50일선은 일봉) 차트 그림을 자동으로 그림:
  오더블록: ① 오더블록 구간 ② 구간 터치 → 진입 ③ 절반 익절 ④ 정리 + 손절선·목표선
  AMD: ① 매집 박스·POC ② 조작(가짜 이탈) ③ POC 진입 ④ 정리 + 손절·목표
  추세 눌림: EMA20·50·200 + 눌림 진입 + 손절(추적) + 정리
  50일선: 일봉 + 50일선 + 진입·정리
결과: data/us/charts/<키>.png + data/us/charts/index.json ("종목|진입 시각" → 그림) → 사이트 매매일지·사고 판 기록, 아침 보고서 매매 기록지에서 씀
ob.yml에서 매시간 (새 매매·끝난 매매가 있을 때만 그림). python scripts/trade_charts.py --need → 그릴 게 있으면 0, 없으면 1로 끝남
"""
import hashlib, json, re, sys
from datetime import timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us"
OUT = D / "charts"
IDX = OUT / "index.json"
KST = timezone(timedelta(hours=9))
NM = {"BTC-USD": "비트코인", "ETH-USD": "이더리움", "SOL-USD": "솔라나"}
C = dict(bg="#0f1013", panel="#18191d", line="#2b2d33", text="#eceef2", muted="#a3a7b1", faint="#6f7480", accent="#7c83ff",
         up="#ff5f6b", down="#4ea3ff", ok="#3ecf8e", warn="#f5b84b", orange="#f0a43a")
SRC = [("ob", "ob_paper.json"), ("ob", "coin_ob.json"), ("ob", "lev10_ob.json"), ("amd", "amd_paper.json"), ("amd", "coin_amd.json"), ("amd", "lev10.json"),
       ("tr", "trend10.json"), ("ma", "crypto_paper.json"), ("ma", "crypto_part_coin.json"), ("ma10", "crypto_lev.json"), ("ma10", "crypto_part_lev.json")]


def j(p):
    try:
        return json.loads((D / p).read_text())
    except Exception:
        return None


def ts(x):
    t = pd.Timestamp(str(x).replace(" ", "T"))
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def key_of(sym, t_in, kind=""):
    return f"{kind}:{sym}|{str(t_in)[:16].replace('T', ' ')}"


def f(x):
    return "—" if x is None else (f"{x:,.2f}" if abs(x) < 1000 else f"{x:,.0f}")


def parse_amd(J):
    """예전 AMD 일지(박스 정보가 문장에만 있음)에서 박스·POC·조작 정보 꺼내기"""
    if J.get("amd"):
        return J["amd"]
    s = " ".join(J.get("why_in") or []); n = lambda x: float(x.replace(",", ""))
    m1 = re.search(r"(\d\d-\d\d \d\d:\d\d)부터 24봉 박스 ([\d,\.]+)~([\d,\.]+).*?POC ([\d,\.]+)", s)
    m2 = re.search(r"를 ([\d,\.]+)까지 깼다가 (\d\d-\d\d \d\d:\d\d) 봉", s)
    if not m1:
        return None
    y = str(J["in_at"])[:4]
    out = dict(box_from=f"{y}-{m1.group(1).replace(' ', 'T')}:00+00:00", blo=n(m1.group(2)), bhi=n(m1.group(3)), poc=n(m1.group(4)))
    if m2:
        out.update(ext=n(m2.group(1)), reclaim_at=f"{y}-{m2.group(2).replace(' ', 'T')}:00+00:00")
    return out


def collect():
    """모든 계좌의 매매 → 그림 할 일 목록 (같은 자리는 하나로)"""
    jobs = {}
    for kind, fn in SRC:
        S = j(fn)
        if not S:
            continue
        for J in S.get("journal") or []:
            if not isinstance(J, dict) or "in_at" not in J:
                continue
            k = key_of(J["sym"], J["in_at"], kind)
            jobs.setdefault(k, dict(kind=kind, sym=J["sym"], side=-1 if J.get("side") == "숏" else 1, t_in=J["in_at"], fill=J.get("fill"), stop=J.get("stop"),
                                    target=J.get("target"), t_out=J.get("out_at"), exit=J.get("exit"), R=J.get("R"), why_out=J.get("why_out"),
                                    partial=J.get("partial") or [], ob=J.get("ob"), amd=parse_amd(J) if kind == "amd" else None, why_list=J.get("why_in") or [],
                                    feat=J.get("feat"), risk_pct=J.get("risk_pct"), accts=[]))["accts"].append(fn)
        for T in S.get("trades") or []:
            sym = T.get("sym") or "BTC-USD"
            if kind == "tr" or (kind.startswith("ma") and T.get("in") and T.get("out")):
                k = key_of(sym, T["in"], kind)
                jobs.setdefault(k, dict(kind=kind, sym=sym, side=T.get("side", 1), t_in=T["in"], fill=T.get("entry"), stop=None, target=None,
                                        t_out=T.get("out"), exit=T.get("exit"), R=T.get("R"), pl=T.get("pl"), why_out=T.get("why"), why_in=T.get("entry_why"), feat=T.get("feat"), accts=[]))["accts"].append(fn)
        pos = S.get("pos")
        if isinstance(pos, dict) and pos and "side" in pos and ("since" in pos or "at" in pos) and kind == "ma10":
            pos = {"BTC-USD": pos}
        items = pos.items() if isinstance(pos, dict) else [(p.get("sym"), p) for p in (pos or [])]
        for sym, p in items:
            if not isinstance(p, dict) or kind in ("ob", "amd"):
                continue
            t_in = p.get("at") if kind == "tr" else p.get("since")
            if not t_in:
                continue
            k = key_of(sym, t_in, kind)
            jobs.setdefault(k, dict(kind=kind, sym=sym, side=p.get("side", 1), t_in=t_in, fill=p.get("entry"), stop=p.get("stop"), target=None, t_out=None, exit=None,
                                    why_in=p.get("why"), feat=p.get("feat"), accts=[]))["accts"].append(fn)
    return jobs


def sig(J):
    return "v2" + hashlib.md5(json.dumps({k: J.get(k) for k in ("t_out", "exit", "stop", "partial")}, sort_keys=True, default=str).encode()).hexdigest()[:8]


def bars(sym, iv):
    import yfinance as yf
    d = yf.Ticker(sym).history(period="180d" if iv == "1h" else "2y", interval=iv).dropna()
    d.index = d.index.tz_convert("UTC"); d.columns = [c.lower() for c in d.columns]
    return d[["open", "high", "low", "close"]]


EDGE = None


def edge_notes(J):
    """진입 순간 특징을 2년 시험 '특징 지도'(data/us/edge.json)와 비교 — 이 자리가 과거에 좋은 칸이었나"""
    global EDGE
    if EDGE is None:
        EDGE = j("edge.json") or {}
    fk = {"ob": "ob", "amd": "amd", "tr": "tr10"}.get(J["kind"]); F = (EDGE.get("formulas") or {}).get(fk) if fk else None
    ft = J.get("feat") or {}
    if not F or not ft:
        return []
    lab = EDGE.get("labels", {}); out = []
    for c in list(F.get("spread", {}))[:3]:
        v = ft.get(c)
        if v is None or c not in F["map"]:
            continue
        for b in F["map"][c]:
            try:
                lo, hi = (float(x) for x in b["b"].split("~"))
            except ValueError:
                if str(b["b"]) == str(v):
                    out.append(f"{lab.get(c, c)} {v} → 2년 시험 같은 칸 평균 {b['R']:+.2f}R ({b['n']}번)")
                break
            if lo <= float(v) <= hi:
                out.append(f"{lab.get(c, c)} {v} → 2년 시험 같은 칸 평균 {b['R']:+.2f}R ({b['n']}번)"); break
    return out


def feedback(J, d):
    """끝난 매매 하나하나 자동 피드백 (11/23 형: 매매 끝나면 하나씩 피드백 → 쌓이면 종합 피드백)"""
    if not J.get("t_out") or J.get("exit") is None or not J.get("fill"):
        return []
    s = J["side"]; e = J["fill"]; t0, t1 = ts(J["t_in"]), ts(J["t_out"])
    risk = abs(e - J["stop"]) if J.get("stop") else (e * 0.07 if J["kind"].startswith("ma") else None)
    held = d[(d.index > t0) & (d.index <= t1)]; after = d[(d.index > t1)].iloc[:24]      # 진입 봉은 빼고 (봉 안에서 진입 전 움직임이 섞임)
    fb = []
    if risk and len(held):
        mfe = ((held.high.max() - e) if s > 0 else (e - held.low.min())) / risk; mae = ((e - held.low.min()) if s > 0 else (held.high.max() - e)) / risk
        fb.append(f"보유 {len(held)}봉 동안 가장 유리했을 때 {mfe:+.1f}R · 가장 불리했을 때 −{max(0, mae):.1f}R")
        R = J.get("R")
        if R is not None and R <= -0.8:
            if mfe >= 1:
                fb.append("1R 넘게 갔다가 손절로 끝남 → '1R에서 본전 손절' 규칙이 있었으면 손실 없이 끝났을 자리 (같은 사례가 쌓이면 시험)")
            if len(after) and J.get("target") and ((after.low.min() <= J["target"]) if s < 0 else (after.high.max() >= J["target"])):
                fb.append("손절 뒤 24봉 안에 목표가까지 감 → 방향은 맞았는데 손절이 좁았던 자리 (쌓이면 손절 폭 시험)")
            elif len(after):
                fb.append("손절 뒤에도 반대로 더 감 → 손절이 맞았던 자리 (진입 근거가 틀림)")
        if R is not None and R > -0.8 and len(after):
            more = ((e - after.low.min()) if s < 0 else (after.high.max() - e)) / risk
            if more >= 2:
                fb.append(f"정리 뒤 24봉 안에 진입가 기준 {more:+.1f}R까지 더 감 → 나머지를 더 길게 가져가는 방법(추적 손절)을 시험할 거리")
    fb += edge_notes(J)
    return fb


def steps(J):
    """그림 아래 글: 왜·어디서 샀는지, 손절·목표 근거, 어떻게 끝났는지"""
    sd = "숏" if J["side"] < 0 else "롱"; k = J["kind"]; L = []
    W = J.get("why_list") or []
    tk = lambda t: ts(t).tz_convert(KST).strftime("%m/%d %H:%M") if t else ""
    if k == "ob":
        ob = J.get("ob") or {}
        lo, hi = sorted([J["fill"], J["stop"]])
        L.append(("①", f"오더블록: {tk(ob.get('t'))} — " + (re.sub(r" \(.*?UTC\)", "", W[0]) if W else "") + (" · " + W[2].split(" — ")[0] if len(W) > 2 else "")))
        L.append(("②", f"진입: 가격이 오더블록 구간 {f(lo)}~{f(hi)}로 되돌아와 {'아래쪽 경계' if J['side'] < 0 else '위쪽 경계'} {f(J['fill'])}에 닿을 때 {sd} ({tk(J['t_in'])})"))
        L.append(("", f"손절 {f(J['stop'])} = 오더블록 꼬리 끝 ({J.get('risk_pct') or ''}%) · 1차 목표 {f(J.get('target'))} = 오더블록 직후 파동 {'저점' if J['side'] < 0 else '고점'}"))
    elif k == "amd":
        A = J.get("amd") or {}
        L.append(("①", f"매집: {tk(A.get('box_from'))}부터 24봉 박스 {f(A.get('blo'))}~{f(A.get('bhi'))} · 거래가 가장 많이 몰린 가격(POC) {f(A.get('poc'))}"))
        if A.get("ext"):
            L.append(("②", f"조작: 박스 {'위' if J['side'] < 0 else '아래'} {f(A['ext'])}까지 가짜로 뚫었다가 {tk(A.get('reclaim_at'))} 봉에 박스 안으로 복귀"))
        L.append(("③", f"진입: POC 쪽으로 되돌아올 때 {sd} {f(J['fill'])} ({tk(J['t_in'])}) — " + (W[2].split(" · ")[0].replace("③ 진입: ", "") if len(W) > 2 else "")))
        L.append(("", f"손절 {f(J['stop'])} = 조작 꼬리 끝 바깥 · 목표 {f(J.get('target'))} = 손익비 2"))
    elif k == "tr":
        L.append(("①", f"진입 {sd} {f(J['fill'])} ({tk(J['t_in'])}): {J.get('why_in') or ''}"))
        L.append(("", f"손절 = 진입가 ± ATR×1.5, 이후 가장 유리한 가격에서 ATR×5 추적 · 익절 없음(큰 추세를 끝까지)"))
    else:
        L.append(("①", f"진입 {sd} {f(J['fill'])} ({tk(J['t_in'])}): 일봉 종가가 50일선 {'아래' if J['side'] < 0 else '위'} → {sd} (반대로 넘으면 정리)"))
    n = len([x for x in L if x[0]])
    for p in J.get("partial") or []:
        n += 1; L.append(("①②③④⑤⑥"[n - 1], f"절반 익절 {f(p['px'])} ({tk(p['at'])}) — {p.get('why', '')} · 나머지는 손절을 본전으로"))
    if J.get("t_out") and J.get("exit") is not None:
        n += 1; res = f"{J['R']:+.2f}R" if J.get("R") is not None else (f"{J['pl'] * 100:+.1f}%" if J.get("pl") is not None else "")
        L.append(("①②③④⑤⑥"[n - 1], f"정리 {f(J['exit'])} ({tk(J['t_out'])}) — {J.get('why_out') or ''} · 결과 {res}"))
    return L


def draw(J, d, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    import textwrap
    for fam in ("Noto Sans CJK KR", "Noto Sans CJK JP", "NanumGothic"):
        if any(fam in x.name for x in fm.fontManager.ttflist):
            plt.rcParams["font.family"] = fam; break
    plt.rcParams["axes.unicode_minus"] = False
    daily = J["kind"].startswith("ma")
    t_in = ts(J["t_in"]); t_out = ts(J["t_out"]) if J.get("t_out") else None
    start = t_in - (timedelta(days=90) if daily else timedelta(hours=30 if J["kind"] == "tr" else 18))
    if J.get("amd") and J["amd"].get("box_from"):
        start = min(start, ts(J["amd"]["box_from"]) - timedelta(hours=6))
    if J.get("ob") and J["ob"].get("t"):
        start = min(start, ts(J["ob"]["t"]) - timedelta(hours=12))
    end = min((t_out or d.index[-1]) + (timedelta(days=10) if daily else timedelta(hours=8)), d.index[-1])
    x = d[(d.index >= start) & (d.index <= end)]
    if len(x) < 5:
        return False
    def xi(t):
        k = x.index.searchsorted(ts(t))
        return min(max(k, 0), len(x) - 1)
    ST = steps(J); FB = J.get("fb") or []
    lines = []
    for no, tx in ST:
        for i, w in enumerate(textwrap.wrap(tx, 74)):
            lines.append(((no + " ") if i == 0 and no else "    ", w, C["text"] if no else C["muted"]))
    if FB:
        lines.append(("", "", C["text"]))
        for i, t_ in enumerate(FB):
            for k_, w in enumerate(textwrap.wrap(t_, 74)):
                lines.append(("피드백 " if i == 0 and k_ == 0 else "        ", ("· " if k_ == 0 else "  ") + w, C["accent"]))
    th = 0.24 * len(lines) + 0.5
    fig = plt.figure(figsize=(10, 4.8 + th), dpi=110); fig.patch.set_facecolor(C["bg"])
    H_ = 4.8 + th
    ax = fig.add_axes([0.07, (th + 0.45) / H_, 0.8, 3.9 / H_])
    ax.set_facecolor(C["panel"])
    for s_ in ax.spines.values():
        s_.set_color(C["line"])
    ax.tick_params(colors=C["faint"], labelsize=8); ax.grid(color=C["line"], lw=.5, alpha=.6)
    o, h, l, c = x.open.values, x.high.values, x.low.values, x.close.values; n = len(x)
    for i in range(n):
        col = C["up"] if c[i] >= o[i] else C["down"]
        ax.vlines(i, l[i], h[i], color=col, lw=.8); ax.add_patch(plt.Rectangle((i - .32, min(o[i], c[i])), .64, max(abs(c[i] - o[i]), (h[i] - l[i]) * .01), color=col))
    if J["kind"] == "tr":
        for nn, colr in ((20, C["warn"]), (50, C["accent"]), (200, C["muted"])):
            ax.plot(range(n), d.close.ewm(span=nn, adjust=False).mean().reindex(x.index).values, color=colr, lw=1.1, label=f"EMA{nn}")
    if daily:
        ax.plot(range(n), d.close.rolling(50).mean().reindex(x.index).values, color=C["warn"], lw=1.4, label="50일선")
    side = J["side"]; i0 = xi(J["t_in"]); rng = (h.max() - l.min()) or 1
    def mark(xx, yy, s_, col, up_):                       # 동그라미 번호만 (설명은 아래 글에)
        ax.annotate(s_, (xx, yy), xytext=(0, 14 if up_ else -16), textcoords="offset points", ha="center", va="center", color=col, fontsize=11, fontweight="bold",
                    bbox=dict(boxstyle="circle,pad=.15", fc=C["bg"], ec=col, lw=1), arrowprops=dict(arrowstyle="-", color=col, lw=.8))
    nums = iter("①②③④⑤⑥")
    if J["kind"] == "ob" and J.get("ob"):
        ib = xi(J["ob"]["t"]); lo, hi = sorted([J["fill"], J["stop"]])
        ax.add_patch(plt.Rectangle((ib - 1.5, lo), max(2, (xi(J["t_out"]) if J.get("t_out") else n - 1) - ib + 2), hi - lo, color=C["accent"], alpha=.28, lw=1.2, ec=C["accent"]))
        mark(ib, hi if side < 0 else lo, next(nums), C["accent"], side < 0)
    if J["kind"] == "amd" and J.get("amd"):
        A = J["amd"]; ib = xi(A["box_from"]); ir = xi(A.get("reclaim_at") or J["t_in"])
        ax.add_patch(plt.Rectangle((ib, A["blo"]), max(1, ir - ib), A["bhi"] - A["blo"], color=C["muted"], alpha=.13, lw=1, ec=C["muted"]))
        ax.hlines(A["poc"], ib, n - 1, color=C["orange"], lw=1, ls="--")
        mark((ib + ir) / 2, A["bhi"] if side > 0 else A["blo"], next(nums), C["muted"], side > 0)
        if A.get("ext"):
            mark(ir, A["ext"], next(nums), C["warn"], side < 0)
    ax.scatter([i0], [J["fill"]], marker="v" if side < 0 else "^", s=90, color="#fff", zorder=5, edgecolor=C["accent"])
    mark(i0, J["fill"], next(nums), "#fff", side > 0)
    for p in J.get("partial") or []:
        ip = xi(p["at"]); ax.scatter([ip], [p["px"]], s=50, color=C["ok"], zorder=5); mark(ip, p["px"], next(nums), C["ok"], side > 0)
    if J.get("t_out") and J.get("exit") is not None:
        io = xi(J["t_out"]); col = C["ok"] if (J.get("R") or J.get("pl") or 0) > 0 else C["up"]
        ax.scatter([io], [J["exit"]], marker="X", s=80, color=col, zorder=5); mark(io, J["exit"], next(nums), col, side < 0)
    right = []                                            # 오른쪽 바깥에 가격 이름표 (차트 위 글자와 안 겹치게)
    if J.get("stop"):
        ax.hlines(J["stop"], i0, n - 1, color=C["up"], lw=1, ls=":"); right.append((J["stop"], f"손절 {f(J['stop'])}", C["up"]))
    if J.get("target"):
        ax.hlines(J["target"], i0, n - 1, color=C["ok"], lw=1, ls=":"); right.append((J["target"], f"목표 {f(J['target'])}", C["ok"]))
    right.append((J["fill"], f"진입 {f(J['fill'])}", "#fff"))
    if J["kind"] == "amd" and J.get("amd"):
        right.append((J["amd"]["poc"], f"POC {f(J['amd']['poc'])}", C["orange"]))
    ylo, yhi = l.min() - rng * .06, h.max() + rng * .1; ax.set_ylim(ylo, yhi); ax.set_xlim(-1, n)
    gap = (yhi - ylo) * .055; placed = []
    for y, t_, col in sorted(right, key=lambda z: z[0]):
        yy = max([y] + [p_ + gap for p_ in placed if abs(p_ - y) < gap])
        placed.append(yy); ax.text(n + .4, yy, t_, color=col, fontsize=8.3, va="center", clip_on=False)
    tk = np.linspace(0, n - 1, 6).astype(int)
    ax.set_xticks(tk); ax.set_xticklabels([x.index[i].tz_convert(KST).strftime("%m/%d" if daily else "%m/%d %H시") for i in tk])
    kindname = {"ob": "오더블록", "amd": "AMD (매집→조작→분산)", "tr": "추세 눌림 (10배 단타)", "ma": "50일선", "ma10": "50일선 (10배)"}[J["kind"]]
    state = "보유 중" if not J.get("t_out") else (f"{J['R']:+.2f}R" if J.get("R") is not None else (f"{J['pl'] * 100:+.1f}%" if J.get("pl") is not None else "끝"))
    fig.text(.07, (H_ - .3) / H_, f"{kindname} · {NM.get(J['sym'], J['sym'])} {'숏' if side < 0 else '롱'} · {t_in.tz_convert(KST):%m/%d %H:%M} 진입 · {state}",
             color=C["text"], fontsize=12, fontweight="bold", va="center")
    if J["kind"] in ("tr", "ma", "ma10"):
        ax.legend(loc="upper left", fontsize=7.5, facecolor=C["bg"], edgecolor=C["line"], labelcolor=C["muted"])
    y = (th + .05) / H_; dy = .24 / H_
    fig.patches.append(plt.Rectangle((.03, .02 / H_), .94, (th + .1) / H_, transform=fig.transFigure, color=C["panel"], zorder=-1))
    for no, w, col in lines:
        y -= dy
        fig.text(.05, y, no, color=C["accent"] if no.startswith("피드백") else "#fff", fontsize=9.2, fontweight="bold", va="center")
        fig.text(.11, y, w, color=col, fontsize=9.2, va="center")
    fig.text(.05, .06 / H_ + 0.004, f"{'1시간봉' if not daily else '일봉'} · 한국 시간 · 빨강 오름 / 파랑 내림 · 번호는 아래 글과 같은 순서", color=C["faint"], fontsize=7.5)
    OUT.mkdir(parents=True, exist_ok=True); fig.savefig(path, facecolor=C["bg"]); plt.close(fig)
    return True


def run(need_only=False):
    jobs = collect()
    try:
        I = json.loads(IDX.read_text())
    except Exception:
        I = {}
    todo = {k: J for k, J in jobs.items() if I.get(k, {}).get("sig") != sig(J) or not (ROOT / I.get(k, {}).get("png", "x")).exists()}
    if need_only:
        print("그릴 매매", len(todo)); sys.exit(0 if todo else 1)
    cache = {}
    for k, J in todo.items():
        iv = "1d" if J["kind"].startswith("ma") else "1h"
        if (J["sym"], iv) not in cache:
            try:
                cache[(J["sym"], iv)] = bars(J["sym"], iv)
            except Exception as e:
                print("시세 실패", J["sym"], e); continue
        name = re.sub(r"[^A-Za-z0-9]", "", J["sym"]) + "_" + ts(J["t_in"]).strftime("%Y%m%d%H%M") + "_" + J["kind"] + ".png"
        p = OUT / name
        try:
            J["fb"] = feedback(J, cache[(J["sym"], iv)])
            if draw(J, cache[(J["sym"], iv)], p):
                I[k] = dict(png=str(p.relative_to(ROOT)), sig=sig(J), kind=J["kind"], accts=sorted(set(J["accts"])), fb=J["fb"], R=J.get("R"), done=bool(J.get("t_out")))
                print("그림:", k, name)
        except Exception as e:
            print("그림 실패", k, e)
    OUT.mkdir(parents=True, exist_ok=True); IDX.write_text(json.dumps(I, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    run("--need" in sys.argv)
