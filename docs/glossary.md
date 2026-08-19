# Glossary

Every term this site uses that a first-time reader would have to guess at, in plain
language. Where a word has an older or shorter name that still appears in the code, that
name is given too.

**Analysis grid** — the one common grid that both fields are placed on before anything is
compared. Two fields stored at different resolutions cannot be compared directly, so both
are transferred onto this shared grid first by averaging over blocks of cells, and the
transfer is recorded as part of the measurement.

**Bundle** — one directory holding everything the repository knows about a single metric,
or a single way of damaging a field: the code, the tests, a machine-readable record, the
written description, and the measured results. Adding a metric means adding one directory
and editing nothing else.

**Card** — the written description of one metric or one degradation, and the page you
read on this site. A card lives inside its bundle, so the file a colleague opens in the
repository and the page a reader opens here are the same text.

**Control** — a metric that is present as a familiar reference point rather than as a
candidate for the panel. The cell-by-cell error norms are the controls: every candidate
metric is read against them.

**Damage** — a metric's raw value rescaled onto a common 0-to-1 scale, where 0 is what the
metric gives the undamaged reference and 1 is what the metric gives a field that shares
the reference's statistics but has no relationship to it. Damage is what makes a result on
density comparable with a result on vorticity, whose raw magnitudes differ by orders of
magnitude.

**Degradation** — a controlled way of making a trusted field wrong, standing in for a way
a surrogate fails in practice. Blurring imitates a model that smooths away detail;
shifting the whole field imitates a model that puts features in the wrong place. Applying
a degradation at a known strength gives an error of known size and kind, which is what
lets a metric be tested.

**Degradation ladder** — the whole collection of degradations, each applied at several
increasing strengths, run against the reference data. Every metric on this site is
measured against the same ladder.

**Derived field** — a physical field computed from other fields, such as vorticity from
velocity. A derived field is always recomputed after the fields are moved onto the
analysis grid, and never averaged directly: the average of a curl is not the curl of the
average.

**Double penalty** — the problem this repository exists to solve. A feature that is
correct in shape and strength but slightly displaced is counted wrong twice, once in the
cells it left and once in the cells it moved into. The same problem is called *cycle
skipping* in seismic imaging.

**Fake prediction** — a deliberately worthless prediction used as a trap test. The main
one keeps the reference field's amplitude spectrum exactly and scrambles all its
structure, so any metric built only on that spectrum scores it as excellent work. It is
called an *impostor* in the code and in some tables.

**Field** — one physical quantity measured everywhere in the domain: density, velocity,
vorticity. Metrics are evaluated on each field separately, and results are never averaged
across fields.

**Flatness** — the fourth moment of a distribution divided by the square of its variance.
The value is 3 for a Gaussian distribution; larger means extreme values occur more often
than a Gaussian would predict, which is the signature of intermittency in turbulence.

**Intermittency** — the tendency of turbulent quantities to be concentrated in rare,
intense bursts rather than spread evenly over the domain, which is why a Gaussian
distribution is a poor model of vorticity.

**Example panel** — the figure on a degradation's page showing that degradation applied to
one fixed snapshot at several strengths, with several different ways of looking at the
same field stacked as rows. Every panel on the site is drawn from the same snapshot so
that the panels can be compared. The panels are called *exemplars* in the code and in the
filenames.

**Monotone** — always moving in one direction. A metric is monotone on a degradation if a
stronger degradation always produces a larger metric value. A metric that is not monotone
is dangerous for choosing between models, because optimising against it can move in the
wrong direction.

**Cell-by-cell metric** — one that compares two fields one grid cell at a time and never
looks at a cell's neighbours. Cheap to compute, and blind to position by construction.
Also called a *pointwise* metric.

**Reference** — the undamaged field that everything else is compared against; the ground
truth of the experiment.

**Separation** — how reliably a metric can tell one strength of damage from the next
strength up. Reported as the smallest overlap found anywhere along the sequence, where 1
means two neighbouring strengths never overlap and 0.5 means the metric cannot separate
them at all.

**Severity** — how strongly a degradation is applied. Sometimes an absolute number, such
as a displacement in grid cells; sometimes measured against the field's own properties,
such as a fraction of the length over which that field varies.

**Severity level** — one degradation applied at one strength: a single experiment.

**Spearman rank correlation** — a measure of whether a metric puts the severity levels in
the right order, ignoring how far apart it spaces them. Computed within a single snapshot
in time here, and never pooled across a trajectory, because these flows decay and pooling
would measure the decay instead of the metric.

**Surrogate** — a model, usually machine-learned, that predicts how a physical system
evolves instead of solving the governing equations directly. Surrogates are what these
metrics are ultimately for.

**Trap test** — a test that is not a model failure at all, but bait for a particular kind
of blind metric. The fake prediction described above is the main one: any metric that
scores it well is ignoring where things are in the field, and must not be used on its own.
Trap tests are called *canaries* in the code and in some tables.
