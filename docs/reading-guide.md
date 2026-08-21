# How to read a metric page

Every metric has one page, and every page is laid out the same way. This guide walks
through that layout section by section, and explains the three measured quantities that
recur throughout. The pages are called **cards** in this repository, and a card lives in
the same directory as the code it describes.

The sections run in a fixed order, from what the metric *is* to what the metric *did on
our data*. The break between those two halves matters: the first four sections hold for
any dataset, so a reader adopting a metric for their own work can stop at Limitations.
The last two report findings from one specific recorded run on our data.

## Definition

The equation, how the equation is turned into arithmetic on a grid, and how the edges of
the domain are handled. "None." is a common and perfectly good answer to that last one — a
metric that never looks beyond a single grid cell has no edge to treat. It is worth
reading, because the choices available at the edge (wrapping around to the opposite side,
mirroring, padding with zeros) give different numbers from the same formula, and two
implementations of one published equation can disagree on nothing else.

## Intuition

The same content in words, with no notation at all, written for an early graduate student
in any field. The section opens with what the metric measures and which way of being
wrong the metric reveals, explains the mechanism, and includes a small worked example —
usually a four-by-four grid — whose numbers are taken from the metric's own test file. The
section closes by naming what the metric ignores, because every metric is blind to
something.

## Reading the output

What to do with a number you are holding: the range the number can take, its units,
whether lower or higher is better, what makes a value good and what that depends on, and
which comparisons are valid. That last part is the one most often needed. Comparing a
cell-by-cell metric across two grid resolutions, for instance, is invalid without first
putting both fields on a common grid, because the value is an average over cells and
refining the grid changes how much weight the small scales get.

## Limitations

At least one concrete situation where the metric gives a misleading answer, described so
that you can recognise the situation in your own results.

## Performance and Results

The measured half of the page. Every number in both sections comes from one recorded
evaluation run, named at the top of Results along with the dataset, the grid and the
number of snapshots it covered.

**Performance** is a single table near the top of the card summarising how the metric
behaved on every family of test, broken down by physical field, so that two metrics can
be compared at a glance.

**Results** breaks that summary down one test at a time. Each subsection links to the
way of damaging the field that it reports, shows the numbers for that damage, and then
says in a few sentences what those numbers mean for this metric.

Three measured quantities recur in those tables, and they are worth understanding before
you read one.

**Damage** puts every metric on the same 0-to-1 scale. A raw mean squared error and a raw
transport distance are not comparable numbers, so each metric's raw value is rescaled:
0 is what the metric gives the undamaged reference, and 1 is what the metric gives a
field that has the right statistics but no relationship whatsoever to the truth. Damage
is what makes a result on density comparable with a result on vorticity. A damage above 1
means the metric considers the prediction *worse* than a completely unrelated field.

**Rank correlation** asks whether the metric puts increasing damage in increasing order.
It is the Spearman rank correlation between the strength of the damage applied and the
value the metric returned, and it runs from -1 (exactly backwards) through 0 (no
relationship) to 1 (perfectly ordered every time). It is computed within a single
snapshot in time and never pooled across a whole trajectory, because these flows decay:
pooling would measure the decay rather than the metric.

**Separation** asks whether the metric can tell one strength of damage from the next
one up. A metric can put the strengths in the right order on average and still overlap so
much between neighbouring strengths that it cannot distinguish two models one step apart.
The reported number is the smallest such overlap along the whole sequence, where 1 means
two neighbouring strengths never overlap and 0.5 means the metric cannot separate them at
all.

## About the figures

Colour limits are shared across each row of a figure and printed at the row's edge. This
matters more than it sounds. If each panel were autoscaled separately, a badly damaged
field would be drawn with exactly the same colours as the original and would look
identical to it — and it would do so with nothing on the page to warn you.
