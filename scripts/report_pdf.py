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


def curve_svg(series, w=560, h=170, unit="$"):
    """[(이름, 색, [[날짜, 값], ...])] → 선 그래프 (격자·끝값 라벨·영역)"""
    pts = [v for _, _, s_ in series for _, v in s_]
    if len(pts) < 2 or max(len(s_) for _, _, s_ in series) < 2:
        return "<p class='small muted'>곡선은 이틀 이상 쌓이면 그려져요.</p>"
    lo, hi = min(pts), max(pts); pad = (hi - lo) * 0.15 or hi * 0.01; lo -= pad; hi += pad
    n = max(len(s_) for _, _, s_ in series)
    L, R, T, B = 52, 90, 16, 24
    X = lambda i: L + i / max(1, n - 1) * (w - L - R)
    Y = lambda v: T + (hi - v) / (hi - lo) * (h - T - B)
    g = "".join(f"<line x1='{L}' x2='{w - R}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' class='gd'/><text x='{L - 6}' y='{Y(v) + 3:.1f}' class='ax' text-anchor='end'>{unit}{v:,.0f}</text>"
                for v in [lo + (hi - lo) * k / 4 for k in range(1, 4)])
    days = series[0][2]
    xt = "".join(f"<text x='{X(i):.1f}' y='{h - 6}' class='ax' text-anchor='middle'>{days[i][0][5:]}</text>" for i in sorted({0, len(days) - 1, len(days) // 2}))
    out = []
    for k, (nm, col, s_) in enumerate(series):
        if len(s_) < 2:
            continue
        xy = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_, v) in enumerate(s_))
        if k == 0:
            out.append(f"<polygon points='{X(0):.1f},{h - B} {xy} {X(len(s_) - 1):.1f},{h - B}' fill='{col}' opacity='.08'/>")
        out.append(f"<polyline points='{xy}' fill='none' stroke='{col}' stroke-width='{2.4 if k == 0 else 1.6}' stroke-linejoin='round'/>")
        lv = s_[-1][1]
        out.append(f"<circle cx='{X(len(s_) - 1):.1f}' cy='{Y(lv):.1f}' r='3' fill='{col}'/><rect x='{w - R + 6}' y='{Y(lv) - 8:.1f}' width='{R - 8}' height='15' rx='3' fill='{col}'/>"
                   f"<text x='{w - R + 10}' y='{Y(lv) + 3:.1f}' class='pill'>{nm[:6]} {unit}{lv:,.0f}</text>")
    return f"<svg viewBox='0 0 {w} {h}' class='curve'>{g}{xt}{''.join(out)}</svg>"


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
    rules = """<div class='box rules'><b>AI 데스크 매수 기준 (전체 규칙)</b>
      <ol class='small'>
      <li><b>Scout — 후보 찾기:</b> 추천 바구니 20, 터틀 진입·돌파 직전, 오늘 급등, 거래량 3배 급증, (장중) 개장 30분 범위 돌파·VWAP 회복·S&P 대비 +2%</li>
      <li><b>Filter — 빼기:</b> 3일 안 실적 발표, 하루 거래대금 $2,000만 미만, 주가 $5 미만, 하루 10%↑ 과열, VIX 35↑ 시장 이상</li>
      <li><b>Analyst — 0~1점, 0.6↑ 통과:</b> 추세 0.30(20·50일선 위, 50>200일선) · RSI 45~70 0.20 · MACD 0.10 · 거래량 0.10 · S&P 대비 강도 0.15 · 목표가 여력 0.10 · 사이트 신호 0.05 · 주간 성적 보정 ±0.10. 장중은 장중 신호 60% + 일봉 40%</li>
      <li><b>Risk — 크기·손절:</b> 손절 = 하루 평균 변동(N)의 2배(5~12%), 손절 시 손실 ≤ 계좌 2%로 금액 계산, 한 종목 20%·8종목·하루 신규 2개(장중 2개), 현금 20% 유지, S&P −3%면 신규 중단</li>
      <li><b>Executor — 주문:</b> 마감 회의 = 종가 −¼N 지정가(2일), 장중 = 현재가 지정가(당일), 중복 금지</li>
      <li><b>매도:</b> 손절 / 목표(손절 폭 ×2.5) / +1R 본전 손절 · +2R → +1R / +15%부터 고점 −8% 추적 / 장중 진입 실패 시 당일 정리</li></ol></div>"""
    return rules + f"""<div class='kpis'>
      <div><span>계좌</span><b>${A['eq_now']:,.0f}</b><em class='{cls(r)}'>{pct(r, 2)}</em></div>
      <div><span>같은 기간 S&P500</span><b class='{cls(b)}'>{pct(b, 2)}</b><em>차이 {pct(r - b, 2) if b is not None else '—'}</em></div>
      <div><span>끝난 거래</span><b>{m.get('n', 0)}건</b><em>{'승률 ' + pct(m['win'], 0).lstrip('+') if m.get('win') is not None else '—'}</em></div>
      <div><span>최대 낙폭</span><b>{pct(m.get('mdd'))}</b><em>현금 ${A['cash']:,.0f}</em></div></div>
      <table class='t'><thead><tr><th>보유</th><th class='num'>매수가</th><th class='num'>현재가</th><th class='num'>손익</th><th class='num'>손절</th><th class='num'>목표</th></tr></thead><tbody>{pos or "<tr><td colspan=6 class='muted'>없음</td></tr>"}</tbody></table>
      <div class='two'><div><div class='cap'>대기 주문</div><ul class='small'>{orders}</ul></div><div><div class='cap'>최근 끝난 거래</div><ul class='small'>{tr}</ul></div></div>
      <div style='break-inside:avoid'><div class='cap'>계좌 곡선 ($)</div>{curve_svg([("AI 데스크", "#3b6fd8", eqs)], h=130)}</div>
      <h3>보유 종목별 — 어디서 샀고, 어디서 팔 계획인지</h3>
      {''.join(pos_card(p) for p in A.get("pos", []))}
      {''.join(sold_card(t) for t in A.get("trades", [])[:3])}"""


def pos_card(p):
    pts = "".join(f"<li>{x}</li>" for x in plan_text(p))
    loss = p["val"] * (p["stop"] / (p["px"] or p["avg"]) - 1) if p.get("stop") and p.get("px") else None
    return (f"<div class='pcard'><div class='ph'><b>{p['sym']}</b><span class='tag'>{p.get('src') or 'Claude 직접'}</span>"
            f"<span class='muted'>{p['since']} 매수 ${p['avg']:,.2f} → 지금 ${(p['px'] or 0):,.2f}</span><b class='big {cls(p['pl'])}'>{pct(p['pl'])}</b></div>"
            f"{pos_chart(p['sym'], p['since'], p['avg'], p.get('stop'), p.get('target'))}"
            f"<div class='two'><div><div class='cap'>왜 샀나 — 매수 근거</div><p class='small'>{p.get('why') or '—'}</p>{entry_check(p['sym'], p['since'])}</div>"
            f"<div><div class='cap'>어디서 팔 계획인지</div><ul class='small'>{pts}</ul>"
            f"<div class='risk'>지금 손절에 걸리면 <b>{'$' + format(abs(loss), ',.0f') if loss is not None else '—'}</b> 손실 · 계좌의 <b>{pct(abs(loss) / 10000) .lstrip('+') if loss is not None else '—'}</b></div></div></div></div>")


def sold_card(t):
    return (f"<div class='pcard'><div class='ph'><b>{t['sym']}</b><span class='tag'>끝난 거래</span><span class='muted'>{t['in']} → {t['out']} · {t['why']}</span><b class='big {cls(t['pl'])}'>{pct(t['pl'])}</b></div>"
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
    lab = {"basket": ("바구니", "#3b6fd8"), "turtle": ("터틀", "#f0a43a"), "spy": ("S&P500", "#8a8f98")}
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


def pos_chart(sym, buy_day, buy_px, stop=None, target=None, sell_day=None, sell_px=None, w=600, h=200):
    """종가(영역) + 20·50일선 + 매수▲·매도▼ + 손실 구간(빨강)·이익 구간(초록) + 손절·목표 라벨"""
    b = bars(sym)
    if len(b) < 30:
        return "<p class='small muted'>그래프 자료가 부족해요.</p>"
    c = [v for _, v in b]
    ma = lambda k: [sum(c[i - k + 1:i + 1]) / k if i >= k - 1 else None for i in range(len(c))]
    m20, m50 = ma(20), ma(50)
    K = 90
    b, c, m20, m50 = b[-K:], c[-K:], m20[-K:], m50[-K:]
    days = [d for d, _ in b]
    lv = c + [x for x in (stop, target, buy_px, sell_px) if x]
    lo, hi = min(lv), max(lv); pad = (hi - lo) * 0.08; lo -= pad; hi += pad
    L, R, T, B = 50, 92, 12, 22
    X = lambda i: L + i / (len(c) - 1) * (w - L - R)
    Y = lambda v: T + (hi - v) / (hi - lo) * (h - T - B)
    def idx(day):
        return next((k for k, d in enumerate(days) if d >= day), len(days) - 1)
    bi = idx(buy_day); ei = idx(sell_day) if sell_day else len(c) - 1
    out = []
    # 위험·보상 구간 (매수 시점부터)
    if stop and stop < buy_px:
        out.append(f"<rect x='{X(bi):.1f}' y='{Y(buy_px):.1f}' width='{X(ei) - X(bi) + 4:.1f}' height='{Y(stop) - Y(buy_px):.1f}' fill='#e5484d' opacity='.10'/>")
    if target:
        out.append(f"<rect x='{X(bi):.1f}' y='{Y(target):.1f}' width='{X(ei) - X(bi) + 4:.1f}' height='{Y(buy_px) - Y(target):.1f}' fill='#2fa36b' opacity='.10'/>")
    # 격자
    for k in range(1, 4):
        v = lo + (hi - lo) * k / 4
        out.append(f"<line x1='{L}' x2='{w - R}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' class='gd'/><text x='{L - 6}' y='{Y(v) + 3:.1f}' class='ax' text-anchor='end'>{v:,.0f}</text>")
    for i in range(0, len(days), 21):
        out.append(f"<text x='{X(i):.1f}' y='{h - 6}' class='ax' text-anchor='middle'>{days[i][5:]}</text>")
    pl = lambda arr, col, wd: "<polyline points='" + " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(arr) if v) + f"' fill='none' stroke='{col}' stroke-width='{wd}' stroke-linejoin='round'/>"
    xy = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(c))
    out.append(f"<polygon points='{X(0):.1f},{h - B} {xy} {X(len(c) - 1):.1f},{h - B}' fill='#3b6fd8' opacity='.07'/>")
    out += [pl(m50, "#f0a43a", 1.3), pl(m20, "#8e6cf0", 1.3), pl(c, "#1b2a4a", 2)]
    def hl(v, col, lab):
        return (f"<line x1='{L}' x2='{w - R}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' stroke='{col}' stroke-dasharray='5 3' stroke-width='1.3'/>"
                f"<rect x='{w - R + 4}' y='{Y(v) - 8:.1f}' width='{R - 6}' height='15' rx='3' fill='{col}'/><text x='{w - R + 8}' y='{Y(v) + 3:.1f}' class='pill'>{lab} {v:,.2f}</text>")
    if stop: out.append(hl(stop, "#e5484d", "손절"))
    if target: out.append(hl(target, "#2fa36b", "목표"))
    out.append(f"<rect x='{w - R + 4}' y='{Y(c[-1]) - 8:.1f}' width='{R - 6}' height='15' rx='3' fill='#1b2a4a'/><text x='{w - R + 8}' y='{Y(c[-1]) + 3:.1f}' class='pill'>지금 {c[-1]:,.2f}</text>")
    def mk(i, px, up, lab):
        x, y = X(i), Y(px); col = "#3b6fd8" if up else "#e5484d"
        tri = f"{x - 6},{y + 13} {x + 6},{y + 13} {x},{y + 4}" if up else f"{x - 6},{y - 13} {x + 6},{y - 13} {x},{y - 4}"
        return (f"<line x1='{x:.1f}' x2='{x:.1f}' y1='{T}' y2='{h - B}' stroke='{col}' stroke-width='.8' stroke-dasharray='2 3'/><polygon points='{tri}' fill='{col}'/>"
                f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3' fill='#fff' stroke='{col}' stroke-width='2'/><text x='{x - 9:.1f}' y='{y + (24 if up else -18):.1f}' class='lb' fill='{col}' text-anchor='end'>{lab} {px:,.2f} · {days[i][5:]}</text>")
    out.append(mk(bi, buy_px, True, "매수"))
    if sell_day and sell_px: out.append(mk(ei, sell_px, False, "매도"))
    leg = (f"<text x='{L}' y='{T - 2}' class='lg'><tspan fill='#1b2a4a'>━ 종가</tspan>   <tspan fill='#8e6cf0'>━ 20일선</tspan>   <tspan fill='#f0a43a'>━ 50일선</tspan>"
           f"   <tspan fill='#e5484d'>■ 손실 구간</tspan>   <tspan fill='#2fa36b'>■ 이익 구간</tspan></text>")
    return f"<svg viewBox='0 0 {w} {h}' class='curve'>{leg}{''.join(out)}</svg>"


def entry_check(sym, day):
    """매수 직전 날 기준 지표 → Analyst 기준과 대조한 체크리스트"""
    b = bars(sym, "2y"); sp = bars("SPY", "2y")
    if len(b) < 60:
        return ""
    i = max(k for k, (d, _) in enumerate(b) if d < day) if any(d < day for d, _ in b) else len(b) - 1
    c = [v for _, v in b[:i + 1]]
    ma = lambda k: sum(c[-k:]) / k if len(c) >= k else None
    m20, m50, m200 = ma(20), ma(50), ma(200)
    d = [c[k] - c[k - 1] for k in range(len(c) - 14, len(c))]
    up = sum(x for x in d if x > 0) / 14; dn = -sum(x for x in d if x < 0) / 14
    rsi = 100 - 100 / (1 + up / dn) if dn else 100
    r20 = c[-1] / c[-21] - 1
    spc = [v for dd, v in sp if dd <= b[i][0]]
    rs = r20 - (spc[-1] / spc[-21] - 1) if len(spc) > 21 else None
    pf = j(f"profile/{sym}.json") or {}
    tg = (pf.get("analyst") or {}).get("mean"); ups = tg / c[-1] - 1 if tg else None
    nx = (pf.get("earn") or {}).get("next")
    rows = [
        ("종가 > 20일선", f"{c[-1]:,.2f} vs {m20:,.2f}" if m20 else "—", m20 and c[-1] > m20, "단기 추세가 위"),
        ("종가 > 50일선", f"{c[-1]:,.2f} vs {m50:,.2f}" if m50 else "—", m50 and c[-1] > m50, "중기 추세가 위"),
        ("50일선 > 200일선", f"{m50:,.2f} vs {m200:,.2f}" if m200 else "자료 부족", m200 and m50 > m200, "장기 상승장 (골든크로스 상태)"),
        ("RSI 45~70", f"{rsi:.0f}", 45 <= rsi <= 70, "너무 과열(70↑)도, 약세(45↓)도 아닌 구간"),
        ("S&P500보다 강함 (20일)", pct(rs) if rs is not None else "—", rs is not None and rs > 0, "시장 대비 상대 강도"),
        ("애널리스트 목표가 여력", pct(ups, 0) if ups is not None else "—", ups is not None and ups > 0.15, "평균 목표가가 15% 이상 위면 만점"),
        ("실적 발표 3일 이내 아님", nx or "—", True, "발표 직전엔 갭 위험 → Filter가 제외"),
    ]
    tr = "".join(f"<tr><td>{'<b class=ok>✔</b>' if ok else '<b class=no>✘</b>'} {k}</td><td class='num'>{v}</td><td class='muted'>{w_}</td></tr>" for k, v, ok, w_ in rows)
    n_ok = sum(1 for r in rows if r[2])
    return f"<div class='cap'>매수 직전({b[i][0]}) 기준 체크 — {n_ok}/{len(rows)} 통과</div><table class='t ck'>{tr}</table>"


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
h2 { font-size: 14.5pt; margin: 20px 0 8px; padding: 6px 0 0; border-top: 3px solid #1b2a4a; color: #1b2a4a; break-after: avoid; }
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
.gd { stroke: #edf0f4; stroke-width: 1; }
.curve .pill { font-size: 8.5px; font-weight: 700; fill: #fff; }
.curve .ax { font-size: 8.5px; fill: #8a8f98; }
.curve .lg { font-size: 8.5px; font-weight: 600; }
.pcard .two { grid-template-columns: 1.25fr 1fr; gap: 12px; } .pcard p.small { margin: 2px 0 6px; line-height: 1.5; }
.pcard { border: 1px solid #e3e7ee; border-radius: 10px; padding: 8px 12px 10px; margin: 10px 0; break-inside: avoid; box-shadow: 0 1px 0 #f2f4f7; }
.ph { display: flex; align-items: baseline; gap: 8px; font-size: 11pt; margin-bottom: 4px; }
.ph .big { margin-left: auto; font-size: 13pt; }
.tag { font-size: 7.5pt; background: #eef2fb; color: #3b6fd8; border-radius: 99px; padding: 1px 7px; font-weight: 700; }
.ck td { padding: 1px 5px; font-size: 8pt; line-height: 1.35; } .ck td:first-child { white-space: nowrap; } .ck td:last-child { font-size: 7.5pt; } .ok { color: #2fa36b; } .no { color: #e5484d; }
.risk { margin-top: 6px; background: #fff3f3; border: 1px solid #f6d3d4; color: #8f2a2e; border-radius: 6px; padding: 5px 9px; font-size: 8.8pt; }
.rules ol { margin: 4px 0 0; padding-left: 18px; } .rules li { margin: 3px 0; }
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
