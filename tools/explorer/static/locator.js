// Injected into the original filing (served by the Explorer). Finds and highlights a value on request:
//  - the answer key: the exact inline-XBRL fact, by its position among the filing's ix:nonFraction tags
//    (the same document-order index the benchmark's parser assigned, f<index>);
//  - a model answer: the table row or passage matching the model's quoted line, then the cell with its value.
(function () {
  "use strict";
  const squash = (s) => String(s || "").replace(/[\s$]/g, "").toLowerCase();
  const digits = (s) => String(s ?? "").replace(/[^0-9.]/g, "").replace(/^0+(?=\d)/, "");
  const facts = () => document.getElementsByTagName("ix:nonfraction");
  const top = (el) => el.getBoundingClientRect().top + window.scrollY;

  function clear(kind) {
    document.querySelectorAll(`.fe-${kind}, .fe-${kind}-row`).forEach((e) => e.classList.remove(`fe-${kind}`, `fe-${kind}-row`));
  }

  function valueCell(scope, value) {
    const v = digits(value);
    if (!v) return null;
    const cells = [...scope.querySelectorAll("ix\\:nonfraction, td")].filter((c) => digits(c.textContent) === v);
    return cells.find((c) => c.tagName.toLowerCase() === "ix:nonfraction") || cells[0] || null;
  }

  function byQuote(span, value, nearTop) {
    const target = squash(span);
    if (target.length < 4) return null;
    const rows = [];
    for (const tr of document.querySelectorAll("tr")) {
      const t = squash(tr.textContent);
      if (t && (t.includes(target) || (target.includes(t) && t.length > 12))) rows.push(tr);
    }
    let blocks = rows;
    if (!blocks.length) {  // prose: the smallest block that contains the quote
      for (const el of document.querySelectorAll("p, div, td, span")) {
        if (squash(el.textContent).includes(target)) blocks.push(el);
      }
      blocks = blocks.filter((b) => !blocks.some((o) => o !== b && b.contains(o)));
    }
    if (!blocks.length) return null;
    const withValue = blocks.filter((b) => valueCell(b, value));
    let pool = withValue.length ? withValue : blocks;
    if (nearTop != null && pool.length > 1) pool = pool.slice().sort((a, b) => Math.abs(top(a) - nearTop) - Math.abs(top(b) - nearTop));
    const row = pool[0];
    return { row, cell: valueCell(row, value), candidates: blocks.length };
  }

  function locate(msg) {
    const kind = msg.kind === "model" ? "model" : "key";
    clear(kind);
    let row = null, cell = null, how = null, note = "";
    if (msg.factIndex != null) {
      cell = facts()[msg.factIndex] || null;
      if (cell) { row = cell.closest("tr"); how = "Exact XBRL fact"; }
    }
    if (!cell && msg.span) {
      let nearTop = null;
      if (msg.nearFact != null && facts()[msg.nearFact]) nearTop = top(facts()[msg.nearFact]);
      const r = byQuote(msg.span, msg.value, nearTop);
      if (r) {
        row = r.row; cell = r.cell; how = "Matched the quoted line";
        if (r.candidates > 1) note = `${r.candidates} places match this quote; showing the closest`;
        if (!cell) note = (note ? note + "; " : "") + "the value itself was not found in that line";
      }
    }
    const target = cell || row;
    if (!target) return { found: false };
    if (row && row !== target) row.classList.add(`fe-${kind}-row`);
    target.classList.add(`fe-${kind}`);
    target.scrollIntoView({ block: "center" });
    return { found: true, how, note, text: (target.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120) };
  }

  window.addEventListener("message", (e) => {
    if (!e.data || e.data.type !== "fe-locate") return;
    parent.postMessage({ type: "fe-located", id: e.data.id, ...locate(e.data) }, "*");
  });
  parent.postMessage({ type: "fe-ready" }, "*");
})();
