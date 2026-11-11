/* AI 트레이딩 데스크 — 6명 에이전트 + 대화방 (data/us/ai_paper.json) */
const DeskUI = (() => {
  const { $, esc } = U;
  const has = (v) => v != null && isFinite(v);
  const pct = (v, d = 1) => (has(v) ? (v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%" : "—");
  const cls = (v) => (!has(v) ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const usd = (v, d = 2) => (has(v) ? "$" + v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) : "—");
  const AG = {
    scout: ["Scout", "S", "#4fd1a5", "시장 탐색", "순위·터틀·급등·거래량 급증에서 후보를 찾아요"],
    filter: ["Filter", "F", "#b8b8be", "걸러내기", "실적 임박·거래대금 부족·$5 미만·과열·시장 이상을 빼요"],
    analyst: ["Analyst", "A", "#7aa2ff", "분석", "추세·RSI·MACD·거래량·상대강도·목표가로 0~1점, 0.6 미만 탈락"],
    risk: ["Risk", "R", "#f0525c", "위험 관리", "손절 필수, 손실 ≤ 계좌 2%, +15%부터 추적 손절, 급락 땐 신규 중단"],
    executor: ["Executor", "E", "#ffffff", "주문 실행", "지정가·스톱 주문, 중복 방지, 30분마다 체결 확인"],
    logger: ["Logger", "L", "#c792ea", "기록·성과", "승률·손익비·최대 낙폭·누적 수익을 기록해요"],
    claude: ["Claude", "C", "#f5c26b", "총괄", "매일 아침 뉴스·이벤트를 보고 판단을 더하고 직접 주문도 내요"],
  };
  let A = null, loaded = false;

  async function onShow() {
    try { const r = await fetch("data/us/ai_paper.json?t=" + Date.now()); if (!r.ok) throw 0; A = await r.json(); }
    catch (_) { $("#dk-chat").innerHTML = `<p class="muted">아직 데스크가 열리지 않았어요.</p>`; return; }
    if (!loaded) {
      loaded = true;
      $("#tab-desk").addEventListener("click", (e) => { const b = e.target.closest("[data-sym]"); if (b) App.openChart(b.dataset.sym); });
    }
    render();
  }

  function render() {
    const m = A.stats || {}, r = A.eq_now / A.cash0 - 1, inv = A.pos.reduce((s, p) => s + (p.val || 0), 0);
    $("#dk-date").textContent = `${A.start} 시작 · ${(A.agents || {}).day ? A.agents.day + " 회의까지" : ""}`;
    $("#dk-rules").textContent = "규칙: " + A.rules;
    const st = [
      ["계좌", usd(A.eq_now, 0), `<span class="${cls(r)}">${pct(r, 2)}</span>`],
      ["같은 기간 S&P500", A.bench == null ? "첫 체결 뒤" : `<span class="${cls(A.bench)}">${pct(A.bench, 2)}</span>`, A.bench == null ? "" : `차이 <b class="${cls(r - A.bench)}">${pct(r - A.bench, 2)}</b>`],
      ["투자 / 현금", `${usd(inv, 0)}`, `현금 ${usd(A.cash, 0)}`],
      ["끝난 거래", `${m.n || 0}건`, m.n ? `승률 ${Math.round(m.win * 100)}%` : "아직 없음"],
      ["손익비", has(m.payoff) ? m.payoff.toFixed(2) : "—", "평균 이익 ÷ 평균 손실"],
      ["최대 낙폭", pct(m.mdd, 1), A.halt ? `<b class="down">🚨 신규 매수 중단 중</b>` : "고점 대비 최대 하락"],
    ];
    $("#dk-stats").innerHTML = st.map(([k, v, s]) => `<div class="hd-stat"><span class="k">${k}</span><b>${v}</b><span class="s">${s}</span></div>`).join("");
    const ag = A.agents || {};
    $("#dk-agents").innerHTML = ["scout", "filter", "analyst", "risk", "executor", "logger"].map((k, i) => {
      const [nm, ini, col, role, desc] = AG[k];
      return `${i ? `<span class="dk-arrow">→</span>` : ""}<div class="dk-agent" title="${esc(desc)}">
        <span class="dk-av" style="--c:${col}">${ini}</span><div><b>${nm}</b><span class="muted small">${role}</span><span class="dk-st">${esc(ag[k] || "대기")}</span></div></div>`;
    }).join("");
    renderChat();
    $("#dk-pos").innerHTML = A.pos.map((p) => `<tr><td><button class="tt-sym" data-sym="${esc(p.sym)}"><b>${esc(p.sym)}</b><span class="muted">${usd(p.val, 0)} · ${esc(p.since.slice(5))}부터</span></button></td>
      <td class="num ${cls(p.pl)}">${pct(p.pl)}</td><td class="num">${usd(p.stop)}<span class="s">${p.target ? usd(p.target) : "—"}</span></td></tr>`).join("")
      || `<tr class="empty-row"><td colspan="3">아직 없음 — 대기 주문이 체결되면 떠요.</td></tr>`;
    $("#dk-orders").innerHTML = A.orders.map((o) => `<li><b>${esc(o.desc)}</b><span class="muted small">${esc(o.why)}</span></li>`).join("") || `<li class="muted">없음</li>`;
    $("#dk-cands").innerHTML = (A.cands || []).slice(0, 8).map((c) => `<div class="dk-cand"><button class="tt-sym" data-sym="${esc(c.t)}"><b>${esc(c.name)}</b><span class="muted">${esc(c.t)} · ${esc(c.src)}</span></button>
      <div class="dk-bar"><i style="width:${Math.round(c.score * 100)}%" class="${c.score >= 0.6 ? "ok" : ""}"></i><span>${c.score.toFixed(2)}</span></div><span class="muted small">${esc(c.why)}</span></div>`).join("") || `<p class="muted small">회의 뒤에 채워져요.</p>`;
    $("#dk-trades").innerHTML = A.trades.slice(0, 15).map((t) => `<li><b>${esc(t.sym)}</b> <span class="${cls(t.pl)}">${pct(t.pl)}</span><span class="muted small">${esc(t.in.slice(5))} → ${esc(t.out.slice(5))} · ${esc(t.why)}${t.src ? " · " + esc(t.src) : ""}</span></li>`).join("") || `<li class="muted">아직 없음</li>`;
  }

  function renderChat() {
    const box = $("#dk-chat"), msgs = A.chat || [];
    $("#dk-chat-sub").textContent = `${msgs.length}개 메시지`;
    let lastDay = "";
    box.innerHTML = msgs.map((c) => {
      const [nm, ini, col] = AG[c.who] || [c.who, "?", "#888"];
      const d = c.at.slice(0, 10);
      const sep = d !== lastDay ? `<div class="dk-day">${d}</div>` : ""; lastDay = d;
      if (c.sep) return sep + `<div class="dk-meet">${esc(c.text)}</div>`;
      const txt = esc(c.text).replace(/@(Scout|Filter|Analyst|Risk|Executor|Logger|Claude)/g, '<span class="dk-at">@$1</span>');
      return sep + `<div class="dk-msg"><span class="dk-av" style="--c:${col}">${ini}</span><div class="dk-bub"><div class="dk-who"><b style="color:${col}">${nm}</b><span class="muted small">${esc(c.at.slice(11))}</span></div><div>${txt}</div></div></div>`;
    }).join("") || `<p class="muted">아직 대화가 없어요.</p>`;
    box.scrollTop = box.scrollHeight;
  }

  return { onShow };
})();
