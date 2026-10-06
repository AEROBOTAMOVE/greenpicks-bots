/* ─────────────────────────────────────────────────────────────
   THE GREEN ROOM · живото поле зад цялата платформа
   Сцената „ПОЛЕТО" (kiber-field) от КИБЕР СЦЕНА — Canvas 2D, нула библиотеки.
   MIT © 2026 Meng To (виж /scena/LICENSE.txt); фабриката е
   пренесена дословно от двигателя, без React обвивката (8 MB → 5 KB).
   Нашите промени: (1) прозрачен фон — отдолу стои изумрудено-златният
   градиент на страницата; (2) мишката се слуша по целия прозорец, защото
   слоят е зад съдържанието и не приема събития; (3) пауза при скрит раздел,
   изключено при „намалено движение", по-рядко на телефон.
   ───────────────────────────────────────────────────────────── */
(function () {
  "use strict";
  if (!window.requestAnimationFrame || !document.createElement("canvas").getContext) return;

  var DEF = { mode: "dark", density: 1, link: 150, speed: 1, pointerAmount: 1, hue: 152, glow: 1, opacity: 1 };
  function rng(seed) { var e = seed >>> 0 || 7; return function () { e ^= e << 13; e >>>= 0; e ^= e >> 17; e ^= e << 5; e >>>= 0; return e / 4294967296; }; }

  // ── фабриката на ПОЛЕТО (от двигателя на СЦЕНА) ──
  function fabrika(host, canvas, opts) {
    var n = canvas.getContext("2d");
    var a = 1, r = 1, s = 1, l = [], d = "", u = performance.now(), h = 0;
    var f = { x: -9999, y: -9999, active: false };
    var m = document.createElement("canvas"), g = m.getContext("2d"), w = "", b = 64;
    function sprite(k, dark) {
      var D = Math.round(k) + "|" + dark;
      if (D === w || !g) return;
      w = D; m.width = b; m.height = b; g.clearRect(0, 0, b, b);
      var P = g.createRadialGradient(b / 2, b / 2, 0, b / 2, b / 2, b / 2);
      P.addColorStop(0, "hsla(" + k + ", 90%, " + (dark ? 78 : 46) + "%, 0.95)");
      P.addColorStop(0.22, "hsla(" + k + ", 86%, " + (dark ? 66 : 42) + "%, 0.5)");
      P.addColorStop(0.55, "hsla(" + k + ", 80%, " + (dark ? 56 : 40) + "%, 0.14)");
      P.addColorStop(1, "hsla(" + k + ", 80%, " + (dark ? 50 : 38) + "%, 0)");
      g.fillStyle = P; g.fillRect(0, 0, b, b);
    }
    function onMove(k) { var R = host.getBoundingClientRect(); f.x = k.clientX - R.left; f.y = k.clientY - R.top; f.active = true; }
    function onLeave() { f.active = false; f.x = -9999; f.y = -9999; }
    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    function seed(k) {
      var R = rng(k * 2654435761);
      l = Array.from({ length: k }, function () { return { x: R() * a, y: R() * r, vx: (R() - 0.5) * 16, vy: (R() - 0.5) * 16, r: 1.3 + R() * 2.1, lit: 0, phase: R() * Math.PI * 2 }; });
      d = k + "|" + Math.round(a) + "x" + Math.round(r);
    }
    return {
      resize: function (k, D) {
        a = Math.max(1, Math.round(k)); r = Math.max(1, Math.round(D));
        s = Math.min(2, window.devicePixelRatio || 1);
        canvas.width = Math.round(a * s); canvas.height = Math.round(r * s);
        canvas.style.width = a + "px"; canvas.style.height = r + "px"; d = "";
      },
      render: function (k) {
        if (!n) return;
        var _ = Object.assign({}, DEF, opts());
        var P = Math.max(30, Math.min(420, Math.round((a * r / 5200) * _.density)));
        if (P + "|" + Math.round(a) + "x" + Math.round(r) !== d) seed(P);
        var F = Math.min(0.05, (k - u) / 1000); u = k;
        var j = _.mode !== "light", z = Math.max(40, _.link), N = Math.max(0.02, _.speed), W = Math.max(0, _.glow);
        h += F * N; sprite(_.hue, j);
        n.setTransform(s, 0, 0, s, 0, 0); n.clearRect(0, 0, a, r); n.globalCompositeOperation = "source-over";
        var I = _.pointerAmount * 130, te = (h * 0.16 % 1.6 - 0.3) * a, H, i2;
        for (i2 = 0; i2 < l.length; i2++) {
          H = l[i2];
          H.x += H.vx * F * N; H.y += H.vy * F * N;
          if (H.x < 0) { H.x = 0; H.vx *= -1; } if (H.x > a) { H.x = a; H.vx *= -1; }
          if (H.y < 0) { H.y = 0; H.vy *= -1; } if (H.y > r) { H.y = r; H.vy *= -1; }
          if (f.active && I > 0) {
            var Z = f.x - H.x, ye = f.y - H.y, ae = Math.hypot(Z, ye);
            if (ae < 220 && ae > 1) { var Se = (1 - ae / 220) * I * F; H.x += Z / ae * Se; H.y += ye / ae * Se; H.lit = Math.min(1, H.lit + (1 - ae / 220) * F * 4); }
          }
          H.lit = Math.max(0, H.lit - F * 0.7);
          var q = 1 - Math.min(1, Math.abs(H.x - te) / (a * 0.24)), pe = 0.5 + 0.5 * Math.sin(h * 1.1 + H.phase);
          H.lit = Math.max(H.lit, q * q * (0.35 + pe * 0.45));
        }
        var Q = Math.max(1, Math.ceil(a / z)), ve = Math.max(1, Math.ceil(r / z)), se = [];
        for (i2 = 0; i2 < Q * ve; i2++) se.push([]);
        l.forEach(function (Hh, qq) { var cx = Math.min(Q - 1, Math.max(0, Math.floor(Hh.x / z))), cy = Math.min(ve - 1, Math.max(0, Math.floor(Hh.y / z))); se[cy * Q + cx].push(qq); });
        n.lineCap = "round";
        for (var Hy = 0; Hy < ve; Hy++) for (var qx = 0; qx < Q; qx++) {
          var cel = se[Hy * Q + qx]; if (!cel.length) continue;
          for (var Zr = 0; Zr <= 1; Zr++) for (var yc = Zr === 0 ? 0 : -1; yc <= 1; yc++) {
            var ax = qx + yc, ay = Hy + Zr;
            if (ax < 0 || ay < 0 || ax >= Q || ay >= ve) continue;
            var dr = se[ay * Q + ax];
            for (var x1 = 0; x1 < cel.length; x1++) for (var x2 = 0; x2 < dr.length; x2++) {
              var Fe = cel[x1], Ue = dr[x2]; if (Ue <= Fe) continue;
              var he = l[Fe], Pe = l[Ue], et = Math.hypot(he.x - Pe.x, he.y - Pe.y); if (et > z) continue;
              var it = 1 - et / z, ft = Math.max(he.lit, Pe.lit), pt = it * it * (0.34 + ft * 0.62) * _.opacity;
              n.lineWidth = 0.8 + it * (0.7 + ft * 1.1);
              n.strokeStyle = "hsla(" + _.hue + ", " + Math.round(60 + ft * 28) + "%, " + (j ? 62 + ft * 24 : 28 + ft * 12) + "%, " + pt + ")";
              n.beginPath(); n.moveTo(he.x, he.y); n.lineTo(Pe.x, Pe.y); n.stroke();
            }
          }
        }
        if (W > 0 && g) {
          n.globalCompositeOperation = j ? "lighter" : "source-over";
          for (i2 = 0; i2 < l.length; i2++) { H = l[i2]; var qs = (H.r * 7 + H.lit * 26) * W; n.globalAlpha = Math.min(1, (0.16 + H.lit * 0.62) * W * _.opacity); n.drawImage(m, H.x - qs / 2, H.y - qs / 2, qs, qs); }
          n.globalAlpha = 1; n.globalCompositeOperation = "source-over";
        }
        for (i2 = 0; i2 < l.length; i2++) {
          H = l[i2]; var qa = (0.62 + H.lit * 0.38) * _.opacity;
          n.fillStyle = "hsla(" + _.hue + ", " + Math.round(54 + H.lit * 34) + "%, " + (j ? 74 + H.lit * 22 : 24 + H.lit * 12) + "%, " + qa + ")";
          n.beginPath(); n.arc(H.x, H.y, H.r * (1 + H.lit * 0.9), 0, Math.PI * 2); n.fill();
        }
      },
      dispose: function () { window.removeEventListener("pointermove", onMove); document.removeEventListener("pointerleave", onLeave); l = []; },
    };
  }

  // ── закачане: един слой зад цялото приложение ──
  function zakachi() {
    if (document.getElementById("zhivo-pole")) return;
    var host = document.createElement("div");
    host.id = "zhivo-pole"; host.setAttribute("aria-hidden", "true");
    var cv = document.createElement("canvas"); host.appendChild(cv);
    document.body.insertBefore(host, document.body.firstChild);
    var tel = Math.min(window.innerWidth, window.innerHeight) < 600;
    var opts = { mode: "dark", hue: 152, density: tel ? 0.45 : 0.6, link: tel ? 120 : 145, speed: 0.6, glow: 0.9, pointerAmount: 1, opacity: 0.75 };
    var u = fabrika(host, cv, function () { return opts; });
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var raf = 0;
    function fit() { var R = host.getBoundingClientRect(); if (R.width < 2 || R.height < 2) return; u.resize(R.width, R.height); u.render(performance.now()); }
    function loop(t) { u.render(t); raf = !document.hidden ? requestAnimationFrame(loop) : 0; }
    function start() { if (!raf && !reduce) raf = requestAnimationFrame(loop); }
    function stop() { if (raf) { cancelAnimationFrame(raf); raf = 0; } }
    if (window.ResizeObserver) new ResizeObserver(fit).observe(host); else window.addEventListener("resize", fit);
    document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });
    fit(); start();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", zakachi); else zakachi();
})();
