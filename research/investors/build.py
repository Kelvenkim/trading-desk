"""큰 수익을 낸 투자자들 — 포트폴리오(13F 2026년 3분기)와 인터뷰 정리 PDF"""
import html
from pathlib import Path
from playwright.sync_api import sync_playwright

H = Path(__file__).parent
OUT = H.parent.parent / "reports/research"
OUT.mkdir(parents=True, exist_ok=True)
e = html.escape

SRC = {
    "brk": "https://www.kiplinger.com/investing/stocks/stocks-berkshire-hathaway-bought-sold-q3-2026",
    "abel": "https://acquirersmultiple.com/2026/03/greg-abel-emphasizes-stewardship-and-capital-discipline-in-first-berkshire-letter/",
    "duq": "https://stockhub.kr/en/insights/duquesne-13f-2026-q3",
    "dr26a": "https://www.itiger.com/hant/news/2614817074",
    "dr26b": "https://acquirersmultiple.com/2026/03/stanley-druckenmiller-massive-disruption-ahead/",
    "drconc": "https://hedgefundalpha.com/strategies/stanley-druckenmiller-make-big-concentrated-bets-when-you-have-a-lot-of-conviction/",
    "dr25": "https://25iq.com/2015/04/11/a-dozen-things-ive-learned-from-stanley-druckenmiller-about-investing/",
    "psh": "https://stockhub.kr/en/insights/pershing-13f-2026-q3",
    "app": "https://stockhub.kr/en/insights/appaloosa-13f-2026-q3",
    "ptj": "https://25iq.com/2015/07/25/a-dozen-things-ive-learned-from-paul-tudor-jones-about-investing-and-trading",
    "med": "https://www.quantt.co.uk/resources/medallion-fund-history",
}

INV = [
    {
        "name": "워런 버핏 → 그렉 아벨 (버크셔 해서웨이)", "style": "가치 투자 · 장기 보유 · 집중",
        "record": "버크셔 시가총액 약 $1.26조. 2026년부터 그렉 아벨이 CEO(버핏 후계).",
        "port": [("애플", "주식 포트폴리오의 약 25% (최고 때 40%+)"), ("상위 5종목", "약 69%"), ("상위 10종목", "약 90%"),
                 ("현금", "$3,570억 (1분기 $3,800억 최고)"), ("3분기 매수", "델타항공 +12%, 레나(주택) 약 2배, 신규 Bending Spoons"),
                 ("3분기 매도", "뱅크오브아메리카 −6%, 캐피털원 −62%, 크로거 −10%")],
        "said": [("아벨 첫 주주 서한(2026-02)", "\"여러분의 돈은 우리 돈과 섞여 있지만 우리 것이 아니다\" — 가치를 꼼꼼히 따지고, 천천히, 오래 보유. 현금은 '기회가 올 때 빨리 움직이기 위한' 요새 같은 재무 구조")],
        "lesson": "10종목이 90% — 아주 집중돼 있어요. 대신 그 종목들은 수십 년 이익을 확인한 회사이고, 현금을 $3,500억 넘게 들고 '좋은 가격'을 기다려요. 과감함의 전제는 '싼 가격 + 검증된 사업 + 기다릴 현금'이에요.",
        "src": ["brk", "abel"],
    },
    {
        "name": "스탠리 드러켄밀러 (듀케인 패밀리 오피스)", "style": "매크로 + 주식 · 확신이 크면 크게",
        "record": "1981~2010년 운용하며 손실 난 해가 없었다고 널리 알려진 투자자. 1992년 소로스와 파운드 공매도. (널리 알려진 이야기 — 이번에 원문은 확인 안 함)",
        "port": [("1위 나테라(유전자 검사)", "29.2% — 한 종목에 약 3분의 1"), ("상위 5종목", "약 49% (나테라·시게이트·아마존·폭스·YPF)"),
                 ("종목 수", "95 → 65개, 48개 전량 매도"), ("신규", "금광주(뉴몬트·배릭·애그니코), 웨스턴디지털, 앱러빈, 스페이스X"),
                 ("정리", "AMD 전량, TSMC −94.5%, 알파벳(전 분기) 매도")],
        "said": [("집중 (The Hustle 인터뷰, 2021 무렵)", "자기가 존경하는 투자자들의 공통점은 \"확신이 큰 곳에 크게 집중 베팅\". 1992년 파운드 공매도를 100%로 하겠다고 하자 소로스가 '평생 한 번 오는 기회면 200%'라고 했다는 일화"),
                 ("크기 (2026-01 모건스탠리 인터뷰)", "맞히는 것보다 '맞았을 때 얼마나 벌고 틀렸을 때 얼마나 잃느냐'(소로스에게 배운 것)가 결과를 정한다. 자기는 겁이 나서 너무 일찍 판 게 가장 큰 후회"),
                 ("지금 생각 (2026-01)", "AI는 더 이상 엔진이 아니다, 구리·금, 달러 약세, 채권 숏으로 헤지. 한국·일본에 큰 포지션"),
                 ("손실", "소로스를 '최고의 손절가'라고 부름 — 안 되면 바로 나온다")],
        "lesson": "형이 말한 '확실한 자리는 과감하게'에 가장 가까운 사람이에요. 하지만 짝이 있어요 — ① 틀리면 바로 나옴 ② 레버리지는 과하지 않게 ③ 크게 거는 건 몇 년에 한 번. 매일 '확실하다'고 느끼는 것과는 달라요.",
        "src": ["duq", "drconc", "dr26a", "dr26b", "dr25"],
    },
    {
        "name": "빌 애크먼 (퍼싱 스퀘어)", "style": "행동주의 · 극단적 집중",
        "record": "소수 종목에 크게 걸고 경영에 목소리를 내는 방식.",
        "port": [("종목 수", "16개뿐"), ("자기 회사(퍼싱 스퀘어) 주식", "33.5% (이번에 처음 신고)"),
                 ("나머지 상위", "우버 7.6%, 아마존 6.9%, 마이크로소프트 6.8%, 메타 6.7%, 하워드휴즈 6.7%"),
                 ("변화", "신규 ICE·알콘, 넷플릭스 +18%, 마이크로소프트 −34.5%, 허츠 전량 매도")],
        "said": [],
        "lesson": "16종목으로 수백억 달러를 굴려요. 집중이지만 '아무 회사'가 아니라 독점력이 있는 대형 우량주예요. 이번에 인터뷰는 따로 확인하지 못했어요.",
        "src": ["psh"],
    },
    {
        "name": "데이비드 테퍼 (아팔루사)", "style": "역발상 · 업종 집중",
        "record": "2009년 금융위기 바닥에서 은행주를 크게 사 큰 수익을 낸 것으로 유명. (널리 알려진 이야기 — 이번에 원문은 확인 안 함)",
        "port": [("1위 마이크론", "17.6% (+28% 추가)"), ("2위 아마존", "14.8%"), ("TSMC", "9.5%"), ("스페이스X", "7.4% (크게 늘림)"),
                 ("변화", "엔비디아 +31%, 램리서치 +63%, 신규 오라클·어플라이드머티리얼즈 / AMD·브로드컴·퀄컴 전량 매도"),
                 ("종목 수", "24개, 약 $76억")],
        "said": [],
        "lesson": "반도체·AI에 강하게 쏠려 있어요. 같은 반도체 안에서도 바꿔 타요(AMD·브로드컴 → 마이크론·장비). 집중은 '종목'이 아니라 '확신하는 흐름'에 해요.",
        "src": ["app"],
    },
    {
        "name": "폴 튜더 존스 (튜더 인베스트먼트)", "style": "매크로 트레이더 · 방어 우선",
        "record": "1987년 블랙먼데이를 예측해 큰 수익을 낸 것으로 유명. (널리 알려진 이야기 — 이번에 원문은 확인 안 함)",
        "port": [("13F", "이번에 확인하지 않았어요(매크로 펀드라 13F가 실제 포지션을 잘 못 보여줌)")],
        "said": [("방어", "\"내 기본 철학은 훌륭한 수비\" · \"돈 버는 데 집중하지 말고 가진 걸 지키는 데 집중하라\""),
                 ("200일선", "\"200일 이동평균 아래로 떨어지는 건 무엇이든 나와라\""),
                 ("손익비", "\"5 대 1은 1달러를 걸고 5달러를 노린다는 뜻\" — 그러면 대부분 틀려도 이긴다")],
        "lesson": "우리 사이트의 200일선 필터(S&P 2000~: 최대 낙폭 −57% → −26%)와 같은 생각이에요. 과감함보다 '살아남기'가 먼저.",
        "src": ["ptj"],
    },
    {
        "name": "짐 사이먼스 (르네상스 메달리온 펀드)", "style": "수학·통계 · 아주 많은 작은 베팅",
        "record": "1988~2018년 수수료 전 연평균 약 66%, 수수료 후 약 39% (주커만 책 인용, 감사받은 공식 수치 아님). 1993년부터 외부 자금 안 받음.",
        "port": [("방식", "집중이 아니라 그 반대 — 수많은 작은 거래")],
        "said": [("상원 제출 자료(2014)", "예측이 맞는 경우는 '아주 조금 더 많을 뿐', 아주 많은 거래로 큰 수의 법칙을 이용해 변동을 줄인다")],
        "lesson": "역사상 최고 기록은 '확실한 한 방'이 아니라 '조금 유리한 확률 × 엄청난 횟수'에서 나왔어요. 우리 AI 데스크의 방향(작은 우위 + 손절 + 많은 거래)과 같은 쪽이에요.",
        "src": ["med"],
    },
]

OUR = """
<h2>형 질문과 연결: "확실한 자리는 과감하게"</h2>
<p>대가들은 두 부류로 나뉘어요.</p>
<table><tr><th></th><th>집중형 (드러켄밀러·소로스·버핏·애크먼)</th><th>분산·확률형 (사이먼스)</th></tr>
<tr><td>방식</td><td>확신이 크면 크게(한 종목 30%도)</td><td>조금 유리한 베팅을 아주 많이</td></tr>
<tr><td>전제</td><td>깊은 조사 + 틀리면 즉시 철수 + 몇 년에 한 번</td><td>통계로 검증된 작은 우위 + 엄격한 크기 관리</td></tr>
<tr><td>위험</td><td>확신이 틀리면 크게 잃음</td><td>우위가 사라지면 서서히 잃음</td></tr></table>
<h3>우리 데이터로 확인 (주식 5만 건, 2015~2026)</h3>
<ul>
<li><b>AI 데스크 점수가 높다고 더 벌지 않았어요.</b> 점수 0.60~0.65: 평균 +0.16R / 0.75~0.80: +0.13R / 0.80~0.85: +0.16R — 거의 같아요. '점수가 높으면 확실하다'는 데이터상 성립하지 않아요.</li>
<li><b>'덜 오른 자리'(50일선 0~5% 위·RSI≤65·MACD↑)만 꾸준히 나았어요:</b> +0.19R vs 보통 +0.15R vs 이미 많이 오른 자리 +0.06R. 앞·뒤 기간 모두 같은 방향.</li>
<li><b>여러 조건을 겹친 '확실해 보이는 자리'</b>(덜 오른 자리 + S&P 200일선 위 + 점수 0.75↑)는 오히려 +0.06R(458건)로 나빴어요. 조건을 많이 겹칠수록 확실해 보이지만, 표본이 줄고 우연이 끼어요.</li>
</ul>
<h3>그래서 (조건으로)</h3>
<ul>
<li>'과감하게'가 통하려면 <b>그 자리가 다른 자리보다 확실히 더 번다는 증거</b>가 있어야 해요. 지금 우리에게 있는 증거는 '덜 오른 자리가 약 1.25배 낫다' 정도 → 크기를 2~3배로 키울 근거는 아직 없어요.</li>
<li>근거에 맞는 크기 조절은 <b>덜 오른 자리 1.25배, 이미 많이 오른 자리 제외(지금 규칙)</b> 정도예요. 형이 원하면 이걸 AI 데스크에 넣을 수 있어요.</li>
<li>드러켄밀러식 '크게 거는 자리'는 매일 오는 신호가 아니라, 장기 투자 리서치(7단계)에서 병목·고객·몸값이 모두 맞는 드문 경우에 어울려요. 그때도 '틀리면 바로 나오는 조건'을 먼저 정해야 해요.</li>
</ul>
"""


def build():
    cards = []
    for v in INV:
        port = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in v["port"])
        said = "".join(f"<li><b>{e(a)}</b> — {e(b)}</li>" for a, b in v["said"]) or "<li class='mut'>이번에 확인한 인터뷰 없음</li>"
        src = " ".join(f"<a href='{SRC[k]}'>[{i + 1}]</a>" for i, k in enumerate(v["src"]))
        cards.append(f"""<section class='inv'><h2>{e(v['name'])}</h2><div class='st'>{e(v['style'])} · {e(v['record'])}</div>
        <h3>포트폴리오 (13F, 2026-09-30 기준)</h3><table>{port}</table>
        <h3>인터뷰·발언 (요약)</h3><ul>{said}</ul>
        <div class='les'><b>배울 점</b> {e(v['lesson'])}</div><div class='src'>출처 {src}</div></section>""")
    srcs = "".join(f"<li>{e(u)}</li>" for u in SRC.values())
    doc = f"""<!doctype html><html><head><meta charset='utf-8'><style>
    @page {{ size: A4; margin: 14mm 13mm; }}
    body {{ font-family: 'Noto Sans CJK KR','Noto Sans KR',sans-serif; font-size: 10.5px; color: #111; line-height: 1.55; }}
    .cover {{ border-bottom: 3px solid #111; padding-bottom: 10px; margin-bottom: 8px; }}
    .cover h1 {{ font-size: 22px; margin: 0; }} .cover p {{ margin: 4px 0; color: #444; }}
    h2 {{ font-size: 14px; margin: 16px 0 4px; border-bottom: 2px solid #111; padding-bottom: 2px; }}
    h3 {{ font-size: 11px; margin: 8px 0 3px; color: #555; }}
    table {{ width: 100%; border-collapse: collapse; }} td, th {{ border-bottom: 1px solid #ddd; padding: 3px 5px; vertical-align: top; text-align: left; }}
    th {{ background: #eee; }} td:first-child {{ width: 26%; font-weight: 600; }}
    ul {{ margin: 2px 0; padding-left: 16px; }} li {{ margin: 2px 0; }}
    .st {{ color: #555; }} .les {{ background: #fff4e0; border-left: 3px solid #e08a00; padding: 6px 8px; margin-top: 6px; }}
    .src {{ font-size: 9px; color: #777; margin-top: 3px; }} .src a {{ color: #777; }} .mut {{ color: #888; }}
    .inv {{ break-inside: avoid; }} .box {{ background: #f4f4f4; padding: 8px 10px; }}
    .foot {{ margin-top: 14px; font-size: 9px; color: #777; border-top: 1px solid #ccc; padding-top: 5px; }}
    </style></head><body>
    <div class='cover'><h1>큰 수익을 낸 투자자들 — 포트폴리오와 인터뷰</h1>
    <p>2026-11-20 작성 · 포트폴리오는 2026년 3분기 13F(9/30 기준, 11/14~16 공시) · 인터뷰는 출처 날짜 표시</p></div>
    <div class='box'><b>한 줄 요약</b> — 큰 수익을 낸 사람들은 '과감한 집중'(드러켄밀러·버핏·애크먼·테퍼)과 '아주 많은 작은 우위'(사이먼스) 두 길로 나뉘지만,
    공통점은 하나예요: <b>손실을 먼저 관리한다</b>(틀리면 바로 철수, 방어 우선, 기다릴 현금). 과감함은 그 위에서만 작동해요.</div>
    <h3>13F 읽는 법</h3><ul><li>분기 말 하루의 '미국 상장 롱 주식'만 보여줘요 — 공매도·채권·해외·현재 보유는 안 보여요. 45일 늦게 공개돼요.</li>
    <li>숫자는 13F 요약 사이트 기준이라 원문(SEC)과 조금 다를 수 있어요.</li></ul>
    {''.join(cards)}
    {OUR}
    <h2>출처</h2><ul class='src'>{srcs}</ul>
    <div class='foot'>투자 권유가 아니라 공부 자료예요. 인용은 짧게 줄이거나 우리말로 옮긴 요약이에요. 과거 성과가 미래를 보장하지 않아요.</div>
    </body></html>"""
    p = OUT / "큰수익_투자자_포트폴리오_인터뷰_2026-11.pdf"
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(); pg.set_content(doc, wait_until="load")
        pg.pdf(path=str(p), format="A4", print_background=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template="<div style='font-size:7px;color:#999;width:100%;text-align:center'><span class='pageNumber'></span> / <span class='totalPages'></span></div>")
        b.close()
    print(p)


if __name__ == "__main__":
    build()
