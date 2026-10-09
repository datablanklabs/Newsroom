/* Force-directed entity network (d3-force). Color + shape both encode entity type. */
window.NetGraph = (function () {
  var C = window.Charts;
  var SHAPES = {
    person: d3.symbolCircle, agency: d3.symbolSquare, company: d3.symbolDiamond, program: d3.symbolTriangle,
    technology: d3.symbolWye, place: d3.symbolCross, organization: d3.symbolStar, idea: d3.symbolCircle,
    identifier: d3.symbolSquare
  };
  var HOLLOW = { idea: true, identifier: true };   // drawn as outlines: themes (ring) and identifiers (square)

  function mount(container, params) {
    var state = { params: Object.assign({ limit: 160, k: 6, minDocs: 4, metric: 'docs', types: C.TYPES.slice(), hideAuto: false, maxDf: 1000000, focus: null, source: 'cooccurrence' }, params) };
    var svg = d3.select(container).append('svg').attr('role', 'img').attr('aria-label', 'Entity relationship network');
    var root = svg.append('g');
    var gLinks = root.append('g'), gNodes = root.append('g'), gLabels = root.append('g');
    var status = container.querySelector('.status');
    var sim, nodes = [], links = [], adj = {}, selected = null, fitted = false;
    var zoom = d3.zoom().scaleExtent([0.15, 6]).on('zoom', function (e) { root.attr('transform', e.transform); });
    svg.call(zoom).on('dblclick.zoom', null);

    function url() {
      var p = state.params;
      var u = C.BASE + '/api/graph?limit=' + p.limit + '&k=' + p.k + '&min_docs=' + p.minDocs + '&metric=' + p.metric +
        '&types=' + p.types.join(',') + '&max_df=' + p.maxDf + (p.hideAuto ? '&hide_auto=1' : '') + '&source=' + p.source;
      if (p.focus) u += '&focus=' + encodeURIComponent(p.focus);
      return u;
    }

    function load() {
      if (status) status.textContent = 'Loading…';
      root.style('opacity', 0.45);   // hold the previous frame while refetching
      return fetch(url()).then(function (r) { return r.json(); }).then(function (data) { draw(data); });
    }

    function weightOf(l) { return state.params.metric === 'npmi' ? Math.max(0, l.npmi) : l.docs; }

    function draw(data) {
      root.style('opacity', 1);
      var prev = {}; nodes.forEach(function (n) { prev[n.id] = n; });
      nodes = data.nodes.map(function (n) { var o = prev[n.id]; return o ? Object.assign(o, n) : n; });
      links = data.links.map(function (l) { return Object.assign({}, l); });
      adj = {}; links.forEach(function (l) {
        (adj[l.source] = adj[l.source] || new Set()).add(l.target);
        (adj[l.target] = adj[l.target] || new Set()).add(l.source);
      });
      var W = container.clientWidth, H = container.clientHeight;
      svg.attr('viewBox', [0, 0, W, H]);
      var maxDc = d3.max(nodes, function (n) { return n.doc_count; }) || 1;
      var compact = !!state.params.compact;
      var rMax = compact ? 16 : 26;
      nodes.forEach(function (n) { n.r = 3.5 + (rMax - 3.5) * Math.sqrt(n.doc_count / maxDc); });
      var maxW = d3.max(links, weightOf) || 1;
      var focusId = data.focus;

      if (status) status.textContent = nodes.length + ' entities · ' + links.length + ' links' + (focusId ? ' · focused' : '');

      var link = gLinks.selectAll('line').data(links, function (l) { return l.source + '-' + l.target; })
        .join('line').attr('class', 'link').attr('stroke-width', function (l) { return 0.6 + 3.4 * weightOf(l) / maxW; });

      var node = gNodes.selectAll('g.node').data(nodes, function (n) { return n.id; })
        .join(function (enter) {
          var g = enter.append('g').attr('class', function (n) { return 'node ' + n.type; }).attr('tabindex', 0);
          g.append('circle').attr('class', 'hit').attr('fill', 'transparent');
          g.append('path');
          return g;
        });
      node.attr('class', function (n) { return 'node ' + n.type; });
      node.select('circle.hit').attr('r', function (n) { return Math.max(12, n.r + 4); });
      node.select('path')
        .attr('d', function (n) { return d3.symbol().type(SHAPES[n.type] || d3.symbolCircle).size(Math.PI * n.r * n.r * (HOLLOW[n.type] ? 0.8 : 1))(); });
      paint();

      // labels: biggest nodes + focus; others appear on hover/selection
      var labelSet = new Set(nodes.slice().sort(function (a, b) { return b.doc_count - a.doc_count; })
        .slice(0, compact ? 30 : Math.min(30, Math.round(nodes.length * 0.2))).map(function (n) { return n.id; }));
      if (focusId) labelSet.add(focusId);
      var label = gLabels.selectAll('text').data(nodes, function (n) { return n.id; }).join('text')
        .attr('class', function (n) { return 'label' + (n.id === focusId ? ' focus' : n.r < 8 ? ' small' : ''); })
        .attr('text-anchor', 'middle')
        .text(function (n) { return n.name.length > 28 ? n.name.slice(0, 26) + '…' : n.name; })
        .style('display', function (n) { return labelSet.has(n.id) ? null : 'none'; });

      node.on('pointerenter focus', function (evt, n) {
          highlight(n);
          var rows = [{ color: C.typeColor(n.type), value: n.doc_count.toLocaleString() + ' docs', label: n.name },
                      { label: C.TYPE_LABEL[n.type] + (n.n_corpora > 1 ? ' · ' + n.n_corpora + ' collections' : '') +
                               (adj[n.id] ? ' · ' + adj[n.id].size + ' links shown' : '') }];
          var e = evt.type === 'focus' ? { clientX: this.getBoundingClientRect().x, clientY: this.getBoundingClientRect().y } : evt;
          C.showTip(e, rows);
        })
        .on('pointermove', C.moveTip)
        .on('pointerleave blur', function () { C.hideTip(); highlight(selected); })
        .on('click', function (evt, n) {
          evt.stopPropagation();
          if (compact) { location.href = C.entityUrl(n.id); return; }
          selected = n; highlight(n); if (state.onSelect) state.onSelect(n, neighborsOf(n));
        })
        .on('dblclick', function (evt, n) { evt.stopPropagation(); if (!compact) setParams({ focus: n.id }); })
        .on('keydown', function (evt, n) { if (evt.key === 'Enter') { selected = n; highlight(n); if (state.onSelect) state.onSelect(n, neighborsOf(n)); } })
        .call(d3.drag()
          .on('start', function (e, n) { if (!e.active) sim.alphaTarget(0.25).restart(); n.fx = n.x; n.fy = n.y; })
          .on('drag', function (e, n) { n.fx = e.x; n.fy = e.y; })
          .on('end', function (e, n) { if (!e.active) sim.alphaTarget(0); n.fx = null; n.fy = null; }));
      svg.on('click', function () { selected = null; highlight(null); if (state.onSelect) state.onSelect(null); });

      if (sim) sim.stop();
      var fNode = focusId ? nodes.find(function (n) { return n.id === focusId; }) : null;
      if (fNode && fNode.x == null) { fNode.x = W / 2; fNode.y = H / 2; }
      sim = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(function (n) { return n.id; })
          .distance(function (l) { return 30 + l.source.r + l.target.r + 70 * (1 - weightOf(l) / maxW); })
          .strength(function (l) { return 0.15 + 0.6 * weightOf(l) / maxW; }))
        .force('charge', d3.forceManyBody().strength(function (n) { return -60 - n.r * 12; }).distanceMax(600))
        .force('collide', d3.forceCollide().radius(function (n) { return n.r + 3; }))
        .force('x', d3.forceX(W / 2).strength(0.04)).force('y', d3.forceY(H / 2).strength(0.05))
        .on('tick', function () {
          link.attr('x1', function (l) { return l.source.x; }).attr('y1', function (l) { return l.source.y; })
              .attr('x2', function (l) { return l.target.x; }).attr('y2', function (l) { return l.target.y; });
          node.attr('transform', function (n) { return 'translate(' + n.x + ',' + n.y + ')'; });
          label.attr('x', function (n) { return n.x; }).attr('y', function (n) { return n.y + n.r + 11; });
        });
      if (fNode) {
        fNode.fx = W / 2; fNode.fy = H / 2;
        if (!compact) setTimeout(function () { fNode.fx = null; fNode.fy = null; }, 1500);   // mini graphs keep the focus centred
      }
      fitted = false;
      setTimeout(fit, compact ? 900 : 1600);
      state.label = label; state.node = node; state.link = link; state.labelSet = labelSet;
      highlight(selected && nodes.find(function (n) { return n.id === selected.id; }) || null);
    }

    function paint() {
      gNodes.selectAll('g.node path').attr('fill', function (n) { return C.typeColor(n.type); })
        .attr('stroke', function (n) { return HOLLOW[n.type] ? C.typeColor(n.type) : null; });
    }

    function neighborsOf(n) {
      var out = [];
      links.forEach(function (l) {
        var s = l.source.id != null ? l.source : null, t = l.target.id != null ? l.target : null;
        if (!s || !t) return;
        if (s.id === n.id) out.push({ node: t, docs: l.docs, npmi: l.npmi });
        else if (t.id === n.id) out.push({ node: s, docs: l.docs, npmi: l.npmi });
      });
      return out.sort(function (a, b) { return state.params.metric === 'npmi' ? b.npmi - a.npmi : b.docs - a.docs; });
    }

    function highlight(n) {
      if (!state.node) return;
      if (!n) {
        state.node.classed('dim', false); state.link.classed('dim', false).classed('hl', false);
        state.label.style('display', function (d) { return state.labelSet.has(d.id) ? null : 'none'; });
        return;
      }
      var nb = adj[n.id] || new Set();
      state.node.classed('dim', function (d) { return d.id !== n.id && !nb.has(d.id); });
      state.link.classed('dim', function (l) { return l.source.id !== n.id && l.target.id !== n.id; })
        .classed('hl', function (l) { return l.source.id === n.id || l.target.id === n.id; });
      state.label.style('display', function (d) { return d.id === n.id || nb.has(d.id) || state.labelSet.has(d.id) ? null : 'none'; });
    }

    function fit() {
      if (fitted || !nodes.length) return;
      fitted = true;
      var W = container.clientWidth, H = container.clientHeight;
      var x0 = d3.min(nodes, function (n) { return n.x - n.r; }), x1 = d3.max(nodes, function (n) { return n.x + n.r; });
      var y0 = d3.min(nodes, function (n) { return n.y - n.r; }), y1 = d3.max(nodes, function (n) { return n.y + n.r + 14; });
      var s = Math.min(2, 0.92 / Math.max((x1 - x0) / W, (y1 - y0) / H));
      var t = d3.zoomIdentity.translate(W / 2, H / 2).scale(s).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
      svg.transition().duration(500).call(zoom.transform, t);
    }

    function setParams(p) {
      Object.assign(state.params, p);
      if (state.onParams) state.onParams(state.params);
      return load();
    }

    window.addEventListener('themechange', paint);
    var rt; window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { svg.attr('viewBox', [0, 0, container.clientWidth, container.clientHeight]); }, 150); });
    load();
    return { setParams: setParams, state: state, select: function (fn) { state.onSelect = fn; }, onParams: function (fn) { state.onParams = fn; } };
  }

  // ---- full page wiring
  function page(opts) {
    var container = document.getElementById('graph');
    var g = mount(container, { focus: opts.focus || null, maxDf: +document.getElementById('maxdf').value });
    var $ = function (id) { return document.getElementById(id); };

    // type toggles double as the legend (shape + color + name)
    var typesBox = $('types');
    C.TYPES.forEach(function (t) {
      var lab = C.el('label', 't-' + t);
      var cb = C.el('input'); cb.type = 'checkbox'; cb.checked = true; cb.value = t;
      lab.appendChild(cb); lab.appendChild(C.el('span', 'dot')); lab.appendChild(C.el('span', null, C.TYPE_LABEL[t]));
      typesBox.appendChild(lab);
      cb.addEventListener('change', function () {
        var ts = Array.prototype.filter.call(typesBox.querySelectorAll('input'), function (i) { return i.checked; }).map(function (i) { return i.value; });
        g.setParams({ types: ts });
      });
    });
    function bindRange(id, key) {
      var inp = $(id), out = $(id + '-v'), timer;
      inp.addEventListener('input', function () {
        out.textContent = inp.value; clearTimeout(timer);
        timer = setTimeout(function () { var p = {}; p[key] = +inp.value; g.setParams(p); }, 250);
      });
    }
    bindRange('limit', 'limit'); bindRange('mindocs', 'minDocs'); bindRange('k', 'k');
    $('metric').addEventListener('change', function () { g.setParams({ metric: this.value }); });
    if ($('source')) $('source').addEventListener('change', function () {
      var rel = this.value === 'relations';
      $('metric').disabled = rel;                 // relations have no NPMI
      if (rel) { $('mindocs').value = 1; $('mindocs-v').textContent = '1'; }
      g.setParams({ source: this.value, minDocs: +$('mindocs').value });
    });
    $('maxdf').addEventListener('change', function () { g.setParams({ maxDf: +this.value }); });
    $('hideauto').addEventListener('change', function () { g.setParams({ hideAuto: this.checked }); });
    $('clear-focus').addEventListener('click', function () { g.setParams({ focus: null }); });
    C.autocomplete($('focus-input'), $('ac'), function (it) { g.setParams({ focus: it.id }); });
    g.onParams(function (p) {
      $('clear-focus').style.display = p.focus ? '' : 'none';
      var u = new URL(location.href);
      if (p.focus) u.searchParams.set('focus', p.focus); else u.searchParams.delete('focus');
      history.replaceState(null, '', u);
    });
    if (opts.focus) $('clear-focus').style.display = '';

    var panel = $('panel');
    g.select(function (n, nbs) {
      panel.replaceChildren();
      var card = C.el('div', 'card'); panel.appendChild(card);
      if (!n) { card.appendChild(C.el('p', 'muted small', 'Click a node to see its details and strongest links.')); return; }
      var chip = C.el('span', 'chip t-' + n.type); chip.style.margin = '0';
      chip.appendChild(C.el('span', 'dot')); chip.appendChild(document.createTextNode(C.TYPE_LABEL[n.type]));
      card.appendChild(chip);
      if (n.auto) { var af = C.el('span', 'auto-flag', 'auto-detected'); af.style.marginLeft = '6px'; card.appendChild(af); }
      var h = C.el('h3', null, n.name); h.style.margin = '8px 0 4px'; card.appendChild(h);
      card.appendChild(C.el('div', 'small muted', n.doc_count.toLocaleString() + ' documents' +
        (n.n_corpora > 1 ? ' in ' + n.n_corpora + ' collections' : '')));
      if (n.description && !n.auto) { var p = C.el('p', 'small secondary', n.description); card.appendChild(p); }
      var actions = C.el('div'); actions.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;margin:10px 0';
      var a1 = C.el('a', 'btn', 'Entity page'); a1.href = C.entityUrl(n.id); actions.appendChild(a1);
      var a2 = C.el('a', 'btn', 'Focus here'); a2.href = '#'; a2.addEventListener('click', function (e) { e.preventDefault(); g.setParams({ focus: n.id }); });
      actions.appendChild(a2);
      var a3 = C.el('a', 'btn', 'Documents'); a3.href = C.docsUrl(n.id); actions.appendChild(a3);
      card.appendChild(actions);
      if (nbs && nbs.length) {
        card.appendChild(C.el('div', 'small muted', 'Strongest links in this view'));
        var t = C.el('table'); t.style.marginTop = '4px';
        var hr = C.el('tr'); hr.appendChild(C.el('th', null, 'Entity')); hr.appendChild(C.el('th', 'num', 'Docs')); hr.appendChild(C.el('th', 'num', 'NPMI')); t.appendChild(hr);
        nbs.slice(0, 25).forEach(function (x) {
          var tr = C.el('tr'); var td = C.el('td');
          var a = C.el('a', 'chip t-' + x.node.type); a.href = C.entityUrl(x.node.id); a.appendChild(C.el('span', 'dot')); a.appendChild(document.createTextNode(x.node.name));
          td.appendChild(a); tr.appendChild(td);
          var tdd = C.el('td', 'num'); var la = C.el('a', null, String(x.docs));
          la.href = C.docsUrl(n.id, x.node.id); la.title = 'Documents mentioning both';
          tdd.appendChild(la); tr.appendChild(tdd);
          tr.appendChild(C.el('td', 'num', x.npmi.toFixed(2)));
          t.appendChild(tr);
        });
        card.appendChild(t);
      }
    });
  }

  return { mount: mount, page: page };
})();
