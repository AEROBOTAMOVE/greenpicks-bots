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
    return `<article class="pk">
      <div class="pk-h">${ik(k.sport, "ik s")}<span class="liga">${esc(k.sport_bg)}${k.liga ? " · " + esc(k.liga) : ""}</span>
        <span class="den">${esc(denEt(k.den))}</span>
        <button class="pk-zv" data-zvezda="${esc(k.id)}" aria-pressed="${vLyubim(k.id)}" aria-label="${vLyubim(k.id) ? "Премахни от любими" : "Добави в любими"}" title="Любими">${ico("zvezda", "zv-ik")}</button></div>
      <div class="pk-mach"><div class="pk-tim">${ekip(k.dom)}<span>${esc(k.dom)}</span></div><div class="pk-vs">VS</div>
        <div class="pk-tim d">${ekip(k.gost)}<span>${esc(k.gost)}</span></div></div>
      <div class="pk-izbor"><div class="pk-izb"><small>Нашата прогноза</small><b>${esc(izborTxt(k.izbor))}</b></div>
        ${k.koef ? `<div class="pk-koef"><small>Коеф.</small><b>${esc(k.koef.toFixed(2))}</b></div>`
          : '<div class="pk-koef bez"><small>Коеф.</small><b>—</b></div>'}
        ${pr ? `<div class="pk-ring" style="--p:${esc(pr)}"><b>${esc(pr)}%</b><small>увереност</small></div>` : ""}</div>
      ${pr || k.zvezdi ? `<div class="pk-dolen">${pr ? `<div class="risk-dots ${riskNiv(k).c}"><i></i><i></i><i></i></div><small class="risk-lab">${riskNiv(k).t}</small>` : ""}${k.zvezdi ? `<span class="zv" aria-label="${esc(k.zvezdi)} звезди">${zvezdi(k.zvezdi)}</span>` : ""}</div>` : ""}
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
      <div class="rz-dolu"><span>Прогноза: <b>${esc(izborTxt(k.izbor))}</b>${k.koef ? ` · ${esc(k.koef.toFixed(2))}` : ""}</span>${znak(k.poznata)}</div>
    </article>`;
  }
  function kartaFish(f) {
    const stT = { poznat: "Спечелен", nepoznat: "Загубен", v_igra: "В игра" }[f.status] || "";
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
    const nav = (cls) => NAV.map(([k, t]) => `<button data-tab="${k}" ${S.tab === k && !S.adminRejim ? 'aria-current="page"' : ""}>${ico(k)}<span>${t}</span>${k === "prognozi" && S.novi > 0 ? `<span class="nav-nov" aria-label="${S.novi} нови прогнози">${S.novi > 9 ? "9+" : S.novi}</span>` : ""}</button>`).join("");
    return `<div class="app">
      <aside class="side"><div class="marka"><img src="/logo.svg" alt=""><div class="ime"><small>THE</small>GREEN ROOM</div></div>
        <nav aria-label="Основно меню">${nav()}</nav>
        <div class="az"><span class="av">${esc(inicial(m.email))}</span><div><b>${esc(m.email || "")}</b><span>${esc(statusTxt(m))}</span></div></div></aside>
      <div>
        <div class="glaven">
          <header class="gore"><div class="marka"><img src="/logo.svg" alt=""><div class="ime"><small>THE</small>GREEN ROOM</div></div>
            ${svezhoHtml()}
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
        <div class="pk-koef"><small>Коеф. Betano</small><b>${esc(Number(v.koef).toFixed(2))}</b></div></div>
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
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/home-joker.png')"></div>
        <div class="hero-copy"><h1>${esc(pozdrav)}</h1><p class="pod">Твоята Green Room е готова.</p>
          <button class="btn full" data-idi="prognozi">Виж прогнозите ${ico("str")}</button></div>
      </div>
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
      </div>
      <a class="tg-banner" href="${TGRUPA}" target="_blank" rel="noopener">
        <span class="ik">${ico("tg", "ico")}</span>
        <div><b>Вземи апа само за една салата</b><span>Влез в общността в Telegram — ежедневни прогнози, разбор и въпроси на живо.</span></div>
        <span class="str">${ico("str")}</span></a>`);
  }

  /* ── СПОРТ ── */
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
      })()}`);
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
    if (S.progSport) x = x.filter((k) => k.sport === S.progSport);
    if (S.samoLyubimi) x = x.filter((k) => S.lyubimi.has(k.id));
    const q = S.q.trim().toLowerCase();
    if (q) x = x.filter((k) => (k.dom + " " + k.gost + " " + k.liga + " " + k.sport_bg).toLowerCase().includes(q));
    return x;
  }
  /* подредбата вътре в един ден — Днес/Утре групите остават */
  const podrF = () => S.progSort === "uv" ? (a, b) => (b.procent || 0) - (a.procent || 0) || (b.zvezdi || 0) - (a.zvezdi || 0)
    : S.progSort === "koef" ? (a, b) => (b.koef || 0) - (a.koef || 0)
      : (a, b) => (a.pusnata || "").localeCompare(b.pusnata || "");
  function listaPrognozi() {
    const x = filtriraniPrognozi();
    if (!x.length) {
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
  function valueSekcia(d) {
    const v = ((d && d.stoynost) || []).filter((x) => x && x.koef && x.ev != null).sort((a, b) => (b.ev || 0) - (a.ev || 0)).slice(0, 8);
    if (!v.length) return "";
    const karti = v.map((x) => `<div class="st-karta">
      <div class="st-top">${ik(x.sport, "ik s")}<span class="st-liga">${esc(x.liga || x.sport_bg || "")}</span></div>
      <b class="st-izbor">${esc(x.izbor || x.izhod)}</b>
      <div class="st-mach">${esc(x.dom || "")}${x.gost ? " — " + esc(x.gost) : ""}</div>
      <div class="st-dolu"><span class="st-koef">${esc(Number(x.koef).toFixed(2))}</span>
        <span class="st-ev">EV +${esc((x.ev * 100).toFixed(1))}%</span></div></div>`).join("");
    return `<section class="sekcia stoynost-sek">
      <header><h2>Стойност днес</h2><span class="st-broy">${v.length}</span></header>
      <p class="st-lead">Залози, при които коефициентът е над реалната ни вероятност — там е дългосрочното предимство.</p>
      <div class="st-redica">${karti}</div></section>`;
  }
  function ekranPrognozi() {
    markSeen();
    const d = S.data || {};
    const br = brSport();
    const sp = (d.sportove || []).filter((s) => br[s.sport]);
    const tb = [["vsichki", "Всички"], ["dnes", "Днес"], ["utre", "Утре"], ["top", "Топ"]];
    const podr = [["red", "Ред"], ["uv", "Увереност"], ["koef", "Коеф."]];
    const nl = brLyubimi();
    return ramka(null, `
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/picks-asa.png')"></div>
        <div class="hero-copy"><p class="eyebrow">Анализ · Селекция · Перспектива</p><h1>Green Room Прогнози</h1></div>
      </div>
      <button class="scen-entry" data-idi="scenario"><span class="scen-entry-ik">🎲</span><div><b>Сценарии</b><span>Симулирай мача · виж вероятностите</span></div><span class="str">${ico("str")}</span></button>
      ${valueSekcia(d)}
      <div class="tabs" style="margin-top:14px">${tb.map(([v, t]) => `<button data-ptab="${v}" aria-pressed="${S.progTab === v}">${t}</button>`).join("")}</div>
      <div class="chipove"><button class="chip lfav" data-lfav="1" aria-pressed="${S.samoLyubimi}">${ico("zvezda", "zv-ik")}Любими<b class="lfav-c">${nl ? " · " + nl : ""}</b></button>
        <button class="chip" data-psport="" aria-pressed="${!S.progSport}">Всички спортове</button>
        ${sp.map((s) => `<button class="chip" data-psport="${esc(s.sport)}" aria-pressed="${S.progSport === s.sport}">${ik(s.sport, "ik s")}${esc(s.sport_bg)} · ${br[s.sport]}</button>`).join("")}</div>
      <div class="podr"><span class="podr-et">Подреди</span>${podr.map(([v, t]) => `<button data-psort="${v}" aria-pressed="${S.progSort === v}">${t}</button>`).join("")}</div>
      <div class="tabs vt"><button data-pkview="simple" aria-pressed="${S.pkView === "simple"}">Кратко</button><button data-pkview="expert" aria-pressed="${S.pkView === "expert"}">Подробно</button></div>
      <label class="tarsene">${ico("tarsi")}<input id="p-q" type="search" placeholder="Търси отбор, играч или лига…" value="${esc(S.q)}" aria-label="Търси"></label>
      <div id="p-lista" class="pk-${S.pkView}">${listaPrognozi()}</div>`);
  }

  /* ── ФИШОВЕ ── */
  function ekranFishove() {
    const f = (S.data && S.data.fishove) || [];
    if (S.fishTab === "moi") return ekranMoiFish(f);
    const akt = f.filter((x) => x.status === "v_igra");
    const pri = f.filter((x) => x.status !== "v_igra");
    const x = S.fishTab === "aktivni" ? akt : pri;
    const pozn = pri.filter((y) => y.status === "poznat").length;
    return ramka(["Фишове", "Комбинирани фишове от нашите прогнози — с общ коефициент."], `
      <div class="tabs"><button data-ftab="aktivni" aria-pressed="${S.fishTab === "aktivni"}">В игра · ${akt.length}</button>
        <button data-ftab="priklyucheni" aria-pressed="${S.fishTab === "priklyucheni"}">Приключили · ${pri.length}</button>
        <button data-ftab="moi" aria-pressed="false">Моят фиш · ${S.slip.length}</button></div>
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
    const tabs = `<div class="tabs"><button data-ftab="aktivni" aria-pressed="false">В игра · ${akt}</button>
      <button data-ftab="priklyucheni" aria-pressed="false">Приключили · ${pri}</button>
      <button data-ftab="moi" aria-pressed="true">Моят фиш · ${S.slip.length}</button></div>`;
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
          <span class="k">${esc(Number(x.koef).toFixed(2))}<button class="maha" data-maha="${esc(x.id)}" aria-label="Махни от фиша">×</button></span>
          <span class="i">${esc(izborTxt(x.izbor))} · ${esc(denEt(x.den))}</span></li>`).join("")}</ol>
        <div class="suma-blok">
          <div class="red-k"><span>Общ коефициент</span><b>${k ? esc(k.toFixed(2)) : "—"}</b></div>
          <label class="red-k"><span>Сума (€)</span><input id="f-suma" type="number" min="1" step="1" inputmode="decimal" value="${esc(S.suma)}"></label>
          <div class="brzi">${[10, 20, 50, 100].map((v) => `<button class="${S.suma === v ? "on" : ""}" data-suma="${v}">${v} €</button>`).join("")}</div>
          <div class="red-k pech"><span>Възможна печалба</span><b id="f-pech">${pech != null ? esc(pech.toFixed(2)) + " €" : "—"}</b></div>
          <div class="fish-akcii">
            <button class="btn" data-spodeli="1">${ico("tg", "btn-ik")}Сподели</button>
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

  /* ── РЕЗУЛТАТИ ── */
  function ekranRezultati() {
    const r = (S.data && S.data.rezultati) || [];
    const scored = r.filter((k) => k.poznata === true || k.poznata === false);
    const forma = scored.slice(0, 14).reverse();
    const fp = forma.filter((k) => k.poznata === true).length;
    const formaHtml = forma.length >= 4 ? `<div class="forma"><div class="forma-h"><b>Форма</b><span>последни ${forma.length}</span></div>
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
        <div class="rk-krug" style="--p:${esc(ob.uspeh || 0)}"><b>${esc(ob.uspeh)}<i>%</i></b><span>успех</span></div>
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
    return ramka(["Резултати", "Как завършиха нашите прогнози."], rekordHtml + daily);
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
    const chips = ["Всички", "Футбол", "Баскетбол", "Тенис", "ММА"];
    const mom = (a) => `<div class="mom">${Array.from({ length: 16 }, (_, i) =>
      `<i style="height:${28 + Math.round(Math.abs(Math.sin((i + a) * 1.15)) * 68)}%;background:${i < 6 ? "var(--em)" : i < 10 ? "var(--gold)" : "var(--line2)"}"></i>`).join("")}</div>`;
    const liveKarta = (lg, dm, gs, rz, mk, vl, demo, i) => `<article class="live-k">
      <div class="live-top"><span class="live-badge"><i></i>НА ЖИВО</span><span class="live-liga">${esc(lg)}</span>${demo ? '<span class="demo-b">ДЕМО</span>' : ""}</div>
      <div class="live-mach"><div class="live-tim">${ekip(dm)}<b>${esc(dm)}</b></div>
        <div class="live-rez">${esc(rz)}</div>
        <div class="live-tim d">${ekip(gs)}<b>${esc(gs)}</b></div></div>
      <div class="live-mom">${mom(i)}<div class="mom-meta"><span>${esc(mk || "Моментум")}</span>${vl ? `<b>${esc(vl)}</b>` : ""}</div></div></article>`;
    const realni = zh.map((z, i) => liveKarta(z.liga || "Футбол", z.dom, z.gost,
      (z.gol_dom != null ? z.gol_dom : "") + " : " + (z.gol_gost != null ? z.gol_gost : ""),
      z.status === "HT" ? "Почивка" : (z.minuta != null ? z.minuta + "'" : "LIVE"), "", false, i)).join("");
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
  function ekranScenario() {
    const scen = [["1", "⚽", "Real вкарва първи", true], ["2", "🔵", "Barça вкарва първи", false], ["0:0", "", "0:0 до 60’", false], ["", "🟥", "Червен картон", false]];
    const gauge = (p, lbl) => `<div class="gauge"><div class="ring" style="--p:${p}"><b>${p}%</b></div><span>${esc(lbl)}</span></div>`;
    return ramka(null, `
      <div class="hero">
        <div class="hero-fig" style="background-image:url('/img/scenario-zar.png')"></div>
        <div class="hero-copy"><p class="eyebrow">Симулация</p><h1>Сценарии</h1><p class="pod">Разгледай сценарии и виж как се менят вероятностите.</p></div>
      </div>
      <article class="pk"><div class="pk-h">${ik("football", "ik s")}<span class="liga">Ла Лига · Днес · 22:00</span></div>
        <div class="pk-mach"><div class="pk-tim">${ekip("Real Madrid")}<span>Real Madrid</span></div><div class="pk-vs">VS</div><div class="pk-tim d">${ekip("Barcelona")}<span>Barcelona</span></div></div></article>
      <section class="sekcia"><header><h2>Избери сценарий</h2></header>
        <div class="scen-grid">${scen.map(([v, e, t, on]) => `<button class="scen-b${on ? " on" : ""}">${e ? `<span class="scen-e">${e}</span>` : v ? `<span class="scen-v">${esc(v)}</span>` : ""}<b>${esc(t)}</b></button>`).join("")}</div></section>
      <section class="sekcia"><header><h2>Минута</h2><span class="scen-min">30’</span></header>
        <div class="slider"><span style="width:38%"></span><i style="left:38%"></i></div></section>
      <section class="sekcia"><header><h2>Вероятности за краен резултат</h2></header>
        <div class="gauges">${gauge(64, "Real")}${gauge(22, "Равен")}${gauge(14, "Barça")}</div></section>
      <div class="dvoino2">
        <div class="view-c">${ico("prognozi", "ico")}<div><b>Green Room View</b><span>Темпото се отваря. Пространствата стават по-важни.</span></div></div>
        <div class="risk-c"><svg class="ico" viewBox="0 0 24 24"><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/></svg><div><b>Риск</b><span>Повишена несигурност</span><div class="risk-bar on2"><i></i><i></i><i></i><i></i></div></div></div>
      </div>
      <div class="scen-act"><button class="btn full">Сравни резултатите</button></div>
      <p class="demo-note">Илюстративни стойности, не реален модел.</p>`);
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
        <div class="koef-b"><span>Коефициент</span><b>${k.koef ? esc(k.koef.toFixed(2)) : "—"}</b></div>
        <div class="koef-b"><span>Увереност</span><b>${pr ? esc(pr) + "%" : "—"}</b></div>
      </div>
      ${k.zashto ? `<div class="lib-card" style="margin-top:16px"><span class="lib-et">Green Room View</span><p>${esc(k.zashto)}</p></div>` : ""}
      <div class="dvoino2" style="margin-top:12px">
        <div class="view-c">${ico("puls", "ico")}<div><b>Напрежение ${puls}</b><span>${esc(napr)}</span></div></div>
        <div class="risk-c risk-${rn.c}"><svg class="ico" viewBox="0 0 24 24"><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/></svg><div><b>Риск</b><span>${esc(rn.t)}</span></div></div>
      </div>
      ${k.koef ? `<button class="btn full" data-slip="${esc(k.id)}" style="margin-top:14px" aria-pressed="${vFisha(k.id)}">${vFisha(k.id) ? "✓ Във фиша" : "+ Добави във фиша"}</button>` : ""}
      <section class="sekcia"><header><h2>Тактическа схема</h2></header>
        <div class="pitch"><span class="p-mid"></span><span class="p-circle"></span>${dots("dom")}${dots("gost")}</div></section>
      <button class="scen-entry" data-idi="scenario" style="margin-top:16px"><span class="scen-entry-ik">🎲</span><div><b>Сценарии</b><span>Разгледай сценариите за мача</span></div><span class="str">${ico("str")}</span></button>`);
  }

  /* ── ПРОФИЛ ── */
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
        <div class="plochka"><b class="em">${o.uspeh != null ? esc(o.uspeh) + "%" : "—"}</b><span>успеваемост 30 дни</span></div></div>
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
      const r = await api("POST", reg ? "/api/register" : "/api/login", { email, password });
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
    Object.assign(S, { me: null, data: null, admin: null, adminRejim: false, tab: "nachalo" });
    ekranVhod("vhod");
  }

  /* ── основното ── */
  function render() {
    if (!S.me) return ekranVhod("vhod");
    const f = S.adminRejim ? ekranAdmin : ({ nachalo: ekranNachalo, sport: ekranSport, live: ekranLive, prognozi: ekranPrognozi, scenario: ekranScenario, mach: ekranMach, fishove: ekranFishove,
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
    if (ds.mach !== undefined) { S.machK = ((S.data && S.data.prognozi) || []).find((p) => p.id === ds.mach) || null; S.machTab = "obzor"; return idi("mach"); }
    if (ds.sport !== undefined) { S.sport = ds.sport || null; S.sportTab = "prog"; return idi("sport"); }
    if (ds.stab) { S.sportTab = ds.stab; return render(); }
    if (ds.nsport !== undefined) { S.novSport = ds.nsport; return render(); }
    if (ds.pkview) { S.pkView = ds.pkview; return render(); }
    if (ds.ptab) { S.progTab = ds.ptab; return render(); }
    if (ds.psort) { S.progSort = ds.psort; return render(); }
    if (ds.lfav) { S.samoLyubimi = !S.samoLyubimi; return render(); }
    if (ds.zvezda) { toggleLyubim(ds.zvezda); if (S.samoLyubimi) return render(); obnoviZvezda(t); obnoviLfav(); return; }
    if (ds.psport !== undefined) { S.progSport = ds.psport; return render(); }
    if (ds.ftab) { S.fishTab = ds.ftab; return render(); }
    if (ds.rez) { S.rezDen = ds.rez; return render(); }
    if (ds.slip) { toggleSlip(ds.slip); obnoviDob(t, ds.slip); obnoviPill(); return; }
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

  async function zarediDanni() {
    const r = await api("GET", "/api/data");
    if (r.s === 200) { S.data = r.j; if (r.j.me) S.me = r.j.me; S.novi = noviBroy(); return true; }
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
    $app.innerHTML = ramka(null, '<div class="skelet" style="margin-top:16px"><div class="sk" style="height:186px"></div><div class="sk k"></div><div class="sk"></div><div class="sk"></div></div>');
    if (await zarediDanni()) { render(); pokazhiVodach(); }
  }
  setInterval(async () => {
    if (document.visibilityState !== "visible" || !S.me || !S.me.active || S.adminRejim) return;
    const a = document.activeElement;
    if (a && a.tagName === "INPUT") return; // не пречи на търсенето
    if (await zarediDanni()) render();
  }, 5 * 60 * 1000);

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
  }
  start();
})();
