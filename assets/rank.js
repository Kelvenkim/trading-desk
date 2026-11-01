/* 오늘의 순위 — data/rank/latest.json, report.json 을 읽어 표시 */
const RankUI = (() => {
  const { $, esc, fmtPct, toast, LC_OPTS } = U;
  let L = null, R = null, open = null, filt = { mkt: "all", q: "", n: 50 }, chart = null, loaded = false;
  const pct = (v, d = 1) => (v == null ? "—" : (v >= 0 ? "+" : "") + (v * 100).toFixed(d) + "%");
  const cls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const won = (v) => (v == null ? "—" : Math.round(v).toLocaleString("ko-KR"));
  const eok = (v) => (v == null ? "—" : (v / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 0 }) + "억");

  async function load() {
    const get = async (p) => { const r = await fetch(p + "?t=" + Date.now()); if (!r.ok) throw new Error(p); return r.json(); };
    try { [L, R] = await Promise.all([get("data/rank/latest.json"), get("data/rank/report.json")]); }
    catch (_) { $("#rk-body").innerHTML = `<tr class="empty-row"><td colspan="7">아직 순위 데이터가 없어요. GitHub Actions에서 '매일 순위'를 한 번 실행해주세요.</td></tr>`; return; }
    loaded = true;
    renderTop(); renderTable(); renderWeights(); renderReport();
  }

  function renderTop() {
    const m = L.market;
    $("#rk-date").textContent = `${L.date} 장 마감 기준 · ${L.sources.universe}종목 · 뉴스 ${L.sources.news}종목 · ${L.sources.earn}`;
    const st = (k, v, sub, c = "") => `<div class="stat"><div class="k">${k}</div><div class="v ${c}">${v}</div><div class="sub muted small">${sub}</div></div>`;
    $("#rk-market").innerHTML =
      st("시장 분위기", m.mood.split(" — ")[0], m.mood.split(" — ")[1] || "코스피200·추세·종목 폭 기준") +
      st("코스피200", m.ks200.toFixed(2), `200일선 대비 ${pct(m.ks_vs200)} · 20일 ${pct(m.ks_20d)}`, cls(m.ks_20d)) +
      st("미국 10년 금리", m.tnx.toFixed(2) + "%", `20일 ${m.tnx_20d_bp >= 0 ? "+" : ""}${m.tnx_20d_bp.toFixed(0)}bp`, m.tnx_20d_bp > 0 ? "down" : "up") +
      st("원/달러", won(m.krw), `20일 ${pct(m.krw_20d)}`) +
      st("60일선 위 종목", (m.breadth60 * 100).toFixed(0) + "%", "300종목 중 상승 추세 비율");
    const bf = R.backfill, lv = R.live["20"] || {};
    $("#rk-trust").innerHTML = `
      <div class="trust-stage"><span class="k">신뢰도 단계</span><b>${esc(R.stage)}</b></div>
      <div class="trust-txt">
        ${bf ? `과거 검증(${bf.from.slice(0, 4)}~${bf.to.slice(0, 4)}, ${bf.n}회): 상위 20종목이 20일 뒤 300종목 평균 대비 <b class="${cls(bf.ex20)}">${pct(bf.ex20, 2)}</b>${bf.ex20 >= 0 ? " 더 올랐고" : "로 오히려 덜 올랐고"}, 평균을 이긴 때가 <b>${(bf.beat * 100).toFixed(0)}%</b>였어요.` : "과거 검증 결과가 아직 없어요."}
        <br>실제 운영 채점: 20일 결과 <b>${lv.n || 0}회</b>${lv.n ? ` · 평균 대비 <b class="${cls(lv.ex)}">${pct(lv.ex, 2)}</b> · 이긴 비율 ${(lv.beat * 100).toFixed(0)}%` : " (첫 채점은 20거래일 뒤)"}.
      </div>`;
  }

  // 비중이 음수인 항목(반대로 맞는 항목)은 낮은 값이 점수를 올리므로 이름도 반대로 표시
  const NEG_NAME = { mom: "6개월 부진", hi52: "고점서 많이 빠짐", trend: "추세 약함", volx: "거래 한산", rev: "단기 급등", lowvol: "변동성 큼",
    rate: "금리 흐름 불리", fx: "환율 흐름 불리", news: "뉴스 나쁨", earn: "실적 부진" };
  const why = (f, z) => (z >= 0 ? L.weights[f].name : NEG_NAME[f] || L.weights[f].name);
  function contrib(r) {
    return Object.entries(r.z).map(([f, z]) => [f, z * ((L.weights[f] || {}).weight || 0)]).sort((a, b) => b[1] - a[1]);
  }

  function rows() {
    const q = filt.q.trim();
    return L.rows.filter((r) => (filt.mkt === "all" || (filt.mkt === "KOSPI" ? r.mkt === "KOSPI" : r.mkt !== "KOSPI")) &&
      (!q || r.name.includes(q) || r.code.includes(q)));
  }

  function renderTable() {
    const list = rows(), shown = list.slice(0, filt.n);
    $("#rk-count").textContent = `${list.length}종목 중 ${shown.length}개 표시`;
    $("#rk-more").hidden = shown.length >= list.length;
    $("#rk-body").innerHTML = shown.map((r) => {
      const top = contrib(r).filter(([, v]) => v > 0.004).slice(0, 3);
      const tone = r.v.news == null ? "" : r.v.news > 0.3 ? `<span class="tone up" title="뉴스 분위기 좋음">뉴스+</span>` : r.v.news < -0.3 ? `<span class="tone down" title="뉴스 분위기 나쁨">뉴스−</span>` : "";
      return `<tr data-code="${r.code}" class="${open === r.code ? "open" : ""}">
        <td class="rk-n">${r.rank}</td>
        <td><b>${esc(r.name)}</b> <span class="sub">${r.code} · ${r.mkt === "KOSPI" ? "코스피" : "코스닥"}</span></td>
        <td><div class="scorebar"><b style="width:${r.score.toFixed(0)}%"></b></div><span class="sub">${r.score.toFixed(0)}</span></td>
        <td class="r">${won(r.close)}</td>
        <td class="r ${cls(r.chg)}">${pct(r.chg, 2)}</td>
        <td class="why">${top.map(([f]) => `<span class="fchip">${esc(why(f, r.z[f]))}</span>`).join("")}${tone}</td>
      </tr>${open === r.code ? `<tr class="detail"><td colspan="6">${detail(r)}</td></tr>` : ""}`;
    }).join("") || `<tr class="empty-row"><td colspan="6">조건에 맞는 종목이 없어요.</td></tr>`;
  }

  function detail(r) {
    const W = L.weights, v = r.v;
    const val = {
      mom: v.mom == null ? "—" : pct(v.mom), hi52: v.hi52 == null ? "—" : `고점의 ${(v.hi52 * 100).toFixed(0)}%`, trend: v.trend == null ? "—" : `${v.trend}/4점`,
      volx: v.volx == null ? "—" : `평소의 ${Math.exp(v.volx).toFixed(1)}배`, rev: v.rev == null ? "—" : `5일 ${pct(-v.rev)}`, lowvol: v.lowvol == null ? "—" : `하루 ±${(-v.lowvol * 100).toFixed(1)}%`,
      rate: v.rate == null ? "—" : pct(v.rate, 2), fx: v.fx == null ? "—" : pct(v.fx, 2),
      news: v.news == null ? (r.news_n === 0 ? "최근 뉴스 없음" : "—") : `${v.news > 0 ? "+" : ""}${v.news.toFixed(2)} (${r.news_n}건)`,
      earn: r.earn ? `${r.earn.rep}` : "—",
    };
    const bars = contrib(r).map(([f, c]) => {
      const z = r.z[f], w = (W[f] || {}).weight || 0;
      return `<div class="fbar"><span class="fn">${esc(W[f].name)}</span>
        <span class="fz"><i class="${z >= 0 ? "pos" : "neg"}" style="${z >= 0 ? "left:50%" : `left:${50 + z * 50}%`};width:${Math.abs(z) * 50}%"></i></span>
        <span class="fv">${esc(val[f])}</span><span class="fc ${cls(c)}">${w === 0 ? "비중 0" : (c >= 0 ? "+" : "") + (c * 100).toFixed(1)}</span></div>`;
    }).join("");
    const news = (r.news || []).map((n) => `<li><span class="${cls(n.s)}">${n.s > 0 ? "▲" : n.s < 0 ? "▼" : "·"}</span> <a href="${esc(n.u)}" target="_blank" rel="noopener">${esc(n.t)}</a> <span class="sub">${esc(n.o || "")} ${n.d ? n.d.slice(4, 6) + "/" + n.d.slice(6, 8) : ""}</span></li>`).join("");
    const e = r.earn;
    const earn = e ? `<p class="small">${esc(e.rep)} (공시 ${e.date}) · 영업이익 ${eok(e.op)} (전년 ${eok(e.op_prev)}) · 매출 ${eok(e.rev)} (전년 ${eok(e.rev_prev)})</p>` : `<p class="small muted">실적 데이터 없음${L.sources.earn.includes("키 없음") ? " — DART 키를 넣으면 표시돼요" : ""}</p>`;
    return `<div class="rk-detail">
      <div><h3>항목별 점수 <span class="muted">막대 = 300종목 중 위치, 오른쪽 숫자 = 종합 점수에 더한 몫</span></h3>${bars}</div>
      <div><h3>최근 뉴스</h3>${news ? `<ul class="news">${news}</ul>` : `<p class="small muted">순위 60위 안 종목만 제목을 보여줘요.</p>`}
        <h3>실적</h3>${earn}
        <button class="btn small" data-chart="${r.code}.${r.mkt === "KOSPI" ? "KS" : "KQ"}">차트 보기</button></div>
    </div>`;
  }

  function renderWeights() {
    const W = Object.entries(L.weights).sort((a, b) => Math.abs(b[1].weight) - Math.abs(a[1].weight));
    const mx = Math.max(...W.map(([, v]) => Math.abs(v.weight)), 0.01);
    $("#rk-weights").innerHTML = W.map(([f, v]) => {
      const src = v.n_eff < 3 ? "데이터 없음 · 기본값" : v.n_eff < 24 ? `데이터 ${v.n_eff}개월치 · 기본값 섞임` : `${v.n_eff}개월치`;
      return `<tr title="${esc(v.desc)}"><td>${esc(v.name)}<div class="sub">${esc(v.desc)}</div></td>
        <td class="r"><span class="wbar"><b style="width:${(Math.abs(v.weight) / mx * 100).toFixed(0)}%;${v.weight < 0 ? "background:var(--down)" : ""}"></b></span> ${(v.weight * 100).toFixed(0)}%</td>
        <td class="r ${cls(v.mean_ic)}">${v.n_days ? v.mean_ic.toFixed(3) : "—"}<div class="sub">${src}</div></td>
        <td class="r">${v.n_days ? v.t.toFixed(1) : "—"}</td></tr>`;
    }).join("");
  }

  function renderReport() {
    const bf = R.backfill;
    if (!bf) { $("#rk-report").innerHTML = `<p class="muted">과거 검증 결과가 없어요.</p>`; return; }
    $("#rk-years").innerHTML = `<thead><tr><th>연도</th><th class="r">상위20 − 평균 (20일)</th><th class="r">이긴 비율</th><th class="r">순위 상관</th></tr></thead><tbody>` +
      bf.years.map((y) => `<tr><td>${y.year}</td><td class="r ${cls(y.ex20)}">${pct(y.ex20, 2)}</td><td class="r">${(y.beat * 100).toFixed(0)}%</td><td class="r">${y.ic.toFixed(3)}</td></tr>`).join("") + "</tbody>";
    const lv = R.live["5"] || {}, lv20 = R.live["20"] || {};
    const liveRows = (lv20.recent || lv.recent || []).slice().reverse().slice(0, 12);
    $("#rk-live").innerHTML = liveRows.length
      ? `<thead><tr><th>순위 날짜</th><th class="r">상위20</th><th class="r">300 평균</th><th class="r">차이</th></tr></thead><tbody>` +
        liveRows.map((r) => `<tr><td>${r.date}</td><td class="r ${cls(r.top)}">${pct(r.top)}</td><td class="r ${cls(r.all)}">${pct(r.all)}</td><td class="r ${cls(r.top - r.all)}">${pct(r.top - r.all)}</td></tr>`).join("") + "</tbody>"
      : `<tbody><tr class="empty-row"><td>매일 쌓이는 중이에요. 5거래일 뒤부터 채점 결과가 여기에 나와요.</td></tr></tbody>`;
    $("#rk-live-sum").textContent = lv.n ? `5일 채점 ${lv.n}회 · 평균 대비 ${pct(lv.ex, 2)} · 이긴 비율 ${(lv.beat * 100).toFixed(0)}%` + (lv20.n ? ` / 20일 채점 ${lv20.n}회 · ${pct(lv20.ex, 2)}` : "") : "아직 채점 전";
    drawCurve(bf.curve);
  }

  function drawCurve(curve) {
    const el = $("#rk-curve");
    if (!curve || !curve.length || typeof LightweightCharts === "undefined") return;
    if (chart) { chart.remove(); chart = null; }
    chart = LightweightCharts.createChart(el, { ...LC_OPTS(), timeScale: { borderVisible: false, timeVisible: false } });
    const a = chart.addSeries(LightweightCharts.LineSeries, { color: "#f2b84b", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    const b = chart.addSeries(LightweightCharts.LineSeries, { color: "#8d98b3", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    a.setData(curve.map(([t, x]) => ({ time: t, value: x })));
    b.setData(curve.map(([t, , y]) => ({ time: t, value: y })));
    chart.timeScale().fitContent();
  }

  function init() {
    $("#rk-body").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-chart]");
      if (btn) { window.App && App.openChart(btn.dataset.chart); return; }
      const tr = e.target.closest("tr[data-code]"); if (!tr) return;
      open = open === tr.dataset.code ? null : tr.dataset.code; renderTable();
    });
    $("#rk-q").addEventListener("input", (e) => { filt.q = e.target.value; renderTable(); });
    $("#rk-mkt").addEventListener("change", (e) => { filt.mkt = e.target.value; renderTable(); });
    $("#rk-more").addEventListener("click", () => { filt.n += 100; renderTable(); });
  }
  return { init, onShow: () => { if (!loaded) load(); else if (chart) chart.timeScale().fitContent(); } };
})();
