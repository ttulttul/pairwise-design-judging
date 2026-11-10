# Recipe: running a blind pairwise design contest on any website

This recipe tells an orchestrating agent how to improve a website's design through repeated
rounds of competition. In each round several designer agents each produce one candidate redesign,
blind judges compare every candidate with the current design one view at a time, a statistical fit
turns the verdicts into strengths, and the best candidate is merged only if it clearly beats what
is already there. The loop repeats until the budget runs out or progress stalls.

The recipe is independent of the site, the framework and the models used. Anything written in
`<angle brackets>` or listed in section 1 is a parameter you set once before round 1.

## 1. Parameters to fix before you start

| Parameter | Meaning | Reasonable default |
|---|---|---|
| $V$ | number of views (pages or distinct screen states) in the contest | every view a user can reach; 10 to 30 |
| $K$ | designers per round | 3 |
| $J$ | distinct judge models | 3, and never fewer than 2 |
| Viewports | sizes captured | desktop 1440 px wide, phone 390 px wide at 2× density |
| Schemes | colour schemes captured | light and dark, if the site supports both |
| Budget | wall-clock or round limit | 24 hours, or 8 rounds |
| $\tau_{\text{merge}}$ | confidence needed to replace the incumbent | 0.90 |
| $\tau_{\text{sep}}$ | confidence needed to separate two leading candidates | 0.75 |
| $L$ | views sampled per ladder comparison | 5 |

Write the chosen values into a `contest.md` file in the contest directory so that every later
decision can be audited against them. Do not change them mid-contest.

## 2. Roles

| Role | Who |
|---|---|
| Orchestrator | one agent that runs rounds, gates, fits and merges; it never designs and never judges |
| Designers | $K$ agents, ideally different models, one candidate each per round, at high effort |
| Judges | fresh sub-agents drawn from $J$ models, one per judging task, at high effort |
| Incumbent | the design currently on the contest branch; before round 1 this is the original site |

Designers and judges may be the same underlying models, because the judging is blind and each
judge is a fresh sub-agent with no memory of having designed anything. A model may still favour
its own style, which is why every comparison is split across two different judge models (section 5).

## 3. One-time setup

1. **Isolate the site.** Create a contest branch from the current main branch. Serve the site
   locally from deterministic fixture data so that every capture of the same code looks the same.
   Nothing in the contest may read from or write to production.
2. **List the views.** Write a manifest of all $V$ views, each with a stable name, a URL or
   navigation script, and any state needed to reach it (logged-in user, open dialog, filled form,
   empty state, error state). Include unglamorous views such as settings and error pages, because
   a redesign that only works on the home page is a regression.
3. **Build the capture script.** It must visit every view at every viewport and scheme, wait for
   the page to settle, and save screenshots. Cut long pages into tiles about 1.5 screens tall
   (about 1600 CSS px on desktop and 1200 on phone) so that judges can read detail instead of
   squinting at a thumbnail. Name files `<view>-<size>-<scheme>[-partNNofMM].png`. The script must
   also record console errors, failed network requests and horizontal overflow.
4. **Define the gate.** List the commands that must pass for a candidate to be judged at all
   (section 4.2), and record the incumbent's lint count as the baseline.
5. **Capture the original.** Run the capture on the untouched site and keep it forever under a
   fixed name such as `original/`. The ladder in section 9 depends on it.
6. **Freeze the judge prompt.** Write it once (section 6) and never edit it during the contest.

## 4. One round

### 4.1 Brief

Give each designer its own git worktree and its own preview ports, the current incumbent, and a
digest of the previous round's judge critiques. The digest contains no scores and no designer
names. It also lists rejected candidates and the specific defects that sank them, so that the same
mistakes are not repeated. Require every designer to work across all $V$ views, not a favourite
subset, and to leave behaviour, routes and data untouched unless the brief says otherwise.

### 4.2 Gate

A candidate is judged only if all of the following pass. A candidate that fails is rejected for
the round, and the reason goes into the next digest.

1. Every test suite and type-check the project has.
2. Lint no worse than the incumbent's baseline.
3. A full capture of all $V$ views with no console errors, no failed network requests and no
   horizontal overflow at phone width.

The gate exists so that judges only ever compare working designs. Never ask a judge to weigh
beauty against breakage.

### 4.3 Capture

Capture every view of each surviving candidate, and of the incumbent if it has changed since its
last capture, at every viewport and scheme.

### 4.4 Plan, judge, fit, decide

Follow sections 5 to 8 in order: plan the blind comparisons, run the judges, fit strengths and
apply the merge rule, and resolve a close call between leaders if there is one.

### 4.5 Merge or keep

If a candidate qualifies, merge it into the contest branch and run CI on the new head. If CI
fails, revert the merge and treat the candidate as rejected. If no candidate qualifies, the
incumbent stays. Keeping the incumbent is a normal, healthy outcome and not a failed round.

### 4.6 Ladder

After a merge, measure real progress against history (section 9).

### 4.7 Digest

Condense the judges' written critiques into the next round's brief. Group them by view and by
theme, keep concrete observations ("table header overlaps the filter bar on phone, dark mode"),
and drop verdicts, scores and anything that identifies who made which candidate.

## 5. Planning the comparisons

Let the round have incumbent $I$, gated candidates $C_1, \dots, C_K$ and views $v_1, \dots, v_V$.

For each candidate $C$ and each view $v$, make one **order-swapped group** of two tasks. In task 1,
$C$ is on the left (called X) and $I$ is on the right (called Y). In task 2 the sides are swapped.
Randomise which task is created first. The two tasks of a group must go to **different judge
models**. Take models from a shuffled rotation and advance it one step per group, so that every
model judges the same share of tasks and no model is tied to one candidate or one side.

Each task is an anonymous folder `JUDGE_DIR/<random hex>/` holding `X/` and `Y/` copies of that
view's tiles. Nothing in the folder path, the file names or the image metadata may reveal the
designer, the round, or which side is the incumbent. Keep the mapping from hex name to
(candidate, view, order, judge model) in a private plan file that judges cannot read.

Tasks per round against the incumbent:

$$
K \times V \times 2 .
$$

With 3 candidates and 21 views that is 126. A head-to-head between two candidates (section 8) adds
$V \times 2$. Each ladder comparison (section 9) adds $L \times 2$.

If $V$ is large enough that this is unaffordable, judge a stratified random sample of views per
round, drawn fresh each round and shared by all candidates, and always include the highest-traffic
views.

## 6. Judging

Every judge receives the same frozen prompt. It names the two folders, tells the judge to open
every screenshot in both, forbids changing files and forbids suggesting improvements, asks for a
short written critique of each side, and requires this final line:

```
VERDICT: X++ | X+ | = | Y+ | Y++
```

`X++` means X is clearly better, `X+` slightly better, `=` no meaningful difference, and likewise
for Y. Tell judges nothing about rounds, scores, incumbents or designers. To a judge, each task is
simply two versions of one screen.

If a reply has no verdict line that can be parsed, discard it and rerun the task with a fresh
judge of the same model. Append every verdict to `verdicts.tsv` with the task's hex name, and
store the critique text beside it for the digest.

## 7. Turning verdicts into a decision

### 7.1 Soft outcomes

Each verdict becomes a score $s \in [0, 1]$ for the left-hand design X:

| Verdict | $s$ for X | $s$ for Y |
|---|---|---|
| `X++` | 1.00 | 0.00 |
| `X+` | 0.75 | 0.25 |
| `=` | 0.50 | 0.50 |
| `Y+` | 0.25 | 0.75 |
| `Y++` | 0.00 | 1.00 |

Store each judgement as a score for one fixed member of the pair, for example whichever entry
sorts first alphabetically (call it $A$), so that both orders of a group are on the same footing:
$s_A = s_X$ if $A$ was on the left, otherwise $s_A = 1 - s_X$.

### 7.2 Order-swap consistency

Each group now holds two scores for $A$, one from each order: $s_A^{(1)}$ and $s_A^{(2)}$. Use
their mean $\bar{s}_A$ as the group's outcome. Averaging cancels any preference a judge has for
the left or right side.

Call a group **contradictory** when its two verdicts pick opposite winners, that is when one score
is above 0.5 and the other below. A contradictory group averages out near 0.5, which is the right
treatment: the view is a toss-up. Send it to a third judge model only when the two scores differ
by 0.75 or more (for example `X++` against `Y+`), and then use the mean of all three.

As a health check, compute the mean of $s_X$ over every task in the round. It should be near 0.5.
If it is outside 0.40 to 0.60, the judges have a position bias; the swap still corrects for it,
but record the figure in the round report.

### 7.3 Fitting strengths

Give every design $i$ a strength $\theta_i$ and model the chance that $i$ is preferred to $j$ with
the Bradley-Terry form

$$
p_{ij} = \frac{1}{1 + e^{-(\theta_i - \theta_j)}} .
$$

Fit the strengths by maximising the soft log-likelihood over all groups $g$ with outcome
$\bar{s}_g$ for design $i$ against design $j$, with a weak penalty that keeps strengths finite when
one design wins everything:

$$
\sum_g \Big[ \bar{s}_g \log p_{ij} + (1 - \bar{s}_g) \log (1 - p_{ij}) \Big] - \frac{\lambda}{2} \sum_i \theta_i^2 , \qquad \lambda = 0.1 .
$$

Fix $\theta_I = 0$ so that every candidate's strength reads as its lead over the incumbent.

### 7.4 Uncertainty

The view is the unit of evidence, so resample views. Draw $V$ views with replacement, keep all
groups belonging to the drawn views, refit, and repeat at least 2000 times. From the resampled
fits compute, for each candidate $C$, the win confidence

$$
P_C = \Pr(\theta_C > \theta_I),
$$

and for any two candidates the separation confidence $\Pr(\theta_{C_a} > \theta_{C_b})$.

### 7.5 The merge rule

Let $C^\ast$ be the candidate with the highest fitted strength. Merge $C^\ast$ only if all three
conditions hold.

1. **Confidence.** $P_{C^\ast} \ge \tau_{\text{merge}}$.
2. **No broken view.** There is no view where both orders returned a double verdict for the
   incumbent (group outcome $\bar{s} = 0$ for the candidate). One clearly worse view vetoes the
   merge however good the rest is, and that view is named in the next digest.
3. **Clear leader.** Either $C^\ast$ is the only candidate meeting conditions 1 and 2, or its
   separation confidence over the next qualifying candidate is at least $\tau_{\text{sep}}$.

If conditions 1 and 2 hold for two or more candidates but condition 3 fails, go to section 8. If no
candidate meets conditions 1 and 2, keep the incumbent.

## 8. Close calls

When two leading candidates both beat the incumbent but cannot be separated, judge them directly
against each other: one order-swapped group per view, $V \times 2$ tasks, planned and judged
exactly as in sections 5 and 6. Add these verdicts to the round's data, refit everything together
and recompute the separation confidence.

Run this head-to-head **at most once per round**. If the two are still not separated, do not keep
judging until noise produces a winner. Pick the one with the higher win confidence against the
incumbent, and break any remaining tie by the smaller diff. Record in the round report that the
choice was a tie-break.

## 9. The ladder

Beating the incumbent each round does not prove the site is getting better. Preferences can cycle,
and a chain of narrow wins can drift sideways. The ladder checks progress against fixed reference
points.

After each merge, judge the new incumbent against two references: the original site, and an
earlier winner (the incumbent from two merges ago is a good choice). Each comparison uses $L$
views, drawn at random but always including the highest-traffic view, in order-swapped groups, so
$L \times 2$ tasks per comparison.

Then refit one Bradley-Terry model over **all** verdicts from **all** rounds: candidates,
incumbents, head-to-heads and ladder checks together, with the original fixed at $\theta = 0$. The
strengths of the successive incumbents on this common scale are the contest's progress curve.
Report it after every round.

If a new incumbent's ladder strength is below the previous incumbent's, with at least 0.75
bootstrap confidence, the contest has drifted. Revert the merge, restore the previous incumbent,
and describe the regression in the next digest.

## 10. When to stop

Stop when the budget is spent, when three consecutive rounds end with no merge, or when the
ladder gain across the last two merges is below 0.1 in strength. On stopping, the contest branch
holds the final design. Deliver it with the progress curve, the per-round reports, and a
before-and-after capture of every view.

## 11. What to keep on disk

Keep one directory per round under `rounds/`, containing the brief sent to designers, the gate
results for each candidate, the captures, the private plan file, `verdicts.tsv`, the critiques,
the fit output with strengths and confidences, the decision with the rule that produced it, and
the digest. A reader should be able to reconstruct every merge decision from these files alone.

## 12. Rules the orchestrator must not break

The orchestrator never judges and never edits a candidate. Judges never learn which side is the
incumbent, who designed anything, or what the scores are. Designers never see scores, only
critiques. The judge prompt, the parameters and the merge rule are fixed before round 1 and are
not adjusted to rescue a candidate the orchestrator happens to like. A candidate that fails the
gate is never judged. Nothing touches production.
