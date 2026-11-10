"""The skill's documents must not link to files that are missing from the repository."""
import os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, 'skills', 'pairwise-design-judging')
DOCS = [
    os.path.join(ROOT, 'README.md'),
    os.path.join(SKILL, 'SKILL.md'),
    os.path.join(SKILL, 'examples', 'design-contest-recipe.md'),
]
LINK = re.compile(r'\[[^\]]*\]\(([^)\s]+)\)')


class DocLinksTest(unittest.TestCase):
    def test_relative_links_point_at_existing_files(self):
        for doc in DOCS:
            with open(doc, encoding='utf-8') as f:
                text = f.read()
            for target in LINK.findall(text):
                if re.match(r'[a-z][a-z0-9+.-]*:', target) or target.startswith('#'):
                    continue  # external URL or in-page anchor
                path = os.path.join(os.path.dirname(doc), target.split('#')[0])
                self.assertTrue(os.path.exists(path), f'{os.path.relpath(doc, ROOT)} links to missing {target}')

    def test_skill_points_at_its_example(self):
        with open(os.path.join(SKILL, 'SKILL.md'), encoding='utf-8') as f:
            self.assertIn('(examples/design-contest-recipe.md)', f.read())


if __name__ == '__main__':
    unittest.main()
