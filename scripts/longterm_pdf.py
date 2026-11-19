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
KC = {"사실": "#1a7f45", "추정": "#b26a00", "모름": "#777"}
tag = lambda k: f'<span class="k" style="color:{KC.get(k, "#333")};border-color:{KC.get(k, "#333")}">{e(k)}</span>'
item = lambda x: f"<li>{tag(x[1])} {e(x[0])}</li>"


def big(v, cur="USD"):
    if v is None:
        return "—"
    s = {"JPY": "¥", "GBp": "£"}.get(cur, "$"); v = v / 100 if cur == "GBp" else v
    return f"{s}{v / 1e12:.2f}조" if v >= 1e12 else f"{s}{v / 1e8:.1f}억" if v >= 1e8 else f"{s}{v / 1e4:,.0f}만" if v >= 1e4 else f"{s}{v:,.0f}"


CSS = """
@page { size: A4; margin: 14mm 13mm; }
body { font-family: 'Noto Sans CJK KR','Noto Sans KR','Pretendard',sans-serif; font-size: 10.5px; color: #111; line-height: 1.5; }
h1 { font-size: 19px; margin: 0 0 2px; } h2 { font-size: 13.5px; margin: 16px 0 6px; border-bottom: 2px solid #111; padding-bottom: 2px; }
h3 { font-size: 11.5px; margin: 8px 0 3px; color: #444; }
.sub { color: #666; font-size: 10px; } .box { background: #f4f4f4; padding: 8px 10px; margin: 8px 0; }
table { width: 100%; border-collapse: collapse; margin: 4px 0; } th, td { border-bottom: 1px solid #ddd; padding: 4px 5px; text-align: left; vertical-align: top; }
th { background: #eee; font-size: 9.5px; } td.n { text-align: right; white-space: nowrap; }
ul { margin: 2px 0; padding-left: 15px; } li { margin: 2px 0; }
.k { display: inline-block; font-size: 8.5px; border: 1px solid; padding: 0 3px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; } .three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.sc { border: 1px solid #ccc; padding: 6px 8px; } .sc p { margin: 3px 0; }
.foot { margin-top: 14px; color: #777; font-size: 9px; border-top: 1px solid #ccc; padding-top: 5px; }
.avoid { break-inside: avoid; }
"""


def page(title, body):
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{e(title)}</title><style>{CSS}</style></head><body>{body}" \
           f"<div class='foot'>투자 권유가 아니라 판단 재료예요. 사실 = 공시·보도로 확인 / 추정 = 판단·가정 / 모름 = 확인 못 함. 과거 검증이 미래를 보장하지 않아요.</div></body></html>"


def industry(R):
    M, N = R["macro"], R["narrative"]
    b = f"<h1>{e(R['name'])} 산업 리서치</h1><div class='sub'>{e(R['asof'])} 기준 · 숫자 {e((R.get('metrics_at') or '')[:10])} · 순서: 매크로 → 산업 → 공급망 → 상장사 → 회사 검증 → 시나리오 → 분류</div>"
    b += f"<div class='box'>{e(R['summary'])}</div>"
    b += f"<h2>1단계 · 매크로 환경 — {e(M['verdict'])}</h2><p>{e(M['verdict_why'])}</p><div class='two'>"
    for n, k in (("우호 요인", "good"), ("비우호 요인", "bad"), ("유동성", "liquidity"), ("지정학", "geo")):
        b += f"<div><h3>{n}</h3><ul>{''.join(item(x) for x in M[k])}</ul></div>"
    b += "</div>"
    b += f"<h2>2단계 · 산업 내러티브</h2><p><b>{e(N['mega'])}</b></p><table><tr><th>축</th><th>뒷받침</th><th>근거</th></tr>"
    b += "".join(f"<tr><td>{e(a)}</td><td>{e(s)}</td><td>{e(t)}</td></tr>" for a, s, t, *_ in N["axes"]) + "</table>"
    b += f"<p>시장 선반영: <b>{N['priced']}%</b> (0 / 50 / 75 중) — {tag(N['priced_why'][1])} {e(N['priced_why'][0])}</p>"
    b += f"<div class='two'><div><h3>강화 시나리오</h3><ul>{''.join(f'<li>{e(x)}</li>' for x in N['up'])}</ul></div><div><h3>약화 시나리오</h3><ul>{''.join(f'<li>{e(x)}</li>' for x in N['down'])}</ul></div></div>"
    b += "<h2>3단계 · 공급망 병목</h2><table><tr><th>레이어</th><th>강도</th><th>발생</th><th>유지</th><th>근거</th></tr>"
    b += "".join(f"<tr class='avoid'><td><b>{e(c['layer'])}</b><br><span class='sub'>{e(c['desc'])}</span></td><td>{e(c['neck'])}</td><td>{e(c['when'])}</td><td>{e(c['dur'])}</td><td>{tag(c['why'][1])} {e(c['why'][0])}{'<br>※ ' + e(c['note']) if c.get('note') else ''}</td></tr>" for c in R["chain"]) + "</table>"
    b += "<h2>4단계 · 글로벌 상장 공급사</h2><table><tr><th>회사</th><th>레이어</th><th>시총</th><th>20일 거래대금</th><th>PS</th><th>등급</th><th>최근 성장</th><th>분류</th></tr>"
    for c in R["companies"]:
        m = c.get("m") or {}
        b += f"<tr class='avoid'><td><b>{e(c['name'])}</b><br><span class='sub'>{e(c['t'])} · {e(c['exch'])}</span></td><td>{e(c['layer'])}</td><td class='n'>{big(m.get('mcap'), m.get('cur'))}</td><td class='n'>{big(m.get('adv'), m.get('cur'))}</td><td class='n'>{f'{m['ps']:.0f}배' if m.get('ps') else '—'}</td><td>{e(c['v']['grade'])}</td><td>{tag(c['growth'][1])} {e(c['growth'][0])}</td><td>{e(c['cls'])}</td></tr>"
    b += "</table><h3>제외한 곳</h3><ul>" + "".join(f"<li>{tag(k)} <b>{e(n)}</b> — {e(w)}</li>" for n, w, k, *_ in R["excluded"]) + "</ul>"
    b += "<h2>7단계 · 최종 분류</h2><table>" + "".join(
        f"<tr><td><b>{e(n)}</b></td><td>{', '.join(e(next((c['name'] for c in R['companies'] if c['t'] == t), t)) for t in ts)}</td><td>{e(w)}</td></tr>" for n, ts, w in R["final"]) + "</table>"
    b += "<h2>출처</h2><ul class='sub'>" + "".join(f"<li>{e(s)}</li>" for s in R["sources"]) + "</ul>"
    return page(R["name"] + " 산업 리서치", b)


def company(R, c):
    v, sc, m = c["v"], c["sc"], c.get("m") or {}
    b = f"<h1>{e(c['name'])} <span class='sub'>{e(c['t'])} · {e(c['exch'])}</span></h1><div class='sub'>{e(R['name'])} 리서치 {e(R['asof'])} · {e(c['layer'])} · 분류: <b>{e(c['cls'])}</b></div>"
    b += f"<div class='box'>주가 {m.get('px', '—')} {e(m.get('cur', ''))} ({e(m.get('day', ''))}) · 시총 {big(m.get('mcap'), m.get('cur'))} · 20일 거래대금 {big(m.get('adv'), m.get('cur'))} · 매출 대비 {f'{m['ps']:.1f}배' if m.get('ps') else '—'} · 200일선 {m.get('ma200', '—')} · 52주 {m.get('lo52', '—')}~{m.get('hi52', '—')}</div>"
    b += f"<p><b>주요 제품</b> {e(c['products'])}<br><b>주요 고객</b> {e(c['customers'])}<br><b>최근 성장</b> {tag(c['growth'][1])} {e(c['growth'][0])}</p>"
    rows = [("① 공급망 지위", v["pos"]), ("　대체 가능성", v["sub"]), ("③ 생산 능력 확장", v["capa"]), ("④ 재무 건전성", v["fin"]), ("⑤ 희석 위험", v["dil"]),
            ("⑥ 경영진·실행력", v["mgmt"]), ("⑦ 지정학·규제", v["geo"]), ("⑧ 밸류에이션", v["val"])]
    b += "<h2>5단계 · 회사 검증</h2><table>" + "".join(f"<tr class='avoid'><td style='width:22%'><b>{n}</b></td><td>{tag(x[1])} {e(x[0])}</td></tr>" for n, x in rows[:2])
    b += f"<tr><td><b>② 고객 검증 등급</b></td><td><b>{e(v['grade'])}</b> — {e(v['grade_why'])}</td></tr>"
    b += "".join(f"<tr class='avoid'><td><b>{n}</b></td><td>{tag(x[1])} {e(x[0])}</td></tr>" for n, x in rows[2:]) + "</table>"
    b += "<p class='sub'>등급: A 공식 고객·장기 공급·반복 매출 / B 이름 비공개지만 대형 고객 확인 / C 구조상 가능 / D 협약·시험 단계 / E 소문</p>"
    B, S, W = sc["best"], sc["base"], sc["worst"]
    b += f"""<h2>6단계 · 시나리오</h2><div class='three avoid'>
<div class='sc'><b>최고 · 약 {B['mult']}배</b><p><b>가정</b> {e(B['assume'])}</p><p><b>근거</b> {e(B['evidence'])}</p><p><b>약점</b> {e(B['weak'])}</p><p><b>재평가 조건</b> {e(B['rerate'])}</p></div>
<div class='sc'><b>기본 · 약 {S['mult']}배</b><p><b>가정</b> {e(S['assume'])}</p><p><b>근거</b> {e(S['evidence'])}</p><p><b>부진 이유</b> {e(S['why_weak'])}</p></div>
<div class='sc'><b>최악 · 약 {W['mult']}배</b><p><b>가정</b> {e(W['assume'])}</p><p><b>위험</b> {e(W['risks'])}</p><p><b>근거</b> {e(W['evidence'])}</p><p><b>손실 경로</b> {e(W['loss'])}</p></div></div>
<p class='sub'>배수는 지금 주가 대비 2029년 무렵을 가정한 추정이에요.</p>"""
    ev = m.get("ev")
    b += "<h2>장기 손익비 · 검증된 공식</h2>"
    if ev:
        b += f"<p>기댓값 = (상방 {ev['G'] * 100:+.0f}% × {ev['pG'] * 100:.0f}%) + (하방 {ev['L'] * 100:+.0f}% × {(1 - ev['pG']) * 100:.0f}%) = <b>{ev['value'] * 100:+.0f}%</b> · 손익비 {f'{ev['ratio']:.1f} : 1' if ev.get('ratio') else '—'} · 본전 확률 {ev['be'] * 100:.0f}% · 이상적 자리(상방 4배↑·하방 반토막 이내) {'맞음' if ev['ideal'] else '아님'}</p>"
    b += "<ul>" + "".join(f"<li><b>{'✔' if f['ok'] else '✘'} {e(f['t'])}</b> <span class='sub'>— {e(f['why'])}</span></li>" for f in m.get("formulas", [])) + "</ul>"
    b += f"<h2>7단계 · 조건</h2><p><b>좋은 투자가 되는 조건</b> {e(c['good_if'])}</p><p><b>가설이 무너지는 조건</b> {e(c['break_if'])}</p>"
    if c.get("src"):
        b += "<h3>출처</h3><ul class='sub'>" + "".join(f"<li>{e(s)}</li>" for s in c["src"]) + "</ul>"
    return page(f"{c['name']} ({c['t']})", b)


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
