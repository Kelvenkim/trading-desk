"""
PDF 공통 모양 (11/22 형: PDF로 주는 모든 것 — 매일 보고서·산업 리서치·기업 분석표 — UI를 사이트 톤으로 통일)
사이트와 같은 색: 어두운 바탕 · 둥근 카드 · 보라 포인트(#7c83ff) · 오름 빨강 / 내림 파랑
쓰는 곳: scripts/report_pdf.py (매일 보고서), scripts/longterm_pdf.py (산업 리서치·기업 분석표)
"""
COL = dict(bg="#0f1013", panel="#18191d", raised="#202227", line="#2b2d33", text="#eceef2", muted="#a3a7b1", faint="#6f7480",
           accent="#7c83ff", up="#ff5f6b", down="#4ea3ff", ok="#3ecf8e", warn="#f5b84b", orange="#f0a43a", violet="#b79bff")

BASE = """
@page { size: A4; margin: 0; }
:root { --bg:#0f1013; --panel:#18191d; --raised:#202227; --line:#2b2d33; --text:#eceef2; --muted:#a3a7b1; --faint:#6f7480; --accent:#7c83ff; --up:#ff5f6b; --down:#4ea3ff; --ok:#3ecf8e; --warn:#f5b84b; }
* { box-sizing: border-box; }
html, body { background: var(--bg); }
body { margin: 0; padding: 0 11mm; font-family: 'Noto Sans CJK KR','Noto Sans KR','Pretendard',sans-serif; font-size: 10px; color: var(--text); line-height: 1.6; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
b, strong { color: #fff; } a { color: var(--accent); text-decoration: none; }
.pg { width: 100%; border-collapse: collapse; font-size: inherit; margin: 0; } .pg > thead td, .pg > tfoot td { height: 10mm; padding: 0; border: 0; } .pg > tbody > tr > td { padding: 0; border: 0; }
.hero { background: linear-gradient(135deg, #23264a, #18191d 60%); border-radius: 18px; padding: 16px 18px; margin-bottom: 12px; }
.hero .tk { color: var(--muted); font-size: 10.5px; } .hero h1 { font-size: 24px; margin: 2px 0 4px; letter-spacing: -.3px; color: #fff; }
.chip { display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: 9.5px; font-weight: 700; background: rgba(124,131,255,.18); color: #c9ccff; margin-right: 4px; }
.sec { background: var(--panel); border-radius: 16px; padding: 12px 14px; margin: 10px 0; }
.sec > h2 { font-size: 13.5px; margin: 0 0 8px; display: flex; align-items: center; gap: 8px; color: #fff; break-after: avoid; }
.sec > h2 .no { color: var(--accent); font-size: 11px; font-weight: 800; } .sec > h2::before { content: ""; width: 4px; height: 15px; border-radius: 3px; background: var(--accent); flex: none; }
h3 { font-size: 11px; margin: 10px 0 4px; color: #fff; break-after: avoid; } p { margin: 4px 0; }
.box { background: #08090b; border-radius: 12px; padding: 8px 11px; margin: 6px 0; break-inside: avoid; }
blockquote { margin: 6px 0; padding: 6px 12px; border-left: 3px solid var(--accent); background: #08090b; border-radius: 0 10px 10px 0; }
table { width: 100%; border-collapse: collapse; margin: 4px 0; font-size: 9.3px; }
th { color: var(--faint); font-weight: 600; text-align: left; padding: 4px 5px; border-bottom: 1px solid var(--line); font-size: 8.6px; background: transparent; }
td { padding: 5px 5px; border-bottom: 1px solid #222428; vertical-align: top; } td.n, th.n, .num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
ul, ol { margin: 3px 0; padding-left: 15px; } li { margin: 3px 0; }
.up { color: var(--up); } .down, .dn { color: var(--down); } .muted, .mut { color: var(--muted); } .small, .sm { font-size: 8.8px; } .sm { color: var(--faint); }
.ok { color: var(--ok); } .no { color: var(--up); }
.k { display: inline-block; font-size: 7.8px; border-radius: 5px; padding: 0 5px; margin-right: 3px; font-weight: 700; vertical-align: 1px; }
.k.f { background: rgba(62,207,142,.15); color: var(--ok); } .k.e { background: rgba(245,184,75,.15); color: var(--warn); } .k.u { background: rgba(163,167,177,.15); color: var(--muted); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; } .three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
.sc { background: var(--raised); border-radius: 12px; padding: 8px 9px; } .sc p { margin: 3px 0; font-size: 9px; }
.cap { font-size: 8.6px; font-weight: 700; color: var(--muted); margin: 6px 0 3px; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin: 6px 0 8px; }
.kpis div { background: var(--raised); border-radius: 12px; padding: 7px 9px; display: grid; } .kpis span { font-size: 8.3px; color: var(--faint); } .kpis b { font-size: 13px; } .kpis em { font-style: normal; font-size: 8.5px; color: var(--muted); }
.tag { font-size: 7.8px; background: rgba(124,131,255,.18); color: #c9ccff; border-radius: 99px; padding: 1px 8px; font-weight: 700; }
.avoid { break-inside: avoid; } .sec { break-inside: avoid-page; } .sec.long { break-inside: auto; }
.foot { color: var(--faint); font-size: 8px; margin-top: 10px; border-top: 1px solid var(--line); padding-top: 6px; }
"""


# 11/24 형: 흑백 프린터라 검은 바탕은 잉크가 너무 듦 → 인쇄용 흰 바탕 (표지만 원래 어두운 모양 유지)
#   PDF_LIGHT=1 환경 변수로 켬. 사이트에 올리는 PDF는 그대로 어두운 바탕.
LIGHT = """
:root { --bg:#ffffff; --panel:#ffffff; --raised:#f4f5f7; --line:#c9ccd3; --text:#16181d; --muted:#454a55; --faint:#6b707c; --accent:#3d44c9; --up:#d42a3a; --down:#1c63c9; --ok:#13804f; --warn:#a86a00; }
html, body { background: #fff !important; } body { color: #16181d; }
b, strong { color: #000; }
.sec { background: #fff; border: 1px solid #c9ccd3; }
.box, blockquote { background: #f4f5f7 !important; }
.hero { background: #fff; border: 1.5px solid #3d44c9; } .hero h1 { color: #000; } .hero .tk { color: #454a55; }
.chip, .tag { background: #e9eafb; color: #2a2f9e; }
.sc, .kpis div, .pcard { background: #f4f5f7 !important; border: 1px solid #dfe1e6; }
td { border-bottom: 1px solid #e1e3e8; } th { color: #454a55; border-bottom: 1px solid #9ea3ad; }
.hdr { color: #454a55 !important; border-bottom-color: #c9ccd3 !important; }
.st { background: #e1e3e8 !important; } .st i.pos { background: #d42a3a !important; } .st i.neg { background: #1c63c9 !important; }
.gd { stroke: #dfe1e6 !important; } .curve .ax { fill: #454a55 !important; } .curve .lg { fill: #333 !important; } .curve .pill { fill: #fff !important; }
svg [fill="#eceef2"] { fill: #222 !important; } svg tspan[fill="#eceef2"] { fill: #222 !important; } svg [stroke="#eceef2"] { stroke: #222 !important; }
svg [fill="#0f1013"], svg [fill="#18191d"], svg [fill="#202227"] { fill: #fff !important; }
svg [stroke="#2b2d33"] { stroke: #dfe1e6 !important; } svg text[fill="#a3a7b1"], svg text[fill="#6f7480"] { fill: #454a55 !important; }
.risk { background: #fdeef0 !important; border-color: #e7a1a9 !important; color: #a3172a !important; }
.fb { color: #2a2f9e !important; }
img { filter: invert(1) hue-rotate(180deg); }      /* 매매 차트 그림(어두운 바탕 PNG)을 밝게 — 색은 비슷하게 유지 */
.cover { margin: -10mm -11mm 0 !important; height: 297mm !important; border-radius: 0 !important; color: #fff; }
.cover, .cover * { -webkit-print-color-adjust: exact; }
.cover b, .cover strong { color: #fff; }
.k.f { background: #e3f4ec; color: #13804f; } .k.e { background: #fbf0dc; color: #8a5a00; } .k.u { background: #eceef2; color: #454a55; }
"""


def wrap(title, body, css=""):
    import os
    if os.environ.get("PDF_LIGHT"):
        css = css + LIGHT
    """어두운 바탕이 종이 끝까지 가도록 @page 여백 0 + 위아래 여백은 표 머리·꼬리로 (모든 쪽에 반복)"""
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>{title}</title><style>{BASE}{css}</style></head><body>"
            f"<table class='pg'><thead><tr><td></td></tr></thead><tfoot><tr><td></td></tr></tfoot><tbody><tr><td>{body}</td></tr></tbody></table></body></html>")


def sec(no, title, html, cls=""):
    return f"<div class='sec {cls}'><h2>{f'<span class=no>{no}</span>' if no else ''}{title}</h2>{html}</div>"
