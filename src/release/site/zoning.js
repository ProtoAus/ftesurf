// P1176: the zoning page. zoning.json is the list as tools/zoningpage.py found it;
// board/api/maps says which maps have zones now (`have` = BSP and zones on the Pi).
// P1180: the zone service's history says who published what, and when.
(function () {
  'use strict';
  var POLL_MS = 60000;
  var HISTORY = 'https://play.proto.bar/api/zones/history';   // POST, text/plain: no preflight
  var list = document.getElementById('zlist');
  var stats = document.getElementById('zstats');
  var bar = document.getElementById('zbar');
  var note = document.getElementById('znote');
  var q = document.getElementById('zq');
  var sortSel = document.getElementById('zsort');
  var showDone = document.getElementById('zdone');
  var tierBox = document.getElementById('ztier');
  var data = null, zoned = null, checked = 0, liveFailed = false, tierMin = 0, timer = 0;
  var byMap = {}, recent = [], serverNow = 0, fetchedAt = 0;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text != null) { e.textContent = text; }
    return e;
  }
  function plural(n, one, many) { return n.toLocaleString() + ' ' + (n === 1 ? one : many); }
  function isDone(r) { return !!((zoned && zoned[r.n]) || byMap[r.n]); }
  function ago(at) {
    var s = Math.max(0, serverNow + (Date.now() - fetchedAt) / 1000 - at);
    if (s < 90) { return 'just now'; }
    if (s < 5400) { return Math.round(s / 60) + ' min ago'; }
    if (s < 129600) { return Math.round(s / 3600) + ' h ago'; }
    return Math.round(s / 86400) + ' days ago';
  }
  function tierBand(t) { return t <= 0 ? 0 : t <= 2 ? 1 : t <= 4 ? 3 : 5; }

  function track(r) {
    var parts = [];
    if (r.l === 1) { parts.push(r.c ? 'Linear, ' + plural(r.c, 'checkpoint', 'checkpoints') : 'Linear'); }
    else if (r.l === 0) { parts.push(plural(r.c, 'stage', 'stages')); }
    if (r.b) { parts.push(plural(r.b, 'bonus', 'bonuses')); }
    return parts.join(', ');
  }

  function row(r) {
    var li = el('li', 'zrow' + (isDone(r) ? ' done' : ''));
    var th = el('span', 'zthumb');
    if (r.s >= 0) {
      // Percentages, so the cell stays put at any thumbnail size (CSS sizes the sheet).
      var cols = data.cell[2], rows = data.cell[3];
      th.style.backgroundPosition = (100 * (r.s % cols) / (cols - 1)) + '% ' +
        (rows > 1 ? 100 * Math.floor(r.s / cols) / (rows - 1) : 0) + '%';
      th.classList.add('has');
    }
    li.appendChild(th);
    var main = el('div', 'zmain');
    var name = el('div', 'zname');
    name.appendChild(el('b', null, r.n));
    if (r.t > 0) { name.appendChild(el('span', 'ztier t' + Math.min(r.t, 7), 'T' + r.t)); }
    if (isDone(r)) {
      var h = byMap[r.n];
      name.appendChild(el('span', 'zok', 'Zoned'));
      if (h) { name.appendChild(el('span', 'zby', (h.by ? 'by ' + h.by + ', ' : '') + ago(h.at))); }
    }
    main.appendChild(name);
    var bits = [];
    var tr = track(r);
    if (tr) { bits.push(tr); }
    if (r.k) { bits.push('KSF: ' + r.k); }
    if (r.p) { bits.push(plural(r.p, 'KSF play', 'KSF plays')); }
    if (r.w) { bits.push('WR ' + r.w.toFixed(2) + 's' + (r.wb ? ' by ' + r.wb : '')); }
    if (r.m) { bits.push('mapper ' + r.m); }
    main.appendChild(el('div', 'zmeta', bits.join(' · ')));
    if (r.x) { main.appendChild(el('div', 'zrel', (r.d ? 'Related to ' + r.d + '. ' : '') + r.x)); }
    li.appendChild(main);
    var need = el('div', 'zneed');
    need.appendChild(el('b', null, String(r.z)));
    need.appendChild(el('small', null, 'zones'));
    need.title = 'Start and end, ' + (r.z - 2 - 2 * r.b) + ' stage or checkpoint zones, and a start and end per bonus';
    li.appendChild(need);
    return li;
  }

  function render() {
    if (!data) { return; }
    var term = q.value.trim().toLowerCase();
    var key = sortSel.value;
    var rows = data.rows.filter(function (r) {
      if (!showDone.checked && isDone(r)) { return false; }
      if (tierMin && tierBand(r.t) !== tierMin) { return false; }
      if (term && r.n.indexOf(term) < 0 && r.m.toLowerCase().indexOf(term) < 0 && r.k.indexOf(term) < 0) { return false; }
      return true;
    });
    rows.sort(function (a, b) {
      if (key === 't') { return (a.t || 99) - (b.t || 99) || b.p - a.p; }
      if (key === 'z') { return a.z - b.z || b.p - a.p; }
      if (key === 'n') { return a.n < b.n ? -1 : a.n > b.n ? 1 : 0; }
      return b.p - a.p || (a.n < b.n ? -1 : 1);
    });
    var frag = document.createDocumentFragment();
    rows.forEach(function (r) { frag.appendChild(row(r)); });
    list.textContent = '';
    list.appendChild(frag);

    var total = data.rows.length;
    var done = zoned ? data.rows.filter(isDone).length : 0;
    stats.textContent = plural(total - done, 'map', 'maps') + ' to zone' +
      (done ? ' · ' + done.toLocaleString() + ' zoned since ' + since() : '');
    bar.style.width = (total ? 100 * done / total : 0).toFixed(1) + '%';
    var tail = rows.length ? '' : 'No maps match. ';
    if (liveFailed) { tail += 'Live status is unavailable, so this is the list as of ' + since() + '.'; }
    else if (checked) { tail += 'Checked ' + new Date(checked).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '.'; }
    note.textContent = tail;
  }

  function since() {
    var d = new Date(data.made);
    return isNaN(d) ? 'this list was made' : d.toLocaleDateString([], { day: 'numeric', month: 'short' });
  }

  function drawRecent() {
    var box = document.getElementById('zrecent'), ol = document.getElementById('zrecent-list');
    ol.textContent = '';
    recent.slice(0, 8).forEach(function (h) {
      var li = el('li');
      li.appendChild(el('b', null, h.map));
      li.appendChild(el('span', null, h.kind === 'rollback' ? 'rolled back, ' + ago(h.at)
                                                                : (h.by ? h.by + ', ' : '') + ago(h.at)));
      ol.appendChild(li);
    });
    box.hidden = !recent.length;
  }

  function history() {
    fetch(HISTORY, { method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'text/plain' }, body: '{}' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (doc) {
        if (!doc || !doc.ok || !Array.isArray(doc.rows)) { return; }
        serverNow = +doc.now || Date.now() / 1000; fetchedAt = Date.now();
        var seen = {};
        recent = doc.rows.filter(function (h) {
          var first = !seen[h.map]; seen[h.map] = 1; return first;    // newest per map
        });
        byMap = {};
        recent.forEach(function (h) { if (h.kind !== 'rollback') { byMap[String(h.map).toLowerCase()] = h; } });
        drawRecent(); render();
      })
      .catch(function () { /* the page works without it */ });
  }

  function poll() {
    clearTimeout(timer);
    fetch('board/api/maps', { credentials: 'omit' }).then(function (r) {
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      return r.json();
    }).then(function (doc) {
      var z = {};
      (doc.maps || []).forEach(function (m) { if (m.have) { z[String(m.map).toLowerCase()] = 1; } });
      zoned = z; checked = Date.now(); liveFailed = false;
    }).catch(function () {
      liveFailed = true;
    }).then(function () {
      render();
      history();
      if (!document.hidden) { timer = setTimeout(poll, POLL_MS); }
    });
  }

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && data && Date.now() - checked > POLL_MS) { poll(); }
  });
  q.addEventListener('input', render);
  sortSel.addEventListener('change', render);
  showDone.addEventListener('change', render);
  tierBox.addEventListener('click', function (e) {
    var b = e.target.closest('button');
    if (!b) { return; }
    tierMin = +b.getAttribute('data-t');
    Array.prototype.forEach.call(tierBox.querySelectorAll('button'), function (x) {
      x.setAttribute('aria-pressed', x === b ? 'true' : 'false');
    });
    render();
  });

  fetch('zoning.json', { credentials: 'omit' }).then(function (r) {
    if (!r.ok) { throw new Error('HTTP ' + r.status); }
    return r.json();
  }).then(function (doc) {
    data = doc;
    render();
    poll();
  }).catch(function () {
    stats.textContent = 'The map list could not be loaded.';
  });
})();
