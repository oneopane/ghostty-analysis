/* global cytoscape */

(function () {
  'use strict';

  function el(tag, attrs, children) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === 'class') n.className = v;
        else if (k === 'text') n.textContent = v;
        else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
        else n.setAttribute(k, String(v));
      }
    }
    if (children) {
      for (const c of children) {
        if (c == null) continue;
        n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      }
    }
    return n;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function normalizeQuery(q) {
    return String(q || '').trim().toLowerCase();
  }

  function resolveRef(refs, key, fallback) {
    if (refs && refs[key]) return refs[key];
    return fallback || null;
  }

  function schemaTableRef(tableName) {
    const name = String(tableName || '').trim();
    if (!name) return null;
    if (name.startsWith('examples_index.')) {
      const suffix = name.split('.', 2)[1];
      return `codebase_map_pack/schemas/#table-examples_index-${suffix}`;
    }
    return `codebase_map_pack/schemas/#table-${name}`;
  }

  async function fetchJson(url) {
    const res = await fetch(url, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`fetch failed: ${url} (${res.status})`);
    return await res.json();
  }

  function mkUrl(base, rel) {
    const u = new URL(rel, base);
    return u.toString();
  }

  function buildShell(root) {
    const left = el('div', { class: 'cbm-left' });
    const main = el('div', { class: 'cbm-main' });
    const right = el('div', { class: 'cbm-right' });
    const shell = el('div', { class: 'cbm-shell' }, [left, main, right]);
    root.appendChild(shell);
    return { left, main, right };
  }

  function renderDetailPanel(right, payload, refs, siteBase) {
    right.innerHTML = '';
    if (!payload) {
      right.appendChild(el('div', { class: 'cbm-kv', text: 'Select a node, edge, or catalog row.' }));
      return;
    }

    const title = payload.title || payload.name || payload.id || 'Details';
    right.appendChild(el('div', { class: 'cbm-detail-title', text: String(title) }));

    const kv = el('div', { class: 'cbm-kv' });
    const keys = Object.keys(payload).filter(k => k !== 'title').sort();
    for (const k of keys) {
      const v = payload[k];
      const line = el('div', null, [
        el('span', { class: 'cbm-pill', text: k }),
        ' ',
        el('code', { text: typeof v === 'string' ? v : JSON.stringify(v) })
      ]);
      kv.appendChild(line);
    }
    right.appendChild(kv);

    const ref = payload.ref || resolveRef(refs, payload.name || payload.id, null);
    if (ref) {
      const href = mkUrl(siteBase, ref);
      right.appendChild(el('div', { class: 'cbm-detail-actions' }, [
        el('a', { href, target: '_self', rel: 'noopener', text: 'Open Docs' })
      ]));
    }
  }

  function makeCytoscapeStyles() {
    return [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'font-size': 10,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'ellipsis',
          'text-max-width': 110,
          'background-color': '#1f6feb',
          'color': '#0b0f17',
          'border-width': 1,
          'border-color': '#0b0f17',
          'width': 'label',
          'height': 'label',
          'padding': 8
        }
      },
      {
        selector: 'node[type = "package"]',
        style: {
          'background-color': '#2da44e'
        }
      },
      {
        selector: 'node[type = "module"]',
        style: {
          'background-color': '#8250df'
        }
      },
      {
        selector: 'node[type = "dataset"]',
        style: {
          'background-color': '#d29922'
        }
      },
      {
        selector: 'edge',
        style: {
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          'target-arrow-color': '#57606a',
          'line-color': '#8c959f',
          'width': 1,
          'label': 'data(label)',
          'font-size': 9,
          'text-rotation': 'autorotate',
          'color': '#57606a'
        }
      },
      {
        selector: '.cbm-hidden',
        style: {
          'display': 'none'
        }
      },
      {
        selector: '.cbm-highlight',
        style: {
          'border-width': 3,
          'border-color': '#fb8500',
          'z-index': 9999
        }
      }
    ];
  }

  function buildGraphElementsFromModuleGraph(doc, refs) {
    const nodes = (doc.nodes || []).map(n => ({
      data: {
        id: n.name,
        name: n.name,
        label: n.name,
        type: n.type || 'node',
        ref: resolveRef(refs, n.name, 'codebase_map_pack/architecture/')
      }
    }));
    const edges = (doc.edges || []).map((e, idx) => ({
      data: {
        id: `e${idx}:${e.from}->${e.to}`,
        source: e.from,
        target: e.to,
        label: e.type || 'edge',
        type: e.type || 'edge'
      }
    }));
    return { nodes, edges };
  }

  function buildGraphElementsFromLineage(doc, refs) {
    const ds = (doc.datasets || []).map(d => ({
      data: {
        id: d.name,
        name: d.name,
        label: d.name,
        type: 'dataset',
        dataset_type: d.type,
        grain: d.grain,
        source: d.source,
        known_by_time: d.known_by_time,
        ref: resolveRef(refs, d.name, 'codebase_map_pack/data_lineage/#dataset-catalog')
      }
    }));
    const edges = (doc.edges || []).map((e, idx) => ({
      data: {
        id: `l${idx}:${e.from}->${e.to}`,
        source: e.from,
        target: e.to,
        label: e.type || 'derived_from',
        type: e.type || 'derived_from'
      }
    }));
    return { nodes: ds, edges };
  }

  function buildGraphElementsFromPipelineDags(doc, refs, pipelineName) {
    const pipelines = doc.pipelines || [];
    const p = pipelines.find(x => x.name === pipelineName) || pipelines[0];
    if (!p) return { nodes: [], edges: [], pipeline: null };

    const nodeId = (n) => `pipeline:${p.name}:${n.name}`;
    const nodes = (p.nodes || []).map(n => ({
      data: {
        id: nodeId(n),
        name: n.name,
        label: n.name,
        type: 'pipeline_node',
        entrypoint: n.entrypoint,
        inputs: n.inputs || [],
        outputs: n.outputs || [],
        schedule: n.schedule || '',
        ref: resolveRef(refs, p.name, 'codebase_map_pack/pipelines/#pipelines')
      }
    }));
    const edges = (p.edges || []).map((e, idx) => ({
      data: {
        id: `p${idx}:${e.from}->${e.to}`,
        source: nodeId({ name: e.from }),
        target: nodeId({ name: e.to }),
        label: '',
        type: 'depends_on'
      }
    }));
    return { nodes, edges, pipeline: p };
  }

  function buildCatalogTable(items, columns, onSelect) {
    const table = el('table', { class: 'cbm-table' });
    const thead = el('thead');
    const trh = el('tr');
    for (const c of columns) trh.appendChild(el('th', { text: c.label }));
    thead.appendChild(trh);
    table.appendChild(thead);
    const tbody = el('tbody');
    for (const item of items) {
      const tr = el('tr', { onclick: () => onSelect(item) });
      for (const c of columns) {
        const v = item[c.key];
        tr.appendChild(el('td', { text: v == null ? '' : (typeof v === 'string' ? v : JSON.stringify(v)) }));
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    return table;
  }

  async function main() {
    const root = document.getElementById('cbm-explorer');
    if (!root) return;

    const artifactsBase = root.getAttribute('data-artifacts-base') || '_artifacts';
    // Use site root so relative URLs work from any page (e.g. /explorer/).
    const siteBase = window.location.origin + '/';

    if (typeof cytoscape !== 'function') {
      root.appendChild(el('div', { class: 'cbm-kv', text: 'Explorer failed to load: cytoscape not available.' }));
      return;
    }

    const { left, main, right } = buildShell(root);
    const cyEl = el('div', { class: 'cbm-cy' });
    main.appendChild(cyEl);

    const tabs = [
      { id: 'module', label: 'Module Graph' },
      { id: 'lineage', label: 'Data Lineage' },
      { id: 'pipelines', label: 'Pipeline DAGs' },
      { id: 'catalogs', label: 'Catalogs' },
      { id: 'temporal', label: 'Temporal Validity' }
    ];

    const tabBox = el('div', { class: 'cbm-tabs' });
    left.appendChild(tabBox);

    const controls = el('div', { class: 'cbm-controls' });
    left.appendChild(controls);

    const searchInput = el('input', { type: 'text', placeholder: 'Search nodes / catalogs...' });
    controls.appendChild(el('label', { text: 'Explorer Search' }));
    controls.appendChild(searchInput);

    const viewSelect = el('select');
    controls.appendChild(el('label', { text: 'View' }));
    controls.appendChild(viewSelect);

    const filterBox = el('div', { class: 'cbm-filter-list' });
    controls.appendChild(el('label', { text: 'Type Filter' }));
    controls.appendChild(filterBox);

    renderDetailPanel(right, null, null, siteBase);

    const refMap = await fetchJson(mkUrl(siteBase, `${artifactsBase}/ref_map.json`)).catch(() => ({ refs: {} }));
    const refs = (refMap && refMap.refs) ? refMap.refs : {};

    // Optional: load MkDocs search index so Explorer search can surface docs pages too.
    const docsSearchIndex = await fetchJson(mkUrl(siteBase, 'search/search_index.json')).catch(() => null);
    const docsDocs = docsSearchIndex && Array.isArray(docsSearchIndex.docs) ? docsSearchIndex.docs : [];
    let docsMatchesEl = null;

    const [moduleGraph, lineageGraph, pipelineDags, schemaCatalog, featureCatalog, labelRegistry, metricRegistry, contracts, temporalValidity] = await Promise.all([
      fetchJson(mkUrl(siteBase, `${artifactsBase}/module_graph.json`)),
      fetchJson(mkUrl(siteBase, `${artifactsBase}/data_lineage_graph.json`)),
      fetchJson(mkUrl(siteBase, `${artifactsBase}/pipeline_dags.json`)),
      fetchJson(mkUrl(siteBase, `${artifactsBase}/schema_catalog.json`)),
      fetchJson(mkUrl(siteBase, `${artifactsBase}/feature_catalog.json`)),
      fetchJson(mkUrl(siteBase, `${artifactsBase}/label_registry.json`)),
      fetchJson(mkUrl(siteBase, `${artifactsBase}/metric_registry.json`)),
      fetchJson(mkUrl(siteBase, `${artifactsBase}/contracts.json`)),
      fetchJson(mkUrl(siteBase, `${artifactsBase}/temporal_validity.json`))
    ]);

    const cy = cytoscape({
      container: cyEl,
      elements: [],
      style: makeCytoscapeStyles(),
      layout: { name: 'breadthfirst', directed: true, padding: 30, spacingFactor: 1.2 }
    });

    function clearHighlights() {
      cy.elements().removeClass('cbm-highlight');
    }

    function applyTypeFilter(activeTypes) {
      cy.nodes().forEach(n => {
        const t = n.data('type') || 'node';
        n.toggleClass('cbm-hidden', !activeTypes.has(t));
      });
      cy.edges().forEach(e => {
        const sHidden = e.source().hasClass('cbm-hidden');
        const tHidden = e.target().hasClass('cbm-hidden');
        e.toggleClass('cbm-hidden', sHidden || tHidden);
      });
    }

    function updateFilterBoxFromGraph() {
      filterBox.innerHTML = '';
      const types = new Set();
      cy.nodes().forEach(n => types.add(n.data('type') || 'node'));
      const sorted = Array.from(types).sort();
      const active = new Set(sorted);
      for (const t of sorted) {
        const id = `cbm-type-${t}`;
        const cb = el('input', { type: 'checkbox', id });
        cb.checked = true;
        cb.addEventListener('change', () => {
          const current = new Set();
          filterBox.querySelectorAll('input[type="checkbox"]').forEach(x => {
            if (x.checked) current.add(x.getAttribute('data-type'));
          });
          applyTypeFilter(current);
        });
        cb.setAttribute('data-type', t);
        filterBox.appendChild(el('div', { class: 'cbm-filter-item' }, [cb, el('label', { for: id, text: t })]));
      }
    }

    function setGraph(elements, layoutName) {
      cy.elements().remove();
      cy.add(elements.nodes);
      cy.add(elements.edges);
      cy.layout({ name: layoutName || 'breadthfirst', directed: true, padding: 30, spacingFactor: 1.2 }).run();
      updateFilterBoxFromGraph();
    }

    function setCatalogView(kind) {
      cy.elements().remove();
      filterBox.innerHTML = '';

      const q = normalizeQuery(searchInput.value);
      let items = [];
      let columns = [];

      if (kind === 'schemas') {
        items = (schemaCatalog.tables || []);
        columns = [
          { key: 'name', label: 'name' },
          { key: 'grain', label: 'grain' },
          { key: 'primary_key', label: 'primary_key' }
        ];
      } else if (kind === 'features') {
        items = (featureCatalog.features || []);
        columns = [
          { key: 'name', label: 'name' },
          { key: 'entity', label: 'entity' },
          { key: 'window', label: 'window' },
          { key: 'known_by_time', label: 'known_by_time' }
        ];
      } else if (kind === 'labels') {
        items = (labelRegistry.labels || []);
        columns = [
          { key: 'name', label: 'name' },
          { key: 'grain', label: 'grain' },
          { key: 'computed_in', label: 'computed_in' }
        ];
      } else if (kind === 'metrics') {
        items = (metricRegistry.metrics || []);
        columns = [
          { key: 'name', label: 'name' },
          { key: 'type', label: 'type' },
          { key: 'implemented_in', label: 'implemented_in' }
        ];
      } else if (kind === 'contracts') {
        items = (contracts.boundaries || []);
        columns = [
          { key: 'from_package', label: 'from' },
          { key: 'to_package', label: 'to' },
          { key: 'api_surface', label: 'api' }
        ];
      } else if (kind === 'temporal') {
        items = (temporalValidity.entities || []);
        columns = [
          { key: 'name', label: 'name' },
          { key: 'available_at', label: 'available_at' },
          { key: 'risk_of_leakage', label: 'risk_of_leakage' }
        ];
      }

      if (q) {
        items = items.filter(it => JSON.stringify(it).toLowerCase().includes(q));
      }

      renderDetailPanel(right, { title: `Catalog: ${kind}`, count: items.length }, refs, siteBase);
      const table = buildCatalogTable(items.slice(0, 500), columns, (item) => {
        const name = item.name || item.from_package || '';
        let ref = resolveRef(refs, String(name), null);
        if (!ref) {
          if (kind === 'schemas') ref = schemaTableRef(item.name);
          else if (kind === 'features') ref = 'codebase_map_pack/features/#feature-families';
          else if (kind === 'labels' || kind === 'metrics') ref = 'codebase_map_pack/labels_metrics/';
          else if (kind === 'contracts') ref = 'codebase_map_pack/contracts/';
          else if (kind === 'temporal') ref = 'codebase_map_pack/temporal_validity/';
        }
        const payload = Object.assign({}, item, {
          title: item.name || `${item.from_package || ''} -> ${item.to_package || ''}`,
          ref
        });
        renderDetailPanel(right, payload, refs, siteBase);
      });
      right.appendChild(el('hr'));
      right.appendChild(table);
    }

    function setActiveTab(id) {
      tabBox.querySelectorAll('button').forEach(b => {
        b.setAttribute('aria-selected', b.getAttribute('data-tab') === id ? 'true' : 'false');
      });
    }

    function populateViewSelect(options) {
      viewSelect.innerHTML = '';
      for (const opt of options) {
        viewSelect.appendChild(el('option', { value: opt.value, text: opt.label }));
      }
    }

    function switchTo(tabId) {
      setActiveTab(tabId);
      searchInput.value = '';
      renderDetailPanel(right, null, refs, siteBase);

      if (tabId === 'module') {
        populateViewSelect([
          { value: 'module_graph', label: 'module_graph.json' }
        ]);
        setGraph(buildGraphElementsFromModuleGraph(moduleGraph, refs), 'cose');
      } else if (tabId === 'lineage') {
        populateViewSelect([
          { value: 'data_lineage', label: 'data_lineage_graph.json' }
        ]);
        setGraph(buildGraphElementsFromLineage(lineageGraph, refs), 'breadthfirst');
      } else if (tabId === 'pipelines') {
        const names = (pipelineDags.pipelines || []).map(p => p.name);
        populateViewSelect(names.map(n => ({ value: n, label: n })));
        const sel = viewSelect.value;
        const built = buildGraphElementsFromPipelineDags(pipelineDags, refs, sel);
        setGraph({ nodes: built.nodes, edges: built.edges }, 'breadthfirst');
        if (built.pipeline) {
          renderDetailPanel(right, { title: `Pipeline: ${built.pipeline.name}` }, refs, siteBase);
        }
      } else if (tabId === 'catalogs') {
        populateViewSelect([
          { value: 'schemas', label: 'Schemas' },
          { value: 'features', label: 'Features' },
          { value: 'labels', label: 'Labels' },
          { value: 'metrics', label: 'Metrics' },
          { value: 'contracts', label: 'Contracts' }
        ]);
        setCatalogView(viewSelect.value);
      } else if (tabId === 'temporal') {
        populateViewSelect([
          { value: 'temporal', label: 'Temporal Validity' }
        ]);
        setCatalogView('temporal');
      }
    }

    for (const t of tabs) {
      tabBox.appendChild(
        el('button', {
          class: 'cbm-tab',
          type: 'button',
          'data-tab': t.id,
          'aria-selected': 'false',
          onclick: () => switchTo(t.id),
          text: t.label
        })
      );
    }

    viewSelect.addEventListener('change', () => {
      const active = tabBox.querySelector('button[aria-selected="true"]');
      const tabId = active ? active.getAttribute('data-tab') : 'module';
      if (tabId === 'pipelines') {
        const built = buildGraphElementsFromPipelineDags(pipelineDags, refs, viewSelect.value);
        setGraph({ nodes: built.nodes, edges: built.edges }, 'breadthfirst');
        if (built.pipeline) {
          renderDetailPanel(right, { title: `Pipeline: ${built.pipeline.name}` }, refs, siteBase);
        }
      } else if (tabId === 'catalogs') {
        setCatalogView(viewSelect.value);
      }
    });

    searchInput.addEventListener('input', () => {
      const q = normalizeQuery(searchInput.value);
      const active = tabBox.querySelector('button[aria-selected="true"]');
      const tabId = active ? active.getAttribute('data-tab') : 'module';

      if (tabId === 'catalogs') {
        setCatalogView(viewSelect.value);
        return;
      }
      if (tabId === 'temporal') {
        setCatalogView('temporal');
        return;
      }

      clearHighlights();
      if (!q) return;
      const matches = cy.nodes().filter(n => String(n.data('name') || '').toLowerCase().includes(q));
      matches.addClass('cbm-highlight');
      if (matches.length > 0) {
        cy.fit(matches, 60);
      }

      // Show docs matches in the detail panel (best-effort substring scan).
      if (docsDocs.length > 0) {
        if (docsMatchesEl && docsMatchesEl.parentNode) {
          docsMatchesEl.parentNode.removeChild(docsMatchesEl);
        }
        const hits = [];
        for (const d of docsDocs) {
          const hay = `${d.title || ''}\n${d.text || ''}`.toLowerCase();
          if (hay.includes(q)) hits.push(d);
          if (hits.length >= 8) break;
        }
        if (hits.length > 0) {
          const box = el('div', { class: 'cbm-docs-matches' });
          box.appendChild(el('div', { class: 'cbm-detail-title', text: 'Docs Matches' }));
          for (const h of hits) {
            const href = mkUrl(siteBase, String(h.location || '')).replace(/index\.html$/, '');
            box.appendChild(el('div', { class: 'cbm-kv' }, [
              el('a', { href, text: String(h.title || h.location || 'doc') })
            ]));
          }
          docsMatchesEl = box;
          right.appendChild(el('hr'));
          right.appendChild(docsMatchesEl);
        }
      }
    });

    cy.on('tap', 'node', (evt) => {
      const n = evt.target;
      renderDetailPanel(right, n.data(), refs, siteBase);
    });

    cy.on('tap', 'edge', (evt) => {
      const e = evt.target;
      renderDetailPanel(right, Object.assign({ title: 'Edge' }, e.data()), refs, siteBase);
    });

    // Initial view
    switchTo('module');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => main().catch(err => {
      const root = document.getElementById('cbm-explorer');
      if (root) root.innerHTML = `<pre>${escapeHtml(String(err && err.stack ? err.stack : err))}</pre>`;
    }));
  } else {
    main().catch(() => {});
  }
})();
