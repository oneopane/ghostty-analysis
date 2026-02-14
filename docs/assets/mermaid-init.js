/* global mermaid */

(function () {
  'use strict';

  function _upgradeMermaidCodeBlocks() {
    // MkDocs renders fenced code blocks as <pre><code class="language-...">...
    // Mermaid expects <div class="mermaid">...</div>.
    const codes = document.querySelectorAll('pre > code.language-mermaid');
    for (const code of codes) {
      const pre = code.parentElement;
      if (!pre) continue;
      const container = document.createElement('div');
      container.className = 'mermaid';
      container.textContent = code.textContent || '';
      pre.replaceWith(container);
    }
  }

  function _renderMermaid() {
    if (typeof mermaid === 'undefined') return;
    _upgradeMermaidCodeBlocks();
    try {
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
      // Render all diagrams on the page (works with instant navigation too).
      const nodes = document.querySelectorAll('.mermaid');
      if (nodes.length > 0) {
        mermaid.run({ nodes });
      }
    } catch (_err) {
      // Best-effort: diagram rendering should not break the docs site.
    }
  }

  // MkDocs Material exposes document$ for instant navigation.
  if (window.document$ && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(() => _renderMermaid());
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _renderMermaid);
  } else {
    _renderMermaid();
  }
})();
