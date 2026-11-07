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

**Codex plugin:**
```sh
codex plugin marketplace add ttulttul/pairwise-design-judging
codex plugin add pairwise-design-judging@pairwise-design-judging
```
In the ChatGPT desktop app, you can instead add the marketplace and install it from the Plugins Directory.

**Standalone skill** (any agent that reads `SKILL.md` skills):
```sh
npx skills add ttulttul/pairwise-design-judging
# or copy it yourself:
git clone https://github.com/ttulttul/pairwise-design-judging
cp -r pairwise-design-judging/skills/pairwise-design-judging ~/.claude/skills/   # or ~/.codex/skills/
```

## Using it in a session

You don't run the scripts yourself. You describe the job in an interactive agent session, and the agent follows `SKILL.md`: it gates and screenshots the candidates, writes `entries.json`, runs `plan.py`, starts one judge sub-agent per planned task, records the verdicts and runs `bt.py`. The agent loads the skill on its own when your request matches the skill's description. You can also name the skill to load it explicitly, as in the examples below.

### Claude Code

Start `claude` in your project and type a slash command followed by your request. With the plugin installed, the command is `/pairwise-design-judging:pairwise-design-judging`. With the standalone skill in `~/.claude/skills/`, it is `/pairwise-design-judging`.

```
> /pairwise-design-judging:pairwise-design-judging Three redesigns of the dashboard
  are on branches redesign-a, redesign-b and redesign-c. main is what's shipped.
  Judge each one against main on the home and heating views, using Sonnet and Opus
  judges, and tell me whether any of them should be merged.
```

A typical run looks like this (abridged):

```
⏺ Skill(pairwise-design-judging)
⏺ Bash(npm test)  ×4 checkouts — all pass
⏺ Bash(node scripts/shoot.mjs …)  home, heating × 1440/390 × light/dark, tiled
⏺ Write(judge/entries.json)
⏺ Bash(python3 …/scripts/plan.py --entries judge/entries.json --out judge --round 1
       --views home,heating --models claude-sonnet-5-5,claude-opus-5-5)
  ⎿ 12 tasks written to judge/plan.tsv
⏺ 12 × Agent(Compare the two user interface designs…)  in parallel, model per plan.tsv
⏺ Bash(printf '3f9c1a\tX+\n…' >> judge/verdicts.tsv)
⏺ Bash(python3 …/scripts/bt.py judge --entries judge/entries.json)
  ⎿ redesign-b   P(beats incumbent) 0.58  [0.47, 0.68]  close: add judgements
⏺ redesign-b is close on heating, so I'm adding one more order-swapped group for that pair.
⏺ Bash(python3 …/scripts/plan.py … --only main,redesign-b --views heating --round 1)
  …
⏺ Decision: merge redesign-b. P(beats main) 0.71 [0.60, 0.80]. redesign-a and
  redesign-c did not beat main. Position bias: 11/22 decided verdicts favoured the left (50%).
```

Follow-up prompts in the same session continue the loop. For example: "Summarise the judges' critiques of redesign-a and redesign-c as a brief for the next round of designers", or "Merge redesign-b and plan round 2 with a ladder comparison against the original baseline."

### Codex

Start `codex` in your project and mention the skill with `$` in the composer. Type `$` (or run `/skills`) to pick it from the list.

```
› $pairwise-design-judging I have screenshots of the current settings page in
  shots/incumbent and of two candidates in shots/c1 and shots/c2, already tiled and
  named <view>-<size>-<scheme>. Judge both against the incumbent on the settings and
  profile views, and tell me which one to ship.
```

Codex follows the same protocol (abridged):

```
• Using skill pairwise-design-judging
• Ran ls shots/*  — 16 screenshots per entry, views: settings, profile
• Wrote judge/entries.json  (incumbent: cur; candidates: c1, c2)
• Ran python3 ~/.codex/skills/pairwise-design-judging/scripts/plan.py --entries judge/entries.json
      --out judge --round 1 --views settings,profile --models gpt-6.1-sol,gpt-6-astra
  └ 8 tasks written to judge/plan.tsv
• Spawned 8 judge sub-agents, one per row of judge/plan.tsv
• Appended 8 verdicts to judge/verdicts.tsv
• Ran python3 …/scripts/bt.py judge --entries judge/entries.json
  └ c1   P(beats incumbent) 0.79  [0.66, 0.88]  MERGE-ELIGIBLE
    c2   P(beats incumbent) 0.44  [0.33, 0.56]
─ Ship c1. It is confidently better than the current page on both views; c2 is not.
```

Each tool's sub-agents run only that vendor's models: Claude models in Claude Code, OpenAI models in Codex. Pass `--models` only the models your session can start. Mixing judge families (the setup the skill was built for) needs an orchestrator that can start both kinds of judge. If the plan names a model the session can't run, the agent should tell you rather than quietly substitute another model.

## Packaging

One repo serves both ecosystems:

| File | Used by |
|---|---|
| `plugin.json` | Portable [agent-plugins](https://agent-plugins.org) manifest (OpenAI Codex / ChatGPT) |
| `.agents/plugins/marketplace.json` | Codex marketplace (`codex plugin marketplace add`) |
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Claude Code plugin and marketplace |
| `skills/pairwise-design-judging/` | The skill itself, in the [Agent Skills](https://agentskills.io) format |

`tools/build-zip.sh` builds `dist/pairwise-design-judging-<version>.zip` for the OpenAI plugin submission portal. CI checks that `plugin.json` matches its schema and that the two manifests carry the same version.

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
