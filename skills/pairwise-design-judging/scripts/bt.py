#!/usr/bin/env python3
"""Fit Bradley–Terry strengths to pairwise design judgements and apply a merge rule.

Inputs in JUDGE_DIR:
  plan.tsv       written by plan.py
  verdicts.tsv   one line per finished task: "<task_id>\t<VERDICT>", where VERDICT is one of
                 X++  X+  =  Y+  Y++   (X much better ... Y much better)
  entries.json   optional, for the self-preference report (entry -> designer model)

Scoring: a verdict gives X a soft outcome of 1, 0.75, 0.5, 0.25 or 0. The two orders of a pair
(same group) must agree on direction. If one prefers A and the other prefers B, both count as
ties, which cancels position bias.

Usage:
  bt.py JUDGE_DIR [--round R] [--view V] [--entries entries.json] [--incumbent ID]
                  [--min-p 0.6] [--boot 2000] [--seed N]

Merge rule: a candidate is merge-eligible when it is confidently better than the incumbent:
the lower 90% bound of P(beats incumbent) is above 0.5 and the point estimate is at least --min-p.
The best eligible candidate wins. "Close" means the interval straddles 0.5 with a point estimate
above 0.5: add an order-swapped judgement for that pair and refit.

Prints strengths with 90% intervals, P(candidate beats incumbent), the merge decision,
pairs whose interval crosses the threshold (add judgements there), position bias, and
self-preference by judge family.
"""
import argparse, collections, json, math, os, random, sys

OUTCOME = {'X++': 1.0, 'X+': 0.75, '=': 0.5, 'Y+': 0.25, 'Y++': 0.0}

p = argparse.ArgumentParser()
p.add_argument('dir')
p.add_argument('--round')
p.add_argument('--view')
p.add_argument('--entries')
p.add_argument('--incumbent')
p.add_argument('--min-p', type=float, default=0.6)
p.add_argument('--boot', type=int, default=2000)
p.add_argument('--seed', type=int, default=1)
a = p.parse_args()

def read_tsv(path, header=True):
    with open(path) as f:
        lines = [l.rstrip('\n').split('\t') for l in f if l.strip()]
    if not header:
        return lines
    keys = lines[0]
    return [dict(zip(keys, l)) for l in lines[1:]]

plan = {r['task_id']: r for r in read_tsv(os.path.join(a.dir, 'plan.tsv'))}
verdict_path = os.path.join(a.dir, 'verdicts.tsv')
verdicts = {}
if os.path.exists(verdict_path):
    for task, v, *_ in read_tsv(verdict_path, header=False):
        v = v.strip()
        if v not in OUTCOME:
            sys.exit(f'bad verdict {v!r} for task {task}; expected one of {list(OUTCOME)}')
        verdicts[task] = v

entries_cfg = json.load(open(a.entries)) if a.entries else None
incumbent = a.incumbent or (entries_cfg or {}).get('incumbent')
designer = {k: v.get('designer') for k, v in (entries_cfg or {}).get('entries', {}).items()}

def family(model):
    return (model or '').split('-')[0]

# Judgements as (group, A, B, outcome for A, judge_model, x_entry, raw verdict).
judged = []
for task, v in verdicts.items():
    r = plan.get(task)
    if r is None:
        sys.exit(f'verdict for unknown task {task}')
    if a.round and r['round'] != a.round:
        continue
    if a.view and r['view'] != a.view:
        continue
    A, B = sorted((r['x'], r['y']))
    s = OUTCOME[v] if r['x'] == A else 1 - OUTCOME[v]
    judged.append({'group': r['group'], 'A': A, 'B': B, 's': s, 'model': r['judge_model'], 'x': r['x'], 'v': v})
if not judged:
    sys.exit('no verdicts match the filters yet')

# Order-swap consistency: within a group, if the two orders point in opposite directions, call both ties.
by_group = collections.defaultdict(list)
for j in judged:
    by_group[j['group']].append(j)
inconsistent = 0
for js in by_group.values():
    signs = {(j['s'] > 0.5) - (j['s'] < 0.5) for j in js}
    if 1 in signs and -1 in signs:
        inconsistent += 1
        for j in js:
            j['s'] = 0.5
groups = list(by_group.values())

def fit(sample):
    """Bradley–Terry by minorise–maximise on soft wins, with one virtual tie per compared pair."""
    wins, n, ents = collections.Counter(), collections.Counter(), set()
    for js in sample:
        for j in js:
            A, B = j['A'], j['B']
            ents.update((A, B))
            wins[A] += j['s']; wins[B] += 1 - j['s']; n[(A, B)] += 1
    for (A, B) in list(n):
        wins[A] += 0.5; wins[B] += 0.5; n[(A, B)] += 1
    p = {e: 1.0 for e in ents}
    for _ in range(500):
        new = {}
        for i in ents:
            den = sum(c / (p[i] + p[k]) for (x, y), c in n.items() for k in ([y] if x == i else [x] if y == i else []))
            new[i] = wins[i] / den if den else p[i]
        g = math.exp(sum(math.log(v) for v in new.values()) / len(new))
        p = {k: v / g for k, v in new.items()}
    return p

point = fit(groups)
rng = random.Random(a.seed)
boots = [fit([rng.choice(groups) for _ in groups]) for _ in range(a.boot)]

def interval(xs, lo=0.05, hi=0.95):
    xs = sorted(xs)
    return xs[int(lo * (len(xs) - 1))], xs[int(hi * (len(xs) - 1))]

print(f'{len(judged)} judgements in {len(groups)} order-swapped groups; {inconsistent} groups disagreed with themselves and count as ties\n')
print('Strength (log scale, 0 = average) with 90% bootstrap interval:')
for e in sorted(point, key=point.get, reverse=True):
    lo, hi = interval([math.log(b[e]) for b in boots if e in b])
    tag = '  (incumbent)' if e == incumbent else ''
    print(f'  {e:16s} {math.log(point[e]):+.2f}  [{lo:+.2f}, {hi:+.2f}]{tag}')

def p_beats(pp, i, j):
    return pp[i] / (pp[i] + pp[j])

if incumbent and incumbent in point:
    print(f'\nAgainst the incumbent (merge if lower 90% bound > 0.50 and P >= {a.min_p}):')
    best, close = None, []
    for e in sorted(point):
        if e == incumbent:
            continue
        ps = [p_beats(b, e, incumbent) for b in boots if e in b and incumbent in b]
        lo, hi = interval(ps)
        pe = p_beats(point, e, incumbent)
        eligible = lo > 0.5 and pe >= a.min_p
        if eligible:
            status = 'MERGE-ELIGIBLE'
        elif lo <= 0.5 < hi and pe > 0.5:
            status = 'close: add judgements'
            close.append(e)
        else:
            status = 'no'
        if eligible and (best is None or pe > best[1]):
            best = (e, pe)
        print(f'  {e:16s} P(beats incumbent) {pe:.2f}  [{lo:.2f}, {hi:.2f}]  {status}')
    print(f'\nDecision: {"merge " + best[0] if best else "keep the incumbent"}')
    if close and not best:
        print('Add an order-swapped judgement for: ' + ', '.join(f'{incumbent},{c}' for c in close))

# Position bias: share of non-tie verdicts that favoured the left (X) design.
decided = [j for j in judged if j['v'] != '=']
if decided:
    left = sum(1 for j in decided if j['v'].startswith('X'))
    print(f'\nPosition bias: {left}/{len(decided)} decided verdicts favoured the left design ({left / len(decided):.0%}; 50% is unbiased)')

# Self-preference: how judges score designs made by their own model family versus others.
if designer:
    own, other = [], []
    for j in judged:
        for e, s in ((j['A'], j['s']), (j['B'], 1 - j['s'])):
            fam = family(designer.get(e))
            if fam:
                (own if fam == family(j['model']) else other).append(s)
    if own and other:
        print(f'Self-preference: judges gave their own family\'s designs {sum(own)/len(own):.2f} on average vs {sum(other)/len(other):.2f} for others ({len(own)}/{len(other)} outcomes)')
