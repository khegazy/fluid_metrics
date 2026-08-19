# Working with this repository

This is the orientation document: what each important file is for, who edits it, and where
you are expected to make changes. Read the summary table, then the section for whichever
file you are about to touch.

The short version: **you write the science and the argument for it; commands write
everything else.** If you find yourself hand-editing a number, a figure, or anything under
a `_generated/` directory, stop — there is a command for it, and hand-writing it defeats
the reason the file exists.

## Summary

### Inside a bundle

A **bundle** is one directory holding one metric or one degradation and everything that
documents it. Adding a metric means adding one directory; nothing elsewhere needs editing.

| File | What it is | Who edits it | When |
|---|---|---|---|
| `metric.py` / `degradation.py` | The implementation. The only file holding your science. | You | Always |
| `test_metric.py` / `test_degradation.py` | Tests specific to this metric, including the worked example the card quotes | You | Always |
| `card.yaml` | The typed record: category, status, bounds, references | You | Always |
| `card.md` | The prose: what it detects, how to read it, where it misleads | You | Always |
| `refs.bib` | BibTeX for the sources this card cites | You | When you cite something |
| `_generated/` | Measured evidence and figures | **A command. Never by hand** | Run the command |

### Around the repository

| File | What it is | Who edits it | When |
|---|---|---|---|
| `AGENTS.md` | The instruction file every coding agent reads | You | When you change how something is added |
| `CLAUDE.md` | The scientific context behind the mechanics | You | When the framing changes |
| `TEST_DESCRIPTION.md` | What every reported quantity means, and the protocol | You | When you add a reported column, degradation or figure |
| `configs/` | Hydra configuration: datasets, ladders, reports | You, carefully | To change what a run does |
| `evaluate.py`, `make_report.py` | The entry points | Rarely anyone | Run them; don't edit them to change one run |
| `fmeval/` | The harness: readers, ladder, analysis, reporting, cards | Whoever changes the harness | Not while adding a metric |
| `metrics/_template/`, `degradations/_template/` | What `new` copies | Whoever changes the contract | Never by hand for one bundle |
| `issues/` | One file per open item, with its evidence | You | When you find a defect you are not fixing now |

### The commands

```bash
python -m fmeval.cards new <name> [--kind degradation]   # scaffold a bundle
python -m fmeval.cards check <name> | --all              # validate; it names the fix
python -m fmeval.cards sign <name> --by <who>            # record that a human read the prose
python -m fmeval.cards list [--status ...]               # the index
python -m metrics ; python -m degradations               # what exists, as a table
python evaluate.py metrics=[mse] dataset=kinet_re5e4_dev # run an evaluation
python make_report.py results/<run> --compile            # render the report
pytest                                                   # the fast suite, about 30 seconds
```

---

## The bundle files in detail

### `metric.py` / `degradation.py` — your implementation

This is the one file in the bundle that holds science rather than bookkeeping. It exports
exactly one decorated function; the registry finds it by walking the package, so there is
no list to add yourself to.

The decorator arguments are declarations about the function, not requests: `differentiable`
says whether this *could* be a training loss, `symmetric` switches on a test that checks
symmetry actually holds, and `fields` restricts which physical fields the metric will ever
be handed. Getting one wrong does not fail loudly on its own — it makes the catalog lie —
so read the argument list in `metrics/registry.py` rather than copying another bundle.

A metric returns **one float** per call. It is handed one reference field and one candidate
field, already remapped onto the common analysis grid. Fields, frames and severity levels
are the evaluation loop's business, not yours.

If you need grid spacing, periodicity, the field name, or a random generator, declare a
keyword-only parameter named `ctx` and the harness will pass one. Its random generator is
derived from the seed, the frame and the field, so results do not depend on the order
things ran in.

Any equation taken from a paper carries a comment with the citation and the equation
number, and the entry goes in this bundle's `refs.bib`.

You may import from another bundle — `rmse` imports `mse` rather than repeating the sum,
which is better than two copies of one formula drifting apart.

### `test_metric.py` — the worked example, and what is specific to this metric

Write this **before** the card. At least one test must have an expected value you worked
out by hand: a test that asserts the code does what the code does will pass through any
mistake.

Keep the inputs small — four by four is ideal — because this same example goes into the
card's Intuition section, where a reader needs to be able to follow it by eye. That is the
real purpose of the size limit: the test and the card share one example, so the numbers in
the prose cannot drift away from the implementation.

Do not repeat the shared contract tests here. Zero on identical fields, symmetry, the
pointwise map reducing to the scalar, shape and dtype preservation — those run
automatically over the whole registry from `tests/test_metric_contract.py` and
`tests/test_degradation_contract.py`. Test the property that makes *this* metric the thing
it claims to be. For mean squared error that is the quadratic response to displacement and
the fact that it scores two equal errors identically wherever they sit.

### `card.yaml` — the typed record

Everything a machine can check, compare or filter on. The catalog, the site's filters and
the catalog reads this, so it is what an agent consults when deciding whether
your metric suits its problem.

Two things to know before you fill it in.

**It never restates what the decorator already says.** Differentiability, symmetry, arity,
cost, units, and a degradation's severity units and direction live on the decorator. They
are not in the card, because two copies of one fact drift apart and a reader cannot tell
which is stale. The catalog merges both sources when it is built.

**`status` is not a quality rating.** `candidate` means implemented but not yet measured
and reviewed. `validated` means the evaluation was run on the canonical data *and* a human
read and signed the card — it says the work was done, not that the results were good.
`control` marks a baseline that candidates are read against. There is no `rejected`, and
nothing in this repository passes or fails a metric: a metric that misses one thing usually
catches another, and that nuance lives in the evidence and the prose. Leave new bundles as
`candidate`; only a human moves a card to `validated`.

Notice what the card does **not** contain: anywhere to say how you think the metric will
behave. That is deliberate. Every statement about behaviour in this repository is either
measured — and then it belongs in the generated evidence, which you do not write — or it
comes from published work, and then it belongs in `## Definition` or `## Assessment` with
a citation. An unsourced prediction is an opinion, and an opinion written in structured
YAML reads like a finding. The schema refuses one.

Every field, and the reasoning behind it, is documented in `fmeval/cards/schema.py`. Read
that file. `python -m fmeval.cards check <name>` will tell you exactly what is wrong and
what to type to fix it.

### `card.md` — your argument, in prose

Seven sections for a metric and six for a degradation, in a fixed order, all
required. They
exist so that three different readers each get what they need: an early graduate student
from any STEM field, a domain expert, and a coding agent.

The order runs from what the metric *is* to what it *did here*:

```
Definition -> Performance -> Intuition -> Reading the output -> Limitations -> Results
```

Definition opens because the equation is the thing being documented and everything after
it is commentary on that equation. Performance follows immediately: one generated table
summarising how the metric behaved on every test, so a reader deciding whether to keep
reading — or comparing several cards — gets the measurements at a glance without opening
Results. You never write it, and it holds no prose at all; a number typed there is a claim
nothing checks, and the reading of those numbers belongs in Results beside the test that
produced each one. Intuition restates the definition in words, then Reading the output
and Limitations finish the account of the metric itself — how to interpret a value, and
where a value misleads. Only then does the card turn to this repository's
measurements. That break matters if you are adopting a metric elsewhere — the first four
sections hold for any dataset, and Results is findings about our run. Degradation cards
follow the same shape, with Severity scale in place of Reading the output and Exemplars
in place of Results.

`## Results` is built from one `### subsection per kind of test` — smoothing, spectral
filtering, displacement, resolution loss, noise, the canaries, and anything that holds
across the whole ladder. Each subsection opens with its generated include and continues
with what those particular numbers show:

```
### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

<!-- GENERATED results_geometric: written by `python -m fmeval.cards evidence mse`, do not edit -->

| axis | field | levels | rank correlation | monotone frames | weakest separation |
| `translate_x` | vorticity | 5 | 1 | 1 | 0.754 |

<!-- END GENERATED results_geometric -->

The response is quadratic in the displacement: the damage ratios per doubling ...
```

The block between the markers is written by the generator and rewritten every time you run
it. It lives in `card.md` rather than in a separate file pulled in at build time because
GitHub does not resolve includes: a figure or table that appears on the site and shows as a
literal include line in the repository fails the colleague who never leaves the repository.
The review ledger strips those blocks before hashing, so regenerating evidence never
invalidates a signature while editing your prose always does.

Say only what the metric did. What the run was — dataset, Reynolds number, resolution,
frame count — goes in the run summary at the top of Results, once, and is generated. What
a degradation does, and what its severity numbers mean, lives in its own bundle, which the
links reach. Repeating either in a subsection means writing it once per metric and then
keeping thirty copies true, so each subsection links to every degradation it reports.

Evidence and explanation used to be two separate sections, and a reader checking a
sentence against the number behind it had to scroll between them and work out which
figure the sentence meant. Keeping them together also discourages an assessment that
summarises the ladder in general instead of saying what each test found. You still never
write the numbers: run `python -m fmeval.cards evidence <name> --results results/<run>`
and never edit anything under `_generated/`. A subsection whose evidence has not been
generated yet warns rather than fails, because there is nothing there to explain.

There are no word counts anywhere in the contract. Say what a section needs to say and
stop; a short complete section beats a padded one, and a reader is the judge.

`## Definition` must contain a `### Boundary handling` subsection, and the checker
enforces it. `None.` is a fine answer — write it, with one clause saying why, rather than
leaving it out. A pointwise metric consults no neighbourhood and so has no boundary to
handle; anything with a stencil, a convolution or a transform does, and periodic wrap,
reflection and zero padding give different numbers from the same formula. Silence and
"none" look identical to a reader, and only one of them is a claim.

Keep the Definition to what the equation does not already say. That a sum runs over the
indices it is written with does not need a sentence.

The two sections people most often get wrong:

A card is signed only once its measurements exist: `python -m fmeval.cards sign <name>
--by <who>` refuses while the bundle has no run behind it. Most of a card's claims are
claims about how the metric behaved, and a signature says a person read them and stands
behind them — there is nothing to stand behind until there are results.

**`## Intuition`** explains the metric. Open with what it measures and which way of being
wrong it reveals, then say how it works. Write about the metric itself — not about its
standing in this project, which `card.yaml` records, and not about how it compares to
others, which belongs in Assessment where measurements support it. It is written for
someone who has never opened a fluid simulation — assume an early graduate student: skip the jargon, keep the rigor, and get
to the point without belabored analogies. No mathematical notation at all — the checker
rejects dollar signs and LaTeX delimiters. It
needs a physical picture, a worked example with real numbers from your test file, and one
sentence naming what the metric ignores. Every metric is blind to something; saying so here
rather than only in Limitations is what makes the section honest.

**`## Assessment`** replaces what other projects would call a verdict. Say what the
measurements show: what this metric sees that the controls do not, what it is blind to
including any canary it fails, and in what situations someone should reach for it. Every
claim here is either a number from the evidence or a citation — if you find yourself
writing what you expect rather than what was measured, that sentence does not belong. Failing a canary is information, not a mark against the metric — a
spectral-energy metric that a phase-randomised impostor fools is still the right tool for
asking about the energy cascade.

`## Performance` is generated in its entirety and holds no prose at all: a number typed
there is a claim nothing checks, and the reading of the numbers belongs in `## Results`
beside the test that produced it. In `## Results` you write the explanations and nothing
else — the tables between the markers are the generator's.

There are no word counts anywhere in the contract. Say what a section needs to say and
stop; a short complete section beats a padded one, and a reader is the judge rather than a
counter.

### `refs.bib` — your citations

One file per bundle, so bundles can be added and removed without touching anyone else's
references. Cite from the card as `[@key]`.

If you cannot verify that a reference exists, write `TODO(cite)` and say so when you
report. The checker rejects `TODO(cite)` deliberately: a guessed DOI, year or equation
number is worse than an admitted gap, because it looks exactly like a real one.

### `_generated/` — never edit this

Measured evidence and figures, written by `python -m fmeval.cards evidence <name>` and
`exemplars <name>`. Every file in here begins with a line saying it was generated.

The rule is absolute, and the reason is the whole point of the system: a number in
documentation must either have come from running real code or be absent. A plausible-looking
value typed in by hand is indistinguishable from a measured one to every reader, and there
is no way to catch it later. If the evidence is wrong, fix what produced it and regenerate.

If no run exists yet, this section says so in words. That is the correct state, not a gap
to fill in.

---

## Around the repository

### `configs/` — what a run does

Hydra configuration. Override from the command line for a one-off
(`python evaluate.py metrics=[mse] dataset.time.reduction=10`); edit the files when you are
changing what the default run means for everyone.

Two knobs change how much work a run does, and both are recorded with the results:
`dataset.time.reduction` evaluates every Nth frame, and `analysis_grid.resolution` sets the
grid everything is compared on. Runs made with different values are not comparable, which
is why they are recorded.

`configs/degradation/default.yaml` defines the severity ladder. Its keys are **labels**,
not operator names, which is what lets one operator appear twice with different options.
Those labels are what the evidence is reported against.

### `evaluate.py` and `make_report.py` — run them, don't edit them

`evaluate.py` runs the metrics over the ladder and writes one self-contained folder per
metric under `results/`, holding the raw numbers, the resolved config, provenance, and a
`main.tex` that compiles on its own. `make_report.py` re-renders a folder from the saved
numbers without recomputing anything.

To change what a run does, change the config or pass an override. Editing these scripts to
get one result is how a run becomes unreproducible.

### `TEST_DESCRIPTION.md` — what the reported quantities mean

The plain-language reference for every column, degradation and figure the suite reports,
plus the protocol behind them. A copy is placed in every run folder, so a folder found in
two years is still readable.

Edit it when you add a reported quantity — a test fails if a column, degradation or figure
is undocumented. It is not per-metric documentation; that is what cards are for.

### `AGENTS.md` — what your agent reads

The canonical instruction file for coding agents, whichever assistant it is: how to add a
metric, a degradation, a data source or a figure, the testing conventions, and a table of
traps that have already caught someone. Tests check that it documents every extension point
and every decorator argument, so it cannot quietly fall behind the code.

### `issues/` — open items

One file per item, with the measurement that established it, so future work is written
where a colleague will find it rather than living in someone's plan document. When a defect
is fixed its file is deleted; `git log --diff-filter=D -- issues/` recovers what was closed.

---

## Adding a metric, start to finish

```bash
python -m fmeval.cards new my_metric        # 1. scaffold; never create the files by hand
# 2. write metric.py
# 3. write test_metric.py, with an example you worked out by hand
pytest metrics/my_metric                     # 4. get it passing
# 5. fill in card.yaml
# 6. fill in card.md, quoting the example from step 3
python -m fmeval.cards check my_metric       # 7. it will tell you exactly what is missing
python evaluate.py metrics=[my_metric] dataset=kinet_re5e4_dev   # 8. does it run?
pytest                                       # 9. the whole suite
```

Then ask a person to read the card and run `python -m fmeval.cards sign my_metric --by
<them>`. Leave the status as `candidate`; promoting it is a human's decision, made after
looking at the evidence.

When you report what you did, say which `TODO(cite)` markers you left and why, and flag any
place where a word floor pushed you toward padding. Both are things someone needs to know
and neither is visible from the diff.


## The commands, in the order you will use them

```bash
python -m fmeval.cards new <name>                       # scaffold a bundle
python -m fmeval.cards new <name> --kind degradation
python evaluate.py metrics=[<name>] dataset=kinet_re5e4_dev degradation=quick   # smoke test
python -m fmeval.cards check <name>                     # what is missing, and the fix
python -m fmeval.cards exemplars <name>                 # a degradation's panel
python -m fmeval.cards evidence <name> --results results/<run>   # a metric's measurements
python -m fmeval.cards catalog                          # refresh docs/catalog.json
python -m fmeval.cards list                             # every bundle, with status
python -m fmeval.cards sign <name> --by <who>           # a human records having read it
```

`evidence` and `exemplars` need the real dataset, so they are run where the data lives and
their output is committed. Everything else works on any machine, which is why the site
builds in CI without a CFS mount.

## Where the numbers in a card come from

Two places, and the difference matters.

**Generated blocks** are written from one named evaluation run. The marker says which
command produced them, `_generated/fingerprint.json` records which run, and regenerating
rewrites them. They cannot silently describe a different experiment from the one the card
claims.

**Numbers you type into a sentence** are not maintained by anything. They are worth writing
— only a sentence can say that two metrics ordering damage alike while weighting it forty
times differently makes them duplicates for ranking and not for training — but they can go
stale when the canonical run is replaced, and this has already happened once. See
[issues/032](https://github.com/khegazy/pde_metrics/blob/main/issues/032-prose-numbers-can-go-stale.md) for the proposed check.
