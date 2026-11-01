/* 오늘의 순위 — 우리 점수(100점 고정 규칙) + 검증된 항목만 쓰는 검증 순위 */
const RankUI = (() => {
  const { $, esc, LC_OPTS } = U;
  let L = null, R = null, B = null, open = null, chart = null, loaded = false;
  const filt = { mkt: "all", q: "", n: 50, grade: "all" };
  const pct = (v, d = 1) => (v == null ? "—" : (v >= 0 ? "+" : "") + (v * 100).toFixed(d) + "%");
  const cls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const won = (v) => (v == null ? "—" : Math.round(v).toLocaleString("ko-KR"));
  const eok = (v) => (v == null ? "—" : (v / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 0 }) + "억");
  const PART_COLOR = { trend: "#f2b84b", earn: "#5ac8a8", news: "#b48cf2", flow: "#f0525c", safe: "#3d8bfd" };
  const sym = (r) => `${r.code}.${r.mkt === "KOSPI" ? "KS" : "KQ"}`;

  async function load() {
    const get = async (p) => { const r = await fetch(p + "?t=" + Date.now()); if (!r.ok) throw new Error(p); return r.json(); };
    try { [L, R] = await Promise.all([get("data/rank/latest.json"), get("data/rank/report.json")]); }
    catch (_) { $("#rk-body").innerHTML = `<tr class="empty-row"><td colspan="6">아직 순위 데이터가 없어요. GitHub Actions에서 '매일 순위'를 한 번 실행해주세요.</td></tr>`; return; }
    loaded = true;
    renderTop(); renderTable(); renderSide(); renderReport();
  }

  // ---------- 위쪽: 시장 + 신뢰도 ----------
  function renderTop() {
    const m = L.market;
    $("#rk-date").textContent = `${L.date} 장 마감 기준 · ${L.sources.universe}종목 · 뉴스 ${L.sources.news}종목 · ${L.sources.earn}`;
    const st = (k, v, sub, c = "") => `<div class="stat"><div class="k">${k}</div><div class="v ${c}">${v}</div><div class="sub muted small">${sub}</div></div>`;
    $("#rk-market").innerHTML =
      st("시장 분위기", m.mood.split(" — ")[0], m.mood.split(" — ")[1] || "코스피200·추세·종목 폭 기준") +
      st("코스피200", m.ks200.toFixed(2), `200일선 대비 ${pct(m.ks_vs200)} · 20일 ${pct(m.ks_20d)}`, cls(m.ks_20d)) +
      st("미국 10년 금리", m.tnx.toFixed(2) + "%", `20일 ${m.tnx_20d_bp >= 0 ? "+" : ""}${m.tnx_20d_bp.toFixed(0)}bp`) +
      st("원/달러", won(m.krw), `20일 ${pct(m.krw_20d)}`) +
      st("60일선 위 종목", (m.breadth60 * 100).toFixed(0) + "%", "300종목 중 상승 추세 비율");
    const bf = R.backfill, lv = R.live["20"] || {};
    const nAct = Object.values(L.weights).filter((w) => w.active).length;
    $("#rk-trust").innerHTML = `
      <div class="trust-stage"><span class="k">검증된 항목</span><b>${nAct}개 / ${Object.keys(L.weights).length}</b></div>
      <div class="trust-txt">
        ${nAct ? `확실성(t) ${L.t_min} 이상으로 검증된 항목만 써서 <b>검증 순위</b>를 만들었어요.` : `아직 <b>확실하게 맞는다고 검증된 항목이 없어서</b> 검증 순위는 비워 뒀어요. 아래 목록은 '우리 점수' 규칙으로 정렬한 거예요.`}
        ${bf ? `<br>우리 점수 상위 20종목의 과거 성적(${bf.from.slice(0, 4)}~${bf.to.slice(0, 4)}, 실적·뉴스 제외): 20일 뒤 300종목 평균 대비 <b class="${cls(bf.ex20)}">${pct(bf.ex20, 2)}</b>, 평균을 이긴 때 ${(bf.beat * 100).toFixed(0)}%.` : ""}
        <br>실제 운영 채점: 20일 결과 <b>${lv.n || 0}회</b>${lv.n ? ` · 평균 대비 <b class="${cls(lv.ex)}">${pct(lv.ex, 2)}</b>` : " (첫 채점은 20거래일 뒤)"}.
      </div>`;
  }

  // ---------- 목록 ----------
  function reasons(r) {
    const p = r.parts, out = [];
    if (p.trend >= 20) out.push(["추세 좋음", ""]); else if (p.trend <= 5) out.push(["추세 꺾임", "neg"]);
    if (p.earn >= 20) out.push(["실적 성장", ""]); else if (p.earn <= 8) out.push(["실적 감소", "neg"]);
    if (p.news >= 16) out.push(["뉴스 호재", ""]); else if (p.news <= 5) out.push(["뉴스 악재", "neg"]);
    if (p.flow >= 12) out.push(["거래 실린 상승", ""]); else if (p.flow <= 2) out.push(["거래 실린 하락", "neg"]);
    if (p.safe >= 12) out.push(["안정적", ""]); else if (p.safe <= 3) out.push(["변동 큼", "neg"]);
    return out;
  }
  const spark = (a) => {
    const v = a.filter((x) => x != null); if (v.length < 2) return "";
    const lo = Math.min(...v), hi = Math.max(...v), w = 76, h = 22;
    const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - (hi > lo ? (x - lo) / (hi - lo) : 0.5) * h).toFixed(1)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><polyline points="${pts}" fill="none" stroke="${v[v.length - 1] >= v[0] ? "var(--up)" : "var(--down)"}" stroke-width="1.5"/></svg>`;
  };
  const stack = (r) => Object.keys(L.ours_def).map((k) => `<i style="width:${r.parts[k]}%;background:${PART_COLOR[k]}" title="${esc(L.ours_def[k].name)} ${r.parts[k].toFixed(0)}/${L.ours_def[k].max}"></i>`).join("");

  function list() {
    const q = filt.q.trim();
    return L.rows.filter((r) => (filt.mkt === "all" || (filt.mkt === "KOSPI" ? r.mkt === "KOSPI" : r.mkt !== "KOSPI")) &&
      (filt.grade === "all" || filt.grade.includes(r.grade)) && (!q || r.name.includes(q) || r.code.includes(q)));
  }

  function renderTable() {
    const all = list(), shown = all.slice(0, filt.n);
    $("#rk-count").textContent = `${all.length}종목 중 ${shown.length}개 표시`;
    $("#rk-more").hidden = shown.length >= all.length;
    $("#rk-body").innerHTML = shown.map((r, i) => `
      <tr data-code="${r.code}" class="${open === r.code ? "open" : ""}">
        <td class="rk-n">${L.rows.indexOf(r) + 1}</td>
        <td><b>${esc(r.name)}</b> <span class="sub">${r.code} · ${r.mkt === "KOSPI" ? "코스피" : "코스닥"}</span></td>
        <td class="rk-score"><span class="grade g-${r.grade}">${r.grade}</span><b>${Math.floor(r.ours)}</b><span class="stack">${stack(r)}</span></td>
        <td class="r rk-px">${spark(r.spark)}<span><b>${won(r.close)}</b><span class="${cls(r.chg)} small">${pct(r.chg, 2)}</span></span></td>
        <td class="why">${reasons(r).map(([t, c]) => `<span class="fchip ${c}">${t}</span>`).join("")}</td>
      </tr>${open === r.code ? `<tr class="detail"><td colspan="5">${detail(r)}</td></tr>` : ""}`).join("")
      || `<tr class="empty-row"><td colspan="5">조건에 맞는 종목이 없어요.</td></tr>`;
    if (open) drawStock(L.rows.find((r) => r.code === open));
  }

  function detail(r) {
    const D = L.ours_def;
    const parts = Object.entries(D).map(([k, d]) => {
      const v = r.parts[k];
      let note = "";
      if (k === "earn" && !r.earn) note = "자료 없음 → 중간값";
      if (k === "news" && !r.news_n) note = "최근 기사 없음 → 중간값";
      if (k === "trend") note = r.v.trend != null ? `52주 고점의 ${(r.v.hi52 * 100).toFixed(0)}%` : "";
      if (k === "flow") note = `5일 ${pct(-r.v.rev)} · 거래량 ${Math.exp(r.v.volx || 0).toFixed(1)}배`;
      if (k === "safe") note = r.v.lowvol != null ? `하루 ±${(-r.v.lowvol * 100).toFixed(1)}%` : "";
      return `<div class="pbar" title="${esc(d.desc)}"><span class="pn">${esc(d.name)}</span>
        <span class="pt"><i style="width:${v / d.max * 100}%;background:${PART_COLOR[k]}"></i></span>
        <span class="pv"><b>${v.toFixed(0)}</b>/${d.max}</span><span class="pnote">${esc(note)}</span></div>`;
    }).join("");
    const news = (r.news || []).map((n) => `<li><span class="${cls(n.s)}">${n.s > 0 ? "▲" : n.s < 0 ? "▼" : "·"}</span> <a href="${esc(n.u)}" target="_blank" rel="noopener">${esc(n.t)}</a> <span class="sub">${esc(n.o || "")} ${n.d ? n.d.slice(4, 6) + "/" + n.d.slice(6, 8) : ""}</span></li>`).join("");
    const e = r.earn;
    const earn = e ? `<p class="small">${esc(e.rep)} (공시 ${e.date}) · 영업이익 ${eok(e.op)} (전년 ${eok(e.op_prev)}) · 매출 ${eok(e.rev)} (전년 ${eok(e.rev_prev)})</p>`
      : `<p class="small muted">실적 자료 없음${L.sources.earn.includes("키 없음") ? " — DART 키를 넣으면 표시돼요" : ""}</p>`;
    return `<div class="rk-detail">
      <div class="rk-chartbox">
        <div class="rk-chart-head"><b>${esc(r.name)}</b> <span class="muted small">최근 6개월 일봉 · 20일선(금색)·60일선(파랑)</span>
          <button class="btn small" data-chart="${sym(r)}">차트 탭에서 크게 보기</button></div>
        <div class="rk-chart" id="rk-stock-chart"><span class="muted small">불러오는 중…</span></div>
      </div>
      <div>
        <h3>우리 점수 ${Math.floor(r.ours)}점 <span class="grade g-${r.grade}">${r.grade}</span></h3>${parts}
        <h3>최근 뉴스</h3>${news ? `<ul class="news">${news}</ul>` : `<p class="small muted">${r.news_n === 0 ? "최근 3일 기사 없음" : "60위 안 종목만 제목을 보여줘요."}</p>`}
        <h3>실적</h3>${earn}
      </div>
    </div>`;
  }

  async function drawStock(r) {
    const el = $("#rk-stock-chart"); if (!el || !r) return;
    if (!B) {
      try { B = await (await fetch("data/rank/bars.json?t=" + L.date)).json(); }
      catch (_) { el.innerHTML = `<span class="muted small">차트 자료를 불러오지 못했어요.</span>`; return; }
      if (open !== r.code) return;
    }
    const rows = (B.bars[r.code] || []).map((x, i) => x && { time: B.days[i], open: x[0], high: x[1], low: x[2], close: x[3], value: x[4] }).filter(Boolean);
    if (!rows.length || typeof LightweightCharts === "undefined") { el.innerHTML = `<span class="muted small">차트 자료 없음</span>`; return; }
    el.innerHTML = "";
    if (chart) { try { chart.remove(); } catch (_) {} }
    const LC = LightweightCharts;
    chart = LC.createChart(el, { ...LC_OPTS(), timeScale: { borderColor: "#253049", timeVisible: false }, localization: { locale: "ko-KR", priceFormatter: (p) => Math.round(p).toLocaleString("ko-KR") } });
    const cs = chart.addSeries(LC.CandlestickSeries, { upColor: "#f0525c", downColor: "#3d8bfd", borderVisible: false, wickUpColor: "#f0525c", wickDownColor: "#3d8bfd", priceLineVisible: false });
    cs.setData(rows);
    const vs = chart.addSeries(LC.HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    vs.setData(rows.map((b) => ({ time: b.time, value: b.value, color: b.close >= b.open ? "rgba(240,82,92,.35)" : "rgba(61,139,253,.35)" })));
    const ma = (n, color) => {
      const s = chart.addSeries(LC.LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(rows.map((b, i) => i >= n - 1 ? { time: b.time, value: rows.slice(i - n + 1, i + 1).reduce((a, x) => a + x.close, 0) / n } : null).filter(Boolean));
    };
    ma(20, "#f2b84b"); ma(60, "#3d8bfd");
    chart.timeScale().fitContent();
  }

  // ---------- 오른쪽: 점수 기준 + 검증 항목 ----------
  function renderSide() {
    $("#rk-def").innerHTML = Object.entries(L.ours_def).map(([k, d]) => `
      <div class="defrow"><span class="dot" style="background:${PART_COLOR[k]}"></span><b>${esc(d.name)}</b><span class="muted small">${d.max}점</span>
      <div class="sub">${esc(d.desc)}</div></div>`).join("") +
      `<div class="sub" style="margin-top:8px">등급: S 80↑ · A 70↑ · B 60↑ · C 45↑ · D 그 아래</div>`;
    const W = Object.entries(L.weights).sort((a, b) => Math.abs(b[1].t) - Math.abs(a[1].t));
    $("#rk-weights").innerHTML = W.map(([f, v]) => {
      const src = v.n_days ? `${v.n_eff}개월치` : "아직 자료 없음";
      return `<tr title="${esc(v.desc)}"><td>${esc(v.name)}<div class="sub">${src}</div></td>
        <td class="r ${cls(v.mean_ic)}">${v.n_days ? v.mean_ic.toFixed(3) : "—"}</td>
        <td class="r">${v.n_days ? v.t.toFixed(1) : "—"}</td>
        <td class="r">${v.active ? `<span class="ok">사용 ${(v.weight * 100).toFixed(0)}%</span>` : `<span class="muted small">대기</span>`}</td></tr>`;
    }).join("");
  }

  function renderReport() {
    const bf = R.backfill;
    if (!bf) { $("#rk-years").innerHTML = ""; return; }
    const G = bf.grades || {};
    $("#rk-grades").innerHTML = `<thead><tr><th>등급</th>${"SABCD".split("").map((g) => `<th class="r"><span class="grade g-${g}">${g}</span></th>`).join("")}</tr></thead>
      <tbody><tr><td class="small">20일 뒤<br>평균 대비</td>${"SABCD".split("").map((g) => `<td class="r ${cls(G[g])}">${G[g] == null ? "—" : pct(G[g], 2)}</td>`).join("")}</tr></tbody>`;
    const P = bf.parts || {};
    $("#rk-parts").innerHTML = Object.entries(L.ours_def).map(([k, d]) => `<span class="fchip ${P[k] == null ? "" : P[k] < 0 ? "neg" : ""}">${esc(d.name)} ${P[k] == null ? "검증 전" : "IC " + P[k].toFixed(3)}</span>`).join("");
    $("#rk-years").innerHTML = `<thead><tr><th>연도</th><th class="r">상위20 − 평균 (20일)</th><th class="r">이긴 비율</th></tr></thead><tbody>` +
      bf.years.map((y) => `<tr><td>${y.year}</td><td class="r ${cls(y.ex20)}">${pct(y.ex20, 2)}</td><td class="r">${(y.beat * 100).toFixed(0)}%</td></tr>`).join("") + "</tbody>";
    const lv = R.live["20"] || {}, lv5 = R.live["5"] || {};
    const rows = ((lv.recent && lv.recent.length ? lv.recent : lv5.recent) || []).slice().reverse().slice(0, 12);
    $("#rk-live").innerHTML = rows.length
      ? `<thead><tr><th>순위 날짜</th><th class="r">상위20</th><th class="r">300 평균</th><th class="r">차이</th></tr></thead><tbody>` +
        rows.map((r) => `<tr><td>${r.date}</td><td class="r ${cls(r.top)}">${pct(r.top)}</td><td class="r ${cls(r.all)}">${pct(r.all)}</td><td class="r ${cls(r.top - r.all)}">${pct(r.top - r.all)}</td></tr>`).join("") + "</tbody>"
      : `<tbody><tr class="empty-row"><td>매일 쌓이는 중이에요. 5거래일 뒤부터 채점 결과가 여기에 나와요.</td></tr></tbody>`;
    $("#rk-live-sum").textContent = lv5.n ? `5일 채점 ${lv5.n}회 · 평균 대비 ${pct(lv5.ex, 2)}` + (lv.n ? ` / 20일 ${lv.n}회 · ${pct(lv.ex, 2)}` : "") : "아직 채점 전";
    drawCurve(bf.curve);
  }

  let curveChart = null;
  function drawCurve(curve) {
    const el = $("#rk-curve");
    if (!curve || !curve.length || typeof LightweightCharts === "undefined") return;
    if (curveChart) curveChart.remove();
    curveChart = LightweightCharts.createChart(el, { ...LC_OPTS(), timeScale: { borderVisible: false, timeVisible: false } });
    const a = curveChart.addSeries(LightweightCharts.LineSeries, { color: "#f2b84b", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    const b = curveChart.addSeries(LightweightCharts.LineSeries, { color: "#8d98b3", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    a.setData(curve.map(([t, x]) => ({ time: t, value: x })));
    b.setData(curve.map(([t, , y]) => ({ time: t, value: y })));
    curveChart.timeScale().fitContent();
  }

  function init() {
    $("#rk-body").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-chart]");
      if (btn) { window.App && App.openChart(btn.dataset.chart); return; }
      if (e.target.closest("a, .rk-chartbox")) return;
      const tr = e.target.closest("tr[data-code]"); if (!tr) return;
      open = open === tr.dataset.code ? null : tr.dataset.code;
      if (!open && chart) { try { chart.remove(); } catch (_) {} chart = null; }
      renderTable();
      if (open) tr.scrollIntoView({ block: "nearest" });
    });
    $("#rk-q").addEventListener("input", (e) => { filt.q = e.target.value; renderTable(); });
    $("#rk-mkt").addEventListener("change", (e) => { filt.mkt = e.target.value; renderTable(); });
    $("#rk-grade").addEventListener("change", (e) => { filt.grade = e.target.value; renderTable(); });
    $("#rk-more").addEventListener("click", () => { filt.n += 100; renderTable(); });
  }
  return { init, onShow: () => { if (!loaded) load(); } };
})();
