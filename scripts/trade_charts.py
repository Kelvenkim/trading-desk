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
                                    partial=J.get("partial") or [], ob=J.get("ob"), amd=parse_amd(J) if kind == "amd" else None, accts=[]))["accts"].append(fn)
        for T in S.get("trades") or []:
            sym = T.get("sym") or "BTC-USD"
            if kind == "tr" or (kind.startswith("ma") and T.get("in") and T.get("out")):
                k = key_of(sym, T["in"], kind)
                jobs.setdefault(k, dict(kind=kind, sym=sym, side=T.get("side", 1), t_in=T["in"], fill=T.get("entry"), stop=None, target=None,
                                        t_out=T.get("out"), exit=T.get("exit"), R=T.get("R"), pl=T.get("pl"), why_out=T.get("why"), why_in=T.get("entry_why"), accts=[]))["accts"].append(fn)
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
                                    why_in=p.get("why"), accts=[]))["accts"].append(fn)
    return jobs


def sig(J):
    return hashlib.md5(json.dumps({k: J.get(k) for k in ("t_out", "exit", "stop", "partial")}, sort_keys=True, default=str).encode()).hexdigest()[:8]


def bars(sym, iv):
    import yfinance as yf
    d = yf.Ticker(sym).history(period="180d" if iv == "1h" else "2y", interval=iv).dropna()
    d.index = d.index.tz_convert("UTC"); d.columns = [c.lower() for c in d.columns]
    return d[["open", "high", "low", "close"]]


def draw(J, d, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
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
    idx = {t: i for i, t in enumerate(x.index)}
    def xi(t):
        t = ts(t); k = x.index.searchsorted(t)
        return min(max(k, 0), len(x) - 1)
    fig, ax = plt.subplots(figsize=(10, 5.4), dpi=110)
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["panel"])
    for s_ in ax.spines.values():
        s_.set_color(C["line"])
    ax.tick_params(colors=C["faint"], labelsize=8); ax.grid(color=C["line"], lw=.5, alpha=.6)
    o, h, l, c = x.open.values, x.high.values, x.low.values, x.close.values
    for i in range(len(x)):
        col = C["up"] if c[i] >= o[i] else C["down"]
        ax.vlines(i, l[i], h[i], color=col, lw=.8); ax.add_patch(plt.Rectangle((i - .32, min(o[i], c[i])), .64, max(abs(c[i] - o[i]), (h[i] - l[i]) * .01), color=col))
    if J["kind"] == "tr":
        cc = d.close
        for n, colr in ((20, C["warn"]), (50, C["accent"]), (200, C["muted"])):
            e = cc.ewm(span=n, adjust=False).mean().reindex(x.index)
            ax.plot(range(len(x)), e.values, color=colr, lw=1.1, label=f"EMA{n}")
    if daily:
        m50 = d.close.rolling(50).mean().reindex(x.index)
        ax.plot(range(len(x)), m50.values, color=C["warn"], lw=1.4, label="50일선")
    side = J["side"]; sd = "숏" if side < 0 else "롱"; i0 = xi(t_in); n = len(x)
    lab = lambda xx, yy, s, col, dy=0: ax.annotate(s, (xx, yy), xytext=(0, dy), textcoords="offset points", color=col, fontsize=8.6, fontweight="bold", ha="center",
                                                   bbox=dict(boxstyle="round,pad=.3", fc=C["bg"], ec=col, lw=.8, alpha=.92))
    rng = (h.max() - l.min()) or 1
    step = 1
    if J["kind"] == "ob" and J.get("ob"):
        ib = xi(J["ob"]["t"]); lo, hi = sorted([J["fill"], J["stop"]])
        if J["ob"].get("t"):
            ent = J.get("fill")
        ax.add_patch(plt.Rectangle((ib - 1.5, lo), max(2, (xi(J["t_out"]) if J.get("t_out") else n - 1) - ib + 2), hi - lo, color=C["accent"], alpha=.30, lw=1.2, ec=C["accent"]))
        lab(ib, hi if side < 0 else lo, f"① 오더블록 ({pd.Timestamp(J['ob']['t']).tz_convert(KST):%m/%d %H시})", C["accent"], 30 if side < 0 else -34); step = 2
    if J["kind"] == "amd" and J.get("amd"):
        A = J["amd"]; ib = xi(A["box_from"]); ir = xi(A.get("reclaim_at") or J["t_in"])
        ax.add_patch(plt.Rectangle((ib, A["blo"]), max(1, ir - ib), A["bhi"] - A["blo"], color=C["muted"], alpha=.12, lw=0))
        ax.hlines(A["poc"], ib, n - 1, color=C["orange"], lw=1, ls="--"); ax.text(n - 1, A["poc"], " POC", color=C["orange"], fontsize=8, va="center")
        lab((ib + ir) / 2, A["bhi"] if side < 0 else A["blo"], "① 매집 박스 (24봉)", C["muted"], -16 if side < 0 else 14)
        if A.get("ext"):
            lab(ir, A["ext"], f"② 조작: 박스 {'위' if side < 0 else '아래'} {f(A['ext'])}까지 가짜 이탈", C["warn"], 14 if side < 0 else -18)
        step = 3
    if J.get("stop"):
        ax.hlines(J["stop"], i0, n - 1, color=C["up"] if side > 0 else C["up"], lw=1, ls=":"); ax.text(n - 1, J["stop"], f" 손절 {f(J['stop'])}", color=C["up"], fontsize=8, va="center")
    if J.get("target"):
        ax.hlines(J["target"], i0, n - 1, color=C["ok"], lw=1, ls=":"); ax.text(n - 1, J["target"], f" 목표 {f(J['target'])}", color=C["ok"], fontsize=8, va="center")
    why = {"ob": "구간 터치 → ", "amd": "POC 되돌림 → ", "tr": "EMA20 눌림 → ", "ma": "50일선 " + ("아래" if side < 0 else "위") + " → ", "ma10": "50일선 " + ("아래" if side < 0 else "위") + " → "}[J["kind"]]
    ax.scatter([i0], [J["fill"]], marker="v" if side < 0 else "^", s=110, color="#fff", zorder=5, edgecolor=C["accent"])
    lab(i0, J["fill"], f"{'①②③'[min(step, 3) - 1] if step <= 3 else ''} {why}{sd} 진입 {f(J['fill'])}".replace("  ", " "), "#fff", 24 if side > 0 else -30)
    k = step + 1
    for p in J.get("partial") or []:
        ip = xi(p["at"]); ax.scatter([ip], [p["px"]], marker="o", s=60, color=C["ok"], zorder=5)
        lab(ip, p["px"], f"{'①②③④⑤'[min(k, 5) - 1]} 절반 익절 {f(p['px'])}", C["ok"], -50 if side < 0 else 44); k += 1
    if J.get("t_out") and J.get("exit") is not None:
        io = xi(J["t_out"]); col = C["ok"] if (J.get("R") or J.get("pl") or 0) > 0 else C["up"]
        ax.scatter([io], [J["exit"]], marker="X", s=90, color=col, zorder=5)
        res = f"{J['R']:+.2f}R" if J.get("R") is not None else (f"{J['pl'] * 100:+.1f}%" if J.get("pl") is not None else "")
        lab(io, J["exit"], f"{'①②③④⑤⑥'[min(k, 6) - 1]} 정리 {f(J['exit'])} {res}", col, 14 if side < 0 else -20)
    ax.set_xlim(-1, n + 6); ax.set_ylim(l.min() - rng * .08, h.max() + rng * .12)
    tk = np.linspace(0, n - 1, 6).astype(int)
    ax.set_xticks(tk); ax.set_xticklabels([x.index[i].tz_convert(KST).strftime("%m/%d" if daily else "%m/%d %H시") for i in tk])
    kindname = {"ob": "오더블록", "amd": "AMD (매집→조작→분산)", "tr": "추세 눌림 (10배 단타)", "ma": "50일선", "ma10": "50일선 (10배)"}[J["kind"]]
    state = "보유 중" if not J.get("t_out") else (f"{J['R']:+.2f}R" if J.get("R") is not None else (f"{J['pl'] * 100:+.1f}%" if J.get("pl") is not None else "끝"))
    ax.set_title(f"{kindname} · {NM.get(J['sym'], J['sym'])} {sd} · {t_in.tz_convert(KST):%m/%d %H:%M} 진입 · {state}", color=C["text"], fontsize=11.5, loc="left", fontweight="bold")
    if J["kind"] in ("tr", "ma", "ma10"):
        ax.legend(loc="upper left", fontsize=7.5, facecolor=C["bg"], edgecolor=C["line"], labelcolor=C["muted"])
    fig.text(.01, .01, f"{'1시간봉' if not daily else '일봉'} · 한국 시간 · 빨강 오름 / 파랑 내림 · {J.get('why_out') or ''}"[:110], color=C["faint"], fontsize=7.5)
    fig.tight_layout(rect=(0, .03, 1, 1)); OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=C["bg"]); plt.close(fig)
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
            if draw(J, cache[(J["sym"], iv)], p):
                I[k] = dict(png=str(p.relative_to(ROOT)), sig=sig(J), kind=J["kind"], accts=sorted(set(J["accts"])))
                print("그림:", k, name)
        except Exception as e:
            print("그림 실패", k, e)
    OUT.mkdir(parents=True, exist_ok=True); IDX.write_text(json.dumps(I, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    run("--need" in sys.argv)
