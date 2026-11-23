"""인쇄 묶음 (11/23 형: "오늘 보고서랑 다 모아서 pdf 하나로, 연구한 것도 스프레드시트로")
  ① 연구 결과 .xlsx (스프레드시트로 가져오기용)  ② 연구 결과 PDF (표 + 막대 그림)  ③ 오늘 매매 기록지 PDF
  ④ 목차 + 최근 보고서 + 산업·기업 보고서 전부를 한 PDF로 묶고 쪽 번호
python research/print_pack.py OUTDIR"""
import base64, io, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "research"))
import pdf_style as PS
from summary_tables import T

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT.mkdir(parents=True, exist_ok=True)
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
for f in font_manager.findSystemFonts():
    if "NotoSansCJK" in f and "Regular" in f:
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = "Noto Sans CJK JP"
plt.rcParams["axes.unicode_minus"] = False

# 1분봉 결과가 있으면 표에 추가
f1 = ROOT / "research/kr2/data/theme1m.json"
if f1.exists():
    R1 = json.loads(f1.read_text())
    T.insert(1, ("테마대장주 1분", R1["title"], "research/kr2/theme_leader_1m.py", R1["head"], R1["rows"],
                 ("방식", R1["head"][1], "1분봉: 하루 평균 손익 (%)"), R1["concl"]))


def chart_rows(sh, head, rows, ch):
    lc, vc = ch[0], ch[1]
    li, vi = head.index(lc), head.index(vc)
    out = []
    for r in rows:
        lab = r[li]
        if li == 1 and r[0] not in ("-",):
            lab = f"{r[0]} · {r[1]}"
        if sh in ("시총구간",) and r[1] != "-":
            lab = f"{r[0]} · {r[1]}"
        if sh == "시총구간" and r[1] == "-":
            lab = r[0]
        if isinstance(r[vi], (int, float)):
            out.append([lab, r[vi]])
    return out


def bar_png(title, pts, unit):
    n = len(pts)
    fig, ax = plt.subplots(figsize=(7.4, 0.32 * n + 0.9), dpi=170)
    bg = PS.COL["panel"]; fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
    labs = [p[0] for p in pts][::-1]; vals = [p[1] for p in pts][::-1]
    cols = [PS.COL["up"] if v >= 0 else PS.COL["down"] for v in vals]   # 사이트 규칙: 오름 빨강 / 내림 파랑
    ax.barh(range(n), vals, color=cols, height=0.62)
    ax.set_yticks(range(n)); ax.set_yticklabels(labs, color=PS.COL["text"], fontsize=8)
    ax.axvline(0, color=PS.COL["muted"], lw=0.8)
    span = max(abs(min(vals + [0])), abs(max(vals + [0]))) or 1
    for i, v in enumerate(vals):
        ax.text(v + (span * 0.02 if v >= 0 else -span * 0.02), i, f"{v:+g}{unit}", va="center", ha="left" if v >= 0 else "right", color=PS.COL["text"], fontsize=7.5)
    lo, hi = min(vals + [0]), max(vals + [0])
    ax.set_xlim(lo - span * 0.22 if lo < 0 else 0, hi + span * 0.22 if hi > 0 else span * 0.05)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="x", colors=PS.COL["faint"], labelsize=7); ax.tick_params(axis="y", length=0)
    ax.set_title(title, color="#fff", fontsize=9.5, loc="left", pad=8)
    fig.tight_layout()
    b = io.BytesIO(); fig.savefig(b, format="png", facecolor=bg); plt.close(fig)
    return base64.b64encode(b.getvalue()).decode()


# ① xlsx
def build_xlsx(path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = "요약"
    H = Font(bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="3B3F8F"); W = Alignment(wrap_text=True, vertical="top")
    ws["A1"] = "트레이딩 연구 결과 — 한눈에"; ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"{NOW:%Y-%m-%d %H:%M} KST 기준 · 가상 돈 시험 · 숫자는 참고용이며 투자 권유가 아님"; ws["A2"].font = Font(color="666666")
    for c, h in enumerate(["시험", "결론", "자세한 표"], 1):
        x = ws.cell(4, c, h); x.font = H; x.fill = HF
    for i, t in enumerate(T, 5):
        ws.cell(i, 1, t[0]).alignment = W; ws.cell(i, 2, t[6]).alignment = W; ws.cell(i, 3, f"'{t[0]}' 시트").alignment = W
    ws.column_dimensions["A"].width = 16; ws.column_dimensions["B"].width = 110; ws.column_dimensions["C"].width = 16
    ws.freeze_panes = "A5"
    specs = []
    for sh, title, src, head, rows, ch, concl in T:
        s = wb.create_sheet(sh)
        s["A1"] = title; s["A1"].font = Font(bold=True, size=13)
        s["A2"] = f"출처: {src}"; s["A2"].font = Font(color="666666")
        for c, h in enumerate(head, 1):
            x = s.cell(4, c, h); x.font = H; x.fill = HF; x.alignment = W
        for i, r in enumerate(rows, 5):
            for c, v in enumerate(r, 1):
                x = s.cell(i, c, v)
                if isinstance(v, float):
                    x.number_format = "+0.00;-0.00;0.00"
                elif isinstance(v, int) and v >= 1000:
                    x.number_format = "#,##0"
        e = 5 + len(rows) + 1
        s.cell(e, 1, "결론").font = Font(bold=True)
        s.cell(e, 2, concl).alignment = W
        s.merge_cells(start_row=e, start_column=2, end_row=e, end_column=len(head))
        s.row_dimensions[e].height = 48
        s.column_dimensions["A"].width = 26 if sh not in ("테마대장주", "테마대장주 1분", "급등이후") else 8
        for c in range(2, len(head) + 1):
            s.column_dimensions[get_column_letter(c)].width = 30 if c == 2 and sh in ("테마대장주", "테마대장주 1분", "급등이후", "시총구간", "익절시험", "공식점검") else 14
        s.freeze_panes = "A5"
        if ch:
            pts = chart_rows(sh, head, rows, ch)
            c0 = e + 3
            s.cell(c0 - 1, 1, "차트용 표 (위 표에서 가져옴)").font = Font(color="666666")
            s.cell(c0, 1, "항목").font = Font(bold=True); s.cell(c0, 2, ch[1]).font = Font(bold=True)
            for k, (lab, v) in enumerate(pts, 1):
                s.cell(c0 + k, 1, lab); x = s.cell(c0 + k, 2, v); x.number_format = "+0.00;-0.00;0.00"
            specs.append(dict(sheet=sh, range=f"A{c0}:B{c0 + len(pts) + 20}", title=ch[2], n=len(pts), anchor=f"{get_column_letter(len(head) + 2)}1"))
    wb.save(path)
    (path.parent / "chart_specs.json").write_text(json.dumps(specs, ensure_ascii=False, indent=1))
    return specs


# ② 연구 결과 PDF
def research_pdf(path):
    secs = []
    for no, (sh, title, src, head, rows, ch, concl) in enumerate(T, 1):
        th = "".join(f"<th class='{'n' if isinstance(rows[0][i], (int, float)) else ''}'>{h}</th>" for i, h in enumerate(head))
        tb = ""
        for r in rows:
            tb += "<tr>" + "".join(
                f"<td class='n {'up' if v > 0 else 'down' if v < 0 else ''}'>{v:+.2f}</td>" if isinstance(v, float) else
                f"<td class='n'>{v:,}</td>" if isinstance(v, int) else f"<td>{v}</td>" for v in r) + "</tr>"
        html = f"<p class='sm'>{title}<br>출처: {src}</p><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>"
        if ch:
            unit = "R" if "R" in ch[1] else "%"
            html += f"<img src='data:image/png;base64,{bar_png(ch[2], chart_rows(sh, head, rows, ch), unit)}' style='width:100%;border-radius:10px;margin-top:6px'>"
        html += f"<blockquote><b>결론</b> · {concl}</blockquote>"
        secs.append(PS.sec(f"{no:02d}", sh, html))
    summ = "".join(f"<tr><td><b>{t[0]}</b></td><td>{t[6]}</td></tr>" for t in T)
    body = (f"<div class='hero' style='margin-top:4mm'><div class='tk'>K TRADING DESK · 연구 결과 모음</div><h1>우리가 시험한 것들 — 결과표</h1>"
            f"<span class='chip'>{NOW:%Y-%m-%d} 기준</span><span class='chip'>가상 돈 · 참고용</span></div>"
            + PS.sec("", "한눈에", f"<table><tbody>{summ}</tbody></table>") + "".join(secs))
    html = PS.wrap("연구 결과", body)
    return render(html, path)


# ③ 오늘 매매 기록지
def tradebook_pdf(path):
    import tradebook as TB
    a, b = TB.window()
    body = (f"<div class='hero' style='margin-top:4mm'><div class='tk'>K TRADING DESK · 매매 기록지</div><h1>지난 보고서 이후 모든 매매</h1>"
            f"<span class='chip'>{NOW:%Y-%m-%d %H:%M} KST까지</span><span class='chip'>가상 돈</span></div>"
            + PS.sec("", "매매 기록지 — 계좌 성적 · 매매 · 차트 · 피드백", TB.build_html(a, b), "long"))
    return render(PS.wrap("매매 기록지", body, TB.CSS), path)


def render(html, path):
    from playwright.sync_api import sync_playwright
    hp = path.with_suffix(".html"); hp.write_text(html)
    with sync_playwright() as pw:
        br = pw.chromium.launch(); pg = br.new_page()
        pg.goto(hp.resolve().as_uri()); pg.wait_for_timeout(500)
        pg.pdf(path=str(path), format="A4", print_background=True, prefer_css_page_size=True)
        br.close()
    hp.unlink()
    return path


# ④ 묶기
NAMES = dict(ai_chip="AI 반도체", ai_infra="AI 인프라", banks="은행", bio="바이오", clean_ev="친환경·전기차", consumer="소비재", crypto="크립토 관련주",
             cyber="사이버보안", defense="방산", energy="에너지", industrial="산업재", materials="소재", nuclear="원자력", quantum="양자컴퓨터", robot="로봇", software="소프트웨어")


def bundle(parts, path):
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    # 목차 쪽수 먼저 세기 (목차 1쪽 가정, 넘치면 다시)
    counts = [len(PdfReader(str(p)).pages) for _, _, p in parts]
    for toc_pages in (1, 2, 3):
        start, rows = toc_pages + 1, []
        for (grp, lab, p), c in zip(parts, counts):
            rows.append((grp, lab, start, c)); start += c
        html = toc_html(rows, start - 1)
        tp = path.parent / "_toc.pdf"; render(html, tp)
        if len(PdfReader(str(tp)).pages) == toc_pages:
            break
    w = PdfWriter()
    for pg in PdfReader(str(tp)).pages:
        w.add_page(pg)
    for _, _, p in parts:
        for pg in PdfReader(str(p)).pages:
            w.add_page(pg)
    total = len(w.pages)
    # 쪽 번호 (아래 가운데, 작게)
    for i, pg in enumerate(w.pages, 1):
        W_, H_ = float(pg.mediabox.width), float(pg.mediabox.height)
        b = io.BytesIO(); c = canvas.Canvas(b, pagesize=(W_, H_)); c.setFont("Helvetica", 7.5); c.setFillColorRGB(0.6, 0.62, 0.68)
        c.drawCentredString(W_ / 2, 12, f"{i} / {total}"); c.save(); b.seek(0)
        pg.merge_page(PdfReader(b).pages[0])
    w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    w.add_metadata({"/Title": f"K Trading Desk 인쇄 묶음 {NOW:%Y-%m-%d}"})
    with open(path, "wb") as fh:
        w.write(fh)
    tp.unlink()
    return total, rows


def toc_html(rows, total):
    tr, last = "", None
    for grp, lab, s, c in rows:
        if grp != last:
            tr += f"<tr><td colspan=3 style='padding-top:9px'><b style='color:#c9ccff'>{grp}</b></td></tr>"; last = grp
        tr += f"<tr><td style='padding-left:12px'>{lab}</td><td class='n'>{c}쪽</td><td class='n'><b>{s}</b></td></tr>"
    body = (f"<div class='hero' style='margin-top:4mm'><div class='tk'>K TRADING DESK · 인쇄 묶음</div><h1>목차</h1>"
            f"<span class='chip'>{NOW:%Y-%m-%d} 기준</span><span class='chip'>모두 {total}쪽</span><span class='chip'>가상 돈 · 투자 권유 아님</span></div>"
            f"<div class='sec long'><table style='font-size:8.6px'><thead><tr><th>내용</th><th class='n'>분량</th><th class='n'>시작 쪽</th></tr></thead><tbody>{tr}</tbody></table></div>")
    return PS.wrap("목차", body, "td{padding:2px 5px}")


if __name__ == "__main__":
    specs = build_xlsx(OUT / "연구결과.xlsx")
    rp = research_pdf(OUT / "연구결과.pdf")
    tp = tradebook_pdf(OUT / "매매기록지.pdf")
    rep = sorted((ROOT / "reports/pdf").glob("*.pdf"))[-1]
    parts = [("1. 연구 결과", "우리가 시험한 것들 — 결과표·그림", rp),
             ("2. 매매 기록지", "지난 보고서 이후 모든 매매 · 차트 · 피드백", tp),
             ("3. 최근 보고서", rep.stem.replace("_", " "), rep)]
    for d in sorted((ROOT / "reports/longterm").iterdir()):
        if not d.is_dir():
            continue
        nm = NAMES.get(d.name, d.name)
        if (d / "industry.pdf").exists():
            parts.append((f"4. 산업·기업 보고서 — {nm}", f"{nm} 산업 리서치", d / "industry.pdf"))
        for p in sorted(d.glob("*.pdf")):
            if p.name != "industry.pdf":
                parts.append((f"4. 산업·기업 보고서 — {nm}", f"{p.stem} 기업 분석", p))
    total, rows = bundle(parts, OUT / f"인쇄묶음_{NOW:%Y-%m-%d}.pdf")
    print("총", total, "쪽"); print(json.dumps(specs, ensure_ascii=False))
