# Glossary

Terms used across the cards, in plain language.

**Analysis grid** — the common grid both fields are placed on before any comparison. Two
fields at different resolutions cannot be compared directly, so both are remapped by
conservative block averaging first, and the remapping is recorded as part of the
measurement.

**Canary** — a test that is not a model failure but a trap for a particular kind of blind
metric. The phase-randomised impostor is the main one: it has the reference's amplitude
spectrum exactly and none of its structure, so any metric built only on that spectrum
scores it as an excellent prediction.

**Card** — the documentation of one metric or degradation: a typed record, prose for three
audiences, and generated measurements, all living in that item's own directory.

**Control** — a metric that is on the panel as a reference point rather than as a candidate.
The pointwise norms are controls: candidates are read against them.

**Damage** — a metric's value rescaled so that 0 is the undegraded reference and 1 is what
an unrelated field scores. What makes results comparable between metrics and between
fields whose magnitudes differ by orders of magnitude.

**Degradation** — a controlled way of making a field wrong, standing in for a way a
surrogate fails. Blurring imitates a model that is too dissipative; translating imitates
one that misplaces features.

**Degradation ladder** — the whole set of degradations, each at several strengths, applied
to the reference data. The protocol every metric is measured against.

**Derived field** — a field computed from others, such as vorticity from velocity. Always
recomputed after a remap, never averaged: the average of a curl is not the curl of the
average.

**Double penalty** — the pathology this repository exists for. A feature that is correct in
shape and strength but slightly displaced is counted wrong twice, once where it should be
and once where it is. Called cycle skipping in seismic inversion.

**Field** — one physical quantity over the domain: density, velocity, vorticity. Metrics
are evaluated per field, and results are never averaged across them.

**Flatness** — the fourth moment of a distribution divided by the square of its variance. 3
for a Gaussian; larger means extreme values are more common than a Gaussian would predict,
which is the signature of intermittency in turbulence.

**Intermittency** — the tendency of turbulent quantities to be concentrated in rare, intense
events rather than spread evenly, which is why a Gaussian is a poor model of vorticity.

**Pointwise metric** — one that compares two fields cell by cell and never looks at a
neighbourhood. Cheap, and blind to position by construction.

**Reference** — the undegraded field a candidate is compared against; the ground truth of
the experiment.

**Severity** — how strongly a degradation is applied. Sometimes an absolute number, such as
a displacement in cells; sometimes calibrated per field, such as a fraction of that field's
characteristic scale.

**Severity level** — one degradation applied at one strength: a single experiment. Replaces
the word "rung", which said nothing to a reader who had not already been told what it
meant.

**Spearman rank correlation** — a measure of whether a metric orders the severities
correctly, regardless of how it spaces them. Computed within a single frame here, never
pooled across the trajectory, because these flows decay and pooling would measure the decay.

**Surrogate** — a model, usually machine-learned, that predicts the evolution of a physical
system in place of solving the equations directly. What these metrics are ultimately for.
