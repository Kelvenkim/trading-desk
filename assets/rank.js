/* 오늘의 순위 (미국) — data/us/rank.json, rank_report.json, bars.json */
const RankUI = (() => {
  const { $, esc, LC_OPTS } = U;
  let L = null, R = null, B = null, open = null, chart = null, loaded = false, showLv = true;
  const filt = { q: "", n: 50, sort: "t", theme: "" };
  const pct = (v, d = 1) => (v == null || !isFinite(v) ? "—" : (v >= 0 ? "+" : "") + (v * 100).toFixed(d) + "%");
  const cls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const usd = (v) => (v == null ? "—" : "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  const get = async (p) => { const r = await fetch(p + "?t=" + Date.now()); if (!r.ok) throw new Error(p); return r.json(); };

  async function load() {
    try { [L, R] = await Promise.all([get("data/us/rank.json"), get("data/us/rank_report.json")]); }
    catch (_) { $("#rk-body").innerHTML = `<tr class="empty-row"><td colspan="5">아직 순위 자료가 없어요.</td></tr>`; return; }
    loaded = true;
    const LS = { td: "basket", t: "t", m: "m", o: "o" }[L.leader || "td"] || "t";     // 채점으로 승격된 방식을 기본 보기로
    if (!filt.touched) { filt.sort = LS; const sel = $("#rk-sort"); if (sel) sel.value = LS; }
    $("#rk-theme-f").innerHTML = `<option value="">모든 테마</option>` + Object.entries(L.themes).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
    renderTop(); renderTable(); renderTrack();
  }

  function renderTop() {
    $("#rk-date").textContent = `${L.date} 미국장 종가 기준 · S&P500·나스닥100 ${L.rows.length}종목`;
    const VB = (R.variants_backfill || {}).variants || {}, vt = (VB["테마 눌림"] || {})["20"] || {}, vm = (VB["12-1 모멘텀"] || {})["20"] || {}, vo = (VB["우리 점수"] || {})["20"] || {};
    const g = L.regime || {};
    $("#rk-trust").innerHTML = `
      <div class="trust-stage"><span class="k">기본</span><b>테마 눌림</b><span class="k">강한 테마 + 최근 5일 눌림</span></div>
      <div class="trust-txt">
        미국 과거 검증(2016~2026, 다음 날 시가 매수): 상위 20이 20일 뒤 평균보다 <b class="up">${pct(vt.ex, 2)}</b>, 11년 중 ${vt.years_pos || "—"}년 플러스, 상승장·하락장 모두 플러스.
        12-1 모멘텀 ${pct(vm.ex, 2)}, 우리 점수 ${pct(vo.ex, 2)}.
        <br>시장: S&P500이 200일선 ${g.up ? "위" : "아래"} (${pct(g.sp_vs200)}). 순위는 상대 비교라 시장 전체가 빠지면 같이 빠져요.
        <span class="muted small">지금 지수에 남은 종목·지금 테마 구성으로 계산해 실제보다 좋게 나왔을 수 있어요.</span>
      </div>`;
  }

  function reasons(r) {
    const out = [];
    if (r.basket) out.push(["바구니", "on"]);
    if (r.theme_pct != null && r.theme_pct >= 0.75) out.push(["강한 테마", ""]); else if (r.theme_pct != null && r.theme_pct <= 0.25) out.push(["약한 테마", "neg"]);
    if (r.rev5 <= -0.03) out.push([`5일 ${pct(r.rev5, 0)}`, ""]);
    if (r.mom != null && r.mom >= 85) out.push(["1년 강세", ""]);
    if (r.parts.trend >= 20) out.push(["추세 좋음", ""]); else if (r.parts.trend <= 5) out.push(["추세 꺾임", "neg"]);
    return out;
  }
  const spark = (a) => {
    const v = (a || []).filter((x) => x != null); if (v.length < 2) return "";
    const lo = Math.min(...v), hi = Math.max(...v), w = 76, h = 22;
    const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - (hi > lo ? (x - lo) / (hi - lo) : 0.5) * h).toFixed(1)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><polyline points="${pts}" fill="none" stroke="${v[v.length - 1] >= v[0] ? "var(--up)" : "var(--down)"}" stroke-width="1.5"/></svg>`;
  };

  function list() {
    const q = filt.q.trim().toLowerCase();
    let rows = L.rows;
    if (filt.sort === "basket") rows = rows.filter((r) => r.basket);
    if (filt.sort === "m") rows = rows.slice().sort((a, b) => (b.mom ?? -1) - (a.mom ?? -1));
    if (filt.sort === "o") rows = rows.slice().sort((a, b) => b.ours - a.ours);
    return rows.filter((r) => (!filt.theme || r.theme === filt.theme) &&
      (!q || r.code.toLowerCase().includes(q) || (r.name || "").toLowerCase().includes(q) || (r.ko || "").includes(filt.q.trim())));
  }

  function renderTable() {
    const all = list(), shown = all.slice(0, filt.n);
    $("#rk-count").textContent = `${all.length}종목 중 ${shown.length}개`;
    $("#rk-more").hidden = shown.length >= all.length;
    $("#rk-body").innerHTML = shown.map((r, i) => `
      <tr data-code="${r.code}" class="${open === r.code ? "open" : ""}">
        <td class="rk-n">${i + 1}</td>
        <td><b>${esc(r.ko || r.code)}</b> <span class="sub">${esc(r.code)}${r.ko ? "" : " · " + esc((r.name || "").slice(0, 28))}</span>
          <div class="sub">${r.theme ? `<span class="rk-theme" data-theme="${r.theme}">${esc(L.themes[r.theme])}</span>` : esc(r.sector || "")}</div></td>
        <td class="rk-score"><span class="tp ${filt.sort === "t" || filt.sort === "basket" ? "on" : ""}"><b>${Math.floor(r.tp)}</b><span class="sub">테마 눌림</span></span>
          <span class="tp ${filt.sort === "m" ? "on" : ""}"><b>${r.mom != null ? Math.floor(r.mom) : "—"}</b><span class="sub">모멘텀</span></span>
          <span class="ours ${filt.sort === "o" ? "on" : ""}"><span class="grade g-${r.grade}">${r.grade}</span></span></td>
        <td class="r rk-px">${spark(r.spark)}<span><b>${usd(r.close)}</b><span class="${cls(r.chg)} small">${pct(r.chg, 2)}</span></span></td>
        <td class="why">${reasons(r).map(([t, c]) => `<span class="fchip ${c}">${t}</span>`).join("")}</td>
      </tr>${open === r.code ? `<tr class="detail"><td colspan="5">${detail(r)}</td></tr>` : ""}`).join("")
      || `<tr class="empty-row"><td colspan="5">조건에 맞는 종목이 없어요.</td></tr>`;
    if (open) drawStock(L.rows.find((r) => r.code === open));
  }

  function detail(r) {
    const D = L.ours_def || {};
    const parts = Object.entries(D).map(([k, d]) => `<div class="pbar" title="${esc(d.desc)}"><span class="pn">${esc(d.name)}</span>
      <span class="pt"><i style="width:${r.parts[k] / d.max * 100}%;background:#fff"></i></span><span class="pv"><b>${r.parts[k].toFixed(0)}</b>/${d.max}</span></div>`).join("");
    return `<div class="rk-detail">
      <div class="rk-chartbox">
        <div class="rk-chart-head"><b>${esc(r.ko || r.code)}</b> <span class="muted small">${esc(r.name || "")} · 최근 6개월 일봉</span>
          <button class="btn small ${showLv ? "on" : ""}" data-lv>${showLv ? "선 숨기기" : "선 보이기"}</button>
          <button class="btn small" data-chart="${esc(r.code)}">차트에서 크게 보기</button></div>
        <div class="rk-chart" id="rk-stock-chart"><span class="muted small">불러오는 중…</span></div>
        <div class="rk-legend small"><span><i class="lg sup"></i>지지선</span><span><i class="lg res"></i>저항선</span><span><i class="lg tl"></i>추세선</span><span><i class="lg zone"></i>매수 구간</span><span><i class="lg stop"></i>손절</span><span><i class="lg tgt"></i>목표</span></div>
        <div id="rk-plan"></div>
      </div>
      <div>
        <h3>점수</h3>
        <div class="kv2"><span>테마 눌림</span><b>${Math.floor(r.tp)} / 100</b></div>
        <div class="kv2"><span>소속 테마의 힘</span><b>${r.theme_pct != null ? Math.round(r.theme_pct * 100) + " / 100" : "테마 없음"}</b></div>
        <div class="kv2"><span>최근 5일</span><b class="${cls(r.rev5)}">${pct(r.rev5)}</b></div>
        <div class="kv2"><span>12-1 모멘텀</span><b>${r.mom != null ? Math.floor(r.mom) + " / 100" : "—"}</b></div>
        <h3>우리 점수 <span class="grade g-${r.grade}">${r.grade}</span> <span class="muted small">종목 상태 점검</span></h3>${parts}
        <p class="hint">테마 눌림 = 강한 장기 테마에 속하면서 최근 며칠 쉬어간 정도(종목 중 위치). 우리 점수는 맞히는 용도가 아니라 위험 점검용이에요.</p>
      </div>
    </div>`;
  }

  async function drawStock(r) {
    const el = $("#rk-stock-chart"); if (!el || !r) return;
    if (!B) {
      try { B = await get("data/us/bars.json"); } catch (_) { el.innerHTML = `<span class="muted small">차트 자료를 불러오지 못했어요.</span>`; return; }
      if (open !== r.code) return;
    }
    const rows = (B.bars[r.code] || []).map((x, i) => x && { time: B.days[i], open: x[0], high: x[1], low: x[2], close: x[3], value: x[4] }).filter(Boolean);
    if (!rows.length) { el.innerHTML = `<span class="muted small">차트 자료 없음</span>`; return; }
    el.innerHTML = "";
    if (chart) { try { chart.remove(); } catch (_) {} }
    const LC = LightweightCharts;
    chart = LC.createChart(el, { ...LC_OPTS(), timeScale: { borderColor: "#2a2a2e", timeVisible: false }, localization: { locale: "ko-KR", priceFormatter: (p) => "$" + p.toFixed(2) } });
    const cs = chart.addSeries(LC.CandlestickSeries, { upColor: "#f0525c", downColor: "#3d8bfd", borderVisible: false, wickUpColor: "#f0525c", wickDownColor: "#3d8bfd", priceLineVisible: false });
    cs.setData(rows);
    const vs = chart.addSeries(LC.HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    vs.setData(rows.map((b) => ({ time: b.time, value: b.value, color: b.close >= b.open ? "rgba(240,82,92,.35)" : "rgba(61,139,253,.35)" })));
    const ma = (n, color) => chart.addSeries(LC.LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      .setData(rows.map((b, i) => i >= n - 1 ? { time: b.time, value: rows.slice(i - n + 1, i + 1).reduce((a, x) => a + x.close, 0) / n } : null).filter(Boolean));
    ma(20, "#ffffff"); ma(60, "#6e6e76");
    const bb = rows.map((x) => ({ t: x.time, day: x.time, ms: Date.parse(x.time + "T00:00:00Z"), o: x.open, h: x.high, l: x.low, c: x.close, v: x.value }));
    let A = null;
    try { A = Levels.analyze(bb, { marketUp: (L.regime || {}).up !== false }); } catch (e) { console.error(e); }
    if (A && showLv) Levels.draw(chart, cs, rows.map((x) => x.time), A, (mk) => LC.createSeriesMarkers && mk.length && LC.createSeriesMarkers(cs, mk));
    const pl = $("#rk-plan"); if (pl) pl.innerHTML = Levels.planHTML(A);
    chart.timeScale().fitContent();
  }

  function renderTrack() {
    const el = $("#rk-track"); if (!el) return;
    const T = (R.track || []).slice().reverse(), V = R.variants || {}, VB = (R.variants_backfill || {}).variants || {};
    const st = (k, h) => { const x = (V[k] || {})[h]; return x ? `${pct(x.ex, 2)} <span class="sub">${x.n}회 · 이김 ${(x.beat * 100).toFixed(0)}%${x.t != null ? ` · t ${x.t.toFixed(1)}` : ""}</span>` : `<span class="muted">채점 전</span>`; };
    const bf = (k) => pct(((VB[k] || {})["20"] || {}).ex, 2);
    el.innerHTML = `
      <table class="tbl"><thead><tr><th>올린 날</th><th class="r">경과</th><th class="r">바구니 20</th><th class="r">테마 눌림</th><th class="r">모멘텀</th><th class="r">전체 평균</th></tr></thead><tbody>
      ${T.map((t) => `<tr><td>${t.date}</td><td class="r">${t.days}일</td>
        <td class="r ${cls(t.td)}"><b>${pct(t.td)}</b> <span class="sub">(${pct(t.td - t.all)})</span></td>
        <td class="r ${cls(t.t)}">${pct(t.t)}</td><td class="r ${cls(t.m)}">${pct(t.m)}</td><td class="r ${cls(t.all)}">${pct(t.all)}</td></tr>`).join("") || `<tr class="empty-row"><td colspan="6">다음 거래일부터 추적이 시작돼요.</td></tr>`}
      </tbody></table>
      <p class="hint">올린 다음 날 시가에 상위 20을 샀다고 보고 최근 종가까지. 괄호는 전체 평균 대비. 매일 갱신돼요.</p>
      <h3>채점 결과 <span class="muted small">상위 20 − 전체 평균</span></h3>
      <table class="tbl"><thead><tr><th>방식</th><th class="r">5일</th><th class="r">20일</th><th class="r">과거 20일</th></tr></thead><tbody>
        <tr><td>바구니 <span class="sub">기본</span></td><td class="r">${st("td", "5")}</td><td class="r">${st("td", "20")}</td><td class="r">—</td></tr>
        <tr><td>테마 눌림</td><td class="r">${st("t", "5")}</td><td class="r">${st("t", "20")}</td><td class="r">${bf("테마 눌림")}</td></tr>
        <tr><td>12-1 모멘텀</td><td class="r">${st("m", "5")}</td><td class="r">${st("m", "20")}</td><td class="r">${bf("12-1 모멘텀")}</td></tr>
        <tr><td>우리 점수</td><td class="r">${st("o", "5")}</td><td class="r">${st("o", "20")}</td><td class="r">${bf("우리 점수")}</td></tr>
      </tbody></table>
      <p class="hint">매일 순위를 기록하고 1·5·20일 뒤 실제 수익으로 채점해요. 20일 채점이 40번 넘게 쌓이고 다른 방식이 같은 날 비교로 확실성(t) 2 이상 앞서면 자동으로 기본을 바꿔요.
        <br><b>지금:</b> ${esc(L.leader_why || "채점 대기 중")}</p>`;
  }

  function init() {
    $("#rk-body").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-chart]"); if (btn) { window.App && App.openChart(btn.dataset.chart); return; }
      if (e.target.closest("[data-lv]")) { showLv = !showLv; renderTable(); return; }
      const th = e.target.closest("[data-theme]"); if (th) { window.App && App.showTheme(th.dataset.theme); return; }
      if (e.target.closest("a, .rk-chartbox")) return;
      const tr = e.target.closest("tr[data-code]"); if (!tr) return;
      open = open === tr.dataset.code ? null : tr.dataset.code;
      if (!open && chart) { try { chart.remove(); } catch (_) {} chart = null; }
      renderTable(); if (open) tr.scrollIntoView({ block: "nearest" });
    });
    $("#rk-q").addEventListener("input", (e) => { filt.q = e.target.value; renderTable(); });
    $("#rk-sort").addEventListener("change", (e) => { filt.sort = e.target.value; filt.touched = true; renderTable(); });
    $("#rk-theme-f").addEventListener("change", (e) => { filt.theme = e.target.value; renderTable(); });
    $("#rk-more").addEventListener("click", () => { filt.n += 100; renderTable(); });
  }
  return { init, onShow: () => { if (!loaded) load(); } };
})();
