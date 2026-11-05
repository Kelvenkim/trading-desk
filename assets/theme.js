/* 장기 테마 — data/narrative/latest.json, history.json */
const ThemeUI = (() => {
  const { $, esc, LC_OPTS, toast } = U;
  let T = null, Hh = null, open = null, chart = null, period = 252, loaded = false;
  const VKEY = "tradingdesk.views";
  const PCOL = { trend: "#ffffff", breadth: "#d6d6db", buzz: "#adadb5", policy: "#86868e", target: "#64646b", earn: "#46464c" };
  const pct = (v, d = 1) => (v == null || !isFinite(v) ? "—" : (v >= 0 ? "+" : "") + (v * 100).toFixed(d) + "%");
  const pp = (v) => (v == null || !isFinite(v) ? "—" : (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%p");
  const cls = (v) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const won = (v) => (v == null ? "—" : Math.round(v).toLocaleString("ko-KR"));
  const views = () => { try { return JSON.parse(localStorage.getItem(VKEY) || "{}"); } catch (_) { return {}; } };
  const saveViews = (v) => { try { localStorage.setItem(VKEY, JSON.stringify(v)); } catch (_) {} };

  async function load() {
    const get = async (p) => { const r = await fetch(p + "?t=" + Date.now()); if (!r.ok) throw new Error(p); return r.json(); };
    try { T = await get("data/narrative/latest.json"); }
    catch (_) { $("#th-list").innerHTML = `<p class="muted">아직 장기 테마 자료가 없어요. 장 마감 후 자동으로 만들어져요.</p>`; return; }
    loaded = true;
    renderTop(); renderList(); renderSide();
    try { Hh = await get("data/narrative/history.json"); } catch (_) {}
    renderList();
  }

  function recLine(name, r) {
    if (!r || !r.n) return `${name}: 체결된 매매 없음`;
    return `${name}: 체결 ${r.n}건 — 끝난 ${r.done}건 중 목표 ${r.win} / 손절 ${r.done - r.win}${r.avg != null ? ` (평균 <b class="${cls(r.avg)}">${pct(r.avg)}</b>)` : ""} · 보유 중 ${r.open}건${r.open_avg != null ? ` (평균 ${pct(r.open_avg)})` : ""}`;
  }

  function renderMacro() {
    const el = $("#th-macro"); if (!el) return;
    const m = T.macro || [], pr = T.pick_record;
    el.innerHTML = `<div class="box-head"><h2>거시 전망 <span class="muted small">예측시장 · 돈을 건 사람들이 매긴 확률</span></h2></div>
      ${m.length ? `<div class="mkts">${m.map(mktHTML).join("")}</div>` : `<p class="small muted">예측시장 자료를 받지 못했어요.</p>`}
      <p class="hint">금리·경기 전망은 모든 테마에 영향을 줘요. 예: 금리 인상 확률이 높으면 성장주·바이오에 불리, 은행·보험에 유리한 경향.</p>
      ${T.market_up === false ? `<div class="mkt-warn">지금은 코스피200이 200일선 아래예요. 추천 기업의 매수 규칙(눌림목·목표 3R)은 과거에 <b>상승장에서만</b> 플러스였어서, 지금 추천은 <b>매수 신호가 아니라 관심 목록</b>이에요.</div>` : ""}
      <div class="pick-rec small">${recLine("규칙대로 (상승장에서만 매수)", pr)}<br>${recLine("시장 필터를 무시했다면", pr && pr.nofilter)}
        <div class="sub">추천 뒤 5거래일 안에 매수 구간까지 내려오면(돌파는 그 가격을 넘으면) 체결, 그 뒤 손절·목표 중 먼저 닿은 결과. 같은 종목 중복 추천은 한 번만 세요.</div></div>`;
  }

  function renderTop() {
    renderMacro();
    $("#th-date").textContent = `${T.date} 기준 · 16개 이야기 · 시총 상위 300 종목`;
    const b = T.backfill || {}, h6 = b["126"] || {}, lv = (T.live || {})["126"] || {};
    $("#th-trust").innerHTML = `
      <div class="trust-stage"><span class="k">과거 검증</span><b>${h6.top_vs_all != null ? pp(h6.top_vs_all) : "—"}</b><span class="k">6개월 · 상위 3개 테마</span></div>
      <div class="trust-txt">
        주가 추세가 가장 강한 테마 3개를 골랐을 때, 그 뒤 6개월 동안 16개 테마 평균보다 <b class="${cls(h6.top_vs_all)}">${pp(h6.top_vs_all)}</b> 더 올랐고, 이긴 때가 <b>${h6.beat != null ? (h6.beat * 100).toFixed(0) : "—"}%</b>였어요(${b.from ? b.from.slice(0, 4) : ""}~${b.to ? b.to.slice(0, 4) : ""}, ${h6.n || 0}번).
        반대로 가장 약한 3개는 ${pp(h6.bot_vs_all)}.
        <br><span class="muted small">${esc(b.note || "")}</span>
        <br>실제 운영 채점(6개월 뒤): ${lv.n ? `${lv.n}번 · 평균 대비 ${pp(lv.ex)}` : "아직 없음 — 6개월 뒤부터 쌓여요"}.
      </div>`;
  }

  function spark(key) {
    if (!Hh || !Hh.idx[key]) return "";
    const n = Hh.dates.length, from = Math.max(0, n - 126), a = Hh.idx[key], k = Hh.ks;
    const v = []; for (let i = from; i < n; i++) if (a[i] && a[from] && k[i]) v.push((a[i] / a[from]) / (k[i] / k[from]));
    if (v.length < 2) return "";
    const lo = Math.min(...v), hi = Math.max(...v), w = 90, h = 26;
    const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - (hi > lo ? (x - lo) / (hi - lo) : 0.5) * h).toFixed(1)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" title="6개월, 코스피200 대비"><polyline points="${pts}" fill="none" stroke="${v[v.length - 1] >= 1 ? "var(--up)" : "var(--down)"}" stroke-width="1.5"/></svg>`;
  }

  function renderList() {
    const V = views();
    $("#th-list").innerHTML = T.rows.map((r) => {
      const my = (V[r.key] || []).slice(-1)[0];
      const stack = Object.keys(T.parts).map((p) => `<i style="width:${r.parts[p]}%;background:${PCOL[p]}" title="${T.parts[p].name} ${r.parts[p].toFixed(0)}/${T.parts[p].max}"></i>`).join("");
      return `<div class="th-card ${open === r.key ? "open" : ""}" data-key="${r.key}">
        <div class="th-row">
          <span class="rk-n">${r.rank}</span>
          <div class="th-name"><b>${esc(r.name)}</b><span class="th-st st-${r.status.replace(/\s/g, "")}">${esc(r.status)}</span>${my ? `<span class="th-my v-${my.view}">내 판단 ${({ good: "좋음", neutral: "중립", bad: "나쁨" })[my.view]}</span>` : ""}
            <div class="sub">${r.n}종목 · 3개월 ${pp(r.r3)} · 6개월 ${pp(r.r6)} (코스피200 대비)</div></div>
          <div class="th-spark">${spark(r.key)}</div>
          <div class="th-score"><b>${Math.floor(r.score)}</b><span class="stack">${stack}</span></div>
        </div>
        ${open === r.key ? detail(r) : ""}
      </div>`;
    }).join("");
    if (open) drawChart(open);
  }

  function detail(r) {
    const st = Object.entries(r.story).filter(([, v]) => v && v !== "—").map(([k, v]) => `<div class="story"><span class="tag">${k}</span>${esc(v)}</div>`).join("");
    const heads = (r.heads || []).map((h) => `<li>${h.pol ? `<span class="tag pol">정책</span>` : `<span class="tag">사업</span>`}
      <a href="${esc(h.u)}" target="_blank" rel="noopener">${esc(h.t)}</a> <span class="sub">${esc(h.name)} · ${esc(h.o || "")} ${h.d ? h.d.slice(4, 6) + "/" + h.d.slice(6, 8) : ""}</span></li>`).join("");
    const parts = Object.entries(T.parts).map(([p, d]) => `<div class="pbar"><span class="pn">${d.name}</span><span class="pt"><i style="width:${r.parts[p] / d.max * 100}%;background:${PCOL[p]}"></i></span><span class="pv"><b>${r.parts[p].toFixed(0)}</b>/${d.max}</span></div>`).join("");
    const stocks = r.stocks.slice(0, 25).map((s) => `<tr data-sym="${s.code}">
      <td><b>${esc(s.name)}</b>${s.primary ? "" : `<span class="sub"> 겸업</span>`}</td>
      <td>${s.grade ? `<span class="grade g-${s.grade}">${s.grade}</span> ${Math.floor(s.ours)}` : "—"}</td>
      <td class="r ${cls(s.r3)}">${pct(s.r3)}</td><td class="r">${s.up != null ? pct(s.up, 0) : "—"}</td>
      <td class="r"><button class="btn small" data-open="${s.code}">차트</button></td></tr>`).join("");
    return `<div class="th-detail">
      <div class="th-col">
        <h3>이야기</h3>${st}
        <h3>근거</h3><ul class="evid">${r.evidence.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>
        ${heads ? `<h4 class="muted small">최근 3일 관련 기사</h4><ul class="news">${heads}</ul>` : `<p class="small muted">최근 3일 관련 기사 없음</p>`}
        <h3>점수 내역</h3>${parts}
        ${myBox(r)}
      </div>
      <div class="th-col">
        <div class="th-chart-head"><h3>테마 지수 vs 코스피200</h3>
          <div class="seg small">${[[126, "6개월"], [252, "1년"], [756, "3년"], [0, "전체"]].map(([n, t]) => `<button data-per="${n}" class="${period === n ? "on" : ""}">${t}</button>`).join("")}</div></div>
        <div class="th-chart" id="th-chart"></div>
        <p class="hint">흰색 = 테마 종목 동일 비중 지수, 회색 = 코스피200. 시작점을 100으로 맞췄어요.</p>
        <h3>종목 <span class="muted small">시총 순 · 등급은 오늘의 우리 점수</span></h3>
        <div class="table-wrap"><table class="tbl th-stocks"><thead><tr><th>종목</th><th>우리 점수</th><th class="r">3개월</th><th class="r">목표가 여력</th><th></th></tr></thead><tbody>${stocks}</tbody></table></div>
      </div>
      <div class="th-full">
        <h3>추천 기업 <span class="muted small">소형주 포함 · 테마 연관도·차트 자리·증권가·수급으로 골랐어요 · 매일 바뀌어요</span></h3>
        ${(r.picks || []).length ? `<div class="picks">${r.picks.map(pickHTML).join("")}</div>` : `<p class="small muted">오늘은 조건(하루 거래대금 20억 이상, 손절 폭 15% 이내)에 맞는 종목이 없어요.</p>`}
        <h3>이 이야기 관련 예측시장 <span class="muted small">Polymarket — 돈을 건 사람들이 매긴 확률</span></h3>
        ${(r.markets || []).length ? `<div class="mkts">${r.markets.map(mktHTML).join("")}</div>` : `<p class="small muted">관련 예측시장을 찾지 못했어요. 한국 개별 기업·산업을 다루는 시장은 거의 없어요.</p>`}
      </div>
    </div>`;
  }

  const REC = { strong_buy: "적극 매수", buy: "매수", hold: "보유", underperform: "비중 축소", sell: "매도", none: "의견 없음" };
  const eok = (v) => (v == null ? "—" : (v >= 0 ? "+" : "") + Math.round(v / 1e8).toLocaleString("ko-KR") + "억");
  function mktHTML(m) {
    const outs = (m.outs || []).map((o) => `<span class="mk-o"><b>${(o.p * 100).toFixed(o.p < 0.1 ? 1 : 0)}%</b> ${esc(m.single ? "예(Yes)" : o.label)}</span>`).join("");
    return `<a class="mk" href="${esc(m.url)}" target="_blank" rel="noopener"><span class="mk-src">${esc(m.src)}</span><span class="mk-t">${esc(m.ko || m.title)}</span>${m.ko ? `<span class="sub">${esc(m.title)}</span>` : ""}<span class="mk-outs">${outs}</span>${m.vol ? `<span class="sub">거래액 $${Math.round(m.vol).toLocaleString("en-US")}</span>` : ""}</a>`;
  }
  function pickHTML(p) {
    const P = p.plan, c = p.consensus || {}, y = p.yahoo || {}, cm = p.community, f = p.flows || {};
    const pos = P.kind === "pullback";
    const evPct = P.ev * 100;
    const cmBar = cm && cm.ratio != null ? `<span class="cm-bar"><i style="width:${cm.ratio * 100}%"></i></span> 낙관 ${cm.bull} · 비관 ${cm.bear} <span class="sub">(최근 ${cm.n}개 글${cm.ratio > 0.75 ? " · 너무 낙관적이면 오히려 과열 신호일 수 있어요" : ""})</span>` : "자료 없음";
    return `<div class="pick">
      <div class="pick-head"><b>${esc(p.name)}</b><span class="sub">${p.code} · 시총 ${p.mv ? p.mv.toLocaleString("ko-KR") + "억" : "—"} · 현재가 ${won(p.px)}</span>
        <span class="verdict ${P.ok && pos && P.in_zone && P.market_up ? "go" : ""}">${esc(P.verdict)}</span>
        <button class="btn small" data-chartsym="${esc(p.sym)}">차트</button></div>
      <div class="rr">
        <div class="rr-row"><span>${pos ? "매수 구간" : "돌파 매수"}</span><b>${pos ? `${won(P.zone[0])} ~ ${won(P.zone[1])}` : won(P.entry)}</b></div>
        <div class="rr-row up"><span>성공하면 (목표 ${won(P.target)})</span><b>${pct(P.gain)}</b></div>
        <div class="rr-row down"><span>실패하면 (손절 ${won(P.stop)})</span><b>${pct(P.loss)}</b></div>
        <div class="rr-row"><span>손익비</span><b>1 : ${P.rr ? P.rr.toFixed(1) : "—"}</b></div>
        <div class="rr-row"><span>종합 기대값 <span class="sub">과거 승률 32%로 계산</span></span><b class="${cls(P.ev)}">${evPct >= 0 ? "+" : ""}${evPct.toFixed(1)}% / 1회</b></div>
        ${c.up != null ? `<div class="rr-row"><span>증권사 목표가까지</span><b>${pct(c.up, 0)}</b></div>` : ""}
        <div class="rr-note sub">10번 하면 약 3번 목표, 7번 손절이라는 뜻이에요. 계좌의 1%만 잃게 하려면 매수 금액 = 계좌 × 1% ÷ ${Math.abs(P.loss * 100).toFixed(1)}% = 계좌의 ${Math.min(100, 1 / Math.abs(P.loss)).toFixed(0)}%.</div>
      </div>
      <div class="pick-why"><h4>근거</h4><ul class="evid">${p.why.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>
      <div class="pick-op"><h4>시장 여론</h4>
        <div class="op"><span class="tag">국내 증권사</span>${c.target ? `목표가 ${won(c.target)}원 (${pct(c.up, 0)}) · 의견 ${c.opinion || "—"}/5${c.date ? ` <span class="sub">${c.date}</span>` : ""}` : "집계 없음"}</div>
        ${(p.reports || []).map((r) => `<div class="op sub">· ${esc(r.broker)} ${r.date ? r.date.slice(4, 6) + "/" + r.date.slice(6) : ""} "${esc(r.title)}"</div>`).join("")}
        <div class="op"><span class="tag">해외 포함 애널리스트</span>${y.n ? `${y.n}명 · 목표가 평균 ${won(y.target)}원 (${pct(y.target / p.px - 1, 0)}) · ${REC[y.rec] || y.rec || "—"}` : "집계 없음"} <span class="sub">Yahoo Finance</span></div>
        <div class="op"><span class="tag">수급 5일</span>외국인 <b class="${cls(f.foreign5)}">${eok(f.foreign5)}</b> · 기관 <b class="${cls(f.organ5)}">${eok(f.organ5)}</b>${f.fhold ? ` · 외국인 보유 ${esc(f.fhold)}` : ""}</div>
        <div class="op"><span class="tag">투자 커뮤니티</span>${cmBar} <span class="sub">네이버 종목토론방</span></div>
        ${(p.markets || []).length ? `<div class="op"><span class="tag">예측시장</span></div><div class="mkts">${p.markets.map(mktHTML).join("")}</div>` : ""}
      </div>
    </div>`;
  }

  function myBox(r) {
    const list = (views()[r.key] || []).slice().reverse();
    const now = Hh && Hh.idx[r.key] ? { i: Hh.idx[r.key][Hh.idx[r.key].length - 1], k: Hh.ks[Hh.ks.length - 1] } : null;
    const hist = list.map((v) => {
      const res = now && v.idx && v.ks && v.date < T.date ? (now.i / v.idx) / (now.k / v.ks) - 1 : null;
      const right = res == null ? "" : v.view === "good" ? res > 0 : v.view === "bad" ? res < 0 : null;
      return `<li><span class="th-my v-${v.view}">${({ good: "좋음", neutral: "중립", bad: "나쁨" })[v.view]}</span> ${v.date}
        ${res != null ? ` · 그 뒤 코스피200 대비 <b class="${cls(res)}">${pp(res)}</b>${right === true ? " ✓ 맞음" : right === false ? " ✕ 틀림" : ""}` : ` · <span class="muted">다음 장 마감부터 채점</span>`}
        ${v.memo ? `<div class="sub">${esc(v.memo)}</div>` : ""}</li>`;
    }).join("");
    return `<div class="mybox"><h3>내 판단</h3>
      <div class="my-btns">${[["good", "좋음"], ["neutral", "중립"], ["bad", "나쁨"]].map(([v, t]) => `<button class="btn small v-${v}" data-view="${v}">${t}</button>`).join("")}</div>
      <input class="my-memo" placeholder="이유 메모 (예: 상법 개정 통과 기대)" maxlength="200" />
      ${hist ? `<ul class="my-hist">${hist}</ul>` : `<p class="small muted">판단을 남기면 그날 테마 지수를 기록해두고, 이후 코스피200보다 잘했는지 자동으로 채점해요. 이 브라우저에만 저장돼요.</p>`}
    </div>`;
  }

  function drawChart(key) {
    const el = $("#th-chart"); if (!el || !Hh || !Hh.idx[key] || typeof LightweightCharts === "undefined") return;
    if (chart) { try { chart.remove(); } catch (_) {} chart = null; }
    const n = Hh.dates.length, from = period ? Math.max(0, n - period) : 0, a = Hh.idx[key], k = Hh.ks;
    let i0 = from; while (i0 < n && !(a[i0] && k[i0])) i0++;
    const A = [], K = [];
    for (let i = i0; i < n; i++) if (a[i] && k[i]) { A.push({ time: Hh.dates[i], value: a[i] / a[i0] * 100 }); K.push({ time: Hh.dates[i], value: k[i] / k[i0] * 100 }); }
    const LC = LightweightCharts;
    chart = LC.createChart(el, { ...LC_OPTS(), timeScale: { borderVisible: false, timeVisible: false } });
    chart.addSeries(LC.LineSeries, { color: "#ffffff", lineWidth: 2, priceLineVisible: false }).setData(A);
    chart.addSeries(LC.LineSeries, { color: "#76767e", lineWidth: 1, priceLineVisible: false }).setData(K);
    chart.timeScale().fitContent();
  }

  function renderSide() {
    $("#th-parts").innerHTML = Object.entries(T.parts).map(([p, d]) => `<div class="defrow"><span class="dot" style="background:${PCOL[p]}"></span><b>${d.name}</b><span class="muted small">${d.max}점</span>
      <div class="sub">${({ trend: "테마 종목 평균이 코스피200보다 3·6개월 얼마나 잘했나", breadth: "테마 종목 중 60일선 위에 있는 비율", buzz: "최근 3일 테마 종목 기사 수", policy: "정부·국회·법안·예산·관세 같은 정책 기사 수", target: "증권사 목표가가 현재가보다 얼마나 높은가", earn: "최근 실적이 늘어난 종목 비율 (DART 키 필요)" })[p]}</div></div>`).join("") +
      `<div class="sub" style="margin-top:8px">각 항목은 16개 테마 안에서 순위로 점수를 매겨요. 과거로 검증된 건 '주가 추세'뿐이고, 나머지는 매일 기록하며 채점 중이에요.</div>`;
    const b = T.backfill || {};
    $("#th-bf").innerHTML = `<thead><tr><th>기간</th><th class="r">상위 3 − 평균</th><th class="r">이긴 비율</th><th class="r">하위 3 − 평균</th><th class="r">상위 3 − 코스피200</th></tr></thead><tbody>` +
      [["63", "3개월"], ["126", "6개월"], ["252", "1년"]].map(([h, t]) => { const x = b[h] || {}; return `<tr><td>${t}</td><td class="r ${cls(x.top_vs_all)}">${pp(x.top_vs_all)}</td><td class="r">${x.beat != null ? (x.beat * 100).toFixed(0) + "%" : "—"}</td><td class="r ${cls(x.bot_vs_all)}">${pp(x.bot_vs_all)}</td><td class="r ${cls(x.top_vs_ks)}">${pp(x.top_vs_ks)}</td></tr>`; }).join("") + "</tbody>";
  }

  function init() {
    $("#th-list").addEventListener("click", (e) => {
      const ob = e.target.closest("[data-open]");
      if (ob) {
        const code = ob.dataset.open;
        Data.loadSymbols().then((list) => { const hit = list.find((x) => x.symbol.startsWith(code + ".")); window.App && App.openChart(hit ? hit.symbol : code + ".KS"); });
        return;
      }
      const cs = e.target.closest("[data-chartsym]"); if (cs) { window.App && App.openChart(cs.dataset.chartsym); return; }
      const per = e.target.closest("[data-per]"); if (per) { period = +per.dataset.per; renderList(); return; }
      const vb = e.target.closest("[data-view]");
      if (vb) {
        const card = vb.closest(".th-card"), key = card.dataset.key, V = views();
        const memo = card.querySelector(".my-memo").value.trim();
        const i = Hh && Hh.idx[key] ? Hh.idx[key].length - 1 : -1;
        (V[key] = V[key] || []).push({ date: T.date, view: vb.dataset.view, memo, idx: i >= 0 ? Hh.idx[key][i] : null, ks: i >= 0 ? Hh.ks[i] : null });
        saveViews(V); toast("내 판단을 저장했어요."); renderList(); return;
      }
      if (e.target.closest("a, input, .th-detail, .th-full")) return;
      const card = e.target.closest(".th-card"); if (!card) return;
      open = open === card.dataset.key ? null : card.dataset.key; renderList();
      if (open) card.scrollIntoView({ block: "nearest" });
    });
  }
  async function openKey(key) {
    open = key;
    if (!loaded) await load(); else renderList();
    const el = document.querySelector(`.th-card[data-key="${key}"]`); if (el) el.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  return { init, onShow: () => { if (!loaded) load(); }, openKey, get data() { return T; } };
})();
