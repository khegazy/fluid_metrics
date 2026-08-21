# Recipes

Step-by-step instructions for extending this repository, written so that an agent — or a
colleague — can produce everything the existing directories already have: the
implementation, the tests, the written description, the figures and the measurements, to
the same standard, without having read the rest of the repository first.

| To add or change | Recipe |
|---|---|
| A metric | [add-a-metric.md](add-a-metric.md) |
| A way of damaging a field | [add-a-degradation.md](add-a-degradation.md) |
| A dataset | [add-a-dataset.md](add-a-dataset.md) |
| A new row on the example figures | [add-a-diagnostic.md](add-a-diagnostic.md) |
| The recorded measurements | [refresh-the-evidence.md](refresh-the-evidence.md) |
| Nothing — check that a refactor changed no numbers | [verify-a-refactor.md](verify-a-refactor.md) |

Before extending anything, also read [docs/decisions.md](../decisions.md), which lists the
things this repository is missing on purpose, so that you do not add one of them back.

These files, and not `AGENTS.md`, are the canonical instructions. `AGENTS.md` summarises
them and points here. They are deliberately kept as separate files, each one pinned by its
own test in `tests/test_documentation.py`, so that no single careless edit can destroy the
instructions: gutting any recipe fails the build with a message naming that recipe.

## Rules that apply to every recipe

Breaking one of these rules produces documentation that is plausible and wrong, which is
the exact failure this repository is designed to prevent. Each rule is repeated in the
recipes where it bites, and gathered here once.

1. **Never invent a number.** Every value in a description is generated from a named
   evaluation run, computed by a test, or absent. If there is no measurement, the
   description says so.
2. **Never invent a citation.** A reference you cannot verify stays as `TODO(cite)`, which
   fails validation on purpose and must be reported rather than resolved by guessing.
3. **Never state expected behaviour.** Claims about how a metric behaves are measurements
   or citations, never predictions. There is deliberately no mechanism for recording an
   expectation, and the schema refuses one.
4. **Never write inside a `<!-- GENERATED ... -->` block**, and never edit anything under
   `_generated/`. Run the command named in the marker instead.
5. **Never sign a card and never set `status: validated`.** Both are acts a person
   performs.
6. **Never edit another bundle while adding yours.** If a change elsewhere seems
   necessary, stop and say why.
7. **If a check seems wrong, report it rather than writing around it.** The checks encode
   deliberate decisions. A check that blocks correct work is a bug in the check, and
   working around it hides that bug.
8. **Report what you did**: what was added, every `TODO(cite)` you left behind, and
   anything flagged that you could not resolve.
