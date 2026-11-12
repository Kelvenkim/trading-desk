"""
일일 보고서 PDF — 표지(K 로고 · N일차) + 숫자 표·그래프(자료에서 자동) + Claude가 쓴 해설(마크다운)
  python scripts/report_pdf.py data/us/reports/2026-11-12_note.md   → reports/pdf/2026-11-12_N일차.pdf
  해설 마크다운은 '## 제목' 단위로 섹션을 나눔. 아래 이름의 섹션 뒤에 자동 표가 붙음:
    '시장' → 지수·자산 표 + 섹터 막대, 'AI 데스크' → 계좌·보유 표, '순위' → 채점 표, '모의 투자' → 3계좌 표
"""
import json, re, sys
from datetime import date, timedelta
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us"
OUT = ROOT / "reports/pdf"
START = date(2026, 11, 9)             # 1일차 = 11/9 미국장
HOL = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15"}


def j(p, d=None):
    try:
        return json.loads((D / p).read_text())
    except Exception:
        return d


def day_n(d):
    n, x = 0, START
    while x <= d:
        if x.weekday() < 5 and x.isoformat() not in HOL:
            n += 1
        x += timedelta(days=1)
    return n


def pct(v, d=1):
    return "—" if v is None else f"{'+' if v > 0 else ''}{v * 100:.{d}f}%"


def cls(v):
    return "" if not v else "up" if v > 0 else "down"


def market_block():
    m = j("market.json", {})
    rows = "".join(f"<tr><td>{a['name']}</td><td class='num'>{a['last']:,.2f}</td><td class='num {cls(a['d1'])}'>{pct(a['d1'], 2)}</td>"
                   f"<td class='num {cls(a.get('m1'))}'>{pct(a.get('m1'))}</td><td class='num {cls(a.get('ytd'))}'>{pct(a.get('ytd'))}</td></tr>" for a in m.get("assets", []))
    sec = sorted(m.get("sectors", []), key=lambda s: -s["d1"])
    mx = max([abs(s["d1"]) for s in sec] or [0.01]) or 0.01
    bars = "".join(f"<div class='sb'><span class='sn'>{s['name']}</span><div class='st'><i class='{'pos' if s['d1'] >= 0 else 'neg'}' style='width:{abs(s['d1']) / mx * 100:.0f}%'></i></div>"
                   f"<span class='num {cls(s['d1'])}'>{pct(s['d1'])}</span></div>" for s in sec)
    b = m.get("breadth") or {}; g = m.get("regime") or {}
    return f"""<div class='two'><table class='t'><thead><tr><th>지수·자산</th><th class='num'>종가</th><th class='num'>하루</th><th class='num'>1달</th><th class='num'>올해</th></tr></thead><tbody>{rows}</tbody></table>
      <div><div class='cap'>섹터 (하루)</div>{bars}
      <div class='cap' style='margin-top:10px'>시장 체력</div>
      <p class='small'>S&P500 200일선 대비 {pct(g.get('sp_vs200'))} · 오른 종목 {b.get('adv', '—')} / 내린 종목 {b.get('dec', '—')} · 50일선 위 {pct(b.get('above50'), 0).lstrip('+')} · 52주 신고가 {b.get('hi52', '—')} / 신저가 {b.get('lo52', '—')}</p></div></div>"""


def curve_svg(series, w=520, h=150):
    """[(이름, 색, [[날짜, 값], ...])] → 간단한 선 그래프"""
    pts = [v for _, _, s in series for _, v in s]
    if len(pts) < 2:
        return "<p class='small muted'>곡선은 며칠 쌓인 뒤에 그려져요.</p>"
    lo, hi = min(pts), max(pts); hi = hi if hi > lo else lo + 1
    n = max(len(s) for _, _, s in series)
    out = []
    for nm, col, s in series:
        if len(s) < 2:
            continue
        xy = " ".join(f"{i / (n - 1) * (w - 60) + 50:.1f},{h - 20 - (v - lo) / (hi - lo) * (h - 40):.1f}" for i, (_, v) in enumerate(s))
        out.append(f"<polyline points='{xy}' fill='none' stroke='{col}' stroke-width='2'/>")
    leg = " ".join(f"<tspan fill='{c}'>■</tspan> {n_}" for n_, c, _ in series)
    return (f"<svg viewBox='0 0 {w} {h}' class='curve'><text x='50' y='12' class='lg'>{leg}</text>"
            f"<text x='2' y='{24}' class='ax'>{hi:,.0f}</text><text x='2' y='{h - 18}' class='ax'>{lo:,.0f}</text>"
            f"<line x1='50' y1='{h - 20}' x2='{w - 10}' y2='{h - 20}' stroke='#ddd'/>{''.join(out)}</svg>")


def desk_block():
    A = j("ai_paper.json", {})
    if not A:
        return ""
    m = A.get("stats", {}); r = A["eq_now"] / A["cash0"] - 1; b = A.get("bench")
    pos = "".join(f"<tr><td>{p['sym']}</td><td class='num'>${p['avg']:,.2f}</td><td class='num'>${(p['px'] or 0):,.2f}</td><td class='num {cls(p['pl'])}'>{pct(p['pl'])}</td>"
                  f"<td class='num'>${p['stop'] or 0:,.2f}</td><td class='num'>{'$' + format(p['target'], ',.2f') if p.get('target') else '추적'}</td></tr>" for p in A.get("pos", []))
    orders = "".join(f"<li>{o['desc']}</li>" for o in A.get("orders", [])) or "<li class='muted'>없음</li>"
    tr = "".join(f"<li>{t['sym']} <b class='{cls(t['pl'])}'>{pct(t['pl'])}</b> · {t['in'][5:]}→{t['out'][5:]} · {t['why']}</li>" for t in A.get("trades", [])[:8]) or "<li class='muted'>아직 없음</li>"
    eqs = [[d, v] for d, v in A.get("eq", [])]
    return f"""<div class='kpis'>
      <div><span>계좌</span><b>${A['eq_now']:,.0f}</b><em class='{cls(r)}'>{pct(r, 2)}</em></div>
      <div><span>같은 기간 S&P500</span><b class='{cls(b)}'>{pct(b, 2)}</b><em>차이 {pct(r - b, 2) if b is not None else '—'}</em></div>
      <div><span>끝난 거래</span><b>{m.get('n', 0)}건</b><em>{'승률 ' + pct(m['win'], 0).lstrip('+') if m.get('win') is not None else '—'}</em></div>
      <div><span>최대 낙폭</span><b>{pct(m.get('mdd'))}</b><em>현금 ${A['cash']:,.0f}</em></div></div>
      <table class='t'><thead><tr><th>보유</th><th class='num'>매수가</th><th class='num'>현재가</th><th class='num'>손익</th><th class='num'>손절</th><th class='num'>목표</th></tr></thead><tbody>{pos or "<tr><td colspan=6 class='muted'>없음</td></tr>"}</tbody></table>
      <div class='two'><div><div class='cap'>대기 주문</div><ul class='small'>{orders}</ul></div><div><div class='cap'>최근 끝난 거래</div><ul class='small'>{tr}</ul></div></div>
      {curve_svg([("AI 데스크 계좌", "#111", eqs)])}
      <h3>보유 종목별 — 어디서 샀고, 어디서 팔 계획인지</h3>
      {''.join(pos_card(p) for p in A.get("pos", []))}
      {''.join(sold_card(t) for t in A.get("trades", [])[:3])}"""


def pos_card(p):
    pts = "".join(f"<li>{x}</li>" for x in plan_text(p))
    return (f"<div class='pcard'><div class='ph'><b>{p['sym']}</b> <span class='muted'>{p['since']} 매수 ${p['avg']:,.2f} → 지금 ${(p['px'] or 0):,.2f}</span> <b class='{cls(p['pl'])}'>{pct(p['pl'])}</b></div>"
            f"{pos_chart(p['sym'], p['since'], p['avg'], p.get('stop'), p.get('target'))}"
            f"<div class='two'><div><div class='cap'>왜 샀나 (매수 근거)</div><p class='small'>{p.get('why') or '—'}</p></div>"
            f"<div><div class='cap'>매도 계획</div><ul class='small'>{pts}</ul></div></div></div>")


def sold_card(t):
    return (f"<div class='pcard'><div class='ph'><b>{t['sym']}</b> <span class='muted'>끝난 거래 {t['in']} → {t['out']}</span> <b class='{cls(t['pl'])}'>{pct(t['pl'])}</b> <span class='muted'>· {t['why']}</span></div>"
            f"{pos_chart(t['sym'], t['in'], t['avg'], sell_day=t['out'], sell_px=t['px'])}"
            f"<p class='small'><b>매수 근거:</b> {t.get('entry_why') or '—'}</p></div>")


def rank_block():
    R = j("rank_report.json", {}); V = R.get("variants", {})
    nm = {"td": "추천 바구니", "t": "테마 눌림", "m": "12-1 모멘텀", "o": "우리 점수"}
    def c(k, h):
        x = (V.get(k) or {}).get(h)
        return f"<td class='num {cls(x['ex'])}'>{pct(x['ex'], 2)} <span class='muted'>({x['n']}번)</span></td>" if x else "<td class='num muted'>—</td>"
    rows = "".join(f"<tr><td>{v}</td>{c(k, '1')}{c(k, '5')}{c(k, '20')}</tr>" for k, v in nm.items())
    return f"<table class='t'><thead><tr><th>방식 (상위 20 − 전체 평균)</th><th class='num'>1일</th><th class='num'>5일</th><th class='num'>20일</th></tr></thead><tbody>{rows}</tbody></table>"


def paper_block():
    P = j("paper.json")
    if not P:
        return ""
    lab = {"basket": ("추천 바구니", "#111"), "turtle": ("터틀", "#3d6fd8"), "spy": ("S&P500 보유", "#999")}
    rows = ""
    for k, (n_, _) in lab.items():
        e = P["acct"][k]["eq"]; v = e[-1][1]; d1 = v / e[-2][1] - 1 if len(e) > 1 else None
        rows += f"<tr><td>{n_}</td><td class='num'>${v:,.0f}</td><td class='num {cls(v / P['cash0'] - 1)}'>{pct(v / P['cash0'] - 1, 2)}</td><td class='num {cls(d1)}'>{pct(d1, 2)}</td><td class='num'>{len(P['acct'][k]['pos'])}</td></tr>"
    return (f"<table class='t'><thead><tr><th>계좌 ($10,000 시작, {P['start']}~)</th><th class='num'>평가액</th><th class='num'>누적</th><th class='num'>하루</th><th class='num'>보유</th></tr></thead><tbody>{rows}</tbody></table>"
            + curve_svg([(n_, c, P["acct"][k]["eq"]) for k, (n_, c) in lab.items()]))


def bars(sym, period="6mo"):
    try:
        import yfinance as yf
        h = yf.Ticker(sym).history(period=period, interval="1d").dropna(subset=["Close"])
        return [(ix.strftime("%Y-%m-%d"), float(r.Close)) for ix, r in h.iterrows()]
    except Exception:
        return []


def pos_chart(sym, buy_day, buy_px, stop=None, target=None, sell_day=None, sell_px=None, w=520, h=190):
    """종가 그래프 + 매수 지점(▲) · 매도 지점(▼) · 손절선(빨강) · 목표선(초록) · 20·50일선"""
    b = bars(sym)
    if len(b) < 30:
        return "<p class='small muted'>그래프 자료가 부족해요.</p>"
    c = [v for _, v in b]
    ma = lambda k: [sum(c[max(0, i - k + 1):i + 1]) / min(k, i + 1) if i >= k - 1 else None for i in range(len(c))]
    m20, m50 = ma(20), ma(50)
    b = b[-90:]; c = c[-90:]; m20 = m20[-90:]; m50 = m50[-90:]
    lv = [v for v in c] + [x for x in (stop, target, buy_px, sell_px) if x]
    lo, hi = min(lv) * 0.98, max(lv) * 1.02
    X = lambda i: 46 + i / (len(c) - 1) * (w - 110)
    Y = lambda v: 10 + (hi - v) / (hi - lo) * (h - 34)
    line = lambda arr, col, wd, dash="": "<polyline points='" + " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(arr) if v) + f"' fill='none' stroke='{col}' stroke-width='{wd}' {dash}/>"
    out = [line(m50, "#c9c9c9", 1), line(m20, "#9db4e8", 1), line(c, "#111", 1.6)]
    def hl(v, col, lab):
        return (f"<line x1='46' x2='{w - 64}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' stroke='{col}' stroke-dasharray='4 3' stroke-width='1.2'/>"
                f"<text x='{w - 60}' y='{Y(v) + 3:.1f}' class='lb' fill='{col}'>{lab} {v:,.2f}</text>")
    if stop: out.append(hl(stop, "#d9363e", "손절"))
    if target: out.append(hl(target, "#1f9d55", "목표"))
    days = [d for d, _ in b]
    def mk(day, px, up, lab):
        i = next((k for k, d in enumerate(days) if d >= day), len(days) - 1)
        x, y = X(i), Y(px)
        tri = f"{x - 5},{y + 11} {x + 5},{y + 11} {x},{y + 3}" if up else f"{x - 5},{y - 11} {x + 5},{y - 11} {x},{y - 3}"
        col = "#1d5fd6" if up else "#d9363e"
        return (f"<polygon points='{tri}' fill='{col}'/><circle cx='{x}' cy='{y}' r='2.5' fill='{col}'/>"
                f"<text x='{x - 9}' y='{y + (20 if up else -14):.1f}' class='lb' fill='{col}' text-anchor='end'>{lab} {px:,.2f} ({day[5:]})</text>")
    out.append(mk(buy_day, buy_px, True, "매수"))
    if sell_day and sell_px: out.append(mk(sell_day, sell_px, False, "매도"))
    ticks = "".join(f"<text x='{X(i):.1f}' y='{h - 6}' class='ax' text-anchor='middle'>{days[i][5:]}</text>" for i in range(0, len(days), 15))
    yt = "".join(f"<text x='2' y='{Y(v) + 3:.1f}' class='ax'>{v:,.0f}</text>" for v in (hi / 1.02, (hi + lo) / 2, lo / 0.98))
    return (f"<svg viewBox='0 0 {w} {h}' class='curve'>{yt}{ticks}{''.join(out)}"
            f"<text x='50' y='{h - 18}' class='lg'><tspan fill='#111'>━ 종가</tspan>  <tspan fill='#9db4e8'>━ 20일선</tspan>  <tspan fill='#c9c9c9'>━ 50일선</tspan></text></svg>")


def plan_text(p):
    avg, st = p["avg"], p.get("stop")
    out = []
    if st:
        out.append(f"손절 ${st:,.2f} ({st / avg - 1:+.1%}) — 여기 닿으면 전량 매도")
    if p.get("target"):
        out.append(f"목표 ${p['target']:,.2f} ({p['target'] / avg - 1:+.1%}) — 닿으면 전량 매도")
    else:
        out.append("목표가 없음 — 오르는 동안 계속 보유")
    if st and st < avg:
        R = avg - st
        out.append(f"+{R / avg:.1%}(1R) 오르면 손절을 본전으로, +{2 * R / avg:.1%}(2R)면 +{R / avg:.1%}로 올림")
    elif st and st >= avg:
        out.append("이미 손절이 본전 이상 — 최악이어도 손해 없음")
    out.append("+15%부터는 고점 대비 −8% 추적 손절")
    return out


AUTO = [("시장", market_block), ("AI 데스크", desk_block), ("순위", rank_block), ("모의 투자", paper_block)]

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
@page :first { margin: 0; }
* { box-sizing: border-box; }
body { font-family: 'Noto Sans CJK KR', 'Noto Sans KR', sans-serif; color: #111; font-size: 10.5pt; line-height: 1.65; margin: 0; }
.cover { height: 296mm; background: #000; color: #fff; margin: 0; padding: 38mm 22mm 20mm; display: flex; flex-direction: column; page-break-after: always; }
.brand { font-size: 12pt; font-weight: 800; letter-spacing: .3em; color: #888; border-bottom: 1px solid #333; padding-bottom: 5mm; }
.cover h1 { font-size: 40pt; line-height: 1.15; margin: 60mm 0 4mm; font-weight: 900; }
.cover .dayn { font-size: 15pt; color: #bbb; }
.cover .meta { margin-top: auto; color: #999; font-size: 9.5pt; border-top: 1px solid #333; padding-top: 6mm; display: flex; justify-content: space-between; }
.cover .hl { margin-top: 14mm; font-size: 12pt; color: #ddd; max-width: 150mm; }
.hdr { display: flex; align-items: center; gap: 8px; font-size: 8.5pt; color: #888; border-bottom: 1px solid #eee; padding-bottom: 6px; margin-bottom: 10px; }
.hdr svg { width: 14px; height: 14px; } .hdr rect:first-child { fill: #000; } .hdr rect:not(:first-child), .hdr path { fill: #fff; stroke: #fff; }
h2 { font-size: 14pt; margin: 18px 0 8px; padding-top: 4px; border-top: 2px solid #000; break-after: avoid; }
h3 { font-size: 11pt; margin: 12px 0 4px; break-after: avoid; }
p { margin: 4px 0 8px; } ul { margin: 4px 0 8px; padding-left: 18px; } li { margin: 2px 0; }
a { color: #1d4fd6; text-decoration: none; }
.t { width: 100%; border-collapse: collapse; font-size: 9pt; margin: 6px 0 10px; break-inside: avoid; }
.t th { text-align: left; font-weight: 600; color: #666; border-bottom: 1px solid #ccc; padding: 4px 6px; }
.t td { padding: 4px 6px; border-bottom: 1px solid #f0f0f0; }
.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.up { color: #d9363e; } .down { color: #1d5fd6; } .muted { color: #999; } .small { font-size: 9pt; }
.two { display: grid; grid-template-columns: 1.15fr 1fr; gap: 14px; break-inside: avoid; }
.cap { font-size: 8.5pt; font-weight: 700; color: #666; margin: 4px 0; }
.sb { display: grid; grid-template-columns: 62px 1fr 48px; gap: 6px; align-items: center; font-size: 8.5pt; margin: 2px 0; }
.st { height: 8px; background: #f2f2f2; border-radius: 2px; overflow: hidden; } .st i { display: block; height: 100%; }
.st i.pos { background: #d9363e; } .st i.neg { background: #1d5fd6; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 6px 0 10px; break-inside: avoid; }
.kpis div { border: 1px solid #e5e5e5; border-radius: 6px; padding: 7px 10px; display: grid; }
.kpis span { font-size: 8pt; color: #888; } .kpis b { font-size: 13pt; } .kpis em { font-style: normal; font-size: 8.5pt; color: #666; }
.curve { width: 100%; height: auto; margin: 4px 0 8px; } .curve .lg { font-size: 9px; fill: #555; } .curve .ax { font-size: 8px; fill: #999; }
blockquote { margin: 6px 0; padding: 6px 12px; border-left: 3px solid #000; background: #f7f7f7; }
.pcard { border: 1px solid #e5e5e5; border-radius: 8px; padding: 8px 12px; margin: 10px 0; break-inside: avoid; }
.ph { font-size: 10.5pt; margin-bottom: 2px; }
.curve .lb { font-size: 8.5px; font-weight: 700; }
.box { border: 1px solid #ddd; background: #fafafa; border-radius: 6px; padding: 8px 12px; margin: 8px 0; break-inside: avoid; }
.foot { margin-top: 18px; font-size: 8pt; color: #999; border-top: 1px solid #eee; padding-top: 6px; }
"""


def build(note_path):
    note = Path(note_path).read_text()
    m = re.match(r"^---\n(.*?)\n---\n", note, re.S)
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", m.group(1), re.M)) if m else {}
    body = note[m.end():] if m else note
    mday = date.fromisoformat(meta.get("market_date") or j("rank.json", {}).get("date"))
    n = day_n(mday)
    kind = meta.get("kind", "일일")
    parts = re.split(r"(?m)^## ", body)
    secs = []
    for p_ in parts:
        if not p_.strip():
            continue
        title, _, txt = p_.partition("\n")
        html = markdown.markdown(txt, extensions=["tables"])
        for key, fn in AUTO:
            if key in title:
                html += fn()
        secs.append(f"<h2>{title.strip()}</h2>{html}")
    hdr = f"<div class='hdr'>K Trading Desk · {n}일차 {kind} 보고서 · {mday}</div>"
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
      <section class="cover"><div class="brand">K TRADING DESK</div>
        <h1>{kind} 보고서</h1><div class="dayn">{n}일차 · 미국장 {mday.strftime('%Y년 %m월 %d일')} ({'월화수목금'[mday.weekday()]})</div>
        <div class="hl">{meta.get('headline', '')}</div>
        <div class="meta"><span>작성 Claude (AI 데스크 총괄)</span><span>참고용 · 투자 권유 아님</span></div></section>
      {hdr}{''.join(secs)}
      <div class="foot">자료: Yahoo Finance, Google 뉴스, 사이트 자체 계산 · 가상 계좌(모의 투자·AI 데스크)는 실제 돈이 아니에요 · 숫자는 참고용이며 투자 권유가 아니에요.</div>
    </body></html>"""
    OUT.mkdir(parents=True, exist_ok=True)
    hp = OUT / f"{mday}_{n}일차.html"; pp = OUT / f"{mday}_{n}일차_{kind}보고서.pdf"
    hp.write_text(html)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page()
        pg.goto(hp.resolve().as_uri()); pg.wait_for_timeout(300)
        pg.pdf(path=str(pp), format="A4", print_background=True, prefer_css_page_size=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template="<div style='font-size:7px;color:#999;width:100%;text-align:center'><span class='pageNumber'></span> / <span class='totalPages'></span></div>")
        b.close()
    hp.unlink()
    print(pp)
    return pp


if __name__ == "__main__":
    build(sys.argv[1])
