// MathJax configuration for the site.
//
// `tags: 'ams'` numbers display equations, so a card's \tag{1} renders as (1) and the
// prose can refer to "Equation (1)". Cross-page references are not supported; cards refer
// to equations by number within their own page and by name across pages.
window.MathJax = {
  tex: {
    tags: "ams",
    inlineMath: [["$", "$"]],
    displayMath: [["$$", "$$"]],
    processEscapes: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
  },
};

document$.subscribe(() => {
  MathJax.startup.output.clearCache();
  MathJax.typesetClear();
  MathJax.texReset();
  MathJax.typesetPromise();
});
