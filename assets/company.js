/* 기업 정보 카드 (차트 화면 아래) — data/us/profile/티커.json, peers.json, rank.json, theme.json */
const CompanyUI = (() => {
  const { $, esc } = U;
  const cache = {}, shared = {};
  let seq = 0;
  const get = async (p, fresh) => { const r = await fetch(p + (fresh ? "?t=" + Date.now() : "")); if (!r.ok) throw new Error(p); return r.json(); };
  const once = (k, p) => (shared[k] = shared[k] || get(p, true).catch(() => null));
  const has = (v) => v != null && isFinite(v);
  const pct = (v, d = 1, sign = true) => (has(v) ? (sign && v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%" : "—");
  const x = (v, d = 1) => (has(v) ? v.toFixed(d) + "배" : "—");
  const usd = (v, d = 2) => (has(v) ? "$" + v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) : "—");
  const cls = (v) => (!has(v) ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
  function big(v) {                                    // 달러 큰 숫자 → 조·억 달러
    if (!has(v)) return "—";
    const a = Math.abs(v), s = v < 0 ? "-" : "";
    if (a >= 1e12) return `${s}$${(a / 1e12).toFixed(2)}조`;
    if (a >= 1e8) return `${s}$${Math.round(a / 1e8).toLocaleString("ko-KR")}억`;
    if (a >= 1e4) return `${s}$${Math.round(a / 1e4).toLocaleString("ko-KR")}만`;
    return s + "$" + a.toFixed(0);
  }
  const daysTo = (d) => Math.round((new Date(d + "T12:00:00") - new Date()) / 864e5);

  const REC = { strong_buy: "적극 매수", buy: "매수", hold: "보유(중립)", underperform: "비중 축소", sell: "매도", none: "—" };
  const GRADE = {                                    // 증권사 의견 → 우리말
    "strong buy": "적극 매수", buy: "매수", outperform: "시장 상회", overweight: "비중 확대", "sector outperform": "업종 상회", "market outperform": "시장 상회",
    positive: "긍정", accumulate: "매수 누적", "top pick": "최선호", "conviction buy": "확신 매수", "long-term buy": "장기 매수", "speculative buy": "투기적 매수",
    hold: "보유", neutral: "중립", "equal-weight": "비중 유지", "equal weight": "비중 유지", "market perform": "시장 수익률", "sector perform": "업종 수익률", "in-line": "중립", "peer perform": "업종 수익률", mixed: "중립",
    underperform: "시장 하회", underweight: "비중 축소", sell: "매도", "strong sell": "적극 매도", reduce: "비중 축소", negative: "부정", "sector underperform": "업종 하회", "market underperform": "시장 하회",
  };
  const grade = (g) => (g ? GRADE[g.toLowerCase()] || g : "");
  const ACT = { up: ["상향", "up"], down: ["하향", "down"], init: ["신규", ""], main: ["유지", "muted"], reit: ["재확인", "muted"] };
  const PER = { "0q": "이번 분기", "+1q": "다음 분기", "0y": "올해", "+1y": "내년" };

  async function show(sym) {
    const el = $("#co-info"); if (!el) return;
    const my = ++seq;
    if (!sym || Data.isKR(sym)) { el.innerHTML = ""; el.hidden = true; return; }
    el.hidden = false;
    el.innerHTML = `<div class="co-load muted">기업 정보를 불러오는 중…</div>`;
    let p = cache[sym];
    if (!p) { try { p = cache[sym] = await get(`data/us/profile/${encodeURIComponent(sym)}.json`, true); } catch (_) { p = null; } }
    const [peers, rank, theme] = await Promise.all([once("peers", "data/us/peers.json"), once("rank", "data/us/rank.json"), once("theme", "data/us/theme.json")]);
    if (my !== seq) return;
    if (!p) {
      el.innerHTML = `<div class="co-box"><p class="muted">이 종목은 아직 기업 정보가 없어요. S&P500·나스닥100 종목은 매일 조금씩 받아 와요.</p></div>`;
      return;
    }
    const row = rank && rank.rows.find((r) => r.code === sym);
    const px = (row && row.close) || p.val.price;
    el.innerHTML = [head(p, px, peers, row, rank), about(p), valuation(p, px, peers), financials(p, peers), street(p, px), earnings(p), ours(row, rank, theme, sym), mood(p), news(p), foot(p)].filter(Boolean).join("");
    el.querySelectorAll("[data-more]").forEach((b) => b.addEventListener("click", () => { b.parentElement.classList.toggle("open"); b.textContent = b.parentElement.classList.contains("open") ? "접기" : "더 보기"; }));
    el.querySelectorAll("[data-theme]").forEach((b) => b.addEventListener("click", () => App.showTheme(b.dataset.theme)));
  }

  function peerOf(p, peers) {
    if (!peers) return {};
    const a = peers["industry:" + p.industry], b = peers["sector:" + p.sector];
    return a && a.n >= 5 ? { ...a, label: "같은 업종" } : b ? { ...b, label: "같은 섹터" } : {};
  }

  // 한눈에 보기: 숫자 몇 개를 짧은 문장으로 (판단은 직접)
  function head(p, px, peers, row, rank) {
    const v = p.val, f = p.fin, a = p.analyst, pr = peerOf(p, peers), out = [];
    if (has(a.mean) && has(px) && a.n) {
      const up = a.mean / px - 1;
      out.push([`월가 ${a.n}명 평균 목표가 ${usd(a.mean)} → 지금보다 <b class="${cls(up)}">${pct(up, 0)}</b>${a.rec && REC[a.rec] ? ` · 평균 의견 <b>${REC[a.rec]}</b>` : ""}`, up > 0.15 ? "pos" : up < 0 ? "neg" : ""]);
    }
    if (has(v.fpe) && has(pr.fpe)) {
      const r = v.fpe / pr.fpe;
      out.push([`내년 이익 기준 PER ${x(v.fpe)} — ${pr.label} 중간값(${x(pr.fpe)})보다 ${r > 1.15 ? "<b>비싼 편</b>" : r < 0.85 ? "<b>싼 편</b>" : "<b>비슷</b>"}`, r < 0.85 ? "pos" : r > 1.5 ? "neg" : ""]);
    } else if (has(v.fpe) && v.fpe < 0) out.push(["아직 적자 — 예상 PER 계산 안 됨", "neg"]);
    if (has(f.rev_g)) out.push([`최근 분기 매출 ${pct(f.rev_g, 0)} (작년 같은 분기 대비)${has(f.eps_g) ? `, 이익 ${pct(f.eps_g, 0)}` : ""}`, f.rev_g > 0.15 ? "pos" : f.rev_g < 0 ? "neg" : ""]);
    if (p.earn && p.earn.next) {
      const d = daysTo(p.earn.next);
      if (d >= 0 && d <= 45) out.push([`실적 발표 <b>${d === 0 ? "오늘" : d + "일 뒤"}</b> (${p.earn.next}) — 발표 전후로 크게 움직일 수 있어요`, d <= 10 ? "warn" : ""]);
    }
    if (row) {
      const tn = (rank.themes || {})[row.theme];
      out.push([`우리 순위: 테마 눌림 ${Math.round(row.tp)}점${tn ? ` (${esc(tn)})` : ""}${row.basket ? " · <b>오늘 추천 바구니</b>" : ""}`, row.basket ? "pos" : ""]);
    }
    const hi = v.hi52, lo = v.lo52;
    const pos = has(hi) && has(lo) && hi > lo && has(px) ? Math.max(0, Math.min(1, (px - lo) / (hi - lo))) : null;
    return `<div class="co-box co-head">
      <div class="co-title">
        <div><h3>${esc(p.ko || p.name)} <span class="muted">${esc(p.ko ? p.name : "")}</span></h3>
        <div class="co-tags">${[p.sector, p.industry].filter(Boolean).map((t) => `<span>${esc(t)}</span>`).join("")}${p.quote_type === "ETF" ? "<span>ETF</span>" : ""}</div></div>
        ${has(v.mcap) ? `<div class="co-cap"><span class="k">시가총액</span><b>${big(v.mcap)}</b></div>` : ""}
      </div>
      ${out.length ? `<ul class="co-glance">${out.map(([t, c]) => `<li class="${c}">${t}</li>`).join("")}</ul>` : ""}
      ${pos != null ? `<div class="co-52"><span>52주 최저 ${usd(lo)}</span><div class="bar"><i style="left:${(pos * 100).toFixed(1)}%"></i></div><span>최고 ${usd(hi)}</span></div>` : ""}
    </div>`;
  }

  function about(p) {
    const s = p.summary_ko || p.summary_en;
    if (!s) return "";
    const meta = [p.hq && `본사 ${esc(p.hq)}`, has(p.employees) && `직원 ${Number(p.employees).toLocaleString("ko-KR")}명`,
      p.website && `<a href="${esc(p.website)}" target="_blank" rel="noopener">${esc(p.website.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, ""))}</a>`].filter(Boolean);
    return `<div class="co-box"><div class="co-h">무슨 회사인가요</div>
      <div class="co-about"><p>${esc(s)}</p><button class="link-btn" data-more>더 보기</button></div>
      <div class="co-meta">${meta.join(" · ")}${p.summary_ko ? ` <span class="faint">· 회사 소개는 자동 번역</span>` : ""}</div></div>`;
  }

  const cell = (k, v, sub, tip) => `<div class="co-cell"${tip ? ` title="${esc(tip)}"` : ""}><span class="k">${k}</span><b>${v}</b>${sub ? `<span class="s">${sub}</span>` : ""}</div>`;
  const vs = (v, m, fmt, lowGood) => {
    if (!has(v) || !has(m)) return "";
    const r = v / m, word = r > 1.15 ? (lowGood ? "업종보다 비쌈" : "업종보다 높음") : r < 0.85 ? (lowGood ? "업종보다 쌈" : "업종보다 낮음") : "업종과 비슷";
    return `${word} (${fmt(m)})`;
  };

  function valuation(p, px, peers) {
    const v = p.val, pr = peerOf(p, peers);
    if (p.quote_type === "ETF") return "";
    return `<div class="co-box"><div class="co-h">가격이 비싼가요 <span class="muted small">— 괄호는 ${pr.label || "업종"} 중간값</span></div>
      <div class="co-grid">
        ${cell("PER (지난 1년)", x(v.pe), "", "주가 ÷ 지난 1년 주당순이익. 낮을수록 이익에 비해 싸요.")}
        ${cell("예상 PER (내년)", x(v.fpe), vs(v.fpe, pr.fpe, x, true), "주가 ÷ 애널리스트가 예상한 내년 주당순이익")}
        ${cell("PEG", has(v.peg) ? v.peg.toFixed(2) : "—", has(v.peg) ? (v.peg < 1 ? "성장에 비해 싼 편" : v.peg > 2 ? "성장에 비해 비싼 편" : "보통") : "", "PER ÷ 이익 성장률. 1 아래면 성장 대비 싸다고 봐요.")}
        ${cell("PSR (매출 대비)", x(v.ps), vs(v.ps, pr.ps, x, true), "시가총액 ÷ 1년 매출")}
        ${cell("PBR (자산 대비)", x(v.pb), "", "주가 ÷ 주당 순자산")}
        ${cell("EV/EBITDA", x(v.ev_ebitda), vs(v.ev_ebitda, pr.ev_ebitda, x, true), "기업가치 ÷ 영업현금이익. 빚까지 넣은 비교")}
        ${cell("배당수익률", has(v.div) ? v.div.toFixed(2) + "%" : "없음")}
        ${cell("베타", has(v.beta) ? v.beta.toFixed(2) : "—", has(v.beta) ? (v.beta > 1.3 ? "시장보다 크게 출렁" : v.beta < 0.8 ? "시장보다 덜 출렁" : "시장과 비슷") : "", "S&P500이 1% 움직일 때 평균 몇 % 움직이는지")}
      </div></div>`;
  }

  function financials(p, peers) {
    const f = p.fin, pr = peerOf(p, peers), o = p.own || {};
    if (p.quote_type === "ETF" || !has(f.rev)) return "";
    const netCash = has(f.cash) && has(f.debt) ? f.cash - f.debt : null;
    return `<div class="co-box"><div class="co-h">돈을 잘 버나요</div>
      <div class="co-grid">
        ${cell("매출 (1년)", big(f.rev), has(f.rev_g) ? `<span class="${cls(f.rev_g)}">분기 성장 ${pct(f.rev_g, 0)}</span>` : "")}
        ${cell("이익 성장 (분기)", `<span class="${cls(f.eps_g)}">${pct(f.eps_g, 0)}</span>`, "작년 같은 분기 대비")}
        ${cell("영업이익률", pct(f.op, 0, false), vs(f.op, pr.op, (m) => pct(m, 0, false), false))}
        ${cell("순이익률", pct(f.net, 0, false), vs(f.net, pr.net, (m) => pct(m, 0, false), false))}
        ${cell("매출총이익률", pct(f.gross, 0, false))}
        ${cell("ROE", pct(f.roe, 0, false), "", "자기자본으로 1년에 얼마를 버는지")}
        ${cell("잉여현금흐름", big(f.fcf), "", "1년 동안 쓰고 남은 현금")}
        ${cell("현금 − 빚", `<span class="${cls(netCash)}">${big(netCash)}</span>`, `현금 ${big(f.cash)} · 빚 ${big(f.debt)}`)}
        ${has(o.short) ? cell("공매도 비율", pct(o.short, 1, false), o.short > 0.1 ? "높음 — 하락에 거는 사람 많음" : "", "유통 주식 중 공매도된 비율") : ""}
        ${has(o.inst) ? cell("기관 보유", pct(o.inst, 0, false)) : ""}
      </div></div>`;
  }

  function street(p, px) {
    const a = p.analyst || {};
    if (!a.n && !(p.changes || []).length) return "";
    let tgt = "";
    if (has(a.low) && has(a.high) && a.high > a.low) {
      const lo = Math.min(a.low, px || a.low), hi = Math.max(a.high, px || a.high), at = (v) => (((v - lo) / (hi - lo)) * 100).toFixed(1);
      tgt = `<div class="co-tgt">
        <div class="track"><span class="rng" style="left:${at(a.low)}%;right:${100 - at(a.high)}%"></span>
          ${has(px) ? `<span class="pin now" style="left:${at(px)}%"><em>지금 ${usd(px)}</em></span>` : ""}
          ${has(a.mean) ? `<span class="pin avg" style="left:${at(a.mean)}%"><em>평균 ${usd(a.mean)}</em></span>` : ""}</div>
        <div class="ends"><span>최저 ${usd(a.low)} <b class="${cls(a.low / px - 1)}">${pct(a.low / px - 1, 0)}</b></span><span>최고 ${usd(a.high)} <b class="${cls(a.high / px - 1)}">${pct(a.high / px - 1, 0)}</b></span></div>
      </div>`;
    }
    const tr = (a.trend || [])[0];
    let dist = "";
    if (tr) {
      const parts = [["strongBuy", "적극 매수", "sb"], ["buy", "매수", "b"], ["hold", "보유", "h"], ["sell", "매도", "s"], ["strongSell", "적극 매도", "ss"]];
      const tot = parts.reduce((s, [k]) => s + (tr[k] || 0), 0);
      if (tot) {
        const prev = (a.trend || [])[3], buyNow = (tr.strongBuy + tr.buy) / tot, buyPrev = prev ? (prev.strongBuy + prev.buy) / Math.max(1, parts.reduce((s, [k]) => s + (prev[k] || 0), 0)) : null;
        dist = `<div class="co-dist"><div class="bar">${parts.map(([k, l, c]) => (tr[k] ? `<i class="${c}" style="flex:${tr[k]}" title="${l} ${tr[k]}명"></i>` : "")).join("")}</div>
          <div class="lg">${parts.map(([k, l, c]) => `<span><i class="${c}"></i>${l} ${tr[k] || 0}</span>`).join("")}</div>
          <div class="muted small">이번 달 ${tot}명 중 매수 의견 ${Math.round(buyNow * 100)}%${buyPrev != null ? ` · 3달 전 ${Math.round(buyPrev * 100)}%` : ""}</div></div>`;
      }
    }
    const ch = (p.changes || []).slice(0, 8);
    const rows = ch.map((c) => {
      const [al, ac] = ACT[c.Action] || [c.Action || "", ""];
      const t = has(c.currentPriceTarget) && c.currentPriceTarget > 0
        ? `${usd(c.currentPriceTarget, 0)}${has(c.priorPriceTarget) && c.priorPriceTarget > 0 && c.priorPriceTarget !== c.currentPriceTarget ? ` <span class="muted">← ${usd(c.priorPriceTarget, 0)}</span>` : ""}` : "—";
      const pa = c.priceTargetAction === "Raises" ? `<span class="up">목표가↑</span>` : c.priceTargetAction === "Lowers" ? `<span class="down">목표가↓</span>` : "";
      return `<tr><td class="muted">${esc((c.GradeDate || "").slice(5))}</td><td>${esc(c.Firm || "")}</td>
        <td><span class="${ac}">${al}</span> ${esc(grade(c.ToGrade))}${c.FromGrade && c.FromGrade !== c.ToGrade ? ` <span class="muted">← ${esc(grade(c.FromGrade))}</span>` : ""}</td><td class="num">${t} ${pa}</td></tr>`;
    }).join("");
    return `<div class="co-box"><div class="co-h">전문가(월가)는 어떻게 보나요 <span class="muted small">${a.n ? `애널리스트 ${a.n}명` : ""}</span></div>
      ${tgt ? `<div class="co-sub">12개월 목표가</div>${tgt}` : ""}
      ${dist ? `<div class="co-sub">투자 의견</div>${dist}` : ""}
      ${rows ? `<div class="co-sub">최근 의견 변경</div><div class="tbl-wrap"><table class="co-tbl"><thead><tr><th>날짜</th><th>증권사</th><th>의견</th><th class="num">목표가</th></tr></thead><tbody>${rows}</tbody></table></div>` : ""}
      <p class="co-note">목표가는 낙관적으로 나오는 경향이 있어요. 숫자 자체보다 최근에 올리는지 내리는지 방향을 함께 보세요.</p>
    </div>`;
  }

  function earnings(p) {
    const e = p.earn || {};
    if (!e.next && !(e.eps_est || []).length && !(e.hist || []).length) return "";
    const d = e.next ? daysTo(e.next) : null;
    const est = (e.eps_est || []).map((r) => {
      const rv = (e.rev_est || []).find((x) => x.period === r.period) || {};
      return `<tr><td>${PER[r.period] || r.period}</td><td class="num">${usd(r.avg)}</td><td class="num ${cls(r.growth)}">${pct(r.growth, 0)}</td>
        <td class="num">${big(rv.avg)}</td><td class="num ${cls(rv.growth)}">${pct(rv.growth, 0)}</td><td class="num muted">${r.numberOfAnalysts || ""}</td></tr>`;
    }).join("");
    const hist = (e.hist || []).slice(-4);
    const beats = hist.filter((h) => has(h.surprisePercent) && h.surprisePercent > 0).length;
    return `<div class="co-box"><div class="co-h">앞으로 실적은 <span class="muted small">— 애널리스트 예상치</span></div>
      ${e.next ? `<div class="co-next"><span class="k">다음 실적 발표</span><b>${e.next}</b>${d != null && d >= 0 ? `<span class="dday">${d === 0 ? "오늘" : "D-" + d}</span>` : ""}
        ${has(e.eps_avg) ? `<span class="muted">예상 주당순이익 ${usd(e.eps_avg)} (${usd(e.eps_low)}~${usd(e.eps_high)})</span>` : ""}</div>` : ""}
      ${est ? `<div class="tbl-wrap"><table class="co-tbl"><thead><tr><th>기간</th><th class="num">주당순이익</th><th class="num">성장</th><th class="num">매출</th><th class="num">성장</th><th class="num">명</th></tr></thead><tbody>${est}</tbody></table></div>` : ""}
      ${hist.length ? `<div class="co-sub">지난 ${hist.length}분기 — 예상보다 잘 나왔나 <span class="muted small">${beats}번 예상 상회</span></div>
        <div class="co-hist">${hist.map((h) => `<div class="${h.surprisePercent > 0 ? "beat" : h.surprisePercent < 0 ? "miss" : ""}"><span class="q">${esc((h.quarter || "").slice(0, 7))}</span>
          <b>${usd(h.epsActual)}</b><span class="muted">예상 ${usd(h.epsEstimate)}</span><span class="${cls(h.surprisePercent)}">${pct(h.surprisePercent, 1)}</span></div>`).join("")}</div>` : ""}
    </div>`;
  }

  function ours(row, rank, theme, sym) {
    if (!row) return "";
    const tn = (rank.themes || {})[row.theme];
    const trow = theme && theme.rows ? theme.rows.find((r) => r.key === row.theme) : null;
    const pick = trow && (trow.picks || []).find((x) => x.code === sym);
    const n = rank.rows.length, pos = rank.rows.slice().sort((a, b) => b.tp - a.tp).findIndex((r) => r.code === sym) + 1;
    return `<div class="co-box"><div class="co-h">우리 점수 <span class="muted small">${esc(rank.date)} 종가 기준</span></div>
      <div class="co-grid">
        ${cell("테마 눌림", `${Math.round(row.tp)}점`, `${n}종목 중 ${pos}위${row.basket ? " · 추천 바구니" : ""}`, "강한 테마 안에서 최근 5일 눌린 종목일수록 높아요 (미국 과거 검증 통과)")}
        ${cell("1년 모멘텀", has(row.mom) ? `${Math.round(row.mom)}점` : "—", "12-1 모멘텀 백분위")}
        ${cell("차트 점수", `${Math.round(row.ours)}점 · ${esc(row.grade)}`, "추세·수급·안정성 (참고용, 검증에선 효과 없음)")}
        ${!tn ? "" : cell("소속 테마", tn ? `<button class="link-btn" data-theme="${esc(row.theme)}">${esc(tn)}</button>` : "—", trow ? `테마 ${trow.rank}위 · ${esc(trow.status || "")}` : "")}
        ${cell("최근 5일", `<span class="${cls(row.rev5)}">${pct(row.rev5, 1)}</span>`)}
        ${pick && pick.plan ? cell("장기 테마 추천", `손익비 ${pick.plan.rr ? pick.plan.rr.toFixed(1) : "—"}`, `매수 ${usd(pick.plan.entry)} · 손절 ${usd(pick.plan.stop)} · 목표 ${usd(pick.plan.target)}`) : ""}
      </div></div>`;
  }

  function mood(p) {
    const s = p.social;
    if (!s || !s.n) return "";
    const tot = (s.bull || 0) + (s.bear || 0), r = tot ? s.bull / tot : null;
    return `<div class="co-box"><div class="co-h">개인 투자자 분위기 <span class="muted small">StockTwits 최근 글 ${s.n}개</span></div>
      ${tot ? `<div class="co-mood"><div class="bar"><i class="bull" style="flex:${s.bull}"></i><i class="bear" style="flex:${s.bear}"></i></div>
        <div class="lg"><span class="up">낙관 ${s.bull}</span><span>${r >= 0.7 ? "낙관 많음" : r <= 0.4 ? "비관 많음" : "엇갈림"}</span><span class="down">비관 ${s.bear}</span></div></div>` : `<p class="muted">의견 표시한 글이 없어요.</p>`}
      <p class="co-note">${has(s.watch) ? `${Number(s.watch).toLocaleString("ko-KR")}명이 지켜보는 중 · ` : ""}${esc(s.span || "")} · 개인 게시판 분위기는 반대 신호일 때도 많아요.</p></div>`;
  }

  function news(p) {
    const li = (a) => a.map((n) => `<li><a href="${esc(n.u)}" target="_blank" rel="noopener">${esc(n.t)}</a><span class="muted small">${esc(n.o || "")} · ${esc((n.at || "").slice(5))}</span></li>`).join("");
    const k = p.news_ko || [], e = p.news_en || [];
    if (!k.length && !e.length) return "";
    return `<div class="co-box"><div class="co-h">관련 뉴스 <span class="muted small">최근 2주</span></div>
      <div class="co-news">${k.length ? `<div><div class="co-sub">국내</div><ul>${li(k)}</ul></div>` : ""}${e.length ? `<div><div class="co-sub">해외</div><ul>${li(e)}</ul></div>` : ""}</div></div>`;
  }

  const foot = (p) => `<p class="co-foot">자료: Yahoo Finance (애널리스트 집계·재무), Google 뉴스, StockTwits · ${esc(p.made)} 기준 · 숫자는 참고용이고 투자 권유가 아니에요.</p>`;

  return { show };
})();
