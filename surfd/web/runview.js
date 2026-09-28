// The run viewer: a recorded run as a path you can scrub, with the speed it
// was carrying at every point.  Fed by /board/api/run/<rid>, which is recplot's
// output -- the same parser the admin run page reads.
//
// TWO CANVASES, ONE CLOCK.  The path is drawn once per size change and cached
// to an offscreen bitmap; only the dot, the trail and the playhead are redrawn
// per frame.  A 1500-point path restroked every frame was measurably worse on a
// phone than the same path blitted, and the run this was built against has
// 5,976 samples before decimation.
//
// EVERY STRING REACHES THE PAGE THROUGH textContent, same rule as board.js:
// names are player-chosen, so the markup-assigning properties are not used here
// at all -- and test_web.py greps both files for their names, which is why this
// sentence spells none of them.
window.FSRun = (function () {
  'use strict';

  // The colour range is mean +/- 2sd clamped into the run's own min..max --
  // Line_Range in src/client/cl_lines.qc, so the web and the game colour one
  // run the same way.  A single slow section does not wash out the whole line.
  var SD = 2.0;
  // The imported tint, LN_FGNCOL in cl_lines.qc: 0.25 0.45 1.00.
  var FGN = [64, 115, 255];
  var TRAIL = 2.2;           // s of run time the bright trail covers
  var DOT = 4.2;             // px

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = String(text); }
    return e;
  }

  // Blue -> cyan -> green -> yellow -> red.  Stops, not a formula, so the
  // midtones are pickable rather than whatever a hue sweep lands on.
  var STOPS = [[60, 110, 190], [70, 190, 230], [110, 220, 130],
               [240, 210, 90], [240, 90, 80]];

  function ramp(u) {
    if (!(u >= 0)) { u = 0; } else if (u > 1) { u = 1; }
    var f = u * (STOPS.length - 1), i = Math.floor(f), k = f - i;
    if (i >= STOPS.length - 1) { return STOPS[STOPS.length - 1]; }
    var a = STOPS[i], b = STOPS[i + 1];
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k,
            a[2] + (b[2] - a[2]) * k];
  }

  function rgb(c, tint) {
    var r = c[0], g = c[1], b = c[2];
    if (tint > 0) {
      r += (FGN[0] - r) * tint; g += (FGN[1] - g) * tint; b += (FGN[2] - b) * tint;
    }
    return 'rgb(' + (r | 0) + ',' + (g | 0) + ',' + (b | 0) + ')';
  }

  function fmt(ms) {
    var neg = ms < 0; if (neg) { ms = -ms; }
    var m = Math.floor(ms / 60000), s = Math.floor(ms / 1000) % 60, r = ms % 1000;
    return (neg ? '-' : '') + m + ':' + (s < 10 ? '0' : '') + s + '.' +
      ('00' + Math.floor(r)).slice(-3);
  }

  // ---- one loaded run -----------------------------------------------------
  function View(host, data, opts) {
    opts = opts || {};
    this.host = host;
    this.d = data;
    this.tint = opts.tint || 0;
    this.onpause = opts.onpause || null;   // told the playhead, for the URL
    // `at` may legitimately be negative (the prestrafe), so presence is its own
    // flag rather than `at > 0`.
    this.have_at = typeof opts.at === 'number' && isFinite(opts.at);
    this.start = this.have_at ? opts.at : 0;
    this.t = 0;                 // playhead, run seconds
    this.playing = false;
    this.raf = 0;
    this.last = 0;
    this.rate = 1;
    this.plan = null;           // cached path bitmap + transform
    this.build();
  }

  View.prototype.range = function () {
    var s = this.d.spd, n = s.length, i, sum = 0, sq = 0, lo = Infinity, hi = 0;
    for (i = 0; i < n; i++) {
      sum += s[i]; sq += s[i] * s[i];
      if (s[i] < lo) { lo = s[i]; }
      if (s[i] > hi) { hi = s[i]; }
    }
    if (!n) { return [0, 1]; }
    var mean = sum / n, sd = Math.sqrt(Math.max(0, sq / n - mean * mean));
    var a = Math.max(lo, mean - SD * sd), b = Math.min(hi, mean + SD * sd);
    if (!(b > a)) { b = a + 1; }
    return [a, b];
  };

  View.prototype.build = function () {
    var d = this.d, self = this;
    this.host.textContent = '';

    var stage = el('div', 'rv-stage');
    this.path = el('canvas', 'rv-path');
    stage.appendChild(this.path);
    this.hud = el('div', 'rv-hud');
    this.vnum = el('span', 'rv-v', '0');
    this.vunit = el('span', 'rv-u', 'u/s');
    this.hud.appendChild(this.vnum);
    this.hud.appendChild(this.vunit);
    this.clock = el('div', 'rv-clock', '0:00.000');
    this.hud.appendChild(this.clock);
    stage.appendChild(this.hud);
    this.host.appendChild(stage);

    this.speed = el('canvas', 'rv-speed');
    this.host.appendChild(this.speed);

    var bar = el('div', 'rv-bar');
    this.btn = el('button', 'rv-play');
    this.btn.type = 'button';
    this.btn.appendChild(document.createTextNode('▶ Play'));
    this.btn.addEventListener('click', function () { self.toggle(); });
    bar.appendChild(this.btn);

    this.scrub = document.createElement('input');
    this.scrub.type = 'range';
    this.scrub.className = 'rv-scrub';
    this.scrub.min = '0';
    this.scrub.max = '1000';
    this.scrub.value = '0';
    this.scrub.setAttribute('aria-label', 'Position in the run');
    this.scrub.addEventListener('input', function () {
      self.pause();
      self.seek(self.t0() + self.dur() * (Number(self.scrub.value) / 1000));
    });
    bar.appendChild(this.scrub);

    var sel = document.createElement('select');
    sel.className = 'rv-rate';
    sel.setAttribute('aria-label', 'Playback speed');
    [[0.25, '¼×'], [0.5, '½×'], [1, '1×'],
     [2, '2×'], [4, '4×']].forEach(function (o) {
      var op = document.createElement('option');
      op.value = String(o[0]);
      op.textContent = o[1];
      if (o[0] === 1) { op.selected = true; }
      sel.appendChild(op);
    });
    sel.addEventListener('change', function () { self.rate = Number(sel.value); });
    bar.appendChild(sel);
    this.host.appendChild(bar);

    this.legend = el('div', 'rv-legend');
    this.host.appendChild(this.legend);

    this.onsize = function () { self.plan = null; self.draw(); };
    window.addEventListener('resize', this.onsize);
    this.speed.addEventListener('click', function (ev) {
      var r = self.speed.getBoundingClientRect();
      self.pause();
      self.seek(self.t0() +
                self.dur() * ((ev.clientX - r.left) / Math.max(1, r.width)));
    });
    this.legendFill();
    this.seek(this.have_at ? this.start : this.t0());
  };

  View.prototype.legendFill = function () {
    var r = this.range(), self = this;
    this.legend.textContent = '';
    this.legend.appendChild(el('span', 'rv-lk', Math.round(r[0]) + ' u/s'));
    var g = el('span', 'rv-grad');
    g.style.background = 'linear-gradient(to right,' +
      STOPS.map(function (c, i) {
        return rgb(ramp(i / (STOPS.length - 1)), self.tint);
      }).join(',') + ')';
    this.legend.appendChild(g);
    this.legend.appendChild(el('span', 'rv-lk', Math.round(r[1]) + ' u/s'));
  };

  // A .rec STARTS BEFORE THE TIMER DOES.  Run time is negative until the start
  // zone is crossed -- measured -2.130 s on rid 5, -3.840 s on rid 4, 3.4% and
  // 5.2% of those timelines.  For surf the entry speed is half the point of
  // watching, so the playhead spans t0..t1 and not 0..t1.
  View.prototype.t0 = function () {
    var t = this.d.t_;
    return t && t.length ? t[0] : 0;
  };

  View.prototype.t1 = function () {
    var t = this.d.t_;
    return t && t.length ? t[t.length - 1] : 0.001;
  };

  View.prototype.dur = function () {
    return Math.max(0.001, this.t1() - this.t0());
  };

  View.prototype.fit = function (cv, h) {
    var dpr = window.devicePixelRatio || 1;
    var w = Math.max(160, cv.clientWidth);
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    cv.style.height = h + 'px';
    var g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { g: g, w: w, h: h };
  };

  // The path bitmap and the world->screen transform, rebuilt only on resize.
  View.prototype.replan = function () {
    var d = this.d, i, n = d.x.length;
    var box = this.fit(this.path, Math.max(260, Math.min(520,
      Math.round(this.path.clientWidth * 0.62))));
    var pad = 14;
    var lo = [Infinity, Infinity], hi = [-Infinity, -Infinity];
    for (i = 0; i < n; i++) {
      if (d.x[i] < lo[0]) { lo[0] = d.x[i]; }
      if (d.x[i] > hi[0]) { hi[0] = d.x[i]; }
      if (d.y[i] < lo[1]) { lo[1] = d.y[i]; }
      if (d.y[i] > hi[1]) { hi[1] = d.y[i]; }
    }
    var sx = (box.w - 2 * pad) / Math.max(1, hi[0] - lo[0]);
    var sy = (box.h - 2 * pad) / Math.max(1, hi[1] - lo[1]);
    var s = Math.min(sx, sy);
    var ox = pad + ((box.w - 2 * pad) - (hi[0] - lo[0]) * s) / 2;
    var oy = pad + ((box.h - 2 * pad) - (hi[1] - lo[1]) * s) / 2;
    // y is flipped: world y grows north, canvas y grows down.
    var self = this;
    var tx = function (i) { return ox + (d.x[i] - lo[0]) * s; };
    var ty = function (i) { return box.h - oy - (d.y[i] - lo[1]) * s; };

    var bmp = document.createElement('canvas');
    bmp.width = this.path.width;
    bmp.height = this.path.height;
    var bg = bmp.getContext('2d');
    var dpr = window.devicePixelRatio || 1;
    bg.setTransform(dpr, 0, 0, dpr, 0, 0);
    var r = this.range(), span = Math.max(1e-6, r[1] - r[0]);
    bg.lineWidth = 2.0;
    bg.lineCap = 'round';
    bg.lineJoin = 'round';
    for (i = 1; i < n; i++) {
      bg.strokeStyle = rgb(ramp((d.spd[i] - r[0]) / span), self.tint * 0.55);
      bg.beginPath();
      bg.moveTo(tx(i - 1), ty(i - 1));
      bg.lineTo(tx(i), ty(i));
      bg.stroke();
    }
    this.plan = { box: box, tx: tx, ty: ty, bmp: bmp, r: r, span: span };
    return this.plan;
  };

  // The sample at or before run time `t`, and how far past it we are.
  View.prototype.at = function (t) {
    var a = this.d.t_, lo = 0, hi = a.length - 1;
    if (hi < 0) { return { i: 0, j: 0, k: 0 }; }
    if (t <= a[0]) { return { i: 0, j: 0, k: 0 }; }
    if (t >= a[hi]) { return { i: hi, j: hi, k: 0 }; }
    while (lo < hi - 1) {
      var mid = (lo + hi) >> 1;
      if (a[mid] <= t) { lo = mid; } else { hi = mid; }
    }
    var d = a[hi] - a[lo];
    return { i: lo, j: hi, k: d > 0 ? (t - a[lo]) / d : 0 };
  };

  View.prototype.draw = function () {
    var p = this.plan || this.replan(), d = this.d;
    var g = p.box.g, at = this.at(this.t);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, this.path.width, this.path.height);
    g.drawImage(p.bmp, 0, 0);
    var dpr = window.devicePixelRatio || 1;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Everything ahead of the playhead dimmed, so the eye finds "now".
    g.globalCompositeOperation = 'destination-out';
    g.globalAlpha = 0.62;
    g.lineWidth = 3.4;
    g.beginPath();
    for (var i = at.j; i < d.x.length; i++) {
      if (i === at.j) { g.moveTo(p.tx(i), p.ty(i)); } else { g.lineTo(p.tx(i), p.ty(i)); }
    }
    g.stroke();
    g.globalCompositeOperation = 'source-over';
    g.globalAlpha = 1;

    // The bright trail: the last TRAIL seconds of run time.
    var back = this.at(Math.max(0, this.t - TRAIL));
    g.lineWidth = 3.0;
    g.lineCap = 'round';
    for (var k = Math.max(1, back.i + 1); k <= at.i; k++) {
      g.strokeStyle = rgb(ramp((d.spd[k] - p.r[0]) / p.span), this.tint * 0.35);
      g.beginPath();
      g.moveTo(p.tx(k - 1), p.ty(k - 1));
      g.lineTo(p.tx(k), p.ty(k));
      g.stroke();
    }

    var x = p.tx(at.i) + (p.tx(at.j) - p.tx(at.i)) * at.k;
    var y = p.ty(at.i) + (p.ty(at.j) - p.ty(at.i)) * at.k;
    var spd = d.spd[at.i] + (d.spd[at.j] - d.spd[at.i]) * at.k;

    g.beginPath();
    g.arc(x, y, DOT + 3.4, 0, Math.PI * 2);
    g.fillStyle = 'rgba(5,5,8,0.72)';
    g.fill();
    g.beginPath();
    g.arc(x, y, DOT, 0, Math.PI * 2);
    g.fillStyle = rgb(ramp((spd - p.r[0]) / p.span), this.tint);
    g.fill();
    g.lineWidth = 1.4;
    g.strokeStyle = '#FFFFFF';
    g.stroke();

    this.vnum.textContent = String(Math.round(spd));
    // NOT clamped to 0: before the start zone the clock reads negative,
    // which is the number the game shows too.
    this.clock.textContent = fmt(this.t * 1000);
    this.drawSpeed(spd);
  };

  View.prototype.drawSpeed = function (now) {
    var d = this.d;
    var box = this.fit(this.speed, 74);
    var g = box.g, n = d.spd.length, i, hi = 1;
    for (i = 0; i < n; i++) { if (d.spd[i] > hi) { hi = d.spd[i]; } }
    g.clearRect(0, 0, box.w, box.h);
    var dur = this.dur(), t0 = this.t0();
    var X = function (t) { return ((t - t0) / dur) * box.w; };
    var Y = function (v) { return box.h - 3 - (v / hi) * (box.h - 8); };
    var r = this.range(), span = Math.max(1e-6, r[1] - r[0]);
    g.lineWidth = 1.4;
    for (i = 1; i < n; i++) {
      g.strokeStyle = rgb(ramp((d.spd[i] - r[0]) / span), this.tint * 0.5);
      g.globalAlpha = d.t_[i] <= this.t ? 1 : 0.32;
      g.beginPath();
      g.moveTo(X(d.t_[i - 1]), Y(d.spd[i - 1]));
      g.lineTo(X(d.t_[i]), Y(d.spd[i]));
      g.stroke();
    }
    g.globalAlpha = 1;
    if (t0 < 0) {
      g.fillStyle = 'rgba(140,140,148,0.13)';
      g.fillRect(0, 0, X(0), box.h);
    }
    // Splits, where the file recorded them: thin ticks, no labels at this size.
    g.strokeStyle = 'rgba(140,140,148,0.5)';
    g.lineWidth = 1;
    (d.marks || []).forEach(function (mk) {
      if (mk.k !== 'split' && mk.k !== 'cp' && mk.k !== 'stage') { return; }
      var px = Math.round(X(mk.t)) + 0.5;
      g.beginPath(); g.moveTo(px, 2); g.lineTo(px, box.h - 2); g.stroke();
    });
    var hx = Math.round(X(this.t)) + 0.5;
    g.strokeStyle = '#FFFFFF';
    g.lineWidth = 1;
    g.beginPath(); g.moveTo(hx, 0); g.lineTo(hx, box.h); g.stroke();
  };

  View.prototype.seek = function (t) {
    this.t = Math.max(this.t0(), Math.min(this.t1(), t));
    this.scrub.value =
      String(Math.round(((this.t - this.t0()) / this.dur()) * 1000));
    this.draw();
  };

  View.prototype.toggle = function () {
    if (this.playing) { this.pause(); } else { this.play(); }
  };

  View.prototype.play = function () {
    if (this.playing) { return; }
    if (this.t >= this.t1() - 1e-6) { this.t = this.t0(); }
    this.playing = true;
    this.btn.textContent = '❚❚ Pause';
    this.last = 0;
    var self = this;
    var step = function (ts) {
      if (!self.playing) { return; }
      if (self.last) { self.seek(self.t + ((ts - self.last) / 1000) * self.rate); }
      self.last = ts;
      if (self.t >= self.t1() - 1e-6) { self.pause(); return; }
      self.raf = window.requestAnimationFrame(step);
    };
    this.raf = window.requestAnimationFrame(step);
  };

  View.prototype.pause = function () {
    this.playing = false;
    this.btn.textContent = '▶ Play';
    if (this.raf) { window.cancelAnimationFrame(this.raf); this.raf = 0; }
    // Where the run stopped goes in the address, so a link shares the moment
    // rather than the run.  replaceState, not a hash write: scrubbing must not
    // fill the back button with a hundred entries.
    if (this.onpause) { this.onpause(this.t); }
  };

  View.prototype.destroy = function () {
    this.pause();
    window.removeEventListener('resize', this.onsize);
    this.host.textContent = '';
  };

  return { View: View, fmt: fmt };
})();
