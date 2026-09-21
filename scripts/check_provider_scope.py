"""Validate the currently supported provider scope without model calls."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from editorial_guard.dataset import PROVIDERS
from editorial_guard.providers import ENDPOINTS,KEY_ENV
from editorial_guard.supplemental import independent_judges
expected={'codex','deepseek','glm'}
assert set(PROVIDERS)==expected
assert set(ENDPOINTS)==set(KEY_ENV)==expected-{'codex'}
for name in ('config.example.json','config.coding-plan.example.json'):
 assert set(json.loads((ROOT/name).read_text(encoding='utf-8'))['providers'])==expected
for author in expected:
 assert set(independent_judges(author))==expected-{author}
assert set(json.loads((ROOT/'evals/provider-scope.json').read_text())['providers'])==expected
print(json.dumps({'status':'pass','providers':sorted(expected),'new_model_calls':0}))
