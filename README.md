# pairwise-design-judging

An agent skill for judging competing UI and design candidates. Judges compare designs in blind, order-swapped pairs, and a Bradley–Terry fit turns those comparisons into a decision. This replaces asking judges for an absolute 0–10 score.

## Why

In iterative "designers improve, judges score" loops, absolute scores break down in two ways:

- **They saturate.** A judge scoring one design alone has no reference point. After a few rounds every decent candidate gets the same score. In the run that produced this skill, 21 of 21 Claude judges gave "8" for four rounds running, so real improvements were invisible.
- **Each judge model has its own baseline.** GPT judges scored about 1.2 points higher than Claude judges. With random judge assignment, an entry that happened to draw generous judges won.

Pairwise judging fixes both. A judge has to say which of two designs is better, and a generous judge is generous to both sides. Swapping the sides cancels position bias, and a Bradley–Terry fit with bootstrap intervals gives a merge rule ("confidently better than what's shipped") instead of improvised tie-breaks.

## What's inside

```
skills/pairwise-design-judging/
  SKILL.md          the protocol: gate, screenshot, plan, judge, record, fit, decide
  scripts/plan.py   builds blind X/Y judging folders, order-swapped, with balanced judge models
  scripts/bt.py     Bradley–Terry fit, 90% bootstrap intervals, merge rule, bias diagnostics
```

The scripts use only the Python 3 standard library.

## Install

**Claude Code plugin:**
```
/plugin marketplace add ttulttul/pairwise-design-judging
/plugin install pairwise-design-judging@pairwise-design-judging
```

**Standalone skill** (Claude Code, or any agent that reads `SKILL.md` skills):
```sh
git clone https://github.com/ttulttul/pairwise-design-judging
cp -r pairwise-design-judging/skills/pairwise-design-judging ~/.claude/skills/
```

## Quick start

```sh
S=~/.claude/skills/pairwise-design-judging/scripts
python3 $S/plan.py --entries entries.json --out judge --round 1 \
  --views home,heating --models gpt-6.1-sol,claude-sonnet-5-5,claude-opus-5-5
# Run one judge per row of judge/plan.tsv; append "<task_id>\t<VERDICT>" to judge/verdicts.tsv
python3 $S/bt.py judge --entries entries.json
```

Example output:

```
Against the incumbent (merge if lower 90% bound > 0.50 and P >= 0.6):
  good             P(beats incumbent) 0.81  [0.71, 0.89]  MERGE-ELIGIBLE
  same             P(beats incumbent) 0.52  [0.44, 0.60]  close: add judgements

Decision: merge good
Position bias: 9/19 decided verdicts favoured the left design (47%; 50% is unbiased)
```

`SKILL.md` has the full protocol, the judge prompt and a budget guide.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

## License

MIT
