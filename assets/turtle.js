/* 터틀 트레이딩 — data/us/turtle.json (매일 신호), data/us/turtle_backtest.json (과거 검증) */
const TurtleUI = (() => {
  const { $, esc, store, LC_OPTS } = U;
  let D = null, B = null, loaded = false, showAll = false, curve = null;
  const has = (v) => v != null && isFinite(v);
  const pct = (v, d = 1) => (has(v) ? (v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%" : "—");
  const cls = (v) => (!has(v) ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  const usd = (v) => (has(v) ? "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—");
  const get = async (p) => { const r = await fetch(p + "?t=" + Date.now()); if (!r.ok) throw new Error(p); return r.json(); };
  const KEY = "tradingdesk.turtle";
  const name = (r) => `<button class="tt-sym" data-sym="${esc(r.code)}"><b>${esc(r.ko || r.name)}</b><span class="muted">${esc(r.code)}${r.theme ? " · " + esc(r.theme) : ""}</span></button>`;

  function acct() {
    const a = +$("#tt-acct").value || 10000, rk = Math.min(2, Math.max(0.1, +$("#tt-risk").value || 1)) / 100;
    return { a, rk };
  }
  function unit(r, px) {                          // 1유닛 = 계좌×위험% ÷ N, 계좌의 8% 상한
    const { a, rk } = acct();
    if (!has(r.N) || r.N <= 0 || !has(px)) return "—";
    let sh = Math.floor((a * rk) / r.N);
    const cap = Math.floor((a * 0.08) / px);
    const capped = sh > cap; sh = Math.min(sh, cap);
    if (sh < 1) return `<span class="muted" title="계좌가 작아서 1주도 안 돼요">1주 미만</span>`;
    return `${sh}주<span class="s">${usd(sh * px)}${capped ? " · 8% 상한" : ""}</span>`;
  }

  async function onShow() {
    if (loaded) return;
    loaded = true;
    try { const s = store.get(KEY, null); if (s) { $("#tt-acct").value = s.a; $("#tt-risk").value = s.r; } } catch (_) {}
    ["#tt-acct", "#tt-risk"].forEach((q) => $(q).addEventListener("input", () => { try { store.set(KEY, { a: $("#tt-acct").value, r: $("#tt-risk").value }); } catch (_) {} renderEntry(); }));
    $("#tt-q").addEventListener("input", renderHold);
    $("#tt-more").addEventListener("click", () => { showAll = !showAll; renderHold(); });
    $("#tab-turtle").addEventListener("click", (e) => { const b = e.target.closest("[data-sym]"); if (b) App.openChart(b.dataset.sym); });
    try { [D, B] = await Promise.all([get("data/us/turtle.json"), get("data/us/turtle_backtest.json").catch(() => null)]); }
    catch (_) { $("#tt-entry").innerHTML = `<tr class="empty-row"><td colspan="7">아직 터틀 신호가 없어요. 매일 미국장 마감 뒤 만들어져요.</td></tr>`; return; }
    render();
  }

  function render() {
    const c = D.count || {}, g = D.regime || {};
    $("#tt-date").textContent = `${D.date} 미국장 종가 기준 · S&P500·나스닥100 ${D.n_uni}종목`;
    const R = (B && B.results) || {}, o = R["원래 규칙 + 시장 필터"] || {}, sp = R["S&P500 그냥 보유"] || {}, raw = R["원래 규칙"] || {};
    $("#tt-trust").innerHTML = `
      <div class="trust-stage"><span class="k">검증</span><b>${has(o.sharpe) && has(sp.sharpe) && o.sharpe > sp.sharpe ? "시장보다 나음" : "시장보다 못함"}</b><span class="k">위험 대비 (샤프)</span></div>
      <div class="trust-txt">
        미국 대형주 과거 검증(${B ? esc(B.period) : "—"}): 원래 규칙은 연 <b class="${cls(raw.cagr)}">${pct(raw.cagr)}</b>, 시장 필터를 붙이면 연 <b class="${cls(o.cagr)}">${pct(o.cagr)}</b> (최대 낙폭 ${pct(o.mdd, 0)}).
        S&P500을 그냥 들고 있었으면 연 ${pct(sp.cagr)} (낙폭 ${pct(sp.mdd, 0)}).
        <br>터틀은 원래 원자재·통화·채권 선물 수십 개에 나눠 쓰던 방식이라, 서로 같이 움직이는 미국 주식에서는 효과가 약해요. 설정을 조금만 바꿔도 결과가 크게 달라져요 (아래 참고).
      </div>`;
    $("#tt-mkt").innerHTML = `<div class="tt-mkt ${g.up ? "on" : "off"}"><b>시장 필터 ${g.up ? "통과" : "멈춤"}</b>
      <span>S&P500이 200일선 ${g.up ? "위" : "아래"} (${pct(g.sp_vs200)}) — ${g.up ? "새 진입 가능" : "검증상 새 진입은 쉬는 게 나았어요"}</span></div>`;
    renderEntry(); renderHold(); renderExit(); renderBT();
  }

  function renderEntry() {
    if (!D) return;
    const rows = D.rows.filter((r) => r.st.kind === "new" || r.st.kind === "near")
      .sort((a, b) => (a.st.kind === "new" ? -1 : 0) - (b.st.kind === "new" ? -1 : 0) || (a.st.distN ?? 0) - (b.st.distN ?? 0));
    $("#tt-entry").innerHTML = rows.map((r) => {
      const s = r.st, isNew = s.kind === "new";
      const px = isNew ? s.avg : s.trigger, stop = isNew ? s.stop : s.stop_if;
      const tag = isNew ? `<span class="tt-tag new">오늘 진입</span>` : `<span class="tt-tag">${s.distN <= 0.3 ? "코앞" : "대기"} ${s.distN.toFixed(1)}N</span>`;
      return `<tr><td>${name(r)}</td><td>${tag}<span class="s">시스템${s.sys} (${s.sys === 1 ? "20일" : "55일"} 돌파)</span></td>
        <td class="num">${usd(r.close)} <span class="s ${cls(r.chg)}">${pct(r.chg)}</span></td>
        <td class="num"><b>${usd(px)}</b>${isNew ? `<span class="s">다음 추가 ${usd(s.next_add)}</span>` : ""}</td>
        <td class="num">${usd(stop)}<span class="s">${pct(stop / px - 1)}</span></td>
        <td class="num">${r.N.toFixed(2)}<span class="s">${pct(r.Npct)}</span></td><td class="num">${unit(r, px)}</td></tr>`;
    }).join("") || `<tr class="empty-row"><td colspan="7">돌파 1N 이내인 종목이 없어요.</td></tr>`;
  }

  function renderHold() {
    if (!D) return;
    const q = ($("#tt-q").value || "").trim().toLowerCase();
    let rows = D.rows.filter((r) => r.st.kind === "hold" && (!q || (r.code + " " + r.name + " " + (r.ko || "")).toLowerCase().includes(q)))
      .sort((a, b) => b.st.R - a.st.R);
    const total = rows.length;
    if (!showAll && !q) rows = rows.slice(0, 15);
    $("#tt-hold").innerHTML = rows.map((r) => {
      const s = r.st;
      return `<tr><td>${name(r)}<span class="s">${esc(s.since.slice(5))}부터 · 시스템${s.sys}</span></td><td class="num">${s.units}/4</td>
        <td class="num ${cls(s.pl)}">${pct(s.pl)}</td><td class="num ${cls(s.R)}">${s.R > 0 ? "+" : ""}${s.R.toFixed(1)}</td>
        <td class="num">${usd(s.stop_eff)}<span class="s">${pct(s.stop_eff / r.close - 1)}</span></td><td class="num">${s.next_add ? usd(s.next_add) : "<span class='muted'>꽉 참</span>"}</td></tr>`;
    }).join("") || `<tr class="empty-row"><td colspan="6">없어요.</td></tr>`;
    $("#tt-more").hidden = q || total <= 15;
    $("#tt-more").textContent = showAll ? "접기" : `${total}개 모두 보기`;
  }

  function renderExit() {
    const all = D.rows.filter((r) => r.st.kind === "exit").sort((a, b) => b.st.pl - a.st.pl);
    const rows = all.length > 12 ? [...all.slice(0, 6), ...all.slice(-6)] : all;
    $("#tt-exit").innerHTML = (all.length > 12 ? `<tr><td colspan="3" class="muted small">${all.length}종목 청산 — 가장 좋았던 6개와 나빴던 6개</td></tr>` : "") + rows.map((r) => `<tr><td>${name(r)}</td><td>${esc(r.st.why)}<span class="s">${esc(r.st.since.slice(5))} 진입 · ${r.st.units}유닛</span></td>
      <td class="num ${cls(r.st.pl)}">${pct(r.st.pl)}</td></tr>`).join("") || `<tr class="empty-row"><td colspan="3">오늘 청산된 종목이 없어요.</td></tr>`;
  }

  function renderBT() {
    if (!B) { $("#tt-bt").innerHTML = `<p class="muted">검증 자료가 없어요.</p>`; return; }
    $("#tt-bt-sub").textContent = `${B.period} · ${B.universe}`;
    const R = B.results, keys = Object.keys(R);
    $("#tt-bt").innerHTML = `<div class="tbl-wrap"><table class="tt-tbl bt"><thead><tr><th>방식</th><th class="num">연 수익</th><th class="num">최대 낙폭</th><th class="num">샤프</th><th class="num">거래</th><th class="num">승률</th><th class="num">평균 이익 / 손실</th><th class="num">투자 비중</th></tr></thead><tbody>
      ${keys.map((k) => { const x = R[k], sp = k.startsWith("S&P");
        return `<tr class="${sp ? "bench" : ""}"><td>${esc(k)}</td><td class="num ${cls(x.cagr)}">${pct(x.cagr)}</td><td class="num">${pct(x.mdd, 0)}</td><td class="num">${x.sharpe.toFixed(2)}</td>
          <td class="num">${sp ? "—" : x.n.toLocaleString()}</td><td class="num">${sp ? "—" : Math.round(x.win * 100) + "%"}</td>
          <td class="num">${sp ? "—" : `+${x.avg_win_R.toFixed(1)}R / ${x.avg_loss_R.toFixed(1)}R`}</td><td class="num">${sp ? "100%" : Math.round(x.exposure * 100) + "%"}</td></tr>`; }).join("")}
      </tbody></table></div>`;
    const S = B.sensitivity || [];
    $("#tt-bt-note").innerHTML = `
      ${S.length ? `<p class="small"><b>설정 민감도</b> (원래 규칙 + 시장 필터, 전체 유닛 한도만 바꿈): ${S.map((x) => `${x.maxu}유닛 → 연 ${pct(x.cagr)} (낙폭 ${pct(x.mdd, 0)})`).join(" · ")}.
        같은 아이디어인데 한도 하나로 연 수익이 두 배 넘게 차이 나요. 가장 좋은 숫자를 믿기보다는 범위로 보세요.</p>` : ""}
      <ul class="small muted tt-notes">
        <li>R = 처음 정한 손절 폭(2N) 대비 몇 배를 벌었나/잃었나. 손실이 −1R보다 큰 건 갭 하락(실적 발표 등)으로 손절가보다 낮게 팔린 경우예요.</li>
        <li>지금 지수에 남아 있는 종목으로만 검증해서 실제보다 좋게 나왔을 가능성이 커요 (중간에 망하거나 빠진 종목이 없음). 추세 추종은 이 편향의 혜택을 특히 많이 받아요.</li>
        <li>${esc(B.rules)}</li>
      </ul>`;
    drawCurve();
  }

  function drawCurve() {
    const el = $("#tt-curve"); if (!el || !B || !B.curves || typeof LightweightCharts === "undefined") return;
    if (curve) { curve.remove(); curve = null; }
    const LC = LightweightCharts;
    curve = LC.createChart(el, { ...LC_OPTS(), grid: { vertLines: { visible: false }, horzLines: { color: "rgba(160,160,168,.07)" } }, layout: { ...LC_OPTS().layout, attributionLogo: false }, rightPriceScale: { mode: 1, borderVisible: false }, timeScale: { borderVisible: false }, handleScroll: false, handleScale: false });
    const pick = [["S&P500 그냥 보유", "#9a9aa2"], ["원래 규칙", "rgba(255,255,255,.45)"], ["원래 규칙 + 시장 필터", "#ffffff"], ["시스템2만 + 시장 필터", "#3d8bfd"]];
    const leg = [];
    pick.forEach(([k, c]) => {
      const d = B.curves[k]; if (!d) return;
      const s = curve.addSeries(LC.LineSeries, { color: c, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
      s.setData(d.map(([m, v]) => ({ time: m + "-01", value: v * 10000 })));
      leg.push(`<span><i style="background:${c}"></i>${esc(k)} $${Math.round(d[d.length - 1][1] * 10000).toLocaleString()}</span>`);
    });
    curve.timeScale().fitContent();
    let lg = el.parentElement.querySelector(".tt-leg");
    if (!lg) { lg = document.createElement("div"); lg.className = "tt-leg"; el.after(lg); }
    lg.innerHTML = `<span class="muted">$10,000으로 시작 (로그 눈금)</span>` + leg.join("");
  }

  return { onShow };
})();
