/* ─────────────────────────────────────────────────────────────
   The Green Room · платформата (клиент)
   Всички данни идват от /api — сървърът решава кой какво вижда.
   Всеки текст от бота минава през esc().
   ───────────────────────────────────────────────────────────── */
(() => {
  "use strict";
  const $app = document.getElementById("app");
  const TG = "https://t.me/green_picks_info_bot";      // съпорт ботът (отговаря + препраща към админа)
  const TGRUPA = "https://t.me/+_oYsaYaVKU80Yjc0";      // общността / канала в Telegram
  const S = {
    me: null, data: null, tab: "nachalo", sport: null, machK: null, machTab: "obzor", novSport: "", pkView: "expert", sportTab: "prog", progTab: "vsichki", progSport: "", progSort: "red", samoLyubimi: false, q: "",
    fishTab: "aktivni", rezDen: null, adminRejim: false, admin: null, aF: "vsichki", aQ: "", spQ: "", spTab: "vsichki",
    slip: [], suma: 10,
  };
  /* МОЯТ ФИШ — пази се в браузъра на клиента (нищо не отива на сървъра) */
  try {
    S.slip = JSON.parse(localStorage.getItem("gr_fish") || "[]") || [];
    S.suma = Number(localStorage.getItem("gr_suma")) || 10;
  } catch (e) { S.slip = []; }
  const pazi = () => { try { localStorage.setItem("gr_fish", JSON.stringify(S.slip)); localStorage.setItem("gr_suma", String(S.suma)); } catch (e) { /* личен режим */ } };
  const flag = (k, v) => { try { return v === undefined ? localStorage.getItem(k) : localStorage.setItem(k, v); } catch (e) { return null; } };
  // хвани реферал код от URL (?ref=XXXX) за евентуална регистрация
  try { const _rf = new URL(location.href).searchParams.get("ref"); if (_rf) flag("gr_ref", String(_rf).toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 12)); } catch (e) { /* игнор */ }
  /* ЛЮБИМИ мачове — също само в браузъра на клиента (нищо на сървъра) */
  try { S.lyubimi = new Set(JSON.parse(localStorage.getItem("gr_lyubimi") || "[]") || []); } catch (e) { S.lyubimi = new Set(); }
  const paziLyubimi = () => { try { localStorage.setItem("gr_lyubimi", JSON.stringify([...S.lyubimi])); } catch (e) { /* личен режим */ } };
  const vLyubim = (id) => S.lyubimi.has(id);
  const toggleLyubim = (id) => { S.lyubimi.has(id) ? S.lyubimi.delete(id) : S.lyubimi.add(id); paziLyubimi(); };
  /* брой любими, които СА в текущите данни (иначе броячът надценява с мъртви id-та) */
  const brLyubimi = () => { const ids = new Set(((S.data && S.data.prognozi) || []).map((k) => k.id)); let n = 0; for (const id of S.lyubimi) if (ids.has(id)) n++; return n; };
  /* НОВО от последното посещение — помни видяните прогнози (per браузър) */
  try { S.seen = new Set(JSON.parse(localStorage.getItem("gr_vidyani") || "[]") || []); } catch (e) { S.seen = new Set(); }
  const noviBroy = () => ((S.data && S.data.prognozi) || []).filter((k) => !S.seen.has(k.id)).length;
  // ── ГЕЙМИНГ: стрийк, броячи, значки, дневни мисии (localStorage) ──
  function dnesISO() { try { return new Date().toISOString().slice(0, 10); } catch (e) { return ""; } }
  function frizAkumulator() { return flag("gr_freeze") == null ? 1 : (Number(flag("gr_freeze")) || 0); }
  function updateStreak() {
    const t = dnesISO(); if (!t) return 0;
    const last = flag("gr_str_last"); let n = Number(flag("gr_str_n")) || 0;
    const oldN = n;
    S.strFroze = false; S.strUp = false;
    if (last !== t) {
      let y = ""; try { y = new Date(Date.now() - 864e5).toISOString().slice(0, 10); } catch (e) { y = ""; }
      if (last === y) { n = n + 1; }
      else if (last && n > 0) {
        const fr = frizAkumulator();
        if (fr > 0) { flag("gr_freeze", String(fr - 1)); n = n + 1; S.strFroze = true; } // щитът пази серията
        else { n = 1; }
      } else { n = 1; }
      // печели щит на всеки 7 дни
      if (n > 0 && n % 7 === 0) flag("gr_freeze", String(frizAkumulator() + 1));
      const oldMax = Number(flag("gr_str_max")) || 0;
      S.strMilestone = "";
      if (n > oldN) { // серията се качи днес → празничен момент
        S.strUp = true;
        if (n % 7 === 0) S.strMilestone = "🛡️ Серия от " + n + " дни — спечели щит!";
        else if (n > oldMax && n >= 3) S.strMilestone = "👑 Нов рекорд: " + n + " поредни дни!";
        else if (n === 3) S.strMilestone = "🔥 3 поредни дни!";
      }
      flag("gr_str_last", t); flag("gr_str_n", String(n));
      flag("gr_str_max", String(Math.max(n, Number(flag("gr_str_max")) || 0)));
    }
    return n;
  }
  function broy(k, inc) { let n = Number(flag("gr_c_" + k)) || 0; if (inc) { n += 1; flag("gr_c_" + k, String(n)); } return n; }
  function questDone(q) { return flag("gr_q_" + dnesISO() + "_" + q) === "1"; }
  function questSet(q) { if (!questDone(q)) { flag("gr_q_" + dnesISO() + "_" + q, "1"); } }
  function znachki() {
    const str = Number(flag("gr_str_max")) || 0;
    return [
      { ik: "🎯", t: "Първи залог", ok: broy("fish") >= 1 },
      { ik: "🔍", t: "Изследовател", ok: broy("mach") >= 5 },
      { ik: "🎲", t: "Сценарист", ok: broy("scen") >= 1 },
      { ik: "🔥", t: "3 дни поред", ok: str >= 3 },
      { ik: "👑", t: "7 дни поред", ok: str >= 7 },
      { ik: "💎", t: "14 дни поред", ok: str >= 14 },
    ];
  }
  function streakZnak() { const n = S.streak || 0; return n >= 1 ? `<span class="streak-znak" title="${n} поредни дни"><i>🔥</i>${n}</span>` : ""; }
  // ── ПЕРСОНАЛИЗАЦИЯ: следени отбори ──
  function sledeni() { try { return new Set(JSON.parse(flag("gr_teams") || "[]") || []); } catch (e) { return new Set(); } }
  function slediOtbor(ime) { const s = sledeni(); if (s.has(ime)) s.delete(ime); else s.add(ime); try { flag("gr_teams", JSON.stringify([...s].slice(0, 60))); } catch (e) { /* игнор */ } }
  function moiteOtboriSekcia(d) {
    const s = sledeni(); if (!s.size) return "";
    const mach = (d.prognozi || []).filter((p) => p && p.dom && (s.has(p.dom) || s.has(p.gost))).slice(0, 4);
    if (!mach.length) return "";
    return `<section class="sekcia"><header><h2>Моите отбори</h2><span class="den-badge">${s.size} следени</span></header>
      <div class="karti kol">${mach.map(kartaPrognoza).join("")}</div></section>`;
  }
  // ── ФОРМАТ НА КОЕФИЦИЕНТА (десетичен / дробен / американски / имплиц. %) ──
  function koefFmt() { const f = flag("gr_koef_fmt"); return ["dec", "frac", "us", "imp"].indexOf(f) >= 0 ? f : "dec"; }
  function nod(a, b) { return b ? nod(b, a % b) : a; }
  function fmtKoef(k, fmt) {
    k = Number(k); if (!(k > 1)) return "—";
    fmt = fmt || koefFmt();
    if (fmt === "imp") return Math.round(100 / k) + "%";
    if (fmt === "us") { const v = k >= 2 ? Math.round((k - 1) * 100) : -Math.round(100 / (k - 1)); return (v > 0 ? "+" : "") + v; }
    if (fmt === "frac") { let num = Math.round((k - 1) * 100), den = 100; const g = nod(num, den) || 1; num /= g; den /= g; return num + "/" + den; }
    return k.toFixed(2);
  }
  function prilozhiRezhim() {
    try {
      document.body.classList.toggle("spoiler", flag("gr_spoiler") === "1");
      document.body.classList.toggle("dostap", flag("gr_dostap") === "1");
    } catch (e) { /* личен режим */ }
  }
  // ── PUSH ИЗВЕСТИЯ (включване от клиента) ──
  function urlB64ToUint8(base64) {
    const pad = "=".repeat((4 - base64.length % 4) % 4);
    const b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(b64), arr = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }
  async function vklyuchiIzvestiya() {
    try {
      if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) { toast("Устройството не поддържа известия."); return; }
      const perm = await Notification.requestPermission();
      if (perm !== "granted") { toast("Известията са отказани от устройството."); return; }
      const kr = await api("GET", "/api/push-key");
      const key = kr.j && kr.j.key;
      if (!key) { flag("gr_push", "1"); toast("Готово — известията ще тръгнат скоро."); return render(); }
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8(key) });
      const r = await api("POST", "/api/push-abonirai", { sub: sub.toJSON ? sub.toJSON() : sub });
      if (r.s === 200) { flag("gr_push", "1"); toast("Известията са включени!"); render(); }
      else toast("Известията не се включиха.");
    } catch (e) { toast("Известията не се включиха."); }
  }
  // ── СПОДЕЛИМА КАРТА на пик (canvas PNG, брандирана) ──
  function spodeliPik(k) {
    if (!k) return;
    try {
      const W = 1080, H = 1080, c = document.createElement("canvas"); c.width = W; c.height = H;
      const x = c.getContext("2d"), mid = W / 2;
      const g = x.createLinearGradient(0, 0, 0, H); g.addColorStop(0, "#0b3021"); g.addColorStop(1, "#04130d");
      x.fillStyle = g; x.fillRect(0, 0, W, H);
      x.strokeStyle = "#d6b45a"; x.lineWidth = 5; x.strokeRect(46, 46, W - 92, H - 92);
      x.textAlign = "center";
      x.fillStyle = "#d6b45a"; x.font = "700 46px Georgia, 'Times New Roman', serif"; x.fillText("THE GREEN ROOM", mid, 150);
      x.fillStyle = "#8fa89a"; x.font = "500 27px Arial, sans-serif"; x.fillText("ПРОГНОЗА ЗА ДЕНЯ", mid, 196);
      const kratko = (s) => { s = String(s || ""); return s.length > 20 ? s.slice(0, 19) + "…" : s; };
      x.fillStyle = "#eaf2ec"; x.font = "700 58px Georgia, serif"; x.fillText(kratko(k.dom), mid, 370);
      x.fillStyle = "#8fa89a"; x.font = "500 32px Arial, sans-serif"; x.fillText("срещу", mid, 425);
      x.fillStyle = "#eaf2ec"; x.font = "700 58px Georgia, serif"; x.fillText(kratko(k.gost), mid, 495);
      x.fillStyle = "#1fc17e"; x.font = "700 66px Georgia, serif"; x.fillText(kratko(izborTxt(k.izbor)), mid, 680);
      if (k.koef) { x.fillStyle = "#d6b45a"; x.font = "700 104px Georgia, serif"; x.fillText(Number(k.koef).toFixed(2), mid, 820); x.fillStyle = "#8fa89a"; x.font = "500 30px Arial, sans-serif"; x.fillText("КОЕФИЦИЕНТ", mid, 862); }
      if (k.procent) { x.fillStyle = "#eaf2ec"; x.font = "600 40px Arial, sans-serif"; x.fillText("Увереност " + k.procent + "%", mid, 950); }
      x.fillStyle = "#5a6b60"; x.font = "500 26px Arial, sans-serif"; x.fillText("thegreenroom-bg.netlify.app · Играй отговорно 18+", mid, 1015);
      c.toBlob((blob) => {
        if (!blob) { toast("Не се създаде картата."); return; }
        const file = (typeof File !== "undefined") ? new File([blob], "greenroom-pik.png", { type: "image/png" }) : null;
        if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
          navigator.share({ files: [file], title: "The Green Room" }).catch(() => {});
        } else {
          const url = URL.createObjectURL(blob), a = document.createElement("a");
          a.href = url; a.download = "greenroom-pik.png"; document.body.appendChild(a); a.click(); a.remove();
          setTimeout(() => URL.revokeObjectURL(url), 8000);
        }
        toast("Картата е готова — сподели я!");
      }, "image/png");
    } catch (e) { toast("Не се създаде картата."); }
  }
  function dnevniMisii() {
    const q = [{ k: "fish", t: "Добави пик във фиша" }, { k: "scen", t: "Пробвай Сценарии" }, { k: "val", t: "Виж Стойност днес" }];
    const done = q.filter((x) => questDone(x.k)).length;
    return `<section class="misii"><div class="misii-h"><b>Дневни мисии</b><span>${done}/${q.length}${done === q.length ? " ✓" : ""}</span></div>
      <div class="misii-red">${q.map((x) => `<button class="misia${questDone(x.k) ? " done" : ""}" data-idi="prognozi"><span class="mi-tik">${questDone(x.k) ? "✓" : ""}</span>${esc(x.t)}</button>`).join("")}</div></section>`;
  }
  const MISII_K = ["fish", "scen", "val"];
  function proveriMisii() {
    try {
      if (!MISII_K.every(questDone)) return;
      const den = dnesISO();
      if (flag("gr_misii_praz") === den) return; // веднъж на ден
      flag("gr_misii_praz", den);
      flag("gr_freeze", String(frizAkumulator() + 1)); // награда: +1 щит за серията
      const el = $app.querySelector(".misii") || $app.querySelector(".streak-znak");
      if (el) praznik(el);
      setTimeout(() => toast("Дневните мисии са готови ✓ — спечели щит 🛡️"), 300);
    } catch (e) { /* без развръзка */ }
  }
  function nastroykiSekcia() {
    const kf = koefFmt();
    const koefi = [["dec", "Десетичен"], ["frac", "Дробен"], ["us", "US"], ["imp", "Вероятност"]];
    const spoil = flag("gr_spoiler") === "1", dostap = flag("gr_dostap") === "1", push = flag("gr_push") === "1";
    return `<section class="sekcia"><header><h2>Настройки</h2></header>
      <div class="nastr">
        <button class="nastr-toggle${push ? " on" : ""}" data-izvestiya="1"><span>Известия<small>Тип на деня · steam-скок · сверен резултат</small></span><i class="sw"></i></button>
        <div class="nastr-red"><span>Формат на коефициента</span><div class="bank-chip-red">${koefi.map(([f, t]) => `<button class="bchip${kf === f ? " on" : ""}" data-koeffmt="${f}">${t}</button>`).join("")}</div></div>
        <button class="nastr-toggle${spoil ? " on" : ""}" data-toggle="gr_spoiler"><span>Без спойлери<small>Замъгли резултатите до докосване</small></span><i class="sw"></i></button>
        <button class="nastr-toggle${dostap ? " on" : ""}" data-toggle="gr_dostap"><span>Достъпен режим<small>По-висок контраст, не само цвят</small></span><i class="sw"></i></button>
      </div></section>`;
  }
  function znachkiSekcia() {
    const z = znachki(), ok = z.filter((x) => x.ok).length, fr = frizAkumulator();
    return `<section class="sekcia"><header><h2>Постижения</h2><span class="den-badge">${ok}/${z.length}</span></header>
      <div class="friz-red"><span class="friz-ik">🛡️</span><div><b>${fr}</b> ${fr === 1 ? "щит" : "щита"} за серията${S.strFroze ? ` · <span class="friz-froze">серията ти беше защитена днес</span>` : ` · пазят серията ти при пропуснат ден`}</div></div>
      <div class="znachki-grid">${z.map((x) => `<div class="znachka-k${x.ok ? " ok" : ""}"><span class="zn-ik">${x.ik}</span><b>${esc(x.t)}</b></div>`).join("")}</div></section>`;
  }
  const markSeen = () => {
    const cur = new Set(((S.data && S.data.prognozi) || []).map((k) => k.id));
    for (const id of cur) S.seen.add(id);
    S.seen = new Set([...S.seen].filter((id) => cur.has(id)));
    try { localStorage.setItem("gr_vidyani", JSON.stringify([...S.seen])); } catch (e) { /* личен режим */ }
    S.novi = 0;
  };
  const vFisha = (id) => S.slip.some((x) => x.id === id);
  const slipKoef = () => (S.slip.length && S.slip.every((x) => x.koef > 1)
    ? Math.round(S.slip.reduce((a, x) => a * x.koef, 1) * 100) / 100 : null);

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
    live: '<circle cx="12" cy="12" r="2.1"/><path d="M8.3 8.3a5.2 5.2 0 000 7.4M15.7 8.3a5.2 5.2 0 010 7.4M5.5 5.5a9 9 0 000 13M18.5 5.5a9 9 0 010 13"/>',
    multi: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.4"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.4"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.4"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.4"/>',
    zvanec: '<path d="M18 8.5a6 6 0 10-12 0c0 6-2.5 7.5-2.5 7.5h17S18 14.5 18 8.5z"/><path d="M10 19.5a2.2 2.2 0 004 0"/>',
    puls: '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>',
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
    zvezda: '<path d="M12 3.1l2.55 5.72 6.2.62-4.64 4.16 1.36 6.09L12 16.9l-5.43 2.79 1.36-6.09L3.29 9.44l6.2-.62z"/>',
    diamant: '<path d="M6 3h12l3.2 5.2L12 21 2.8 8.2z"/><path d="M2.8 8.2h18.4M9.2 3 7 8.2l5 12.8 5-12.8-2.2-5.2M12 8.2v12.8"/>',
    spodeliik: '<circle cx="18" cy="5" r="2.6"/><circle cx="6" cy="12" r="2.6"/><circle cx="18" cy="19" r="2.6"/><path d="m8.3 10.7 7.4-4.3M8.3 13.3l7.4 4.3"/>',
    tg: '<path d="M21.5 4.3 2.9 11.4c-.9.3-.9 1.6.1 1.9l4.6 1.4 1.8 5.4c.2.7 1.1.9 1.6.3l2.4-2.6 4.6 3.4c.6.4 1.4.1 1.6-.6L22.7 5.4c.2-.8-.5-1.4-1.2-1.1z"/><path d="m7.6 14.7 9-6.2-6.9 6.7"/>',
    obshtnost: '<circle cx="9" cy="9" r="3"/><path d="M3.5 19c.6-3 3-4.8 5.5-4.8s4.9 1.8 5.5 4.8"/><circle cx="17" cy="8" r="2.2"/><path d="M15.5 13.6c2.2.2 3.9 1.7 4.5 4"/>',
  };
  const ico = (n, cls = "ico") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICO[n] || ""}</svg>`;
  const TOPKA = '<svg viewBox="0 0 24 24" aria-hidden="true">' + SVG.football + "</svg>";

  const NAV = [["nachalo", "Начало"], ["sport", "Спорт"], ["live", "На живо"], ["prognozi", "Прогнози"], ["novini", "Новини"], ["profil", "Профил"]];
  // Спортната библиотека — образователно съдържание по спорт (по макетите).
  const LIB_HERO = { football: "lib-futbol", basketball: "lib-basket", tennis: "lib-tenis", mma: "lib-mma", boxing: "lib-boks", hockey: "lib-hokey", volleyball: "lib-voleybol", tabletennis: "lib-tenis-masa", baseball: "lib-beysbol", esports: "lib-esport", rugby: "lib-ragbi", amfootball: "lib-am-futbol" };
  const SPORT_LIB = {
    football: { pod: "История · Правила · Легенди · Постижения", kak: "11 срещу 11 · два тайма по 45 минути", kakP: "Побеждава отборът с повече голове. Засадата и нарушенията менят позиционирането.", ist: ["1930", "Първо световно първенство", "Първенството в Уругвай слага началото на модерния футбол."], mom: ["Пеле и Бразилия", "Пет световни титли · Пеле е шампион през 1958, 1962 и 1970."], izt: "fifa.com" },
    basketball: { pod: "История · Правила · Легенди · Постижения", kak: "5 срещу 5 · точки 1, 2 и 3", kakP: "Дрибъл, пас и стрелба. Владенията имат времеви лимит; ритъмът е бърз.", ist: ["1891", "Джеймс Нейсмит създава играта", "Родена в спортна зала в Спрингфийлд, Масачузетс."], mom: ["Dream Team", "Олимпийско злато в Барселона 1992 — Джордан, Бърд и Меджик."], izt: "fiba.basketball" },
    tennis: { pod: "История · Правила · Легенди · Постижения", kak: "Точки → геймове → сетове", kakP: "Сервисът започва разиграването. Форматът на тайбрека зависи от турнира.", ist: ["1968", "Начало на Open Era", "Професионалистите влизат в турнирите от Големия шлем."], mom: ["Джокович · Париж 2024", "Кариерен Golden Slam — четирите мейджъра и олимпийско злато."], izt: "itftennis.com" },
    mma: { pod: "История · Правила · Легенди · Постижения", kak: "Удари · борба · събмишъни", kakP: "Победа с нокаут, събмишън или съдийско решение. Правилата зависят от организацията.", ist: ["1993", "Първият UFC турнир", "Различните стилове се срещат в осмоъгълника за пръв път."], mom: ["Royce Gracie · UFC 1", "Три победи в една вечер доказват бразилското джу-джицу."], izt: "ufc.com" },
    boxing: { pod: "История · Правила · Легенди · Постижения", kak: "Рундове · категории · съдийски точки", kakP: "Само удари с ръце в позволените зони. Нокаут или съдийско решение определя победителя.", ist: ["1960", "Олимпийски турнир в Рим", "Сцена за раждането на легенди."], mom: ["Мохамед Али", "Злато в Рим 1960 като Касиус Клей — после легенда."], izt: "—" },
    hockey: { pod: "История · Правила · Легенди · Постижения", kak: "5 полеви + вратар · шайба · лед", kakP: "Смени в движение, силова игра и числено предимство. Повече голове печели.", ist: ["1875", "Организиран мач в Монреал", "Първият закрит мач слага началото на играта."], mom: ["Ванкувър 2010 · Кросби", "Златният гол в продължение за Канада."], izt: "iihf.com" },
    volleyball: { pod: "История · Правила · Легенди · Постижения", kak: "6 срещу 6 · до 25 точки · най-добър от 5 сета", kakP: "Три докосвания на страна, ротация при спечелен сервис, петият сет е до 15. Всяко разиграване носи точка.", ist: ["1895", "Уилям Морган измисля играта", "В Холиоук, Масачузетс — по-мек отборен спорт от баскетбола."], mom: ["България · Световно 2018", "България е съдомакин на мъжкото Световно първенство — силна волейболна традиция."], izt: "fivb.com" },
    tabletennis: { pod: "История · Правила · Легенди · Постижения", kak: "1 срещу 1 · до 11 точки · най-добър от 5 или 7 гейма", kakP: "Сервисът се сменя на всеки две точки, геймът е до 11 с преднина от два. Ръбът на масата брои.", ist: ["1988", "Олимпийски дебют в Сеул", "Роден в Англия като салонна игра в края на XIX век, влиза в олимпийската програма."], mom: ["Господството на Китай", "От 80-те насам Китай владее световния и олимпийския елит на спорта."], izt: "ittf.com" },
    baseball: { pod: "История · Правила · Легенди · Постижения", kak: "9 срещу 9 · 9 ининга · удар и обиколка на базите", kakP: "Питчърът хвърля, батерът удря и тича по четирите бази; обиколка е рън. Три страйка са аут, три аута сменят страните.", ist: ["1845", "Правилата на Knickerbocker", "Александър Картрайт кодифицира играта в Ню Йорк — основата на модерния бейзбол."], mom: ["MLB и NPB", "Северноамериканската MLB и японската NPB са двете най-силни лиги в света."], izt: "mlb.com" },
    esports: { pod: "История · Правила · Легенди · Постижения", kak: "5 срещу 5 · CS2 · League of Legends · Dota 2", kakP: "Отбори се борят на дигитална арена за карти или обекти. Форматът е серия от карти; печели първият до нужните победи.", ist: ["1999", "Counter-Strike се ражда", "Мод на Half-Life прераства в най-гледаната тактическа стрелба; LoL идва през 2009."], mom: ["The International", "Наградните фондове на Dota 2 надхвърлят десетки милиони долари — връх на професионалния еспорт."], izt: "hltv.org" },
    rugby: { pod: "История · Правила · Легенди · Постижения", kak: "15 срещу 15 · тъч даун (try) = 5 точки", kakP: "Топката се подава само назад, напредъкът е с бягане и ритници. Try, гол след try и дузпа носят точки.", ist: ["1823", "Легендата за Уилям Уеб Елис", "По преданието ученик в училището Rugby грабва топката с ръце — оттам тръгва играта."], mom: ["Световна купа от 1987", "Трофеят носи името на Уеб Елис; Нова Зеландия е сред най-титулуваните."], izt: "world.rugby" },
    amfootball: { pod: "История · Правила · Легенди · Постижения", kak: "11 срещу 11 · даунове · тъчдаун = 6 точки", kakP: "Атаката има четири опита да мине 10 ярда. Тъчдаун, гол-поле и точка след това градят резултата.", ist: ["1869", "Първи университетски мач", "Rutgers срещу Princeton поставя началото; NFL се ражда през 1920."], mom: ["Супербоул", "Финалът на NFL е най-гледаното спортно събитие в САЩ всяка година."], izt: "nfl.com" },
  };

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
  /* лека хаптика + празничен изблик на геймифициран връх (турнир/стрийк). Тих при reduced-motion. */
  function haptika(ms) { try { if (navigator.vibrate) navigator.vibrate(ms); } catch (e) { /* без вибрация */ } }
  function praznik(el) {
    haptika(16);
    try {
      if (!el || !el.getBoundingClientRect || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const r = el.getBoundingClientRect();
      const wrap = document.createElement("div"); wrap.className = "praznik";
      wrap.style.left = (r.left + r.width / 2) + "px"; wrap.style.top = (r.top + r.height / 2) + "px";
      const boi = ["#e3c574", "#ecd28c", "#1fc17e", "#2fce89"];
      for (let i = 0; i < 14; i++) {
        const s = document.createElement("i");
        const ang = (Math.PI * 2 * i) / 14 + Math.random() * 0.5, dist = 32 + Math.random() * 38;
        s.style.setProperty("--dx", (Math.cos(ang) * dist).toFixed(1) + "px");
        s.style.setProperty("--dy", (Math.sin(ang) * dist).toFixed(1) + "px");
        s.style.background = boi[i % boi.length]; s.style.color = boi[i % boi.length];
        s.style.animationDelay = Math.round(Math.random() * 40) + "ms";
        wrap.appendChild(s);
      }
      document.body.appendChild(wrap);
      setTimeout(() => wrap.remove(), 950);
    } catch (e) { /* без празник */ }
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
  const evNa = (k) => (k.procent && k.koef) ? (k.procent / 100) * k.koef - 1 : null; // очаквана стойност на пик
  /* Риск от увереността/звездите (по MASTER PLAN: Risk LOW/MED/HIGH) */
  const riskNiv = (k) => {
    const p = k.procent || 0, z = k.zvezdi || 0;
    if (p >= 72 || z >= 3) return { t: "Нисък риск", c: "nis" };
    if (p >= 60 || z === 2) return { t: "Среден риск", c: "sred" };
    return { t: "Висок риск", c: "vis" };
  };

  /* ── парчета ── */
  function kartaPrognoza(k) {
    const pr = k.procent;
    const ev = (pr && k.koef) ? (pr / 100) * k.koef - 1 : null;
    const evChip = ev != null && ev >= 0.02 ? `<span class="ev-chip" title="Коефициентът е над реалната ни вероятност">Стойност +${(ev * 100).toFixed(0)}%</span>` : "";
    return `<article class="pk${evChip ? " ima-stoynost" : ""}">
      <div class="pk-h">${ik(k.sport, "ik s")}<span class="liga">${esc(k.sport_bg)}${k.liga ? " · " + esc(k.liga) : ""}</span>
        <span class="den">${esc(denEt(k.den))}</span>
        <button class="pk-zv" data-zvezda="${esc(k.id)}" aria-pressed="${vLyubim(k.id)}" aria-label="${vLyubim(k.id) ? "Премахни от любими" : "Добави в любими"}" title="Любими">${ico("zvezda", "zv-ik")}</button></div>
      <div class="pk-mach"><div class="pk-tim">${ekip(k.dom)}<span>${esc(k.dom)}</span></div><div class="pk-vs">VS</div>
        <div class="pk-tim d">${ekip(k.gost)}<span>${esc(k.gost)}</span></div></div>
      <div class="pk-izbor"><div class="pk-izb"><small>Нашата прогноза</small><b>${esc(izborTxt(k.izbor))}</b></div>
        ${k.koef ? `<div class="pk-koef"><small>Коеф.</small><b>${esc(fmtKoef(k.koef))}</b></div>`
          : '<div class="pk-koef bez"><small>Коеф.</small><b>—</b></div>'}
        ${pr ? `<div class="pk-ring" style="--p:${esc(pr)}"><b>${esc(pr)}%</b><small>увереност</small></div>` : ""}</div>
      ${pr || k.zvezdi || evChip ? `<div class="pk-dolen">${pr ? `<div class="risk-dots ${riskNiv(k).c}"><i></i><i></i><i></i></div><small class="risk-lab">${riskNiv(k).t}</small>` : ""}${evChip}${k.zvezdi ? `<span class="zv" aria-label="${esc(k.zvezdi)} звезди">${zvezdi(k.zvezdi)}</span>` : ""}</div>` : ""}
      ${k.zashto ? `<p class="pk-zashto"><b>Защо?</b> ${esc(k.zashto)}</p>` : ""}
      ${k.koef ? `<button class="pk-dob" data-slip="${esc(k.id)}" aria-pressed="${vFisha(k.id)}">${vFisha(k.id) ? "✓ Във фиша" : "+ Добави във фиша"}</button>` : ""}
    </article>`;
  }
  // Голямата „мач на деня" карта с GAME PULSE (напрежение), изведено от увереност+звезди.
  function kartaGeroiMach(k) {
    const pr = k.procent || 0;
    const puls = Math.max(28, Math.min(99, Math.round(pr * 0.72 + (k.zvezdi || 0) * 9 + 20)));
    const napr = puls >= 82 ? "силно напрежение" : puls >= 62 ? "голям интерес" : "равностоен мач";
    return `<button class="mach-feat" data-mach="${esc(k.id)}">
      <div class="mf-top">${ik(k.sport, "ik s")}<span class="mf-liga">${esc(k.sport_bg)}${k.liga ? " · " + esc(k.liga) : ""}</span><span class="den">${esc(denEt(k.den))}</span></div>
      <div class="mf-body">
        <div class="mf-teams">
          <div class="mf-tim">${ekip(k.dom)}<b>${esc(k.dom)}</b></div>
          <span class="mf-vs">VS</span>
          <div class="mf-tim">${ekip(k.gost)}<b>${esc(k.gost)}</b></div>
        </div>
        <div class="mf-pulse" style="--p:${puls}"><span class="mf-lab">Напрежение</span><b>${puls}</b><span class="mf-napr">${esc(napr)}</span></div>
      </div>
      <div class="mf-cta">Влез в стаята на мача ${ico("str")}</div>
    </button>`;
  }
  const znak = (p) => (p === true ? '<span class="znak p">✓ Спечелена</span>' : p === false ? '<span class="znak n">✗ Загубена</span>' : '<span class="znak v">—</span>');
  function kartaRezultat(k) {
    const sk = String(k.rezultat || "").split(/[:\-–]/).map((x) => x.trim());
    const dva = sk.length === 2;
    return `<article class="rz">
      <div class="rz-t">${ekip(k.dom)}<span>${esc(k.dom)}</span></div><div class="rz-sk">${dva ? esc(sk[0]) : ""}</div>
      <div class="rz-t">${ekip(k.gost)}<span>${esc(k.gost)}</span></div><div class="rz-sk">${dva ? esc(sk[1]) : esc(k.rezultat || "")}</div>
      <div class="rz-dolu"><span>Прогноза: <b>${esc(izborTxt(k.izbor))}</b>${k.koef ? ` · ${esc(fmtKoef(k.koef))}` : ""}</span>${znak(k.poznata)}</div>
    </article>`;
  }
  // „Как мина вчера" — момент на връщане, веднъж на ден, най-горе на Начало
  function vcheraKart(d) {
    if (!d || !d.dnes) return "";
    if (flag("gr_vchera") === d.dnes) return ""; // вече видяно/скрито днес
    let vch = ""; try { vch = new Date(new Date(d.dnes + "T12:00:00Z").getTime() - 864e5).toISOString().slice(0, 10); } catch (e) { return ""; }
    const rez = (d.rezultati || []).filter((r) => r.den === vch && (r.poznata === true || r.poznata === false));
    if (rez.length < 2) return ""; // без достатъчно оценени — не показвай
    const poz = rez.filter((r) => r.poznata === true).length, obsht = rez.length;
    const proc = Math.round(100 * poz / obsht);
    const dobre = proc >= 55;
    const dots = rez.slice(0, 14).map((r) => `<i class="${r.poznata ? "w" : "l"}"></i>`).join("");
    const str = S.streak || 0;
    return `<div class="vchera${dobre ? " dobre" : ""}">
      <button class="vchera-x" data-vchera-x="1" aria-label="Скрий">×</button>
      <div class="vchera-h"><span class="vchera-ik">${dobre ? "📈" : "📊"}</span><b>${dobre ? "Силен вчерашен ден" : "Вчера — честно, без разкрасяване"}</b></div>
      <div class="vchera-red"><div class="vchera-broy"><b data-count="${poz}">${poz}</b><span>от ${obsht} познати</span></div>
        <div class="vchera-proc"><b data-count="${proc}" data-suf="%">${proc}%</b><small>успеваемост</small></div>
        <div class="vchera-dots" aria-label="вчерашни изходи">${dots}</div></div>
      ${str >= 1 ? `<div class="vchera-streak">🔥 <b>${str}</b> ${str === 1 ? "пореден ден" : "поредни дни"} — продължи ги днес</div>` : ""}
      <div class="vchera-akcii"><button class="vchera-vij" data-idi="prognozi">Виж днешните прогнози ${ico("str")}</button>
        <button class="vchera-vij2" data-idi="rezultati">Всички резултати</button></div>
    </div>`;
  }
  function kartaFish(f) {
    const stT = { poznat: "Спечелен", nepoznat: "Загубен", v_igra: "В игра" }[f.status] || "";
    return `<article class="fs">
      <header><b>Фиш №${esc(f.nomer)}</b><span class="den">${esc(denDylag(f.den))}</span><span class="st ${esc(f.status)}">${stT}</span></header>
      <ol>${f.kraka.map((k) => `<li>${ik(k.sport, "ik s")}<span class="m">${esc(k.dom)} — ${esc(k.gost)}</span>
        <span class="k">${k.koef ? esc(fmtKoef(k.koef)) : "—"}${k.poznata === true || k.poznata === false ? znak(k.poznata) : ""}</span>
        <span class="i">${esc(izborTxt(k.izbor))}${k.rezultat ? ` · ${esc(k.rezultat)}` : ""}</span></li>`).join("")}</ol>
      <footer><span>${esc(f.kraka.length)} събития · общ коефициент</span><b>${f.koef ? esc(f.koef.toFixed(2)) : "—"}</b></footer>
    </article>`;
  }

  /* ── рамката ── */
  function ramka(glava, telo) {
    const m = S.me || {};
    const nav = (cls) => NAV.map(([k, t]) => `<button data-tab="${k}" ${S.tab === k && !S.adminRejim ? 'aria-current="page"' : ""}>${ico(k)}<span>${t}</span>${k === "prognozi" && S.novi > 0 ? `<span class="nav-nov" aria-label="${S.novi} нови прогнози">${S.novi > 9 ? "9+" : S.novi}</span>` : ""}</button>`).join("");
    return `<div class="app">
      <aside class="side"><div class="marka"><img src="/logo.svg" alt=""><div class="ime"><small>THE</small>GREEN ROOM</div></div>
        <nav aria-label="Основно меню">${nav()}</nav>
        <div class="az"><span class="av">${esc(inicial(m.email))}</span><div><b>${esc(m.email || "")}</b><span>${esc(statusTxt(m))}</span></div></div></aside>
      <div>
        <div class="glaven">
          <header class="gore"><div class="marka"><img src="/logo.svg" alt=""><div class="ime"><small>THE</small>GREEN ROOM</div></div>
            ${svezhoHtml()}${streakZnak()}
            <button class="glav-tarsi" data-cmdk="1" aria-label="Търсене (Ctrl+K)" title="Търсене">${ico("tarsi")}</button>
            <button class="bell" data-tab="profil" aria-label="Известия и профил">${ico("zvanec")}<i class="bell-dot"></i></button></header>
          ${glava ? `<div class="glava"><h1>${esc(glava[0])}</h1>${glava[1] ? `<p>${esc(glava[1])}</p>` : ""}</div>` : ""}
          ${telo}
          <footer class="podpis"><div class="s">THE GREEN ROOM</div>По-добри играчи. По-умни решения. · 18+</footer>
        </div>
      </div>
      <nav class="dolu" aria-label="Основно меню"><div class="v">${nav()}</div></nav>
      ${S.slip.length && !(S.tab === "fishove" && S.fishTab === "moi") && !S.adminRejim ? `<button class="slip-pill" data-moi="1">${ico("fishove")}Моят фиш · ${S.slip.length}${slipKoef() ? `<b>${esc(slipKoef().toFixed(2))}</b>` : ""}</button>` : ""}
    </div>`;
  }
  function svezhoHtml() {
    const d = S.data;
    let t = "на линия";
    if (d && d.fetched_utc) {
      const min = Math.round((Date.now() - new Date(d.fetched_utc)) / 60000);
      t = min <= 1 ? "току-що" : min < 60 ? "преди " + min + " мин" : "преди " + Math.round(min / 60) + " ч";
    }
    return `<button class="svezhо${S.svezhVarti ? " varti" : ""}" data-svezhi="1" aria-label="Обнови данните" title="Обнови"><span class="tochka"></span>${esc(t)}</button>`;
  }
  function statusTxt(m) {
    if (!m) return "";
    if (m.admin) return "Администратор 👑";
    if (m.status === "active") return `Активен · ${m.days_left} ${m.days_left === 1 ? "ден" : "дни"}`;
    return { expired: "Изтекъл", locked: "Заключен" }[m.status] || "";
  }

  function kartaZhivo(z) {
    const et = z.status === "HT" ? "Почивка" : (z.minuta != null ? z.minuta + "'" : "LIVE");
    return `<article class="rz zhivo-k">
      <div class="rz-t">${ekip(z.dom)}<span>${esc(z.dom)}</span></div><div class="rz-sk">${esc(z.gol_dom != null ? z.gol_dom : "")}</div>
      <div class="rz-t">${ekip(z.gost)}<span>${esc(z.gost)}</span></div><div class="rz-sk">${esc(z.gol_gost != null ? z.gol_gost : "")}</div>
      <div class="rz-dolu"><span>${esc(z.liga)}</span><span class="zhivo-min"><i class="tochka"></i>${esc(et)}</span></div>
    </article>`;
  }

  function kartaStoynost(v) {
    return `<article class="pk pk-st">
      <div class="pk-h">${ik(v.sport, "ik s")}<span class="liga">${esc(v.sport_bg)}${v.liga ? " · " + esc(v.liga) : ""}</span></div>
      <div class="pk-mach"><div class="pk-tim">${ekip(v.dom)}<span>${esc(v.dom)}</span></div><div class="pk-vs">VS</div>
        <div class="pk-tim d">${ekip(v.gost)}<span>${esc(v.gost)}</span></div></div>
      <div class="pk-izbor"><div><small>Стойностен изход</small><b>${esc(v.izbor)}</b></div>
        <div class="pk-koef"><small>Коеф. Betano</small><b>${esc(fmtKoef(v.koef))}</b></div></div>
      <div class="pk-val">${ico("diamant", "val-ik")}<b>Стойност +${esc(Math.round(v.ev * 100))}%</b>${v.kely ? `<span>заложи ${esc((v.kely * 100).toFixed(1))}% от банката</span>` : ""}</div>
    </article>`;
  }

  /* ── НАЧАЛО ── */
  function ekranNachalo() {
    const d = S.data || {};
    const pr = d.prognozi || [];
    const dnes = pr.filter((k) => k.den === d.dnes);
    const topSorted = (dnes.length ? dnes : pr).slice().sort((a, b) => (b.procent || 0) - (a.procent || 0));
    const geroiPk = (dnes.length && topSorted[0] && eTop(topSorted[0])) ? topSorted[0] : null;
    const top = topSorted.filter((k) => !geroiPk || k.id !== geroiPk.id).slice(0, 4);
    const br = brSport();
    const sp = (d.sportove || []).filter((s) => br[s.sport]);
    const o = d.obshto || {};
    const fDnes = (d.fishove || []).filter((f) => f.den === d.dnes);
    const rez = (d.rezultati || []).slice(0, 4);
    const nov = (d.novini || []).slice(0, 4);
    const visoki = dnes.filter((k) => (k.procent || 0) >= 72 || (k.zvezdi || 0) >= 3).length;
    const sportaDnes = new Set(dnes.map((k) => k.sport)).size;
    const brief = dnes.length
      ? `Днес имаме <b>${dnes.length}</b> ${dnes.length === 1 ? "прогноза" : "прогнози"} в <b>${sportaDnes}</b> ${sportaDnes === 1 ? "спорт" : "спорта"}${visoki ? `, ${visoki} с висока увереност` : ""}${fDnes.length ? ` и <b>${fDnes.length}</b> ${fDnes.length === 1 ? "фиш" : "фиша"} на деня` : ""}.`
      : "Новите прогнози за деня излизат през целия ден — върни се по-късно или разгледай утрешните.";
    const pwa = !flag("gr_pwa_skrit") && !(matchMedia("(display-mode: standalone)").matches) ? `
      <div class="pwa-lenta"><span class="ik">${ico("prognozi", "ico")}</span>
        <p><b>Сложи The Green Room на телефона</b>Отваря се като приложение, на един допир.</p>
        <button class="btn m" data-pwa="1">Добави</button><button class="x" data-pwa-x="1" aria-label="Скрий">×</button></div>` : "";
    const meMail = (d.me && d.me.email) || "";
    const nm0 = meMail.split("@")[0].split(/[._\-0-9]/)[0];
    const imeGost = nm0 ? nm0.charAt(0).toUpperCase() + nm0.slice(1) : "";
    const hr = new Date().getHours();
    const pozdrav = (hr < 5 ? "Добра нощ" : hr < 12 ? "Добро утро" : hr < 18 ? "Добър ден" : "Добър вечер") + (imeGost ? ", " + imeGost : "");
    return ramka(null, `
      ${vcheraKart(d)}
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/home-joker.png')"></div>
        <div class="hero-copy"><h1>${esc(pozdrav)}</h1><p class="pod">Твоята Green Room е готова.</p>
          <button class="btn full" data-idi="prognozi">Виж прогнозите ${ico("str")}</button></div>
      </div>
      ${dnevniMisii()}
      <button class="scen-entry tur-entry" data-idi="turnir"><span class="scen-entry-ik">🏆</span><div><b>Турнир „Зелен фиш"</b><span>Предскажи · мери се с модела и тълпата</span></div><span class="str">${ico("str")}</span></button>
      ${moiteOtboriSekcia(d)}
      ${geroiPk ? kartaGeroiMach(geroiPk) : ""}
      ${(d.zhivo || []).length ? `<section class="sekcia zhivo-sek"><header><h2>На живо сега</h2><span class="den-badge zh"><i class="tochka"></i>${(d.zhivo || []).length}</span></header>
        <div class="karti kol">${(d.zhivo || []).slice(0, 4).map(kartaZhivo).join("")}</div></section>` : ""}
      <section class="brief"><div class="brief-h">${ico("prognozi", "ico")}<b>Дневен фокус</b><span class="brief-den">Днес</span></div>
        <p>${brief}</p></section>
      ${geroiPk ? `<section class="sekcia izbor-den"><header><h2>Най-силната прогноза днес</h2><span class="den-badge">Днес</span></header>${kartaPrognoza(geroiPk)}</section>` : ""}
      ${(d.stoynost || []).length ? `<section class="sekcia stoynost-sek"><header><h2>Стойност днес</h2><span class="den-badge val">${ico("diamant", "badge-ik")}Betano</span></header>
        <p class="stoynost-pod">Изходи, където коефициентът на Betano е над честната пазарна цена — с препоръчан залог.</p>
        <div class="karti kol">${(d.stoynost || []).slice(0, 4).map(kartaStoynost).join("")}</div></section>` : ""}
      ${pwa}
      <div class="plochki" style="margin-top:14px">
        <div class="plochka"><b>${esc(dnes.length)}</b><span>прогнози днес</span></div>
        <div class="plochka"><b>${esc(pr.filter(eTop).length)}</b><span>топ избора</span></div>
        <div class="plochka"><b class="em">${o.uspeh != null ? esc(o.uspeh) + "%" : "—"}</b><span>успеваемост · ${esc(o.n || 0)} прогнози / 30 дни</span></div></div>
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
      </div>
      <a class="tg-banner" href="${TGRUPA}" target="_blank" rel="noopener">
        <span class="ik">${ico("tg", "ico")}</span>
        <div><b>Вземи апа само за една салата</b><span>Влез в общността в Telegram — ежедневни прогнози, разбор и въпроси на живо.</span></div>
        <span class="str">${ico("str")}</span></a>`);
  }

  /* ── СПОРТ ── */
  function klasiraneSekcia(d) {
    const kl = (d && d.klasirane) || [];
    if (!kl.length) return "";
    const li = (S.klIdx != null && kl[S.klIdx]) ? S.klIdx : 0;
    const t = kl[li];
    const fdot = (f) => `<span class="kl-forma">${(f || []).slice(-5).map((r) => `<i class="fd-${String(r).toLowerCase()}"></i>`).join("")}</span>`;
    const zone = (poz) => t.zoni && poz <= t.zoni.evro ? " evro" : (t.zoni && poz >= t.zoni.izpadane ? " izpad" : "");
    return `<section class="sekcia klas-sek"><header><h2>Класиране</h2></header>
      ${kl.length > 1 ? `<div class="chipove">${kl.map((x, i) => `<button class="chip${i === li ? " on" : ""}" data-klidx="${i}">${esc(x.liga.split("·").pop().trim())}</button>`).join("")}</div>` : ""}
      <div class="klas-glava">${esc(t.liga)}</div>
      <div class="klas-tabl">
        <div class="kl-row kl-head"><span>#</span><span>Отбор</span><span>М</span><span>ГР</span><span>Т</span><span class="kl-fh">Форма</span></div>
        ${t.otbori.map((o) => `<div class="kl-row${zone(o.poz)}"><span class="kl-poz">${o.poz}</span><span class="kl-ime">${ekip(o.ime)}<b>${esc(o.ime)}</b></span><span>${o.igri}</span><span>${o.gr > 0 ? "+" : ""}${o.gr}</span><span class="kl-t">${o.t}</span>${fdot(o.forma)}</div>`).join("")}
      </div>
      <div class="klas-leg"><span class="kl-l-e">Европа</span><span class="kl-l-i">Изпадане</span></div></section>`;
  }
  function ekranSport() {
    const d = S.data || {};
    const br = brSport();
    if (S.sport) {
      const s = S.sport;
      const ime = ((d.sportove || []).find((x) => x.sport === s) || {}).sport_bg || s;
      const lib = SPORT_LIB[s];
      const hero = (lib && LIB_HERO[s]) ? LIB_HERO[s] : "sport-trofei";
      const pr = (d.prognozi || []).filter((k) => k.sport === s);
      const rz = (d.rezultati || []).filter((k) => k.sport === s);
      const lista = S.sportTab === "rez"
        ? (rz.length ? `<div class="karti kol">${rz.slice(0, 60).map(kartaRezultat).join("")}</div>` : '<p class="prazno">Още няма резултати за този спорт.</p>')
        : (pr.length ? `<div class="karti kol">${pr.map(kartaPrognoza).join("")}</div>` : '<p class="prazno">В момента няма прогнози за този спорт.</p>');
      const libTabs = ["Правила", "История", "Легенди", "Постижения"];
      const libBlok = lib ? `
        <div class="tabs">${libTabs.map((t, i) => `<button aria-pressed="${i === 0}">${esc(t)}</button>`).join("")}</div>
        <section class="sekcia"><header><h2>Как се играе</h2></header>
          <div class="lib-card"><b class="lib-lead">${esc(lib.kak)}</b><p>${esc(lib.kakP)}</p></div></section>
        <div class="dvoino2" style="margin-top:16px">
          <div class="lib-card"><span class="lib-et">История</span><b>${esc(lib.ist[0])} · ${esc(lib.ist[1])}</b><p>${esc(lib.ist[2])}</p></div>
          <div class="lib-card zlat"><span class="lib-et">Велик момент</span><b>${esc(lib.mom[0])}</b><p>${esc(lib.mom[1])}</p></div></div>
        <div class="lib-links">
          <a class="lib-link" href="#sport-mach">${ico("prognozi", "ico")}<span>Виж мачовете</span></a>
          <button class="lib-link" data-idi="novini">${ico("novini", "ico")}<span>Новини</span></button>
          <button class="lib-link" data-sport="">${ico("multi", "ico")}<span>Всички</span></button></div>
        <p class="demo-note">Източник: ${esc(lib.izt)} · съдържанието е с образователна цел.</p>` : "";
      return ramka(null, `
        <div class="hero">
          <div class="hero-fig" style="background-image:url('/img/${hero}.png')"></div>
          <div class="hero-copy"><p class="eyebrow">Библиотека · ${esc(ime)}</p><h1>${esc(ime)}</h1>${lib ? `<p class="pod">${esc(lib.pod)}</p>` : ""}</div>
        </div>
        ${libBlok}
        <section class="sekcia" id="sport-mach"><header><h2>Мачове и прогнози</h2><button class="vsichki" data-sport="">Всички спортове</button></header>
          <div class="tabs"><button data-stab="prog" aria-pressed="${S.sportTab !== "rez"}">Прогнози</button>
            <button data-stab="rez" aria-pressed="${S.sportTab === "rez"}">Резултати</button></div>
          <div style="margin-top:14px">${lista}</div></section>`);
    }
    return ramka(null, `
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/sport-trofei.png')"></div>
        <div class="hero-copy"><p class="eyebrow">Всеки спорт · Една стая</p><h1>Твоята Арена</h1></div>
      </div>
      <div class="tabs">${[["vsichki", "Всички"], ["populyarni", "Популярни"], ["az", "А-Я"]].map(([v, t]) =>
        `<button data-sptab="${v}" aria-pressed="${S.spTab === v}">${t}</button>`).join("")}</div>
      <label class="tarsene">${ico("tarsi")}<input id="sp-q" type="search" placeholder="Търси спорт…" value="${esc(S.spQ)}" aria-label="Търси спорт"></label>
      <div class="sp-grid" id="sp-lista" style="margin-top:12px">${listaSportove()}</div>
      ${(() => {
        const ligi = {};
        for (const k of (d.prognozi || [])) if (k.liga) ligi[k.liga] = (ligi[k.liga] || 0) + 1;
        const t = Object.entries(ligi).sort((a, b) => b[1] - a[1]).slice(0, 8);
        return t.length ? `<section class="sekcia"><header><h2>Активни лиги</h2></header><div class="chipove">${t.map(([l, n]) => `<span class="chip">${esc(l)} · ${n}</span>`).join("")}</div></section>` : "";
      })()}
      ${klasiraneSekcia(d)}`);
  }
  function listaSportove() {
    const d = S.data || {};
    const br = brSport();
    const rz = {};
    for (const k of d.rezultati || []) rz[k.sport] = (rz[k.sport] || 0) + 1;
    const q = S.spQ.trim().toLowerCase();
    let sp = (d.sportove || []).filter((s) => !q || s.sport_bg.toLowerCase().includes(q));
    if (S.spTab === "populyarni") sp = sp.filter((s) => br[s.sport]);
    sp = S.spTab === "az" ? sp.sort((a, b) => a.sport_bg.localeCompare(b.sport_bg, "bg"))
      : sp.sort((a, b) => (br[b.sport] || 0) - (br[a.sport] || 0));
    return sp.length ? sp.map((s) => {
      const bp = br[s.sport] || 0, br_ = rz[s.sport] || 0;
      const meta = bp ? bp + (bp === 1 ? " прогноза" : " прогнози") : (br_ ? br_ + " резултата" : "скоро");
      return `<button class="sp-plocha${bp ? " ima" : ""}" data-sport="${esc(s.sport)}">${ik(s.sport, "ik")}
        <b>${esc(s.sport_bg)}</b><span class="pod">${meta}</span></button>`;
    }).join("") : '<p class="prazno">Няма такъв спорт.</p>';
  }

  /* ── ПРОГНОЗИ ── */
  function filtriraniPrognozi() {
    const d = S.data || {};
    let x = d.prognozi || [];
    if (S.progTab === "dnes") x = x.filter((k) => k.den === d.dnes);
    else if (S.progTab === "utre") x = x.filter((k) => k.den > d.dnes);
    else if (S.progTab === "top") x = x.filter(eTop);
    if (S.calDen) x = x.filter((k) => k.den === S.calDen);
    if (S.progSport) x = x.filter((k) => k.sport === S.progSport);
    if (S.samoStoynost) x = x.filter((k) => (evNa(k) == null ? -1 : evNa(k)) > 0); // положителна очаквана стойност (коеф. над честната ни цена)
    if (S.samoLyubimi) x = x.filter((k) => S.lyubimi.has(k.id));
    const q = S.q.trim().toLowerCase();
    if (q) x = x.filter((k) => (k.dom + " " + k.gost + " " + k.liga + " " + k.sport_bg).toLowerCase().includes(q));
    return x;
  }
  /* подредбата вътре в един ден — Днес/Утре групите остават */
  const podrF = () => S.progSort === "uv" ? (a, b) => (b.procent || 0) - (a.procent || 0) || (b.zvezdi || 0) - (a.zvezdi || 0)
    : S.progSort === "koef" ? (a, b) => (b.koef || 0) - (a.koef || 0)
      : S.progSort === "ev" ? (a, b) => ((evNa(b) == null ? -9 : evNa(b)) - (evNa(a) == null ? -9 : evNa(a)))
        : (a, b) => (a.pusnata || "").localeCompare(b.pusnata || "");
  function kalendarLenta() {
    const pr = (S.data && S.data.prognozi) || [];
    const broy = {}; for (const k of pr) if (k.den) broy[k.den] = (broy[k.den] || 0) + 1;
    const dni = Object.keys(broy).sort();
    if (dni.length < 2) return "";
    return `<div class="kal-lenta"><button class="kal-d${!S.calDen ? " on" : ""}" data-calden="">Всички</button>${dni.map((dn) => `<button class="kal-d${S.calDen === dn ? " on" : ""}" data-calden="${esc(dn)}"><b>${esc(denEt(dn))}</b><span>${broy[dn]}</span></button>`).join("")}</div>`;
  }
  function listaPrognozi() {
    const x = filtriraniPrognozi();
    if (!x.length) {
      if (S.samoStoynost) return '<p class="prazno">В момента няма прогнози с положителна стойност (коефициент над честната ни цена). Това е честно — реалната стойност е рядка. Махни филтъра, за да видиш всички.</p>';
      if (S.samoLyubimi) return brLyubimi()
        ? '<p class="prazno">Няма любими за този избор — смени спорта/деня или махни търсенето.</p>'
        : '<p class="prazno">Още нямаш любими мачове. Докосни ★ на някоя прогноза, за да я запазиш тук.</p>';
      return '<p class="prazno">Няма прогнози за този избор.</p>';
    }
    const po = new Map();
    for (const k of x) { if (!po.has(k.den)) po.set(k.den, []); po.get(k.den).push(k); }
    const sf = podrF();
    return [...po.entries()].map(([den, ks]) => `<div class="den-glava" role="heading" aria-level="3">${esc(denDylag(den))} · ${ks.length}</div>
      <div class="karti kol">${ks.slice().sort(sf).map(kartaPrognoza).join("")}</div>`).join("");
  }
  function bankRoll() { const b = Number(flag("gr_bank")); return b > 0 ? b : 100; }
  function kellyFrac() { const f = Number(flag("gr_kfrac")); return [0.25, 0.5, 1].indexOf(f) >= 0 ? f : 0.25; }
  function kellyZalog(x, bank, frac) {
    // Кели-дял: ползвай брайновия kely ако го има, иначе го смятай от p и коеф.
    let f = Number(x.kely);
    if (!(f > 0)) { const p = (x.ev != null && x.koef) ? (1 + x.ev) / x.koef : 0; const b = (Number(x.koef) || 1) - 1; f = b > 0 ? Math.max(0, (p * b - (1 - p)) / b) : 0; }
    const st = Math.min(bank * 0.03, f * frac * bank); // таван 3% от банката
    return st;
  }
  function valueSekcia(d) {
    const v = ((d && d.stoynost) || []).filter((x) => x && x.koef && x.ev != null).sort((a, b) => (b.ev || 0) - (a.ev || 0)).slice(0, 8);
    if (!v.length) return "";
    questSet("val");
    const bank = bankRoll(), frac = kellyFrac();
    const fracEt = frac === 1 ? "пълен" : frac === 0.5 ? "½" : "¼";
    const banki = [50, 100, 200, 500, 1000];
    const karti = v.map((x) => {
      const z = kellyZalog(x, bank, frac);
      return `<div class="st-karta">
      <div class="st-top">${ik(x.sport, "ik s")}<span class="st-liga">${esc(x.liga || x.sport_bg || "")}</span></div>
      <b class="st-izbor">${esc(x.izbor || x.izhod)}</b>
      <div class="st-mach">${esc(x.dom || "")}${x.gost ? " — " + esc(x.gost) : ""}</div>
      <div class="st-dolu"><span class="st-koef">${esc(fmtKoef(x.koef))}</span>
        <span class="st-ev">EV +${esc((x.ev * 100).toFixed(1))}%</span></div>
      <div class="st-zalog"><span>Кели залог</span><b>${z >= 0.1 ? z.toFixed(z < 10 ? 1 : 0) + " €" : "< 0.1 €"}</b></div></div>`;
    }).join("");
    return `<section class="sekcia stoynost-sek">
      <header><h2>Стойност днес</h2><span class="st-broy">${v.length}</span></header>
      <p class="st-lead">Залози, при които коефициентът е над реалната ни вероятност — там е дългосрочното предимство.</p>
      <div class="bank-red">
        <div class="bank-lyavo"><span>Банка</span><div class="bank-chip-red">${banki.map((b) => `<button class="bchip${bank === b ? " on" : ""}" data-bank="${b}">${b}</button>`).join("")}</div></div>
        <div class="bank-lyavo"><span>Кели</span><div class="bank-chip-red">${[[0.25, "¼"], [0.5, "½"], [1, "1"]].map(([f, e]) => `<button class="bchip${frac === f ? " on" : ""}" data-kfrac="${f}">${e}</button>`).join("")}</div></div>
      </div>
      <p class="st-lead" style="margin-top:0">Препоръчан залог по <b>${fracEt} Кели</b> при банка <b>${bank} €</b> (таван 3%). Малкият ръб = малък залог — честно.</p>
      <div class="st-redica">${karti}</div></section>`;
  }
  function ekranPrognozi() {
    markSeen();
    const d = S.data || {};
    const br = brSport();
    const sp = (d.sportove || []).filter((s) => br[s.sport]);
    const tb = [["vsichki", "Всички"], ["dnes", "Днес"], ["utre", "Утре"], ["top", "Топ"]];
    const podr = [["red", "Ред"], ["uv", "Увереност"], ["ev", "Стойност"], ["koef", "Коеф."]];
    const nl = brLyubimi();
    return ramka(null, `
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/picks-asa.png')"></div>
        <div class="hero-copy"><p class="eyebrow">Анализ · Селекция · Перспектива</p><h1>Green Room Прогнози</h1></div>
      </div>
      <button class="scen-entry" data-idi="scenario"><span class="scen-entry-ik">🎲</span><div><b>Сценарии</b><span>Симулирай мача · виж вероятностите</span></div><span class="str">${ico("str")}</span></button>
      ${valueSekcia(d)}
      <div class="tabs" style="margin-top:14px">${tb.map(([v, t]) => `<button data-ptab="${v}" aria-pressed="${S.progTab === v}">${t}</button>`).join("")}</div>
      ${kalendarLenta()}
      <div class="chipove"><button class="chip lfav" data-lfav="1" aria-pressed="${S.samoLyubimi}">${ico("zvezda", "zv-ik")}Любими<b class="lfav-c">${nl ? " · " + nl : ""}</b></button>
        <button class="chip stoynost" data-stoynost="1" aria-pressed="${!!S.samoStoynost}">💎 Само стойност</button>
        <button class="chip" data-psport="" aria-pressed="${!S.progSport}">Всички спортове</button>
        ${sp.map((s) => `<button class="chip" data-psport="${esc(s.sport)}" aria-pressed="${S.progSport === s.sport}">${ik(s.sport, "ik s")}${esc(s.sport_bg)} · ${br[s.sport]}</button>`).join("")}</div>
      <div class="podr"><span class="podr-et">Подреди</span>${podr.map(([v, t]) => `<button data-psort="${v}" aria-pressed="${S.progSort === v}">${t}</button>`).join("")}</div>
      <div class="tabs vt"><button data-pkview="simple" aria-pressed="${S.pkView === "simple"}">Кратко</button><button data-pkview="expert" aria-pressed="${S.pkView === "expert"}">Подробно</button></div>
      <label class="tarsene">${ico("tarsi")}<input id="p-q" type="search" placeholder="Търси отбор, играч или лига…" value="${esc(S.q)}" aria-label="Търси"></label>
      <div id="p-lista" class="pk-${S.pkView}">${listaPrognozi()}</div>`);
  }

  /* ── СИСТЕМА ЗАЛОЗИ (Trixie/Yankee/Lucky15…) — чиста клиентска математика ── */
  function sistemaData() {
    const legs = S.slip.filter((x) => x.koef > 1);
    return { n: legs.length, odds: legs.map((x) => x.koef), perLine: Math.max(1, Number(S.suma) || 0) };
  }
  const SIS_MAPA = { 3: [["Trixie", [2, 3]], ["Patent", [1, 2, 3]]], 4: [["Yankee", [2, 3, 4]], ["Lucky 15", [1, 2, 3, 4]]], 5: [["Super Yankee", [2, 3, 4, 5]], ["Lucky 31", [1, 2, 3, 4, 5]]], 6: [["Heinz", [2, 3, 4, 5, 6]], ["Lucky 63", [1, 2, 3, 4, 5, 6]]] };
  function sistemaRedove() {
    const { n, odds, perLine } = sistemaData();
    if (n < 3 || n > 6) return "";
    const C = (a, k) => { let r = 1; for (let i = 0; i < k; i++) r = r * (a - i) / (i + 1); return Math.round(r); };
    const combSum = (k) => { let s = 0; const rec = (st, pr, c) => { if (c === k) { s += pr; return; } for (let i = st; i < n; i++) rec(i + 1, pr * odds[i], c + 1); }; rec(0, 1, 0); return s; };
    return (SIS_MAPA[n] || []).map(([ime, folds]) => {
      const lines = folds.reduce((a, k) => a + C(n, k), 0);
      const stake = lines * perLine;
      const maxRet = folds.reduce((a, k) => a + combSum(k), 0) * perLine;
      return `<div class="sis-red"><div class="sis-ime"><b>${esc(ime)}</b><small>${lines} залога${folds[0] === 1 ? " · с единични" : ""}</small></div>
        <div class="sis-col"><small>Общ залог</small><b>${stake.toFixed(2)} €</b></div>
        <div class="sis-col"><small>Ако всички познаят</small><b class="em">${maxRet.toFixed(2)} €</b></div></div>`;
    }).join("");
  }
  function sistemaBlok() {
    const { n, perLine } = sistemaData();
    if (n < 3 || n > 6) return "";
    return `<details class="sistema"><summary><span class="sis-ik">⚙️</span><b>Система залог</b><small>частичните успехи също плащат</small></summary>
      <p class="sis-pod">Залог на линия <b id="sis-perline">${perLine.toFixed(2)} €</b> (= полето „Сума"). Системата покрива всички комбинации, за да печелиш и без всичките ${n} да познаят.</p>
      <div id="sis-redove">${sistemaRedove()}</div></details>`;
  }

  /* ── ПОРТФЕЙЛ „Моите залози" — следи твоите записани залози + авто-сетълмент + P/L ── */
  function portfeil() { try { return JSON.parse(localStorage.getItem("gr_portfeil") || "[]") || []; } catch (e) { return []; } }
  function paziPortfeil(a) { try { localStorage.setItem("gr_portfeil", JSON.stringify(a)); } catch (e) { /* личен режим */ } }
  function zapishiZalog() {
    if (!S.slip.length) return toast("Фишът е празен — добави поне един избор.");
    const k = slipKoef();
    const arr = portfeil();
    arr.unshift({ id: "z" + Date.now(), ts: Date.now(), den: (S.data && S.data.dnes) || "", suma: Number(S.suma) || 0, koef: k || null, legs: S.slip.map((x) => ({ dom: x.dom, gost: x.gost, izbor: x.izbor, koef: x.koef, sport: x.sport, den: x.den })) });
    paziPortfeil(arr.slice(0, 100));
    toast("Записано в портфейла · " + Math.min(arr.length, 100) + " залога");
    S.fishTab = "portfeil"; render();
  }
  function legStatus(leg) { // залозите идват от НАШИ пикове → използваме poznata на резултата
    const m = ((S.data && S.data.rezultati) || []).find((r) => r.dom === leg.dom && r.gost === leg.gost);
    if (!m || m.poznata == null) return "pending";
    return m.poznata === true ? "won" : "lost";
  }
  function betStatus(bet) {
    const st = (bet.legs || []).map(legStatus);
    if (st.some((s) => s === "lost")) return "lost";
    if (st.length && st.every((s) => s === "won")) return "won";
    return "pending";
  }
  function betPL(bet) { const s = betStatus(bet); return s === "won" ? bet.suma * (bet.koef || 1) - bet.suma : s === "lost" ? -bet.suma : 0; }
  function portfeilSekcia() {
    const bets = portfeil();
    if (!bets.length) return `<p class="prazno" style="margin-top:14px">Още нямаш записани залози. Събери фиш в „Моят фиш" и натисни <b>„Заложих го"</b>, за да го следиш тук с реален резултат и печалба/загуба.</p>
      <div style="text-align:center;margin-top:12px"><button class="btn" data-ftab="moi">Към моя фиш ${ico("str")}</button></div>`;
    const settled = bets.filter((b) => betStatus(b) !== "pending");
    const staked = settled.reduce((a, b) => a + (b.suma || 0), 0);
    const pl = settled.reduce((a, b) => a + betPL(b), 0);
    const roi = staked ? (pl / staked * 100) : 0;
    const open = bets.length - settled.length;
    const won = settled.filter((b) => betStatus(b) === "won").length;
    const stEt = { won: "Спечелен", lost: "Загубен", pending: "В игра" };
    const legEt = { won: "✓", lost: "✗", pending: "•" };
    return `<div class="pf-svod">
        <div><b class="${pl >= 0 ? "poz" : "neg"}">${pl >= 0 ? "+" : ""}${pl.toFixed(2)} €</b><span>резултат</span></div>
        <div><b class="${roi >= 0 ? "poz" : "neg"}">${roi >= 0 ? "+" : ""}${roi.toFixed(1)}%</b><span>ROI</span></div>
        <div><b>${won}/${settled.length}</b><span>спечелени</span></div>
        <div><b>${open}</b><span>в игра</span></div>
      </div>
      <div class="pf-lista">${bets.map((b) => { const st = betStatus(b), plb = betPL(b); return `<article class="pf-bet ${st}">
        <header><b>${b.legs.length === 1 ? "Единичен" : "Комбиниран · " + b.legs.length}</b><span class="den">${esc(denDylag(b.den))}</span><span class="pf-st ${st}">${stEt[st]}</span></header>
        <ol>${b.legs.map((l) => `<li><span class="pf-leg-st ${legStatus(l)}">${legEt[legStatus(l)]}</span><span class="m">${esc(l.dom)} — ${esc(l.gost)}</span><span class="i">${esc(izborTxt(l.izbor))} · ${esc(fmtKoef(l.koef))}</span></li>`).join("")}</ol>
        <footer><span>${esc((b.suma || 0).toFixed(2))} € @ ${b.koef ? esc(b.koef.toFixed(2)) : "—"}</span>${st === "pending" ? '<b class="pf-pend">в игра</b>' : `<b class="${plb >= 0 ? "poz" : "neg"}">${plb >= 0 ? "+" : ""}${plb.toFixed(2)} €</b>`}<button class="pf-x" data-pfmaha="${esc(b.id)}" aria-label="Изтрий">×</button></footer>
      </article>`; }).join("")}</div>`;
  }

  function fishTabs(active) {
    const f = (S.data && S.data.fishove) || [];
    const akt = f.filter((x) => x.status === "v_igra").length, pri = f.length - akt, pf = portfeil().length;
    return `<div class="tabs tabs-fish"><button data-ftab="aktivni" aria-pressed="${active === "aktivni"}">В игра · ${akt}</button>
      <button data-ftab="priklyucheni" aria-pressed="${active === "priklyucheni"}">Приключили · ${pri}</button>
      <button data-ftab="moi" aria-pressed="${active === "moi"}">Моят фиш · ${S.slip.length}</button>
      <button data-ftab="portfeil" aria-pressed="${active === "portfeil"}">Портфейл${pf ? " · " + pf : ""}</button></div>`;
  }
  function ekranPortfeil() {
    return ramka(["Моите залози", "Записаните ти залози със реален резултат и печалба/загуба."], fishTabs("portfeil") + portfeilSekcia());
  }

  /* ── ФИШОВЕ ── */
  function ekranFishove() {
    const f = (S.data && S.data.fishove) || [];
    if (S.fishTab === "moi") return ekranMoiFish(f);
    if (S.fishTab === "portfeil") return ekranPortfeil();
    const akt = f.filter((x) => x.status === "v_igra");
    const pri = f.filter((x) => x.status !== "v_igra");
    const x = S.fishTab === "aktivni" ? akt : pri;
    const pozn = pri.filter((y) => y.status === "poznat").length;
    return ramka(["Фишове", "Комбинирани фишове от нашите прогнози — с общ коефициент."], `
      ${fishTabs(S.fishTab)}
      ${S.fishTab !== "aktivni" && pri.length ? `<div class="obzor"><div class="pryasten" style="--p:${Math.round((100 * pozn) / pri.length)}"><b>${Math.round((100 * pozn) / pri.length)}%</b></div>
        <p>Спечелени фишове за 7 дни<br><b>${pozn}</b> от ${pri.length}</p></div>` : ""}
      <div class="karti kol" style="margin-top:14px">${x.length ? x.map(kartaFish).join("") : `<p class="prazno">${S.fishTab === "aktivni" ? "В момента няма фишове в игра." : "Още няма приключили фишове."}</p>`}</div>`);
  }

  /* ── МОЯТ ФИШ ── */
  function ekranMoiFish(f) {
    const akt = f.filter((x) => x.status === "v_igra").length;
    const pri = f.length - akt;
    const k = slipKoef();
    const pech = k ? Math.round(S.suma * k * 100) / 100 : null;
    const tabs = fishTabs("moi");
    const gl = ["Моят фиш", "Събери свой фиш от нашите прогнози и виж общия коефициент."];
    if (!S.slip.length) {
      return ramka(gl, tabs + `<p class="prazno" style="margin-top:14px">Фишът е празен. Отвори „Прогнози“ и натисни „+ Добави във фиша“ под избора, който харесваш.</p>
        <div style="text-align:center;margin-top:14px"><button class="btn" data-idi="prognozi">Към прогнозите ${ico("str")}</button></div>`);
    }
    return ramka(gl, tabs + `
      <article class="fs moi" style="margin-top:14px">
        <header><b>${S.slip.length === 1 ? "Единичен" : "Комбиниран"}</b><span class="den">${S.slip.length} ${S.slip.length === 1 ? "събитие" : "събития"}</span>
          <button class="btn m v2" data-izchisti="1" style="margin-left:auto">Изчисти</button></header>
        <ol>${S.slip.map((x) => `<li>${ik(x.sport, "ik s")}<span class="m">${esc(x.dom)} — ${esc(x.gost)}</span>
          <span class="k">${esc(fmtKoef(x.koef))}<button class="maha" data-maha="${esc(x.id)}" aria-label="Махни от фиша">×</button></span>
          <span class="i">${esc(izborTxt(x.izbor))} · ${esc(denEt(x.den))}</span></li>`).join("")}</ol>
        <div class="suma-blok">
          <div class="red-k"><span>Общ коефициент</span><b>${k ? esc(k.toFixed(2)) : "—"}</b></div>
          <label class="red-k"><span>Сума (€)</span><input id="f-suma" type="number" min="1" step="1" inputmode="decimal" value="${esc(S.suma)}"></label>
          <div class="brzi">${[10, 20, 50, 100].map((v) => `<button class="${S.suma === v ? "on" : ""}" data-suma="${v}">${v} €</button>`).join("")}</div>
          <div class="red-k pech"><span>Възможна печалба</span><b id="f-pech">${pech != null ? esc(pech.toFixed(2)) + " €" : "—"}</b></div>
          <div class="red-k risk"><span>Залог под риск</span><b id="f-risk">${esc((Number(S.suma) || 0).toFixed(2))} €</b></div>
          ${k ? `<p class="risk-note">Шанс да не мине ~<b>${Math.round(100 - 100 / k)}%</b> (по общия коефициент). Залагаш на своя отговорност · 18+.</p>` : ""}
          ${sistemaBlok()}
          <button class="btn full" data-zapishi="1" style="margin-top:12px">${ico("fishove", "btn-ik")}Заложих го — следи в портфейла</button>
          <div class="fish-akcii">
            <button class="btn v2" data-spodeli="1">${ico("tg", "btn-ik")}Сподели</button>
            <button class="btn v2" data-kopirai="1">Копирай</button>
          </div>
        </div>
      </article>`);
  }
  function toggleSlip(id) {
    if (vFisha(id)) { S.slip = S.slip.filter((x) => x.id !== id); pazi(); return; }
    const k = ((S.data && S.data.prognozi) || []).find((x) => x.id === id);
    if (!k || !k.koef) return;
    if (S.slip.some((x) => x.dom === k.dom && x.gost === k.gost)) { toast("Този мач вече е във фиша."); return; }
    S.slip.push({ id: k.id, sport: k.sport, dom: k.dom, gost: k.gost, izbor: k.izbor, koef: k.koef, den: k.den });
    pazi();
    toast("Добавено във фиша · " + S.slip.length + (S.slip.length > 1 && slipKoef() ? " · общ коеф. " + slipKoef().toFixed(2) : ""));
  }
  /* обновяване НА МЯСТО — без пренасяне на целия екран (скролът остава) */
  function obnoviDob(b, id) {
    const inn = vFisha(id);
    b.setAttribute("aria-pressed", inn ? "true" : "false");
    b.textContent = inn ? "✓ Във фиша" : "+ Добави във фиша";
  }
  /* звездата НА МЯСТО — сменя състоянието, обновява името и подскача САМО при клик */
  function obnoviZvezda(b) {
    const beshe = b.getAttribute("aria-pressed") === "true";
    b.setAttribute("aria-pressed", beshe ? "false" : "true");
    b.setAttribute("aria-label", beshe ? "Добави в любими" : "Премахни от любими");
    try { if (!matchMedia("(prefers-reduced-motion: reduce)").matches) b.animate([{ transform: "scale(1)" }, { transform: "scale(1.32)" }, { transform: "scale(1)" }], { duration: 280, easing: "ease" }); } catch (e) { /* без анимация */ }
  }
  function obnoviLfav() { const c = document.querySelector(".lfav-c"); if (c) { const n = brLyubimi(); c.textContent = n ? " · " + n : ""; } }
  function obnoviPill() {
    const app = document.querySelector(".app");
    if (!app) return;
    let pill = app.querySelector(".slip-pill");
    const trqbva = S.slip.length && !(S.tab === "fishove" && S.fishTab === "moi") && !S.adminRejim;
    if (!trqbva) { if (pill) pill.remove(); return; }
    const html = `${ico("fishove")}Моят фиш · ${S.slip.length}${slipKoef() ? `<b>${esc(slipKoef().toFixed(2))}</b>` : ""}`;
    if (pill) { pill.innerHTML = html; return; }
    pill = document.createElement("button");
    pill.className = "slip-pill";
    pill.dataset.moi = "1";
    pill.innerHTML = html;
    app.appendChild(pill);
  }
  function tekstNaFisha() {
    const k = slipKoef();
    return ["The Green Room · моят фиш",
      ...S.slip.map((x, i) => `${i + 1}. ${x.dom} — ${x.gost} (${denEt(x.den)}): ${izborTxt(x.izbor)} @ ${Number(x.koef).toFixed(2)}`),
      k ? `Общ коефициент: ${k.toFixed(2)}` : ""].filter(Boolean).join("\n");
  }
  async function kopirai() {
    if (!S.slip.length) return toast("Фишът е празен.");
    const t = tekstNaFisha();
    try { await navigator.clipboard.writeText(t); toast("Фишът е копиран."); } catch (e) { prompt("Копирай фиша:", t); }
  }
  async function spodeli() {
    if (!S.slip.length) return toast("Фишът е празен.");
    const share = tekstNaFisha() + "\n\nИграй с нас: https://thegreenroom-bg.netlify.app";
    if (navigator.share) {
      try { await navigator.share({ title: "The Green Room · моят фиш", text: share }); return; }
      catch (e) { if (e && e.name === "AbortError") return; }
    }
    try { await navigator.clipboard.writeText(share); toast("Фишът е копиран — пусни го на приятел."); }
    catch (e) { prompt("Копирай и сподели фиша:", share); }
  }
  async function pokani() {
    const share = "The Green Room — по-умни спортни прогнози, анализи и стойностни залози.\n\nВлез тук: https://thegreenroom-bg.netlify.app";
    if (navigator.share) {
      try { await navigator.share({ title: "The Green Room", text: share }); return; }
      catch (e) { if (e && e.name === "AbortError") return; }
    }
    try { await navigator.clipboard.writeText(share); toast("Линкът е копиран — прати го на приятел."); }
    catch (e) { prompt("Копирай и сподели линка:", share); }
  }

  /* ── ЧЕСТНОСТ: крива на банката + калибрация (от сверените ни резултати) ── */
  function chestnostBlok(scored) {
    if (!scored || scored.length < 8) return "";
    const hron = [...scored].sort((a, b) => ((a.den || "") + (a.pusnata || "")).localeCompare((b.den || "") + (b.pusnata || "")));
    let bank = 0, peak = 0, dd = 0, profit = 0, wins = 0, curL = 0, maxL = 0; const pts = [];
    for (const k of hron) {
      const win = k.poznata === true;
      if (win) { const g = (Number(k.koef) || 1) - 1; bank += g; profit += g; wins += 1; curL = 0; } else { bank -= 1; profit -= 1; curL += 1; if (curL > maxL) maxL = curL; }
      if (bank > peak) peak = bank; if (peak - bank > dd) dd = peak - bank; pts.push(bank);
    }
    const n = hron.length, yld = (profit / n) * 100, winrate = Math.round((wins / n) * 100);
    // SVG крива
    const W = 320, H = 88, min = Math.min(0, ...pts), max = Math.max(0.5, ...pts), rng = (max - min) || 1;
    const sx = (i) => n < 2 ? W : (i / (n - 1)) * W, sy = (v) => H - ((v - min) / rng) * H;
    const line = pts.map((v, i) => (i ? "L" : "M") + sx(i).toFixed(1) + " " + sy(v).toFixed(1)).join(" ");
    const zeroY = sy(0).toFixed(1);
    const area = "M0 " + zeroY + " " + pts.map((v, i) => "L" + sx(i).toFixed(1) + " " + sy(v).toFixed(1)).join(" ") + " L" + W + " " + zeroY + " Z";
    const posit = profit >= 0;
    // калибрация по обявен процент
    const bins = [[50, 60], [60, 70], [70, 80], [80, 90], [90, 101]];
    const kal = bins.map(([lo, hi]) => {
      const g = scored.filter((k) => { const p = Number(k.procent) || 0; return p >= lo && p < hi; });
      if (g.length < 3) return null;
      return { et: lo + "–" + (hi > 100 ? 99 : hi) + "%", nn: g.length, pred: Math.round(g.reduce((s, k) => s + (Number(k.procent) || 0), 0) / g.length), act: Math.round(100 * g.filter((k) => k.poznata === true).length / g.length) };
    }).filter(Boolean);
    return `<section class="chest">
      <div class="chest-h"><b>Крива на банката</b><span>${n} залога · 1 юнит${(S.data && S.data.dnes) ? " · към " + esc(denDylag(S.data.dnes)) : ""}</span></div>
      <div class="bank-chisla">
        <div><b class="${posit ? "poz" : "neg"}">${posit ? "+" : ""}${profit.toFixed(1)}</b><span>юнита</span></div>
        <div><b class="${yld >= 0 ? "poz" : "neg"}">${yld >= 0 ? "+" : ""}${yld.toFixed(1)}%</b><span>доходност</span></div>
        <div><b>${winrate}%</b><span>печеливши</span></div>
        <div><b>−${dd.toFixed(1)}</b><span>макс. спад</span></div>
        <div><b>${maxL}</b><span>макс. губеща серия</span></div>
      </div>
      <svg class="bank-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
        <defs><linearGradient id="bg-grad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--em2)" stop-opacity=".28"/><stop offset="1" stop-color="var(--em2)" stop-opacity="0"/></linearGradient></defs>
        <line x1="0" y1="${zeroY}" x2="${W}" y2="${zeroY}" class="bank-zero"/>
        <path d="${area}" fill="url(#bg-grad)"/>
        <path d="${line}" class="bank-line ${posit ? "poz" : "neg"}"/>
      </svg>
      <p class="chest-note">Доходност = печалба на заложен юнит — по-честна от голия процент печеливши (той се надува с ниски коефициенти).</p>
      ${kal.length >= 2 ? `<div class="kal">
        <div class="chest-h"><b>Калибрация</b><span>обявено срещу сбъднато</span></div>
        ${kal.map((b) => `<div class="kal-row"><span class="kal-et">${b.et}</span>
          <span class="kal-track"><i class="kal-obyaveno" style="width:${b.pred}%"></i><i class="kal-marker" style="left:${b.act}%"></i></span>
          <span class="kal-val"><b>${b.act}%</b><small>n=${b.nn}</small></span></div>`).join("")}
        <p class="chest-note">Лентата = обявеното; чертичката = реално сбъднатото. Колкото по-близо, толкова по-честни са процентите.</p></div>` : ""}
    </section>`;
  }

  /* ── РЕЗУЛТАТИ ── */
  function ekranRezultati() {
    const r = (S.data && S.data.rezultati) || [];
    const scored = r.filter((k) => k.poznata === true || k.poznata === false);
    const forma = scored.slice(0, 14).reverse();
    const fp = forma.filter((k) => k.poznata === true).length;
    let seria = 0; const seriaW = scored[0] && scored[0].poznata === true;
    for (const k of scored) { if (k.poznata === seriaW) seria++; else break; }
    const seriaHtml = seria >= 2 ? `<span class="seria ${seriaW ? "hot" : "cold"}">${seriaW ? "🔥" : "❄️"} ${seria} ${seriaW ? "поредни" : "без"}</span>` : "";
    const formaHtml = forma.length >= 4 ? `<div class="forma"><div class="forma-h"><b>Форма</b>${seriaHtml || `<span>последни ${forma.length}</span>`}</div>
      <div class="forma-dots">${forma.map((k) => `<i class="${k.poznata ? "w" : "l"}"></i>`).join("")}</div>
      <div class="forma-sum"><b>${fp}</b><span>/${forma.length}</span></div></div>` : "";
    const dni = [...new Set(r.map((x) => x.den))].slice(0, 7);
    if (!S.rezDen || !dni.includes(S.rezDen)) S.rezDen = dni[0] || null;
    const x = r.filter((k) => k.den === S.rezDen);
    const p = x.filter((k) => k.poznata === true).length;
    const n = x.filter((k) => k.poznata === true || k.poznata === false).length;
    const po = new Map();
    for (const k of x) { const kl = k.sport_bg + (k.liga ? " · " + k.liga : ""); if (!po.has(kl)) po.set(kl, { s: k.sport, ks: [] }); po.get(kl).ks.push(k); }
    // ── ТРАК-РЕКОРД (общо + успех по спорт) — прозрачност за клиента ──
    const ob = (S.data && S.data.obshto) || {};
    const st = ((S.data && S.data.statistika) || []).filter((s) => s && s.n >= 10).sort((a, b) => (b.uspeh || 0) - (a.uspeh || 0));
    const maxU = Math.max(60, ...st.map((s) => s.uspeh || 0));
    const rekordHtml = ob.n ? `<section class="rekord">
      <div class="rk-glava">
        <div class="rk-krug" style="--p:${esc(ob.uspeh || 0)}"><b data-count="${esc(ob.uspeh || 0)}" data-suf="%">${esc(ob.uspeh)}%</b><span>успех</span></div>
        <div class="rk-chisla">
          <div><b>${esc(ob.n)}</b><span>прогнози</span></div>
          <div><b>${esc(ob.poznati)}</b><span>познати</span></div>
          <div><b>${esc(ob.dni)}</b><span>дни</span></div>
        </div>
      </div>
      ${st.length ? `<div class="rk-sport"><div class="rk-sport-h"><b>Успех по спорт</b><span>цялата история</span></div>
        ${st.map((s) => `<div class="rk-bar"><span class="rk-ime">${ik(s.sport, "ik s")}${esc(s.sport_bg)}</span>
          <span class="rk-track"><i class="rk-fill${(s.uspeh || 0) >= 55 ? " top" : (s.uspeh || 0) < 50 ? " nisko" : ""}" style="width:${Math.max(6, Math.round((100 * (s.uspeh || 0)) / maxU))}%"></i></span>
          <span class="rk-pct"><b>${esc(s.uspeh)}%</b><small>${esc(s.n)}</small></span></div>`).join("")}
        <div class="rk-legenda">Числото до всеки спорт е броят оценени прогнози. Печалбата тръгва около 53%.</div></div>` : ""}
    </section>` : "";
    const daily = dni.length ? `
      ${formaHtml}
      <div class="tabs">${dni.slice(0, 4).map((d) => `<button data-rez="${esc(d)}" aria-pressed="${S.rezDen === d}">${esc(denEt(d))}</button>`).join("")}</div>
      ${dni.length > 4 ? `<div class="chipove">${dni.slice(4).map((d) => `<button class="chip" data-rez="${esc(d)}" aria-pressed="${S.rezDen === d}">${ico("kalendar", "ico")}${esc(denEt(d))}</button>`).join("")}</div>` : ""}
      ${n ? `<div class="obzor"><div class="pryasten" style="--p:${Math.round((100 * p) / n)}"><b>${Math.round((100 * p) / n)}%</b></div>
        <p>${esc(denDylag(S.rezDen))}<br><b>${p}</b> спечелени от ${n}</p></div>` : ""}
      ${[...po.entries()].map(([kl, g]) => `<div class="liga-glava">${ik(g.s, "ik s")}${esc(kl)}</div><div class="karti kol">${g.ks.map(kartaRezultat).join("")}</div>`).join("")}`
      : (rekordHtml ? "" : '<p class="prazno">Още няма оценени прогнози.</p>');
    return ramka(["Резултати", "Как завършиха нашите прогнози."], rekordHtml + chestnostBlok(scored) + daily);
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
    const d = S.data || {};
    const nf = (d.novini_full || []).filter((x) => x && x.title);
    const tit = d.novini || [];
    if (!nf.length && !tit.length) return ramka(["Новини"], '<p class="prazno">Няма нови новини в момента.</p>');
    const hero = `
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/news-vestnik.png')"></div>
        <div class="hero-copy"><p class="eyebrow">Историите зад играта</p><h1>Новинарска стая</h1></div>
      </div>`;
    if (!nf.length) {
      const [g, ...ost] = tit;
      return ramka(null, hero + `
        <article class="nov-glavna">${ik(sportOtZaglavie(g), "ik")}<div class="etiket">Водеща новина</div><h3>${esc(g)}</h3></article>
        <div class="spisyk kol" style="margin-top:12px">${ost.map((t) => `<div class="novina">${ik(sportOtZaglavie(t), "ik")}<p>${esc(t)}</p></div>`).join("")}</div>`);
    }
    const spIme = (s) => ((d.sportove || []).find((x) => x.sport === s) || {}).sport_bg || (s || "Спорт");
    const spSet = [...new Set(nf.map((x) => x.sport).filter(Boolean))];
    const flt = S.novSport || "";
    const spisak = flt ? nf.filter((x) => x.sport === flt) : nf;
    const chips = `<div class="chipove"><button class="chip" data-nsport="" aria-pressed="${!flt}">Всички</button>${spSet.map((s) => `<button class="chip" data-nsport="${esc(s)}" aria-pressed="${flt === s}">${ik(s, "ik s")}${esc(spIme(s))}</button>`).join("")}</div>`;
    const [g, ...ost] = spisak;
    const artikul = (x) => `<a class="nov-art" href="${esc(x.link || "#")}" target="_blank" rel="noopener">
      ${x.image ? `<span class="na-img" style="background-image:url('${esc(x.image)}')"></span>` : `<span class="na-img na-ik">${ik(x.sport, "ik")}</span>`}
      <span class="na-txt"><span class="na-meta">${esc(spIme(x.sport))}${x.source ? " · " + esc(x.source) : ""}</span><b>${esc(x.title)}</b></span></a>`;
    return ramka(null, hero + chips + `
      ${g ? `<a class="nov-feat" href="${esc(g.link || "#")}" target="_blank" rel="noopener">
        ${g.image ? `<span class="nf-img" style="background-image:url('${esc(g.image)}')"></span>` : ""}
        <span class="nf-body"><span class="nf-meta">${esc(spIme(g.sport))} · водеща</span><h3>${esc(g.title)}</h3><span class="na-src">${esc(g.source)}</span></span></a>` : ""}
      ${ost.length ? `<div class="karti kol" style="margin-top:12px">${ost.map(artikul).join("")}</div>` : ""}
      <button class="scen-entry" data-idi="sport" style="margin-top:16px"><span class="scen-entry-ik">📚</span><div><b>Библиотека на спорта</b><span>Правила · История · Легенди</span></div><span class="str">${ico("str")}</span></button>`);
  }

  /* ── LIVE CENTER ── */
  function ekranLive() {
    const d = S.data || {};
    const zh = d.zhivo || [];
    // Реален индикатор за хода на мача (минута/90 от истинската minuta) — не декор.
    const napredak = (min, status) => {
      const pct = status === "HT" ? 50 : Math.max(2, Math.min(100, Math.round(((min || 0) / 90) * 100)));
      return `<div class="live-progres"><span class="lp-track"><i style="width:${pct}%"></i><span class="lp-ht"></span></span>
        <div class="lp-meta"><span>Ход на мача</span><b>${status === "HT" ? "Полувреме" : (min != null ? min + "′" : "На живо")}</b></div></div>`;
    };
    const liveKarta = (lg, dm, gs, rz, min, status) => `<article class="live-k">
      <div class="live-top"><span class="live-badge"><i></i>НА ЖИВО</span><span class="live-liga">${esc(lg)}</span></div>
      <div class="live-mach"><div class="live-tim">${ekip(dm)}<b>${esc(dm)}</b></div>
        <div class="live-rez">${esc(rz)}</div>
        <div class="live-tim d">${ekip(gs)}<b>${esc(gs)}</b></div></div>
      ${napredak(min, status)}</article>`;
    const realni = zh.map((z) => liveKarta(z.liga || "Футбол", z.dom, z.gost,
      (z.gol_dom != null ? z.gol_dom : "") + " : " + (z.gol_gost != null ? z.gol_gost : ""),
      z.minuta, z.status)).join("");
    const broy = zh.length;
    return ramka(null, `
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/live-stadion.png')"></div>
        <div class="hero-copy"><p class="eyebrow">Усети всеки момент</p><h1>Център на живо</h1></div>
      </div>
      ${broy ? `<div class="chipove"><span class="chip on"><span class="tochka"></span>${broy} ${broy === 1 ? "мач" : "мача"} на живо сега</span></div>
      <div class="karti kol" style="margin-top:14px">${realni}</div>
      <button class="multiview">${ico("multi", "ico")}<div><b>Мултиизглед</b><span>Следи няколко мача едновременно</span></div><span class="str">${ico("str")}</span></button>`
      : `<div class="prazno-live">${ico("live", "ico big")}<b>В момента няма мачове на живо</b><p>Върни се по-късно — тук ще виждаш резултата и моментума на течащите мачове в реално време.</p>
        <button class="btn v2 shir" data-idi="prognozi">Виж днешните прогнози</button></div>`}`);
  }

  /* ── SCENARIO LAB ── */
  // ── РЕАЛЕН IN-PLAY POISSON ДВИГАТЕЛ + Dixon-Coles корекция (Сценарии) ──
  const DC_RHO = -0.03; // повдига 0:0 и 1:1 (чистият Poisson подценява равните)
  function poissonPmf(lam, k) {
    if (lam <= 0) return k === 0 ? 1 : 0;
    let p = Math.exp(-lam);
    for (let i = 1; i <= k; i++) p *= lam / i;
    return p;
  }
  function dcTau(i, j, lh, lg) {
    if (i === 0 && j === 0) return Math.max(0, 1 - lh * lg * DC_RHO);
    if (i === 0 && j === 1) return Math.max(0, 1 + lh * DC_RHO);
    if (i === 1 && j === 0) return Math.max(0, 1 + lg * DC_RHO);
    if (i === 1 && j === 1) return Math.max(0, 1 - DC_RHO);
    return 1;
  }
  function inplayHDA(lamH, lamG, minute, gh, gg, red) {
    const f = Math.max(0, (90 - minute) / 90);
    let lh = lamH * f, lg = lamG * f;
    if (red === "dom") { lh *= 0.72; lg *= 1.10; }
    else if (red === "gost") { lg *= 0.72; lh *= 1.10; }
    const MAX = 10, ph = [], pg = [];
    for (let i = 0; i <= MAX; i++) { ph[i] = poissonPmf(lh, i); pg[i] = poissonPmf(lg, i); }
    let H = 0, D = 0, A = 0;
    for (let i = 0; i <= MAX; i++) for (let j = 0; j <= MAX; j++) {
      const p = ph[i] * pg[j] * dcTau(i, j, lh, lg), fh = gh + i, fg = gg + j;
      if (fh > fg) H += p; else if (fh === fg) D += p; else A += p;
    }
    const s = H + D + A || 1;
    return { h: H / s, d: D / s, a: A / s };
  }
  function fitLambdas(outcome, procent, mu) {
    const target = Math.min(0.94, Math.max(0.06, (procent || 55) / 100));
    if (outcome === "X") {
      let lo = 0.6, hi = 3.4;
      for (let it = 0; it < 34; it++) { const mid = (lo + hi) / 2; (inplayHDA(mid / 2, mid / 2, 0, 0, 0, null).d < target) ? hi = mid : lo = mid; }
      const m = (lo + hi) / 2; return { lh: m / 2, lg: m / 2 };
    }
    const key = outcome === "2" ? "a" : "h", inc = key === "h";
    let lo = 0.2, hi = 6.0;
    for (let it = 0; it < 40; it++) { const r = (lo + hi) / 2; const pv = inplayHDA(mu * r / (1 + r), mu / (1 + r), 0, 0, 0, null)[key]; ((pv < target) === inc) ? lo = r : hi = r; }
    const r = (lo + hi) / 2; return { lh: mu * r / (1 + r), lg: mu / (1 + r) };
  }
  function pickOutcome(p) {
    const s = String((p && (p.izhod != null ? p.izhod : p.izbor)) || "").trim();
    if (/^2([·.\s]|$)/.test(s)) return "2";
    if (/^[XХ]([·.\s]|$)/.test(s)) return "X";
    return "1";
  }
  function scoreMatrica(lh, lg) {
    const MAX = 6, m = [];
    for (let i = 0; i <= MAX; i++) for (let j = 0; j <= MAX; j++) m.push({ i: i, j: j, p: poissonPmf(lh, i) * poissonPmf(lg, j) * dcTau(i, j, lh, lg) });
    const s = m.reduce((a, b) => a + b.p, 0) || 1; m.forEach((x) => { x.p /= s; });
    return m;
  }
  function futbolPrognoza(m) {
    if (!m || m.sport !== "football") return null;
    const f = fitLambdas(pickOutcome(m), m.procent, 2.7);
    const mat = scoreMatrica(f.lh, f.lg);
    const top = [...mat].sort((a, b) => b.p - a.p).slice(0, 3);
    const btts = mat.filter((x) => x.i >= 1 && x.j >= 1).reduce((a, b) => a + b.p, 0);
    const over = mat.filter((x) => x.i + x.j >= 3).reduce((a, b) => a + b.p, 0);
    return { top: top, btts: Math.round(btts * 100), over: Math.round(over * 100) };
  }
  function winProbSvg(lh, lg, sc) {
    const mins = [], ph = [], pa = [];
    for (let m = 0; m <= 90; m += 6) { const r = inplayHDA(lh, lg, m, sc.gh, sc.gg, sc.red); mins.push(m); ph.push(r.h); pa.push(r.a); }
    const W = 300, H = 66, sx = (m) => (m / 90) * W, sy = (p) => H - p * H;
    const path = (arr) => arr.map((p, i) => (i ? "L" : "M") + sx(mins[i]).toFixed(1) + " " + sy(p).toFixed(1)).join(" ");
    const mx = sx(Math.min(90, sc.minute)).toFixed(1);
    return `<svg class="wp-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
      <line x1="0" y1="${(H / 2).toFixed(1)}" x2="${W}" y2="${(H / 2).toFixed(1)}" class="wp-mid"/>
      <path d="${path(ph)}" class="wp-h"/><path d="${path(pa)}" class="wp-a"/>
      <line x1="${mx}" y1="0" x2="${mx}" y2="${H}" class="wp-now"/></svg>`;
  }
  function scenMach() {
    const d = S.data || {};
    if (S.machK && S.machK.sport === "football" && S.machK.dom) return S.machK;
    const pool = (d.prognozi || []).concat(d.dnes || []);
    return pool.find((p) => p && p.sport === "football" && p.dom && p.gost) || S.machK || (d.prognozi || [])[0] || null;
  }
  function kratkoIme(s) { s = String(s || ""); const w = s.split(/\s+/); return (w[0] && w[0].length <= 12) ? w[0] : s.slice(0, 11); }
  function scenView(m, sc) {
    if (sc.red) { const t = sc.red === "dom" ? m.gost : m.dom; return "Червен картон мени силите — " + kratkoIme(t) + " с човек повече поема инициативата."; }
    if (sc.gh > sc.gg) return kratkoIme(m.dom) + " води; с оставащото време преднината тежи все повече.";
    if (sc.gg > sc.gh) return kratkoIme(m.gost) + " води на чужд терен — обрат се иска все по-бързо.";
    if (sc.minute >= 70) return "Равенство в последните минути — реми става все по-вероятно.";
    if (sc.minute >= 45) return "Второто полувреме тръгва равно; всеки гол мени картината рязко.";
    return "Изчислено от силите на отборите преди начало.";
  }
  function ekranScenario() {
    flag("gr_c_scen", "1"); questSet("scen");
    const m = scenMach();
    if (!m || !m.dom) return ramka(["Сценарии", "Симулирай мача."], '<p class="prazno">Няма футболен мач за симулация в момента.</p>');
    const mid = m.id || (m.dom + m.gost);
    if (!S.scen || S.scen.id !== mid) S.scen = { id: mid, gh: 0, gg: 0, red: null, minute: 0 };
    const sc = S.scen, outcome = pickOutcome(m);
    const { lh, lg } = fitLambdas(outcome, m.procent, 2.7);
    const pr = inplayHDA(lh, lg, sc.minute, sc.gh, sc.gg, sc.red);
    let H = Math.round(pr.h * 100), D = Math.round(pr.d * 100), A = Math.round(pr.a * 100);
    const fix = 100 - (H + D + A), mx = Math.max(H, D, A); if (H === mx) H += fix; else if (A === mx) A += fix; else D += fix;
    const gauge = (p, lbl) => `<div class="gauge"><div class="ring" style="--p:${p}"><b>${p}%</b></div><span>${esc(lbl)}</span></div>`;
    const scB = [["gol-dom", "⚽", "Гол " + kratkoIme(m.dom)], ["gol-gost", "⚽", "Гол " + kratkoIme(m.gost)],
      ["red-dom", "🟥", "Червен " + kratkoIme(m.dom), sc.red === "dom"], ["red-gost", "🟥", "Червен " + kratkoIme(m.gost), sc.red === "gost"]];
    const mins = [0, 15, 30, 45, 60, 75, 85];
    return ramka(null, `
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/scenario-zar.png')"></div>
        <div class="hero-copy"><p class="eyebrow">Симулация · реален разчет</p><h1>Сценарии</h1><p class="pod">Промени случките и виж как моделът мени вероятностите.</p></div>
      </div>
      <article class="pk"><div class="pk-h">${ik("football", "ik s")}<span class="liga">${esc(m.sport_bg || "Футбол")}${m.liga ? " · " + esc(m.liga) : ""}</span></div>
        <div class="pk-mach"><div class="pk-tim">${ekip(m.dom)}<span>${esc(kratkoIme(m.dom))}</span></div>
          <div class="scen-tablo"><b>${sc.gh} : ${sc.gg}</b><span>${sc.minute}′${sc.red ? " · 🟥" : ""}</span></div>
          <div class="pk-tim d">${ekip(m.gost)}<span>${esc(kratkoIme(m.gost))}</span></div></div></article>
      <section class="sekcia"><header><h2>Вероятности за краен резултат</h2></header>
        <div class="gauges">${gauge(H, kratkoIme(m.dom))}${gauge(D, "Равен")}${gauge(A, kratkoIme(m.gost))}</div></section>
      <section class="sekcia"><header><h2>Вероятност през мача</h2><span class="scen-min">${sc.minute}′</span></header>
        ${winProbSvg(lh, lg, sc)}
        <div class="wp-leg"><span class="wp-l-h">${esc(kratkoIme(m.dom))}</span><span class="wp-l-a">${esc(kratkoIme(m.gost))}</span></div></section>
      <section class="sekcia"><header><h2>Случки в мача</h2><button class="vsichki" data-scen="reset">Нулирай</button></header>
        <div class="scen-grid">${scB.map(([a, e, t, on]) => `<button class="scen-b${on ? " on" : ""}" data-scen="${a}"><span class="scen-e">${e}</span><b>${esc(t)}</b></button>`).join("")}</div></section>
      <section class="sekcia"><header><h2>Минута</h2><span class="scen-min">${sc.minute}′</span></header>
        <div class="chipove">${mins.map((x) => `<button class="chip" data-scen="min:${x}" aria-pressed="${sc.minute === x}">${x}′</button>`).join("")}</div></section>
      <div class="view-c">${ico("prognozi", "ico")}<div><b>Green Room View</b><span>${esc(scenView(m, sc))}</span></div></div>
      <p class="scen-note">Разчетът е по Поасон върху оставащото време, стъпил на реалната ни прогноза${m.procent ? " (" + esc(m.procent) + "% за " + esc(izborTxt(m.izbor || outcome)) + ")" : ""}. Реален модел, не илюстрация.</p>`);
  }

  /* ── ФОРМА + H2H от нашия архив (без API) ── */
  function izhodOtRezT(k, ime) { // W/D/L за отбора ime от резултата „a:b"
    const sk = String(k.rezultat || "").split(/[:\-–]/).map((s) => parseInt(s.trim(), 10));
    if (sk.length < 2 || isNaN(sk[0]) || isNaN(sk[1])) return null;
    const mine = k.dom === ime ? sk[0] : sk[1], opp = k.dom === ime ? sk[1] : sk[0];
    return mine > opp ? "W" : mine < opp ? "L" : "D";
  }
  function otborForma(ime, n) {
    const rez = ((S.data && S.data.rezultati) || []).filter((k) => k.dom === ime || k.gost === ime)
      .sort((a, b) => String(b.den || "").localeCompare(String(a.den || "")));
    const out = [];
    for (const k of rez) { const r = izhodOtRezT(k, ime); if (r) out.push(r); if (out.length >= (n || 5)) break; }
    return out; // най-скорошните първи
  }
  function h2hArhiv(dom, gost) {
    return ((S.data && S.data.rezultati) || []).filter((k) => (k.dom === dom && k.gost === gost) || (k.dom === gost && k.gost === dom))
      .sort((a, b) => String(b.den || "").localeCompare(String(a.den || ""))).slice(0, 5);
  }
  function formaHistSek(k) {
    const fd = otborForma(k.dom), fg = otborForma(k.gost), h2h = h2hArhiv(k.dom, k.gost);
    if (fd.length < 2 && fg.length < 2 && !h2h.length) return ""; // архивът е тънък — не показвай празно
    const brto = (f) => ({ W: f.filter((x) => x === "W").length, D: f.filter((x) => x === "D").length, L: f.filter((x) => x === "L").length });
    const red = (ime, f) => f.length ? `<div class="fh-red"><span class="fh-ime">${esc(kratkoIme(ime))}</span>
      <span class="fdots">${f.slice().reverse().map((r) => `<i class="fd fd-${r.toLowerCase()}" title="${r}"></i>`).join("")}</span>
      <span class="fh-broj">${(() => { const b = brto(f); return b.W + "-" + b.D + "-" + b.L; })()}</span></div>` : "";
    return `<section class="sekcia fh-sek"><header><h2>Форма и история</h2><span class="scen-min">от нашия архив</span></header>
      <div class="fh-formi">${red(k.dom, fd)}${red(k.gost, fg)}</div>
      ${h2h.length ? `<div class="fh-h2h"><div class="fh-h2h-h">Последни срещи</div>
        ${h2h.map((m) => `<div class="fh-m"><span>${esc(kratkoIme(m.dom))}</span><b>${esc(m.rezultat || "—")}</b><span>${esc(kratkoIme(m.gost))}</span><small>${esc(denEt(m.den))}</small></div>`).join("")}</div>`
        : `<p class="fh-note">Няма предишни срещи в архива ни — формата (последни ${Math.max(fd.length, fg.length)}) е по-надеждният сигнал.</p>`}</section>`;
  }

  /* ── MATCH ROOM ── */
  function ekranMach() {
    const k = S.machK;
    if (!k) return idi("nachalo"), "";
    const pr = k.procent || 0;
    const puls = Math.max(28, Math.min(99, Math.round(pr * 0.72 + (k.zvezdi || 0) * 9 + 20)));
    const napr = puls >= 82 ? "силно напрежение" : puls >= 62 ? "голям интерес" : "равностоен мач";
    const rn = riskNiv(k);
    const dots = (kl) => Array.from({ length: 11 }, (_, i) => {
      const row = i === 0 ? 0 : i <= 4 ? 1 : i <= 7 ? 2 : 3;
      const inRow = i === 0 ? 1 : row === 1 ? 4 : 3;
      const idx = i === 0 ? 0 : row === 1 ? i - 1 : row === 2 ? i - 5 : i - 8;
      const across = 50 / (inRow + 1) * (idx + 1);
      const pos = kl === "dom" ? `left:${8 + across}%` : `right:${8 + across}%`;
      return `<i class="p-dot ${kl}" style="${pos};top:${12 + row * 25}%"></i>`;
    }).join("");
    return ramka(null, `
      <div class="mach-hero">
        <div class="mach-atmos" style="background-image:url('/img/mach-atmos.jpg')"></div>
        <div class="mach-liga">${ik(k.sport, "ik s")}<span>${esc(k.sport_bg)}${k.liga ? " · " + esc(k.liga) : ""}</span></div>
        <div class="mach-vs">
          <div class="mach-tim">${ekip(k.dom)}<b>${esc(k.dom)}</b></div>
          <div class="mach-ball">${ico("sport", "ico")}</div>
          <div class="mach-tim">${ekip(k.gost)}<b>${esc(k.gost)}</b></div>
        </div>
        <div class="mach-kpast">${esc(denEt(k.den))}${k.pusnata ? " · пусната " + esc(k.pusnata) : ""}</div>
      </div>
      <div class="koef-red">
        <div class="koef-b"><span>Нашата прогноза</span><b class="sm">${esc(izborTxt(k.izbor))}</b></div>
        <div class="koef-b"><span>Коефициент</span><b>${k.koef ? esc(fmtKoef(k.koef)) : "—"}</b></div>
        <div class="koef-b"><span>Увереност</span><b>${pr ? esc(pr) + "%" : "—"}</b></div>
      </div>
      ${k.zashto ? `<div class="lib-card" style="margin-top:16px"><span class="lib-et">Green Room View</span><p>${esc(k.zashto)}</p></div>` : ""}
      <div class="dvoino2" style="margin-top:12px">
        <div class="view-c">${ico("puls", "ico")}<div><b>Напрежение ${puls}</b><span>${esc(napr)}</span></div></div>
        <div class="risk-c risk-${rn.c}"><svg class="ico" viewBox="0 0 24 24"><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/></svg><div><b>Риск</b><span>${esc(rn.t)}</span></div></div>
      </div>
      ${k.koef ? `<button class="btn full" data-slip="${esc(k.id)}" style="margin-top:14px" aria-pressed="${vFisha(k.id)}">${vFisha(k.id) ? "✓ Във фиша" : "+ Добави във фиша"}</button>` : ""}
      <button class="btn v2 full" data-spodelipik="1" style="margin-top:10px">${ico("spodeliik")}Сподели картата</button>
      <div class="sledi-red">${[k.dom, k.gost].map((tm) => `<button class="sledi-b${sledeni().has(tm) ? " on" : ""}" data-sledi="${esc(tm)}">${ico("zvezda", "zv-ik")}${sledeni().has(tm) ? "Следваш " : "Следи "}${esc(kratkoIme(tm))}</button>`).join("")}</div>
      ${(() => { const fp = futbolPrognoza(k); return fp ? `<section class="sekcia rezultati-p"><header><h2>Вероятен резултат</h2><span class="scen-min">по модела</span></header>
        <div class="rp-scores">${fp.top.map((s) => `<div class="rp-s"><b>${s.i}:${s.j}</b><span>${Math.round(s.p * 100)}%</span></div>`).join("")}</div>
        <div class="rp-pazari"><div class="rp-p"><span>Двата бележат</span><b>${fp.btts}%</b></div><div class="rp-p"><span>Над 2.5 гола</span><b>${fp.over}%</b></div></div></section>` : ""; })()}
      ${formaHistSek(k)}
      <section class="sekcia"><header><h2>Тактическа схема</h2></header>
        <div class="pitch"><span class="p-mid"></span><span class="p-circle"></span>${dots("dom")}${dots("gost")}</div></section>
      <button class="scen-entry" data-idi="scenario" style="margin-top:16px"><span class="scen-entry-ik">🎲</span><div><b>Сценарии</b><span>Разгледай сценариите за мача</span></div><span class="str">${ico("str")}</span></button>`);
  }

  /* ── ПРОФИЛ ── */
  /* ── ТУРНИР „Зелен фиш" + Модел срещу Тълпата ── */
  async function zarediTurnir() {
    const r = await api("GET", "/api/turnir");
    if (r.s === 200) { S.turnir = r.j; return true; }
    if (r.s === 401) { S.me = null; ekranVhod("vhod"); return false; }
    if (r.s === 403) { ekranIzteklo(r.j.error); return false; }
    toast((r.j && r.j.error) || "Турнирът не се зареди."); return false;
  }
  function ekranTurnir() {
    const d = S.turnir;
    if (!d) return ramka(["Турнир", "Зареждам…"], '<div class="skelet"><div class="sk" style="height:120px"></div><div class="sk"></div></div>');
    const az = d.az || {};
    const izb = [["1", "1"], ["X", "рав"], ["2", "2"]];
    const machKarta = (m) => {
      const t = m.tълpa || { "1": 0, "X": 0, "2": 0 }, tot = (t["1"] || 0) + (t["X"] || 0) + (t["2"] || 0);
      const proc = (k) => tot ? Math.round(100 * (t[k] || 0) / tot) : 0;
      const vod = ["1", "X", "2"].sort((a, b) => (t[b] || 0) - (t[a] || 0))[0];
      const contra = m.nash && tot >= 3 && proc(vod) >= 55 && vod !== m.nash;
      const zaklyuchen = m.moi && m.moi.scored;
      return `<article class="tur-mach">
        <div class="tur-h">${ik(m.sport, "ik s")}<span>${esc(m.sport_bg || "")}${m.liga ? " · " + esc(m.liga) : ""}</span>${m.nash ? `<span class="tur-nash">Моделът: ${esc(m.nash)}</span>` : ""}</div>
        <div class="tur-tim"><b>${esc(m.dom)}</b><span>vs</span><b>${esc(m.gost)}</b></div>
        <div class="tur-izb">${izb.map(([k, t2]) => `<button class="tur-b${m.moi && m.moi.izbor === k ? " on" : ""}${m.nash === k ? " model" : ""}" data-predskazhi="${k}~${esc(m.den)}~${esc(m.sport)}~${esc(m.match_key)}"${zaklyuchen ? " disabled" : ""}><b>${t2}</b><span class="tur-bar"><i style="width:${proc(k)}%"></i></span><small>${proc(k)}%</small></button>`).join("")}</div>
        ${contra ? `<div class="tur-contra">🎯 СРЕЩУ ТЕЧЕНИЕТО — тълпата е на „${vod}", моделът не е съгласен</div>` : ""}
        ${zaklyuchen ? `<div class="tur-rez">${m.moi.points > 0 ? "✓ Позна · +" + m.moi.points : "✗ Не позна"}</div>` : ""}</article>`;
    };
    return ramka(null, `
      <div class="hero"><div class="hero-fig" style="background-image:url('/img/tur-shampion.jpg')"></div>
        <div class="hero-copy"><p class="eyebrow">Играй · Предскажи · Изкачвай се</p><h1>Турнир</h1><p class="pod">Мери инстинкта си срещу модела и тълпата.</p></div></div>
      <div class="tur-az"><div><b>${az.rank ? "#" + az.rank : "—"}</b><span>място</span></div><div><b data-count="${az.points || 0}">${az.points || 0}</b><span>точки</span></div><div><b>${az.tochni || 0}/${az.obshto || 0}</b><span>познати</span></div></div>
      <section class="sekcia"><header><h2>Предскажи днешните</h2><span class="den-badge">3 точки за познат</span></header>
        ${d.mach && d.mach.length ? d.mach.map(machKarta).join("") : '<p class="prazno">Няма мачове за прогноза в момента.</p>'}</section>
      ${d.tabla && d.tabla.length ? `<section class="sekcia"><header><h2>Класация</h2></header>
        <div class="tur-tabla"><div class="tur-red tur-glava"><span>#</span><span>Играч</span><span>Позн.</span><b>Точки</b></div>
        ${d.tabla.map((t) => `<div class="tur-red"><span class="tur-poz">${t.poz}</span><span class="tur-ime">${esc(t.ime)}</span><span class="tur-toch">${t.tochni}/${t.obshto}</span><b>${t.points}</b></div>`).join("")}</div></section>` : ""}`);
  }
  async function zarediRef() {
    if (S.refKod !== undefined) return;
    S.refKod = null;
    try { const r = await api("GET", "/api/ref"); if (r.s === 200) { S.refKod = r.j.kod || ""; S.refBonus = r.j.bonus || 7; if (S.tab === "profil" && !S.adminRejim) render(); } } catch (e) { /* игнор */ }
  }
  function refKart() {
    if (S.refKod === undefined) { zarediRef(); }
    const k = S.refKod;
    if (!k) return "";
    const link = "https://thegreenroom-bg.netlify.app/?ref=" + k;
    return `<section class="sekcia"><header><h2>Доведи приятел</h2><span class="den-badge val">+${S.refBonus || 7} дни</span></header>
      <div class="ref-kart"><p class="ref-lead">Сподели кода си — и <b>ти</b>, и приятелят получавате по <b>${S.refBonus || 7} дни</b> пълен достъп.</p>
        <div class="ref-kod"><code>${esc(k)}</code><button class="btn v2 shir" data-refcopy="${esc(link)}">${ico("spodeliik")}Копирай линка</button></div></div></section>`;
  }
  function rgSekcia() {
    return `<section class="sekcia"><header><h2>Играй отговорно</h2><span class="den-badge">18+</span></header>
      <div class="rg-kart">
        <p class="rg-lead"><b>Ние сме анализ, не букмейкър</b> — не приемаме залози и не държим пари. Прогнозите ни са <b>анализ, не гаранция</b>. Дори реален ръб има губещи серии — залагай само това, което можеш да си позволиш да загубиш, и никога „да си върнеш".</p>
        <ul class="rg-spisak">
          <li>${ico("shtit", "ico")}<span>Заложи предварително лимит и се придържай към него.</span></li>
          <li>${ico("kalendar", "ico")}<span>Прави почивки — хазартът не е начин за печелене на пари.</span></li>
          <li>${ico("pomosht", "ico")}<span>Ако играта спре да е забавна — спри и потърси помощ.</span></li>
        </ul>
        <a class="rg-link" href="https://www.begambleaware.org/" target="_blank" rel="noopener">${ico("pomosht", "ico")}<span>Нужна ти е помощ? BeGambleAware</span><span class="str">${ico("str")}</span></a>
      </div></section>`;
  }
  function dobaviKalendar() {
    const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//The Green Room//BG//", "CALSCALE:GREGORIAN", "BEGIN:VEVENT",
      "UID:greenroom-daily-" + Date.now() + "@greenroom", "DTSTAMP:20260101T170000Z", "DTSTART:20260101T180000", "RRULE:FREQ=DAILY",
      "SUMMARY:The Green Room — виж прогнозите за деня", "DESCRIPTION:Отвори The Green Room и виж днешните прогнози и Топ 5 на деня.",
      "BEGIN:VALARM", "TRIGGER:-PT10M", "ACTION:DISPLAY", "DESCRIPTION:The Green Room", "END:VALARM", "END:VEVENT", "END:VCALENDAR"].join("\r\n");
    try {
      const blob = new Blob([ics], { type: "text/calendar" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "green-room-napomnyach.ics"; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      toast("Напомнячът е свален — отвори го, за да го добавиш в календара.");
    } catch (e) { toast("Календарът не се поддържа тук."); }
  }
  function wrappedSek(d) {
    if (!d || !d.dnes) return "";
    let dni; try { dni = new Set(Array.from({ length: 7 }, (_, i) => new Date(new Date(d.dnes + "T12:00:00Z").getTime() - i * 864e5).toISOString().slice(0, 10))); } catch (e) { return ""; }
    const rez = (d.rezultati || []).filter((r) => dni.has(r.den) && (r.poznata === true || r.poznata === false));
    if (rez.length < 5) return "";
    const wins = rez.filter((r) => r.poznata === true).length, proc = Math.round(100 * wins / rez.length);
    let units = 0; for (const r of rez) units += r.poznata === true ? ((Number(r.koef) || 1) - 1) : -1;
    const bySport = {}; for (const r of rez) { const s = r.sport_bg || r.sport || "—"; (bySport[s] = bySport[s] || { n: 0, w: 0 }); bySport[s].n++; if (r.poznata === true) bySport[s].w++; }
    let bestSport = null, bestPct = -1; for (const s in bySport) { const v = bySport[s]; if (v.n >= 3) { const p = v.w / v.n; if (p > bestPct) { bestPct = p; bestSport = s + " " + Math.round(p * 100) + "%"; } } }
    const byDen = {}; for (const r of rez) if (r.poznata === true) byDen[r.den] = (byDen[r.den] || 0) + 1;
    let bestDen = null, bestDenN = 0; for (const dd in byDen) if (byDen[dd] > bestDenN) { bestDenN = byDen[dd]; bestDen = dd; }
    return `<section class="sekcia wrapped-sek"><header><h2>Седмицата в цифри</h2><span class="scen-min">последни 7 дни</span></header>
      <div class="wr-grid">
        <div class="wr-big"><b data-count="${proc}" data-suf="%">${proc}%</b><span>успеваемост · ${wins}/${rez.length}</span></div>
        <div class="wr-tiles">
          <div class="wr-t"><b class="${units >= 0 ? "poz" : "neg"}">${units >= 0 ? "+" : ""}${units.toFixed(1)}</b><span>юнита (1 залог)</span></div>
          <div class="wr-t"><b>${S.streak || 0}</b><span>серия дни</span></div>
          ${bestSport ? `<div class="wr-t"><b class="sm">${esc(bestSport)}</b><span>най-добър спорт</span></div>` : ""}
          ${bestDen ? `<div class="wr-t"><b class="sm">${esc(denEt(bestDen))} · ${bestDenN}</b><span>най-добър ден</span></div>` : ""}
        </div>
      </div>
      <p class="wr-note">Обзор на нашите оценени прогнози за 7 дни — честно, с юнитите (по-вярно от голия процент).</p></section>`;
  }
  function ekranProfil() {
    const m = S.me || {};
    const d = S.data || {};
    const o = d.obshto || {};
    return ramka(null, `
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/profil-karta.png')"></div>
        <div class="hero-copy"><p class="eyebrow">Член · The Green Room</p><h1>Твоята Green Room</h1></div>
      </div>
      <section class="prof"><span class="av">${esc(inicial(m.email))}</span><h2>${esc(m.email)}</h2>
        <span class="znachka ${esc(m.admin ? "admin" : m.status)}">${esc(statusTxt(m))}</span></section>
      ${!m.admin && m.status === "active" && m.days_left != null && m.days_left <= 3 ? `<div class="preduprezhdenie">${ico("kalendar")}<span>Достъпът ти изтича след <b>${esc(m.days_left)} ${m.days_left === 1 ? "ден" : "дни"}</b>. Пиши на <a href="${TG}" target="_blank" rel="noopener">съпорта</a>, за да го продължиш.</span></div>` : ""}
      <div class="plochki" style="margin-top:12px">
        <div class="plochka"><b>${esc((d.prognozi || []).length)}</b><span>прогнози сега</span></div>
        <div class="plochka"><b>${esc((d.fishove || []).filter((f) => f.status === "v_igra").length)}</b><span>фиша в игра</span></div>
        <div class="plochka"><b class="em">${o.uspeh != null ? esc(o.uspeh) + "%" : "—"}</b><span>успеваемост · ${esc(o.n || 0)} прогнози / 30 дни</span></div></div>
      ${wrappedSek(d)}
      <button class="scen-entry" data-ics="1"><span class="scen-entry-ik">${ico("kalendar", "ico")}</span><div><b>Дневен напомняч</b><span>Добави в календара — да не пропускаш деня</span></div><span class="str">${ico("str")}</span></button>
      ${znachkiSekcia()}
      ${refKart()}
      ${nastroykiSekcia()}
      ${rgSekcia()}
      <section class="sekcia"><div class="meniu">
        ${m.admin ? "" : `<div class="info-red">${ico("kalendar")}<span>Достъп до</span><span>${esc(datBg(m.access_until))}</span></div>`}
        <div class="info-red">${ico("poshta")}<span>Регистриран</span><span>${esc(datBg(m.registered))}</span></div>
        ${m.admin ? `<button data-admin="1">${ico("shtit")}<span>Админ панел</span><span class="str">${ico("str")}</span></button>` : ""}
        <button data-pokani="1">${ico("spodeliik")}<span>Доведи приятел</span><span class="str">${ico("str")}</span></button>
        <a href="${TG}" target="_blank" rel="noopener">${ico("pomosht")}<span>Съпорт в Telegram</span><span class="str">${ico("str")}</span></a>
        <a href="${TGRUPA}" target="_blank" rel="noopener">${ico("obshtnost")}<span>Нашата общност в Telegram</span><span class="str">${ico("str")}</span></a>
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
  function ekranVhod(rejim, greshka, email) {
    const reg = rejim === "reg";
    $app.innerHTML = `<main class="vhod"><div class="vhod-k">
      <img class="logo-g" src="/logo.svg" alt=""><div class="the">— THE —</div><div class="gr">GREEN ROOM</div>
      <div class="motto">Повече от прогнози. По-умни решения.</div>
      <div class="vhod-kutia"><h1>${reg ? "Създай профил" : "Добре дошъл!"}</h1>
        <p>${reg ? "Новият профил получава 21 дни пълен достъп." : "Влез в своя свят на анализи и прогнози."}</p>
        <form id="f-vhod" novalidate>
          <label class="pole"><span>Имейл</span><span class="vhod-p">${ico("poshta")}<input id="v-email" type="email" autocomplete="email" placeholder="ime@primer.bg" value="${esc(email || "")}" required></span></label>
          <label class="pole"><span>Парола</span><span class="vhod-p">${ico("kliuch")}<input id="v-pass" type="password" autocomplete="${reg ? "new-password" : "current-password"}" placeholder="${reg ? "поне 8 знака" : "паролата ти"}" minlength="8" required>
            <button type="button" class="oko" data-oko="1" aria-pressed="false" aria-label="Покажи паролата">${ico("oko")}</button></span></label>
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
      const r = await api("POST", reg ? "/api/register" : "/api/login", reg && flag("gr_ref") ? { email, password, ref: flag("gr_ref") } : { email, password });
      b.disabled = false;
      if (r.s === 200 || r.s === 201) { S.me = r.j; await start(); } else ekranVhod(rejim, r.j.error || "Грешка " + r.s, email);
    });
    $app.querySelector("[data-rejim]").addEventListener("click", (e) => ekranVhod(e.currentTarget.dataset.rejim));
    $app.querySelector("[data-oko]").addEventListener("click", (e) => { const i = document.getElementById("v-pass"); const pok = i.type === "password"; i.type = pok ? "text" : "password"; const b = e.currentTarget; b.setAttribute("aria-pressed", pok ? "true" : "false"); b.setAttribute("aria-label", pok ? "Скрий паролата" : "Покажи паролата"); });
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
    try { localStorage.removeItem("gr_me"); localStorage.removeItem("gr_data"); } catch (e) { /* */ }
    Object.assign(S, { me: null, data: null, admin: null, adminRejim: false, tab: "nachalo" });
    ekranVhod("vhod");
  }

  /* ── ГОСТ: стойност ПРЕДИ стената (реален трак-рекорд + 1 безплатен пик) ── */
  function gostPik(f) {
    if (!f) return "";
    const pr = f.procent;
    return `<article class="gost-pik">
      <div class="gp-ribbon">${ico("diamant", "badge-ik")} Безплатен пик на деня</div>
      <div class="gp-h">${ik(f.sport, "ik s")}<span class="liga">${esc(f.sport_bg)}${f.liga ? " · " + esc(f.liga) : ""}</span><span class="den">${esc(denEt(f.den))}</span></div>
      <div class="gp-mach"><div class="gp-tim">${ekip(f.dom)}<span>${esc(f.dom)}</span></div><div class="gp-vs">VS</div><div class="gp-tim d">${ekip(f.gost)}<span>${esc(f.gost)}</span></div></div>
      <div class="gp-izbor"><div class="gp-izb"><small>Нашата прогноза</small><b>${esc(izborTxt(f.izbor))}</b></div>
        ${f.koef ? `<div class="gp-koef"><small>Коеф.</small><b>${esc(fmtKoef(f.koef))}</b></div>` : ""}
        ${pr ? `<div class="pk-ring" style="--p:${esc(pr)}"><b>${esc(pr)}%</b><small>увереност</small></div>` : ""}</div>
      ${f.zashto ? `<p class="pk-zashto"><b>Защо?</b> ${esc(f.zashto)}</p>` : ""}</article>`;
  }
  function ekranGost() {
    const g = S.preview || {};
    const t = g.track || {};
    const ima = t.uspeh != null;
    const pokana = flag("gr_ref");
    const ostavat = Math.max(0, (g.broy_dnes || 0) - (g.free ? 1 : 0));
    const bari = (g.statistika || []).map((s) =>
      `<div class="gtb"><span class="gtb-sp">${esc(s.sport_bg)}</span><div class="gtb-bar"><i style="width:${Math.max(4, Math.min(100, s.uspeh))}%"></i></div><b>${esc(s.uspeh)}%</b><small>${esc(s.n)} прогн.</small></div>`).join("");
    const zakl = [
      ostavat > 0 ? `Още <b>${ostavat}</b> ${ostavat === 1 ? "прогноза" : "прогнози"} за днес` : "Прогнози с обяснение всеки ден",
      "Фишове на деня + твой собствен фиш",
      "Турнир „Зелен фиш“ · мери се с модела и тълпата",
      "Стойностни залози (EV) + Kelly калкулатор",
      "Класирания, форма и мач-стаи на живо",
    ];
    $app.innerHTML = `<main class="gost">
      <header class="gost-top">
        <img class="logo-g" src="/logo.svg" alt=""><div class="the">— THE —</div><div class="gr">GREEN ROOM</div>
        <div class="motto">Повече от прогнози. По-умни решения.</div>
      </header>
      <div class="gost-hero"><div class="gost-fig" style="background-image:url('/img/gost-heroy.jpg')" role="img" aria-label="Домакинът на The Green Room"></div></div>
      ${pokana ? `<div class="gost-pokana"><span class="gp-tick">🎟️</span> Имаш покана от приятел — <b>+7 дни бонус</b> при регистрация.</div>` : ""}
      <section class="gost-proof">
        <div class="gp-headline"><h1>Виж защо ни се доверяват — преди да влезеш.</h1>
          <p>Показваме реалната си успеваемост, не хиперболи. Ето числата от последните ${esc(t.dni || 30)} дни.</p></div>
        ${ima ? `<div class="gost-rekord">
          <div class="gr-big"><b data-count="${esc(t.uspeh)}" data-suf="%">${esc(t.uspeh)}%</b><span>успеваемост</span></div>
          <div class="gr-meta"><div><b>${esc(t.n || 0)}</b><span>оценени прогнози</span></div><div><b>${esc(t.dni || 30)}</b><span>дни назад</span></div></div>
        </div>${bari ? `<div class="gost-bari">${bari}</div>` : ""}` : `<p class="prazno">Числата се обновяват — влез, за да видиш пълната картина.</p>`}
      </section>
      ${g.free ? `<section class="gost-free"><h2>Ето какво получаваш всеки ден</h2>${gostPik(g.free)}</section>` : ""}
      <section class="gost-zakl">
        <div class="gz-h"><span class="gz-lock">${ico("kliuch", "ico")}</span><b>Зад стената те чака</b></div>
        <ul>${zakl.map((x) => `<li><span class="li-chek">✓</span><span>${x}</span></li>`).join("")}</ul>
      </section>
      <section class="gost-cta">
        <button class="btn full" data-gost="reg">Създай безплатен профил <span class="cta-sub">21 дни пълен достъп</span></button>
        <button class="btn v2 full" data-gost="vhod">Вече имам профил — вход</button>
        <p class="gost-fine">Анализ, не гаранция за печалба. Само за 18+. Играй отговорно.</p>
      </section>
      <a class="tg-banner" href="${TGRUPA}" target="_blank" rel="noopener">
        <span class="ik">${ico("tg", "ico")}</span>
        <div><b>Влез и в общността в Telegram</b><span>Ежедневни прогнози, разбор и въпроси на живо.</span></div>
        <span class="str">${ico("str")}</span></a>
    </main>`;
    animCount();
  }
  async function zapochniGost() {
    try { const r = await api("GET", "/api/preview"); S.preview = (r.s === 200 && r.j && r.j.guest) ? r.j : null; }
    catch (e) { S.preview = null; }
    ekranGost();
  }

  /* ── основното ── */
  function animCount() {
    try {
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      $app.querySelectorAll("[data-count]").forEach((el) => {
        const to = Number(el.getAttribute("data-count")) || 0, suf = el.getAttribute("data-suf") || "";
        if (to <= 0) { el.textContent = to + suf; return; }
        const dur = 620, t0 = performance.now();
        const step = (t) => { const p = Math.min(1, (t - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))) + suf; if (p < 1) requestAnimationFrame(step); };
        requestAnimationFrame(step);
      });
    } catch (e) { /* без анимация */ }
  }
  // ── ОНБОРДИНГ (първо стартиране, показва се веднъж) ──
  function onboardingHtml() {
    const slides = [
      { ik: "🎯", t: "Добре дошъл в The Green Room", p: "Умни спортни прогнози, анализи и стойностни залози — на едно премиум място." },
      { ik: "📊", t: "Честни проценти", p: "Показваме реалната си калибрация и доходност, не хиперболи. Кажем ли 66%, то е измерено." },
      { ik: "🏆", t: "Играй турнира", p: "Предскажи мачовете, мери се с модела и тълпата, качвай се в класацията." },
    ];
    const i = Math.min(S.onbStep || 0, slides.length - 1), s = slides[i], last = i === slides.length - 1;
    return `<div class="onb-kart">
      <div class="onb-ik">${s.ik}</div><h2>${esc(s.t)}</h2><p>${esc(s.p)}</p>
      <div class="onb-dots">${slides.map((_, j) => `<i class="${j === i ? "on" : ""}"></i>`).join("")}</div>
      <button class="btn full" data-onb="${last ? "done" : "next"}">${last ? "Започни" : "Напред"}</button>
      ${last ? "" : `<button class="onb-skip" data-onb="done">Пропусни</button>`}</div>`;
  }
  function pokazhiOnboarding() {
    if (flag("gr_onboarded") === "1" || document.getElementById("onb-root")) return;
    S.onbStep = 0;
    const div = document.createElement("div"); div.id = "onb-root"; div.className = "onb-overlay";
    const draw = () => { div.innerHTML = onboardingHtml(); };
    draw();
    div.addEventListener("click", (e) => {
      const b = e.target.closest("[data-onb]"); if (!b) return;
      if (b.getAttribute("data-onb") === "done") { flag("gr_onboarded", "1"); div.remove(); return; }
      S.onbStep = (S.onbStep || 0) + 1; draw();
    });
    document.body.appendChild(div);
  }
  function render() {
    if (!S.me) return ekranVhod("vhod");
    const f = S.adminRejim ? ekranAdmin : ({ nachalo: ekranNachalo, sport: ekranSport, live: ekranLive, prognozi: ekranPrognozi, scenario: ekranScenario, mach: ekranMach, fishove: ekranFishove,
      rezultati: ekranRezultati, novini: ekranNovini, profil: ekranProfil, turnir: ekranTurnir }[S.tab] || ekranNachalo);
    $app.innerHTML = f();
    animCount();
    proveriMisii();
  }
  // Плавен преход между екрани (View Transitions) — една жива повърхност вместо твърд разрез.
  // Пада обратно към gr-enter анимацията, ако браузърът не поддържа или е изключено движението.
  function prehod(fn) {
    try {
      if (document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
        document.documentElement.classList.add("vt");
        const t = document.startViewTransition(() => fn());
        // прекъснат преход (бърза смяна на табове / скрит таб) отхвърля ready/finished — поглъщаме и двете
        if (t && t.ready && t.ready.catch) t.ready.catch(() => {});
        (t && t.finished ? t.finished : Promise.resolve()).catch(() => {}).finally(() => document.documentElement.classList.remove("vt"));
        return;
      }
    } catch (e) { /* fallback долу */ }
    fn();
  }
  const idi = (tab) => { S.tab = tab; S.adminRejim = false; prehod(render); window.scrollTo(0, 0); };

  $app.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t || !$app.contains(t)) return;
    const ds = t.dataset;
    if (ds.gost) return ekranVhod(ds.gost);
    if (ds.cmdk) return otvoriPaletka();
    if (ds.vcheraX) { flag("gr_vchera", (S.data && S.data.dnes) || "1"); const el = t.closest(".vchera"); if (el) el.remove(); return; }
    if (ds.tab) { if (ds.tab !== "sport") S.sport = null; return idi(ds.tab); }
    if (ds.predskazhi) {
      const parts = String(ds.predskazhi).split("~");
      const iz = parts[0], den = parts[1], sp = parts[2], mk = parts.slice(3).join("~");
      return api("POST", "/api/predskazhi", { match_key: mk, izbor: iz, den: den, sport: sp }).then((r) => {
        if (r.s === 200) { broy("turnir", 1); questSet("turnir"); praznik(t); return zarediTurnir().then((ok) => { if (ok) render(); }); }
        toast((r.j && r.j.error) || "Не се записа."); });
    }
    if (ds.idi === "turnir") { S.sport = null; S.tab = "turnir"; if (!S.turnir) return zarediTurnir().then((ok) => { if (ok) render(); }); return render(); }
    if (ds.idi) { S.sport = null; return idi(ds.idi); }
    if (ds.mach !== undefined) { broy("mach", 1); S.machK = ((S.data && S.data.prognozi) || []).find((p) => p.id === ds.mach) || null; S.machTab = "obzor"; return idi("mach"); }
    if (ds.sport !== undefined) { S.sport = ds.sport || null; S.sportTab = "prog"; return idi("sport"); }
    if (ds.stab) { S.sportTab = ds.stab; return render(); }
    if (ds.nsport !== undefined) { S.novSport = ds.nsport; return render(); }
    if (ds.pkview) { S.pkView = ds.pkview; return render(); }
    if (ds.scen) {
      if (!S.scen) return render();
      const a = ds.scen;
      if (a === "reset") S.scen = { id: S.scen.id, gh: 0, gg: 0, red: null, minute: 0 };
      else if (a === "gol-dom") S.scen.gh = Math.min(9, S.scen.gh + 1);
      else if (a === "gol-gost") S.scen.gg = Math.min(9, S.scen.gg + 1);
      else if (a === "red-dom") S.scen.red = S.scen.red === "dom" ? null : "dom";
      else if (a === "red-gost") S.scen.red = S.scen.red === "gost" ? null : "gost";
      else if (a.slice(0, 4) === "min:") S.scen.minute = parseInt(a.slice(4), 10) || 0;
      return render();
    }
    if (ds.spodelipik) { spodeliPik(S.machK); return; }
    if (ds.sledi) { slediOtbor(ds.sledi); return render(); }
    if (ds.izvestiya) { if (flag("gr_push") === "1") { flag("gr_push", "0"); toast("Известията са изключени."); return render(); } return vklyuchiIzvestiya(); }
    if (ds.refcopy) { (async () => { try { await navigator.clipboard.writeText(ds.refcopy); toast("Линкът е копиран — прати го на приятел."); } catch (e) { try { await navigator.share({ title: "The Green Room", text: ds.refcopy }); } catch (e2) { prompt("Копирай линка:", ds.refcopy); } } })(); return; }
    if (ds.koeffmt) { flag("gr_koef_fmt", ds.koeffmt); return render(); }
    if (ds.toggle) { flag(ds.toggle, flag(ds.toggle) === "1" ? "0" : "1"); prilozhiRezhim(); return render(); }
    if (ds.klidx !== undefined) { S.klIdx = Number(ds.klidx); return render(); }
    if (ds.bank) { flag("gr_bank", ds.bank); return render(); }
    if (ds.kfrac) { flag("gr_kfrac", ds.kfrac); return render(); }
    if (ds.ptab) { S.progTab = ds.ptab; S.calDen = null; return render(); }
    if (ds.calden !== undefined) { S.calDen = ds.calden || null; if (S.calDen) S.progTab = "vsichki"; return render(); }
    if (ds.psort) { S.progSort = ds.psort; return render(); }
    if (ds.lfav) { S.samoLyubimi = !S.samoLyubimi; return render(); }
    if (ds.stoynost) { S.samoStoynost = !S.samoStoynost; return render(); }
    if (ds.zvezda) { toggleLyubim(ds.zvezda); if (S.samoLyubimi) return render(); obnoviZvezda(t); obnoviLfav(); return; }
    if (ds.psport !== undefined) { S.progSport = ds.psport; return render(); }
    if (ds.ftab) { S.fishTab = ds.ftab; return render(); }
    if (ds.zapishi) return zapishiZalog();
    if (ds.ics) return dobaviKalendar();
    if (ds.pfmaha) { if (!confirm("Да изтрия ли този залог от портфейла?")) return; paziPortfeil(portfeil().filter((b) => b.id !== ds.pfmaha)); return render(); }
    if (ds.rez) { S.rezDen = ds.rez; return render(); }
    if (ds.slip) { broy("fish", 1); questSet("fish"); toggleSlip(ds.slip); obnoviDob(t, ds.slip); obnoviPill(); return; }
    if (ds.maha) { S.slip = S.slip.filter((x) => x.id !== ds.maha); pazi(); return render(); }
    if (ds.izchisti) { S.slip = []; pazi(); return render(); }
    if (ds.suma) { S.suma = Number(ds.suma); pazi(); return render(); }
    if (ds.spodeli) return spodeli();
    if (ds.pokani) return pokani();
    if (ds.kopirai) return kopirai();
    if (ds.moi) { S.fishTab = "moi"; return idi("fishove"); }
    if (ds.svezhi) return opresni();
    if (ds.sptab) { S.spTab = ds.sptab; return render(); }
    if (ds.pwa) return pwaInstalirai();
    if (ds.pwaX) { flag("gr_pwa_skrit", "1"); const el = t.closest(".pwa-lenta"); if (el) el.remove(); return; }
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
    else if (id === "f-suma") {
      S.suma = Math.max(0, Number(e.target.value) || 0);
      pazi();
      const k = slipKoef();
      const el = document.getElementById("f-pech");
      if (el) el.textContent = k ? (Math.round(S.suma * k * 100) / 100).toFixed(2) + " €" : "—";
      const rk = document.getElementById("f-risk");
      if (rk) rk.textContent = (Number(S.suma) || 0).toFixed(2) + " €";
      const sr = document.getElementById("sis-redove");
      if (sr) { sr.innerHTML = sistemaRedove(); const sp = document.getElementById("sis-perline"); if (sp) sp.textContent = (Math.max(1, Number(S.suma) || 0)).toFixed(2) + " €"; }
      $app.querySelectorAll(".brzi button").forEach((b) => b.classList.toggle("on", Number(b.dataset.suma) === S.suma));
    }
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

  /* ── опресняване ── */
  async function opresni() {
    if (S.svezhVarti) return;
    S.svezhVarti = true;
    const b = $app.querySelector(".svezhо");
    if (b) b.classList.add("varti");
    const ok = await zarediDanni();
    S.svezhVarti = false;
    if (ok) { render(); toast("Обновено."); }
  }

  /* ── водачът при първо влизане ── */
  const VODACH = [
    { ik: "prognozi", h: "Прогнози с обяснение", p: "Всеки мач идва с нашата прогноза, коефициента и кратко „защо“ го избираме. Филтрирай по спорт, ден или гледай само топ избора." },
    { ik: "fishove", h: "Събери свой фиш", p: "Хареса ли ти избор — натисни „Добави във фиша“. В таб „Фишове → Моят фиш“ виждаш общия коефициент и възможната печалба." },
    { ik: "rezultati", h: "Виждаш всичко честно", p: "Резултатите показват кои прогнози са познати и успеваемостта по спорт. Нищо скрито — по-добри играчи, по-умни решения." },
  ];
  function vodachHtml() {
    const i = S.vodachI || 0;
    const s = VODACH[i];
    return `<div class="vodach" role="dialog" aria-modal="true" aria-label="Кратко въведение в The Green Room"><div class="vodach-k">
      <span class="ik">${ico(s.ik, "ico")}</span><h3>${esc(s.h)}</h3><p>${esc(s.p)}</p>
      <div class="tochki">${VODACH.map((_, k) => `<i class="${k === i ? "on" : ""}"></i>`).join("")}</div>
      <div class="redba">${i > 0 ? '<button class="btn v2" data-vodach-naz="1">Назад</button>' : ""}
        <button class="btn" ${i < VODACH.length - 1 ? 'data-vodach-nap="1"' : 'data-vodach-kraj="1"'}>${i < VODACH.length - 1 ? "Напред" : "Разбрах, започвам!"}</button></div>
      <button class="propusni" data-vodach-kraj="1">Пропусни</button></div></div>`;
  }
  function vodachNode() {
    const w = document.createElement("div");
    w.innerHTML = vodachHtml();
    const el = w.firstElementChild;
    const predi = document.activeElement;
    const zatvori = () => { flag("gr_vodach", "1"); el.remove(); document.removeEventListener("keydown", onKey); try { predi && predi.focus && predi.focus(); } catch (e) { /* няма къде */ } };
    // Esc затваря + капан за фокуса (модалът е извън #app)
    function onKey(e) {
      if (e.key === "Escape") return zatvori();
      if (e.key !== "Tab") return;
      const f = [...el.querySelectorAll("button")].filter((b) => b.offsetParent !== null);
      if (!f.length) return;
      const pyrvi = f[0], posl = f[f.length - 1];
      if (e.shiftKey && document.activeElement === pyrvi) { e.preventDefault(); posl.focus(); }
      else if (!e.shiftKey && document.activeElement === posl) { e.preventDefault(); pyrvi.focus(); }
    }
    document.addEventListener("keydown", onKey);
    // водачът е извън #app, затова носи собствен обработчик
    el.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.dataset.vodachNap) vodachStapka(1);
      else if (b.dataset.vodachNaz) vodachStapka(-1);
      else if (b.dataset.vodachKraj) zatvori();
    });
    setTimeout(() => { const f = el.querySelector(".redba .btn"); if (f) f.focus(); }, 0);
    return el;
  }
  function pokazhiVodach() {
    if (flag("gr_vodach")) return;
    S.vodachI = 0;
    document.body.appendChild(vodachNode());
  }
  function vodachStapka(d) {
    S.vodachI = Math.max(0, Math.min(VODACH.length - 1, (S.vodachI || 0) + d));
    const el = document.querySelector(".vodach");
    if (el) el.replaceWith(vodachNode());
  }

  /* ── «сложи на телефона» ── */
  let pwaEvt = null;
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); pwaEvt = e; });
  async function pwaInstalirai() {
    if (!pwaEvt) return toast("В менюто на браузъра избери „Добави към началния екран“.");
    pwaEvt.prompt();
    try { await pwaEvt.userChoice; } catch (e) { /* */ }
    pwaEvt = null;
    flag("gr_pwa_skrit", "1");
    const el = $app.querySelector(".pwa-lenta");
    if (el) el.remove();
  }

  /* Кеш на данните (за мигновен екран на връщащия се). Пази се без me; годен до 12ч. */
  function paziDanni(b) {
    try { const c = { ...b }; delete c.me; localStorage.setItem("gr_data", JSON.stringify({ ts: Date.now(), d: c })); } catch (e) { /* пълно хранилище/личен режим */ }
  }
  function chetiDanni() {
    try { const o = JSON.parse(localStorage.getItem("gr_data") || "null"); if (o && o.d && o.ts && Date.now() - o.ts < 12 * 3600e3) return o.d; } catch (e) { /* */ }
    return null;
  }
  function paziMe(m) { try { if (m) localStorage.setItem("gr_me", JSON.stringify(m)); } catch (e) { /* */ } }
  function chetiMe() { try { const m = JSON.parse(localStorage.getItem("gr_me") || "null"); return m && m.email ? m : null; } catch (e) { return null; } }
  const skeletHtml = '<div class="skelet" style="margin-top:16px"><div class="sk" style="height:186px"></div><div class="sk k"></div><div class="sk"></div><div class="sk"></div></div>';
  function splash() { return `<main class="vhod"><div class="vhod-k"><img class="logo-g" src="/logo.svg" alt=""><div class="the">— THE —</div><div class="gr">GREEN ROOM</div><div class="motto">Зареждаме…</div></div></main>`; }
  async function zarediDanni() {
    const r = await api("GET", "/api/data");
    if (r.s === 200) { S.data = r.j; if (r.j.me) { S.me = r.j.me; paziMe(S.me); } S.novi = noviBroy(); paziDanni(r.j); return true; }
    if (r.s === 401) { S.me = null; ekranVhod("vhod"); return false; }
    if (r.s === 403) { ekranIzteklo(r.j.error); return false; }
    toast(r.j.error || "Данните не се заредиха. Опитай пак.");
    return true;
  }
  async function start() {
    prilozhiRezhim();
    S.streak = updateStreak();
    // Мигновен екран за връщащия се от кеша (кеширан me + данни), без да чакаме мрежата.
    const cm = chetiMe(), cd = chetiDanni();
    if (!S.me && cm && cm.active) S.me = cm;
    if (S.me && S.me.active && cd) { S.data = { ...cd, me: S.me }; S.novi = noviBroy(); render(); }
    else if (S.me && S.me.active) $app.innerHTML = ramka(null, skeletHtml);
    else $app.innerHTML = splash(); // непознат посетител: неутрален бранд сплаш, не app рамка
    // ЕДНА заявка носи и данните, и me (слято /api/me → −1 round-trip на старта).
    const r = await api("GET", "/api/data");
    if (r.s === 200) {
      if (r.j.me) { S.me = r.j.me; paziMe(S.me); }
      if (!S.me || !S.me.active) return ekranIzteklo((S.me && S.me.message) || "");
      S.data = r.j; S.novi = noviBroy(); paziDanni(r.j);
      render(); pokazhiVodach();
      if (S.strUp) { const el = $app.querySelector(".streak-znak"); if (el) praznik(el); if (S.strMilestone) setTimeout(() => toast(S.strMilestone), 400); }
      return;
    }
    if (r.s === 401) { S.me = null; return zapochniGost(); }
    if (r.s === 403) return ekranIzteklo(r.j.error);
    // мрежов проблем: ако имаме кеширан екран — остани на него; иначе покажи госта
    if (S.me && S.data) { toast(r.j.error || "Данните се обновяват. Опитай пак."); render(); }
    else return zapochniGost();
  }
  setInterval(async () => {
    if (document.visibilityState !== "visible" || !S.me || !S.me.active || S.adminRejim) return;
    const a = document.activeElement;
    if (a && a.tagName === "INPUT") return; // не пречи на търсенето
    if (await zarediDanni()) render();
  }, 5 * 60 * 1000);

  // Cmd+K / „/" командна палитра — глобално търсене на мач/отбор/лига + бърза навигация
  function otvoriPaletka() {
    if (!S.me || !S.me.active || document.getElementById("cmdk")) return;
    const NAV = [["nachalo", "Начало"], ["prognozi", "Прогнози"], ["sport", "Спорт"], ["live", "На живо"], ["rezultati", "Резултати"], ["novini", "Новини"], ["turnir", "Турнир"], ["scenario", "Сценарии"], ["fishove", "Моят фиш"], ["profil", "Профил"]];
    const div = document.createElement("div"); div.id = "cmdk"; div.className = "cmdk";
    div.innerHTML = `<div class="cmdk-box" role="dialog" aria-label="Търсене"><div class="cmdk-inp">${ico("tarsi", "ico")}<input id="cmdk-in" type="text" placeholder="Търси мач, отбор, лига или екран…" autocomplete="off" spellcheck="false"></div><div class="cmdk-res" id="cmdk-res"></div><div class="cmdk-hint">↑↓ навигация · ↵ отвори · Esc затвори</div></div>`;
    document.body.appendChild(div);
    const inp = div.querySelector("#cmdk-in"), res = div.querySelector("#cmdk-res");
    let items = [], sel = 0;
    const zatvori = () => { div.remove(); document.removeEventListener("keydown", onKey, true); };
    const izpylni = (it) => {
      if (!it) return; zatvori();
      if (it.type === "nav") { if (it.k === "turnir") { S.sport = null; S.tab = "turnir"; if (!S.turnir) return zarediTurnir().then((ok) => { if (ok) render(); }); return render(); } return idi(it.k); }
      S.machK = ((S.data && S.data.prognozi) || []).find((p) => p.id === it.id) || null;
      if (S.machK) { S.machTab = "obzor"; idi("mach"); }
    };
    const build = (q) => {
      q = q.trim().toLowerCase();
      const nav = NAV.filter(([k, t]) => !q || t.toLowerCase().includes(q)).map(([k, t]) => ({ type: "nav", k, t }));
      let mch = [];
      if (q) { mch = ((S.data && S.data.prognozi) || []).filter((p) => (p.dom + " " + p.gost + " " + (p.liga || "") + " " + (p.sport_bg || "")).toLowerCase().includes(q)).slice(0, 8).map((p) => ({ type: "mach", id: p.id, t: p.dom + " — " + p.gost, sub: (p.sport_bg || "") + (p.liga ? " · " + p.liga : "") })); }
      items = q ? [...mch, ...nav] : nav; sel = 0; draw();
    };
    const draw = () => {
      res.innerHTML = items.length ? items.map((it, i) => `<button class="cmdk-it${i === sel ? " on" : ""}" data-i="${i}"><span class="cmdk-ik">${it.type === "mach" ? "🎯" : "→"}</span><span class="cmdk-t">${esc(it.t)}</span>${it.sub ? `<span class="cmdk-sub">${esc(it.sub)}</span>` : it.type === "nav" ? `<span class="cmdk-sub">Екран</span>` : ""}</button>`).join("") : `<div class="cmdk-prazno">Няма съвпадения</div>`;
    };
    function onKey(e) {
      if (e.key === "Escape") { e.preventDefault(); return zatvori(); }
      if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(items.length - 1, sel + 1); draw(); scrollSel(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(0, sel - 1); draw(); scrollSel(); }
      else if (e.key === "Enter") { e.preventDefault(); izpylni(items[sel]); }
    }
    const scrollSel = () => { const el = res.querySelector(".cmdk-it.on"); if (el) el.scrollIntoView({ block: "nearest" }); };
    document.addEventListener("keydown", onKey, true);
    res.addEventListener("click", (e) => { const b = e.target.closest("[data-i]"); if (b) izpylni(items[Number(b.dataset.i)]); });
    div.addEventListener("click", (e) => { if (e.target === div) zatvori(); });
    inp.addEventListener("input", () => build(inp.value));
    build("");
    setTimeout(() => inp.focus(), 30);
  }
  document.addEventListener("keydown", (e) => {
    const k = e.key.toLowerCase();
    if ((e.metaKey || e.ctrlKey) && k === "k") { e.preventDefault(); return otvoriPaletka(); }
    const t = e.target, inField = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
    if (k === "/" && !inField && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); otvoriPaletka(); }
  });

  // 18+ гейт при първо влизане (еднократно; комплайънс за хазартно-съседен апп)
  function pokazhi18(onOk) {
    const div = document.createElement("div"); div.id = "g18-root"; div.className = "gate18";
    div.innerHTML = `<div class="g18-k">
      <img class="logo-g" src="/logo.svg" alt=""><div class="g18-gr">GREEN ROOM</div>
      <div class="g18-badge">18+</div>
      <h2>Само за пълнолетни</h2>
      <p>The Green Room е <b>аналитична</b> платформа за спортни прогнози. Съдържанието е за лица на 18 и повече години. Ние сме анализ — <b>не букмейкър</b>: не приемаме залози и не държим пари. Играй отговорно.</p>
      <button class="btn full" data-g18="ok">Да, навършил съм 18 години</button>
      <button class="btn v2 full" data-g18="no">Не съм</button></div>`;
    div.addEventListener("click", (e) => {
      const b = e.target.closest("[data-g18]"); if (!b) return;
      if (b.dataset.g18 === "ok") { flag("gr_18", "1"); div.remove(); onOk(); }
      else { div.querySelector(".g18-k").innerHTML = `<div class="g18-gr">GREEN ROOM</div><div class="g18-badge">18+</div><h2>Съжаляваме</h2><p>Платформата е достъпна само за лица на 18 и повече години. Моля, затвори раздела.</p>`; }
    });
    document.body.appendChild(div);
  }

  // Hero parallax/tilt — фигурата „реагира" на курсора (истинско 3D усещане). Само на мишка/тъчпад, тих при reduced-motion.
  (function heroTilt() {
    try {
      if (!matchMedia("(hover: hover) and (pointer: fine)").matches || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      let raf = 0, cur = null, lx = 0, ly = 0;
      const apply = () => { raf = 0; if (cur) cur.style.transform = `perspective(1000px) rotateY(${(lx * 5).toFixed(2)}deg) rotateX(${(-ly * 4).toFixed(2)}deg)`; };
      document.addEventListener("pointermove", (e) => {
        const h = e.target.closest && e.target.closest(".hero, .gost-hero");
        if (!h) { if (cur) { cur.style.transform = ""; cur = null; } return; }
        const rect = h.getBoundingClientRect(); if (!rect.width) return;
        lx = (e.clientX - (rect.left + rect.width / 2)) / rect.width;
        ly = (e.clientY - (rect.top + rect.height / 2)) / rect.height;
        cur = h;
        if (!raf) raf = requestAnimationFrame(apply);
      }, { passive: true });
    } catch (e) { /* без тилт */ }
  })();

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  }
  if (flag("gr_18") === "1") start(); else pokazhi18(start);
})();
