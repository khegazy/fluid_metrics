# Decisions that look like gaps

This repository is missing several things on purpose. Each absence below was a decision,
made by the repository owner, and each is enforced by a test. This page exists so that you
do not "fix" one of them.

**How to use this page:** if something seems missing, look for it here before adding it.
If a test blocks your change and the test's message points here, the answer is here. If
you believe a decision is wrong, say so in your report and stop — do not work around the
test, and do not change the test to let your change through.

## There are no predictions

A card never states how a metric is expected to behave. There is no `expectations` field,
and the schema rejects one. Every claim about behaviour is either a measurement from a
named run or a citation to published work.

Why: an unsourced prediction is an opinion, and an opinion in structured YAML looks
exactly like a finding. This repository must contain only evidence.

If you want to record how a metric behaves: run the evaluation and generate the evidence.
Do not write what you think will happen.

## There is no pass or fail

No metric is marked good or bad. There is no `rejected` status, no score, and no ranking.
The `status` field means only "how far has the work progressed": `candidate` (evidence
incomplete or unreviewed), `validated` (measured and human-reviewed — says nothing about
whether the results were good), `control` (a baseline others are read against),
`deprecated` (superseded, kept for the record).

Why: a metric that fails one test usually catches something else. The useful record is
what each metric sees and what it misses, so a reader can match a metric to their
question. A pass/fail marker would erase exactly that information.

## There are no word counts

No section of any card has a minimum or maximum length. What each section must *say* is
described in the templates and the recipes; how long it takes to say it is the author's
judgement, checked by a human reviewer.

Why: a word count measures length, not clarity, and an author told to reach a number
reaches it by padding. Say what the section needs and stop.

## There are no metric IDs

A metric's name — the directory name, what users type in `metrics=[...]` — is its only
identity. You may find two-letter prefixes like `NM-0` or `OT-1` in old documents such as
`Table_of_Ideas.tex`. They are retired. Do not introduce IDs, and do not use those
prefixes in new work. A card's `category` field carries the classification instead.

## Cards do not repeat what the decorator declares

`differentiable`, `symmetric`, `units`, `cost`, `arity`, `higher_is_better` live on the
`@metric` decorator and nowhere else. The card holds only what the code cannot declare:
the category, the prose, and the mathematical properties (`triangle_inequality`,
`scale_dependent`, `resolution_dependent`, `complexity`).

Why: any fact stored in two places will eventually disagree. The catalog merges both
sources at build time, and it takes the machine-checkable ones from the code.

## Generated content lives inside card.md, between HTML markers

Measured tables and figures sit in `card.md` between `<!-- GENERATED name: ... -->` and
`<!-- END GENERATED name -->` markers, written by `python -m fmeval.cards evidence` or
`exemplars`. There are no include directives.

Why: cards are read in two places — GitHub's file view and the documentation site — and
GitHub does not resolve includes. A card must render fully in both.

Never write anything between the markers. Your prose goes below the closing marker.

## Equations use only `$...$` and `$$...$$` with `\tag{n}`

Never `\begin{equation}`, `\label`, `\eqref`, `\(`, or `\[`. The checker rejects them.

Why: those render on the site but appear as raw source on GitHub, silently — no error is
shown anywhere. The dollar forms are the only subset both readers share.

## Evidence comes only from registered datasets

`python -m fmeval.cards evidence` refuses a run on any dataset not listed in
`configs/cards/default.yaml`. In particular it refuses `kinet_re5e4_dev`, always.

Why: the dev dataset is the first 100 solver steps, before the flow develops. Its numbers
are physically meaningless, and once written into a card they would be indistinguishable
from meaningful ones. Use the dev dataset for smoke tests and refactor verification only.

## Agents never sign, and never set `validated`

`python -m fmeval.cards sign` records that a **human** read the prose and stands behind
it. Never run it, not even to test it — it writes the user's name. It also refuses to run
until the bundle has measurements, because most of a card's claims are measured ones and
an earlier signature would attest to nothing.

## Card validation happens at `get()`, not at import

A broken or missing card makes `registry.get(<name>)` fail with the fix command. It does
not make `import metrics` fail.

Why: one colleague's half-edited card must not break every other metric's runs. Do not
"strengthen" this into import-time validation; it was placed deliberately.

## A broken operator stops the run; an unsupported severity does not

If a degradation raises `NameError`, `AttributeError`, `ImportError` or `TypeError`, the
run stops and names the operator — that is a code defect. If it fails any other way, that
severity level is dropped with a warning and the run continues — that is a limit of the
configured grid.

Why: these were once treated the same, and a run once completed missing 630 rows with only
a misleading warning. Do not catch exceptions around operators to keep a run alive.

## Figures are committed, and only fingerprints must be byte-stable

Exemplar panels (PNGs) are committed so cards render on GitHub without a build step.
Regenerating with the same matplotlib version must produce byte-identical files; across
versions the PNGs may differ, and that is acceptable. The numbers in
`exemplars.json` and `fingerprint.json` are the stable record — never the pixels.

One canonical frame (`configs/cards/default.yaml`, `exemplar_frame`) is used for every
panel in the repository, so panels can be compared. Do not illustrate a degradation on a
different snapshot.

## The instructions live in docs/recipes/, not in AGENTS.md

`AGENTS.md` is a summary. The canonical instructions are the recipe files, each pinned by
its own test. Where they disagree, the recipe wins.

## Known accepted risks

- `metrics` is a generic top-level import name; the collision risk is accepted for now
  (`issues/020`).
- Numbers typed into card prose are not yet checked against the fingerprints beside them
  (`issues/032`). Until that check exists, reconciling them after a new run is a manual
  step in `docs/recipes/refresh-the-evidence.md`.
- Committed figures currently total about 6 MB. If the repository trends past roughly
  50 MB, the fallback is Git LFS — raise it, do not delete panels.
- The local checkout may be in a directory named `fluid_metrics`. The repository is
  `pde_metrics`; the directory name is historical and means nothing.
