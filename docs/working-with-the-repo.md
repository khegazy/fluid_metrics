# Working with this repository

This is the orientation document: what each important file is for, who edits it, and where
you are expected to make changes. Read the summary table, then read the section for
whichever file you are about to touch.

The short version: **you write the science and the argument for it; commands write
everything else.** If you find yourself hand-editing a number, a figure, or anything under
a `_generated/` directory, stop — there is a command that produces it, and writing it by
hand defeats the reason the file exists.

## Summary

### Inside a bundle

A **bundle** is one directory holding one metric, or one way of damaging a field, together
with everything that documents it. Adding a metric means adding one directory; nothing
elsewhere needs editing.

| File | What it is | Who edits it | When |
|---|---|---|---|
| `metric.py` / `degradation.py` | The implementation. The only file in the bundle that holds your science. | You | Always |
| `test_metric.py` / `test_degradation.py` | Tests specific to this one metric, including the worked example that the description quotes | You | Always |
| `card.yaml` | The machine-readable record: category, status, bounds, references | You | Always |
| `card.md` | The written description: what the metric detects, how to read its output, where it misleads | You | Always |
| `refs.bib` | BibTeX entries for the sources this description cites | You | When you cite something |
| `_generated/` | Measured results and figures | **A command. Never by hand** | Run the command |

### Around the repository

| File | What it is | Who edits it | When |
|---|---|---|---|
| `AGENTS.md` | The instruction file every coding agent reads | You | When you change how something is added |
| `CLAUDE.md` | The scientific context behind the mechanics | You | When the framing changes |
| `TEST_DESCRIPTION.md` | What every reported quantity means, and the protocol behind it | You | When you add a reported column, degradation or figure |
| `configs/` | Hydra configuration: datasets, degradations, reports | You, carefully | To change what an evaluation run does |
| `evaluate.py`, `make_report.py` | The entry points | Rarely anyone | Run them; don't edit them to change one run |
| `fmeval/` | The shared machinery: data readers, the degradation sequence, analysis, reporting, pages | Whoever changes that machinery | Not while adding a metric |
| `metrics/_template/`, `degradations/_template/` | What the `new` command copies | Whoever changes the contract | Never by hand for one bundle |
| `issues/` | One file per open item, with the evidence for it | You | When you find a defect you are not fixing now |

### The commands

```bash
python -m fmeval.cards new <name> [--kind degradation]   # create an empty bundle
python -m fmeval.cards check <name> | --all              # validate, and name the fix
python -m fmeval.cards sign <name> --by <who>            # record that a person read the prose
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
exactly one decorated function; the registry finds that function by walking the package,
so there is no list to add yourself to.

The decorator's arguments are declarations about your function, not requests:
`differentiable` says whether this function *could* be used as a training loss,
`symmetric` switches on a test that checks the symmetry you claimed actually holds, and
`fields` restricts which physical quantities the metric will ever be handed. Getting one
of these wrong does not fail loudly on its own — it makes the published catalog lie — so
read the argument list in `metrics/registry.py` rather than copying another bundle.

A metric returns **one float** per call. The metric is handed one reference field and one
candidate field, both already placed on the common analysis grid. Which fields, which
snapshots in time, and which strengths of damage to run are the evaluation loop's business
and not yours.

If you need the grid spacing, whether the domain wraps around, the field's name, or a
random number generator, declare a keyword-only parameter named `ctx` and the machinery
will pass one in. Its random number generator is derived from the run's seed, the snapshot
and the field, so results never depend on the order in which things ran.

Any equation taken from a paper carries a comment naming the citation and the equation
number, and the citation itself goes in this bundle's `refs.bib`.

You may import from another bundle. `rmse` imports `mse` rather than repeating the sum,
which is better than having two copies of one formula that can drift apart.

### `test_metric.py` — the worked example, and what is specific to this metric

Write this file **before** the description. At least one test must have an expected value
that you worked out by hand: a test asserting that the code does what the code does will
pass any mistake straight through.

Keep the inputs small — four cells by four cells is ideal — because this same example goes
into the description's Intuition section, where a reader needs to be able to follow it by
eye. That is the real purpose of the size limit: the test and the description share one
example, so the numbers in the prose cannot drift away from the implementation.

Do not repeat the shared contract tests here. Returning zero on identical fields,
symmetry, the per-cell map averaging back to the single value, and preservation of array
shape and type all run automatically over the whole registry, from
`tests/test_metric_contract.py` and `tests/test_degradation_contract.py`. Test instead the
property that makes *this* metric the thing it claims to be. For mean squared error that
is the quadratic response to displacement, and the fact that it scores two equal errors
identically wherever in the domain they sit.

### `card.yaml` — the machine-readable record

Everything a program can check, compare or filter on. The catalog and this site's filters
both read this file, so it is what a program consults when deciding whether your metric
suits its problem.

Two things to know before you fill it in.

**This file never restates what the decorator already says.** Differentiability, symmetry,
how many fields the metric takes, cost, units, and a degradation's severity units and
direction all live on the decorator. None of them appear in `card.yaml`, because two copies
of one fact drift apart and a reader cannot tell which copy is stale. The catalog merges
both sources when the catalog is built.

**`status` is not a quality rating.** `candidate` means implemented but not yet measured
and reviewed. `validated` means the evaluation was run on the reference data *and* a person
read and signed the description — so `validated` says the work was done, not that the
results were good. `control` marks a familiar baseline that candidates are read against.
There is no `rejected`, and nothing in this repository passes or fails a metric: a metric
that misses one thing usually catches another, and that nuance lives in the measurements
and the prose. Leave new bundles as `candidate`; only a person moves a bundle to
`validated`.

Notice what `card.yaml` does **not** contain: anywhere to say how you think the metric
will behave. That absence is deliberate. Every statement about behaviour in this
repository is either measured — and then it belongs in the generated results, which you do
not write — or it comes from published work, and then it belongs in `## Definition` or `##
Results` with a citation. An unsourced prediction is an opinion, and an opinion written in
a structured file reads like a finding. The schema refuses one.

Every field, and the reasoning behind it, is documented in `fmeval/cards/schema.py`. Read
that file. `python -m fmeval.cards check <name>` will tell you exactly what is wrong and
what to type to fix it.

### `card.md` — your argument, in prose

Seven sections for a metric and six for a degradation, in a fixed order, all required.
They exist so that three different readers each get what they need: an early graduate
student from any STEM field, an expert in fluids, and a coding agent.

The order runs from what the metric *is* to what the metric *did on our data*:

```
Definition -> Performance -> Intuition -> Reading the output -> Limitations -> Results
```

Definition opens because the equation is the thing being documented and everything after
it is commentary on that equation. Performance follows immediately: one generated table
summarising how the metric behaved on every test, so that a reader deciding whether to
keep reading — or comparing several metrics — gets the measurements at a glance without
opening Results. You never write Performance, and it holds no prose at all; a number typed
there is a claim that nothing checks, and the reading of those numbers belongs in Results
beside the test that produced each one. Intuition then restates the definition in words,
and Reading the output and Limitations finish the account of the metric itself — how to
interpret a value, and where a value misleads. Only then does the page turn to this
repository's own measurements.

That break matters if you are adopting a metric elsewhere: the first four sections hold
for any dataset, and Results reports findings from our run alone. A degradation's page
follows the same shape, with Severity scale in place of Reading the output, and What the
degradation looks like in place of Results.

`## Results` is built from one `###` subsection per kind of test — smoothing, spectral
filtering, displacement, resolution loss, noise, the trap tests, and anything that holds
across every degradation at once. Each subsection opens with its generated block and
continues with what those particular numbers show:

```
### Displacement

[translate_x](../../degradations/translate/card.md) ·
[translate_subpixel](../../degradations/translate_subpixel/card.md)

H0

The response is quadratic in the displacement: the damage ratios per doubling ...
```

The block between the markers is written by the generator and rewritten every time you run
it. That block sits inside `card.md` rather than in a separate file pulled in at build
time because GitHub does not resolve include directives: a figure or table that appears on
this site while showing as a literal include line in the repository fails the colleague
who never leaves the repository. The review ledger strips those blocks before hashing, so
regenerating measurements never invalidates a signature, while editing your own prose
always does.

Say only what the metric did. What the evaluation run was — dataset, Reynolds number,
resolution, number of snapshots — goes in the run summary at the top of Results, once, and
is generated. What a degradation does, and what its strength numbers mean, lives in that
degradation's own bundle, which the links reach. Repeating either one in a subsection
means writing it once per metric and then keeping thirty copies true, so each subsection
links to every degradation it reports instead.

The measurements and the explanation of them used to be two separate sections, and a
reader checking a sentence against the number behind it had to scroll between the two and
work out which table the sentence meant. Keeping them together also discourages a summary
that talks about the degradations in general instead of saying what each test found. You
still never write the numbers: run `python -m fmeval.cards evidence <name> --results
results/<run>` and never edit anything under `_generated/`. A subsection whose
measurements have not been generated yet produces a warning rather than a failure, because
there is nothing there to explain.

There are no word counts anywhere in the contract. Say what a section needs to say and
stop; a short complete section beats a padded one, and the reader is the judge.

`## Definition` must contain a `### Boundary handling` subsection, and the checker
enforces that. `None.` is a fine answer — write it, with one clause saying why, rather
than leaving it out. A metric that looks at one cell at a time consults no neighbours and
so has no edge to handle; anything with a stencil, a convolution or a Fourier transform
does, and wrapping around, mirroring and padding with zeros give different numbers from
the same formula. Silence and "none" look identical to a reader, and only one of them is a
claim.

Keep the Definition to what the equation does not already say. That a sum runs over the
indices it is written with does not need a sentence.

Two sections need particular care.

**`## Intuition`** explains the metric. Open with what the metric measures and which way of
being wrong the metric reveals, then say how the metric works. Write about the metric
itself — not about its standing in this project, which `card.yaml` records, and not about
how it compares to other metrics, which belongs in Results where measurements support the
comparison. Intuition is written for someone who has never opened a fluid simulation, so
assume an early graduate student: skip the jargon, keep the rigour, and get to the point
without laboured analogies. No mathematical notation at all — the checker rejects dollar
signs and LaTeX delimiters. The section needs a physical picture, a worked example with
real numbers taken from your test file, and one sentence naming what the metric ignores.
Every metric is blind to something, and saying so here rather than only in Limitations is
what makes the section honest.

**`## Results`** is where other projects would put a verdict. Say what the measurements
show: what this metric sees that the baselines do not, what this metric is blind to
including any trap test it falls for, and in what situations someone should reach for it.
Every claim here is either a number from the generated tables or a citation — if you find
yourself writing what you expect rather than what was measured, that sentence does not
belong. Falling for a trap test is information, not a mark against the metric: a metric
built on the energy spectrum, which a fake prediction with the right spectrum will fool, is
still the right tool for asking about the energy cascade.

`## Performance` is generated in its entirety and holds no prose at all: a number typed
there is a claim nothing checks, and the reading of the numbers belongs in `## Results`
beside the test that produced each one. In `## Results` you write the explanations and
nothing else — the tables between the markers belong to the generator.

A page is signed only once its measurements exist. `python -m fmeval.cards sign <name>
--by <who>` refuses while the bundle has no evaluation run behind it, because most of a
page's claims are claims about how the metric behaved, and a signature says a person read
those claims and stands behind them. There is nothing to stand behind until there are
results.

### `refs.bib` — your citations

One file per bundle, so that bundles can be added and removed without touching anyone
else's references. Cite from the description as `[@key]`.

If you cannot verify that a reference exists, write `TODO(cite)` and say so when you
report. The checker rejects `TODO(cite)` deliberately: a guessed DOI, year or equation
number is worse than an admitted gap, because a guess looks exactly like a real citation.

### `_generated/` — never edit this

Measured results and figures, written by `python -m fmeval.cards evidence <name>` and
`python -m fmeval.cards exemplars <name>`. Every file in here begins with a line saying it
was generated.

The rule is absolute, and the reason for it is the whole point of the system: a number in
documentation must either have come from running real code or be absent. A
plausible-looking value typed in by hand is indistinguishable from a measured one to every
reader, and there is no way to catch it later. If the measurements are wrong, fix whatever
produced them and regenerate.

If no evaluation run exists yet, this section says so in words. That is the correct state,
not a gap to fill in.

---

## Around the repository

### `configs/` — what an evaluation run does

Hydra configuration. Override a setting from the command line for a one-off (`python
evaluate.py metrics=[mse] dataset.time.reduction=10`); edit the files when you are
changing what the default run means for everyone.

Two settings change how much work a run does, and both are recorded with the results.
`dataset.time.reduction` evaluates every Nth snapshot in time, and
`analysis_grid.resolution` sets the common grid that everything is compared on. Runs made
with different values are not comparable with each other, which is why both are recorded.

`configs/degradation/default.yaml` defines the sequence of degradations and the strengths
each is applied at. Its keys are **labels**, not operator names, which is what lets one
operator appear twice with different options. Those labels are what the measurements are
reported against.

### `evaluate.py` and `make_report.py` — run them, don't edit them

`evaluate.py` runs the metrics over every degradation and writes one self-contained folder
per metric under `results/`, holding the raw numbers, the resolved configuration, a record
of where the numbers came from, and a `main.tex` that compiles on its own.
`make_report.py` re-renders one of those folders from the saved numbers without
recomputing anything.

To change what a run does, change the configuration or pass an override. Editing these two
scripts to get one particular result is how a run becomes impossible to reproduce.

### `TEST_DESCRIPTION.md` — what the reported quantities mean

The plain-language reference for every column, every degradation and every figure the
suite reports, plus the protocol behind them. A copy is placed in every results folder, so
that a folder found in two years is still readable.

Edit this file when you add a reported quantity — a test fails if a column, a degradation
or a figure is undocumented. It is not per-metric documentation; that is what the
individual pages are for.

### `AGENTS.md` — what your coding agent reads

The canonical instruction file for coding agents, whichever assistant is running: how to
add a metric, a degradation, a data source or a figure, the testing conventions, and a
table of traps that have already caught someone. Tests check that this file documents
every extension point and every decorator argument, so it cannot quietly fall behind the
code.

### `issues/` — open items

One file per item, with the measurement that established it, so that future work is
written down where a colleague will find it rather than living in someone's private plan
document. When a defect is fixed its file is deleted; `git log --diff-filter=D -- issues/`
recovers what was closed.

---

## Adding a metric, start to finish

```bash
python -m fmeval.cards new my_metric        # 1. create the bundle; never create the files by hand
# 2. write metric.py
# 3. write test_metric.py, with an example you worked out by hand
pytest metrics/my_metric                     # 4. get it passing
# 5. fill in card.yaml
# 6. fill in card.md, quoting the example from step 3
python -m fmeval.cards check my_metric       # 7. it names exactly what is missing
python evaluate.py metrics=[my_metric] dataset=kinet_re5e4_dev   # 8. does it run?
pytest                                       # 9. the whole suite
```

Then ask a person to read the description and run `python -m fmeval.cards sign my_metric
--by <them>`. Leave the status as `candidate`; promoting a metric is a person's decision,
made after looking at the evidence.

When you report what you did, say which `TODO(cite)` markers you left and why. That is
something someone needs to know and it is not visible from the diff.


## The commands, in the order you will use them

```bash
python -m fmeval.cards new <name>                       # create a bundle
python -m fmeval.cards new <name> --kind degradation
python evaluate.py metrics=[<name>] dataset=kinet_re5e4_dev degradation=quick   # smoke test
python -m fmeval.cards check <name>                     # what is missing, and the fix
python -m fmeval.cards exemplars <name>                 # a degradation's example panel
python -m fmeval.cards evidence <name> --results results/<run>   # a metric's measurements
python -m fmeval.cards catalog                          # refresh docs/catalog.json
python -m fmeval.cards list                             # every bundle, with its status
python -m fmeval.cards sign <name> --by <who>           # a person records having read it
```

`evidence` and `exemplars` need the real dataset, so both are run where the data lives and
their output is committed. Everything else works on any machine, which is why this site
builds in CI without access to the data.

## Where the numbers on a page come from

Two places, and the difference between them matters.

**Generated blocks** are written from one named evaluation run. The marker says which
command produced the block, `_generated/fingerprint.json` records which run it came from,
and regenerating rewrites it. A generated block cannot silently describe a different
experiment from the one the page claims.

**Numbers you type into a sentence** are maintained by nothing. They are still worth
writing — only a sentence can say that two metrics ordering damage alike while weighting it
forty times differently makes them duplicates for ranking and not for training — but they
can go stale when the reference run is replaced, and that has already happened once. See
[issues/032](https://github.com/khegazy/pde_metrics/blob/main/issues/032-prose-numbers-can-go-stale.md)
for the proposed check.
