# Things missing on purpose

This repository is missing several things deliberately. Each absence listed below was a
decision made by the repository owner, and each is enforced by an automated test. This
page exists so that nobody "fixes" one of them.

**How to use this page:** if something seems to be missing, look for it here before adding
it. If a test blocks your change and the test's message points here, the answer is here.
If you believe one of these decisions is wrong, say so in your report and stop — do not
work around the test, and do not change the test to let your change through.

## There are no predictions

A metric's page never states how the metric is expected to behave. There is no field for
recording an expectation, and the schema rejects one. Every claim about behaviour is
either a measurement from a named evaluation run or a citation to published work.

Why: an unsourced prediction is an opinion, and an opinion written into a structured file
looks exactly like a finding. This repository must contain only evidence.

If you want to record how a metric behaves, run the evaluation and generate the evidence.
Do not write down what you think will happen.

## There is no pass or fail

No metric is marked good or bad. There is no "rejected" state, no score, and no ranking.
The one status field records only how far the work has progressed:

- **candidate** — implemented, but the evidence is incomplete or nobody has reviewed it;
- **validated** — measured, and read and signed off by a person. This says the work was
  done, and says nothing at all about whether the results were good;
- **control** — a familiar baseline that candidate metrics are read against;
- **deprecated** — superseded, kept for the record.

Why: a metric that fails one test usually catches something another metric misses. The
useful record is what each metric sees and what each metric misses, so that a reader can
match a metric to their own question. A pass/fail marker would erase exactly that
information.

## There are no word counts

No section of any page has a minimum or a maximum length. What each section must *say* is
described in the templates and the recipes; how many words that takes is the author's
judgement, checked by a human reviewer.

Why: a word count measures length rather than clarity, and an author told to reach a
number will reach that number by padding. Say what the section needs to say, then stop.

## There are no metric IDs

A metric's name — which is its directory name, and exactly what users type in
`metrics=[...]` — is its only identity. You may find two-letter prefixes such as `NM-0` or
`OT-1` in old documents like `Table_of_Ideas.tex`. Those prefixes are retired. Do not
introduce IDs, and do not use those prefixes in new work. Each metric's `category` field
carries the classification instead.

## A page never repeats what the code already declares

Whether a metric is differentiable, whether it is symmetric, what units its value carries,
how expensive it is, how many fields it takes, and whether higher or lower is better all
live on the `@metric` decorator in the code and nowhere else. The page holds only what the
code cannot declare: the category, the prose, and the mathematical properties.

Why: any fact stored in two places will eventually disagree with itself. The catalog
merges both sources when the site is built, taking the machine-checkable facts from the
code.

## Generated content lives inside the page, between HTML markers

Measured tables and figures sit inside `card.md` between `<!-- GENERATED name: ... -->` and
`<!-- END GENERATED name -->` markers, written there by `python -m fmeval.cards evidence`
or `python -m fmeval.cards exemplars`. There is no mechanism for including a separate file.

Why: these pages are read in two places — GitHub's file view and this documentation site —
and GitHub does not resolve include directives. A page must render completely in both.

Never write anything between the markers. Your own prose goes below the closing marker.

## Equations use only `$...$` and `$$...$$` with `\tag{n}`

Never `\begin{equation}`, `\label`, `\eqref`, `\(`, or `\[`. The checker rejects all of
those.

Why: they render on this site but appear as raw source on GitHub, and they do so silently,
with no error shown anywhere. The dollar-sign forms are the only subset that both readers
handle.

## Evidence comes only from registered datasets

`python -m fmeval.cards evidence` refuses to run against any dataset not listed in
`configs/cards/default.yaml`. In particular it always refuses `kinet_re5e4_dev`.

Why: the development dataset holds only the first 100 solver steps, before the flow has
developed. Its numbers are physically meaningless, and once written into a page they would
be indistinguishable from meaningful ones. Use the development dataset for quick smoke
tests and for checking that a refactor changed nothing, and for nothing else.

## Agents never sign, and never set `validated`

`python -m fmeval.cards sign` records that a **person** read the prose and stands behind
it. Never run that command, not even to test it — it writes the user's name. The command
also refuses to run until the bundle has measurements, because most of a page's claims are
claims about measurements, and a signature recorded before them would attest to nothing.

## A page is validated at `get()`, not at import

A broken or missing page makes `registry.get(<name>)` fail, with the command that fixes
it. A broken page does not make `import metrics` fail.

Why: one colleague's half-edited page must not break every other metric's runs. Do not
"strengthen" this into validation at import time; it was placed here deliberately.

## A broken operator stops the run; an unsupported strength does not

If a degradation raises `NameError`, `AttributeError`, `ImportError` or `TypeError`, the
run stops and names the operator, because that is a defect in the code. If a degradation
fails in any other way, that one strength is dropped with a warning and the run continues,
because that is a limit of the configured range rather than a bug.

Why: these two cases were once treated the same way, and a run once completed with 630
rows silently missing and only a misleading warning to show for it. Do not wrap operators
in exception handlers to keep a run alive.

## Figures are committed, and only the numbers behind them must be byte-stable

The example panels (PNG files) are committed so that pages render on GitHub with no build
step. Regenerating a panel with the same matplotlib version must produce a byte-identical
file; across different matplotlib versions the PNGs may differ, and that is acceptable.
The numbers in `exemplars.json` and `fingerprint.json` are the stable record — never the
pixels.

One fixed snapshot (`configs/cards/default.yaml`, `exemplar_frame`) is used for every
panel in the repository, so that panels can be compared with one another. Do not
illustrate a degradation on a different snapshot.

## The instructions live in docs/recipes/, not in AGENTS.md

`AGENTS.md` is a summary. The canonical instructions are the recipe files, each one pinned
by its own test. Where the two disagree, the recipe wins.

## Known risks, accepted for now

- `metrics` is a generic name for a top-level Python package; the risk of colliding with
  another package is accepted for now (`issues/020`).
- Numbers typed into the prose of a page are not yet checked against the generated tables
  beside them (`issues/032`). Until that check exists, reconciling them after a new
  evaluation run is a manual step, described in
  `docs/recipes/refresh-the-evidence.md`.
- The committed figures currently total about 6 MB. If the repository grows past roughly
  50 MB, the fallback is Git LFS — raise the question, do not delete panels.
- Your local copy of the repository may sit in a directory named `fluid_metrics`. The
  repository is `pde_metrics`; the directory name is historical and means nothing.
