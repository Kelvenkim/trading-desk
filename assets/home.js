/* 홈 — 오늘의 미국 시장 한눈에 */
const HomeUI = (() => {
  const { $, esc } = U;
  let M = null, R = null, T = null, N = null, loaded = false, secSpan = "d1";
  const pct = (v, d = 1) => (v == null || !isFinite(v) ? "—" : (v >= 0 ? "+" : "") + (v * 100).toFixed(d) + "%");
  const cls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const num = (v, t) => (v == null ? "—" : t === "^TNX" ? v.toFixed(2) + "%" : t === "KRW=X" ? Math.round(v).toLocaleString("ko-KR") + "원" :
    v >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v.toLocaleString("en-US", { maximumFractionDigits: 2 }));
  const usd = (v) => (v == null ? "—" : "$" + v.toLocaleString("en-US", { maximumFractionDigits: 2 }));
  const spark = (a, w = 92, h = 26) => {
    const v = (a || []).filter((x) => x != null); if (v.length < 2) return "";
    const lo = Math.min(...v), hi = Math.max(...v);
    const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - (hi > lo ? (x - lo) / (hi - lo) : 0.5) * h).toFixed(1)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><polyline points="${pts}" fill="none" stroke="${v[v.length - 1] >= v[0] ? "var(--up)" : "var(--down)"}" stroke-width="1.5"/></svg>`;
  };
  const get = async (p) => { const r = await fetch(p + "?t=" + Date.now()); if (!r.ok) throw new Error(p); return r.json(); };

  async function load() {
    [M, R, T, N] = await Promise.all(["data/us/market.json", "data/us/rank.json", "data/us/theme.json", "data/news/latest.json"].map((p) => get(p).catch(() => null)));
    loaded = true; render(); liveAssets();
  }

  function status() {
    const m = U.usMarket();
    $("#hm-status").innerHTML = `<span class="live-dot ${m.live ? "on" : ""}"></span>미국장 <b>${m.state}</b> · 뉴욕 ${m.ny} · 한국 ${m.kst}${M ? ` · 종가 기준 ${M.date}` : ""}`;
  }

  function render() {
    status();
    if (!M) { $("#hm-assets").innerHTML = `<p class="muted">시장 자료가 아직 없어요.</p>`; return; }
    $("#hm-assets").innerHTML = M.assets.map((a) => `<button class="hm-asset" data-sym="${esc(a.t)}" id="as-${esc(a.t.replace(/[^A-Za-z0-9]/g, "_"))}">
      <span class="hm-a-name">${esc(a.name)}</span><span class="hm-a-px">${num(a.last, a.t)}</span>
      <span class="hm-a-chg ${a.t === "^VIX" ? "" : cls(a.d1)}">${pct(a.d1, 2)}</span><span class="hm-a-sp">${spark(a.spark)}</span></button>`).join("");
    renderSectors();
    const mv = (list) => list.slice(0, 7).map((s) => `<li data-sym="${esc(s.t)}"><span><b>${esc(s.ko || s.t)}</b> <span class="sub">${esc(s.ko ? s.t : (s.name || "").replace(/,? Inc\.?|,? Corp(oration)?\.?|Common Stock/g, "").slice(0, 22))}</span></span><span class="r">${usd(s.px)}</span><span class="r ${cls(s.d1)}">${pct(s.d1)}</span></li>`).join("");
    $("#hm-up").innerHTML = mv(M.up); $("#hm-down").innerHTML = mv(M.down);
    const b = M.breadth || {}, g = M.regime || {};
    $("#hm-breadth").innerHTML = `
      <div class="hm-kv"><span>오른 종목 / 내린 종목</span><b><span class="up">${b.adv}</span> / <span class="down">${b.dec}</span></b></div>
      <div class="hm-kv"><span>50일선 위 종목</span><b>${(b.above50 * 100).toFixed(0)}%</b></div>
      <div class="hm-kv"><span>200일선 위 종목</span><b>${(b.above200 * 100).toFixed(0)}%</b></div>
      <div class="hm-kv"><span>52주 신고가 / 신저가</span><b>${b.hi52} / ${b.lo52}</b></div>
      <div class="hm-kv"><span>S&P500 vs 200일선</span><b class="${cls(g.sp_vs200)}">${pct(g.sp_vs200)}</b></div>
      <p class="hint">${g.up ? "S&P500이 200일선 위 — 상승장 규칙(추천 기업 매수)이 켜져 있어요." : "S&P500이 200일선 아래 — 추천 기업은 매수 신호가 아니라 관심 목록이에요."}</p>`;
    if (T) {
      $("#hm-themes").innerHTML = T.rows.slice(0, 6).map((r) => `<li data-theme="${r.key}"><span><b>${esc(r.name)}</b> <span class="th-st st-${r.status.replace(/\s/g, "")}">${esc(r.status)}</span></span>
        <span class="r ${cls(r.r3)}">3개월 ${pct(r.r3)}p</span><span class="r"><b>${Math.floor(r.score)}</b></span></li>`).join("");
      $("#hm-macro").innerHTML = (T.macro || []).slice(0, 4).map((m) => `<a class="mk" href="${esc(m.url)}" target="_blank" rel="noopener"><span class="mk-src">${esc(m.src)}</span>
        <span class="mk-t">${esc(m.ko || m.title)}</span><span class="mk-outs">${(m.outs || []).slice(0, 2).map((o) => `<span class="mk-o"><b>${(o.p * 100).toFixed(o.p < 0.1 ? 1 : 0)}%</b> ${esc(m.single ? "예(Yes)" : o.label)}</span>`).join("")}</span></a>`).join("");
    }
    if (R) {
      $("#hm-basket").innerHTML = R.rows.filter((r) => r.basket).slice(0, 8).map((r) => `<li data-sym="${esc(r.code)}"><span><b>${esc(r.ko || r.code)}</b> <span class="sub">${esc(r.ko ? r.code + " · " : "")}${esc((R.themes || {})[r.theme] || r.sector || "")}</span></span>
        <span class="r">${usd(r.close)}</span><span class="r ${cls(r.chg)}">${pct(r.chg)}</span></li>`).join("");
    }
    if (N) {
      $("#hm-news").innerHTML = N.news.slice(0, 7).map((n) => `<li><a href="${esc(n.u)}" target="_blank" rel="noopener">${esc(n.t)}</a> <span class="sub">${esc(n.o || "")} ${esc((n.at || "").slice(11, 16))}</span></li>`).join("");
    }
  }

  function renderSectors() {
    if (!M) return;
    const S = M.sectors.slice().sort((a, b) => (b[secSpan] ?? -9) - (a[secSpan] ?? -9));
    const mx = Math.max(...S.map((s) => Math.abs(s[secSpan] || 0)), 0.005);
    $("#hm-sectors").innerHTML = S.map((s) => { const v = s[secSpan] || 0; return `<div class="sec" data-sym="${esc(s.t)}"><span class="sec-n">${esc(s.name)}</span>
      <span class="sec-bar"><i class="${v >= 0 ? "pos" : "neg"}" style="${v >= 0 ? "left:50%" : `left:${50 - Math.abs(v) / mx * 50}%`};width:${Math.abs(v) / mx * 50}%"></i></span>
      <span class="sec-v ${cls(v)}">${pct(v)}</span></div>`; }).join("");
    document.querySelectorAll("#hm-secspan button").forEach((b) => b.classList.toggle("on", b.dataset.span === secSpan));
  }

  // 장중에는 지수 카드를 1분마다 실시간으로
  async function liveAssets() {
    status();
    if (!M || !Data.getProxy() || document.hidden || !$("#tab-home").classList.contains("active")) return;
    const m = U.usMarket();
    if (!m.live) return;
    await Promise.all(M.assets.map(async (a) => {
      try {
        const q = await Data.liveQuote(a.t);
        const el = document.getElementById("as-" + a.t.replace(/[^A-Za-z0-9]/g, "_")); if (!el) return;
        el.querySelector(".hm-a-px").textContent = num(q.price, a.t);
        const c = el.querySelector(".hm-a-chg"); c.textContent = pct(q.chg, 2); c.className = "hm-a-chg " + (a.t === "^VIX" ? "" : cls(q.chg));
        if (q.pts.length > 3) el.querySelector(".hm-a-sp").innerHTML = spark(q.pts);
        el.classList.add("is-live");
      } catch (_) {}
    }));
    $("#hm-status").insertAdjacentHTML("beforeend", ` · 지수 실시간 ${new Date().toLocaleTimeString("ko-KR", { hour12: false })}`);
  }
  setInterval(liveAssets, 60000);

  function init() {
    $("#tab-home").addEventListener("click", (e) => {
      const sp = e.target.closest("[data-span]"); if (sp) { secSpan = sp.dataset.span; renderSectors(); return; }
      const th = e.target.closest("[data-theme]"); if (th) { window.App && App.showTheme(th.dataset.theme); return; }
      const sy = e.target.closest("[data-sym]"); if (sy) { window.App && App.openChart(sy.dataset.sym); return; }
      const go = e.target.closest("[data-go]"); if (go) { window.App && App.go(go.dataset.go); }
    });
  }
  return { init, onShow: () => { if (!loaded) load(); else { status(); liveAssets(); } } };
})();
