// Public leaderboard page.  Every URL is relative (the proxy adds a prefix),
// and every server string is set with textContent: names are player-chosen.
//
// Five views behind one hash route -- map list, one board, one run, one player,
// player search.  The run view's canvas work lives in runview.js; this file
// does the fetching, the lists and the routing.
(function () {
  'use strict';

  var PAGE = 50;
  var state = {
    maps: null, sort: 'active', mt: 0, view: null, seq: 0, run: null
  };

  // Difficulty tiers come from Momentum's own map metadata (tools/msml.py reads
  // the game's _cache; surfd serves it as `mt`).  A map with no rating has no
  // `mt` at all rather than tier 0 -- unrated and "tier zero" are not the same
  // claim, and the filter has to be able to say so.
  var TIER_MAX = 10;

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined && text !== null) { e.textContent = String(text); }
    return e;
  }

  // Quake colour codes: ^0-^9, ^xRGB, ^&FB and a few style letters; ^^ is a caret.
  // surfd has a copy of this rule (web_plain) for matching a search; change both.
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

  function n0(x) { return x || 0; }

  function vchip() {
    var c = el('span', 'vchip', 'VERIFIED');
    c.title = 'Re-simulated exactly by the server, or reviewed';
    return c;
  }

  // Source, in one word, with why it matters in the tooltip.  The blue
  // is LN_FGNCOL from cl_lines.qc, so an imported row reads the same colour here
  // as the imported line does in the game.
  var SRC = {
    momentum: ['MOM', 'Imported from Momentum Mod. The time is theirs; the line '
      + 'is reconstructed from their demo and is lower fidelity than ours.'],
    ksf: ['KSF', 'Imported from the KSF Counter-Strike: Source servers. Time '
      + 'only — KSF publishes no demo we can read.'],
    ranked: ['OURS', 'Set on an official FTESurf server and re-simulated here.']
  };

  function srcChip(tier) {
    var s = SRC[tier];
    if (!s) { return null; }
    var c = el('span', 'src src-' + tier, s[0]);
    c.title = s[1];
    return c;
  }

  function mtBadge(mt) {
    if (!mt) { return null; }
    var b = el('span', 'mt', 'T' + mt);
    b.title = 'Momentum difficulty tier ' + mt;
    return b;
  }

  function legName(track, leg) {
    if (track <= 0) { return leg <= 0 ? 'Main' : 'Stage ' + leg; }
    return leg <= 0 ? 'Bonus ' + track : 'Bonus ' + track + ' · Stage ' + leg;
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
      if (r.status === 404) { throw new Error('Not found'); }
      if (r.status === 422) { throw new Error('That recording could not be read'); }
      if (!r.ok) { throw new Error('Could not load the board (HTTP ' + r.status + ')'); }
      return r.json();
    }, function () { throw new Error('Could not reach the server'); });
  }

  // ---- hash --------------------------------------------------------------
  //   #m=<map>&t=&l=&s=&tier=   one board
  //   #r=<rid>                  one run
  //   #p=<handle>               one player
  //   #who=<query>              player search
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
      '&s=' + style + (tier && tier !== 'ranked' ? '&tier=' + tier : '');
  }

  function link(cls, href, text) {
    var a = el('a', cls, text);
    a.href = href;
    return a;
  }

  function showOnly(id) {
    ['list', 'map', 'run', 'player', 'people'].forEach(function (k) {
      $(k).hidden = k !== id;
    });
    if (state.run && id !== 'run') { state.run.destroy(); state.run = null; }
  }

  // ---- map list ----------------------------------------------------------
  var SORTS = {
    active: function (a, b) { return (b.last - a.last) || byName(a, b); },
    az: function (a, b) { return byName(a, b); },
    runs: function (a, b) { return (b.runs - a.runs) || byName(a, b); },
    times: function (a, b) {
      return ((b.imp + b.runs) - (a.imp + a.runs)) || byName(a, b);
    },
    demos: function (a, b) { return (n0(b.reps) - n0(a.reps)) || byName(a, b); },
    tier: function (a, b) { return (n0(a.mt) - n0(b.mt)) || byName(a, b); }
  };

  function byName(a, b) {
    var x = a.map.toLowerCase(), y = b.map.toLowerCase();
    return x < y ? -1 : x > y ? 1 : 0;
  }

  function tierRow() {
    var row = $('tiers');
    if (row.firstChild) { return; }
    var mk = function (v, label, title) {
      var b = el('button', 'chip', label);
      b.type = 'button';
      b.title = title;
      b.setAttribute('aria-pressed', state.mt === v ? 'true' : 'false');
      b.addEventListener('click', function () {
        state.mt = state.mt === v ? 0 : v;
        Array.prototype.forEach.call(row.children, function (o) {
          o.setAttribute('aria-pressed',
            o === b && state.mt === v ? 'true' : 'false');
        });
        renderList();
      });
      return b;
    };
    row.appendChild(mk(-1, 'Unrated', 'Maps Momentum has not given a tier'));
    for (var t = 1; t <= TIER_MAX; t++) {
      row.appendChild(mk(t, 'T' + t, 'Momentum difficulty tier ' + t));
    }
  }

  function passTier(m) {
    if (!state.mt) { return true; }
    if (state.mt === -1) { return !m.mt; }
    return m.mt === state.mt;
  }

  function renderList() {
    var maps = state.maps;
    if (!maps) { return; }
    var q = $('q').value.trim().toLowerCase();
    var list = maps.slice().sort(SORTS[state.sort]);
    var frag = document.createDocumentFragment();
    var timed = 0, watch = 0, shown = 0;
    maps.forEach(function (m) {
      if (m.runs > 0 || m.imp > 0) { timed++; }
      watch += n0(m.reps);
    });
    list.forEach(function (m) {
      if (q && m.map.toLowerCase().indexOf(q) < 0) { return; }
      if (!passTier(m)) { return; }
      shown++;
      var has = m.runs > 0 || m.imp > 0;
      var li = el('li', has ? '' : 'opt');
      var a = el('a');
      a.href = '#m=' + encodeURIComponent(m.map);
      var who = el('span', 'who', m.map);
      a.appendChild(who);
      var badge = mtBadge(m.mt);
      if (badge) { a.appendChild(badge); }
      if (m.wr) {
        a.appendChild(el('span', 'wr', fmt(m.wr.ms)));
        a.appendChild(el('span', 'why', plain(m.wr.name)));
        if (m.wr.ver) { a.appendChild(vchip()); }
      }
      var bits = [];
      if (m.runs > 0) {
        bits.push(m.runs + (m.runs === 1 ? ' run' : ' runs') +
          (m.last ? ' · last ' + ago(m.last) : ''));
      }
      if (m.imp > 0) { bits.push(m.imp + ' imported'); }
      if (n0(m.reps) > 0) { bits.push(m.reps + ' to watch'); }
      if (!bits.length) { bits.push('no times yet'); }
      if (!m.have) { bits.push('not installed here'); }
      a.appendChild(el('span', 'why', bits.join(' · ')));
      li.appendChild(a);
      frag.appendChild(li);
    });
    var ul = $('maps');
    ul.textContent = '';
    ul.appendChild(frag);
    var bits = [maps.length + ' maps', timed + ' with times',
                watch.toLocaleString() + ' runs to watch'];
    if (q || state.mt) { bits.push(shown + ' matching'); }
    $('summary').textContent = bits.join(' · ');
  }

  function showList() {
    showOnly('list');
    document.title = 'FTESurf Leaderboard';
    tierRow();
    if (state.maps) { renderList(); return; }
    get('api/maps').then(function (body) {
      state.maps = (body.maps || []).map(function (m) {
        if (m.imp === undefined) { m.imp = 0; }
        return m;
      });
      $('tiers').hidden = !body.tiers;
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

  var TIER_TABS = [['ranked', 'Ours'], ['imported', 'Imported'],
                   ['combined', 'Combined']];

  function renderTabs(v, counts) {
    var legs = $('legs'), styles = $('styles'), srcs = $('srcs');
    legs.textContent = ''; styles.textContent = ''; srcs.textContent = '';

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
        if (b.track === v.track && b.leg === v.leg && b.style === s) { n = b.n + n0(b.ni); }
      });
      styles.appendChild(tabButton(cap(s), n, s === v.style,
        function () { go(v, v.track, v.leg, s, v.tier); }));
    });

    var imp = n0(counts.momentum) + n0(counts.ksf);
    [['ranked', n0(counts.ranked)], ['imported', imp],
     ['combined', n0(counts.ranked) + imp]].forEach(function (p, i) {
      srcs.appendChild(tabButton(TIER_TABS[i][1], p[1], p[0] === v.tier,
        function () { go(v, v.track, v.leg, v.style, p[0]); }));
    });
  }

  function appendRows(v, rows) {
    var tbody = $('rows');
    rows.forEach(function (r) {
      var tier = r.tr || v.tier;
      if (tier === 'combined' || tier === 'imported') { tier = 'momentum'; }
      var tr = el('tr', tier !== 'ranked' ? 'foreign' : '');
      tr.appendChild(el('td', 'num', r.r));
      var who = el('td', 'name');
      who.appendChild(link('plink', '#p=' + r.who, plain(r.name)));
      if (v.tier !== 'ranked') {
        var c = srcChip(r.tr || 'ranked');
        if (c) { who.appendChild(c); }
      }
      tr.appendChild(who);
      tr.appendChild(el('td', 'num', fmt(r.ms)));
      tr.appendChild(el('td', 'num gap', r.r === 1 ? '' : gap(r.ms - v.best)));
      tr.appendChild(el('td', 'date', day(r.when)));
      var act = el('td', 'act');
      if (r.rep) {
        act.appendChild(link('watch', '#r=' + r.rep, 'Watch'));
      } else if (r.run) {
        act.appendChild(link('watch dim', '#r=' + r.run, 'Full run'));
      }
      if (r.ver) { act.appendChild(vchip()); }
      tr.appendChild(act);
      tbody.appendChild(tr);
    });
  }

  function renderMap(body) {
    var v = {
      map: body.disp, key: body.map, track: body.track, leg: body.leg,
      style: body.style, tier: body.tier || 'ranked',
      boards: body.boards || [], total: body.n || 0, shown: 0, best: 0
    };
    state.view = v;
    document.title = body.disp + ' · FTESurf Leaderboard';
    var title = $('title');
    title.textContent = body.disp;
    var badge = mtBadge(body.mt);
    if (badge) { title.appendChild(document.createTextNode(' ')); title.appendChild(badge); }
    renderTabs(v, body.counts || {});
    $('rows').textContent = '';
    var rows = body.rows || [];
    if (rows.length && rows[0].r === 1) { v.best = rows[0].ms; }
    appendRows(v, rows);
    v.shown = rows.length;
    $('table').hidden = rows.length === 0;
    $('more').hidden = v.shown >= v.total;
    var empty = $('empty');
    if (rows.length === 0) {
      empty.textContent = 'No ' + v.style + ' times on ' +
        legName(v.track, v.leg) + ' yet';
      empty.hidden = false;
    } else {
      empty.hidden = true;
    }
    var note = $('mapnote');
    note.textContent = body.have ? ''
      : 'This map is not installed on the servers — the times below are '
        + 'imported, and you cannot play it here yet.';
    note.hidden = !!body.have;
    var full = hashFor(v.map, v.track, v.leg, v.style, v.tier);
    if (location.hash !== full && history.replaceState) {
      history.replaceState(null, '', full);
    }
  }

  function mapQuery(h, offset) {
    var q = 'api/map?map=' + encodeURIComponent(h.m);
    if (h.t !== undefined || h.l !== undefined || h.s !== undefined) {
      q += '&track=' + encodeURIComponent(h.t || '0') +
        '&leg=' + encodeURIComponent(h.l || '0') +
        '&style=' + encodeURIComponent(h.s || 'clean');
    }
    if (h.tier) { q += '&tier=' + encodeURIComponent(h.tier); }
    return q + (offset ? '&offset=' + offset : '');
  }

  function showMap(h) {
    showOnly('map');
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
    var h = { m: v.key, t: v.track, l: v.leg, s: v.style, tier: v.tier };
    $('more').disabled = true;
    get(mapQuery(h, v.shown)).then(function (body) {
      $('more').disabled = false;
      if (seq !== state.seq || state.view !== v) { return; }
      var rows = body.rows || [];
      appendRows(v, rows);
      v.shown += rows.length;
      $('more').hidden = rows.length < PAGE || v.shown >= v.total;
    }, function (e) {
      $('more').disabled = false;
      showError(e.message);
    });
  }

  // ---- one run -----------------------------------------------------------
  function dlRow(dl, k, v) {
    dl.appendChild(el('dt', null, k));
    dl.appendChild(el('dd', null, v));
  }

  function renderRun(body, at) {
    var imported = body.tr !== 'ranked';
    document.title = plain(body.name) + ' on ' + body.disp + ' · FTESurf';
    var h = $('runtitle');
    h.textContent = '';
    h.appendChild(el('span', 'rt-time', fmt(body.ms)));
    h.appendChild(el('span', 'rt-sep', '·'));
    h.appendChild(link('rt-map', hashFor(body.disp, body.track, body.leg,
      body.style, imported ? 'combined' : 'ranked'), body.disp));

    var sub = $('runsub');
    sub.textContent = '';
    sub.appendChild(link('plink', '#p=' + body.who, plain(body.name)));
    var chip = srcChip(body.tr);
    if (chip) { sub.appendChild(chip); }
    sub.appendChild(el('span', 'why', legName(body.track, body.leg) + ' · ' +
      cap(body.style) + ' · ' + day(body.when)));
    if (body.ext) {
      sub.appendChild(link('dimlink',
        'https://momentum-mod.org/profile/' + encodeURIComponent(body.ext),
        'Momentum profile ↗'));
    }

    var st = $('runstats');
    st.textContent = '';
    var add = function (label, value, title) {
      var d = el('div', 'stat');
      var n = el('span', 'sv', value);
      d.appendChild(n);
      d.appendChild(el('span', 'sl', label));
      if (title) { d.title = title; }
      st.appendChild(d);
    };
    add('top speed', Math.round(body.stats.max_speed) + ' u/s');
    add('average', Math.round(body.stats.avg_speed) + ' u/s');
    add('duration', body.stats.duration.toFixed(2) + ' s');
    add('samples', body.n + (body.stride > 1 ? ' /' + body.stride : ''),
        body.stride > 1 ? 'Plotted every ' + body.stride + 'th sample' : '');

    if (state.run) { state.run.destroy(); }
    state.run = new window.FSRun.View($('runcanvas'), body, {
      tint: imported ? 0.45 : 0,
      at: at,
      onpause: function (t) {
        if (!history.replaceState) { return; }
        history.replaceState(null, '', '#r=' + body.rid +
          (t > 0.05 ? '&at=' + t.toFixed(2) : ''));
      }
    });

    // The imported caveat goes next to the line, not in a footnote: the shape
    // is reconstructed from a demo that was never meant to be replayed here.
    var warn = $('runwarn');
    warn.textContent = imported
      ? 'Reconstructed from an imported demo. The time is the source’s; the '
        + 'path is derived and lower fidelity than a run recorded here.'
      : '';
    warn.hidden = !imported;

    var dl = $('runhead');
    dl.textContent = '';
    dlRow(dl, 'map', body.head.map || body.map);
    dlRow(dl, 'leg', legName(body.track, body.leg));
    dlRow(dl, 'ticks', String(body.ticks));
    if (body.head.tickrate) { dlRow(dl, 'tick interval', body.head.tickrate + ' s'); }
    if (body.head.clock) { dlRow(dl, 'clock', body.head.clock); }
    if (body.head.startseg !== undefined) {
      dlRow(dl, 'start segment', String(body.head.startseg));
    }
    dlRow(dl, 'recording', (body.bytes > 0
      ? (body.bytes / 1024).toFixed(0) + ' KiB' : 'size unknown'));
    if (body.truncated) { dlRow(dl, 'note', 'the file was read up to a limit'); }
    $('rundl').href = '../api/replay/' + body.rid;

    var sp = $('runsplits');
    sp.textContent = '';
    var splits = body.splits || [];
    $('splitwrap').hidden = splits.length === 0;
    splits.forEach(function (s, i) {
      var li = el('li');
      li.appendChild(el('span', 'sp-k', 'Split ' + (s[0] !== undefined ? s[0] : i + 1)));
      var secs = body.rate ? s[1] * body.rate : null;
      li.appendChild(el('span', 'sp-v', secs === null ? s[1] + ' ticks'
        : window.FSRun.fmt(secs * 1000)));
      sp.appendChild(li);
    });
  }

  function showRun(rid, at) {
    showOnly('run');
    var seq = ++state.seq;
    $('runtitle').textContent = 'Loading…';
    get('api/run/' + encodeURIComponent(rid)).then(function (body) {
      if (seq !== state.seq) { return; }
      showError('');
      renderRun(body, Number(at) > 0 ? Number(at) : 0);
    }, function (e) {
      if (seq !== state.seq) { return; }
      $('runtitle').textContent = '';
      showError(e.message === 'Not found'
        ? 'That run is not available to watch' : e.message);
    });
  }

  // ---- players -----------------------------------------------------------
  function personRow(p) {
    var li = el('li');
    var a = el('a');
    a.href = '#p=' + p.who;
    a.appendChild(el('span', 'who', plain(p.name) || '(no name)'));
    var chip = srcChip(p.src);
    if (chip) { a.appendChild(chip); }
    a.appendChild(el('span', 'wr', p.n + (p.n === 1 ? ' time' : ' times')));
    a.appendChild(el('span', 'why', p.maps + ' maps' +
      (p.last ? ' · last ' + ago(p.last) : '')));
    li.appendChild(a);
    return li;
  }

  function showPeople(q) {
    showOnly('people');
    document.title = 'Players · FTESurf';
    var box = $('pq');
    if (box.value !== q) { box.value = q; }
    var seq = ++state.seq;
    get('api/players' + (q ? '?q=' + encodeURIComponent(q) : ''))
      .then(function (body) {
        if (seq !== state.seq) { return; }
        showError('');
        var ul = $('people-list');
        ul.textContent = '';
        var frag = document.createDocumentFragment();
        (body.players || []).forEach(function (p) { frag.appendChild(personRow(p)); });
        ul.appendChild(frag);
        var shown = (body.players || []).length;
        $('psummary').textContent = body.n === 0
          ? (q ? 'No player matches “' + q + '”' : 'No players yet')
          : body.n + ' player' + (body.n === 1 ? '' : 's') +
            (shown < body.n ? ' · showing the top ' + shown : '');
      }, function (e) {
        if (seq !== state.seq) { return; }
        $('people-list').textContent = '';
        $('psummary').textContent = '';
        showError(e.message);
      });
  }

  function bar(done, of) {
    var wrap = el('div', 'bar');
    var fill = el('i');
    fill.style.width = (of > 0 ? Math.round((done / of) * 100) : 0) + '%';
    wrap.appendChild(fill);
    return wrap;
  }

  function renderProfile(body) {
    document.title = plain(body.name) + ' · FTESurf';
    var h = $('ptitle');
    h.textContent = plain(body.name) || '(no name)';
    var sub = $('psub');
    sub.textContent = '';
    var chip = srcChip(body.src);
    if (chip) { sub.appendChild(chip); }
    if (body.ext) {
      sub.appendChild(link('dimlink',
        'https://momentum-mod.org/profile/' + encodeURIComponent(body.ext),
        'Momentum profile ↗'));
    }
    if (body.last) { sub.appendChild(el('span', 'why', 'last time ' + ago(body.last))); }

    var st = $('pstats');
    st.textContent = '';
    var add = function (v, label, title) {
      var d = el('div', 'stat');
      d.appendChild(el('span', 'sv', v));
      d.appendChild(el('span', 'sl', label));
      if (title) { d.title = title; }
      st.appendChild(d);
    };
    add(body.n, body.n === 1 ? 'time' : 'times');
    // The headline is the CONTESTED count. Most imported stage boards hold one
    // row -- the only person we have a time for -- and counting those as
    // records read as 35 where 34 were uncontested. The raw figure is still
    // here, in the tooltip, because it is not nothing.
    var wrc = n0(body.wrc);
    add(wrc, wrc === 1 ? 'record' : 'records',
        'First on ' + wrc + ' board' + (wrc === 1 ? '' : 's') +
        ' where somebody else has a time too — ' + n0(body.wr) +
        ' first places counting boards nobody else is on');
    if (n0(body.top10)) {
      add(body.top10, 'top tens', 'Top ten on a board with more than one time');
    }
    add(body.maps, 'maps');
    var c = body.completion;
    if (c) {
      add(c.done + ' / ' + c.of, 'maps finished',
          'A map counts once the main track is finished');
    }

    var comp = $('pcomp'), wrap = $('compwrap');
    comp.textContent = '';
    if (!c) {
      // A MISSING CATALOGUE IS NOT 0%.  surfd sends completion: null when it has
      // no map difficulty data, and the page has to say that rather than draw
      // empty bars that look like a player who has done nothing.
      wrap.hidden = false;
      $('compnote').textContent =
        'Difficulty tiers are unavailable on this server, so per-tier '
        + 'completion cannot be shown.';
      $('compnote').hidden = false;
    } else {
      $('compnote').hidden = true;
      wrap.hidden = c.tiers.length === 0;
      c.tiers.forEach(function (t) {
        var row = el('div', 'crow');
        var lbl = el('span', 'ck', 'Tier ' + t.tier);
        lbl.title = 'Momentum difficulty tier ' + t.tier;
        row.appendChild(lbl);
        row.appendChild(bar(t.done, t.of));
        row.appendChild(el('span', 'cv', t.done + ' / ' + t.of));
        comp.appendChild(row);
      });
      if (c.untiered) {
        var note = el('div', 'crow crow-dim');
        note.appendChild(el('span', 'ck', 'Unrated'));
        note.appendChild(el('span', 'cfree',
          c.untiered + ' maps carry no difficulty tier'));
        comp.appendChild(note);
      }
    }

    var bt = body.by_tier || {};
    var multi = ['ranked', 'momentum', 'ksf']
      .filter(function (k) { return n0(bt[k]) > 0; }).length > 1;
    var tbody = $('prows');
    tbody.textContent = '';
    (body.rows || []).forEach(function (r) {
      var tr = el('tr', r.tr !== 'ranked' ? 'foreign' : '');
      var pos = el('td', 'num');
      pos.appendChild(el('span', r.r === 1 ? 'gold' : null, '#' + r.r));
      pos.appendChild(el('span', 'of', ' / ' + r.of));
      tr.appendChild(pos);
      var mp = el('td', 'name');
      mp.appendChild(link('plink', hashFor(r.disp, r.track, r.leg, r.style,
        r.tr === 'ranked' ? 'ranked' : 'combined'), r.disp));
      // Only when the profile actually spans sources: a chip on every row of a
      // single-source profile is noise that says the same thing 100 times.
      if (multi) {
        var ch = srcChip(r.tr);
        if (ch) { mp.appendChild(ch); }
      }
      tr.appendChild(mp);
      tr.appendChild(el('td', 'leg', legName(r.track, r.leg)));
      tr.appendChild(el('td', 'num', fmt(r.ms)));
      tr.appendChild(el('td', 'date', day(r.when)));
      var act = el('td', 'act');
      if (r.rep) { act.appendChild(link('watch', '#r=' + r.rep, 'Watch')); }
      tr.appendChild(act);
      tbody.appendChild(tr);
    });
    $('ptable').hidden = (body.rows || []).length === 0;
  }

  function showProfile(handle) {
    showOnly('player');
    $('ptitle').textContent = 'Loading…';
    var seq = ++state.seq;
    get('api/player/' + encodeURIComponent(handle)).then(function (body) {
      if (seq !== state.seq) { return; }
      showError('');
      renderProfile(body);
    }, function (e) {
      if (seq !== state.seq) { return; }
      $('ptitle').textContent = '';
      showError(e.message === 'Not found' ? 'No such player' : e.message);
    });
  }

  // ---- routing -----------------------------------------------------------
  function route() {
    var h = readHash();
    showError('');
    if (h.r) { showRun(h.r, h.at); return; }
    if (h.p) { showProfile(h.p); return; }
    if (h.who !== undefined) { showPeople(h.who); return; }
    if (h.m) { showMap(h); return; }
    state.seq++;
    state.view = null;
    showList();
  }

  var tsearch = 0;

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
    $('pq').addEventListener('input', function () {
      var v = $('pq').value.trim();
      window.clearTimeout(tsearch);
      tsearch = window.setTimeout(function () {
        location.hash = '#who=' + encodeURIComponent(v);
      }, 220);
    });
    window.addEventListener('hashchange', route);
    route();
  });
})();
