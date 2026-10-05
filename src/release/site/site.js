// The site's one script: the hero's run line, the copy buttons, the fade-ups.
// Fixed in every release -- release.ps1 substitutes nothing here, and the copy
// buttons read their text out of the DOM.
(function () {
  'use strict';
  var reduce = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);

  // ---- copy buttons: shipped hidden, a dead button with JS off is worse ----
  function legacy(text, done) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (e) { /* stays selectable */ }
    document.body.removeChild(ta);
  }
  function copy(text, btn) {
    var done = function () {
      var old = btn.textContent;
      btn.textContent = 'Copied';
      setTimeout(function () { btn.textContent = old; }, 1400);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, function () { legacy(text, done); });
    } else {
      legacy(text, done);
    }
  }
  Array.prototype.forEach.call(document.querySelectorAll('.copy[data-copy]'), function (btn) {
    var src = document.getElementById(btn.getAttribute('data-copy'));
    if (!src) { return; }
    btn.hidden = false;
    btn.addEventListener('click', function () { copy(src.textContent, btn); });
  });

  // ---- fade-up: only blocks still below the fold are ever hidden ----
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -6% 0px' });
    Array.prototype.forEach.call(document.querySelectorAll('[data-reveal]'), function (b) {
      if (b.getBoundingClientRect().top > window.innerHeight) {
        b.classList.add('pre');
        io.observe(b);
      }
    });
  }

  // ---- the hero: a real run's path, coloured by speed as the game colours it ----
  var cv = document.getElementById('runline');
  if (!cv || !cv.getContext || !window.fetch) { return; }
  fetch(cv.getAttribute('data-src'), { credentials: 'omit' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && d.x && d.x.length > 2) { runLine(cv, d); } }, function () {});

  // Blue -> cyan -> green -> yellow -> red: runview.js STOPS.
  var STOPS = [[60, 110, 190], [70, 190, 230], [110, 220, 130], [240, 210, 90], [240, 90, 80]];
  function ramp(u) {
    var f = Math.max(0, Math.min(1, u)) * (STOPS.length - 1), i = Math.min(STOPS.length - 2, Math.floor(f));
    var k = f - i, a = STOPS[i], b = STOPS[i + 1];
    return 'rgb(' + Math.round(a[0] + (b[0] - a[0]) * k) + ',' + Math.round(a[1] + (b[1] - a[1]) * k) +
      ',' + Math.round(a[2] + (b[2] - a[2]) * k) + ')';
  }

  function runLine(cv, d) {
    var n = d.x.length, i;
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (i = 0; i < n; i++) {
      var p = [d.x[i], d.y[i], d.z[i]];
      for (var a = 0; a < 3; a++) { lo[a] = Math.min(lo[a], p[a]); hi[a] = Math.max(hi[a], p[a]); }
    }
    var R = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2 || 1;
    var P = new Float32Array(n * 3);
    for (i = 0; i < n; i++) {
      P[i * 3] = (d.x[i] - (lo[0] + hi[0]) / 2) / R;
      P[i * 3 + 1] = (d.y[i] - (lo[1] + hi[1]) / 2) / R;
      P[i * 3 + 2] = (d.z[i] - (lo[2] + hi[2]) / 2) / R;
    }
    // The colour range is mean +/- 2sd inside the run's own min..max
    // (Line_Range, src/client/cl_lines.qc), so one slow corner does not wash
    // the whole line out.
    var mean = 0, sd = 0, smin = Infinity, smax = -Infinity;
    for (i = 0; i < n; i++) { mean += d.s[i]; smin = Math.min(smin, d.s[i]); smax = Math.max(smax, d.s[i]); }
    mean /= n;
    for (i = 0; i < n; i++) { sd += (d.s[i] - mean) * (d.s[i] - mean); }
    sd = Math.sqrt(sd / n);
    var s0 = Math.max(smin, mean - 2 * sd), s1 = Math.min(smax, mean + 2 * sd);
    var NB = 24, cols = [], bucket = new Uint8Array(n);
    for (i = 0; i < NB; i++) { cols.push(ramp(i / (NB - 1))); }
    for (i = 0; i < n; i++) {
      bucket[i] = Math.round(Math.max(0, Math.min(1, (d.s[i] - s0) / ((s1 - s0) || 1))) * (NB - 1));
    }

    var ctx = cv.getContext('2d');
    var X = new Float32Array(n), Y = new Float32Array(n);
    var W = 0, H = 0, dpr = 1, raf = 0, shown = true, t0 = 0, head = 0;
    var REVEAL = 4.5;                       // s for the line to draw itself
    var T = d.t[n - 1] - d.t[0];

    function size() {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      W = Math.round(cv.clientWidth * dpr);
      H = Math.round(cv.clientHeight * dpr);
      cv.width = W; cv.height = H;
      ask();
    }
    function ask() { if (!raf && shown) { raf = requestAnimationFrame(frame); } }

    // `glow` passes add light; the core does not, or the round caps where two
    // colour runs meet would add up into bright dots.
    function stroke(from, to, width, alpha, glow) {
      ctx.globalCompositeOperation = glow ? 'lighter' : 'source-over';
      ctx.lineWidth = width;
      ctx.globalAlpha = alpha;
      for (var b = 0; b < NB; b++) {
        var open = false;
        ctx.beginPath();
        for (var j = Math.max(1, from); j < to; j++) {
          if (bucket[j] !== b) { open = false; continue; }
          if (!open) { ctx.moveTo(X[j - 1], Y[j - 1]); open = true; }
          ctx.lineTo(X[j], Y[j]);
        }
        ctx.strokeStyle = cols[b];
        ctx.stroke();
      }
    }

    function frame(now) {
      raf = 0;
      if (!t0) { t0 = now; }
      var t = (now - t0) / 1000;
      var yaw = 0.7 + (reduce ? 0 : t * 0.05), el = 0.58;
      var cy = Math.cos(yaw), sy = Math.sin(yaw), ce = Math.cos(el), se = Math.sin(el);
      // Sized by the shorter side, but never smaller than the hero is tall: on
      // a phone the line runs off the edges rather than shrinking to a squiggle.
      var F = Math.max(Math.min(W, H * 1.6), H * 0.95) * 0.95, D = 3.1, ox = W / 2, oy = H * 0.48;
      for (var j = 0; j < n; j++) {
        var x = P[j * 3], y = P[j * 3 + 1], z = P[j * 3 + 2];
        var x1 = x * cy - y * sy, y1 = x * sy + y * cy;
        var depth = D + y1 * ce + z * se, up = z * ce - y1 * se;
        X[j] = ox + F * x1 / depth;
        Y[j] = oy - F * up / depth;
      }
      ctx.clearRect(0, 0, W, H);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      var k = reduce ? n : Math.min(n, Math.ceil(n * (1 - Math.pow(1 - Math.min(1, t / REVEAL), 3))));
      stroke(1, k, 9 * dpr, 0.07, true);
      stroke(1, k, 2.2 * dpr, 0.62, false);
      if (!reduce && k === n && T > 0) {
        // A bright head travels the line on the run's own clock.
        var tt = d.t[0] + ((t - REVEAL) % T);
        if (d.t[head] > tt) { head = 0; }
        while (head < n - 1 && d.t[head + 1] <= tt) { head++; }
        var tail = head;
        while (tail > 0 && d.t[tail] > tt - 2.2) { tail--; }
        stroke(tail + 1, head + 1, 7 * dpr, 0.25, true);
        stroke(tail + 1, head + 1, 3.2 * dpr, 1, false);
        ctx.globalAlpha = 1;
        ctx.fillStyle = '#fff';
        ctx.shadowColor = cols[bucket[head]];
        ctx.shadowBlur = 18 * dpr;
        ctx.beginPath();
        ctx.arc(X[head], Y[head], 3.6 * dpr, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
      if (!reduce && shown && !document.hidden) { ask(); }
    }

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (es) { shown = es[0].isIntersecting; ask(); }).observe(cv);
    }
    document.addEventListener('visibilitychange', ask);
    window.addEventListener('resize', size);
    size();
  }
})();
