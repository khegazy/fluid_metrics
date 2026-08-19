# Recipes

Step-by-step instructions for extending this repository, written so that an agent — or a
colleague — can produce everything the existing bundles have: the implementation, the
tests, the card, the figures and the measurements, to the same standard, without having
read the rest of the repository first.

| To add or change | Recipe |
|---|---|
| A metric | [add-a-metric.md](add-a-metric.md) |
| A degradation | [add-a-degradation.md](add-a-degradation.md) |
| A dataset | [add-a-dataset.md](add-a-dataset.md) |
| A diagnostic (a new panel row) | [add-a-diagnostic.md](add-a-diagnostic.md) |
| The recorded evidence | [refresh-the-evidence.md](refresh-the-evidence.md) |
| Nothing — verify a refactor changed no numbers | [verify-a-refactor.md](verify-a-refactor.md) |

Before extending anything, also read [docs/decisions.md](../decisions.md): the list of
things this repository is missing on purpose, so you do not add one of them back.

These files, not `AGENTS.md`, are the canonical instructions. `AGENTS.md` summarises and
points here. They are deliberately separate files, each pinned by its own test in
`tests/test_documentation.py`, so that no single careless edit can destroy the
instructions: gutting any recipe fails CI naming that recipe.

## Rules that apply to every recipe

These are the rules whose violation produces plausible, wrong documentation — the failure
this repository is designed to prevent. They are repeated in each recipe where they bite,
and gathered here once.

1. **Never invent a number.** Every value in a card is generated from a named run, computed
   by a test, or absent. If there is no measurement, the card says so.
2. **Never invent a citation.** An unverifiable reference stays `TODO(cite)`, which fails
   validation on purpose and must be reported rather than resolved by guessing.
3. **Never state expected behaviour.** Claims about how a metric behaves are measurements
   or citations. There is no expectations mechanism, deliberately, and the schema refuses
   one.
4. **Never write inside a `<!-- GENERATED ... -->` block** and never edit `_generated/`.
   Run the generator named in the marker.
5. **Never sign a card and never set `status: validated`.** Both are human acts.
6. **Never edit another bundle while adding yours.** If a change elsewhere seems necessary,
   stop and say why.
7. **If a check seems wrong, report it rather than writing around it.** The checks encode
   decisions; a check that blocks correct work is a bug in the check, and gaming it hides
   the bug.
8. **Report what you did**: what was added, every `TODO(cite)` left, and anything flagged
   that you could not resolve.
