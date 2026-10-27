"""Replay local article checks and render full-text comparisons; no model calls."""
import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from editorial_guard.core import Context, content_hash, lint_text, verify_edit


def inspect(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    cases = []
    for name in ('work-report', 'tutorial'):
        folder = ROOT / 'examples/full-articles' / name
        original = (folder / 'original.md').read_text(encoding='utf-8')
        source = json.loads((folder / 'source.json').read_text(encoding='utf-8'))
        if content_hash(original) != source['original_sha256']:
            raise ValueError('Original differs from the selected public sample: ' + name)
        context = Context.from_dict(json.loads((folder / 'context.json').read_text(encoding='utf-8')))
        result = {'case': name, 'source_id': source['id'], 'original_characters': len(original),
                  'lint_original': lint_text(original, context), 'candidates': {}}
        for method in ('brief', 'previous-skill', 'updated-skill', 'edited'):
            candidate = (folder / (method + '.md')).read_text(encoding='utf-8')
            result['candidates'][method] = {
                'characters': len(candidate),
                'verifier': verify_edit(original, candidate, context),
                'lint': lint_text(candidate, context),
            }
        final = (folder / 'edited.md').read_text(encoding='utf-8')
        comparison = difflib.HtmlDiff(wrapcolumn=48).make_file(
            original.splitlines(), final.splitlines(),
            fromdesc='Original / 完整原文', todesc='Revised example / 后续修订示范稿',
            context=False, charset='utf-8')
        (output / (name + '.html')).write_text(comparison, encoding='utf-8')
        cases.append(result)
    report = {'scope': 'Offline signals and source hashes only; no semantic pass or reader rating.',
              'raw_candidate_count': 6, 'post_observation_revisions': 2, 'cases': cases}
    (output / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.output)
    for case in report['cases']:
        print(case['case'], {m: c['verifier']['reasons'] for m, c in case['candidates'].items()})
