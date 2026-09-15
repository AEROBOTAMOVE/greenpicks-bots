/* ─────────────────────────────────────────────────────────────
   The Green Room · платформата (клиент)
   Всички данни идват от /api — сървърът решава кой какво вижда.
   Всеки текст от бота минава през esc().
   ───────────────────────────────────────────────────────────── */
(() => {
  "use strict";
  const $app = document.getElementById("app");
  const TG = "https://t.me/green_picks_info_bot";
  const S = {
    me: null, data: null, tab: "nachalo", sport: null, sportTab: "prog", progTab: "vsichki", progSport: "", q: "",
    fishTab: "aktivni", rezDen: null, adminRejim: false, admin: null, aF: "vsichki", aQ: "", spQ: "",
  };

  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ── иконите ── */
  const SVG = {
    football: '<circle cx="12" cy="12" r="9"/><path d="M12 7.6l3.2 2.3-1.2 3.8h-4l-1.2-3.8z"/><path d="M12 3v4.6M15.2 9.9l4.4-1.4M14 13.7l2.6 4.1M10 13.7l-2.6 4.1M8.8 9.9 4.4 8.5"/>',
    basketball: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3v18M5.7 5.7c3 3.1 3 9.5 0 12.6M18.3 5.7c-3 3.1-3 9.5 0 12.6"/>',
    tennis: '<circle cx="12" cy="12" r="9"/><path d="M5.3 6.1c3.5 2.9 3.5 8.9 0 11.8M18.7 6.1c-3.5 2.9-3.5 8.9 0 11.8"/>',
    tabletennis: '<circle cx="10" cy="10" r="6.2"/><path d="M14.4 14.4 19.6 19.6"/><circle cx="18.6" cy="5.6" r="1.9"/>',
    volleyball: '<circle cx="12" cy="12" r="9"/><path d="M12 3c-1.2 4 .2 7.2 3.4 9.1M20.8 13.8c-3.6-1.4-7.2-.8-9.6 2.1M5.1 17.9c2.7-2.6 3.6-6.2 2.2-10.1"/>',
    hockey: '<path d="M7 3.5l5.3 13.2c.3.8 1 1.3 1.9 1.3H20"/><path d="M4 20.5h7"/><ellipse cx="17.2" cy="20.6" rx="2.6" ry="1"/>',
    baseball: '<circle cx="12" cy="12" r="9"/><path d="M7.4 4.9c1.8 2.5 1.8 11.7 0 14.2M16.6 4.9c-1.8 2.5-1.8 11.7 0 14.2"/><path d="M8.7 8.2H7.2M9 12H7.3M8.7 15.8H7.2M15.3 8.2h1.5M15 12h1.7M15.3 15.8h1.5"/>',
    mma: '<path d="M7.2 11.2V7.4a4.2 4.2 0 0 1 4.2-4.2h1.4a4.2 4.2 0 0 1 4.2 4.2v4.9a4.2 4.2 0 0 1-4.2 4.2h-.9V21H8.2v-5.6a3.3 3.3 0 0 1-1-4.2z"/><path d="M7.4 11.3h5"/>',
    esports: '<path d="M6.2 8h11.6a4 4 0 0 1 3.8 5.2l-1 3.1a2.5 2.5 0 0 1-4.3.8L15 15H9l-1.3 2.1a2.5 2.5 0 0 1-4.3-.8l-1-3.1A4 4 0 0 1 6.2 8z"/><path d="M8.2 10.4v3.2M6.6 12h3.2"/><circle cx="15.9" cy="11" r=".7"/><circle cx="17.6" cy="13" r=".7"/>',
    rugby: '<ellipse cx="12" cy="12" rx="9.4" ry="5.4" transform="rotate(-40 12 12)"/><path d="M9.2 14.8l5.6-5.6M10.2 11.6l2.2 2.2M11.8 10l2.2 2.2"/>',
    _: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  };
  SVG.boxing = SVG.mma;
  SVG.amfootball = SVG.rugby;
  const ik = (sport, cls = "ik") => `<span class="${cls}"><svg viewBox="0 0 24 24" aria-hidden="true">${SVG[sport] || SVG._}</svg></span>`;
  const ICO = {
    nachalo: '<path d="M3.5 11 12 4l8.5 7v9h-5.5v-6h-6v6H3.5z"/>',
    sport: '<circle cx="12" cy="12" r="9"/><path d="M12 7.6l3.2 2.3-1.2 3.8h-4l-1.2-3.8z"/>',
    prognozi: '<path d="M4 19.5V5M4 19.5h16M8 15l4-4 3 3 5-6"/>',
    fishove: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    rezultati: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8.5 12.2 2.4 2.4 4.8-5"/>',
    novini: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9h6M7 13h10M7 16h7"/>',
    profil: '<circle cx="12" cy="8.5" r="4"/><path d="M4.5 20.5c1-4 4.2-6 7.5-6s6.5 2 7.5 6"/>',
    tarsi: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    poshta: '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="m4 7 8 6 8-6"/>',
    kliuch: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    oko: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    str: '<path d="m9 5 7 7-7 7"/>',
    shtit: '<path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6z"/><path d="m9 12 2 2 4-4"/>',
    pomosht: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.3a2.5 2.5 0 1 1 3.4 2.4c-.7.3-1 .8-1 1.6v.4M12 17h.01"/>',
    izhod: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l-4-4 4-4M6 12h10"/>',
    kalendar: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
  };
  const ico = (n, cls = "ico") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICO[n] || ""}</svg>`;
  const TOPKA = '<svg viewBox="0 0 24 24" aria-hidden="true">' + SVG.football + "</svg>";

  const NAV = [["nachalo", "Начало"], ["sport", "Спорт"], ["prognozi", "Прогнози"], ["fishove", "Фишове"], ["rezultati", "Резултати"], ["novini", "Новини"], ["profil", "Профил"]];

  /* ── мрежата ── */
  async function api(method, path, body) {
    const o = { method, headers: {}, credentials: "same-origin" };
    if (body !== undefined) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(body); }
    try {
      const r = await fetch(path, o);
      let j = null;
      try { j = await r.json(); } catch (e) { j = null; }
      return { s: r.status, j: j || {} };
    } catch (e) {
      return { s: 0, j: { error: "Няма връзка. Провери интернета и опитай пак." } };
    }
  }
  function toast(t) {
    const d = document.createElement("div");
    d.className = "suob";
    d.setAttribute("role", "status");
    d.textContent = t;
    document.body.appendChild(d);
    setTimeout(() => d.remove(), 2800);
  }

  /* ── помощници ── */
  function denEt(den) {
    const d = S.data && S.data.dnes;
    if (!den) return "";
    if (d) {
      const r = Math.round((new Date(den + "T12:00:00Z") - new Date(d + "T12:00:00Z")) / 86400000);
      if (r === 0) return "Днес";
      if (r === 1) return "Утре";
      if (r === -1) return "Вчера";
    }
    const p = den.split("-");
    return `${p[2]}.${p[1]}`;
  }
  const MES = ["януари", "февруари", "март", "април", "май", "юни", "юли", "август", "септември", "октомври", "ноември", "декември"];
  const denDylag = (den) => {
    if (!den) return "";
    const p = den.split("-");
    const e = denEt(den);
    const t = `${Number(p[2])} ${MES[Number(p[1]) - 1]}`;
    return e === "Днес" || e === "Утре" || e === "Вчера" ? `${e} · ${t}` : t;
  };
  const datBg = (iso) => {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleDateString("bg-BG", { timeZone: "Europe/Sofia", day: "2-digit", month: "2-digit", year: "numeric" }); }
    catch (e) { return String(iso).slice(0, 10); }
  };
  function izborTxt(s) {
    s = String(s || "");
    const m = /^([12])\s*·\s*(.+)$/.exec(s);
    if (m) return "Победа за " + m[2].trim().replace(/^победа\s+(за\s+)?/i, "");
    if (/^(1[ХX]|[ХX]2|12)(\s|·|$)/.test(s)) return "Двоен шанс " + s.split("·")[0].trim();
    if (/^[ХX](\s|·|$)/.test(s)) return "Равенство";
    return s;
  }
  function inicial(t) {
    const w = String(t || "").replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
    if (!w.length) return "?";
    return (w.length > 1 ? w[0][0] + w[1][0] : w[0].slice(0, 2)).toUpperCase();
  }
  function ekip(name) {
    let h = 0;
    for (const c of String(name)) h = (h * 31 + c.codePointAt(0)) >>> 0;
    const hue = [152, 168, 190, 205, 42, 18, 262, 96][h % 8];
    return `<span class="ekip" style="--h:${hue}" aria-hidden="true">${esc(inicial(name))}</span>`;
  }
  const zvezdi = (n) => (n ? "★".repeat(Math.min(3, n)) + "☆".repeat(Math.max(0, 3 - n)) : "");
  const brSport = () => {
    const m = {};
    for (const k of (S.data && S.data.prognozi) || []) m[k.sport] = (m[k.sport] || 0) + 1;
    return m;
  };
  const eTop = (k) => (k.zvezdi || 0) >= 3 || (k.procent || 0) >= 70;

  /* ── парчета ── */
  function kartaPrognoza(k) {
    const pr = k.procent;
    return `<article class="pk">
      <div class="pk-h">${ik(k.sport, "ik s")}<span class="liga">${esc(k.sport_bg)}${k.liga ? " · " + esc(k.liga) : ""}</span>
        ${k.fish ? `<span class="fish">фиш ${esc(k.fish)}</span>` : ""}<span class="den">${esc(denEt(k.den))}</span></div>
      <div class="pk-mach"><div class="pk-tim">${ekip(k.dom)}<span>${esc(k.dom)}</span></div><div class="pk-vs">VS</div>
        <div class="pk-tim d">${ekip(k.gost)}<span>${esc(k.gost)}</span></div></div>
      <div class="pk-izbor"><div><small>Нашата прогноза</small><b>${esc(izborTxt(k.izbor))}</b></div>
        ${k.koef ? `<div class="pk-koef"><small>Коеф.</small><b>${esc(k.koef.toFixed(2))}</b></div>` : ""}</div>
      ${k.zashto ? `<p class="pk-zashto">${esc(k.zashto)}</p>` : ""}
      ${pr ? `<div class="pk-uv"><span>Увереност</span><div class="bar"><i style="width:${Math.max(4, Math.min(100, pr))}%"></i></div><b>${esc(pr)}%</b>
        ${k.zvezdi ? `<span class="zv" aria-label="${esc(k.zvezdi)} звезди">${zvezdi(k.zvezdi)}</span>` : ""}</div>` : ""}
    </article>`;
  }
  const znak = (p) => (p === true ? '<span class="znak p">✓ Позната</span>' : p === false ? '<span class="znak n">✗ Непозната</span>' : '<span class="znak v">—</span>');
  function kartaRezultat(k) {
    const sk = String(k.rezultat || "").split(/[:\-–]/).map((x) => x.trim());
    const dva = sk.length === 2;
    return `<article class="rz">
      <div class="rz-t">${ekip(k.dom)}<span>${esc(k.dom)}</span></div><div class="rz-sk">${dva ? esc(sk[0]) : ""}</div>
      <div class="rz-t">${ekip(k.gost)}<span>${esc(k.gost)}</span></div><div class="rz-sk">${dva ? esc(sk[1]) : esc(k.rezultat || "")}</div>
      <div class="rz-dolu"><span>Прогноза: <b>${esc(izborTxt(k.izbor))}</b>${k.koef ? ` · ${esc(k.koef.toFixed(2))}` : ""}</span>${znak(k.poznata)}</div>
    </article>`;
  }
  function kartaFish(f) {
    const stT = { poznat: "Познат", nepoznat: "Непознат", v_igra: "В игра" }[f.status] || "";
    return `<article class="fs">
      <header><b>Фиш №${esc(f.nomer)}</b><span class="den">${esc(denDylag(f.den))}</span><span class="st ${esc(f.status)}">${stT}</span></header>
      <ol>${f.kraka.map((k) => `<li>${ik(k.sport, "ik s")}<span class="m">${esc(k.dom)} — ${esc(k.gost)}</span>
        <span class="k">${k.koef ? esc(k.koef.toFixed(2)) : "—"}${k.poznata === true || k.poznata === false ? znak(k.poznata) : ""}</span>
        <span class="i">${esc(izborTxt(k.izbor))}${k.rezultat ? ` · ${esc(k.rezultat)}` : ""}</span></li>`).join("")}</ol>
      <footer><span>${esc(f.kraka.length)} събития · общ коефициент</span><b>${f.koef ? esc(f.koef.toFixed(2)) : "—"}</b></footer>
    </article>`;
  }

  /* ── рамката ── */
  function ramka(glava, telo) {
    const m = S.me || {};
    const nav = (cls) => NAV.map(([k, t]) => `<button data-tab="${k}" ${S.tab === k && !S.adminRejim ? 'aria-current="page"' : ""}>${ico(k)}<span>${t}</span></button>`).join("");
    return `<div class="app">
      <aside class="side"><div class="marka"><img src="/logo.svg" alt=""><div class="ime"><small>THE</small>GREEN ROOM</div></div>
        <nav aria-label="Основно меню">${nav()}</nav>
        <div class="az"><span class="av">${esc(inicial(m.email))}</span><div><b>${esc(m.email || "")}</b><span>${esc(statusTxt(m))}</span></div></div></aside>
      <div>
        <div class="glaven">
          <header class="gore"><div class="marka"><img src="/logo.svg" alt=""><div class="ime"><small>THE</small>GREEN ROOM</div></div>
            <button class="avatar" data-tab="profil" aria-label="Профил">${esc(inicial(m.email))}</button></header>
          ${glava ? `<div class="glava"><h1>${esc(glava[0])}</h1>${glava[1] ? `<p>${esc(glava[1])}</p>` : ""}</div>` : ""}
          ${telo}
          <footer class="podpis"><div class="s">THE GREEN ROOM</div>По-добри играчи. По-умни решения. · 18+</footer>
        </div>
      </div>
      <nav class="dolu" aria-label="Основно меню"><div class="v">${nav()}</div></nav>
    </div>`;
  }
  function statusTxt(m) {
    if (!m) return "";
    if (m.admin) return "Администратор";
    if (m.status === "active") return `Активен · ${m.days_left} ${m.days_left === 1 ? "ден" : "дни"}`;
    return { expired: "Изтекъл", locked: "Заключен" }[m.status] || "";
  }

  /* ── НАЧАЛО ── */
  function ekranNachalo() {
    const d = S.data || {};
    const pr = d.prognozi || [];
    const dnes = pr.filter((k) => k.den === d.dnes);
    const top = (dnes.length ? dnes : pr).slice().sort((a, b) => (b.procent || 0) - (a.procent || 0)).slice(0, 4);
    const br = brSport();
    const sp = (d.sportove || []).filter((s) => br[s.sport]);
    const o = d.obshto || {};
    const fDnes = (d.fishove || []).filter((f) => f.den === d.dnes);
    const rez = (d.rezultati || []).slice(0, 4);
    const nov = (d.novini || []).slice(0, 4);
    return ramka(null, `
      <section class="geroi" style="margin-top:16px"><span class="lyk"></span><span class="topka">${TOPKA}</span>
        <h2>Големи мачове.<br>По-добри решения.</h2><p>Всяка прогноза идва с анализ и обяснение защо.</p>
        <button class="btn" data-idi="prognozi">Виж прогнозите ${ico("str")}</button></section>
      <div class="plochki" style="margin-top:14px">
        <div class="plochka"><b>${esc(dnes.length)}</b><span>прогнози днес</span></div>
        <div class="plochka"><b>${esc(pr.filter(eTop).length)}</b><span>топ избора</span></div>
        <div class="plochka"><b class="em">${o.uspeh != null ? esc(o.uspeh) + "%" : "—"}</b><span>успеваемост 30 дни</span></div></div>
      ${sp.length ? `<section class="sekcia"><header><h2>Спортове</h2><button class="vsichki" data-idi="sport">Всички</button></header>
        <div class="sp-red">${sp.map((s) => `<button class="sp-it" data-sport="${esc(s.sport)}">${ik(s.sport)}<span>${esc(s.sport_bg)}</span></button>`).join("")}</div></section>` : ""}
      <div class="dvoino">
        <section class="sekcia"><header><h2>${dnes.length ? "Топ прогнози за днес" : "Топ прогнози"}</h2><button class="vsichki" data-idi="prognozi">Виж всички</button></header>
          ${top.length ? `<div class="karti">${top.map(kartaPrognoza).join("")}</div>` : '<p class="prazno">Новите прогнози излизат през целия ден.</p>'}</section>
        <div>
          ${fDnes.length ? `<section class="sekcia"><header><h2>Фишове днес</h2><button class="vsichki" data-idi="fishove">Всички</button></header>
            <div class="karti">${fDnes.slice(0, 2).map(kartaFish).join("")}</div></section>` : ""}
          ${rez.length ? `<section class="sekcia"><header><h2>Последни резултати</h2><button class="vsichki" data-idi="rezultati">Всички</button></header>
            <div class="karti">${rez.map(kartaRezultat).join("")}</div></section>` : ""}
          ${nov.length ? `<section class="sekcia"><header><h2>Новини</h2><button class="vsichki" data-idi="novini">Всички</button></header>
            <div class="spisyk">${nov.map((t) => `<div class="novina">${ik(sportOtZaglavie(t), "ik")}<p>${esc(t)}</p></div>`).join("")}</div></section>` : ""}
        </div>
      </div>`);
  }

  /* ── СПОРТ ── */
  function ekranSport() {
    const d = S.data || {};
    const br = brSport();
    if (S.sport) {
      const s = S.sport;
      const ime = ((d.sportove || []).find((x) => x.sport === s) || {}).sport_bg || s;
      const pr = (d.prognozi || []).filter((k) => k.sport === s);
      const rz = (d.rezultati || []).filter((k) => k.sport === s);
      const lista = S.sportTab === "rez"
        ? (rz.length ? `<div class="karti kol">${rz.slice(0, 60).map(kartaRezultat).join("")}</div>` : '<p class="prazno">Още няма резултати за този спорт.</p>')
        : (pr.length ? `<div class="karti kol">${pr.map(kartaPrognoza).join("")}</div>` : '<p class="prazno">В момента няма прогнози за този спорт.</p>');
      return ramka([ime, `${pr.length} прогнози · ${rz.length} резултата за 7 дни`], `
        <div class="chipove" style="margin-top:0"><button class="chip" data-sport="">${ico("str")}Всички спортове</button></div>
        <div class="tabs" style="margin-top:12px"><button data-stab="prog" aria-pressed="${S.sportTab === "prog"}">Прогнози</button>
          <button data-stab="rez" aria-pressed="${S.sportTab === "rez"}">Резултати</button></div>
        <div style="margin-top:14px">${lista}</div>`);
    }
    return ramka(["Всички спортове", "Избери спорт — прогнозите и резултатите му са на едно място."], `
      <label class="tarsene">${ico("tarsi")}<input id="sp-q" type="search" placeholder="Търси спорт…" value="${esc(S.spQ)}" aria-label="Търси спорт"></label>
      <div class="spisyk kol" id="sp-lista" style="margin-top:12px">${listaSportove()}</div>`);
  }
  function listaSportove() {
    const d = S.data || {};
    const br = brSport();
    const rz = {};
    for (const k of d.rezultati || []) rz[k.sport] = (rz[k.sport] || 0) + 1;
    const q = S.spQ.trim().toLowerCase();
    const sp = (d.sportove || []).filter((s) => !q || s.sport_bg.toLowerCase().includes(q))
      .sort((a, b) => (br[b.sport] || 0) - (br[a.sport] || 0));
    return sp.length ? sp.map((s) => `<button class="red" data-sport="${esc(s.sport)}">${ik(s.sport)}
      <span><b>${esc(s.sport_bg)}</b><span class="pod">${br[s.sport] ? br[s.sport] + " прогнози" : "няма прогнози в момента"}${rz[s.sport] ? " · " + rz[s.sport] + " резултата" : ""}</span></span>
      <span class="str">${ico("str")}</span></button>`).join("") : '<p class="prazno">Няма такъв спорт.</p>';
  }

  /* ── ПРОГНОЗИ ── */
  function filtriraniPrognozi() {
    const d = S.data || {};
    let x = d.prognozi || [];
    if (S.progTab === "dnes") x = x.filter((k) => k.den === d.dnes);
    else if (S.progTab === "utre") x = x.filter((k) => k.den > d.dnes);
    else if (S.progTab === "top") x = x.filter(eTop);
    if (S.progSport) x = x.filter((k) => k.sport === S.progSport);
    const q = S.q.trim().toLowerCase();
    if (q) x = x.filter((k) => (k.dom + " " + k.gost + " " + k.liga + " " + k.sport_bg).toLowerCase().includes(q));
    return x;
  }
  function listaPrognozi() {
    const x = filtriraniPrognozi();
    if (!x.length) return '<p class="prazno">Няма прогнози за този избор.</p>';
    const po = new Map();
    for (const k of x) { if (!po.has(k.den)) po.set(k.den, []); po.get(k.den).push(k); }
    return [...po.entries()].map(([den, ks]) => `<div class="den-glava">${esc(denDylag(den))} · ${ks.length}</div>
      <div class="karti kol">${ks.map(kartaPrognoza).join("")}</div>`).join("");
  }
  function ekranPrognozi() {
    const d = S.data || {};
    const br = brSport();
    const sp = (d.sportove || []).filter((s) => br[s.sport]);
    const tb = [["vsichki", "Всички"], ["dnes", "Днес"], ["utre", "Утре"], ["top", "Топ"]];
    return ramka(["Прогнози", "Всеки избор с коефициент, увереност и защо го даваме."], `
      <div class="tabs">${tb.map(([v, t]) => `<button data-ptab="${v}" aria-pressed="${S.progTab === v}">${t}</button>`).join("")}</div>
      <div class="chipove"><button class="chip" data-psport="" aria-pressed="${!S.progSport}">Всички спортове</button>
        ${sp.map((s) => `<button class="chip" data-psport="${esc(s.sport)}" aria-pressed="${S.progSport === s.sport}">${ik(s.sport, "ik s")}${esc(s.sport_bg)} · ${br[s.sport]}</button>`).join("")}</div>
      <label class="tarsene">${ico("tarsi")}<input id="p-q" type="search" placeholder="Търси отбор, играч или лига…" value="${esc(S.q)}" aria-label="Търси"></label>
      <div id="p-lista">${listaPrognozi()}</div>`);
  }

  /* ── ФИШОВЕ ── */
  function ekranFishove() {
    const f = (S.data && S.data.fishove) || [];
    const akt = f.filter((x) => x.status === "v_igra");
    const pri = f.filter((x) => x.status !== "v_igra");
    const x = S.fishTab === "aktivni" ? akt : pri;
    const pozn = pri.filter((y) => y.status === "poznat").length;
    return ramka(["Фишове", "Комбинирани фишове от нашите прогнози — с общ коефициент."], `
      <div class="tabs"><button data-ftab="aktivni" aria-pressed="${S.fishTab === "aktivni"}">В игра · ${akt.length}</button>
        <button data-ftab="priklyucheni" aria-pressed="${S.fishTab !== "aktivni"}">Приключили · ${pri.length}</button></div>
      ${S.fishTab !== "aktivni" && pri.length ? `<div class="obzor"><div class="pryasten" style="--p:${Math.round((100 * pozn) / pri.length)}"><b>${Math.round((100 * pozn) / pri.length)}%</b></div>
        <p>Познати фишове за 7 дни<br><b>${pozn}</b> от ${pri.length}</p></div>` : ""}
      <div class="karti kol" style="margin-top:14px">${x.length ? x.map(kartaFish).join("") : `<p class="prazno">${S.fishTab === "aktivni" ? "В момента няма фишове в игра." : "Още няма приключили фишове."}</p>`}</div>`);
  }

  /* ── РЕЗУЛТАТИ ── */
  function ekranRezultati() {
    const r = (S.data && S.data.rezultati) || [];
    const dni = [...new Set(r.map((x) => x.den))].slice(0, 7);
    if (!S.rezDen || !dni.includes(S.rezDen)) S.rezDen = dni[0] || null;
    const x = r.filter((k) => k.den === S.rezDen);
    const p = x.filter((k) => k.poznata === true).length;
    const n = x.filter((k) => k.poznata === true || k.poznata === false).length;
    const po = new Map();
    for (const k of x) { const kl = k.sport_bg + (k.liga ? " · " + k.liga : ""); if (!po.has(kl)) po.set(kl, { s: k.sport, ks: [] }); po.get(kl).ks.push(k); }
    return ramka(["Резултати", "Как завършиха нашите прогнози."], dni.length ? `
      <div class="tabs">${dni.slice(0, 4).map((d) => `<button data-rez="${esc(d)}" aria-pressed="${S.rezDen === d}">${esc(denEt(d))}</button>`).join("")}</div>
      ${dni.length > 4 ? `<div class="chipove">${dni.slice(4).map((d) => `<button class="chip" data-rez="${esc(d)}" aria-pressed="${S.rezDen === d}">${ico("kalendar", "ico")}${esc(denEt(d))}</button>`).join("")}</div>` : ""}
      ${n ? `<div class="obzor"><div class="pryasten" style="--p:${Math.round((100 * p) / n)}"><b>${Math.round((100 * p) / n)}%</b></div>
        <p>${esc(denDylag(S.rezDen))}<br><b>${p}</b> познати от ${n}</p></div>` : ""}
      ${[...po.entries()].map(([kl, g]) => `<div class="liga-glava">${ik(g.s, "ik s")}${esc(kl)}</div><div class="karti kol">${g.ks.map(kartaRezultat).join("")}</div>`).join("")}`
      : '<p class="prazno">Още няма оценени прогнози.</p>');
  }

  /* ── НОВИНИ ── */
  function sportOtZaglavie(t) {
    const s = String(t).toLowerCase();
    if (/тенис на маса/.test(s)) return "tabletennis";
    if (/тенис|уимбълдън|ролан|us open|atp|wta|алкарас|синер|джокович/.test(s)) return "tennis";
    if (/баскет|нба|nba|евролига/.test(s)) return "basketball";
    if (/волей/.test(s)) return "volleyball";
    if (/хокей|nhl|нхл/.test(s)) return "hockey";
    if (/ufc|мма|mma|бокс|боец|двубой/.test(s)) return "mma";
    if (/формула|f1|мотогп/.test(s)) return "_";
    return "football";
  }
  function ekranNovini() {
    const n = (S.data && S.data.novini) || [];
    if (!n.length) return ramka(["Новини"], '<p class="prazno">Няма нови новини в момента.</p>');
    const [g, ...ost] = n;
    return ramka(["Новини", "Най-важното от спорта днес."], `
      <article class="nov-glavna">${ik(sportOtZaglavie(g), "ik")}<div class="etiket">Водеща новина</div><h3>${esc(g)}</h3></article>
      <div class="spisyk kol" style="margin-top:12px">${ost.map((t) => `<div class="novina">${ik(sportOtZaglavie(t), "ik")}<p>${esc(t)}</p></div>`).join("")}</div>`);
  }

  /* ── ПРОФИЛ ── */
  function ekranProfil() {
    const m = S.me || {};
    const d = S.data || {};
    const o = d.obshto || {};
    return ramka(["Моят профил"], `
      <section class="prof"><span class="av">${esc(inicial(m.email))}</span><h2>${esc(m.email)}</h2>
        <span class="znachka ${esc(m.admin ? "admin" : m.status)}">${esc(statusTxt(m))}</span></section>
      <div class="plochki" style="margin-top:12px">
        <div class="plochka"><b>${esc((d.prognozi || []).length)}</b><span>прогнози сега</span></div>
        <div class="plochka"><b>${esc((d.fishove || []).filter((f) => f.status === "v_igra").length)}</b><span>фиша в игра</span></div>
        <div class="plochka"><b class="em">${o.uspeh != null ? esc(o.uspeh) + "%" : "—"}</b><span>успеваемост 30 дни</span></div></div>
      <section class="sekcia"><div class="meniu">
        ${m.admin ? "" : `<div class="info-red">${ico("kalendar")}<span>Достъп до</span><span>${esc(datBg(m.access_until))}</span></div>`}
        <div class="info-red">${ico("poshta")}<span>Регистриран</span><span>${esc(datBg(m.registered))}</span></div>
        ${m.admin ? `<button data-admin="1">${ico("shtit")}<span>Админ панел</span><span class="str">${ico("str")}</span></button>` : ""}
        <a href="${TG}" target="_blank" rel="noopener">${ico("pomosht")}<span>Помощ в Telegram</span><span class="str">${ico("str")}</span></a>
        <button data-izhod="1" class="cherv">${ico("izhod")}<span>Изход</span></button>
      </div></section>`);
  }

  /* ── АДМИН ── */
  function ekranAdmin() {
    const a = S.admin;
    let telo;
    if (!a) telo = '<p class="tiho">Зарежда се…</p>';
    else if (a.error) telo = `<p class="greshka">${esc(a.error)}</p>`;
    else {
      const u = a.users || [];
      const br = { vsichki: u.length, active: u.filter((x) => x.status === "active").length, expired: u.filter((x) => x.status === "expired").length, locked: u.filter((x) => x.status === "locked").length };
      const fl = [["vsichki", "Всички"], ["active", "Активни"], ["expired", "Изтекли"], ["locked", "Заключени"]];
      telo = `<div class="plochki">
          <div class="plochka"><b>${br.vsichki}</b><span>профила</span></div><div class="plochka"><b class="em">${br.active}</b><span>активни</span></div>
          <div class="plochka"><b>${br.expired + br.locked}</b><span>изтекли/заключени</span></div></div>
        <div class="chipove">${fl.map(([v, t]) => `<button class="chip" data-af="${v}" aria-pressed="${S.aF === v}">${t} · ${br[v]}</button>`).join("")}</div>
        <label class="tarsene">${ico("tarsi")}<input id="a-q" type="search" placeholder="Търси имейл…" value="${esc(S.aQ)}" aria-label="Търси имейл"></label>
        <div class="spisyk kol" id="a-lista" style="margin-top:12px">${listaPotrebiteli()}</div>`;
    }
    return ramka(["Админ панел", "Кой имейл до кога има достъп. Новите профили получават 21 дни."], `
      <div class="chipove" style="margin-top:0"><button class="chip" data-nazad="1">${ico("str")}Профил</button><button class="chip" data-opresni="1">Опресни</button></div>
      <details class="nov-potr" style="margin-top:12px"><summary>${ico("plus")}Нов профил</summary>
        <form id="f-sazdai" autocomplete="off">
          <label class="pole"><span>Имейл</span><input class="bez" id="n-email" type="email" required></label>
          <label class="pole"><span>Парола (поне 8 знака)</span><input class="bez" id="n-pass" type="text" minlength="8" required></label>
          <label class="pole"><span>Дни достъп</span><input class="bez" id="n-dni" type="number" min="1" max="3650" value="21"></label>
          <button class="btn" type="submit">Създай профила</button></form></details>
      <div style="margin-top:14px">${telo}</div>`);
  }
  function listaPotrebiteli() {
    const a = S.admin || {};
    const q = S.aQ.trim().toLowerCase();
    const u = (a.users || []).filter((x) => (S.aF === "vsichki" || x.status === S.aF) && (!q || x.email.includes(q)));
    if (!u.length) return '<p class="prazno">Няма профили за този избор.</p>';
    return u.map((x) => `<div class="potr"><div class="g"><span class="av">${esc(inicial(x.email))}</span><b>${esc(x.email)}</b>
        <span class="znachka ${esc(x.admin ? "admin" : x.status)}">${esc(x.admin ? "администратор" : x.status_bg)}</span></div>
      <div class="meta">${x.admin ? "" : `Достъп до <b>${esc(datBg(x.access_until))}</b>${x.days_left ? ` · ${esc(x.days_left)} дни` : ""} · `}регистриран ${esc(datBg(x.registered))} · последен вход ${esc(x.last_login ? datBg(x.last_login) : "—")}</div>
      ${x.admin ? "" : `<div class="deistvia">
        <button class="btn m" data-a="extend" data-d="7" data-e="${esc(x.email)}">+7 дни</button>
        <button class="btn m" data-a="extend" data-d="21" data-e="${esc(x.email)}">+21</button>
        <button class="btn m" data-a="extend" data-d="30" data-e="${esc(x.email)}">+30</button>
        <input type="date" aria-label="Точна дата за ${esc(x.email)}" data-dat="${esc(x.email)}">
        <button class="btn m v2" data-a="set_until" data-e="${esc(x.email)}">Задай дата</button>
        ${x.locked ? `<button class="btn m v2" data-a="unlock" data-e="${esc(x.email)}">Отключи</button>` : `<button class="btn m v2" data-a="lock" data-e="${esc(x.email)}">Заключи</button>`}
        <button class="btn m v2" data-a="set_password" data-e="${esc(x.email)}">Нова парола</button>
        <button class="btn m cherv" data-a="delete" data-e="${esc(x.email)}">Изтрий</button></div>`}
    </div>`).join("");
  }
  async function zarediAdmin() {
    const r = await api("GET", "/api/admin/users");
    S.admin = r.s === 200 ? r.j : { error: r.j.error || "Грешка " + r.s };
    if (S.adminRejim) render();
  }
  async function adminDeistvie(action, email, extra) {
    const r = await api("POST", "/api/admin/user", Object.assign({ action, email }, extra || {}));
    if (r.s >= 200 && r.s < 300) { toast("Готово."); await zarediAdmin(); } else toast(r.j.error || "Грешка " + r.s);
  }

  /* ── ВХОД ── */
  function ekranVhod(rejim, greshka) {
    const reg = rejim === "reg";
    $app.innerHTML = `<main class="vhod"><div class="vhod-k">
      <img class="logo-g" src="/logo.svg" alt=""><div class="the">— THE —</div><div class="gr">GREEN ROOM</div>
      <div class="motto">Повече от прогнози. По-умни решения.</div>
      <div class="vhod-kutia"><h1>${reg ? "Създай профил" : "Добре дошъл!"}</h1>
        <p>${reg ? "Новият профил получава 21 дни пълен достъп." : "Влез в своя свят на анализи и прогнози."}</p>
        <form id="f-vhod" novalidate>
          <label class="pole"><span>Имейл</span><span class="vhod-p">${ico("poshta")}<input id="v-email" type="email" autocomplete="email" placeholder="ime@primer.bg" required></span></label>
          <label class="pole"><span>Парола</span><span class="vhod-p">${ico("kliuch")}<input id="v-pass" type="password" autocomplete="${reg ? "new-password" : "current-password"}" placeholder="${reg ? "поне 8 знака" : "паролата ти"}" minlength="8" required>
            <button type="button" class="oko" data-oko="1" aria-label="Покажи паролата">${ico("oko")}</button></span></label>
          <button class="btn shir" type="submit">${reg ? "Създай профила" : "Вход"}</button>
          <div class="greshka" role="alert">${esc(greshka || "")}</div>
          ${reg ? "" : '<button type="button" class="zabr" data-zabr="1">Забравена парола?</button>'}
        </form>
        <div class="ili">или</div>
        <button class="btn v2 shir" data-rejim="${reg ? "vhod" : "reg"}">${reg ? "Имам профил — вход" : "Създай нов акаунт"}</button>
      </div>
      <div class="krai">По-добри играчи. По-умни решения. · 18+</div></div></main>`;
    const f = document.getElementById("f-vhod");
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("v-email").value.trim();
      const password = document.getElementById("v-pass").value;
      const b = f.querySelector('button[type="submit"]');
      b.disabled = true;
      const r = await api("POST", reg ? "/api/register" : "/api/login", { email, password });
      b.disabled = false;
      if (r.s === 200 || r.s === 201) { S.me = r.j; await start(); } else ekranVhod(rejim, r.j.error || "Грешка " + r.s);
    });
    $app.querySelector("[data-rejim]").addEventListener("click", (e) => ekranVhod(e.currentTarget.dataset.rejim));
    $app.querySelector("[data-oko]").addEventListener("click", () => { const i = document.getElementById("v-pass"); i.type = i.type === "password" ? "text" : "password"; });
    const z = $app.querySelector("[data-zabr]");
    if (z) z.addEventListener("click", () => toast("Пиши ни в Telegram — администраторът ще ти даде нова парола."));
  }
  function ekranIzteklo(msg) {
    $app.innerHTML = `<main class="vhod"><div class="vhod-k">
      <img class="logo-g" src="/logo.svg" alt=""><div class="the">— THE —</div><div class="gr">GREEN ROOM</div>
      <div class="vhod-kutia" style="margin-top:18px"><h1>Достъпът ти изтече</h1>
        <p>${esc(msg || "Достъпът ти изтече. Свържи се с администратора.")}</p>
        <a class="btn shir" href="${TG}" target="_blank" rel="noopener">Пиши ни в Telegram</a>
        <div class="ili">или</div><button class="btn v2 shir" id="b-izhod">Изход</button></div></div></main>`;
    document.getElementById("b-izhod").addEventListener("click", izhod);
  }
  async function izhod() {
    await api("POST", "/api/logout", {});
    Object.assign(S, { me: null, data: null, admin: null, adminRejim: false, tab: "nachalo" });
    ekranVhod("vhod");
  }

  /* ── основното ── */
  function render() {
    if (!S.me) return ekranVhod("vhod");
    const f = S.adminRejim ? ekranAdmin : ({ nachalo: ekranNachalo, sport: ekranSport, prognozi: ekranPrognozi, fishove: ekranFishove,
      rezultati: ekranRezultati, novini: ekranNovini, profil: ekranProfil }[S.tab] || ekranNachalo);
    $app.innerHTML = f();
  }
  const idi = (tab) => { S.tab = tab; S.adminRejim = false; render(); window.scrollTo(0, 0); };

  $app.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t || !$app.contains(t)) return;
    const ds = t.dataset;
    if (ds.tab) { if (ds.tab !== "sport") S.sport = null; return idi(ds.tab); }
    if (ds.idi) { S.sport = null; return idi(ds.idi); }
    if (ds.sport !== undefined) { S.sport = ds.sport || null; S.sportTab = "prog"; return idi("sport"); }
    if (ds.stab) { S.sportTab = ds.stab; return render(); }
    if (ds.ptab) { S.progTab = ds.ptab; return render(); }
    if (ds.psport !== undefined) { S.progSport = ds.psport; return render(); }
    if (ds.ftab) { S.fishTab = ds.ftab; return render(); }
    if (ds.rez) { S.rezDen = ds.rez; return render(); }
    if (ds.izhod) return izhod();
    if (ds.admin) { S.adminRejim = true; S.admin = null; render(); window.scrollTo(0, 0); return zarediAdmin(); }
    if (ds.nazad) { S.adminRejim = false; return idi("profil"); }
    if (ds.opresni) return zarediAdmin();
    if (ds.af) { S.aF = ds.af; return render(); }
    if (ds.a) {
      const email = ds.e;
      if (ds.a === "extend") return adminDeistvie("extend", email, { days: Number(ds.d) });
      if (ds.a === "set_until") {
        const inp = $app.querySelector(`input[data-dat="${CSS.escape(email)}"]`);
        if (!inp || !inp.value) return toast("Избери дата в полето до бутона.");
        return adminDeistvie("set_until", email, { until: inp.value });
      }
      if (ds.a === "set_password") {
        const v = prompt("Нова парола за " + email + " (поне 8 знака):");
        return v ? adminDeistvie("set_password", email, { password: v }) : undefined;
      }
      if (ds.a === "delete") return confirm("Да изтрия ли профила " + email + " завинаги?") ? adminDeistvie("delete", email) : undefined;
      return adminDeistvie(ds.a, email);
    }
  });
  $app.addEventListener("input", (e) => {
    const id = e.target.id;
    if (id === "p-q") { S.q = e.target.value; document.getElementById("p-lista").innerHTML = listaPrognozi(); }
    else if (id === "sp-q") { S.spQ = e.target.value; document.getElementById("sp-lista").innerHTML = listaSportove(); }
    else if (id === "a-q") { S.aQ = e.target.value; document.getElementById("a-lista").innerHTML = listaPotrebiteli(); }
  });
  $app.addEventListener("submit", async (e) => {
    if (e.target.id !== "f-sazdai") return;
    e.preventDefault();
    const email = document.getElementById("n-email").value.trim();
    const password = document.getElementById("n-pass").value;
    const days = Number(document.getElementById("n-dni").value) || 21;
    const r = await api("POST", "/api/admin/user", { action: "create", email, password, days });
    if (r.s === 201) { toast("Профилът е създаден."); zarediAdmin(); } else toast(r.j.error || "Грешка " + r.s);
  });

  async function zarediDanni() {
    const r = await api("GET", "/api/data");
    if (r.s === 200) { S.data = r.j; if (r.j.me) S.me = r.j.me; return true; }
    if (r.s === 401) { S.me = null; ekranVhod("vhod"); return false; }
    if (r.s === 403) { ekranIzteklo(r.j.error); return false; }
    toast(r.j.error || "Данните не се заредиха. Опитай пак.");
    return true;
  }
  async function start() {
    if (!S.me) {
      const r = await api("GET", "/api/me");
      if (r.s !== 200) return ekranVhod("vhod");
      S.me = r.j;
    }
    if (!S.me.active) return ekranIzteklo(S.me.message);
    if (await zarediDanni()) render();
  }
  setInterval(async () => {
    if (document.visibilityState !== "visible" || !S.me || !S.me.active || S.adminRejim) return;
    const a = document.activeElement;
    if (a && a.tagName === "INPUT") return; // не пречи на търсенето
    if (await zarediDanni()) render();
  }, 5 * 60 * 1000);

  start();
})();
