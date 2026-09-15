/* The Green Room · платформата (клиент). Всички данни идват от /api — сървърът
   решава кой какво вижда. Текстът от бота винаги минава през esc(). */
(() => {
  "use strict";
  const $app = document.getElementById("app");
  const S = { me: null, data: null, tab: "nachalo", sport: null, prog: "dnes", rezDen: null, admin: null, adminRejim: false };
  const IKONI = { football: "⚽", tennis: "🎾", basketball: "🏀", tabletennis: "🏓", volleyball: "🏐", hockey: "🏒",
    baseball: "⚾", mma: "🥊", boxing: "🥊", esports: "🎮", rugby: "🏉", amfootball: "🏈" };

  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

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
    d.className = "suobshtenie";
    d.textContent = t;
    document.body.appendChild(d);
    setTimeout(() => d.remove(), 2600);
  }

  /* ── дати ── */
  function denEt(den) {
    const d = S.data && S.data.dnes;
    if (!den) return "";
    if (d) {
      const t = new Date(d + "T12:00:00Z").getTime();
      const x = new Date(den + "T12:00:00Z").getTime();
      const r = Math.round((x - t) / 86400000);
      if (r === 0) return "Днес";
      if (r === 1) return "Утре";
      if (r === -1) return "Вчера";
    }
    const [y, m, dd] = den.split("-");
    return `${dd}.${m}`;
  }
  const datBg = (iso) => {
    if (!iso) return "—";
    try { return new Date(iso).toLocaleDateString("bg-BG", { timeZone: "Europe/Sofia", day: "2-digit", month: "2-digit", year: "numeric" }); }
    catch (e) { return String(iso).slice(0, 10); }
  };

  /* ── парчета ── */
  function zvezdi(n) { return n ? "★".repeat(Math.min(3, n)) + "☆".repeat(Math.max(0, 3 - n)) : ""; }

  function karta(k, rez) {
    const pr = k.procent;
    let znak = "";
    if (rez) znak = k.poznata === true ? '<span class="znak p" title="Позната">✓</span>' : k.poznata === false ? '<span class="znak n" title="Непозната">✗</span>' : '<span class="znak v" title="Без резултат">–</span>';
    return `<article class="karta">
      <div class="k-gore"><span>${IKONI[k.sport] || "•"}</span><span class="liga">${esc(k.sport_bg)}${k.liga ? " · " + esc(k.liga) : ""}</span>
        ${k.fish ? `<span class="fish">фиш ${esc(k.fish)}</span>` : ""}<span class="koga">${esc(denEt(k.den))}</span></div>
      <div class="k-mach">${esc(k.dom)} — ${esc(k.gost)}</div>
      <div class="k-dolu">${znak}<div><div class="k-et">${rez ? (k.rezultat ? "Резултат " + esc(k.rezultat) : "Нашата прогноза") : "Нашата прогноза"}</div>
        <div class="k-izbor">${esc(k.izbor)}</div></div>${k.koef ? `<div class="k-koef">${esc(k.koef.toFixed(2))}</div>` : ""}</div>
      ${!rez && pr ? `<div class="k-bar"><i style="width:${Math.max(4, Math.min(100, pr))}%"></i></div>
        <div class="k-uv"><span>Увереност ${esc(pr)}%</span><span class="zv">${zvezdi(k.zvezdi)}</span></div>` : ""}
    </article>`;
  }

  const IKONKI = {
    nachalo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 11 12 4l9 7v9h-6v-6H9v6H3z"/></svg>',
    sport: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/></svg>',
    prognozi: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 19V5M4 19h16M8 15l4-4 3 3 5-6"/></svg>',
    rezultati: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 12 3 3 5-6"/></svg>',
    novini: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 8h10M7 12h10M7 16h6"/></svg>',
    profil: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4.5-6 8-6s7 2 8 6"/></svg>',
  };
  const TABOVE = [["nachalo", "Начало"], ["sport", "Спорт"], ["prognozi", "Прогнози"], ["rezultati", "Резултати"], ["novini", "Новини"], ["profil", "Профил"]];

  function ramka(zaglavie, sadarzhanie) {
    const d = S.data;
    return `<div class="ramka">
      <header class="gorna"><img src="/logo.svg" alt=""><div class="marka"><small>THE</small>GREEN ROOM</div>
        <div class="dyasno">${d && d.fetched_utc ? "обновено " + esc(new Date(d.fetched_utc).toLocaleTimeString("bg-BG", { hour: "2-digit", minute: "2-digit" })) : ""}</div></header>
      ${zaglavie ? `<h1 class="zaglavie">${esc(zaglavie)}</h1>` : ""}
      ${sadarzhanie}
      <p class="podpis"><span class="ser">THE GREEN ROOM</span><br>По-добри играчи. По-умни решения. · 18+</p>
    </div>
    <div class="lenta"><nav aria-label="Основно меню">${TABOVE.map(([k, t]) =>
      `<button data-tab="${k}" ${S.tab === k ? 'aria-current="page"' : ""}>${IKONKI[k]}<span>${t}</span></button>`).join("")}</nav></div>`;
  }

  /* ── екраните ── */
  function prognoziZa(filtar, sport) {
    const d = S.data;
    if (!d) return [];
    let x = d.prognozi || [];
    if (sport) x = x.filter((k) => k.sport === sport);
    if (filtar === "dnes") x = x.filter((k) => k.den === d.dnes);
    else if (filtar === "utre") x = x.filter((k) => k.den > d.dnes);
    return x;
  }
  function brPoSport() {
    const m = {};
    for (const k of (S.data && S.data.prognozi) || []) m[k.sport] = (m[k.sport] || 0) + 1;
    return m;
  }

  function ekranNachalo() {
    const d = S.data || {};
    const dnes = prognoziZa("dnes").slice(0, 6);
    const br = brPoSport();
    const sp = (d.sportove || []).filter((s) => br[s.sport]);
    const o = d.obshto || {};
    return ramka("", `
      <section class="geroi"><h2>Големи мачове.<br>По-добри решения.</h2>
        <button class="btn" data-idi="prognozi">Виж прогнозите →</button></section>
      ${sp.length ? `<h2 class="podz">Спортове<button class="vizh" data-idi="sport">Всички</button></h2>
      <div class="chipove">${sp.map((s) => `<button class="chip" data-sport="${esc(s.sport)}">${IKONI[s.sport] || ""} ${esc(s.sport_bg)} · ${br[s.sport]}</button>`).join("")}</div>` : ""}
      <h2 class="podz">Днешни прогнози<button class="vizh" data-idi="prognozi">Виж всички</button></h2>
      ${dnes.length ? `<div class="karti">${dnes.map((k) => karta(k)).join("")}</div>` : '<p class="prazno">Днес още няма прогнози. Нови излизат през целия ден.</p>'}
      ${o.n ? `<h2 class="podz">Последните ${esc(o.dni)} дни</h2>
      <div class="tabla"><div class="plochka"><b>${esc(o.n)}</b><span>прогнози</span></div>
        <div class="plochka"><b>${esc(o.poznati)}</b><span>познати</span></div>
        <div class="plochka"><b>${esc(o.uspeh)}%</b><span>успеваемост</span></div></div>` : ""}`);
  }

  function ekranSport() {
    const d = S.data || {};
    const br = brPoSport();
    if (S.sport) {
      const s = S.sport;
      const ime = ((d.sportove || []).find((x) => x.sport === s) || {}).sport_bg || s;
      const k = prognoziZa("vsichki", s);
      const rez = (d.rezultati || []).filter((x) => x.sport === s).slice(0, 10);
      return ramka(`${IKONI[s] || ""} ${ime}`, `
        <div class="chipove"><button class="chip" data-sport="">← Всички спортове</button></div>
        <h2 class="podz">Прогнози</h2>
        ${k.length ? `<div class="karti">${k.map((x) => karta(x)).join("")}</div>` : '<p class="prazno">В момента няма прогнози за този спорт.</p>'}
        ${rez.length ? `<h2 class="podz">Последни резултати</h2><div class="karti">${rez.map((x) => karta(x, true)).join("")}</div>` : ""}`);
    }
    const sp = d.sportove || [];
    return ramka("Всички спортове", `<div class="spisyk">${sp.map((s) => `
      <button class="red-sport" data-sport="${esc(s.sport)}"><span class="ik">${IKONI[s.sport] || "•"}</span>
        <span><b>${esc(s.sport_bg)}</b><span class="pod">${br[s.sport] ? br[s.sport] + " прогнози" : "няма в момента"}</span></span><span class="str">›</span></button>`).join("")}</div>`);
  }

  function ekranPrognozi() {
    const k = prognoziZa(S.prog);
    const ch = [["dnes", "Днес"], ["utre", "Утре"], ["vsichki", "Всички"]];
    return ramka("Прогнози", `
      <div class="chipove">${ch.map(([v, t]) => `<button class="chip" data-prog="${v}" aria-pressed="${S.prog === v}">${t}</button>`).join("")}</div>
      <div class="karti" style="margin-top:12px">${k.length ? k.map((x) => karta(x)).join("") : '<p class="prazno">Няма прогнози за този избор.</p>'}</div>`);
  }

  function ekranRezultati() {
    const r = (S.data && S.data.rezultati) || [];
    const dni = [...new Set(r.map((x) => x.den))].slice(0, 8);
    if (!S.rezDen || !dni.includes(S.rezDen)) S.rezDen = dni[0] || null;
    const x = r.filter((k) => k.den === S.rezDen);
    const p = x.filter((k) => k.poznata === true).length;
    const n = x.filter((k) => k.poznata === true || k.poznata === false).length;
    return ramka("Резултати", dni.length ? `
      <div class="chipove">${dni.map((d) => `<button class="chip" data-rez="${esc(d)}" aria-pressed="${S.rezDen === d}">${esc(denEt(d))}</button>`).join("")}</div>
      ${n ? `<p class="tiho">Познати <b>${p}</b> от <b>${n}</b>${n ? ` · ${Math.round((100 * p) / n)}%` : ""}</p>` : ""}
      <div class="karti">${x.map((k) => karta(k, true)).join("")}</div>` : '<p class="prazno">Още няма оценени прогнози.</p>');
  }

  function ekranNovini() {
    const n = (S.data && S.data.novini) || [];
    return ramka("Новини", n.length ? `<div class="spisyk">${n.map((t) => `<div class="novina"><span class="t"></span><div>${esc(t)}</div></div>`).join("")}</div>`
      : '<p class="prazno">Няма нови новини в момента.</p>');
  }

  function ekranProfil() {
    const m = S.me || {};
    const st = m.status || "";
    const stBg = { active: "активен", expired: "изтекъл", locked: "заключен", admin: "администратор" }[st] || st;
    return ramka("Моят профил", `
      <div class="redove">
        <div><span>Имейл</span><span>${esc(m.email)}</span></div>
        <div><span>Състояние</span><span><span class="status ${esc(st)}">${esc(stBg)}</span></span></div>
        ${m.admin ? "" : `<div><span>Достъп до</span><span>${esc(datBg(m.access_until))}${m.days_left != null ? ` · ${esc(m.days_left)} дни` : ""}</span></div>`}
        <div><span>Регистриран</span><span>${esc(datBg(m.registered))}</span></div>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:14px">
        ${m.admin ? '<button class="btn" data-admin="1">Админ панел</button>' : ""}
        <button class="btn vtori" data-izhod="1">Изход</button></div>`);
  }

  /* ── админ ── */
  function ekranAdmin() {
    const a = S.admin;
    const spisyk = !a ? '<p class="tiho">Зарежда се…</p>' : a.error ? `<p class="greshka">${esc(a.error)}</p>` : `
      <p class="tiho">Профили: <b>${esc(a.count)}</b></p>
      <div class="spisyk">${a.users.map((u) => `
        <div class="potr"><div class="gore"><b>${esc(u.email)}</b><span class="status ${esc(u.status)}">${esc(u.status_bg)}</span></div>
          <div class="info">${u.admin ? "администратор" : `достъп до ${esc(datBg(u.access_until))}${u.days_left ? ` · ${esc(u.days_left)} дни` : ""}`}
            · регистриран ${esc(datBg(u.registered))} · последен вход ${esc(u.last_login ? datBg(u.last_login) : "—")}</div>
          ${u.admin ? "" : `<div class="deistvia">
            <button class="btn malak" data-a="extend" data-d="7" data-e="${esc(u.email)}">+7 дни</button>
            <button class="btn malak" data-a="extend" data-d="21" data-e="${esc(u.email)}">+21 дни</button>
            <button class="btn malak" data-a="extend" data-d="30" data-e="${esc(u.email)}">+30 дни</button>
            <button class="btn malak vtori" data-a="set_until" data-e="${esc(u.email)}">Точна дата</button>
            ${u.locked ? `<button class="btn malak vtori" data-a="unlock" data-e="${esc(u.email)}">Отключи</button>`
              : `<button class="btn malak vtori" data-a="lock" data-e="${esc(u.email)}">Заключи</button>`}
            <button class="btn malak vtori" data-a="set_password" data-e="${esc(u.email)}">Нова парола</button>
            <button class="btn malak zle" data-a="delete" data-e="${esc(u.email)}">Изтрий</button></div>`}
        </div>`).join("")}</div>`;
    return ramka("Админ панел", `
      <div class="chipove"><button class="chip" data-nazad="1">← Профил</button></div>
      <h2 class="podz">Нов профил</h2>
      <form class="forma-red" id="f-sazdai" autocomplete="off">
        <label class="pole" style="margin:0"><span>Имейл</span><input id="n-email" type="email" required></label>
        <label class="pole" style="margin:0"><span>Парола (поне 8)</span><input id="n-pass" type="text" minlength="8" required></label>
        <label class="pole" style="margin:0"><span>Дни</span><input id="n-dni" type="number" min="1" max="3650" value="21"></label>
        <button class="btn" type="submit">Създай</button>
      </form>
      <h2 class="podz">Всички профили<button class="vizh" data-opresni="1">Опресни</button></h2>
      ${spisyk}`);
  }

  async function zarediAdmin() {
    const r = await api("GET", "/api/admin/users");
    S.admin = r.s === 200 ? r.j : { error: r.j.error || "Грешка " + r.s };
    render();
  }

  async function adminDeistvie(action, email, extra) {
    const r = await api("POST", "/api/admin/user", Object.assign({ action, email }, extra || {}));
    if (r.s >= 200 && r.s < 300) { toast("Готово."); await zarediAdmin(); }
    else toast(r.j.error || "Грешка " + r.s);
  }

  /* ── вход / регистрация / изтекъл ── */
  function ekranVhod(rejim, greshka) {
    const reg = rejim === "reg";
    $app.innerHTML = `<main class="vhod"><div class="vhod-kutia">
      <img class="logo-g" src="/logo.svg" alt=""><div class="the">— THE —</div><div class="ime">GREEN ROOM</div>
      <h1>${reg ? "Създай профил" : "Добре дошъл!"}</h1>
      <p class="tiho">${reg ? "Новият профил има 21 дни достъп до всичко." : "Влез в своя свят на анализи и възможности."}</p>
      <form id="f-vhod" novalidate>
        <label class="pole"><span>Имейл</span><input id="v-email" type="email" autocomplete="email" required></label>
        <label class="pole"><span>Парола</span><input id="v-pass" type="password" autocomplete="${reg ? "new-password" : "current-password"}" minlength="8" required></label>
        <button class="btn" type="submit">${reg ? "Създай профил" : "Вход"}</button>
        <div class="greshka" role="alert">${esc(greshka || "")}</div>
      </form>
      <button class="vryzka" data-rejim="${reg ? "vhod" : "reg"}">${reg ? "Имам профил — вход" : "Създай нов акаунт"}</button>
      <p class="malko">По-добри играчи. По-умни решения. · 18+</p></div></main>`;
    const f = document.getElementById("f-vhod");
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("v-email").value.trim();
      const password = document.getElementById("v-pass").value;
      const b = f.querySelector("button");
      b.disabled = true;
      const r = await api("POST", reg ? "/api/register" : "/api/login", { email, password });
      b.disabled = false;
      if (r.s === 200 || r.s === 201) { S.me = r.j; await start(); }
      else ekranVhod(rejim, r.j.error || "Грешка " + r.s);
    });
    document.querySelector("[data-rejim]").addEventListener("click", (e) => ekranVhod(e.currentTarget.dataset.rejim));
  }

  function ekranIzteklo(msg) {
    $app.innerHTML = `<main class="vhod"><div class="vhod-kutia">
      <img class="logo-g" src="/logo.svg" alt=""><div class="the">— THE —</div><div class="ime">GREEN ROOM</div>
      <h1>Достъпът ти изтече</h1><p class="tiho">${esc(msg || "Достъпът ти изтече. Свържи се с администратора.")}</p>
      <button class="btn vtori" id="b-izhod">Изход</button></div></main>`;
    document.getElementById("b-izhod").addEventListener("click", izhod);
  }

  async function izhod() {
    await api("POST", "/api/logout", {});
    S.me = null; S.data = null; S.admin = null; S.adminRejim = false;
    ekranVhod("vhod");
  }

  /* ── основното ── */
  function render() {
    if (!S.me) return ekranVhod("vhod");
    const v = S.adminRejim ? ekranAdmin() : ({ nachalo: ekranNachalo, sport: ekranSport, prognozi: ekranPrognozi,
      rezultati: ekranRezultati, novini: ekranNovini, profil: ekranProfil }[S.tab] || ekranNachalo)();
    $app.innerHTML = v;
  }

  $app.addEventListener("click", async (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    const ds = t.dataset;
    if (ds.tab) { S.tab = ds.tab; S.adminRejim = false; if (ds.tab !== "sport") S.sport = null; render(); window.scrollTo(0, 0); }
    else if (ds.idi) { S.tab = ds.idi; S.sport = null; render(); window.scrollTo(0, 0); }
    else if (ds.sport !== undefined) { S.tab = "sport"; S.sport = ds.sport || null; render(); window.scrollTo(0, 0); }
    else if (ds.prog) { S.prog = ds.prog; render(); }
    else if (ds.rez) { S.rezDen = ds.rez; render(); }
    else if (ds.izhod) izhod();
    else if (ds.admin) { S.adminRejim = true; S.admin = null; render(); zarediAdmin(); }
    else if (ds.nazad) { S.adminRejim = false; S.tab = "profil"; render(); }
    else if (ds.opresni) zarediAdmin();
    else if (ds.a) {
      const email = ds.e;
      if (ds.a === "extend") return adminDeistvie("extend", email, { days: Number(ds.d) });
      if (ds.a === "set_until") {
        const v = prompt("Достъп до коя дата? (ГГГГ-ММ-ДД, напр. 2026-12-31)");
        if (v) return adminDeistvie("set_until", email, { until: v.trim() });
        return;
      }
      if (ds.a === "set_password") {
        const v = prompt("Нова парола за " + email + " (поне 8 знака):");
        if (v) return adminDeistvie("set_password", email, { password: v });
        return;
      }
      if (ds.a === "delete") { if (confirm("Да изтрия ли профила " + email + " завинаги?")) return adminDeistvie("delete", email); return; }
      return adminDeistvie(ds.a, email);
    }
  });

  $app.addEventListener("submit", async (e) => {
    if (e.target.id !== "f-sazdai") return;
    e.preventDefault();
    const email = document.getElementById("n-email").value.trim();
    const password = document.getElementById("n-pass").value;
    const days = Number(document.getElementById("n-dni").value) || 21;
    const r = await api("POST", "/api/admin/user", { action: "create", email, password, days });
    if (r.s === 201) { toast("Профилът е създаден."); zarediAdmin(); }
    else toast(r.j.error || "Грешка " + r.s);
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
    if (document.visibilityState === "visible" && S.me && S.me.active && !S.adminRejim) {
      if (await zarediDanni()) render();
    }
  }, 5 * 60 * 1000);

  start();
})();
