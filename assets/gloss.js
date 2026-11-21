/* 사이트 전체 용어 풀이 — data/gloss.json
   화면 글에서 어려운 말을 찾아 점선 밑줄 → 마우스를 올리거나(PC) 누르면(폰) 뜻이 떠요.
   같은 덩어리(문단·표 칸) 안에서는 처음 나온 한 번만 밑줄. 버튼·링크·입력칸·차트 안은 건드리지 않아요. */
const Gloss = (() => {
  let G = null, RX = null, tip = null, timer = null, curEl = null;
  const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "BUTTON", "A", "INPUT", "TEXTAREA", "SELECT", "OPTION", "CODE", "CANVAS", "SVG", "TEXT", "LABEL"]);
  const SKIP_SEL = "header.top, nav, .gl, .gl-t, .tv-lightweight-charts, [contenteditable], .no-gloss, #gl-tip";
  const BLOCK = "p, li, td, th, summary, h2, h3, h4, h5, dd, dt, .lt-edge, .nw-b, .nw-t, div";
  const seen = new WeakMap();
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  async function init() {
    try { G = await (await fetch("data/gloss.json?t=" + Math.floor(Date.now() / 36e5))).json(); } catch (_) { return; }
    const keys = Object.keys(G).sort((a, b) => b.length - a.length);
    // 영문 약어는 단어 경계, 한글은 그대로
    RX = new RegExp(keys.map((k) => /^[A-Za-z0-9&\-\/ .]+$/.test(k) ? `(?<![A-Za-z0-9])${esc(k)}(?![A-Za-z0-9])` : esc(k)).join("|"), "g");
    tip = document.createElement("div"); tip.id = "gl-tip"; tip.hidden = true; document.body.appendChild(tip);
    const root = document.querySelector("main") || document.body;
    scan(root);
    new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(() => scan(root), 250); }).observe(root, { childList: true, subtree: true });
    const dlgObs = () => document.querySelectorAll("dialog").forEach((d) => { if (!d._gl) { d._gl = 1; new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(() => scan(d), 250); }).observe(d, { childList: true, subtree: true }); } });
    dlgObs();
    // PC: 올리면 보이고 / 폰: 누르면 토글
    document.addEventListener("mouseover", (e) => { const t = e.target.closest && e.target.closest(".gl, .gl-t"); if (t && matchMedia("(hover: hover)").matches) show(t); });
    document.addEventListener("mouseout", (e) => { const t = e.target.closest && e.target.closest(".gl, .gl-t"); if (t && matchMedia("(hover: hover)").matches) hide(); });
    document.addEventListener("click", (e) => {
      const t = e.target.closest && e.target.closest(".gl, .gl-t");
      if (t) { e.preventDefault(); e.stopPropagation(); if (curEl === t && !tip.hidden) hide(); else show(t); return; }
      if (!e.target.closest("#gl-tip")) hide();
    }, true);
    window.addEventListener("scroll", hide, { passive: true });
    document.addEventListener("click", () => { clearTimeout(timer); timer = setTimeout(() => { scan(root); document.querySelectorAll("dialog[open]").forEach(scan); }, 300); });   // 탭 전환 등 숨어 있던 화면
  }

  function scan(root) {
    if (!RX) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (!n.nodeValue || n.nodeValue.trim().length < 2) return NodeFilter.FILTER_REJECT;
        const p = n.parentElement; if (!p) return NodeFilter.FILTER_REJECT;
        if (SKIP_TAGS.has(p.tagName.toUpperCase()) || p.closest(SKIP_SEL) || p.closest("button, a, select, svg")) return NodeFilter.FILTER_REJECT;
        if (p.offsetParent === null && !p.closest("dialog[open]")) return NodeFilter.FILTER_REJECT;   // 안 보이는 탭은 나중에
        RX.lastIndex = 0; return RX.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const n of nodes) wrap(n);
  }

  function wrap(n) {
    const blk = n.parentElement.closest(BLOCK) || n.parentElement;
    let used = seen.get(blk); if (!used) { used = new Set(); seen.set(blk, used); }
    const s = n.nodeValue; RX.lastIndex = 0; let m, last = 0, frag = null;
    while ((m = RX.exec(s))) {
      const k = m[0]; if (used.has(k)) continue;
      used.add(k); frag = frag || document.createDocumentFragment();
      frag.appendChild(document.createTextNode(s.slice(last, m.index)));
      const sp = document.createElement("span"); sp.className = "gl"; sp.dataset.gl = k; sp.textContent = k; sp.tabIndex = 0;
      frag.appendChild(sp); last = m.index + k.length;
    }
    if (!frag) return;
    frag.appendChild(document.createTextNode(s.slice(last)));
    n.parentNode.replaceChild(frag, n);
  }

  function show(el) {
    const k = el.dataset.gl; if (!G[k]) return;
    const host = el.closest("dialog[open]") || document.body; if (tip.parentNode !== host) host.appendChild(tip);   // 모달 창 위에 보이도록
    curEl = el; tip.innerHTML = `<b>${k.replace(/</g, "&lt;")}</b>${G[k].replace(/</g, "&lt;")}`; tip.hidden = false;
    const r = el.getBoundingClientRect(), w = Math.min(300, window.innerWidth - 24);
    tip.style.maxWidth = w + "px";
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let x = Math.min(Math.max(12, r.left + r.width / 2 - tw / 2), window.innerWidth - tw - 12);
    let y = r.bottom + 8; if (y + th > window.innerHeight - 8) y = r.top - th - 8;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hide() { if (tip) tip.hidden = true; curEl = null; }
  return { init, scan: () => RX && scan(document.querySelector("main") || document.body) };
})();
document.addEventListener("DOMContentLoaded", () => Gloss.init());
