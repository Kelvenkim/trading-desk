"""
장기 투자 리서치 PDF — 산업 보고서 1개 + 회사별 1개씩 (인쇄용 흰 바탕)
reports/longterm/<산업>/industry.pdf, reports/longterm/<산업>/<티커>.pdf
"""
import html, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us/longterm"
OUT = ROOT / "reports/longterm"
e = lambda x: html.escape(str(x if x is not None else ""))
tag = lambda k: f"<span class='k {'f' if k == '사실' else 'e' if k == '추정' else 'u'}'>{e(k)}</span>"
item = lambda x: f"<li>{tag(x[1])} {e(x[0])}</li>"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pdf_style as PS


def big(v, cur="USD"):
    if v is None:
        return "—"
    s = {"JPY": "¥", "GBp": "£", "EUR": "€", "KRW": "₩", "GBP": "£"}.get(cur, "$"); v = v / 100 if cur == "GBp" else v
    return f"{s}{v / 1e12:.2f}조" if v >= 1e12 else f"{s}{v / 1e8:.1f}억" if v >= 1e8 else f"{s}{v / 1e4:,.0f}만" if v >= 1e4 else f"{s}{v:,.0f}"


def page(title, body):
    """11/22: 산업 리서치도 사이트 톤(pdf_style)으로 통일"""
    return PS.wrap(e(title), body + "<div class='foot'>투자 권유가 아니라 판단 재료예요. 사실 = 공시·보도로 확인 / 추정 = 판단·가정 / 모름 = 확인 못 함. 과거 검증이 미래를 보장하지 않아요.</div>")


def industry(R):
    M, N = R["macro"], R["narrative"]; S = PS.sec
    b = (f"<div class='hero'><div class='tk'>산업 리서치 · {e(R['asof'])} 기준 · 숫자 {e((R.get('metrics_at') or '')[:10])}</div><h1>{e(R['name'])}</h1>"
         f"<span class='chip'>매크로 → 산업 → 공급망 → 상장사 → 회사 검증 → 시나리오 → 분류</span><div class='box' style='margin-top:10px'>{e(R['summary'])}</div></div>")
    s1 = f"<p>{e(M['verdict_why'])}</p><div class='two'>" + "".join(f"<div><h3>{n}</h3><ul>{''.join(item(x) for x in M[k])}</ul></div>"
                                                              for n, k in (("우호 요인", "good"), ("비우호 요인", "bad"), ("유동성", "liquidity"), ("지정학", "geo"))) + "</div>"
    b += S("1단계", f"매크로 환경 — {e(M['verdict'])}", s1)
    s2 = f"<p><b>{e(N['mega'])}</b></p><table><tr><th>축</th><th>뒷받침</th><th>근거</th></tr>"
    s2 += "".join(f"<tr><td>{e(a)}</td><td>{e(s_)}</td><td>{e(t)}</td></tr>" for a, s_, t, *_ in N["axes"]) + "</table>"
    s2 += f"<p>시장 선반영: <b>{N['priced']}%</b> (0 / 50 / 75 중) — {tag(N['priced_why'][1])} {e(N['priced_why'][0])}</p>"
    s2 += f"<div class='two'><div><h3>강화 시나리오</h3><ul>{''.join(f'<li>{e(x)}</li>' for x in N['up'])}</ul></div><div><h3>약화 시나리오</h3><ul>{''.join(f'<li>{e(x)}</li>' for x in N['down'])}</ul></div></div>"
    b += S("2단계", "산업 내러티브", s2)
    s3 = "<table><tr><th>레이어</th><th>강도</th><th>발생</th><th>유지</th><th>근거</th></tr>"
    s3 += "".join(f"<tr class='avoid'><td><b>{e(c['layer'])}</b><br><span class='sm'>{e(c['desc'])}</span></td><td>{e(c['neck'])}</td><td>{e(c['when'])}</td><td>{e(c['dur'])}</td><td>{tag(c['why'][1])} {e(c['why'][0])}{'<br>※ ' + e(c['note']) if c.get('note') else ''}</td></tr>" for c in R["chain"]) + "</table>"
    b += S("3단계", "공급망 병목", s3, "long")
    s4 = "<table><tr><th>회사</th><th>레이어</th><th class='n'>시총</th><th class='n'>20일 거래대금</th><th class='n'>PS</th><th>등급</th><th>최근 성장</th><th>분류</th></tr>"
    for c in R["companies"]:
        m = c.get("m") or {}
        s4 += f"<tr class='avoid'><td><b>{e(c['name'])}</b><br><span class='sm'>{e(c['t'])} · {e(c['exch'])}</span></td><td>{e(c['layer'])}</td><td class='n'>{big(m.get('mcap'), m.get('cur'))}</td><td class='n'>{big(m.get('adv'), m.get('cur'))}</td><td class='n'>{f'{m['ps']:.0f}배' if m.get('ps') else '—'}</td><td>{e(c['v']['grade'])}</td><td>{tag(c['growth'][1])} {e(c['growth'][0])}</td><td>{e(c['cls'])}</td></tr>"
    s4 += "</table><h3>제외한 곳</h3><ul>" + "".join(f"<li>{tag(k)} <b>{e(n)}</b> — {e(w)}</li>" for n, w, k, *_ in R["excluded"]) + "</ul>"
    b += S("4단계", "글로벌 상장 공급사", s4, "long")
    s7 = "<table>" + "".join(f"<tr><td><b>{e(n)}</b></td><td>{', '.join(e(next((c['name'] for c in R['companies'] if c['t'] == t), t)) for t in ts)}</td><td>{e(w)}</td></tr>" for n, ts, w in R["final"]) + "</table>"
    b += S("7단계", "최종 분류", s7)
    b += S("", "출처", "<ul class='sm'>" + "".join(f"<li>{e(x)}</li>" for x in R["sources"]) + "</ul>", "long")
    return page(R["name"] + " 산업 리서치", b)


# ---------------- 회사 분석표 (사이트 톤: 어두운 바탕·보라 포인트·둥근 카드) ----------------
SCSS = """
@page { size: A4; margin: 0; }
:root { --bg:#0f1013; --panel:#18191d; --raised:#202227; --line:#2b2d33; --text:#eceef2; --muted:#a3a7b1; --faint:#6f7480; --accent:#7c83ff; --up:#ff5f6b; --down:#4ea3ff; --ok:#3ecf8e; --warn:#f5b84b; }
* { box-sizing: border-box; }
html, body { background: var(--bg); }
body { margin: 0; padding: 0 11mm; font-family: 'Noto Sans CJK KR','Noto Sans KR',sans-serif; font-size: 10px; color: var(--text); line-height: 1.6; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
b { color: #fff; } a { color: var(--accent); }
.hero { background: linear-gradient(135deg, #23264a, #18191d 60%); border-radius: 18px; padding: 16px 18px; margin-bottom: 12px; }
.hero .tk { color: var(--muted); font-size: 10.5px; } .hero h1 { font-size: 24px; margin: 2px 0 4px; letter-spacing: -.3px; }
.chip { display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 9.5px; font-weight: 700; background: rgba(124,131,255,.18); color: #c9ccff; margin-right: 4px; }
.kgrid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; margin-top: 12px; }
.kgrid div { background: rgba(255,255,255,.04); border-radius: 12px; padding: 7px 9px; } .kgrid span { display: block; color: var(--faint); font-size: 8.5px; } .kgrid b { font-size: 12px; }
.sec { background: var(--panel); border-radius: 16px; padding: 12px 14px; margin: 10px 0; }
.sec > h2 { font-size: 13.5px; margin: 0 0 8px; display: flex; align-items: center; gap: 8px; }
.sec > h2 .no { color: var(--accent); font-size: 11px; font-weight: 800; } .sec > h2::before { content: ""; width: 4px; height: 15px; border-radius: 3px; background: var(--accent); }
.sec h3 { font-size: 11px; margin: 10px 0 4px; color: #fff; } .sec p { margin: 4px 0; }
.wrap { display: grid; grid-template-columns: minmax(0, 1fr) 30%; gap: 12px; }
.side { border-left: 1px solid var(--line); padding-left: 10px; font-size: 8.6px; color: var(--muted); }
.side .t { color: var(--accent); font-weight: 700; display: block; margin-top: 5px; } .side .h { color: var(--faint); font-size: 8px; letter-spacing: .5px; }
.box { background: #08090b; border-radius: 12px; padding: 8px 11px; margin: 6px 0; }
table { width: 100%; border-collapse: collapse; margin: 4px 0; font-size: 9.3px; }
th { color: var(--faint); font-weight: 600; text-align: left; padding: 4px 5px; border-bottom: 1px solid var(--line); font-size: 8.6px; }
td { padding: 5px 5px; border-bottom: 1px solid #222428; vertical-align: top; } td.n, th.n { text-align: right; white-space: nowrap; }
tr.me td { background: rgba(124,131,255,.10); }
.k { display: inline-block; font-size: 7.8px; border-radius: 5px; padding: 0 5px; margin-right: 3px; font-weight: 700; vertical-align: 1px; }
.k.f { background: rgba(62,207,142,.15); color: var(--ok); } .k.e { background: rgba(245,184,75,.15); color: var(--warn); } .k.u { background: rgba(163,167,177,.15); color: var(--muted); }
.up { color: var(--up); } .dn { color: var(--down); } .mut { color: var(--muted); } .sm { font-size: 8.6px; color: var(--faint); }
ul { margin: 3px 0; padding-left: 14px; } li { margin: 3px 0; }
.thesis li { margin: 6px 0; }
.chain { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin: 6px 0; }
.chain div { background: var(--raised); border-radius: 10px; padding: 6px 7px; font-size: 8.6px; min-height: 36px; border: 1px solid transparent; }
.chain div.me { border-color: var(--accent); background: rgba(124,131,255,.14); } .chain i { display: block; font-style: normal; color: var(--faint); font-size: 8px; }
.lvl { font-weight: 800; } .lvl.s { color: var(--ok); } .lvl.m { color: var(--warn); } .lvl.w { color: var(--up); }
.three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; } .sc { background: var(--raised); border-radius: 12px; padding: 8px 9px; } .sc p { margin: 3px 0; font-size: 9px; }
.qa { background: var(--raised); border-radius: 12px; padding: 8px 11px; margin: 7px 0; break-inside: avoid; }
.qa .q { font-weight: 700; color: #fff; } .qa .q em { color: var(--accent); font-style: normal; margin-right: 4px; } .qa .a { margin-top: 4px; color: #d6d8de; }
.chart { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 6px 0; } .chart div { background: var(--raised); border-radius: 12px; padding: 7px 9px; }
.ck li { list-style: none; margin-left: -14px; } .ck .y { color: var(--ok); font-weight: 800; } .ck .n { color: var(--warn); font-weight: 800; }
.concl { border: 1px solid var(--accent); border-radius: 14px; padding: 9px 12px; background: rgba(124,131,255,.07); } .concl p { margin: 5px 0; font-size: 10.3px; }
.avoid, .sec { break-inside: avoid-page; } .sec.long { break-inside: auto; }
.pg { width: 100%; border-collapse: collapse; font-size: inherit; margin: 0; } .pg > thead td, .pg > tfoot td { height: 10mm; padding: 0; border: 0; } .pg > tbody > tr > td { padding: 0; border: 0; }
.sec > h2 { break-after: avoid; } h3 { break-after: avoid; }
.foot { color: var(--faint); font-size: 8px; margin-top: 10px; }
"""
REC = {"strong_buy": "강력 매수", "buy": "매수", "hold": "보유", "underperform": "비중 축소", "sell": "매도", "none": "—"}
KT = lambda k: f"<span class='k {'f' if k == '사실' else 'e' if k == '추정' else 'u'}'>{e(k)}</span>"


def money(v, cur="USD"):
    if v is None:
        return "—"
    s = {"JPY": "¥", "EUR": "€", "KRW": "₩", "GBP": "£"}.get(cur, "$"); neg = v < 0; v = abs(v)
    t = f"{v / 1e12:.2f}조" if v >= 1e12 else f"{v / 1e8:,.0f}억" if v >= 1e10 else f"{v / 1e8:,.1f}억" if v >= 1e9 else f"{v / 1e8:.2f}억" if v >= 1e8 else f"{v / 1e4:,.0f}만" if v >= 1e4 else f"{v:,.0f}"
    return ("−" if neg else "") + s + t


def pc(x, d=0):
    return "—" if x is None else f"{x * 100:+.{d}f}%"


def side(text, G, seen):
    """본문에 나온 어려운 말을 찾아 옆 칸 풀이로 (같은 문서에서 이미 풀이한 말은 생략)"""
    hits = [k for k in sorted(G, key=len, reverse=True) if k in text and k not in seen]
    out = []
    for k in hits:
        if any(k in h and k != h for h in out):
            continue
        out.append(k); seen.add(k)
    return "".join(f"<span class='t'>{e(k)}</span>{e(G[k])}" for k in out[:7])


def sec(no, title, body, G, seen, long=False):
    import re
    plain = re.sub(r"<[^>]+>", " ", body)
    sd = side(plain, G, seen)
    inner = f"<div class='wrap'><div>{body}</div><div class='side'><span class='h'>용어 풀이</span>{sd}</div></div>" if sd else body
    return f"<div class='sec{' long' if long else ''}'><h2><span class='no'>{no}</span>{e(title)}</h2>{inner}</div>"


def bars(vals, labels, fmt, h=70, w=230, color=None):
    """분기 막대 그래프 (SVG). 양수 빨강·음수 파랑(사이트 규칙)"""
    vs = [v for v in vals if v is not None]
    if not vs:
        return "<p class='sm'>자료 없음</p>"
    mx = max(abs(v) for v in vs) or 1; has_neg = any(v < 0 for v in vs)
    base = h / 2 if has_neg else h - 12; sc = (h / 2 - 10 if has_neg else h - 22) / mx
    n = len(vals); bw = w / n * 0.56; g = ""
    for i, (v, lb) in enumerate(zip(vals, labels)):
        x = w / n * i + (w / n - bw) / 2
        if v is not None:
            hh = abs(v) * sc; y = base - hh if v >= 0 else base
            c = color or ("#ff5f6b" if v >= 0 else "#4ea3ff")
            g += f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{max(hh, .8):.1f}' rx='2' fill='{c}'/>"
            ty = y - 2 if v >= 0 else y + hh + 7
            g += f"<text x='{x + bw / 2:.1f}' y='{ty:.1f}' font-size='6.4' fill='#a3a7b1' text-anchor='middle'>{fmt(v)}</text>"
        g += f"<text x='{x + bw / 2:.1f}' y='{h + 8}' font-size='6.4' fill='#6f7480' text-anchor='middle'>{lb}</text>"
    g += f"<line x1='0' x2='{w}' y1='{base}' y2='{base}' stroke='#2b2d33' stroke-width='.6'/>"
    return f"<svg viewBox='0 -4 {w} {h + 14}' width='100%'>{g}</svg>"


def pline(m, cur, w=560, h=90):
    """1년 주간 종가 + 리서치 시점 표시 (보라 선)"""
    W = m.get("wk") or []
    if len(W) < 10:
        return ""
    xs = [x for _, x in W]; lo, hi = min(xs), max(xs); rg = (hi - lo) or 1
    pts = " ".join(f"{i / (len(xs) - 1) * w:.1f},{h - (x - lo) / rg * (h - 14) - 4:.1f}" for i, x in enumerate(xs))
    g = f"<polyline points='{pts}' fill='none' stroke='#7c83ff' stroke-width='1.6'/>"
    if m.get("ma200") and lo <= m["ma200"] <= hi:
        y = h - (m["ma200"] - lo) / rg * (h - 14) - 4
        g += f"<line x1='0' x2='{w}' y1='{y:.1f}' y2='{y:.1f}' stroke='#6f7480' stroke-dasharray='3 3' stroke-width='.7'/><text x='{w - 2}' y='{y - 3:.1f}' font-size='7' fill='#6f7480' text-anchor='end'>200일선 {m['ma200']}</text>"
    g += f"<text x='0' y='9' font-size='7' fill='#a3a7b1'>최고 {hi}</text><text x='0' y='{h + 6}' font-size='7' fill='#a3a7b1'>최저 {lo}</text>"
    g += f"<text x='{w}' y='{h + 6}' font-size='7' fill='#a3a7b1' text-anchor='end'>{W[0][0]} ~ {m.get('day', W[-1][0])} 주간 종가 ({cur})</text>"
    return f"<div style='margin-top:10px'><svg viewBox='0 0 {w} {h + 8}' width='100%'>{g}</svg></div>"


def company(R, c):
    import re
    from datetime import date, timedelta
    v, sc, m = c["v"], c["sc"], c.get("m") or {}
    A, Dp, G = c.get("about") or {}, c.get("deep") or {}, R.get("gloss") or {}
    seen = set(); cur = m.get("cur", "USD"); fn = m.get("fin") or {}; Q = fn.get("q") or []; st = m.get("street") or {}
    ql = lambda q: f"{q[2:4]}.{(int(q[5:7]) + 2) // 3}Q"
    # ---------- 표지 ----------
    pos52 = (m["px"] - m["lo52"]) / (m["hi52"] - m["lo52"]) if m.get("hi52") and m.get("lo52") and m["hi52"] > m["lo52"] else None
    kp = [("주가", f"{m.get('px', '—')} {cur}"), ("시가총액", money(m.get("mcap"), cur)), ("EV", money(st.get("ev"), cur)),
          ("매출 대비(PS)", f"{m['ps']:.1f}배" if m.get("ps") else "—"), ("52주 범위 내 위치", ("최저 근처" if pos52 < .05 else "최고 근처" if pos52 > .95 else f"{pos52 * 100:.0f}%") if pos52 is not None else "—"),
          ("공매도 비율", f"{st['short'] * 100:.1f}%" if st.get("short") else "—")]
    b = f"""<div class='hero'><div class='tk'>{e(c['t'])} · {e(c['exch'])} · {e(R['name'])} 장기 리서치</div><h1>{e(c['name'])} 기업 분석표</h1>
<span class='chip'>분류 · {e(c['cls'])}</span><span class='chip'>고객 검증 {e(v['grade'])}등급</span><span class='chip'>산업 매크로 · {e(R['macro']['verdict'])}</span>
<div class='kgrid'>{''.join(f"<div><span>{k}</span><b>{x}</b></div>" for k, x in kp)}</div>
{pline(m, cur)}<div class='sm' style='margin-top:8px'>리서치 {e(R['asof'])} · 시세·재무 {e(m.get('day', ''))} (yfinance, 회사 공시 기반) · <span class='k f'>사실</span>공시·보도 확인 <span class='k e'>추정</span>판단·가정 <span class='k u'>모름</span>확인 못 함</div></div>"""
    # ---------- 01 요약 ----------
    s1 = ""
    if A.get("edge"):
        s1 += f"<div class='box'><b>핵심 한 줄</b> — {e(A['edge'])}</div>"
    if Dp.get("thesis"):
        s1 += "<h3>투자 논지</h3><ul class='thesis'>" + "".join(f"<li>{KT(k)} {e(t)}</li>" for t, k in Dp["thesis"]) + "</ul>"
    if Dp.get("debates"):
        s1 += "<h3>핵심 쟁점 — 어디서 의견이 갈리나</h3><table><tr><th style='width:16%'>쟁점</th><th>강세 논리</th><th>약세 논리</th><th style='width:24%'>우리 판단 기준</th></tr>" + "".join(
            f"<tr><td><b>{e(a)}</b></td><td class='up'>{e(x)}</td><td class='dn'>{e(y)}</td><td>{e(z)}</td></tr>" for a, x, y, z in Dp["debates"]) + "</table>"
    if not s1:
        s1 = f"<p>{e(c['cls'])} — {e(c['good_if'])}</p>"
    b += sec("01", "요약", s1, G, seen)
    # ---------- 02 사업 이해 ----------
    s2 = ""
    if A:
        s2 += f"<p><b>사업 정의</b> {e(A['what'])}</p><p><b>제품·매출원</b> {e(A['makes'])}</p><p><b>가치사슬에서 왜 필요한가</b> {e(A['why'])}</p>"
    s2 += "".join(f"<p class='mut'>{e(x)}</p>" for x in Dp.get("hook", []))
    if Dp.get("money"):
        s2 += "<h3>매출 구조</h3><table><tr><th>부문</th><th>내용</th><th class='n'>최근 분기</th><th class='n'>비중</th></tr>" + "".join(
            f"<tr><td><b>{e(n)}</b></td><td>{e(x)}</td><td class='n'>{e(y)}</td><td class='n'>{e(z)}</td></tr>" for n, x, y, z in Dp["money"]) + "</table>"
    else:
        s2 += f"<p><b>주요 제품</b> {e(c['products'])}</p>"
    s2 += f"<p><b>주요 고객</b> {e(c['customers'])}</p><p><b>최근 성장</b> {KT(c['growth'][1])} {e(c['growth'][0])}</p>"
    b += sec("02", "사업 이해", s2, G, seen, long=True)
    # ---------- 03 기술 ----------
    if Dp.get("tech"):
        b += sec("03", "기술과 제품 — 무엇이 경쟁력인가", "".join(f"<h3>{e(t)}</h3><p>{e(x)}</p>" for t, x in Dp["tech"]), G, seen, long=True)
    # ---------- 04 산업·경쟁 ----------
    mine = set(re.findall(r"L(\d)", c["layer"]))
    lv = lambda x: re.match(r"L(\d)", x)
    s4 = f"<p class='sm'>{e(R['name'])} 공급망 — 보라 테두리가 이 회사 위치. 아래 작은 글씨 = 병목 강도 · 유지 기간</p><div class='chain'>"
    s4 += "".join(f"<div class='{'me' if lv(x['layer']) and lv(x['layer']).group(1) in mine else ''}'><b>{e(x['layer'])}</b><i>{e(x['neck'])} · {e(x['dur'])}</i></div>" for x in R["chain"]) + "</div>"
    peers = sorted([p for p in R["companies"] if (p.get("m") or {}).get("mcap")], key=lambda p: -p["m"]["mcap"])
    if len(peers) > 1:
        def gm(p):
            qq = ((p.get("m") or {}).get("fin") or {}).get("q") or []
            x = next((y.get("gm") for y in reversed(qq) if y.get("gm") is not None), None)
            return f"{x * 100:.0f}%" if x is not None else "—"
        s4 += "<h3>같은 산업 상장사 비교</h3><table><tr><th>회사</th><th>위치</th><th class='n'>시총</th><th class='n'>PS</th><th class='n'>매출 성장</th><th class='n'>총마진</th><th class='n'>200일선 대비</th><th>분류</th></tr>"
        for p in peers[:9] + ([c] if c not in peers[:9] and c in peers else []):
            pm = p["m"]
            s4 += (f"<tr class='{'me' if p is c else ''}'><td><b>{e(p['name'])}</b> <span class='sm'>{e(p['t'])}</span></td><td class='sm'>{e(p['layer'][:22])}</td>"
                   f"<td class='n'>{money(pm.get('mcap'), pm.get('cur', 'USD'))}</td><td class='n'>{f'{pm['ps']:.1f}' if pm.get('ps') else '—'}</td>"
                   f"<td class='n'>{pc(pm.get('rev_g'))}</td><td class='n'>{gm(p)}</td><td class='n'>{pc(pm['px'] / pm['ma200'] - 1) if pm.get('ma200') else '—'}</td><td class='sm'>{e(p['cls'][:14])}</td></tr>")
        s4 += "</table><p class='sm'>매출 성장은 최근 분기 전년 대비(yfinance). 통화가 다른 회사는 시총을 현지 통화로 표시.</p>"
    if Dp.get("moat"):
        cls = {"강": "s", "중": "m", "약": "w"}
        s4 += "<h3>경쟁 우위(해자) 평가</h3><table><tr><th style='width:20%'>원천</th><th style='width:9%'>강도</th><th>근거</th></tr>" + "".join(
            f"<tr><td><b>{e(a)}</b></td><td class='lvl {cls.get(l[0], 'm')}'>{e(l)}</td><td>{e(x)}</td></tr>" for a, l, x in Dp["moat"]) + "</table>"
    s4 += f"<p><b>공급망 지위</b> {KT(v['pos'][1])} {e(v['pos'][0])}</p><p><b>대체 가능성</b> {KT(v['sub'][1])} {e(v['sub'][0])}</p>"
    b += sec("04", "산업 구조와 경쟁", s4, G, seen, long=True)
    # ---------- 05 재무 ----------
    s5 = ""
    if Q:
        L = [ql(x["q"]) for x in Q]
        s5 += f"""<div class='chart'><div><b class='sm'>분기 매출</b>{bars([x.get('rev') for x in Q], L, lambda z: money(z, cur), color='#7c83ff')}</div>
<div><b class='sm'>분기 FCF (빨강 +, 파랑 −)</b>{bars([x.get('fcf') for x in Q], L, lambda z: money(z, cur))}</div></div>"""
        rows = [("매출", "rev", money), ("전년 대비", "yoy", None), ("총마진", "gm", None), ("영업이익", "op", money), ("순이익", "ni", money),
                ("연구개발", "rnd", money), ("영업현금흐름", "ocf", money), ("설비 투자", "capex", money), ("FCF", "fcf", money),
                ("주식 보상", "sbc", money), ("현금·단기투자", "cash", money), ("총부채", "debt", money), ("발행 주식", "sh", None), ("주식 수 전년 대비", "sh_yoy", None)]
        s5 += "<table><tr><th>항목</th>" + "".join(f"<th class='n'>{l}</th>" for l in L) + "</tr>"
        for nm, k, f in rows:
            if all(x.get(k) is None for x in Q):
                continue
            cells = []
            for x in Q:
                val = x.get(k)
                if val is None:
                    cells.append("—")
                elif k in ("yoy", "sh_yoy"):
                    cells.append(f"<span class='{'up' if val > 0 else 'dn'}'>{pc(val)}</span>")
                elif k == "gm":
                    cells.append(f"{val * 100:.1f}%")
                elif k == "sh":
                    cells.append(f"{val / 1e8:.2f}억 주")
                else:
                    cells.append(f"<span class='{'dn' if val < 0 else ''}'>{f(val, cur)}</span>")
            s5 += f"<tr><td>{nm}</td>" + "".join(f"<td class='n'>{z}</td>" for z in cells) + "</tr>"
        s5 += "</table>"
        ocf4 = [x["ocf"] for x in Q[-4:] if x.get("ocf") is not None]
        if fn.get("runway_q") and ocf4 and sum(ocf4) < 0:
            s5 += f"<div class='box'><b>런웨이(단순 계산)</b> 현금·단기투자 ÷ 최근 4분기 평균 FCF 적자 = 약 <b>{fn['runway_q']:.0f}분기</b>. 차입·증자·장기 투자 자산은 빼고 계산한 보수적 값.</div>"
        elif ocf4 and sum(ocf4) > 0 and fn.get("ttm_fcf") is not None and fn["ttm_fcf"] < 0:
            s5 += "<div class='box'>영업현금흐름은 플러스 — FCF 적자는 본업 적자가 아니라 <b>설비 투자</b> 때문. 런웨이보다 '투자 회수 속도'와 '조달 비용'이 쟁점.</div>"
    s5 += "".join(f"<p>{KT(k)} {e(t)}</p>" for t, k in Dp.get("fin_notes", []))
    vf = v["fin"]
    if vf[1] == "모름" and Q:
        lq = Q[-1]; f4 = [x["fcf"] for x in Q[-4:] if x.get("fcf") is not None]
        vf = (f"최근 4분기 FCF 합계 {money(sum(f4), cur) if len(f4) == 4 else '—'}, 현금·단기투자 {money(lq.get('cash'), cur)}, 총부채 {money(lq.get('debt'), cur)} ({ql(lq['q'])}, 위 표 자동 요약)", "사실")
    s5 += f"<p><b>재무 건전성</b> {KT(vf[1])} {e(vf[0])}</p><p><b>희석</b> {KT(v['dil'][1])} {e(v['dil'][0])}</p>"
    b += sec("05", "재무 분석 — 숫자를 쪼개 보기", s5, G, seen, long=True)
    # ---------- 06 밸류에이션 ----------
    evs = st.get("ev") / fn["ttm_rev"] if st.get("ev") and fn.get("ttm_rev") else None
    s6 = f"<p><b>지금({e(m.get('day', ''))})</b> 시총 {money(m.get('mcap'), cur)} · EV {money(st.get('ev'), cur)} · 최근 4분기 매출 {money(fn.get('ttm_rev'), cur)} · PS {f'{m['ps']:.1f}배' if m.get('ps') else '—'} · EV/매출 {f'{evs:.1f}배' if evs else '—'}</p>"
    s6 += f"<p class='mut'><b>리서치 당시({e(R['asof'])}) 판단</b> {KT(v['val'][1])} {e(v['val'][0])}</p>"
    if st.get("n"):
        up = st["target"] / m["px"] - 1 if st.get("target") and m.get("px") else None
        s6 += f"<p><b>월가</b> 애널리스트 {st['n']}명 평균 목표가 {f"{st['target']:,.2f}" if st.get('target') else '—'} ({pc(up)}) · 의견 {e(REC.get(st.get('rec'), st.get('rec') or '—'))} · 기관 보유 {pc(st.get('inst')).lstrip('+')} · 내부자 {pc(st.get('insider'), 1).lstrip('+')}</p>"
    ttm = fn.get("ttm_rev"); mc = m.get("mcap")
    if ttm and mc and ttm > 0:
        ni4 = [x["ni"] for x in Q[-4:] if x.get("ni") is not None]
        cur_m = sum(ni4) / ttm if len(ni4) == 4 else None
        mg = Dp.get("margin") or (min(max(cur_m, .05), .30) if cur_m and cur_m > 0 else .15); pe = Dp.get("pe") or 25
        need = mc * 1.10 ** 5 / (pe * mg); cagr = (need / ttm) ** (1 / 5) - 1
        s6 += f"""<h3>역산 — 지금 몸값이 맞으려면</h3><div class='box'>연 10% 기대수익을 요구하는 투자자 기준, 5년 뒤 시총은 지금의 1.61배여야 합니다. 그때 PER {pe}배·순이익률 {mg * 100:.0f}%(성숙기 가정, {KT('추정')})라면
필요한 5년 뒤 연 매출은 <b>{money(need, cur)}</b> — 최근 4분기 매출 {money(ttm, cur)}에서 <b>매년 {cagr * 100:.0f}%</b> 성장해야 합니다.</div>
{f"<p>{KT('추정')} {e(Dp['val_note'])}</p>" if Dp.get('val_note') else ''}<p class='sm'>해석: 이 성장률이 회사 가이던스·산업 성장률보다 높으면 '성장이 이미 가격에 들어 있음', 낮으면 '기대가 보수적'. 가정을 바꾸면 결과가 크게 달라지니 방향만 참고.</p>"""
    B, S, W = sc["best"], sc["base"], sc["worst"]
    s6 += f"""<h3>시나리오 (리서치 시점 주가 대비 2029년 무렵, {KT('추정')})</h3><div class='three'>
<div class='sc'><b class='up'>최고 · 약 {B['mult']}배</b><p><b>가정</b> {e(B['assume'])}</p><p><b>근거</b> {e(B['evidence'])}</p><p><b>약점</b> {e(B['weak'])}</p><p><b>재평가 조건</b> {e(B['rerate'])}</p></div>
<div class='sc'><b>기본 · 약 {S['mult']}배</b><p><b>가정</b> {e(S['assume'])}</p><p><b>근거</b> {e(S['evidence'])}</p><p><b>부진 이유</b> {e(S['why_weak'])}</p></div>
<div class='sc'><b class='dn'>최악 · 약 {W['mult']}배</b><p><b>가정</b> {e(W['assume'])}</p><p><b>위험</b> {e(W['risks'])}</p><p><b>손실 경로</b> {e(W['loss'])}</p></div></div>"""
    ev = m.get("ev")
    if ev:
        s6 += f"<div class='box'><b>장기 손익비</b> 기댓값 = 상방 {ev['G'] * 100:+.0f}% × {ev['pG'] * 100:.0f}% + 하방 {ev['L'] * 100:+.0f}% × {(1 - ev['pG']) * 100:.0f}% = <b>{ev['value'] * 100:+.0f}%</b> · 손익비 {f'{ev['ratio']:.1f} : 1' if ev.get('ratio') else '—'} · 본전 확률 {ev['be'] * 100:.0f}% · 우리 기준 이상적 자리(상방 4배↑·하방 반토막 이내) <b>{'맞음' if ev['ideal'] else '아님'}</b></div>"
    b += sec("06", "밸류에이션", s6, G, seen, long=True)
    # ---------- 07 촉매·KPI ----------
    s7 = ""
    if Dp.get("catalysts"):
        s7 += "<h3>다가오는 확인 일정</h3><table><tr><th style='width:17%'>시점</th><th style='width:24%'>사건</th><th>볼 것</th></tr>" + "".join(f"<tr><td>{e(a)}</td><td><b>{e(x)}</b></td><td>{e(y)}</td></tr>" for a, x, y in Dp["catalysts"]) + "</table>"
    elif st.get("earn"):
        try:
            ed = date.fromisoformat(st["earn"]); nx = ed + timedelta(days=91) if ed < date.today() else ed
            s7 += f"<p><b>다음 실적</b> 약 {nx.isoformat()} 무렵 {KT('추정')}{f' · 다음 분기 매출 컨센서스 {money(st['next_rev'], cur)}' if st.get('next_rev') else ''}</p>"
        except Exception:
            pass
    if Dp.get("kpis"):
        s7 += "<h3>추적 지표 — 분기마다 이것만 보면 된다</h3><table><tr><th>지표</th><th class='n'>최근</th><th>좋은 신호</th><th>나쁜 신호</th></tr>" + "".join(
            f"<tr><td><b>{e(a)}</b></td><td class='n'>{e(x)}</td><td class='up'>{e(y)}</td><td class='dn'>{e(z)}</td></tr>" for a, x, y, z in Dp["kpis"]) + "</table>"
    else:
        s7 += f"<ul><li class='up'>좋은 신호: {e(c['good_if'])}</li><li class='dn'>나쁜 신호: {e(c['break_if'])}</li></ul>"
    b += sec("07", "촉매와 추적 지표", s7, G, seen, long=True)
    # ---------- 08 리스크 ----------
    if Dp.get("risks"):
        s8 = "<table><tr><th>위험</th><th style='width:9%'>가능성</th><th style='width:9%'>영향</th><th>먼저 보이는 신호</th></tr>" + "".join(
            f"<tr><td><b>{e(a)}</b></td><td>{e(p)}</td><td>{e(i)}</td><td>{e(s)}</td></tr>" for a, p, i, s in Dp["risks"]) + "</table>"
    else:
        s8 = f"<p><b>위험</b> {e(W['risks'])}</p><p><b>손실 경로</b> {e(W['loss'])}</p>"
    s8 += f"<p><b>경영진·실행</b> {KT(v['mgmt'][1])} {e(v['mgmt'][0])}</p><p><b>지정학·규제</b> {KT(v['geo'][1])} {e(v['geo'][0])}</p><p><b>생산 능력</b> {KT(v['capa'][1])} {e(v['capa'][0])}</p>"
    b += sec("08", "리스크", s8, G, seen, long=True)
    # ---------- 09 Q&A ----------
    qa = Dp.get("qa") or [
        ("이 회사를 다른 회사로 대체할 수 있나?", f"{v['pos'][0]} / {v['sub'][0]}", v["sub"][1]),
        ("지금 가격에 성장이 얼마나 들어 있나?", v["val"][0] + " — 위 역산 결과와 같이 보세요.", v["val"][1]),
        ("가장 크게 잃는 경로는?", f"{W['loss']}. 가설을 접는 신호: {c['break_if']}", "추정")]
    b += sec("09", "궁금증 Q&A", "".join(f"<div class='qa'><div class='q'><em>Q{i}</em>{e(q)}</div><div class='a'>{KT(k)} {e(a)}</div></div>" for i, (q, a, k) in enumerate(qa, 1)), G, seen, long=True)
    # ---------- 10 7단계 ----------
    M, N = R["macro"], R["narrative"]
    s10 = "<p class='sm'>모든 장기 종목 공통 틀: 매크로 → 산업 내러티브 → 공급망 병목 → 상장 공급사 → 회사 검증 8항목 → 시나리오 → 분류. 결론이 아니라 조건으로.</p>"
    s10 += f"<p><b>1 매크로 · {e(M['verdict'])}</b> {e(M['verdict_why'])}</p><p><b>2 산업 내러티브</b> {e(N['mega'])} · 시장 선반영 약 {N['priced']}%</p><p><b>3·4 공급망 위치</b> {e(c['layer'])}</p>"
    vr = [("① 공급망 지위", v["pos"]), ("③ 생산 능력", v["capa"]), ("④ 재무", v["fin"]), ("⑤ 희석", v["dil"]), ("⑥ 경영진·실행", v["mgmt"]), ("⑦ 지정학·규제", v["geo"]), ("⑧ 밸류에이션", v["val"])]
    s10 += "<h3>5 회사 검증 8항목</h3><table>" + f"<tr><td style='width:20%'><b>② 고객 검증</b></td><td><b>{e(v['grade'])}등급</b> — {e(v['grade_why'])}</td></tr>" + "".join(
        f"<tr><td><b>{n}</b></td><td>{KT(x[1])} {e(x[0])}</td></tr>" for n, x in vr) + "</table><p class='sm'>등급: A 공식 고객·장기 공급·반복 매출 / B 이름 비공개 대형 고객 확인 / C 구조상 가능 / D 협약·시험 / E 소문</p>"
    s10 += "<h3>검증된 공식 (우리 백테스트로 확인한 것만)</h3><ul>" + "".join(f"<li><b class='{'up' if f['ok'] else 'dn'}'>{'✔' if f['ok'] else '✘'}</b> {e(f['t'])} <span class='sm'>— {e(f['why'])}</span></li>" for f in m.get("formulas", [])) + "</ul>"
    s10 += f"<p><b>7 분류 · {e(c['cls'])}</b></p><p class='up'>좋은 투자가 되는 조건 — {e(c['good_if'])}</p><p class='dn'>가설이 무너지는 조건 — {e(c['break_if'])}</p>"
    b += sec("10", "우리 분석법으로 검증", s10, G, seen, long=True)
    # ---------- 11 결론 ----------
    concl = Dp.get("concl") or [f"{A.get('edge', c['name'])}.", f"지금 위치는 '{c['cls']}'. 좋은 투자가 되려면: {c['good_if']}", f"이런 일이 보이면 가설을 접어요: {c['break_if']}"]
    s11 = "<div class='concl'>" + "".join(f"<p>{e(x)}</p>" for x in concl) + "</div>"
    s11 += "<h3>내가 틀릴 수 있는 이유</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in (Dp.get("counter") or [f"최고 시나리오의 재평가 조건이 빨리 충족될 수 있음: {B['rerate']}"])) + "</ul>"
    s11 += "<p class='sm'>손절은 산 가격의 최대 −7%. 조건이 확인되기 전에는 분할·소액 — 수익보다 손실 최소화가 먼저.</p>"
    b += sec("11", f"결론 — 그래서 {c['name']}는?", s11, G, seen)
    # ---------- 12 한계 ----------
    ck = [("사업 정의·매출원", bool(A)), ("부문별 매출 구조", bool(Dp.get("money"))), ("기술·경쟁력 설명", bool(Dp.get("tech"))), ("동종 비교", len(peers) > 1),
          ("분기 재무 추세", bool(Q)), ("역산 밸류에이션", bool(ttm and mc)), ("확인 일정·추적 지표", bool(Dp.get("catalysts"))), ("리스크 표", bool(Dp.get("risks"))),
          ("반대 논리", bool(Dp.get("counter"))), ("확인 못 한 것 목록", bool(Dp.get("unknowns"))),
          ("경영진 심층 평가(이력·보상·내부자 매매)", bool(Dp.get("mgmt_deep")))]
    s12 = "<h3>스스로 점검 — 이 분석표가 충분한가?</h3><ul class='ck'>" + "".join(f"<li><span class='{'y' if ok else 'n'}'>{'✔' if ok else '△'}</span> {e(n)}{'' if ok else ' — 아직 부족 (자동 항목·한 줄 평가로 대체)'}</li>" for n, ok in ck) + "</ul>"
    if Dp.get("unknowns"):
        s12 += "<h3>확인 못 한 것 (모름)</h3><ul>" + "".join(f"<li>{KT('모름')} {e(x)}</li>" for x in Dp["unknowns"]) + "</ul>"
    s12 += "<p class='sm'>재무표는 yfinance 분기 자료(최대 5분기)라 회사 공시와 항목 정의가 조금 다를 수 있음. 숫자는 매일 다시 계산, 문장은 리서치 날짜 기준.</p>"
    if c.get("src"):
        s12 += "<h3>출처</h3><ul class='sm'>" + "".join(f"<li>{e(x)}</li>" for x in c["src"]) + "</ul>"
    b += sec("12", "이 분석표의 한계", s12, G, seen, long=True)
    b += "<div class='foot'>투자 권유가 아니라 판단 재료입니다. 과거 검증이 미래를 보장하지 않습니다.</div>"
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{e(c['name'])} 기업 분석표</title><style>{SCSS}</style></head><body><table class='pg'><thead><tr><td></td></tr></thead><tfoot><tr><td></td></tr></tfoot><tbody><tr><td>{b}</td></tr></tbody></table></body></html>"


def run(keys=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page()
        for f in sorted(D.glob("*.json")):
            if f.name == "index.json" or (keys and f.stem not in keys):
                continue
            R = json.loads(f.read_text()); od = OUT / f.stem; od.mkdir(parents=True, exist_ok=True)
            jobs = [("industry", industry(R))] + [(c["t"], company(R, c)) for c in R["companies"]]
            for name, h in jobs:
                pg.set_content(h, wait_until="load"); pg.pdf(path=str(od / f"{name}.pdf"), format="A4", print_background=True)
            print("장기 리서치 PDF:", f.stem, len(jobs), "개")
        br.close()


if __name__ == "__main__":
    run(sys.argv[1:] or None)
