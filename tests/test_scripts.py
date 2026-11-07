"""End-to-end tests: plan comparisons on synthetic entries, simulate judges, fit, and decide."""
import csv, json, os, random, re, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'pairwise-design-judging', 'scripts')
MODELS = 'gpt-6.1-sol,claude-sonnet-5-5,claude-opus-5-5'


def run(*args):
    return subprocess.run([sys.executable, *args], check=True, capture_output=True, text=True).stdout


class PairwiseJudgingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.quality = {'cur': 0.0, 'good': 0.9, 'same': 0.0, 'bad': -0.9}
        entries = {}
        for e in self.quality:
            d = os.path.join(self.tmp, 'shots', e)
            os.makedirs(d)
            for view in ('home', 'heating'):
                for part in ('part01of02', 'part02of02'):
                    with open(os.path.join(d, f'{view}-desktop-light-{part}.png'), 'w') as f:
                        f.write(e)
            entries[e] = {'dir': d, 'designer': 'gpt-6.1-sol' if e == 'same' else 'claude-opus-5-5'}
        self.entries = os.path.join(self.tmp, 'entries.json')
        with open(self.entries, 'w') as f:
            json.dump({'incumbent': 'cur', 'entries': entries}, f)
        self.judge = os.path.join(self.tmp, 'judge')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def plan(self, *extra):
        return run(os.path.join(SCRIPTS, 'plan.py'), '--entries', self.entries, '--out', self.judge,
                   '--round', '1', '--models', MODELS, '--seed', '5', *extra)

    def rows(self):
        with open(os.path.join(self.judge, 'plan.tsv')) as f:
            return list(csv.DictReader(f, delimiter='\t'))

    def simulate(self, noise=0.4, left_bias=0.0, seed=11):
        rng = random.Random(seed)
        with open(os.path.join(self.judge, 'verdicts.tsv'), 'w') as f:
            for r in self.rows():
                d = self.quality[r['x']] - self.quality[r['y']] + rng.gauss(0, noise) + left_bias
                v = 'X++' if d > 1 else 'X+' if d > 0.3 else '=' if d > -0.3 else 'Y+' if d > -1 else 'Y++'
                f.write(f"{r['task_id']}\t{v}\n")

    def test_plan_is_blind_order_swapped_and_balanced(self):
        self.plan('--views', 'home,heating', '--reps', '2')
        rows = self.rows()
        self.assertEqual(len(rows), 3 * 2 * 2 * 2)  # candidates x views x reps x orders
        groups = {}
        for r in rows:
            groups.setdefault(r['group'], []).append(r)
            self.assertEqual(sorted(os.listdir(r['dir'])), ['X', 'Y'])
            files = os.listdir(os.path.join(r['dir'], 'X'))
            self.assertTrue(files and all(f.startswith(r['view'] + '-') for f in files))
            self.assertRegex(os.path.basename(r['dir']), r'^[0-9a-f]{8}$')
            # X really holds the x entry's screenshots (contents are the entry name here).
            with open(os.path.join(r['dir'], 'X', files[0])) as f:
                self.assertEqual(f.read(), r['x'])
        for g in groups.values():
            self.assertEqual(len(g), 2)
            self.assertEqual({(g[0]['x'], g[0]['y'])}, {(g[1]['y'], g[1]['x'])})
            self.assertNotEqual(g[0]['judge_model'], g[1]['judge_model'])
        counts = {}
        for r in rows:
            counts[r['judge_model']] = counts.get(r['judge_model'], 0) + 1
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 2)

    def test_fit_merges_the_better_candidate_and_reports_bias(self):
        self.plan('--views', 'home,heating', '--reps', '3')
        self.simulate()
        out = run(os.path.join(SCRIPTS, 'bt.py'), self.judge, '--entries', self.entries, '--boot', '400')
        self.assertIn('Decision: merge good', out)
        self.assertRegex(out, r'bad\s+P\(beats incumbent\) 0\.[0-3]\d.*\bno\b')
        self.assertIn('Position bias:', out)
        self.assertIn('Self-preference:', out)
        strengths = dict(re.findall(r'^\s+(\w+)\s+([+-]\d\.\d\d)\s+\[', out, re.M))
        self.assertGreater(float(strengths['good']), float(strengths['cur']))
        self.assertGreater(float(strengths['cur']), float(strengths['bad']))

    def test_ties_keep_the_incumbent_and_ask_for_more_judgements(self):
        self.quality = {'cur': 0.0, 'good': 0.25, 'same': 0.0, 'bad': 0.0}
        self.plan('--views', 'home', '--reps', '1')
        self.simulate(noise=0.3, seed=3)
        out = run(os.path.join(SCRIPTS, 'bt.py'), self.judge, '--entries', self.entries, '--boot', '300')
        self.assertIn('Decision: keep the incumbent', out)

    def test_position_bias_is_cancelled_by_order_swap(self):
        # Every judge prefers the left design strongly; with order swap no candidate should win.
        self.quality = {e: 0.0 for e in self.quality}
        self.plan('--views', 'home,heating', '--reps', '2')
        self.simulate(noise=0.1, left_bias=0.8)
        out = run(os.path.join(SCRIPTS, 'bt.py'), self.judge, '--entries', self.entries, '--boot', '300')
        self.assertIn('Decision: keep the incumbent', out)
        self.assertRegex(out, r'disagreed with themselves')
        self.assertRegex(out, r'favoured the left design \((9\d|100)%')

    def test_only_adds_judgements_for_one_pair(self):
        self.plan('--views', 'home')
        before = len(self.rows())
        self.plan('--views', 'home', '--only', 'cur,good')
        added = self.rows()[before:]
        self.assertEqual(len(added), 2)
        self.assertEqual({frozenset((r['x'], r['y'])) for r in added}, {frozenset(('cur', 'good'))})

    def test_bad_verdict_is_rejected(self):
        self.plan('--views', 'home')
        task = self.rows()[0]['task_id']
        with open(os.path.join(self.judge, 'verdicts.tsv'), 'w') as f:
            f.write(f'{task}\tmaybe\n')
        with self.assertRaises(subprocess.CalledProcessError):
            run(os.path.join(SCRIPTS, 'bt.py'), self.judge)


if __name__ == '__main__':
    unittest.main()
