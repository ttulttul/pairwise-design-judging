---
name: pairwise-design-judging
description: Judge competing UI and design candidates with blind, order-swapped pairwise comparisons and a Bradley–Terry fit instead of absolute 0–10 scores. Use when running design tournaments or iterative improve-and-judge loops with sub-agent designers and judges, when absolute judge scores saturate or tie, or when judges from different models score with different biases.
---

# Pairwise design judging

Absolute scores fail in iterative design loops. A judge scoring one design alone has no reference, so after a few rounds every decent candidate gets the same score (a long run once saw 21 of 21 Claude judges give "8"), and each judge model scores on its own baseline (GPT judges ran about 1.2 points higher than Claude judges). Pairwise judging fixes both problems: a judge must say which of two designs is better, and a generous judge is generous to both sides.

This skill covers the judging half of a loop. Designers, merging and deployment are up to the caller. For a whole contest built around it, see [the example at the end](#example-a-full-contest-from-one-prompt).

## Protocol

### 1. Gate candidates before judging
Do not spend judges on a candidate that is objectively broken. Before a candidate enters judging, it must pass:
- the project's tests;
- a screenshot run with no console errors and no horizontal overflow at phone width (390px);
- ideally, checks for clipped or overflowing text and an automated contrast pass (for example axe-core).

Judges in past runs spent much of their attention rediscovering clipped labels that a script could catch.

### 2. Capture screenshots that judges can actually read
- Capture every view at desktop (about 1440px) and phone (about 390px at 2×), in each colour scheme the UI supports.
- **Tile long pages** into slices about 1.5 screens tall (around 1600 CSS px on desktop, 1200 on a phone). A judge's image viewer downscales a 12,000px page until detail work is invisible, so tiling is not optional.
- Name files `<view>-<size>-<scheme>[-partNNofMM].png` so `plan.py` can select them by view.
- Capture the incumbent (the current shipped version) with the same harness and settings as the candidates.

### 3. Describe the entries
Write `entries.json`:
```json
{"incumbent": "cur",
 "entries": {
   "cur":  {"dir": "/abs/shots/incumbent", "designer": "claude-opus-5-5"},
   "c1":   {"dir": "/abs/shots/c1",        "designer": "gpt-6.1-sol"},
   "c2":   {"dir": "/abs/shots/c2",        "designer": "claude-sonnet-5-5"}}}
```
`designer` is the model that produced the entry. It is used only for the self-preference report.

### 4. Plan the comparisons
```sh
S=<this skill's directory>/scripts   # e.g. ~/.claude/skills/pairwise-design-judging/scripts
python3 $S/plan.py --entries entries.json --out JUDGE_DIR --round 1 \
  --views machines,home,heating --models gpt-6.1-sol,claude-sonnet-5-5,claude-opus-5-5
```
- The default `--mode vs-incumbent` compares each candidate with the incumbent. That is enough to decide a merge, and it costs `candidates × views × 2` judge calls. Use `--mode all-pairs` when you also want candidates ranked against each other.
- **Compare one view at a time.** Smaller comparisons are more reliable, and you learn which views improved. Include only the views a candidate changed if budget is tight.
- Each pair is judged **twice, once in each order**, with X on the left in one task and on the right in the other. The two orders go to **different judge models**, and models rotate evenly. This balanced assignment replaces random assignment, which confounded results whenever one entry happened to draw all of one model.
- Each task gets an anonymous folder `JUDGE_DIR/<hex>/` containing `X/` and `Y/`. The plan is in `JUDGE_DIR/plan.tsv` (columns `task_id`, `judge_model`, `dir`, and so on).

### 5. Run the judges
Start one fresh judge sub-agent per row of `plan.tsv`, on that row's `judge_model`. Run them in parallel. Give each judge only this prompt, with nothing about rounds, scores, incumbents or which designer made what:

> Compare the two user interface designs whose screenshots are in `<dir>/X` and `<dir>/Y`. Each folder shows the same views of the same product.
>
> Use the Anthropic frontend-design skill if your harness offers it (invoke `frontend-design`).
>
> Do not create, modify or delete any files. Do not make suggestions. Look at every screenshot in both folders, deliberate carefully about which design is better overall, and end your reply with a single line in exactly this form:
> `VERDICT: X++` (X much better), `X+` (X slightly better), `=` (no meaningful difference), `Y+` (Y slightly better) or `Y++` (Y much better).

Notes:
- The design-skill line is optional. Keep it only if your judges have a design skill such as [Anthropic's frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design); either way, use the same prompt for every judge.
- Keep the judge prompt identical across tasks and rounds.
- If you use a fixed rubric (for example hierarchy, legibility, consistency, mobile, data clarity), put it in this prompt and never change it. Do not add critique, history or scores.
- Set judge reasoning effort explicitly. Low-effort judges return one generic paragraph.
- If a judge's reply has no parseable verdict, rerun that task with a fresh judge. Don't guess.

### 6. Record verdicts
Append one line per finished task to `JUDGE_DIR/verdicts.tsv`:
```
<task_id>\t<X++|X+|=|Y+|Y++>
```
Take the verdict from the judge's last line matching `VERDICT:\s*(X\+\+|X\+|=|Y\+|Y\+\+)`.

### 7. Fit and decide
```sh
python3 $S/bt.py JUDGE_DIR --entries entries.json            # all views pooled
python3 $S/bt.py JUDGE_DIR --entries entries.json --view home  # one view
```
`bt.py` fits Bradley–Terry strengths and reports the following:
- **Soft outcomes:** `X++` counts as 1, `X+` as 0.75, `=` as 0.5, and so on.
- **Order-swap consistency:** if the two orders of a pair point in opposite directions, both count as a tie. This cancels position bias.
- **Uncertainty:** 90% bootstrap intervals, resampling whole order-swapped groups.
- **Merge rule:** a candidate is eligible when it is *confidently better* than the incumbent: the lower 90% bound of P(beats incumbent) is above 0.5 and the point estimate is at least `--min-p` (default 0.6). The best eligible candidate wins. Otherwise keep the incumbent. The incumbent must be beaten, not tied.
- **Adaptive judging:** if a pair is `close` (its interval straddles 0.5), add one more order-swapped group for just that pair with `plan.py --only INCUMBENT,CANDIDATE --views V`, judge it, and refit. Stop when the decision is stable or a budget cap is reached. This replaces improvised tie-breaks and coin flips.
- **Diagnostics:**
  - *Position bias:* the share of decided verdicts that favour the left design.
  - *Self-preference:* how judges rate designs from their own model family. If it is large, weight it in the write-up and keep judge assignment balanced.

### 8. Keep a ladder across rounds
Measure progress, not just round winners. Each round, also plan a few comparisons of the new incumbent against the original baseline and one or two earlier winners. Use the same `JUDGE_DIR` and `--round N`, with `all-pairs` or `--only`. Fitting `bt.py` without `--round` pools everything into one strength scale, which gives an honest progress curve.

## Budget guide
| Setup | Judge calls per round |
|---|---|
| 3 candidates vs incumbent, 1 pooled view | 6 |
| 3 candidates vs incumbent, 5 views | 30 |
| all pairs of 4 entries, 5 views | 60 |
| plus adaptive groups for close pairs | +2 each |

Start with candidates against the incumbent, judged only on the views each candidate changed. Add groups only where the decision is close.

## Lessons from the run that produced this skill
These come from an overnight loop of 10 rounds, with three designers and 12 judges per round, on a home-lab dashboard.

- Feed judges' *critiques* (never their scores) back to designers as a summary in the next round's brief. This drove most of the improvement.
- Tell designers about rejected attempts and the defects that sank them. Ambitious passes otherwise reintroduce the same regressions.
- Default-effort GPT designers produced token changes (around 20 lines). Set designer reasoning effort explicitly.
- Two designers can collide on a shared preview port. Make the screenshot tool reuse only a server started from its own checkout.

## Example: a full contest from one prompt
[examples/design-contest-recipe.md](examples/design-contest-recipe.md) is an example of what this skill can produce when it is invoked with a prompt like this one:

```
/pairwise-design-judging Run a 24 hour refinement contest with three design models and three judges for {MY_WEBSITE}. Use mock fixtures to populate the interface. Explore and refine all pages and areas in each round. Use the models: `claude-sonnet-5-5`, `claude-opus-5-5`, and `claude-fable-5-2` as both designers and judges. Commit your work as you go and show the user sample screenshots from each round’s work by each judge along with identifying the winner.
```

`{MY_WEBSITE}` can be a Git repository URL, or simply the name of the project at the current project folder root. The agents work out which.

The recipe is a site-independent description of the whole contest: the parameters to fix before round 1, the roles, the one-time setup, the steps of a round (brief, gate, capture, plan, judge, fit, merge or keep, ladder, digest), close calls, stopping rules and what to keep on disk.

Read it as an example of output, not as part of the protocol above. It sets some decision rules of its own that `bt.py` does not implement:
- a merge threshold on win confidence (0.90) instead of the lower-bound rule in step 7;
- a veto when one view is clearly worse, and a separation threshold with a single head-to-head between two leading candidates;
- a bootstrap that resamples views rather than order-swapped groups, and a third judge for strongly contradictory groups.

An orchestrator that adopts those rules has to apply them itself. Otherwise use `bt.py`'s decision as it stands.
