/* =========================================================
 * 백테스트 탭
 *  - 한 종목 / 여러 종목(동일 비중 포트폴리오)
 *  - 결과: 지표, 매매 시점, 자산 곡선, 낙폭, 월별 수익, 거래 내역
 *  - 설정 자동 탐색: 학습 구간에서 고르고 검증 구간에서 확인
 *  - 저장한 결과 비교
 *  - 대화로 설정하기 (Claude API 또는 간단 모드)
 * ========================================================= */
const BTUI = (() => {
  const { $, $$, esc, krw, fmtPx, fmtWon, fmtPct, cls, store, toast, attachSearch, download, LC_OPTS } = U;
  const LC = LightweightCharts;
  const UP = "#f0525c", DOWN = "#3d8bfd", GOLD = "#ffffff", MUTED = "#9a9aa2", MINT = "#4fd1a5";
  const OPT_KEYS = ["direction", "sizing", "sizePct", "riskPct", "atrMult", "pyrN", "pyrMode", "pyrPct", "tp1Pct", "tp1Frac",
    "stopLoss", "takeProfit", "trailing", "maxHold", "dayClose", "capital", "buyFee", "sellFee", "slip", "borrowFee", "volCap", "tick", "limit"];
  const BOOL = new Set(["dayClose", "tick", "limit"]), STR = new Set(["direction", "sizing", "pyrMode"]);
  const RUNS_KEY = "tradingdesk.runs", BASKET_KEY = "tradingdesk.basket", FORM_KEY = "tradingdesk.btform";
  const DIR = { 1: "롱", "-1": "숏" };

  const S = {
    ctx: null, mode: "single", sym: null, csv: null, last: null, charts: null, search: null,
    basketCustom: store.get(BASKET_KEY, []),
    rules: {
      entry: { logic: "AND", rules: [
        { a: { ind: "rsi", n: 14 }, op: "cross_up", b: { ind: "num", v: 30 } },
        { a: { ind: "volume" }, op: ">", b: { ind: "vol_sma", n: 20 }, mult: 1.5 },
      ] },
      exit: { logic: "OR", rules: [
        { a: { ind: "rsi", n: 14 }, op: "cross_up", b: { ind: "num", v: 70 } },
        { a: { ind: "close" }, op: "<", b: { ind: "ll", n: 10 } },
      ] },
    },
    opt: { running: false, stop: false, result: null, heat: "train" },
  };

  // ================= 폼 읽기/쓰기 =================
  const num = (v) => (v === "" || v == null ? 0 : +v);
  function readOpt() {
    const o = {};
    OPT_KEYS.forEach((k) => {
      const el = $("#o-" + k);
      o[k] = BOOL.has(k) ? el.checked : STR.has(k) ? el.value : num(el.value);
    });
    o.pyrN = Math.max(1, Math.round(o.pyrN)); o.maxHold = Math.max(0, Math.round(o.maxHold));
    return o;
  }
  function writeOpt(o) {
    Object.entries(o || {}).forEach(([k, v]) => {
      const el = $("#o-" + k);
      if (!el || v === undefined) return;
      if (BOOL.has(k)) el.checked = !!v; else el.value = v;
    });
    updateWhen();
  }
  function readParams() {
    const sid = $("#bt-strategy").value, St = BT.STRATEGIES[sid], p = {};
    St.params.forEach((d) => { const el = $(`[data-p="${d.key}"]`); p[d.key] = d.type === "select" ? el.value : +el.value; });
    if (sid === "custom") p.rules = readRules();
    return p;
  }
  function readSettings() {
    return {
      mode: S.mode, symbol: S.mode === "single" && !S.csv ? curSym() : null, csv: S.csv ? S.csv.name : null,
      basket: $("#bt-basket").value, basketList: [...S.basketCustom],
      interval: $("#bt-interval").value, start: $("#bt-start").value, end: $("#bt-end").value,
      strategy: $("#bt-strategy").value, params: readParams(), opt: readOpt(),
    };
  }
  function writeSettings(s) {
    if (s.mode) setMode(s.mode);
    if (s.symbol) { S.sym = s.symbol; S.csv = null; S.search.set(s.symbol); $("#bt-csv-name").textContent = ""; }
    if (s.basket) { $("#bt-basket").value = s.basket; syncBasket(); }
    if (s.basketList) { S.basketCustom = s.basketList; store.set(BASKET_KEY, S.basketCustom); renderTags(); }
    if (s.interval) $("#bt-interval").value = s.interval;
    if (s.start !== undefined) $("#bt-start").value = s.start || "";
    if (s.end !== undefined) $("#bt-end").value = s.end || "";
    if (s.strategy) { $("#bt-strategy").value = s.strategy; renderParams(); }
    if (s.params) {
      const St = BT.STRATEGIES[$("#bt-strategy").value];
      St.params.forEach((d) => { if (s.params[d.key] !== undefined) $(`[data-p="${d.key}"]`).value = s.params[d.key]; });
      if (s.params.rules) { S.rules = JSON.parse(JSON.stringify(s.params.rules)); renderRules(); }
    }
    if (s.opt) writeOpt(s.opt);
    saveForm();
  }
  const saveForm = () => store.set(FORM_KEY, readSettings());
  const curSym = () => S.sym || (S.ctx && S.ctx.current());

  // data-when="sizing=fixed", "pyrN>1&pyrMode!=signal", "direction!=long"
  function updateWhen() {
    const o = {};
    OPT_KEYS.forEach((k) => { const el = $("#o-" + k); o[k] = BOOL.has(k) ? el.checked : el.value; });
    $$("#bt-controls [data-when]").forEach((el) => {
      const ok = el.dataset.when.split("&").every((cond) => {
        const m = cond.match(/^(\w+)(!=|=|>)(.+)$/);
        if (!m) return true;
        const v = o[m[1]];
        return m[2] === "=" ? String(v) === m[3] : m[2] === "!=" ? String(v) !== m[3] : +v > +m[3];
      });
      el.hidden = !ok;
    });
  }

  // ================= 대상 =================
  function setMode(m) {
    S.mode = m;
    $$("#bt-mode button").forEach((b) => b.classList.toggle("on", b.dataset.mode === m));
    $$("#bt-controls [data-show]").forEach((el) => (el.hidden = el.dataset.show !== m));
  }
  function syncBasket() {
    const v = $("#bt-basket").value;
    $("#bt-basket-pick").hidden = v !== "custom";
    const note = { watch: "watchlist.json 종목과 별표로 추가한 종목이에요.", top20: "현재 시가총액 기준이라 과거 성과가 실제보다 좋게 보일 수 있어요(살아남은 종목만 고른 효과).", top50: "현재 시가총액 기준이라 과거 성과가 실제보다 좋게 보일 수 있어요. 종목이 많아 처음엔 불러오는 데 시간이 걸려요." }[v] || "검색해서 종목을 추가하세요.";
    $("#bt-basket-note").textContent = note + (v !== "watch" && !Data.getProxy() ? " 관심종목 외 종목은 시세 중계 서버가 필요해요." : "");
  }
  function renderTags() {
    $("#bt-basket-tags").innerHTML = S.basketCustom.map((s) => `<span class="tag">${esc(Data.info(s).name)}<button data-rm="${esc(s)}" title="빼기">✕</button></span>`).join("")
      || `<span class="muted small">아직 고른 종목이 없어요.</span>`;
    $$("#bt-basket-tags [data-rm]").forEach((b) => b.addEventListener("click", () => {
      S.basketCustom = S.basketCustom.filter((x) => x !== b.dataset.rm); store.set(BASKET_KEY, S.basketCustom); renderTags();
    }));
  }
  async function basketSymbols() {
    const v = $("#bt-basket").value;
    if (v === "custom") return [...S.basketCustom];
    if (v === "watch") {
      const base = Data.meta.symbols.map((s) => s.symbol);
      return [...base, ...store.get("tradingdesk.favs", []).filter((s) => !base.includes(s))];
    }
    const list = await Data.loadSymbols();
    const n = v === "top50" ? 50 : 20;
    return list.filter((s) => (s.market === "KOSPI" || s.market === "KOSDAQ") && /0\.(KS|KQ)$/.test(s.symbol)).slice(0, n).map((s) => s.symbol);
  }

  // ================= 전략 화면 =================
  function renderParams() {
    const sid = $("#bt-strategy").value, St = BT.STRATEGIES[sid];
    $("#bt-desc").textContent = St.desc;
    $("#bt-params").innerHTML = St.params.map((p) => p.type === "select"
      ? `<label>${p.label}<select data-p="${p.key}">${p.options.map((o) => `<option ${o === p.def ? "selected" : ""}>${o}</option>`).join("")}</select></label>`
      : `<label>${p.label}<input type="number" data-p="${p.key}" value="${p.def}" min="${p.min ?? ""}" max="${p.max ?? ""}" step="${p.step ?? 1}"></label>`).join("");
    $("#bt-custom").hidden = sid !== "custom";
    if (sid === "custom") renderRules();
    renderRanges();
  }

  // ---------- 조건 조합 ----------
  function specHTML(s, role) {
    const opts = Object.entries(BT.IND).filter(([k]) => role === "b" || k !== "num")
      .map(([k, d]) => `<option value="${k}" ${k === s.ind ? "selected" : ""}>${d.label}</option>`).join("");
    const d = BT.IND[s.ind] || { args: [] };
    const args = d.args.map((a) => `<input type="number" data-f="${a}" value="${s[a] ?? (d.def || {})[a] ?? ""}" step="${a === "k" ? 0.1 : a === "v" ? "any" : 1}" title="${a === "n" ? "기간" : a === "m" ? "긴 기간" : a === "k" ? "배수" : "값"}" class="arg ${a}">`).join("");
    return `<span class="spec" data-role="${role}"><select data-f="ind">${opts}</select>${args}</span>`;
  }
  function renderRules() {
    ["entry", "exit"].forEach((g) => {
      const box = $(`.rule-group[data-group="${g}"]`), grp = S.rules[g];
      $("[data-logic]", box).value = grp.logic;
      $(".rules", box).innerHTML = grp.rules.map((r, i) => `<div class="rule" data-i="${i}">
          ${specHTML(r.a, "a")}
          <select data-f="op">${Object.entries(BT.OPS).map(([k, v]) => `<option value="${k}" ${k === r.op ? "selected" : ""}>${v}</option>`).join("")}</select>
          ${specHTML(r.b, "b")}
          <label class="mult" title="오른쪽 값에 곱할 배수">×<input type="number" data-f="mult" value="${r.mult ?? 1}" step="0.1"></label>
          <button class="del" data-del-rule title="삭제">✕</button>
        </div>`).join("") || `<div class="muted small">조건이 없으면 신호가 나오지 않아요.</div>`;
    });
  }
  function readRules() {
    const out = {};
    ["entry", "exit"].forEach((g) => {
      const box = $(`.rule-group[data-group="${g}"]`);
      out[g] = { logic: $("[data-logic]", box).value, rules: $$(".rule", box).map((row) => {
        const spec = (role) => {
          const el = $(`.spec[data-role="${role}"]`, row), s = { ind: $('[data-f="ind"]', el).value };
          $$(".arg", el).forEach((inp) => (s[inp.dataset.f] = +inp.value));
          return s;
        };
        return { a: spec("a"), op: $('[data-f="op"]', row).value, b: spec("b"), mult: +$('[data-f="mult"]', row).value || 1 };
      }) };
    });
    S.rules = out;
    return out;
  }
  function initRules() {
    $("#bt-custom").addEventListener("change", (e) => {
      readRules();
      if (e.target.dataset.f === "ind") renderRules(); // 지표가 바뀌면 입력칸 다시 그리기
      saveForm();
    });
    $("#bt-custom").addEventListener("click", (e) => {
      const g = e.target.closest(".rule-group");
      if (!g) return;
      readRules();
      if (e.target.matches("[data-add-rule]")) S.rules[g.dataset.group].rules.push({ a: { ind: "close" }, op: ">", b: { ind: "sma", n: 20 }, mult: 1 });
      else if (e.target.matches("[data-del-rule]")) S.rules[g.dataset.group].rules.splice(+e.target.closest(".rule").dataset.i, 1);
      else return;
      renderRules(); saveForm();
    });
  }

  // ================= 데이터 =================
  function parseCSV(text) {
    const lines = text.trim().split(/\r?\n/).filter(Boolean);
    const head = lines[0].split(/[,;\t]/).map((h) => h.trim().replace(/^"|"$/g, "").toLowerCase());
    const find = (...n) => head.findIndex((h) => n.includes(h));
    const it = find("time", "date", "datetime", "timestamp", "날짜", "일자"), io = find("open", "시가"), ih = find("high", "고가"),
      il = find("low", "저가"), ic = find("close", "종가", "adj close"), iv = find("volume", "거래량", "vol");
    if ([it, io, ih, il, ic].some((x) => x < 0)) throw new Error("time, open, high, low, close 열이 필요해요");
    const raw = lines.slice(1).map((ln) => {
      const c = ln.split(/[,;\t]/).map((x) => x.trim().replace(/^"|"$/g, ""));
      let ms;
      if (/^\d+(\.\d+)?$/.test(c[it])) { ms = +c[it]; if (ms < 1e12) ms *= 1000; }
      else ms = Date.parse(/[T ]/.test(c[it]) ? c[it] : c[it] + "T00:00:00Z");
      return { ms, o: +c[io], h: +c[ih], l: +c[il], c: +c[ic], v: iv >= 0 ? +c[iv] || 0 : 0 };
    }).filter((b) => !isNaN(b.ms) && !isNaN(b.c) && b.o > 0).sort((a, b) => a.ms - b.ms);
    if (raw.length < 30) throw new Error("데이터가 너무 적어요 (30봉 이상 필요)");
    const gaps = raw.slice(1, 200).map((b, i) => b.ms - raw[i].ms).sort((a, b) => a - b);
    const intraday = gaps[Math.floor(gaps.length / 2)] < 86400000 * 0.9;
    const bars = raw.map((b) => intraday ? { ...b, t: Math.floor(b.ms / 1000) + Data.KST, day: Data.kstDay(b.ms) }
      : { ...b, t: new Date(b.ms).toISOString().slice(0, 10), day: new Date(b.ms).toISOString().slice(0, 10) });
    return { bars: bars.filter((b, i) => i === 0 || b.t !== bars[i - 1].t), intraday };
  }
  function dateFilter(all) {
    const s = Date.parse($("#bt-start").value + "T00:00:00Z") - Data.KST * 1000;
    const e = Date.parse($("#bt-end").value + "T23:59:59Z") - Data.KST * 1000;
    return all.filter((b) => (isNaN(s) || b.ms >= s) && (isNaN(e) || b.ms <= e));
  }
  async function loadSeries(sym) {
    const iv = $("#bt-interval").value;
    const bars = dateFilter(await Data.getBars(sym, iv));
    return { sym, bars, title: Data.info(sym).name, intraday: !Data.IV[iv].daily };
  }
  const labelFn = (bars, intraday) => (i) => intraday ? new Date(bars[i].ms + Data.KST * 1000).toISOString().slice(0, 16).replace("T", " ") : bars[i].day;

  function engineOpt(sym, bars, intraday, base) {
    const o = { ...(base || readOpt()) };
    const kr = !sym || krw(sym);
    o.dayKey = intraday ? (i) => bars[i].day : null;
    if (!intraday) o.dayClose = false;
    o.tick = o.tick && kr; o.limit = o.limit && kr;
    o.etf = !!sym && (Data.info(sym).market === "ETF" || /^(KODEX|TIGER|KBSTAR|ACE|SOL|HANARO|ARIRANG|KOSEF|RISE|PLUS)\b/.test(Data.info(sym).name));
    // 국내 ETF는 매도 시 증권거래세가 없음 → 매도 비용에서 세금(0.20%)만 뺌
    if (o.etf && kr && o.sellFee >= 0.2) { o.sellFee = +(o.sellFee - 0.2).toFixed(4); o.etfTaxFree = true; }
    return o;
  }

  // 코스피200 비교 (일봉, 한국 종목일 때만)
  async function benchFor(bars) {
    if ($("#bt-interval").value !== "1d") return null;
    try {
      const b = await Data.getBars("069500.KS", "1d");
      const m = new Map(b.map((x) => [x.day, x.c]));
      let last = NaN;
      const closes = bars.map((x) => { const v = m.get(x.day); if (v) last = v; return last; });
      const first = closes.find((v) => isFinite(v));
      if (!first) return null;
      return closes.map((v) => (isFinite(v) ? v / first : 1));
    } catch (_) { return null; }
  }

  // ================= 실행: 한 종목 =================
  async function runSingle(silent) {
    let src;
    if (S.csv) src = { sym: null, bars: dateFilter(S.csv.bars), title: S.csv.name, intraday: S.csv.intraday };
    else {
      const sym = curSym();
      if (!sym) throw new Error("종목을 골라주세요.");
      src = await loadSeries(sym);
    }
    if (src.bars.length < 30) throw new Error("선택한 기간의 봉이 30개 미만이에요. 기간을 늘려주세요.");
    const sid = $("#bt-strategy").value, p = readParams();
    const opt = engineOpt(src.sym, src.bars, src.intraday);
    const res = BT.run(src.bars, sid, p, opt);
    const bench = src.sym && krw(src.sym) ? await benchFor(src.bars) : null;
    S.last = { kind: "single", ...src, res, sid, p, opt, bench, label: labelFn(src.bars, src.intraday), settings: readSettings() };
    renderSingle(S.last);
    return S.last;
  }

  // ================= 실행: 여러 종목 =================
  async function loadBasket(onProgress) {
    const syms = await basketSymbols();
    if (!syms.length) throw new Error("묶음에 종목이 없어요.");
    const out = [], fails = [];
    let done = 0, idx = 0;
    const worker = async () => {
      while (idx < syms.length) {
        const s = syms[idx++];
        try { const r = await loadSeries(s); if (r.bars.length >= 30) out.push(r); else fails.push(`${Data.info(s).name}(데이터 부족)`); }
        catch (e) { fails.push(`${Data.info(s).name}${e.needProxy ? "(중계 서버 필요)" : ""}`); }
        onProgress && onProgress(++done, syms.length);
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    out.sort((a, b) => syms.indexOf(a.sym) - syms.indexOf(b.sym));
    if (!out.length) throw new Error("불러온 종목이 없어요. " + (fails.length ? fails.slice(0, 5).join(", ") : ""));
    return { list: out, fails };
  }
  // 종목별 자산을 시간축에 맞춰 합친 동일 비중 포트폴리오
  function combine(list, eqOf, capEach) {
    const daily = !list[0].intraday;
    const times = [...new Set(list.flatMap((x) => x.bars.map((b) => b.ms)))].sort((a, b) => a - b);
    const dayOf = new Map();
    list.forEach((x) => x.bars.forEach((b) => dayOf.set(b.ms, b.day)));
    const ptr = list.map(() => 0), lastV = list.map(() => capEach);
    const total = times.map((ms) => {
      let s = 0;
      list.forEach((x, k) => {
        const bs = x.bars;
        while (ptr[k] < bs.length && bs[ptr[k]].ms <= ms) { lastV[k] = eqOf(x, ptr[k]); ptr[k]++; }
        s += lastV[k];
      });
      return s;
    });
    const t = times.map((ms) => (daily ? dayOf.get(ms) : Math.floor(ms / 1000) + Data.KST));
    return { times, t, days: times.map((ms) => dayOf.get(ms)), total };
  }
  async function runBasket(silent, progressEl) {
    const btn = progressEl || $("#bt-run");
    const { list, fails } = await loadBasket((d, n) => (btn.textContent = `불러오는 중 ${d}/${n}`));
    btn.textContent = "계산 중…";
    const sid = $("#bt-strategy").value, p = readParams(), base = readOpt();
    const capEach = base.capital / list.length;
    list.forEach((x) => {
      x.opt = engineOpt(x.sym, x.bars, x.intraday, { ...base, capital: capEach });
      x.res = BT.run(x.bars, sid, p, x.opt);
    });
    const port = combine(list, (x, i) => x.res.equity[i], capEach);
    const bh = combine(list, (x, i) => (capEach * x.bars[i].c) / x.bars[0].o, capEach);
    const pbars = port.times.map((ms, i) => ({ ms, day: port.days[i], t: port.t[i], o: bh.total[0], c: bh.total[i] }));
    const trades = list.flatMap((x) => x.res.trades.map((t) => ({ ...t, sym: x.sym, name: x.title, label: labelFn(x.bars, x.intraday) })));
    trades.sort((a, b) => a.label(a.exitIdx) < b.label(b.exitIdx) ? -1 : 1);
    const st = BT.stats(pbars, port.total, trades, { capital: base.capital }, null);
    st.buyHold = (bh.total[bh.total.length - 1] / base.capital - 1) * 100;
    st.exposure = list.reduce((s, x) => s + x.res.stats.exposure, 0) / list.length;
    st.blocked = list.reduce((s, x) => s + x.res.stats.blocked, 0);
    st.capped = list.reduce((s, x) => s + x.res.stats.capped, 0);
    const rets = list.map((x) => x.res.stats.totalRet).sort((a, b) => a - b);
    st.posShare = list.filter((x) => x.res.stats.totalRet > 0).length / list.length * 100;
    st.beatShare = list.filter((x) => x.res.stats.totalRet > x.res.stats.buyHold).length / list.length * 100;
    st.median = rets[Math.floor(rets.length / 2)];
    let bench = null;
    if (krw(list[0].sym)) bench = await benchFor(pbars);
    S.last = { kind: "basket", list, fails, port, bh, pbars, trades, stats: st, sid, p, opt: base, bench, intraday: list[0].intraday,
      title: `${$("#bt-basket").selectedOptions[0].textContent} (${list.length}종목)`, settings: readSettings() };
    renderBasket(S.last);
    return S.last;
  }

  async function run(silent = false) {
    const btn = $("#bt-run"); btn.disabled = true; btn.textContent = "계산 중…";
    saveForm();
    try {
      const r = S.mode === "basket" ? await runBasket(silent) : await runSingle(silent);
      showSub("result");
      return r;
    } catch (err) {
      const msg = err.needProxy ? "이 종목은 ⚙ 설정에서 시세 중계 서버를 연결해야 백테스트할 수 있어요." : err.message;
      if (silent) throw new Error(msg);
      toast(esc(msg), true);
    } finally { btn.disabled = false; btn.textContent = "백테스트 실행"; }
  }

  // ================= 내 목표 기준 =================
  const GOAL_KEY = "tradingdesk.goal";
  const GOAL_DEF = { winMin: 50, winMax: "", payoff: 1.5, trades: 100, mdd: -20, worstDay: -3 };
  const goal = () => ({ ...GOAL_DEF, ...store.get(GOAL_KEY, {}) });
  function goalChecks(st) {
    const g = goal(), max = g.winMax === "" || g.winMax == null ? 100 : +g.winMax;
    const f2 = (v) => (isFinite(v) ? v.toFixed(2) : "∞");
    return [
      { label: "승률", need: `${g.winMin}~${max === 100 ? "" : max}%`, value: st.trades ? st.winRate.toFixed(1) + "%" : "—", pass: st.trades > 0 && st.winRate >= +g.winMin && st.winRate <= max },
      { label: "손익비 (평균 수익÷평균 손실)", need: `${g.payoff} 이상`, value: f2(st.payoff), pass: st.payoff >= +g.payoff },
      { label: "거래당 기대값", need: "0보다 큼", value: fmtPct(st.expectancy), pass: st.expectancy > 0 },
      { label: "거래 수", need: `${g.trades}회 이상`, value: st.trades + "회", pass: st.trades >= +g.trades },
      { label: "최대 낙폭", need: `${g.mdd}% 이내`, value: fmtPct(st.mdd), pass: st.mdd >= +g.mdd },
      { label: "하루 최대 손실", need: `${g.worstDay}% 이내`, value: fmtPct(st.worstDay), pass: st.worstDay >= +g.worstDay },
    ];
  }
  const goalPassTrain = (t) => {
    const g = goal(), max = g.winMax === "" || g.winMax == null ? 100 : +g.winMax;
    return t.trades > 0 && t.win >= +g.winMin && t.win <= max && t.payoff >= +g.payoff && t.mdd >= +g.mdd && t.exp > 0;
  };
  function renderGoal(st) {
    const cs = goalChecks(st), passN = cs.filter((c) => c.pass).length;
    $("#goal-chips").innerHTML = `<div class="goal-score ${passN === cs.length ? "up" : ""}">${passN} / ${cs.length} 통과</div>` +
      cs.map((c) => `<div class="goal-chip ${c.pass ? "pass" : "fail"}"><span class="gi">${c.pass ? "✓" : "✕"}</span>
        <span class="gl">${esc(c.label)}</span><b>${esc(c.value)}</b><span class="gn">기준 ${esc(c.need)}</span></div>`).join("");
  }
  function initGoal() {
    const fill = () => { const g = goal(); Object.keys(GOAL_DEF).forEach((k) => ($("#g-" + k).value = g[k])); };
    fill();
    $("#goal-edit").addEventListener("click", () => { const f = $("#goal-form"); f.hidden = !f.hidden; $("#goal-edit").textContent = f.hidden ? "기준 바꾸기" : "닫기"; });
    $("#goal-form").addEventListener("change", () => {
      const g = {};
      Object.keys(GOAL_DEF).forEach((k) => { const v = $("#g-" + k).value; g[k] = k === "winMax" && v === "" ? "" : +v; });
      store.set(GOAL_KEY, g);
      const st = S.last && (S.last.kind === "basket" ? S.last.stats : S.last.res.stats);
      if (st) renderGoal(st);
      if (S.opt.result) renderOpt();
    });
  }

  // ================= 일별 손익 =================
  function renderDaily(st) {
    const d = st.dailyRets || [];
    const card = (k, v, c = "") => `<div class="ds"><span>${k}</span><b class="${c}">${v}</b></div>`;
    $("#bt-daystats").innerHTML = d.length
      ? card("거래한 날", `${st.activeDays}일 / ${st.days}일`) + card("플러스인 날", st.posDays.toFixed(1) + "%", st.posDays >= 50 ? "up" : "down") +
        card("하루 평균", fmtPct(st.avgDay), cls(st.avgDay)) + card("가장 좋은 날", fmtPct(st.bestDay), "up") + card("가장 나쁜 날", fmtPct(st.worstDay), "down")
      : `<span class="muted small">포지션을 들고 있던 날이 없어요.</span>`;
    if (!d.length) { $("#bt-histo").innerHTML = ""; return; }
    // 분포: 0을 가운데로 대칭 구간
    const lim = Math.max(0.5, Math.ceil(Math.max(...d.map(Math.abs)) * 2) / 2), steps = 20, w = (2 * lim) / steps;
    const bins = new Array(steps).fill(0);
    d.forEach((v) => { bins[Math.min(steps - 1, Math.max(0, Math.floor((v + lim) / w)))]++; });
    const mx = Math.max(...bins);
    $("#bt-histo").innerHTML = `<div class="hbars">${bins.map((c, i) => {
      const lo = -lim + i * w, hi = lo + w, pos = lo >= 0;
      return `<div class="hb" title="${lo.toFixed(2)}% ~ ${hi.toFixed(2)}%: ${c}일"><i style="height:${(c / mx) * 100}%;background:${pos ? UP : DOWN}"></i></div>`;
    }).join("")}</div><div class="haxis"><span>${(-lim).toFixed(1)}%</span><span>0</span><span>+${lim.toFixed(1)}%</span></div>`;
  }

  // ================= 결과 화면 =================
  function initCharts() {
    const pc = LC.createChart($("#bt-price"), LC_OPTS()), ec = LC.createChart($("#bt-equity"), LC_OPTS()), dc = LC.createChart($("#bt-dd"), LC_OPTS());
    const candles = pc.addSeries(LC.CandlestickSeries, { upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN, wickUpColor: UP, wickDownColor: DOWN });
    const won = { type: "price", precision: 0, minMove: 1 };
    S.charts = {
      pc, ec, dc, candles, marks: LC.createSeriesMarkers(candles, []), lines: [],
      eq: ec.addSeries(LC.LineSeries, { color: GOLD, lineWidth: 2, priceLineVisible: false, priceFormat: won }),
      bh: ec.addSeries(LC.LineSeries, { color: MUTED, lineWidth: 1, lineStyle: 2, priceLineVisible: false, priceFormat: won }),
      bench: ec.addSeries(LC.LineSeries, { color: MINT, lineWidth: 1, priceLineVisible: false, priceFormat: won }),
      dd: dc.addSeries(LC.AreaSeries, { lineColor: DOWN, topColor: "rgba(61,139,253,.05)", bottomColor: "rgba(61,139,253,.35)", lineWidth: 1, priceLineVisible: false, priceFormat: { type: "price", precision: 1, minMove: 0.1 } }),
    };
    dc.applyOptions({ localization: { locale: "ko-KR", priceFormatter: (v) => v.toFixed(1) + "%" } });
    ec.applyOptions({ localization: { locale: "ko-KR", priceFormatter: (v) => Math.round(v).toLocaleString("ko-KR") } });
    let syncing = false;
    const link = (a, others) => a.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      if (syncing || !r) return; syncing = true; others.forEach((o) => o.timeScale().setVisibleLogicalRange(r)); syncing = false;
    });
    link(ec, [dc]); link(dc, [ec]);
  }
  function chartTime(intraday) {
    [S.charts.pc, S.charts.ec, S.charts.dc].forEach((c) => c.applyOptions({ timeScale: { timeVisible: intraday } }));
  }

  function metricCards(st, extra = []) {
    const card = (k, v, c = "", x = "") => `<div class="stat ${x}"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`;
    const f2 = (v) => (v == null || !isFinite(v) ? "—" : v.toFixed(2));
    return [
      card("총 수익률", fmtPct(st.totalRet), cls(st.totalRet), "hero"),
      card("최종 자산", fmtWon(st.final)),
      card("보유만 했을 때", fmtPct(st.buyHold), cls(st.buyHold)),
      ...extra,
      card("연환산 (CAGR)", st.cagr == null ? "—" : fmtPct(st.cagr), cls(st.cagr)),
      card("최대 낙폭 (MDD)", fmtPct(st.mdd), "down"),
      card("샤프 지수", f2(st.sharpe)),
      card("소르티노 지수", f2(st.sortino)),
      card("칼마 지수", f2(st.calmar)),
      card("거래 수", String(st.trades)),
      card("승률", st.trades ? st.winRate.toFixed(1) + "%" : "—"),
      card("평균 수익 / 손실", `${fmtPct(st.avgWin, 1)} / ${fmtPct(st.avgLoss, 1)}`),
      card("손익비 (평균 수익÷손실)", !isFinite(st.payoff) ? "∞" : st.payoff.toFixed(2)),
      card("총이익÷총손실 (PF)", !isFinite(st.profitFactor) ? "∞" : st.profitFactor.toFixed(2)),
      card("플러스인 날", st.activeDays ? st.posDays.toFixed(1) + "%" : "—"),
      card("거래당 기대값", fmtPct(st.expectancy), cls(st.expectancy)),
      ...(st.avgR != null ? [card("평균 R (손절 폭 대비)", (st.avgR >= 0 ? "+" : "") + st.avgR.toFixed(2) + "R", cls(st.avgR))] : []),
      card("최대 연속 손실", st.maxLoseStreak + "회"),
      card("평균 보유", st.avgHold.toFixed(1) + "봉"),
      card("시장 노출", st.exposure.toFixed(1) + "%"),
    ].join("");
  }
  function warnings(st, kind) {
    const w = [];
    const L = S.last;
    if (L && ((L.opt && L.opt.etfTaxFree) || (L.list && L.list.some((x) => x.opt.etfTaxFree)))) w.push("ETF는 매도 시 증권거래세가 없어서 매도 비용에서 세금 0.20%를 빼고 계산했어요.");
    if (st.trades < 20) w.push(`거래가 ${st.trades}회뿐이라 우연히 나온 결과일 수 있어요.`);
    if (st.blocked) w.push(`상·하한가 때문에 ${st.blocked}번 체결하지 못했어요.`);
    if (st.capped) w.push(`거래량 한도 때문에 ${st.capped}번 주문을 줄여서 체결했어요.`);
    if (kind === "basket" && $("#bt-basket").value.startsWith("top")) w.push("현재 시가총액 상위 종목을 과거에 적용해서 실제보다 좋게 나왔을 수 있어요.");
    const el = $("#bt-warn"); el.hidden = !w.length; el.innerHTML = w.map(esc).join("<br/>");
  }
  function renderEquity(t, eq, bh, bench, cap, dd) {
    const C = S.charts;
    C.eq.setData(t.map((x, i) => ({ time: x, value: eq[i] })));
    C.bh.setData(t.map((x, i) => ({ time: x, value: bh[i] })));
    C.bench.setData(bench ? t.map((x, i) => ({ time: x, value: cap * bench[i] })) : []);
    $("#bench-legend").hidden = !bench;
    C.dd.setData(t.map((x, i) => ({ time: x, value: dd[i] })));
    C.ec.timeScale().fitContent(); C.dc.timeScale().fitContent();
  }
  function renderMonthly(monthly) {
    const years = {};
    Object.entries(monthly).forEach(([k, v]) => { const [y, m] = k.split("-"); (years[y] = years[y] || {})[+m] = v; });
    const cell = (v) => {
      if (v == null) return `<td></td>`;
      const a = Math.min(Math.abs(v) / 10, 1) * 0.55 + 0.06;
      const bg = v >= 0 ? `rgba(240,82,92,${a})` : `rgba(61,139,253,${a})`;
      return `<td class="r" style="background:${bg}">${v.toFixed(1)}</td>`;
    };
    const rows = Object.keys(years).sort().reverse().map((y) => {
      const ms = years[y];
      const yr = (Object.values(ms).reduce((p, v) => p * (1 + v / 100), 1) - 1) * 100;
      return `<tr><th>${y}</th>${Array.from({ length: 12 }, (_, i) => cell(ms[i + 1])).join("")}<td class="r yr ${cls(yr)}"><b>${yr.toFixed(1)}</b></td></tr>`;
    }).join("");
    $("#bt-monthly").innerHTML = `<thead><tr><th></th>${Array.from({ length: 12 }, (_, i) => `<th class="r">${i + 1}월</th>`).join("")}<th class="r">연간</th></tr></thead><tbody>${rows}</tbody>`;
  }
  function renderTrades(trades, open, labelOf, symOf) {
    const rows = trades.map((t, i) => `<tr><td>${i + 1}</td><td class="${t.side > 0 ? "up" : "down"}">${DIR[t.side]}</td>
      <td>${t.name ? `<b>${esc(t.name)}</b> ` : ""}${labelOf(t, t.entryIdx)}</td><td class="r">${fmtPx(t.entryPx, symOf(t))}</td>
      <td>${labelOf(t, t.exitIdx)}</td><td class="r">${fmtPx(t.exitPx, symOf(t))}</td><td class="r">${t.bars}봉</td>
      <td class="r ${cls(t.ret)}">${fmtPct(t.ret)}</td><td>${esc(t.reason)}${t.adds ? ` · 추가 ${t.adds}회` : ""}${t.partial ? " · 1차 익절" : ""}</td></tr>`);
    if (open) rows.push(`<tr><td>—</td><td class="${open.side > 0 ? "up" : "down"}">${DIR[open.side]}</td><td>${labelOf(open, open.entryIdx)}</td>
      <td class="r">${fmtPx(open.entryPx, symOf(open))}</td><td class="sub">보유 중</td><td class="r">${fmtPx(open.lastPx, symOf(open))}</td><td class="r">—</td>
      <td class="r ${cls(open.ret)}">${fmtPct(open.ret)}</td><td>평가</td></tr>`);
    const shown = rows.reverse();
    $("#bt-trades tbody").innerHTML = shown.length ? shown.slice(0, 500).join("") + (shown.length > 500 ? `<tr class="empty-row"><td colspan="9">최근 500건만 보여요. 전체는 CSV로 저장하세요.</td></tr>` : "")
      : `<tr class="empty-row"><td colspan="9">이 기간에는 매매 신호가 없었어요. 기간을 늘리거나 설정을 바꿔보세요.</td></tr>`;
  }

  function renderSingle(run) {
    const { res: r, bars, sym, label, bench, opt } = run, st = r.stats, C = S.charts;
    $("#bt-metrics").innerHTML = metricCards(st, bench ? [`<div class="stat"><div class="k">코스피200 (같은 기간)</div><div class="v ${cls(bench[bench.length - 1] - 1)}">${fmtPct((bench[bench.length - 1] - 1) * 100)}</div></div>`] : []);
    warnings(st, "single");
    $("#bt-basket-box").hidden = true; $("#bt-price-box").hidden = false;
    $("#bt-range").textContent = `${run.title} · ${label(0)} ~ ${label(bars.length - 1)} · ${bars.length.toLocaleString()}개 봉`;
    chartTime(run.intraday);
    const pf = krw(sym) ? { type: "price", precision: 0, minMove: 1 } : { type: "price", precision: 2, minMove: 0.01 };
    C.candles.applyOptions({ priceFormat: pf });
    C.pc.applyOptions({ localization: { locale: "ko-KR", priceFormatter: (v) => fmtPx(v, sym) } });
    C.candles.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    C.lines.forEach((s) => C.pc.removeSeries(s));
    C.lines = r.lines.map((ln) => {
      const s = C.pc.addSeries(LC.LineSeries, { color: ln.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(bars.map((b, i) => ({ time: b.t, value: ln.data[i] })).filter((x) => isFinite(x.value))); return s;
    });
    // 차트 셋업: 거래마다 손절선(파랑)·목표선(빨강)을 진입~청산 구간에만 그림 (최근 80거래)
    const planned = [...r.trades, ...(r.open ? [{ ...r.open, exitIdx: bars.length - 1 }] : [])].filter((t) => isFinite(t.stopPx)).slice(-80);
    planned.forEach((t) => {
      [["stopPx", "#3d8bfd"], ["targetPx", "#f0525c"]].forEach(([key, col]) => {
        if (!isFinite(t[key])) return;
        const s = C.pc.addSeries(LC.LineSeries, { color: col, lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        s.setData([{ time: bars[t.entryIdx].t, value: t[key] }, ...(t.exitIdx > t.entryIdx ? [{ time: bars[t.exitIdx].t, value: t[key] }] : [])]);
        C.lines.push(s);
      });
    });
    const tradeAt = new Map(r.trades.map((t) => [t.exitIdx, t]));
    const marks = r.fills.map((f) => {
      const t = tradeAt.get(f.i);
      const closing = f.kind === "close" && t;
      const text = f.kind === "add" ? "추가" : f.kind === "tp1" ? "1차 익절" : closing ? `${t.ret >= 0 ? "+" : ""}${t.ret.toFixed(1)}%` : f.buy ? (f.kind === "open" ? "매수" : "환매") : "숏";
      return { time: bars[f.i].t, position: f.buy ? "belowBar" : "aboveBar", color: f.buy ? UP : DOWN, shape: f.buy ? "arrowUp" : "arrowDown", text };
    });
    marks.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    C.marks.setMarkers(marks.slice(-800));
    C.pc.timeScale().fitContent();
    const bh = bars.map((b) => (opt.capital * b.c) / bars[0].o);
    renderEquity(bars.map((b) => b.t), r.equity, bh, bench, opt.capital, st.drawdown);
    renderMonthly(st.monthly);
    renderGoal(st); renderDaily(st);
    renderTrades(r.trades, r.open, (_, i) => label(i), () => sym);
  }

  function renderBasket(run) {
    const st = run.stats;
    const extra = [
      `<div class="stat"><div class="k">플러스 종목 비율</div><div class="v">${st.posShare.toFixed(0)}%</div></div>`,
      `<div class="stat"><div class="k">보유보다 나은 종목</div><div class="v">${st.beatShare.toFixed(0)}%</div></div>`,
      `<div class="stat"><div class="k">종목별 수익 중앙값</div><div class="v ${cls(st.median)}">${fmtPct(st.median)}</div></div>`,
    ];
    if (run.bench) extra.push(`<div class="stat"><div class="k">코스피200 (같은 기간)</div><div class="v ${cls(run.bench[run.bench.length - 1] - 1)}">${fmtPct((run.bench[run.bench.length - 1] - 1) * 100)}</div></div>`);
    $("#bt-metrics").innerHTML = metricCards(st, extra);
    warnings(st, "basket");
    if (run.fails.length) { const w = $("#bt-warn"); w.hidden = false; w.innerHTML += (w.innerHTML ? "<br/>" : "") + `불러오지 못한 종목: ${esc(run.fails.slice(0, 10).join(", "))}${run.fails.length > 10 ? ` 외 ${run.fails.length - 10}개` : ""}`; }
    $("#bt-basket-box").hidden = false; $("#bt-price-box").hidden = true;
    chartTime(run.intraday);
    S.basketRows = run.list.map((x) => {
      const s = x.res.stats;
      return { sym: x.sym, name: x.title, ret: s.totalRet, bh: s.buyHold, ex: s.totalRet - s.buyHold, mdd: s.mdd, sharpe: s.sharpe, trades: s.trades, win: s.trades ? s.winRate : NaN, pf: s.profitFactor };
    });
    renderBasketTable("ret", -1);
    renderEquity(run.port.t, run.port.total, run.bh.total, run.bench, run.opt.capital, st.drawdown);
    renderMonthly(st.monthly);
    renderGoal(st); renderDaily(st);
    renderTrades(run.trades, null, (t, i) => t.label(i), (t) => t.sym);
  }
  function renderBasketTable(key, dir) {
    S.basketSort = { key, dir };
    const rows = [...S.basketRows].sort((a, b) => (key === "name" ? a.name.localeCompare(b.name) : (isFinite(a[key]) ? a[key] : -1e9) - (isFinite(b[key]) ? b[key] : -1e9)) * dir);
    const f2 = (v) => (isFinite(v) ? v.toFixed(2) : v === Infinity ? "∞" : "—");
    $("#bt-basket-table tbody").innerHTML = rows.map((r) => `<tr data-sym="${esc(r.sym)}">
      <td><b>${esc(r.name)}</b><div class="sub">${esc(r.sym)}</div></td>
      <td class="r ${cls(r.ret)}">${fmtPct(r.ret)}</td><td class="r ${cls(r.bh)}">${fmtPct(r.bh)}</td><td class="r ${cls(r.ex)}">${fmtPct(r.ex)}</td>
      <td class="r">${fmtPct(r.mdd)}</td><td class="r">${f2(r.sharpe)}</td><td class="r">${r.trades}</td>
      <td class="r">${isFinite(r.win) ? r.win.toFixed(0) + "%" : "—"}</td><td class="r">${f2(r.pf)}</td></tr>`).join("");
    $$("#bt-basket-table th").forEach((th) => th.classList.toggle("sorted", th.dataset.k === key));
  }

  // ================= 설정 자동 탐색 =================
  const RISK_RANGES = [
    { key: "stopLoss", label: "손절 %", from: 0, to: 10, step: 2, risk: true },
    { key: "takeProfit", label: "익절 %", from: 0, to: 20, step: 5, risk: true },
    { key: "trailing", label: "트레일링 %", from: 0, to: 10, step: 2, risk: true },
    { key: "maxHold", label: "최대 보유 봉", from: 0, to: 40, step: 10, risk: true },
  ];
  function rangeDefs() {
    const St = BT.STRATEGIES[$("#bt-strategy").value];
    const p = readParams(), o = readOpt();
    const sp = St.params.filter((d) => d.type !== "select").map((d) => {
      const cur = +p[d.key], step = d.step || Math.max(1, Math.round(cur / 5));
      return { key: d.key, label: d.label, from: Math.max(d.min ?? -Infinity, +(cur - 2 * step).toFixed(4)), to: Math.min(d.max ?? Infinity, +(cur + 2 * step).toFixed(4)), step, cur };
    });
    return [...sp, ...RISK_RANGES.map((r) => ({ ...r, cur: o[r.key] }))];
  }
  function renderRanges() {
    const prev = new Map($$("#opt-ranges tbody tr").map((tr) => [tr.dataset.key, readRangeRow(tr)]));
    $("#opt-ranges tbody").innerHTML = rangeDefs().map((d) => {
      const pv = prev.get(d.key);
      const r = pv || { on: false, from: d.from, to: d.to, step: d.step };
      return `<tr data-key="${d.key}" data-risk="${d.risk ? 1 : 0}">
        <td><input type="checkbox" ${r.on ? "checked" : ""}></td><td>${d.label} <span class="muted small">지금 ${d.cur}</span></td>
        <td class="r"><input type="number" data-r="from" value="${r.from}" step="any"></td>
        <td class="r"><input type="number" data-r="to" value="${r.to}" step="any"></td>
        <td class="r"><input type="number" data-r="step" value="${r.step}" step="any" min="0"></td>
        <td class="r cnt"></td></tr>`;
    }).join("");
    countCombos();
  }
  function readRangeRow(tr) {
    const v = (k) => +$(`[data-r="${k}"]`, tr).value;
    return { key: tr.dataset.key, risk: tr.dataset.risk === "1", on: $("input[type=checkbox]", tr).checked, from: v("from"), to: v("to"), step: v("step") };
  }
  function rangeValues(r) {
    if (!r.on) return null;
    if (!(r.step > 0) || r.to < r.from) return [r.from];
    const out = [];
    for (let v = r.from; v <= r.to + 1e-9 && out.length < 200; v += r.step) out.push(+v.toFixed(6));
    return out;
  }
  function countCombos() {
    let total = 1, on = 0;
    $$("#opt-ranges tbody tr").forEach((tr) => {
      const r = readRangeRow(tr), vals = rangeValues(r);
      $(".cnt", tr).textContent = vals ? vals.length : "";
      if (vals) { total *= vals.length; on++; }
    });
    const mult = S.mode === "basket" ? " × 종목 수" : "";
    $("#opt-count").textContent = on ? `조합 ${total.toLocaleString()}개${mult}` + (total > 3000 ? " · 너무 많아요 (3,000개까지)" : "") : "탐색할 항목을 체크하세요";
    return { total, on };
  }

  // 구간 성과 (equity 배열 기준)
  function segStats(eq, ms, from, to, startVal, trades) {
    const n = to - from;
    if (n < 2) return null;
    let peak = startVal, mdd = 0, prev = startVal, s = 0, s2 = 0;
    const rets = [];
    for (let i = from; i < to; i++) {
      const r = eq[i] / prev - 1; prev = eq[i]; rets.push(r); s += r;
      if (eq[i] > peak) peak = eq[i]; mdd = Math.min(mdd, eq[i] / peak - 1);
    }
    const mean = s / n;
    rets.forEach((r) => (s2 += (r - mean) ** 2));
    const sd = Math.sqrt(s2 / n);
    const years = Math.max((ms[to - 1] - ms[from]) / (365.25 * 86400000), 1 / 365);
    const ret = eq[to - 1] / startVal - 1;
    const ann = years >= 0.25 && eq[to - 1] > 0 ? Math.pow(eq[to - 1] / startVal, 1 / years) - 1 : ret;
    const tr = trades || [];
    const W = tr.filter((t) => t.pnl > 0), Lo = tr.filter((t) => t.pnl <= 0);
    const gw = W.reduce((a, t) => a + t.pnl, 0), gl = -Lo.reduce((a, t) => a + t.pnl, 0);
    const aw = W.length ? W.reduce((a, t) => a + t.ret, 0) / W.length : 0, al = Lo.length ? Lo.reduce((a, t) => a + t.ret, 0) / Lo.length : 0;
    return {
      payoff: al < 0 ? aw / -al : aw > 0 ? 99 : 0, exp: tr.length ? tr.reduce((a, t) => a + t.ret, 0) / tr.length : 0,
      ret: ret * 100, mdd: mdd * 100, sharpe: sd > 0 ? (mean / sd) * Math.sqrt(n / years) : 0,
      calmar: mdd < 0 ? ann / -mdd : ann > 0 ? 99 : 0, pf: gl > 0 ? gw / gl : gw > 0 ? 99 : 0,
      trades: tr.length, win: tr.length ? (tr.filter((t) => t.pnl > 0).length / tr.length) * 100 : 0,
    };
  }
  function spearman(a, b) {
    const rank = (arr) => {
      const idx = arr.map((v, i) => [v, i]).sort((x, y) => x[0] - y[0]);
      const r = new Array(arr.length);
      for (let i = 0; i < idx.length;) {
        let j = i; while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++;
        for (let k = i; k <= j; k++) r[idx[k][1]] = (i + j) / 2;
        i = j + 1;
      }
      return r;
    };
    if (a.length < 3) return NaN;
    const ra = rank(a), rb = rank(b), n = a.length, ma = (n - 1) / 2;
    let num = 0, da = 0, db = 0;
    for (let i = 0; i < n; i++) { num += (ra[i] - ma) * (rb[i] - ma); da += (ra[i] - ma) ** 2; db += (rb[i] - ma) ** 2; }
    return da && db ? num / Math.sqrt(da * db) : NaN;
  }

  async function optimize(spec = {}) {
    if (S.opt.running) return;
    if (spec.ranges) {
      // 대화 도우미가 범위를 정해준 경우
      $$("#opt-ranges tbody tr").forEach((tr) => {
        const r = spec.ranges.find((x) => x.key === tr.dataset.key);
        $("input[type=checkbox]", tr).checked = !!r;
        if (r) { $('[data-r="from"]', tr).value = r.from; $('[data-r="to"]', tr).value = r.to; $('[data-r="step"]', tr).value = r.step; }
      });
      if (spec.train_pct) $("#opt-train").value = spec.train_pct;
      if (spec.objective) $("#opt-objective").value = spec.objective;
      if (spec.min_trades != null) $("#opt-mintrades").value = spec.min_trades;
      if (spec.goal_filter != null) $("#opt-goal").checked = !!spec.goal_filter;
    }
    const ranges = $$("#opt-ranges tbody tr").map(readRangeRow).filter((r) => r.on);
    if (!ranges.length) throw new Error("탐색할 항목을 하나 이상 체크하세요.");
    const { total } = countCombos();
    if (total > 3000) throw new Error("조합이 3,000개를 넘어요. 범위를 줄이거나 간격을 넓혀주세요.");
    const trainPct = Math.min(90, Math.max(30, +$("#opt-train").value || 70)) / 100;
    const objective = $("#opt-objective").value, minTrades = +$("#opt-mintrades").value || 0, useGoal = $("#opt-goal").checked;
    const sid = $("#bt-strategy").value, baseP = readParams(), baseO = readOpt();

    S.opt.running = true; S.opt.stop = false;
    $("#opt-run").disabled = true; $("#opt-stop").hidden = false; $("#opt-progress").hidden = false;
    const bar = $("#opt-progress i"); bar.style.width = "0%";
    try {
      // 데이터 준비
      let sets;
      if (S.mode === "basket") sets = (await loadBasket((d, n) => ($("#opt-count").textContent = `종목 불러오는 중 ${d}/${n}`))).list;
      else if (S.csv) sets = [{ sym: null, bars: dateFilter(S.csv.bars), title: S.csv.name, intraday: S.csv.intraday }];
      else sets = [await loadSeries(curSym())];
      sets = sets.filter((x) => x.bars.length >= 60);
      if (!sets.length) throw new Error("데이터가 너무 적어요 (60봉 이상 필요).");
      const allMs = sets.flatMap((x) => [x.bars[0].ms, x.bars[x.bars.length - 1].ms]);
      const t0 = Math.min(...allMs), t1 = Math.max(...allMs), splitMs = t0 + (t1 - t0) * trainPct;
      sets.forEach((x) => { x.k = x.bars.findIndex((b) => b.ms >= splitMs); if (x.k < 0) x.k = x.bars.length; });
      const capEach = baseO.capital / sets.length;

      const evalOne = (vals) => {
        const p = { ...baseP }, o = { ...baseO, capital: capEach };
        ranges.forEach((r, j) => { if (r.risk) o[r.key] = vals[j]; else p[r.key] = vals[j]; });
        if (sets.length === 1) {
          const x = sets[0], res = BT.run(x.bars, sid, p, engineOpt(x.sym, x.bars, x.intraday, o)), ms = x.bars.map((b) => b.ms);
          const trTrain = res.trades.filter((t) => t.exitIdx < x.k), trTest = res.trades.filter((t) => t.exitIdx >= x.k);
          return { train: segStats(res.equity, ms, 0, x.k, capEach, trTrain), test: segStats(res.equity, ms, x.k, x.bars.length, res.equity[x.k - 1] || capEach, trTest) };
        }
        sets.forEach((x) => (x.res = BT.run(x.bars, sid, p, engineOpt(x.sym, x.bars, x.intraday, o))));
        const port = combine(sets, (x, i) => x.res.equity[i], capEach);
        const k = port.times.findIndex((m) => m >= splitMs);
        const trTrain = sets.flatMap((x) => x.res.trades.filter((t) => t.exitIdx < x.k)), trTest = sets.flatMap((x) => x.res.trades.filter((t) => t.exitIdx >= x.k));
        return { train: segStats(port.total, port.times, 0, k, baseO.capital, trTrain), test: segStats(port.total, port.times, k, port.times.length, port.total[k - 1] || baseO.capital, trTest) };
      };

      const valsList = ranges.map(rangeValues);
      const combos = valsList.reduce((acc, vs) => acc.flatMap((a) => vs.map((v) => [...a, v])), [[]]);
      const rows = [];
      const current = evalOne(ranges.map((r) => (r.risk ? baseO[r.key] : baseP[r.key])));
      let i = 0, lastPaint = 0;
      while (i < combos.length && !S.opt.stop) {
        const tStart = performance.now();
        while (i < combos.length && performance.now() - tStart < 40) { const r = evalOne(combos[i]); rows.push({ vals: combos[i], ...r }); i++; }
        if (performance.now() - lastPaint > 120) { bar.style.width = `${(i / combos.length) * 100}%`; $("#opt-count").textContent = `${i.toLocaleString()} / ${combos.length.toLocaleString()}`; lastPaint = performance.now(); }
        await new Promise((r) => setTimeout(r, 0));
      }
      bar.style.width = "100%";
      S.opt.result = { ranges, rows, current, objective, minTrades, useGoal, trainPct, splitMs, stopped: S.opt.stop, mode: S.mode };
      renderOpt();
      return S.opt.result;
    } finally {
      S.opt.running = false; $("#opt-run").disabled = false; $("#opt-stop").hidden = true;
      setTimeout(() => ($("#opt-progress").hidden = true), 600);
      countCombos();
    }
  }

  const objLabel = { sharpe: "샤프", calmar: "수익÷MDD", ret: "총수익", pf: "PF", exp: "기대값" };
  const fmtObj = (k, v) => (v == null || !isFinite(v) ? "—" : k === "ret" || k === "exp" ? fmtPct(v) : v.toFixed(2));
  function renderOpt() {
    const R = S.opt.result;
    if (!R) return;
    R.useGoal = $("#opt-goal").checked;
    const ok = R.rows.filter((r) => r.train && r.test && r.train.trades >= R.minTrades && (!R.useGoal || goalPassTrain(r.train)));
    ok.sort((a, b) => b.train[R.objective] - a.train[R.objective]);
    const best = ok[0];
    const goalTest = ok.filter((r) => goalPassTrain(r.test)).length;
    const rho = spearman(ok.map((r) => r.train[R.objective]), ok.map((r) => r.test[R.objective]));
    const posTest = ok.length ? ok.filter((r) => r.test.ret > 0).length / ok.length * 100 : 0;
    const verdict = !ok.length ? "조건에 맞는 조합이 없어요. 최소 거래 수를 낮추거나 기간을 늘려보세요."
      : !isFinite(rho) ? "조합이 너무 적어 판단하기 어려워요."
      : rho < 0.1 ? "학습 성적이 검증 성적으로 이어지지 않아요. 상위 설정은 과거에만 맞춘 것일 가능성이 커요."
      : rho < 0.4 ? "학습과 검증이 약하게만 이어져요. 1등 설정보다 비슷한 설정들이 고르게 괜찮은지 보세요."
      : "학습 성적이 좋은 설정이 검증에서도 대체로 좋았어요. 비교적 믿을 만한 편이에요.";
    const card = (k, v, c = "") => `<div class="stat"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`;
    $("#opt-summary").innerHTML =
      card("탐색한 조합", `${R.rows.length.toLocaleString()}${R.stopped ? " (중간에 멈춤)" : ""}`) +
      card("조건 맞는 조합", ok.length.toLocaleString()) +
      card(`학습 1위 → 검증 ${objLabel[R.objective]}`, best ? `${fmtObj(R.objective, best.train[R.objective])} → ${fmtObj(R.objective, best.test[R.objective])}` : "—") +
      card("학습 1위 검증 수익", best ? fmtPct(best.test.ret) : "—", best ? cls(best.test.ret) : "") +
      card("학습·검증 순위 상관", isFinite(rho) ? rho.toFixed(2) : "—", rho >= 0.4 ? "up" : rho < 0.1 ? "down" : "") +
      card("검증에서 플러스인 조합", posTest.toFixed(0) + "%") +
      card("검증에서도 목표 기준 통과", ok.length ? `${goalTest}개 (${(goalTest / ok.length * 100).toFixed(0)}%)` : "—") +
      card("지금 설정 학습 → 검증 수익", R.current.train && R.current.test ? `${fmtPct(R.current.train.ret, 1)} → ${fmtPct(R.current.test.ret, 1)}` : "—") +
      `<div class="stat wide-note"><div class="k">한 줄 판단</div><div class="v small-v">${esc(verdict)}</div></div>`;
    $("#opt-out").hidden = false;

    // 히트맵 (두 항목)
    $("#opt-heat-box").hidden = R.ranges.length !== 2;
    if (R.ranges.length === 2) renderHeat(R);

    // 상위 표
    const names = R.ranges.map((r) => rangeDefs().find((d) => d.key === r.key)?.label || r.key);
    const head = `<thead><tr><th>#</th>${names.map((n) => `<th class="r">${esc(n)}</th>`).join("")}
      <th class="r">학습 ${objLabel[R.objective]}</th><th class="r">학습 수익</th><th class="r">학습 승률</th><th class="r">학습 손익비</th><th class="r">학습 MDD</th><th class="r">학습 거래</th>
      <th class="r">검증 ${objLabel[R.objective]}</th><th class="r">검증 수익</th><th class="r">검증 승률</th><th class="r">검증 손익비</th><th class="r">검증 MDD</th><th class="r">검증 거래</th></tr></thead>`;
    const pf2 = (v) => (v >= 99 ? "∞" : v.toFixed(2));
    const row = (r, i, extraCls = "") => `<tr data-i="${i}" class="${extraCls}"><td>${i < 0 ? "지금" : i + 1}</td>${r.vals.map((v) => `<td class="r">${v}</td>`).join("")}
      <td class="r"><b>${fmtObj(R.objective, r.train[R.objective])}</b></td><td class="r ${cls(r.train.ret)}">${fmtPct(r.train.ret, 1)}</td><td class="r">${r.train.win.toFixed(0)}%</td><td class="r">${pf2(r.train.payoff)}</td><td class="r">${fmtPct(r.train.mdd, 1)}</td><td class="r">${r.train.trades}</td>
      <td class="r"><b>${fmtObj(R.objective, r.test[R.objective])}</b></td><td class="r ${cls(r.test.ret)}">${fmtPct(r.test.ret, 1)}</td><td class="r ${goalPassTrain(r.test) ? "up" : ""}">${r.test.win.toFixed(0)}%</td><td class="r">${pf2(r.test.payoff)}</td><td class="r">${fmtPct(r.test.mdd, 1)}</td><td class="r">${r.test.trades}</td></tr>`;
    const cur = R.current.train && R.current.test ? row({ vals: R.ranges.map((r) => (r.risk ? readOpt()[r.key] : readParams()[r.key])), ...R.current }, -1, "current") : "";
    $("#opt-table").innerHTML = head + `<tbody>${cur}${ok.slice(0, 20).map((r, i) => row(r, i)).join("") || `<tr class="empty-row"><td colspan="${13 + names.length}">조건에 맞는 조합이 없어요.${R.useGoal ? " 목표 기준 필터를 끄거나 기준을 낮춰보세요." : ""}</td></tr>`}</tbody>`;
    S.opt.top = ok.slice(0, 20);
  }
  function renderHeat(R) {
    const [r1, r2] = R.ranges, v1 = rangeValues(r1), v2 = rangeValues(r2), which = S.opt.heat, k = R.objective;
    const map = new Map(R.rows.map((r) => [r.vals.join("|"), r]));
    const vals = R.rows.map((r) => r[which] && r[which][k]).filter((v) => isFinite(v));
    const mx = Math.max(...vals.map(Math.abs), 1e-9);
    const names = R.ranges.map((r) => rangeDefs().find((d) => d.key === r.key)?.label || r.key);
    let html = `<thead><tr><th>${esc(names[0])} ↓ / ${esc(names[1])} →</th>${v2.map((v) => `<th class="r">${v}</th>`).join("")}</tr></thead><tbody>`;
    v1.forEach((a) => {
      html += `<tr><th>${a}</th>` + v2.map((b) => {
        const r = map.get(`${a}|${b}`), v = r && r[which] ? r[which][k] : NaN;
        const ok = r && r.train && r.train.trades >= R.minTrades;
        if (!isFinite(v)) return `<td></td>`;
        const al = Math.min(Math.abs(v) / mx, 1) * 0.6 + 0.08;
        const bg = v >= 0 ? `rgba(240,82,92,${al})` : `rgba(61,139,253,${al})`;
        return `<td class="r ${ok ? "" : "dim"}" style="background:${bg}" title="학습 ${fmtObj(k, r.train[k])} / 검증 ${fmtObj(k, r.test[k])}">${fmtObj(k, v)}</td>`;
      }).join("") + "</tr>";
    });
    $("#opt-heat").innerHTML = html + "</tbody>";
  }
  function applyOptRow(r) {
    const R = S.opt.result, o = {}, p = {};
    R.ranges.forEach((rg, j) => { if (rg.risk) o[rg.key] = r.vals[j]; else p[rg.key] = r.vals[j]; });
    writeOpt(o);
    Object.entries(p).forEach(([k, v]) => { const el = $(`[data-p="${k}"]`); if (el) el.value = v; });
    saveForm();
  }

  // ================= 저장한 결과 =================
  const loadRuns = () => store.get(RUNS_KEY, []);
  function saveRun() {
    const L = S.last;
    if (!L) { toast("먼저 백테스트를 실행해주세요."); return; }
    const st = L.kind === "basket" ? L.stats : L.res.stats;
    const eq = L.kind === "basket" ? L.port.total : L.res.equity;
    const ms = L.kind === "basket" ? L.port.times : L.bars.map((b) => b.ms);
    const step = Math.max(1, Math.ceil(eq.length / 400));
    const curve = [];
    for (let i = 0; i < eq.length; i += step) curve.push([Math.floor(ms[i] / 1000), +(eq[i] / eq[0] * 100).toFixed(3)]);
    curve.push([Math.floor(ms[eq.length - 1] / 1000), +(eq[eq.length - 1] / eq[0] * 100).toFixed(3)]);
    const defName = `${L.title} · ${BT.STRATEGIES[L.sid].name}`;
    let name = window.prompt("저장할 이름", defName);
    if (name === null) return;
    name = name.trim() || defName;
    const runs = loadRuns();
    runs.unshift({
      id: Date.now(), name, at: new Date().toISOString().slice(0, 16).replace("T", " "), title: L.title, kind: L.kind,
      strategy: BT.STRATEGIES[L.sid].name, interval: Data.IV[L.settings.interval]?.label || "",
      period: L.kind === "basket" ? `${L.port.days[0]} ~ ${L.port.days[L.port.days.length - 1]}` : `${L.label(0)} ~ ${L.label(L.bars.length - 1)}`,
      stats: { totalRet: st.totalRet, buyHold: st.buyHold, cagr: st.cagr, mdd: st.mdd, sharpe: st.sharpe, sortino: st.sortino, trades: st.trades, winRate: st.winRate, profitFactor: isFinite(st.profitFactor) ? st.profitFactor : 999 },
      settings: L.settings, curve,
    });
    store.set(RUNS_KEY, runs.slice(0, 40));
    renderSaved(); toast("저장했어요. ‘저장한 결과’에서 비교할 수 있어요.");
  }
  function renderSaved() {
    const runs = loadRuns();
    $("#saved-count").textContent = runs.length ? runs.length : "";
    const f2 = (v) => (v == null || !isFinite(v) ? "—" : v >= 999 ? "∞" : v.toFixed(2));
    $("#saved-table").innerHTML = `<thead><tr><th></th><th>이름</th><th>봉</th><th>기간</th><th class="r">수익률</th><th class="r">보유만</th><th class="r">MDD</th><th class="r">샤프</th><th class="r">거래</th><th class="r">승률</th><th class="r">손익비</th><th></th></tr></thead><tbody>` +
      (runs.map((r) => `<tr data-id="${r.id}"><td><input type="checkbox" data-cmp ${S.cmp && S.cmp.has(r.id) ? "checked" : ""}></td>
        <td><b>${esc(r.name)}</b><div class="sub">${esc(r.at)}</div></td><td>${esc(r.interval)}</td><td class="sub">${esc(r.period)}</td>
        <td class="r ${cls(r.stats.totalRet)}">${fmtPct(r.stats.totalRet)}</td><td class="r">${fmtPct(r.stats.buyHold)}</td><td class="r">${fmtPct(r.stats.mdd)}</td>
        <td class="r">${f2(r.stats.sharpe)}</td><td class="r">${r.stats.trades}</td><td class="r">${r.stats.trades ? r.stats.winRate.toFixed(0) + "%" : "—"}</td><td class="r">${f2(r.stats.profitFactor)}</td>
        <td class="nowrap"><button class="btn small" data-load>불러오기</button> <button class="del" data-del title="삭제">✕</button></td></tr>`).join("")
        || `<tr class="empty-row"><td colspan="12">아직 저장한 결과가 없어요. 결과 화면의 <b>결과 저장</b>을 눌러보세요.</td></tr>`) + "</tbody>";
    renderCompare();
  }
  function renderCompare() {
    const runs = loadRuns().filter((r) => S.cmp && S.cmp.has(r.id));
    $("#saved-chart-box").hidden = !runs.length;
    if (!runs.length) return;
    if (!S.cmpChart) {
      S.cmpChart = LC.createChart($("#saved-chart"), LC_OPTS());
      S.cmpChart.applyOptions({ timeScale: { timeVisible: false } });
      S.cmpSeries = [];
    }
    S.cmpSeries.forEach((s) => S.cmpChart.removeSeries(s));
    const colors = [GOLD, "#7aa2ff", MINT, "#c792ea", UP, "#f5f5f7"];
    S.cmpSeries = runs.map((r, i) => {
      const s = S.cmpChart.addSeries(LC.LineSeries, { color: colors[i % colors.length], lineWidth: 2, priceLineVisible: false });
      const pts = r.curve.filter((p, j, a) => j === 0 || p[0] > a[j - 1][0]).map(([t, v]) => ({ time: t + Data.KST, value: v }));
      s.setData(pts); return s;
    });
    $("#saved-legend").innerHTML = runs.map((r, i) => `<span><i style="background:${colors[i % colors.length]}"></i>${esc(r.name)}</span>`).join("");
    S.cmpChart.timeScale().fitContent();
  }

  // ================= 화면 전환 =================
  function showSub(name) {
    $$("#bt-subtabs button").forEach((b) => b.classList.toggle("on", b.dataset.sub === name));
    $$("[data-subpanel]").forEach((p) => (p.hidden = p.dataset.subpanel !== name));
    if (name === "opt") { renderRanges(); }
    if (name === "saved") renderSaved();
    // 숨겨져 있던 차트 크기 다시 맞추기
    requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
  }

  // ================= 대화로 설정하기 =================
  const CHAT_KEY = "tradingdesk.chat";
  const chat = { history: [], busy: false };
  const chatCfg = () => store.get(CHAT_KEY, { model: "claude-sonnet-5-5", pass: "" });

  function summarize(L) {
    if (!L) return null;
    const s = L.kind === "basket" ? L.stats : L.res.stats, r2 = (v) => (v == null || !isFinite(v) ? null : Math.round(v * 100) / 100);
    const out = {
      target: L.title, kind: L.kind, strategy: BT.STRATEGIES[L.sid].name, params: L.p,
      total_return_pct: r2(s.totalRet), buy_hold_pct: r2(s.buyHold), cagr_pct: r2(s.cagr), mdd_pct: r2(s.mdd),
      sharpe: r2(s.sharpe), sortino: r2(s.sortino), calmar: r2(s.calmar), trades: s.trades, win_rate_pct: r2(s.winRate),
      avg_win_pct: r2(s.avgWin), avg_loss_pct: r2(s.avgLoss), profit_factor: r2(s.profitFactor), expectancy_pct: r2(s.expectancy),
      max_losing_streak: s.maxLoseStreak, avg_hold_bars: r2(s.avgHold), exposure_pct: r2(s.exposure),
      payoff_ratio: r2(s.payoff), positive_days_pct: r2(s.posDays), worst_day_pct: r2(s.worstDay), best_day_pct: r2(s.bestDay),
      goal: goalChecks(s).map((c) => `${c.pass ? "통과" : "미달"}: ${c.label} ${c.value} (기준 ${c.need})`),
    };
    if (L.bench) out.kospi200_pct = r2((L.bench[L.bench.length - 1] - 1) * 100);
    if (L.kind === "basket") {
      out.share_positive_pct = r2(s.posShare); out.share_beat_hold_pct = r2(s.beatShare); out.median_symbol_return_pct = r2(s.median);
      out.per_symbol = S.basketRows.slice().sort((a, b) => b.ret - a.ret).map((r) => ({ name: r.name, ret: r2(r.ret), hold: r2(r.bh), mdd: r2(r.mdd), trades: r.trades }));
    } else out.period = `${L.label(0)} ~ ${L.label(L.bars.length - 1)}`;
    return out;
  }
  function optSummary(R) {
    if (!R) return null;
    const ok = R.rows.filter((r) => r.train && r.test && r.train.trades >= R.minTrades && (!R.useGoal || goalPassTrain(r.train))).sort((a, b) => b.train[R.objective] - a.train[R.objective]);
    const rho = spearman(ok.map((r) => r.train[R.objective]), ok.map((r) => r.test[R.objective]));
    const pick = (r) => ({ values: Object.fromEntries(R.ranges.map((g, j) => [g.key, r.vals[j]])), train: r.train, test: r.test });
    return { objective: R.objective, goal_filter: !!R.useGoal, train_pct: R.trainPct * 100, combos: R.rows.length, valid: ok.length,
      test_goal_pass: ok.filter((r) => goalPassTrain(r.test)).length,
      rank_corr_train_test: isFinite(rho) ? Math.round(rho * 100) / 100 : null,
      share_test_positive_pct: ok.length ? Math.round(ok.filter((r) => r.test.ret > 0).length / ok.length * 100) : 0,
      current: R.current, top5: ok.slice(0, 5).map(pick) };
  }

  /** 대화 도우미·간단 모드가 쓰는 설정 적용 */
  async function applyChat(a) {
    const done = [];
    const set = {};
    if (a.mode) { set.mode = a.mode; done.push(a.mode === "basket" ? "여러 종목" : "한 종목"); }
    if (a.basket) { set.mode = "basket"; set.basket = a.basket; done.push(`묶음 ${a.basket}`); }
    if (a.symbol_query) {
      const hit = (await Data.search(String(a.symbol_query), 1))[0];
      if (!hit) throw new Error(`'${a.symbol_query}' 종목을 찾지 못했어요.`);
      set.symbol = hit.symbol; if (!a.mode && !a.basket) set.mode = "single"; done.push(`종목 ${hit.name}`);
    }
    if (a.interval && Data.IV[a.interval]) {
      if ($("#bt-interval").value !== a.interval) { $("#bt-interval").value = a.interval; $("#bt-interval").dispatchEvent(new Event("change")); }
      done.push(`${Data.IV[a.interval].label}봉`);
    }
    if (a.start !== undefined) { set.start = a.start; done.push(`시작 ${a.start || "처음부터"}`); }
    if (a.end !== undefined) { set.end = a.end; done.push(`종료 ${a.end || "끝까지"}`); }
    if (a.strategy && BT.STRATEGIES[a.strategy]) { set.strategy = a.strategy; done.push(`전략 ${BT.STRATEGIES[a.strategy].name}`); }
    writeSettings(set);
    if (a.params && typeof a.params === "object") {
      const St = BT.STRATEGIES[$("#bt-strategy").value];
      for (const [k, v] of Object.entries(a.params)) {
        const d = St.params.find((x) => x.key === k), el = $(`[data-p="${k}"]`);
        if (!d || !el) continue;
        el.value = d.type === "select" ? (d.options.includes(v) ? v : d.def) : Math.min(d.max ?? Infinity, Math.max(d.min ?? -Infinity, +v));
        done.push(`${d.label} ${el.value}`);
      }
    }
    if (a.custom_rules && typeof a.custom_rules === "object") {
      writeSettings({ strategy: "custom" });
      S.rules = { entry: a.custom_rules.entry || { logic: "AND", rules: [] }, exit: a.custom_rules.exit || { logic: "AND", rules: [] } };
      renderRules(); done.push("조건 조합 설정");
    }
    const map = { direction: "direction", sizing: "sizing", size_pct: "sizePct", risk_pct: "riskPct", atr_mult: "atrMult", pyramid_n: "pyrN", pyramid_mode: "pyrMode", pyramid_pct: "pyrPct",
      tp1_pct: "tp1Pct", tp1_frac: "tp1Frac", stop_loss: "stopLoss", take_profit: "takeProfit", trailing: "trailing", max_hold: "maxHold", day_close: "dayClose",
      capital: "capital", buy_fee: "buyFee", sell_fee: "sellFee", slippage: "slip", borrow_fee: "borrowFee", tick_rules: "tick", limit_rules: "limit", volume_cap: "volCap" };
    const o = {};
    Object.entries(map).forEach(([k, key]) => { if (a[k] !== undefined && a[k] !== null) { o[key] = a[k]; done.push(`${key} ${a[k]}`); } });
    if (Object.keys(o).length) writeOpt(o);
    saveForm();
    return done;
  }

  function systemPrompt() {
    const strategies = Object.entries(BT.STRATEGIES).filter(([k]) => k !== "custom").map(([k, s]) =>
      `- ${k} (${s.name}): ${s.desc}\n  파라미터: ${s.params.map((p) => `${p.key}=${p.label}${p.type === "select" ? `(${p.options.join("/")})` : `(${p.min}~${p.max}, 기본 ${p.def})`}`).join(", ")}`).join("\n");
    const inds = Object.entries(BT.IND).map(([k, d]) => `${k}(${d.label}${d.args.length ? ", 인자 " + d.args.join("/") : ""})`).join(", ");
    return `너는 개인 주식 연구 사이트 "Trading Desk"의 백테스트 탭 안에 있는 도우미야. 사용자는 한국 개인 투자자이고 한국어로 대화해.

할 수 있는 일
- configure_backtest: 설정(한 종목/여러 종목, 종목, 봉, 기간, 전략, 파라미터, 조건 조합, 방향, 비중, 분할매수, 1차 익절, 손절·익절·트레일링·최대 보유, 장 마감 청산, 비용, 체결 규칙)을 바꾸고 run=true면 실행해서 결과를 받아.
- optimize_settings: 기간을 학습/검증으로 나눠 범위 안의 설정을 전부 돌려보고, 학습 상위 설정과 그 검증 성적, 학습·검증 순위 상관을 받아. 설정을 "찾아줘/최적화해줘"라고 하면 써. 조합은 300개 안팎으로 잡아.
- "해줘/바꿔줘/돌려줘"면 바로 도구를 써. 애매하면 합리적인 기본값을 쓰고 무엇을 골랐는지 말해. 한 턴에 실행은 6번까지.
- 결과 해석: 총수익을 '그냥 보유'와 코스피200과 비교하고, MDD·샤프·거래 수·승률·손익비를 같이 봐. 거래 20회 미만이면 우연일 수 있다고 말해. 여러 종목이면 플러스 종목 비율과 중앙값도 봐.
- 최적화 결과는 학습 1위보다 '검증 성적'과 '순위 상관'을 중심으로 판단해. 상관이 0.1 미만이면 과최적화라고 분명히 말해.
- 수익을 장담하거나 특정 종목 매수·매도를 권하지 마. 연구용 도구라는 전제로 사실과 수치 중심으로 말해.

봉 id: ${Data.INTERVALS.map((x) => `${x.id}(${x.label})`).join(", ")}. 분봉은 최근 60일(1시간봉 약 2년), 1분봉은 최근 5일 정도. 분봉이면 day_close를 보통 켜.
여러 종목 묶음: watch(관심종목), top20/top50(현재 시총 상위, 생존 편향 있음).

전략
${strategies}
- custom (직접 만들기): custom_rules = {entry:{logic:"AND"|"OR", rules:[{a:{ind,n,k}, op, b:{ind,n,k,v}, mult}]}, exit:{...}}
  지표 ind: ${inds}
  op: > < >= <= cross_up cross_down. b에 숫자를 쓸 땐 {ind:"num", v:값}. mult는 b에 곱하는 배수(예: 거래량 > 평균거래량×2).

엔진: 신호는 봉 종가로 판단하고 다음 봉 시가에 체결. direction long/short/both(신호마다 뒤집기). sizing all/fixed(size_pct)/risk(risk_pct, atr_mult). pyramid_n>1이면 비중을 나눠 down(물타기)/up(불타기)/signal 방식으로 추가. tp1_pct에 닿으면 tp1_frac%만 매도. 손절·익절은 평균단가 기준, 같은 봉에 둘 다 닿으면 손절 우선. 기본 비용: 매수 0.015%, 매도 수수료+세금 0.215%, 슬리피지 편도 0.05%.

사용자의 매매 철학: 매일 이기는 것보다 승률 50~60%, 손실은 작게, 이익은 크게(손익비 1.5 이상). 결과에는 '내 목표 기준' 통과 여부(goal)가 있으니 이것을 중심으로 평가하고, 손익비를 키우는 방법(손절 고정, 1차 익절 후 트레일링, 진입 필터)을 제안해.
ETF는 매도 시 증권거래세가 없어 매도 비용을 0.015% 정도로 낮게 잡아도 돼.

이 사용자의 지난 연구: 한국 대형주에서 같은 종목 박스권 롱숏 비중조절은 1시간봉·5분봉·일봉 모두 비용 후 우위가 없었고, 1시간봉 박스 상단 돌파 뒤에는 추세가 이어지는 경향이 있었어.

답변은 짧고 읽기 쉽게. 숫자는 퍼센트 소수 한두 자리로.`;
  }
  const TOOLS = () => [{
    name: "configure_backtest",
    description: "백테스트 설정을 바꾸고 run=true면 실행해서 결과 요약을 돌려준다. 바꾸지 않을 항목은 넣지 않는다.",
    input_schema: {
      type: "object",
      properties: {
        mode: { type: "string", enum: ["single", "basket"] },
        basket: { type: "string", enum: ["watch", "top20", "top50"] },
        symbol_query: { type: "string", description: "종목명, 코드, 티커" },
        interval: { type: "string", enum: Data.INTERVALS.map((x) => x.id) },
        start: { type: "string", description: "YYYY-MM-DD, 빈 문자열이면 처음부터" },
        end: { type: "string", description: "YYYY-MM-DD, 빈 문자열이면 끝까지" },
        strategy: { type: "string", enum: Object.keys(BT.STRATEGIES) },
        params: { type: "object", description: "전략 파라미터 {key: 값}" },
        custom_rules: { type: "object", description: "strategy=custom일 때 조건 조합" },
        direction: { type: "string", enum: ["long", "short", "both"] },
        sizing: { type: "string", enum: ["all", "fixed", "risk"] },
        size_pct: { type: "number" }, risk_pct: { type: "number" }, atr_mult: { type: "number" },
        pyramid_n: { type: "integer" }, pyramid_mode: { type: "string", enum: ["down", "up", "signal"] }, pyramid_pct: { type: "number" },
        tp1_pct: { type: "number" }, tp1_frac: { type: "number" },
        stop_loss: { type: "number" }, take_profit: { type: "number" }, trailing: { type: "number" }, max_hold: { type: "integer" }, day_close: { type: "boolean" },
        capital: { type: "number" }, buy_fee: { type: "number" }, sell_fee: { type: "number" }, slippage: { type: "number" }, borrow_fee: { type: "number" },
        tick_rules: { type: "boolean" }, limit_rules: { type: "boolean" }, volume_cap: { type: "number" },
        run: { type: "boolean" },
      },
    },
  }, {
    name: "optimize_settings",
    description: "현재 설정을 바탕으로 지정한 항목들의 범위를 모두 돌려 학습 구간 상위 설정과 검증 성적을 돌려준다. key는 전략 파라미터 key 또는 stopLoss/takeProfit/trailing/maxHold.",
    input_schema: {
      type: "object",
      properties: {
        ranges: { type: "array", items: { type: "object", properties: { key: { type: "string" }, from: { type: "number" }, to: { type: "number" }, step: { type: "number" } }, required: ["key", "from", "to", "step"] } },
        train_pct: { type: "number" }, objective: { type: "string", enum: ["sharpe", "calmar", "ret", "exp", "pf"] }, min_trades: { type: "integer" },
        goal_filter: { type: "boolean", description: "학습 구간에서 사용자의 목표 기준을 만족한 설정만 남길지" },
      },
      required: ["ranges"],
    },
  }];

  function md(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/^[-•] (.*)$/gm, "<span class=\"li\">$1</span>").replace(/<\/span>\n/g, "</span>").replace(/\n/g, "<br/>");
  }
  function addMsg(role, html, extra = "") {
    const box = $("#chat-log");
    $(".chat-empty", box)?.remove();
    const el = document.createElement("div");
    el.className = `msg ${role} ${extra}`; el.innerHTML = html;
    box.appendChild(el); box.scrollTop = box.scrollHeight;
    return el;
  }
  const typing = () => addMsg("bot", `<span class="dots"><i></i><i></i><i></i></span>`, "typing");

  async function callClaude(messages) {
    const proxy = Data.getProxy();
    if (!proxy) { const e = new Error("no proxy"); e.code = "no_proxy"; throw e; }
    const cfg = chatCfg();
    const r = await fetch(proxy.replace(/\/+$/, "") + "/chat", {
      method: "POST",
      headers: { "content-type": "application/json", ...(cfg.pass ? { "x-td-pass": cfg.pass } : {}) },
      body: JSON.stringify({ model: cfg.model, max_tokens: 2000, system: systemPrompt(), tools: TOOLS(), messages }),
    });
    let j = null; try { j = await r.json(); } catch (_) {}
    if (!r.ok) { const e = new Error((j && j.error && j.error.message) || `AI 서버 오류 (${r.status})`); e.code = (j && j.error && j.error.type) || r.status; throw e; }
    return j;
  }
  const brief = (st) => `수익 <b class="${cls(st.totalRet)}">${fmtPct(st.totalRet)}</b> (보유 ${fmtPct(st.buyHold)}), MDD ${fmtPct(st.mdd)}, 거래 ${st.trades}회`;

  async function runTool(c) {
    if (c.name === "optimize_settings") {
      showSub("opt");
      const R = await optimize(c.input || {});
      const sm = optSummary(R);
      addMsg("bot", `<span class="chip-note">설정 탐색: ${sm.combos}개 조합, 학습·검증 순위 상관 ${sm.rank_corr_train_test ?? "—"}</span>`, "note");
      return sm;
    }
    const done = await applyChat(c.input || {});
    const out = { applied: done };
    if (c.input && c.input.run) {
      const L = await run(true);
      out.result = summarize(L);
      const st = L.kind === "basket" ? L.stats : L.res.stats;
      addMsg("bot", `<span class="chip-note">실행: ${esc(L.title)} · ${esc(BT.STRATEGIES[L.sid].name)} → ${brief(st)}</span>`, "note");
    } else if (done.length) addMsg("bot", `<span class="chip-note">설정 변경: ${esc(done.join(", "))}</span>`, "note");
    return out;
  }

  async function sendChat(text) {
    if (chat.busy || !text.trim()) return;
    chat.busy = true; $("#chat-send").disabled = true;
    addMsg("me", md(text));
    const ctx = `[현재 설정]\n${JSON.stringify(readSettings())}\n[최근 결과]\n${JSON.stringify(summarize(S.last))}\n\n`;
    chat.history.push({ role: "user", content: [{ type: "text", text: ctx + text }] });
    let t = typing();
    try {
      for (let round = 0; round < 6; round++) {
        const res = await callClaude(chat.history);
        chat.history.push({ role: "assistant", content: res.content });
        const said = res.content.filter((b) => b.type === "text").map((b) => b.text).join("\n").trim();
        const calls = res.content.filter((b) => b.type === "tool_use");
        t.remove();
        if (said) addMsg("bot", md(said));
        if (res.stop_reason !== "tool_use" || !calls.length) break;
        const results = [];
        for (const c of calls) {
          try { results.push({ type: "tool_result", tool_use_id: c.id, content: JSON.stringify(await runTool(c)) }); }
          catch (err) {
            addMsg("bot", `<span class="chip-note err">${esc(err.message)}</span>`, "note");
            results.push({ type: "tool_result", tool_use_id: c.id, content: err.message, is_error: true });
          }
        }
        chat.history.push({ role: "user", content: results });
        t = typing();
      }
    } catch (err) {
      t.remove();
      while (chat.history.length && chat.history[chat.history.length - 1].role === "user") chat.history.pop();
      const lastA = chat.history[chat.history.length - 1];
      if (lastA && lastA.role === "assistant" && lastA.content.some((b) => b.type === "tool_use")) chat.history.pop();
      if (["no_proxy", "not_configured", 404, 405].includes(err.code)) await localCommand(text, err.code);
      else if (err.code === "bad_password") addMsg("bot", `대화 비밀번호가 맞지 않아요. ⚙ 설정의 <b>대화 비밀번호</b>를 Cloudflare에 넣은 CHAT_PASSWORD와 같게 맞춰주세요.`, "warn");
      else addMsg("bot", `AI 응답을 받지 못했어요: ${esc(err.message)}`, "warn");
    } finally {
      $("#chat-log .typing")?.remove();
      chat.busy = false; $("#chat-send").disabled = false;
      if (chat.history.length > 40) {
        const i = chat.history.findIndex((m, k) => k > chat.history.length - 30 && m.role === "user" && m.content[0].type === "text");
        if (i > 0) chat.history = chat.history.slice(i);
      }
    }
  }

  // AI 연결 전 간단 모드
  async function localCommand(text, code) {
    const a = {}, q = text.replace(/\s+/g, " ");
    const numOf = (re) => { const m = q.match(re); return m ? +m[1] : undefined; };
    for (const [k, v] of [["1분", "1m"], ["15분", "15m"], ["30분", "30m"], ["5분", "5m"], ["1시간", "1h"], ["60분", "1h"], ["시간봉", "1h"], ["일봉", "1d"], ["주봉", "1w"], ["월봉", "1M"]])
      if (q.includes(k)) { a.interval = v; break; }
    for (const [re, v] of [[/이동평균|이평|골든|크로스/i, "ma_cross"], [/rsi/i, "rsi"], [/볼린저|박스/, "bollinger"], [/돌파|급등/, "breakout"]])
      if (re.test(q)) { a.strategy = v; break; }
    a.stop_loss = numOf(/손절\s*(\d+(?:\.\d+)?)/); a.take_profit = numOf(/익절\s*(\d+(?:\.\d+)?)/); a.trailing = numOf(/트레일링\s*(\d+(?:\.\d+)?)/);
    const yrs = numOf(/(\d+)\s*년/), mons = numOf(/(\d+)\s*개월/);
    if (yrs || mons) { const d = new Date(); d.setMonth(d.getMonth() - (yrs ? yrs * 12 : mons)); a.start = d.toISOString().slice(0, 10); a.end = new Date().toISOString().slice(0, 10); }
    if (/당일|장\s*마감|단타/.test(q)) a.day_close = true;
    if (/양방향/.test(q)) a.direction = "both"; else if (/숏/.test(q)) a.direction = "short";
    if (/상위\s*50|50개/.test(q)) a.basket = "top50"; else if (/상위\s*20|20개|시총/.test(q)) a.basket = "top20"; else if (/관심종목\s*(전체|다|모두)/.test(q)) a.basket = "watch";
    if (!a.basket) for (const w of q.split(/[\s,.!?]+/).filter((x) => x.length >= 2 && !/봉|손절|익절|전략|해줘|돌려|테스트|백테스트|년|개월|숏|양방향|상위|시총/.test(x))) {
      const hit = (await Data.search(w.replace(/(으로|로|을|를|이|가|은|는|에서|의)$/, ""), 1))[0];
      if (hit) { a.symbol_query = hit.symbol; break; }
    }
    Object.keys(a).forEach((k) => a[k] === undefined && delete a[k]);
    const why = code === "no_proxy" ? "중계 서버가 연결되지 않아서" : "AI가 아직 연결되지 않아서";
    if (!Object.keys(a).length) {
      addMsg("bot", `${why} 간단 모드로 동작 중이에요. 이렇게 말하면 알아들어요: <b>“삼성전자 5분봉 돌파 손절 2 실행”</b>, <b>“시총 상위 20 일봉 RSI 3년 실행”</b>.<br/>자유롭게 대화하려면 README의 <b>대화 도우미 연결하기</b>를 참고하세요.`, "warn");
      return;
    }
    try {
      const done = await applyChat(a);
      let msg = `${why} 간단 모드로 처리했어요. 바꾼 설정: ${esc(done.join(", "))}`;
      if (/실행|돌려|테스트|해줘|보여/.test(q)) {
        const L = await run(true);
        msg += `<br/>결과: ${brief(L.kind === "basket" ? L.stats : L.res.stats)}`;
      }
      addMsg("bot", msg);
    } catch (err) { addMsg("bot", esc(err.message), "warn"); }
  }

  function initChat() {
    const input = $("#chat-input");
    const send = () => { const v = input.value; input.value = ""; input.style.height = ""; sendChat(v); };
    $("#chat-send").addEventListener("click", send);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
    input.addEventListener("input", () => { input.style.height = ""; input.style.height = Math.min(input.scrollHeight, 140) + "px"; });
    $$("#chat-chips button").forEach((b) => b.addEventListener("click", () => sendChat(b.textContent)));
    $("#chat-clear").addEventListener("click", () => { chat.history = []; $("#chat-log").innerHTML = `<div class="chat-empty">대화를 지웠어요. 새로 물어보세요.</div>`; });
    const cfg = chatCfg();
    $("#chat-model").value = cfg.model; $("#chat-pass").value = cfg.pass || "";
    const saveCfg = () => store.set(CHAT_KEY, { model: $("#chat-model").value, pass: $("#chat-pass").value.trim() });
    $("#chat-model").addEventListener("change", saveCfg); $("#chat-pass").addEventListener("change", saveCfg);
  }

  // ================= 시작 =================
  function init(ctx) {
    S.ctx = ctx;
    S.search = attachSearch($("#bt-symbol").closest(".search"), (sym) => { S.sym = sym; S.csv = null; $("#bt-csv-name").textContent = ""; saveForm(); });
    attachSearch($("#bt-basket-add").closest(".search"), (sym) => {
      if (!S.basketCustom.includes(sym)) S.basketCustom.push(sym);
      store.set(BASKET_KEY, S.basketCustom); renderTags(); $("#bt-basket-add").value = "";
    });
    $("#bt-interval").innerHTML = Data.INTERVALS.map((x) => `<option value="${x.id}" ${x.id === "1d" ? "selected" : ""}>${x.label}봉</option>`).join("");
    $("#bt-strategy").innerHTML = Object.entries(BT.STRATEGIES).map(([k, s]) => `<option value="${k}">${s.name}</option>`).join("");
    const setDates = () => {
      const iv = Data.IV[$("#bt-interval").value], end = new Date(), start = new Date(end);
      if (iv.daily) start.setFullYear(end.getFullYear() - 5);
      $("#bt-start").value = iv.daily ? start.toISOString().slice(0, 10) : "";
      $("#bt-end").value = end.toISOString().slice(0, 10);
      $("#o-dayClose").checked = !iv.daily;
    };
    $("#bt-interval").addEventListener("change", () => { setDates(); saveForm(); });
    $("#bt-strategy").addEventListener("change", () => { renderParams(); saveForm(); });
    $$("#bt-mode button").forEach((b) => b.addEventListener("click", () => { setMode(b.dataset.mode); countCombos(); saveForm(); }));
    $("#bt-basket").addEventListener("change", () => { syncBasket(); saveForm(); });
    $("#bt-controls").addEventListener("change", (e) => { if (e.target.id && e.target.id.startsWith("o-")) { updateWhen(); saveForm(); } if (e.target.dataset.p) saveForm(); });
    $("#bt-controls").addEventListener("input", (e) => { if (e.target.id && e.target.id.startsWith("o-")) updateWhen(); });
    initRules();

    $("#bt-csv").addEventListener("change", async (e) => {
      const f = e.target.files[0]; if (!f) return;
      try {
        S.csv = { name: f.name.replace(/\.[^.]+$/, ""), ...parseCSV(await f.text()) };
        setMode("single");
        $("#bt-csv-name").textContent = `${f.name} · ${S.csv.bars.length.toLocaleString()}개 봉 (${S.csv.intraday ? "분봉" : "일봉"}) · 종목을 다시 고르면 해제돼요`;
        $("#bt-start").value = ""; $("#bt-end").value = ""; $("#o-dayClose").checked = S.csv.intraday;
      } catch (err) { toast(`CSV를 읽지 못했어요: ${esc(err.message)}`, true); }
      e.target.value = "";
    });

    $("#bt-run").addEventListener("click", () => run());
    $$("#bt-subtabs button").forEach((b) => b.addEventListener("click", () => showSub(b.dataset.sub)));
    $("#bt-pine").addEventListener("click", () => {
      const sid = $("#bt-strategy").value;
      $("#pine-code").textContent = BT.pine(sid, readParams(), readOpt(), `TD - ${BT.STRATEGIES[sid].name}`);
      $("#pine-dialog").showModal();
    });
    $("#pine-copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText($("#pine-code").textContent); toast("복사했어요. TradingView Pine 에디터에 붙여넣으세요."); }
      catch (_) { toast("클립보드를 쓸 수 없어요. 코드를 직접 선택해서 복사해주세요.", true); }
    });
    $("#bt-trades-csv").addEventListener("click", () => {
      const L = S.last; if (!L) { toast("먼저 백테스트를 실행해주세요."); return; }
      const lines = ["no,symbol,side,entry_time,entry_price,exit_time,exit_price,bars,return_pct,pnl,reason,adds,partial"];
      const trades = L.kind === "basket" ? L.trades : L.res.trades.map((t) => ({ ...t, sym: L.sym || L.title, label: L.label }));
      trades.forEach((t, i) => lines.push([i + 1, t.sym, t.side > 0 ? "long" : "short", t.label(t.entryIdx), t.entryPx, t.label(t.exitIdx), t.exitPx, t.bars, t.ret.toFixed(3), t.pnl.toFixed(0), t.reason, t.adds, t.partial].join(",")));
      download("trades.csv", "﻿" + lines.join("\n"), "text/csv");
    });
    $("#bt-save").addEventListener("click", saveRun);
    $("#bt-basket-table thead").addEventListener("click", (e) => {
      const th = e.target.closest("th[data-k]"); if (!th || !S.basketRows) return;
      const k = th.dataset.k, dir = S.basketSort && S.basketSort.key === k ? -S.basketSort.dir : (k === "name" ? 1 : -1);
      renderBasketTable(k, dir);
    });
    $("#bt-basket-table tbody").addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-sym]"); if (!tr) return;
      writeSettings({ mode: "single", symbol: tr.dataset.sym }); run();
    });

    // 자동 탐색
    $("#opt-ranges").addEventListener("input", countCombos);
    $("#opt-ranges").addEventListener("change", countCombos);
    $("#opt-run").addEventListener("click", async () => { try { await optimize(); } catch (err) { toast(esc(err.message), true); } });
    $("#opt-stop").addEventListener("click", () => (S.opt.stop = true));
    $("#opt-objective").addEventListener("change", () => { if (S.opt.result) { S.opt.result.objective = $("#opt-objective").value; renderOpt(); } });
    $("#opt-goal").addEventListener("change", () => { if (S.opt.result) renderOpt(); });
    $("#opt-mintrades").addEventListener("change", () => { if (S.opt.result) { S.opt.result.minTrades = +$("#opt-mintrades").value || 0; renderOpt(); } });
    $$("#opt-heat-seg button").forEach((b) => b.addEventListener("click", () => {
      S.opt.heat = b.dataset.h; $$("#opt-heat-seg button").forEach((x) => x.classList.toggle("on", x === b)); renderHeat(S.opt.result);
    }));
    $("#opt-table").addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-i]"); if (!tr || +tr.dataset.i < 0) return;
      applyOptRow(S.opt.top[+tr.dataset.i]); run();
    });

    // 저장한 결과
    S.cmp = new Set();
    $("#saved-table").addEventListener("click", (e) => {
      const tr = e.target.closest("tr[data-id]"); if (!tr) return;
      const id = +tr.dataset.id, runs = loadRuns(), r = runs.find((x) => x.id === id);
      if (e.target.matches("[data-del]")) { store.set(RUNS_KEY, runs.filter((x) => x.id !== id)); S.cmp.delete(id); renderSaved(); }
      else if (e.target.matches("[data-load]")) { writeSettings(r.settings); showSub("result"); toast("설정을 불러왔어요. 백테스트 실행을 누르면 다시 계산해요."); }
    });
    $("#saved-table").addEventListener("change", (e) => {
      if (!e.target.matches("[data-cmp]")) return;
      const id = +e.target.closest("tr").dataset.id;
      if (e.target.checked) S.cmp.add(id); else S.cmp.delete(id);
      renderCompare();
    });

    initCharts(); initChat(); initGoal();
    setDates();
    renderParams();
    const saved = store.get(FORM_KEY, null);
    if (saved) { try { writeSettings({ ...saved, symbol: saved.symbol || undefined }); } catch (_) {} }
    syncBasket(); renderTags(); updateWhen(); renderSaved();
  }
  function onShow(sym) {
    if (!S.sym && !S.csv && sym) { S.sym = sym; S.search.set(sym); }
  }

  return { init, onShow, run, optimize, readSettings, writeSettings, get last() { return S.last; } };
})();
