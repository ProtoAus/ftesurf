// Public leaderboard page.  Every URL is relative (the proxy adds a prefix),
// and every server string is set with textContent: names are player-chosen.
(function () {
  'use strict';

  var PAGE = 50;
  var state = { maps: null, sort: 'active', view: null, seq: 0 };

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = String(text); }
    return e;
  }

  // Quake colour codes: ^0-^9, ^xRGB, ^&FB and a few style letters; ^^ is a caret.
  function plain(s) {
    return String(s).replace(/\^(\^|x[0-9A-Fa-f]{3}|&[0-9A-Fa-f-]{2}|[0-9abhmrsu])/g,
      function (m, c) { return c === '^' ? '^' : ''; });
  }

  function fmt(ms) {
    var m = Math.floor(ms / 60000), s = Math.floor(ms / 1000) % 60, r = ms % 1000;
    return m + ':' + (s < 10 ? '0' : '') + s + '.' + ('00' + r).slice(-3);
  }

  function gap(ms) {
    return ms < 60000 ? '+' + (ms / 1000).toFixed(3) : '+' + fmt(ms);
  }

  function ago(t) {
    var d = Math.max(0, Date.now() / 1000 - t);
    if (d < 3600) { return Math.max(1, Math.floor(d / 60)) + 'm ago'; }
    if (d < 86400) { return Math.floor(d / 3600) + 'h ago'; }
    return Math.floor(d / 86400) + 'd ago';
  }

  function day(t) {
    return new Date(t * 1000).toISOString().slice(0, 10);
  }

  function vchip() {
    var c = el('span', 'vchip', 'VERIFIED');
    c.title = 'Re-simulated exactly by the server, or reviewed';
    return c;
  }

  function legName(track, leg) {
    if (track <= 0) { return leg <= 0 ? 'Main' : 'Stage ' + leg; }
    return leg <= 0 ? 'Bonus ' + track : 'Bonus ' + track + ' \u00b7 Stage ' + leg;
  }

  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  function showError(msg) {
    var e = $('err');
    e.textContent = msg || '';
    e.hidden = !msg;
  }

  function get(url) {
    return fetch(url, { credentials: 'omit' }).then(function (r) {
      if (r.status === 429) { throw new Error('Too many requests, try again in a minute'); }
      if (r.status === 404) { throw new Error('No such map'); }
      if (!r.ok) { throw new Error('Could not load the board (HTTP ' + r.status + ')'); }
      return r.json();
    }, function () { throw new Error('Could not reach the server'); });
  }

  // ---- hash: #m=<map>&t=<track>&l=<leg>&s=<style>&k=<tier> ----------------
  function readHash() {
    var o = {};
    location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
      var i = kv.indexOf('=');
      if (i <= 0) { return; }
      try { o[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1)); } catch (e) { /* skip */ }
    });
    return o;
  }

  function hashFor(map, track, leg, style, tier) {
    return '#m=' + encodeURIComponent(map) + '&t=' + track + '&l=' + leg +
      '&s=' + style + '&k=' + tier;
  }

  // ---- map list ----------------------------------------------------------
  var SORTS = {
    active: function (a, b) { return (b.last - a.last) || byName(a, b); },
    az: function (a, b) { return byName(a, b); },
    runs: function (a, b) { return (b.runs - a.runs) || byName(a, b); }
  };

  function byName(a, b) {
    var x = a.map.toLowerCase(), y = b.map.toLowerCase();
    return x < y ? -1 : x > y ? 1 : 0;
  }

  function renderList() {
    var maps = state.maps;
    if (!maps) { return; }
    var q = $('q').value.trim().toLowerCase();
    var list = maps.slice().sort(SORTS[state.sort]);
    var frag = document.createDocumentFragment();
    var timed = 0, shown = 0;
    maps.forEach(function (m) { if (m.runs > 0) { timed++; } });
    list.forEach(function (m) {
      if (q && m.map.toLowerCase().indexOf(q) < 0) { return; }
      shown++;
      var li = el('li', m.runs > 0 ? '' : 'opt');
      var a = el('a');
      a.href = '#m=' + encodeURIComponent(m.map);
      a.appendChild(el('span', 'who', m.map));
      if (m.wr) {
        a.appendChild(el('span', 'wr', fmt(m.wr.ms)));
        a.appendChild(el('span', 'why', plain(m.wr.name)));
        if (m.wr.ver) { a.appendChild(vchip()); }
      }
      if (m.runs > 0) {
        a.appendChild(el('span', 'why', m.runs + (m.runs === 1 ? ' run' : ' runs') +
          (m.last ? ' \u00b7 last ' + ago(m.last) : '')));
      } else {
        a.appendChild(el('span', 'why', 'no times yet'));
      }
      li.appendChild(a);
      frag.appendChild(li);
    });
    var ul = $('maps');
    ul.textContent = '';
    ul.appendChild(frag);
    $('summary').textContent = maps.length + ' maps \u00b7 ' + timed + ' with times' +
      (q ? ' \u00b7 ' + shown + ' matching' : '');
  }

  function showList() {
    $('map').hidden = true;
    $('list').hidden = false;
    document.title = 'FTESurf Leaderboard';
    if (state.maps) { renderList(); return; }
    get('api/maps').then(function (body) {
      state.maps = body.maps || [];
      showError('');
      renderList();
    }, function (e) {
      $('summary').textContent = '';
      showError(e.message);
    });
  }

  // ---- one map -----------------------------------------------------------
  function tabButton(label, n, pressed, go) {
    var b = el('button');
    b.type = 'button';
    b.setAttribute('aria-pressed', pressed ? 'true' : 'false');
    b.appendChild(document.createTextNode(label));
    if (n !== null) { b.appendChild(el('span', 'n', n)); }
    b.addEventListener('click', go);
    return b;
  }

  function go(v, track, leg, style, tier) {
    location.hash = hashFor(v.map, track, leg, style, tier);
  }

  function renderTabs(v) {
    var legs = $('legs'), styles = $('styles'), tiers = $('tiers');
    legs.textContent = ''; styles.textContent = ''; tiers.textContent = '';

    var seen = {}, pairs = [];
    v.boards.concat([{ track: v.track, leg: v.leg }]).forEach(function (b) {
      var k = b.track + ':' + b.leg;
      if (!seen[k]) { seen[k] = 1; pairs.push(b); }
    });
    pairs.sort(function (a, b) { return (a.track - b.track) || (a.leg - b.leg); });
    pairs.forEach(function (p) {
      legs.appendChild(tabButton(legName(p.track, p.leg), null,
        p.track === v.track && p.leg === v.leg,
        function () { go(v, p.track, p.leg, v.style, v.tier); }));
    });

    ['clean', 'segmented'].forEach(function (s) {
      var n = 0;
      v.boards.forEach(function (b) {
        if (b.track === v.track && b.leg === v.leg && b.tier === v.tier && b.style === s) { n = b.n; }
      });
      styles.appendChild(tabButton(cap(s), n, s === v.style,
        function () { go(v, v.track, v.leg, s, v.tier); }));
    });
    ['ranked', 'community'].forEach(function (k) {
      tiers.appendChild(tabButton(cap(k), v.counts[k] || 0, k === v.tier,
        function () { go(v, v.track, v.leg, v.style, k); }));
    });
  }

  function appendRows(v, rows) {
    var tbody = $('rows');
    rows.forEach(function (r) {
      var tr = el('tr');
      tr.appendChild(el('td', 'num', r.r));
      tr.appendChild(el('td', 'name', plain(r.name)));
      tr.appendChild(el('td', 'num', fmt(r.ms)));
      tr.appendChild(el('td', 'num gap', r.r === 1 ? '' : gap(r.ms - v.best)));
      tr.appendChild(el('td', 'date', day(r.when)));
      var c = el('td');
      if (r.ver) { c.appendChild(vchip()); }
      tr.appendChild(c);
      tbody.appendChild(tr);
    });
  }

  function renderMap(body) {
    var v = {
      map: body.disp, track: body.track, leg: body.leg, tier: body.tier,
      style: body.style, boards: body.boards || [], counts: body.counts || {},
      shown: 0, best: 0
    };
    state.view = v;
    document.title = body.disp + ' \u00b7 FTESurf Leaderboard';
    $('title').textContent = body.disp;
    renderTabs(v);
    $('rows').textContent = '';
    var rows = body.rows || [];
    if (rows.length && rows[0].r === 1) { v.best = rows[0].ms; }
    appendRows(v, rows);
    v.shown = rows.length;
    var total = v.counts[v.tier] || 0;
    $('table').hidden = rows.length === 0;
    $('more').hidden = v.shown >= total;
    var empty = $('empty');
    if (rows.length === 0) {
      var other = v.tier === 'ranked' ? 'community' : 'ranked';
      empty.textContent = 'No ' + v.tier + ' ' + v.style + ' times on ' +
        legName(v.track, v.leg) + ' yet' +
        (v.counts[other] ? ' \u00b7 ' + v.counts[other] + ' ' + other : '');
      empty.hidden = false;
    } else {
      empty.hidden = true;
    }
    // Make the address shareable once the server has picked the board.
    var full = hashFor(v.map, v.track, v.leg, v.style, v.tier);
    if (location.hash !== full && history.replaceState) {
      history.replaceState(null, '', full);
    }
  }

  function mapQuery(h, offset) {
    var q = 'api/map?map=' + encodeURIComponent(h.m);
    if (h.t !== undefined || h.l !== undefined || h.s !== undefined || h.k !== undefined) {
      q += '&track=' + encodeURIComponent(h.t || '0') + '&leg=' + encodeURIComponent(h.l || '0') +
        '&style=' + encodeURIComponent(h.s || 'clean') + '&tier=' + encodeURIComponent(h.k || 'ranked');
    }
    return q + (offset ? '&offset=' + offset : '');
  }

  function showMap(h) {
    $('list').hidden = true;
    $('map').hidden = false;
    $('title').textContent = h.m;
    var seq = ++state.seq;
    get(mapQuery(h, 0)).then(function (body) {
      if (seq !== state.seq) { return; }
      showError('');
      renderMap(body);
    }, function (e) {
      if (seq !== state.seq) { return; }
      $('table').hidden = true;
      $('more').hidden = true;
      $('empty').hidden = true;
      showError(e.message);
    });
  }

  function more() {
    var v = state.view;
    if (!v) { return; }
    var seq = state.seq;
    var h = { m: v.map, t: v.track, l: v.leg, s: v.style, k: v.tier };
    $('more').disabled = true;
    get(mapQuery(h, v.shown)).then(function (body) {
      $('more').disabled = false;
      if (seq !== state.seq || state.view !== v) { return; }
      var rows = body.rows || [];
      appendRows(v, rows);
      v.shown += rows.length;
      $('more').hidden = rows.length < PAGE || v.shown >= (v.counts[v.tier] || 0);
    }, function (e) {
      $('more').disabled = false;
      showError(e.message);
    });
  }

  function route() {
    var h = readHash();
    showError('');
    if (h.m) { showMap(h); } else { state.seq++; state.view = null; showList(); }
  }

  document.addEventListener('DOMContentLoaded', function () {
    $('q').addEventListener('input', renderList);
    var chips = document.querySelectorAll('.chip[data-sort]');
    Array.prototype.forEach.call(chips, function (c) {
      c.addEventListener('click', function () {
        state.sort = c.getAttribute('data-sort');
        Array.prototype.forEach.call(chips, function (o) {
          o.setAttribute('aria-pressed', o === c ? 'true' : 'false');
        });
        renderList();
      });
    });
    $('more').addEventListener('click', more);
    window.addEventListener('hashchange', route);
    route();
  });
})();
