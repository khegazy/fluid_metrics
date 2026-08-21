// MathJax configuration for the site.
//
// The delimiters below must match what `pymdownx.arithmatex` *emits*, not what an author
// types. In `generic: true` mode arithmatex has already parsed the dollar-delimited source
// and rewritten every equation into `\(...\)` inline and `\[...\]` display, wrapped in an
// element of class `arithmatex`. Declaring `$...$` and `$$...$$` here instead replaces
// MathJax's delimiter list and drops the backslash forms, so MathJax scans those elements,
// matches nothing, and leaves the raw LaTeX on the page.
//
// That failure is silent in every way that matters: the build succeeds, `--strict` is
// happy, no console error appears, and the page shows the source of each equation as
// though it were meant to be read. Authors still write `$...$` and `$$...$$` in card.md;
// `fmeval/cards/prose.py` enforces that subset, and docs/decisions.md says why.
//
// `tags: 'ams'` numbers display equations, so a card's \tag{1} renders as (1) and the
// prose can refer to "Equation (1)". Cross-page references are not supported; cards refer
// to equations by number within their own page and by name across pages.
window.MathJax = {
  tex: {
    tags: "ams",
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
  },
};

// `navigation.instant` swaps the page body without a reload, so MathJax has to be told to
// typeset the new content. MathJax typesets the *first* page itself as part of startup;
// this handler exists for every page after that.
//
// The guard is not defensive clutter. This file loads before tex-mml-chtml.js, so on the
// first emission `MathJax` is still the plain configuration object above and has no
// `startup` -- calling through it would throw and kill the subscription for the rest of
// the session, breaking maths on every subsequent page.
document$.subscribe(() => {
  if (!window.MathJax || !window.MathJax.startup || !window.MathJax.startup.promise) {
    return;
  }
  MathJax.startup.promise.then(() => {
    MathJax.startup.output.clearCache();
    MathJax.typesetClear();
    MathJax.texReset();
    return MathJax.typesetPromise();
  });
});
