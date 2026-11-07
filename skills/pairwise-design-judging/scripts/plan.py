#!/usr/bin/env python3
"""Plan blind, order-swapped pairwise design comparisons.

For each pair of entries and each view, this creates two judging folders, one per order
(A on the left as X and B on the right as Y, then swapped). Each folder holds X/ and Y/
with copies of that view's screenshots, under an anonymous hex name. Judge models are
assigned in a balanced way: the two orders of a pair always go to different models, and
models rotate evenly across tasks.

entries.json:
  {"incumbent": "cur", "entries": {"cur": {"dir": "/path/to/tiles", "designer": "claude-opus-5-5"}, ...}}
Screenshot files must start with "<view>-" (e.g. heating-desktop-dark-part01of03.png).

Usage:
  plan.py --entries entries.json --out JUDGE_DIR --round 3 \
          --views machines,home,heating --models gpt-6.1-sol,claude-sonnet-5-5,claude-opus-5-5 \
          [--mode vs-incumbent|all-pairs] [--only A,B] [--reps 1] [--seed N]

Appends to JUDGE_DIR/plan.tsv (task_id, round, view, x, y, group, judge_model, dir) and prints
the new tasks. Run it again with --only A,B --views v to add judgements to a close pair.
"""
import argparse, itertools, json, os, random, secrets, shutil, sys

p = argparse.ArgumentParser()
p.add_argument('--entries', required=True)
p.add_argument('--out', required=True)
p.add_argument('--round', required=True)
p.add_argument('--views', required=True)
p.add_argument('--models', required=True)
p.add_argument('--mode', choices=['vs-incumbent', 'all-pairs'], default='vs-incumbent')
p.add_argument('--only', help='restrict to one pair, e.g. A,B')
p.add_argument('--reps', type=int, default=1, help='order-swapped repetitions per pair and view')
p.add_argument('--seed', type=int)
a = p.parse_args()

rng = random.Random(a.seed)
cfg = json.load(open(a.entries))
entries, inc = cfg['entries'], cfg['incumbent']
views, models = a.views.split(','), a.models.split(',')
if len(models) < 2:
    sys.exit('need at least two judge models so the two orders of a pair get different judges')

if a.only:
    pairs = [tuple(a.only.split(','))]
elif a.mode == 'vs-incumbent':
    pairs = [(inc, e) for e in entries if e != inc]
else:
    pairs = list(itertools.combinations(sorted(entries), 2))
for pair in pairs:
    for e in pair:
        if e not in entries:
            sys.exit(f'unknown entry {e}')

os.makedirs(a.out, exist_ok=True)
plan_path = os.path.join(a.out, 'plan.tsv')
new_file = not os.path.exists(plan_path)
rotation = models[:]
rng.shuffle(rotation)
turn = 0
rows = []
for view in views:
    for (e1, e2) in pairs:
        for rep in range(a.reps):
            group = secrets.token_hex(4)
            # Randomize which order comes first, then run both orders with different models.
            orders = [(e1, e2), (e2, e1)]
            rng.shuffle(orders)
            first = rotation[turn % len(rotation)]
            second = rotation[(turn + 1) % len(rotation)]
            turn += 1
            for (x, y), model in zip(orders, (first, second)):
                task = secrets.token_hex(4)
                d = os.path.join(a.out, task)
                for side, entry in (('X', x), ('Y', y)):
                    src = entries[entry]['dir']
                    files = sorted(f for f in os.listdir(src) if f.startswith(view + '-') and f.endswith('.png'))
                    if not files:
                        sys.exit(f'no "{view}-*.png" screenshots in {src}')
                    os.makedirs(os.path.join(d, side))
                    for f in files:
                        shutil.copy2(os.path.join(src, f), os.path.join(d, side, f))
                rows.append((task, a.round, view, x, y, group, model, d))

with open(plan_path, 'a') as out:
    if new_file:
        out.write('task_id\tround\tview\tx\ty\tgroup\tjudge_model\tdir\n')
    for r in rows:
        out.write('\t'.join(map(str, r)) + '\n')
for r in rows:
    print('\t'.join(map(str, r)))
print(f'{len(rows)} tasks appended to {plan_path}', file=sys.stderr)
