/* Combobox con buscador para listas largas (institución, nacionalidad, carrera...).
   Estructura HTML esperada:
   <div class="combo" data-name="campo" [data-source="inline" data-json="id-json"]>
     <input class="combo-input" ...>
     <input type="hidden" name="campo" class="combo-value" value="...">
     <div class="combo-list" hidden></div>
   </div>
   El <input hidden> es el que se envía (guarda el código). El visible muestra el texto. */
class Combobox {
  constructor(root) {
    this.root = root;
    this.input = root.querySelector(".combo-input");
    this.hidden = root.querySelector(".combo-value");
    this.list = root.querySelector(".combo-list");
    this.data = [];
    this.onselect = null;
    this._norm = (s) => (s || "").toLowerCase()
      .normalize("NFD").replace(/[̀-ͯ]/g, ""); // ignora acentos
    this._bind();
    const src = root.getAttribute("data-source");
    if (src === "inline") {
      const el = document.getElementById(root.getAttribute("data-json"));
      this.setData(JSON.parse(el.textContent));
    } else if (src === "url") {
      fetch(root.getAttribute("data-url")).then((r) => r.json()).then((d) => this.setData(d));
    }
  }
  setData(arr) { this.data = arr || []; this._syncFromHidden(); }
  setByCode(code) {  // fija el valor por código (usado por el arrastre tipo Excel)
    this.hidden.value = code || "";
    const it = this.data.find((o) => o.codigo === code);
    this.input.value = it ? it.descripcion : (code || "");
  }
  getCode() { return this.hidden.value; }
  _syncFromHidden() {
    const v = this.hidden.value;
    if (v) { const it = this.data.find((o) => o.codigo === v); if (it) this.input.value = it.descripcion; }
  }
  _bind() {
    this.input.addEventListener("input", () => { this.hidden.value = ""; this._render(this.input.value); });
    this.input.addEventListener("focus", () => this._render(this.input.value));
    document.addEventListener("click", (e) => { if (!this.root.contains(e.target)) this._close(); });
  }
  _render(q) {
    const nq = this._norm(q);
    let res = this.data;
    if (nq) res = this.data.filter((o) => this._norm(o.descripcion).includes(nq) || o.codigo.includes(nq));
    const total = res.length;
    res = res.slice(0, 50);
    if (!res.length) { this.list.innerHTML = '<div class="combo-empty">Sin resultados</div>'; this.list.hidden = false; return; }
    let html = res.map((o) => `<div class="combo-opt" data-c="${o.codigo}">${o.descripcion}</div>`).join("");
    if (total > 50) html += `<div class="combo-empty">… sigue escribiendo para afinar (${total} coincidencias)</div>`;
    this.list.innerHTML = html;
    this.list.hidden = false;
    this.list.querySelectorAll(".combo-opt").forEach((el) =>
      el.addEventListener("mousedown", (e) => { e.preventDefault(); this._pick(el.getAttribute("data-c"), el.textContent); }));
  }
  _pick(c, t) { this.hidden.value = c; this.input.value = t; this._close(); if (this.onselect) this.onselect(c); }
  _close() { this.list.hidden = true; }
}
