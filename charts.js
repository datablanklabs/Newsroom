/* Shared chart helpers: tooltip, bar chart with hover + table view, autocomplete. */
window.Charts = (function () {
  // entity types present in this corpus and their labels come from the server (base.html)
  var TYPES = window.TYPES || ['person', 'agency', 'company', 'program', 'technology', 'place', 'organization', 'idea', 'identifier'];
  var TYPE_LABEL = window.TYPE_LABEL || {};
  var BASE = window.BASE || '';
  var GLOBAL = !!window.GLOBAL;   // the /all/ views: entity ids are global keys ('person:lee harvey oswald')

  // entity page, and the documents mentioning an entity (and optionally a second one)
  function entityUrl(id) { return GLOBAL ? BASE + '/entity?key=' + encodeURIComponent(id) : BASE + '/entity/' + id; }
  function docsUrl(id, id2) {
    if (GLOBAL) return entityUrl(id) + (id2 != null ? '&with=' + encodeURIComponent(id2) : '') + '#documents';
    return BASE + '/search?entity=' + id + (id2 != null ? '&entity2=' + id2 : '') + '&sort=date';
  }

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function typeColor(t) { return css('--t-' + t) || css('--text-muted'); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  // ---- tooltip (all labels inserted with textContent: names come from the documents)
  var tip;
  function showTip(evt, rows) {
    tip = tip || document.getElementById('tooltip');
    tip.replaceChildren();
    rows.forEach(function (r) {
      var row = el('div', 'row');
      if (r.color) { var k = el('span', 'key'); k.style.background = r.color; row.appendChild(k); }
      if (r.value != null) row.appendChild(el('span', 'tv', r.value));
      if (r.label != null) row.appendChild(el('span', 'tl', r.label));
      tip.appendChild(row);
    });
    tip.style.display = 'block';
    moveTip(evt);
  }
  function moveTip(evt) {
    if (!tip) return;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var x = evt.clientX + 14, y = evt.clientY + 14;
    if (x + w > window.innerWidth - 8) x = evt.clientX - w - 14;
    if (y + h > window.innerHeight - 8) y = evt.clientY - h - 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hideTip() { if (tip) tip.style.display = 'none'; }

  function barPath(x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h));
    return 'M' + x + ',' + (y + h) + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y +
      'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + (y + h) + 'Z';
  }

  // ---- single-series bar chart over a continuous integer x (years); missing x filled with 0
  function bars(container, opts) {
    if (!container) return;
    opts = opts || {};
    var xKey = container.dataset.x || 'year', yKey = container.dataset.y || 'n', yLabel = container.dataset.ylabel || '';
    var raw = JSON.parse(container.dataset.rows || '[]');
    if (!raw.length) { container.appendChild(el('div', 'small muted', 'No dated documents.')); return; }
    var byX = {}; raw.forEach(function (r) { byX[r[xKey]] = r[yKey]; });
    var xs = raw.map(function (r) { return +r[xKey]; });
    var lo = Math.min.apply(null, xs), hi = Math.max.apply(null, xs);
    var data = []; for (var x = lo; x <= hi; x++) data.push({ x: x, y: byX[x] || 0 });
    var compact = !!opts.compact;

    var svgHolder = el('div'); container.appendChild(svgHolder);
    var tableHolder = el('div'); tableHolder.style.display = 'none'; container.appendChild(tableHolder);
    if (!compact) {
      var toggle = el('button', 'viewtoggle', 'Show table'); toggle.style.marginTop = '6px';
      toggle.addEventListener('click', function () {
        var showing = tableHolder.style.display !== 'none';
        tableHolder.style.display = showing ? 'none' : 'block'; svgHolder.style.display = showing ? 'block' : 'none';
        toggle.textContent = showing ? 'Show table' : 'Show chart';
      });
      container.appendChild(toggle);
      var t = el('table'); var hr = el('tr'); hr.appendChild(el('th', null, 'Year')); hr.appendChild(el('th', 'num', yLabel || 'value')); t.appendChild(hr);
      data.forEach(function (d) { var tr = el('tr'); tr.appendChild(el('td', null, d.x)); tr.appendChild(el('td', 'num', d.y.toLocaleString())); t.appendChild(tr); });
      tableHolder.appendChild(t);
    }

    function draw() {
      svgHolder.replaceChildren();
      var W = Math.max(200, svgHolder.clientWidth || container.clientWidth || 400);
      var H = opts.height || 220;
      var m = compact ? { t: 6, r: 4, b: 18, l: 4 } : { t: 10, r: 8, b: 24, l: 40 };
      var iw = W - m.l - m.r, ih = H - m.t - m.b;
      var svg = d3.select(svgHolder).append('svg').attr('viewBox', [0, 0, W, H]).attr('role', 'img')
        .attr('aria-label', (yLabel || 'values') + ' per year, ' + lo + ' to ' + hi);
      var xs = d3.scaleBand().domain(data.map(function (d) { return d.x; })).range([0, iw]).paddingInner(0);
      var ymax = d3.max(data, function (d) { return d.y; }) || 1;
      var ys = d3.scaleLinear().domain([0, ymax]).nice(compact ? 2 : 4).range([ih, 0]);
      var g = svg.append('g').attr('transform', 'translate(' + m.l + ',' + m.t + ')');
      if (!compact) {
        ys.ticks(4).forEach(function (tv) {
          g.append('line').attr('class', 'gridline').attr('x1', 0).attr('x2', iw).attr('y1', ys(tv)).attr('y2', ys(tv));
          g.append('text').attr('class', 'axis-label').attr('x', -8).attr('y', ys(tv)).attr('dy', '0.32em').attr('text-anchor', 'end').text(tv.toLocaleString());
        });
      }
      var bw = xs.bandwidth(), gap = Math.min(2, bw * 0.25);
      var markW = Math.min(bw - gap, 48), inset = (bw - markW) / 2;   // thin marks even when there are few bars
      g.selectAll('path.bar').data(data).join('path').attr('class', 'bar')
        .attr('d', function (d) { var h = ih - ys(d.y); return h > 0 ? barPath(xs(d.x) + inset, ys(d.y), Math.max(1, markW), h, 4) : ''; });
      g.append('line').attr('class', 'baseline').attr('x1', 0).attr('x2', iw).attr('y1', ih).attr('y2', ih);
      var step = Math.ceil(data.length / Math.max(2, Math.floor(iw / (compact ? 34 : 44))));
      data.forEach(function (d, i) {
        if (i % step === 0 || i === data.length - 1 && compact) {
          g.append('text').attr('class', 'axis-label').attr('x', xs(d.x) + bw / 2).attr('y', ih + 14).attr('text-anchor', 'middle').text(compact ? "'" + String(d.x).slice(2) : d.x);
        }
      });
      // hit targets: full-height columns (bigger than the mark)
      g.selectAll('rect.hit').data(data).join('rect').attr('class', 'hit')
        .attr('x', function (d) { return xs(d.x); }).attr('y', 0).attr('width', bw).attr('height', ih)
        .attr('fill', 'transparent').style('cursor', opts.onClick ? 'pointer' : 'default')
        .attr('tabindex', compact ? null : 0)
        .on('pointerenter focus', function (evt, d) {
          g.selectAll('path.bar').classed('hover', function (b) { return b === d; });
          showTip(evt.type === 'focus' ? { clientX: this.getBoundingClientRect().x, clientY: this.getBoundingClientRect().y } : evt,
            [{ value: d.y.toLocaleString(), label: (yLabel ? yLabel + ' · ' : '') + d.x }]);
        })
        .on('pointermove', moveTip)
        .on('pointerleave blur', function () { g.selectAll('path.bar').classed('hover', false); hideTip(); })
        .on('click', function (evt, d) { if (opts.onClick && d.y) opts.onClick({ year: d.x, n: d.y }); });
    }
    draw();
    var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(draw, 150); });
  }

  // ---- entity autocomplete
  function autocomplete(input, list, onPick) {
    var items = [], sel = -1, timer;
    function render() {
      list.replaceChildren();
      items.forEach(function (it, i) {
        var row = el('div', 't-' + it.type + (i === sel ? ' sel' : ''));
        row.appendChild(el('span', 'dot'));
        row.appendChild(el('span', null, it.name));
        row.appendChild(el('span', 'small muted', ' ' + TYPE_LABEL[it.type] + ' · ' + it.doc_count + ' docs' +
          (it.n_corpora > 1 ? ' · ' + it.n_corpora + ' collections' : '')));
        row.addEventListener('mousedown', function (e) { e.preventDefault(); pick(i); });
        list.appendChild(row);
      });
      list.style.display = items.length ? 'block' : 'none';
    }
    function pick(i) { var it = items[i]; if (!it) return; items = []; render(); input.value = ''; onPick(it); }
    input.addEventListener('input', function () {
      clearTimeout(timer);
      var v = input.value.trim();
      if (v.length < 2) { items = []; render(); return; }
      timer = setTimeout(function () {
        fetch(BASE + '/api/entities?q=' + encodeURIComponent(v)).then(function (r) { return r.json(); })
          .then(function (rows) { items = rows; sel = rows.length ? 0 : -1; render(); });
      }, 120);
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { sel = Math.min(items.length - 1, sel + 1); render(); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { sel = Math.max(0, sel - 1); render(); e.preventDefault(); }
      else if (e.key === 'Enter') { pick(sel); e.preventDefault(); }
      else if (e.key === 'Escape') { items = []; render(); }
    });
    input.addEventListener('blur', function () { setTimeout(function () { items = []; render(); }, 150); });
  }

  return { TYPES: TYPES, TYPE_LABEL: TYPE_LABEL, BASE: BASE, GLOBAL: GLOBAL, entityUrl: entityUrl, docsUrl: docsUrl, css: css, typeColor: typeColor, el: el,
    showTip: showTip, moveTip: moveTip, hideTip: hideTip, bars: bars, autocomplete: autocomplete, barPath: barPath };
})();
