/* Multi-entity timeline: lines + crosshair tooltip + legend + table view.
   Color follows the entity: a slot is assigned when an entity is added and never repainted. */
(function () {
  var C = window.Charts;
  var $ = function (id) { return document.getElementById(id); };
  var chartEl = $('tl-chart'), legendEl = $('tl-legend'), tableEl = $('tl-table');
  var ids = [], slotOf = {}, data = null;
  var mode = $('tl-mode').value;

  function freeSlot() {
    var used = new Set(Object.values(slotOf));
    for (var s = 1; s <= 8; s++) if (!used.has(s)) return s;
    return null;
  }
  function norm(id) { return C.GLOBAL ? String(id) : +id; }   // global views use string keys
  function add(id) {
    id = norm(id);
    if (ids.indexOf(id) >= 0 || ids.length >= 8) return;
    slotOf[id] = freeSlot(); ids.push(id); sync();
  }
  function remove(id) { ids = ids.filter(function (x) { return x !== id; }); delete slotOf[id]; sync(); }
  function color(id) { return C.css('--series-' + slotOf[id]); }

  function sync() {
    history.replaceState(null, '', '#' + ids.map(encodeURIComponent).join(','));
    if (!ids.length) { data = null; render(); return; }
    chartEl.style.opacity = 0.5;   // hold previous frame while refetching
    var qs = ids.map(function (i) { return 'id=' + encodeURIComponent(i); }).join('&');
    fetch(C.BASE + '/api/timeline?' + qs + '&mode=' + mode).then(function (r) { return r.json(); })
      .then(function (d) { data = d; chartEl.style.opacity = 1; render(); });
  }

  function render() {
    chartEl.replaceChildren(); legendEl.replaceChildren(); tableEl.replaceChildren();
    if (!data || !data.series.length) {
      chartEl.appendChild(C.el('p', 'muted small', 'Add entities above, or pick a preset.'));
      return;
    }
    // only years with enough dated documents to make a share meaningful
    var years = data.totals.filter(function (t) { return t.n >= 5; }).map(function (t) { return t.year; });
    var series = data.series.map(function (s) {
      return { id: s.id, name: s.name, type: s.type, values: s.values.filter(function (v) { return years.indexOf(v.year) >= 0; }) };
    });
    var unit = mode === 'share' ? '%' : ' docs';

    // legend (line keys) + remove buttons
    series.forEach(function (s) {
      var it = C.el('span', 'item');
      var k = C.el('span', 'line'); k.style.background = color(s.id); it.appendChild(k);
      var a = C.el('a', null, s.name); a.href = C.entityUrl(s.id); it.appendChild(a);
      var x = C.el('button', null, '×'); x.title = 'Remove'; x.style.cssText = 'padding:0 6px;font-size:12px';
      x.addEventListener('click', function () { remove(s.id); }); it.appendChild(x);
      legendEl.appendChild(it);
    });

    var W = Math.max(320, chartEl.clientWidth), H = 360;
    var direct = series.length <= 4;
    var m = { t: 12, r: direct ? 130 : 16, b: 28, l: 44 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var svg = d3.select(chartEl).append('svg').attr('viewBox', [0, 0, W, H]).attr('role', 'img')
      .attr('aria-label', 'Timeline of ' + series.map(function (s) { return s.name; }).join(', '));
    var g = svg.append('g').attr('transform', 'translate(' + m.l + ',' + m.t + ')');
    var x = d3.scaleLinear().domain(d3.extent(years)).range([0, iw]);
    var ymax = d3.max(series, function (s) { return d3.max(s.values, function (v) { return v.value; }); }) || 1;
    var y = d3.scaleLinear().domain([0, ymax]).nice(5).range([ih, 0]);
    y.ticks(5).forEach(function (tv) {
      g.append('line').attr('class', 'gridline').attr('x1', 0).attr('x2', iw).attr('y1', y(tv)).attr('y2', y(tv));
      g.append('text').attr('class', 'axis-label').attr('x', -8).attr('y', y(tv)).attr('dy', '0.32em').attr('text-anchor', 'end').text(tv + (mode === 'share' ? '%' : ''));
    });
    g.append('line').attr('class', 'baseline').attr('x1', 0).attr('x2', iw).attr('y1', ih).attr('y2', ih);
    var step = Math.ceil(years.length / Math.max(2, Math.floor(iw / 48)));
    years.forEach(function (yr, i) {
      if (i % step === 0 || i === years.length - 1) g.append('text').attr('class', 'axis-label').attr('x', x(yr)).attr('y', ih + 18)
        .attr('text-anchor', i === years.length - 1 ? 'end' : i === 0 ? 'start' : 'middle').text(yr);
    });
    var line = d3.line().x(function (v) { return x(v.year); }).y(function (v) { return y(v.value); });
    series.forEach(function (s) {
      g.append('path').attr('d', line(s.values)).attr('fill', 'none').attr('stroke', color(s.id))
        .attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');
    });
    // direct labels at line ends (<= 4 series), nudged apart to avoid collisions
    if (direct) {
      var ends = series.map(function (s) { var v = s.values[s.values.length - 1]; return { s: s, y: y(v.value) }; })
        .sort(function (a, b) { return a.y - b.y; });
      for (var i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
      // keep the stack inside the plot: backward pass clamps to the bottom edge
      for (var j = ends.length - 1; j >= 0; j--) {
        var limit = j === ends.length - 1 ? ih : ends[j + 1].y - 14;
        if (ends[j].y > limit) ends[j].y = limit;
      }
      ends.forEach(function (e) {
        g.append('text').attr('x', iw + 8).attr('y', e.y).attr('dy', '0.32em').style('font-size', '12px')
          .style('fill', 'var(--text-secondary)').text(e.s.name.length > 18 ? e.s.name.slice(0, 17) + '…' : e.s.name);
      });
    }
    // crosshair + markers + tooltip listing every series at the hovered year
    var cross = g.append('line').attr('class', 'baseline').attr('y1', 0).attr('y2', ih).style('display', 'none');
    var dots = g.append('g');
    g.append('rect').attr('width', iw).attr('height', ih).attr('fill', 'transparent')
      .on('pointermove', function (evt) {
        var px = d3.pointer(evt)[0];
        var yr = years.reduce(function (best, cur) { return Math.abs(x(cur) - px) < Math.abs(x(best) - px) ? cur : best; }, years[0]);
        cross.style('display', null).attr('x1', x(yr)).attr('x2', x(yr));
        dots.selectAll('circle').data(series).join('circle').attr('r', 4).attr('cx', x(yr))
          .attr('cy', function (s) { var v = s.values.find(function (v) { return v.year === yr; }); return y(v ? v.value : 0); })
          .attr('fill', function (s) { return color(s.id); }).attr('stroke', 'var(--surface-1)').attr('stroke-width', 2);
        var rows = [{ label: String(yr) }].concat(series.map(function (s) {
          var v = s.values.find(function (v) { return v.year === yr; });
          return { color: color(s.id), value: (v ? v.value : 0) + unit, label: s.name };
        }).sort(function (a, b) { return parseFloat(b.value) - parseFloat(a.value); }));
        C.showTip(evt, rows);
      })
      .on('pointerleave', function () { cross.style('display', 'none'); dots.selectAll('circle').remove(); C.hideTip(); });

    // table twin
    var t = C.el('table'); var hr = C.el('tr'); hr.appendChild(C.el('th', null, 'Year'));
    series.forEach(function (s) { hr.appendChild(C.el('th', 'num', s.name)); }); t.appendChild(hr);
    years.forEach(function (yr) {
      var tr = C.el('tr'); tr.appendChild(C.el('td', null, yr));
      series.forEach(function (s) { var v = s.values.find(function (v) { return v.year === yr; }); tr.appendChild(C.el('td', 'num', (v ? v.value : 0) + (mode === 'share' ? '%' : ''))); });
      t.appendChild(tr);
    });
    tableEl.appendChild(t);
  }

  C.autocomplete($('tl-input'), $('tl-ac'), function (it) { add(it.id); });
  $('tl-mode').addEventListener('change', function () { mode = this.value; sync(); });
  $('tl-clear').addEventListener('click', function () { ids = []; slotOf = {}; sync(); });
  $('tl-table-toggle').addEventListener('click', function () {
    var show = tableEl.style.display === 'none';
    tableEl.style.display = show ? 'block' : 'none';
    this.textContent = show ? 'Hide table' : 'Show table';
  });
  $('tl-preset').addEventListener('change', function () {
    var names = this.value ? this.value.split('|') : [];
    if (!names.length) return;
    ids = []; slotOf = {};
    Promise.all(names.map(function (n) {
      return fetch(C.BASE + '/api/entities?q=' + encodeURIComponent(n)).then(function (r) { return r.json(); })
        .then(function (rows) { return rows.find(function (r) { return r.name.toLowerCase() === n.toLowerCase(); }) || null; });
    })).then(function (found) { found.forEach(function (f) { if (f && ids.indexOf(f.id) < 0 && ids.length < 8) { slotOf[f.id] = freeSlot(); ids.push(f.id); } }); sync(); });
  });
  window.addEventListener('themechange', render);
  var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(render, 150); });

  var initial = location.hash.slice(1).split(',').filter(Boolean).map(decodeURIComponent)
    .filter(function (x) { return C.GLOBAL || /^\d+$/.test(x); }).slice(0, 8);
  if (initial.length) { initial.forEach(function (id) { slotOf[norm(id)] = freeSlot(); ids.push(norm(id)); }); sync(); }
  else if ($('tl-preset').options.length > 1) {
    $('tl-preset').selectedIndex = 1;           // the corpus's first preset
    $('tl-preset').dispatchEvent(new Event('change'));
  } else render();
})();
