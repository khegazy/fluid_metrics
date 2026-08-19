# Site link rewriting is checked for dead links, not for correct destinations

**Category:** technical debt
**Priority:** medium
**Status:** open

## Context

Cards are written once and read in two places with different layouts. In the repository a
card is `metrics/<name>/card.md`, and a link between cards is
`../../degradations/<name>/card.md`. On the site the pages are flat — `metrics/<name>.md`
and `degradations/<name>.md` — and figures are served from a namespaced directory. So
`docs/gen_pages.py` rewrites three kinds of reference as it emits each page:

| Written in the card | Rewritten to | Pattern |
|---|---|---|
| `](../../degradations/translate/card.md)` | `](../degradations/translate.md)` | `_CARD_LINK` |
| `](_generated/exemplars.png)` | `](_generated/gaussian_blur_exemplars.png)` | `_ASSET` |
| `](metrics/mse/card.md)` in a root-level file | `](metrics/mse.md)` | `_ROOT_CARD_LINK` |

The only thing checking any of this is `mkdocs build --strict`, which fails on a link whose
target does not exist.

That catches a **dead** link. It does not catch a link that resolves to the **wrong**
page, and the rewriting is exactly the kind of code that produces those: three regexes,
each capturing a bundle name and interpolating it into a new path, with an asset rule that
prefixes a name onto a filename. A capture group referenced by the wrong index, a
namespacing prefix applied from the enclosing loop variable rather than the matched
bundle, or a pattern that matches one character too greedily all produce a path that
exists and points somewhere else.

The consequence is quiet and specific to this repository's purpose: a reader following
"what does this degradation do?" from a metric card would arrive at a different
degradation's page and have no reason to suspect it. Every panel image on the site being
the *same* panel is the same class of error, and it very nearly shipped — the asset
namespacing was added only because every bundle names its figure `exemplars.png` and the
first version wrote them all to one path, where the last one written won.

## What is needed

A test that renders the site's pages and checks, for each rewritten reference, that it
resolves to the destination the card *meant* — not merely to something that exists.

The tractable version does not need mkdocs. For every bundle:

1. Read `card.md`, extract every match of the three patterns before rewriting, and record
   the bundle name each match names.
2. Apply `_for_site` (and `_ROOT_CARD_LINK` for the protocol page).
3. Resolve each rewritten path against the site's known layout, and assert the resolved
   destination names the same bundle as the original did.

That last assertion is the point: it compares the *meaning* of the link before and after,
rather than the existence of a file. It would fail on a swapped capture group, on a
mis-namespaced asset, and on a pattern that eats a character of the name — none of which
`--strict` can see.

Worth covering at the same time, since they share the mechanism:

- **The asset rule prefixes the bundle name**, so a card that links to two figures, or a
  future bundle whose figure is not called `exemplars.png`, must still resolve correctly.
- **Round-tripping should be idempotent.** Applying the rewrite twice must not produce
  `../../metrics/metrics/...`; a rewritten link fed back through the pattern should not
  match again.
- **A card link the patterns do not match should be reported rather than passed through.**
  Today an unmatched form is emitted unchanged and `--strict` may or may not notice
  depending on whether the path happens to exist on the site. A card writing
  `](../../metrics/mse/card.md#definition)` — a fragment — is the likely real instance.

## Acceptance criteria

- A test fails when a rewritten link resolves to a different bundle than the card named,
  even though the target exists.
- A test fails when a figure reference resolves to another bundle's figure.
- Applying the rewriting twice is a no-op.
- A card reference in a form none of the patterns handle is reported by name rather than
  emitted unchanged.

## Related

- `docs/gen_pages.py` — `_CARD_LINK`, `_ASSET`, `_ROOT_CARD_LINK`, `_for_site`,
  `_write_protocol`.
- `tests/test_cards.py::test_the_site_builds_without_the_dataset` is the current coverage:
  it asserts the build succeeds under `--strict` and that a few expected pages exist.
- `tests/test_cards.py::test_every_degradation_a_card_links_to_exists` checks the
  repository side of the same links, which is why the GitHub-facing direction is in better
  shape than the site-facing one.
