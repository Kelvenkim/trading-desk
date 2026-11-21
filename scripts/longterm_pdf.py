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
    s = {"JPY": "¥", "GBp": "£", "EUR": "€", "KRW": "₩", "GBP": "£"}.get(cur, "$"); v = v / 100 if cur == "GBp" else v
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


DCSS = """
.cover h1 { font-size: 30px; color: #c8102e; font-style: italic; text-align: center; margin: 10px 0 2px; letter-spacing: .5px; }
.cover .sub { text-align: center; }
h2.r { border: 0; margin: 22px 0 8px; font-size: 15px; } h2.r span { background: #fde2e4; padding: 1px 6px; }
h3.n { font-size: 12.5px; color: #111; margin: 14px 0 4px; } h3.n b { color: #c8102e; }
.info td:first-child { width: 27%; color: #444; background: #fafafa; } .info td { border: 1px solid #ccc; }
.hl { background: #fff4c2; } .lead p { margin: 6px 0; font-size: 11px; }
.like { border-left: 4px solid #c8102e; background: #fff5f6; padding: 7px 10px; margin: 8px 0; font-size: 11px; }
.gl { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 8px 0; } .gl div { border: 1px solid #d9d9d9; border-radius: 6px; padding: 5px 8px; background: #fbfbfb; }
.gl b { color: #c8102e; }
.chain { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin: 6px 0; }
.chain div { border: 1px solid #ccc; border-radius: 6px; padding: 5px 6px; font-size: 9.5px; min-height: 34px; }
.chain div.me { border: 2px solid #c8102e; background: #fff5f6; } .chain div i { display: block; font-style: normal; color: #777; font-size: 8.5px; }
.qa { border: 1px solid #ddd; border-radius: 8px; padding: 8px 10px; margin: 8px 0; break-inside: avoid; }
.qa .q { font-weight: 700; } .qa .q b { color: #c8102e; } .qa .a { margin-top: 4px; } .qa .a b { color: #1a5fb4; }
.step { background: #111; color: #fff; display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 9.5px; margin-right: 4px; }
.fw { border: 2px solid #111; border-radius: 8px; padding: 6px 10px; margin: 8px 0; }
.concl { border: 2px solid #c8102e; border-radius: 8px; padding: 8px 12px; margin: 10px 0; } .concl p { margin: 5px 0; font-size: 11px; }
.pb { break-before: page; }
"""


def company(R, c):
    import re
    v, sc, m = c["v"], c["sc"], c.get("m") or {}
    A, Dp = c.get("about") or {}, c.get("deep") or {}
    cur = m.get("cur", "USD")
    pct = lambda a, b: f"{(a / b - 1) * 100:+.0f}%" if a and b else "—"
    # ---- 표지 + 기업정보 ----
    b = f"<div class='cover'><h1>{e(c['name'])} ANALYSIS</h1><div class='sub'>{e(c['t'])} · {e(c['exch'])} · {e(R['name'])} 장기 리서치 · 작성 {e(R['asof'])} · 숫자 {e(m.get('day', ''))}</div></div>"
    b += "<h2 class='r'><span>기업정보</span></h2><table class='info'>"
    rows = [(k, x, t) for k, x, t in Dp.get("info", [])] or [("거래소", c["exch"], "사실"), ("산업 위치", c["layer"], "사실"), ("최근 성장", c["growth"][0], c["growth"][1])]
    b += "".join(f"<tr><td>{e(k)}</td><td>{e(x)} {tag(t) if t != '사실' else ''}</td></tr>" for k, x, t in rows)
    b += f"<tr><td>지금 주가</td><td>{m.get('px', '—')} {e(cur)} · 52주 {m.get('lo52', '—')}~{m.get('hi52', '—')} (고점 대비 {pct(m.get('px'), m.get('hi52'))})</td></tr>"
    b += f"<tr><td>시가총액 · 몸값</td><td>{big(m.get('mcap'), cur)} · 매출 대비 {f'{m['ps']:.1f}배' if m.get('ps') else '—'} · 20일 거래대금 {big(m.get('adv'), cur)}</td></tr>"
    b += f"<tr><td>우리 분류</td><td><b class='hl'>{e(c['cls'])}</b></td></tr></table>"
    # ---- 이 회사는요 + 왜 지금 ----
    if A:
        b += "<h2 class='r'><span>한눈에 — 어떤 회사인가</span></h2><div class='lead'>"
        b += f"<p><b>어떤 회사?</b> {e(A['what'])}</p><p><b>뭘 만드나?</b> {e(A['makes'])}</p><p><b>왜 필요한가?</b> {e(A['why'])}</p></div>"
        if A.get("like"):
            b += f"<div class='like'>한 줄 비유 — <b>{e(A['like'])}</b></div>"
    if Dp.get("hook"):
        b += "<h2 class='r'><span>왜 지금 이 회사를 봐야 하나</span></h2><div class='lead'>" + "".join(f"<p>{e(x)}</p>" for x in Dp["hook"]) + "</div>"
    # ---- 어떤 회사며 어떻게 돈을 버나 ----
    b += "<h2 class='r pb'><span>어떤 회사며, 어떻게 돈을 버나</span></h2>"
    b += f"<h3 class='n'><b>①</b> 무엇을 파나</h3><p>{e(c['products'])}</p><p><b>주요 고객</b> {e(c['customers'])}</p>"
    if Dp.get("tech"):
        b += "<h3 class='n'><b>②</b> 기술이 뭔가</h3>" + "".join(f"<p><b>{e(t)}</b> — {e(x)}</p>" for t, x in Dp["tech"])
    if Dp.get("gloss"):
        b += "<div class='gl'>" + "".join(f"<div><b>{e(t)}</b><br>{e(x)}</div>" for t, x in Dp["gloss"]) + "</div>"
    if Dp.get("money"):
        b += "<h3 class='n'><b>③</b> 어떻게 돈을 버나</h3><table><tr><th>사업</th><th>내용</th><th>숫자</th></tr>" + "".join(
            f"<tr><td><b>{e(n)}</b></td><td>{e(x)}</td><td class='n'>{e(y)}</td></tr>" for n, x, y in Dp["money"]) + "</table>"
    b += f"<h3 class='n'><b>{'④' if Dp else '②'}</b> 최근 성장</h3><p>{tag(c['growth'][1])} {e(c['growth'][0])}</p>"
    # ---- 산업 구조 (공급망 속 위치) ----
    mine = set(re.findall(r"L(\d)", c["layer"]))
    b += f"<h2 class='r'><span>산업 구조 — {e(R['name'])} 공급망 속 위치</span></h2><p class='sub'>빨간 테두리 = 이 회사가 있는 자리. 아래 글자 = 병목 강도·유지 기간</p><div class='chain'>"
    b += "".join(f"<div class='{'me' if re.match(r'L(\d)', x['layer']) and re.match(r'L(\d)', x['layer']).group(1) in mine else ''}'><b>{e(x['layer'])}</b><i>{e(x['neck'])} · {e(x['dur'])}</i></div>" for x in R["chain"])
    b += "</div>"
    # ---- 최근 이슈 ----
    if Dp.get("issues"):
        b += "<h2 class='r'><span>최근 이슈</span></h2>" + "".join(
            f"<h3 class='n'><span class='hl'>{e(t)}</span> {tag(k)}</h3><p>{e(x)} <span class='sub'>{e(u)}</span></p>" for t, x, k, u in Dp["issues"])
    # ---- 궁금증 Q&A ----
    qa = Dp.get("qa") or [
        ("왜 이 회사여야 하나? 다른 회사로 바꿀 수 있나?", f"{v['pos'][0]} / 대체 가능성: {v['sub'][0]}", v["pos"][1]),
        ("지금 몸값은 비싼가?", v["val"][0] + " · 공식 점검: " + ", ".join(f"{'✔' if f['ok'] else '✘'} {f['t']}" for f in m.get("formulas", [])), v["val"][1]),
        ("가장 크게 잃는 경로는?", f"{sc['worst']['loss']} — 이런 일이 보이면 가설을 접어요: {c['break_if']}", "추정")]
    b += "<h2 class='r pb'><span>궁금증 Q&amp;A</span></h2>" + "".join(
        f"<div class='qa'><div class='q'><b>궁금증 {i}.</b> {e(q)}</div><div class='a'><b>답 {i}.</b> {tag(k)} {e(a)}</div></div>" for i, (q, a, k) in enumerate(qa, 1))
    # ---- 우리 분석법 ----
    M, N = R["macro"], R["narrative"]
    b += "<h2 class='r pb'><span>우리 분석법으로 검증 — 7단계 + 검증된 공식</span></h2>"
    b += "<div class='fw small'>순서: <span class='step'>1 매크로</span><span class='step'>2 산업 내러티브</span><span class='step'>3 공급망 병목</span><span class='step'>4 상장 공급사</span><span class='step'>5 회사 검증 8항목</span><span class='step'>6 시나리오</span><span class='step'>7 분류</span> · 결론이 아니라 조건 · 사실/추정/모름 구분</div>"
    b += f"<p><span class='step'>1</span><b>매크로 — {e(M['verdict'])}</b> {e(M['verdict_why'])}</p>"
    b += f"<p><span class='step'>2</span><b>산업 내러티브</b> {e(N['mega'])} · 시장 선반영 약 {N['priced']}%</p>"
    b += f"<p><span class='step'>3·4</span><b>공급망 위치</b> {e(c['layer'])}</p>"
    vr = [("① 공급망 지위", v["pos"]), ("　대체 가능성", v["sub"]), ("③ 생산 능력 확장", v["capa"]), ("④ 재무 건전성", v["fin"]), ("⑤ 희석 위험", v["dil"]),
          ("⑥ 경영진·실행력", v["mgmt"]), ("⑦ 지정학·규제", v["geo"]), ("⑧ 밸류에이션", v["val"])]
    b += "<h3 class='n'><span class='step'>5</span>회사 검증 8항목</h3><table>" + "".join(f"<tr class='avoid'><td style='width:22%'><b>{n}</b></td><td>{tag(x[1])} {e(x[0])}</td></tr>" for n, x in vr[:2])
    b += f"<tr><td><b>② 고객 검증 등급</b></td><td><b>{e(v['grade'])}</b> — {e(v['grade_why'])}</td></tr>"
    b += "".join(f"<tr class='avoid'><td><b>{n}</b></td><td>{tag(x[1])} {e(x[0])}</td></tr>" for n, x in vr[2:]) + "</table>"
    b += "<p class='sub'>등급: A 공식 고객·장기 공급·반복 매출 / B 이름 비공개지만 대형 고객 확인 / C 구조상 가능 / D 협약·시험 단계 / E 소문</p>"
    B, S, W = sc["best"], sc["base"], sc["worst"]
    b += f"""<h3 class='n'><span class='step'>6</span>시나리오 (지금 주가 대비 2029년 무렵, 추정)</h3><div class='three avoid'>
<div class='sc'><b>최고 · 약 {B['mult']}배</b><p><b>가정</b> {e(B['assume'])}</p><p><b>근거</b> {e(B['evidence'])}</p><p><b>약점</b> {e(B['weak'])}</p><p><b>재평가 조건</b> {e(B['rerate'])}</p></div>
<div class='sc'><b>기본 · 약 {S['mult']}배</b><p><b>가정</b> {e(S['assume'])}</p><p><b>근거</b> {e(S['evidence'])}</p><p><b>부진 이유</b> {e(S['why_weak'])}</p></div>
<div class='sc'><b>최악 · 약 {W['mult']}배</b><p><b>가정</b> {e(W['assume'])}</p><p><b>위험</b> {e(W['risks'])}</p><p><b>근거</b> {e(W['evidence'])}</p><p><b>손실 경로</b> {e(W['loss'])}</p></div></div>"""
    ev = m.get("ev")
    b += "<h3 class='n'>장기 손익비 · 검증된 공식 (우리가 백테스트로 확인한 것만)</h3>"
    if ev:
        b += f"<p>기댓값 = (상방 {ev['G'] * 100:+.0f}% × {ev['pG'] * 100:.0f}%) + (하방 {ev['L'] * 100:+.0f}% × {(1 - ev['pG']) * 100:.0f}%) = <b>{ev['value'] * 100:+.0f}%</b> · 손익비 {f'{ev['ratio']:.1f} : 1' if ev.get('ratio') else '—'} · 본전 확률 {ev['be'] * 100:.0f}% · 이상적 자리(상방 4배↑·하방 반토막 이내) {'맞음' if ev['ideal'] else '아님'}</p>"
    b += "<ul>" + "".join(f"<li><b>{'✔' if f['ok'] else '✘'} {e(f['t'])}</b> <span class='sub'>— {e(f['why'])}</span></li>" for f in m.get("formulas", [])) + "</ul>"
    b += "<p class='sub'>손절은 최대 −7%(개별 판단으로 더 짧게 가능). 가장 중요한 건 손실 최소화 — 조건이 확인되기 전에는 분할·소액.</p>"
    b += f"<h3 class='n'><span class='step'>7</span>분류 — {e(c['cls'])}</h3><p><b>좋은 투자가 되는 조건</b> {e(c['good_if'])}</p><p><b>가설이 무너지는 조건</b> {e(c['break_if'])}</p>"
    # ---- 결론 ----
    concl = Dp.get("concl") or [f"{A.get('like', c['name'])}." if A else c["name"], f"지금 위치는 '{c['cls']}'. 좋은 투자가 되려면: {c['good_if']}", f"이런 일이 보이면 가설을 접어요: {c['break_if']}"]
    b += f"<h2 class='r'><span>그래서 {e(c['name'])}는?</span></h2><div class='concl'>" + "".join(f"<p>{e(x)}</p>" for x in concl) + "</div>"
    if c.get("src"):
        b += "<h3>출처</h3><ul class='sub'>" + "".join(f"<li>{e(s)}</li>" for s in c["src"]) + "</ul>"
    return page(f"{c['name']} ({c['t']}) 분석", b).replace("</style>", DCSS + "</style>", 1)


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
