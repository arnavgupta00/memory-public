"""AMB's continuous BEAM score, the number Hindsight publishes (73.9% at 1M) and HydraDB compares against (82%).

`score_result` and `_rubric_item_score` are executed verbatim from `amb_beam_reference.py` (vectorize-io/agent-memory-
benchmark, src/memory_bench/dataset/beam.py). For every rubric item, Mem0's nugget-judge prompt scores 0/0.5/1, with
event-ordering items framed as "should mention". The question score is the mean over its items, and the headline is the
mean over questions.

The judge is called like AMB's GeminiLLM.generate: JSON output with the schema {score: number, reason: string},
temperature 0, no seed.
- Primary judge: gemini-2.5-flash-lite, the `judge_llm` in Hindsight's published BEAM-1M results file.
- Check: gemini-3.5-flash, AMB's current default.

The answers are our system's own (R9 configuration) for Canary A (100) and Canary B (260).
Usage: runs/.beam-official-judge-venv/bin/python runs/amb-judge-20261012/amb_score.py <judge-model>"""
import ast, json, os, sys, time, pathlib, urllib.request, urllib.error, collections, types, logging
from concurrent.futures import ThreadPoolExecutor
ROOT = pathlib.Path('/Users/arnav/programming/projects/memory'); HERE = ROOT / 'runs/amb-judge-20261012'
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'gemini-2.5-flash-lite'
KEY = next(l.split('=', 1)[1].strip().strip('"').strip("'") for l in open(ROOT / '.env') if l.startswith('GEMINI_API_KEY='))
URL = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}'
class Schema:   # stand-in for memory_bench.llm.base.Schema (properties + required)
    def __init__(self, properties, required): self.properties, self.required = properties, required
GT = {'number': 'NUMBER', 'string': 'STRING', 'boolean': 'BOOLEAN'}
class GeminiREST:   # same config as AMB GeminiLLM.generate: JSON mime type, response schema, temperature 0, no seed
    def generate(self, prompt, schema):
        cfg = {'responseMimeType': 'application/json', 'temperature': 0.0, 'responseSchema': {'type': 'OBJECT', 'required': schema.required,
               'properties': {k: {'type': GT[v['type']], **({'description': v['description']} if 'description' in v else {})} for k, v in schema.properties.items()}}}
        body = json.dumps({'contents': [{'role': 'user', 'parts': [{'text': prompt}]}], 'generationConfig': cfg}).encode()
        for attempt in range(8):
            try:
                with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json'}), timeout=300) as r:
                    d = json.loads(r.read()); return json.loads(''.join(p.get('text', '') for p in d['candidates'][0]['content']['parts'] if not p.get('thought')))
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504): time.sleep(min(60, 2 ** attempt)); continue
                raise
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError): time.sleep(min(60, 2 ** attempt))
        raise RuntimeError('Gemini failed after retries')
ref = (HERE / 'amb_beam_reference.py').read_text(); NS = {'Schema': Schema, 'LLM': object, 'QueryResult': object, 'logger': logging.getLogger('amb')}
for node in ast.parse(ref).body:
    if isinstance(node, ast.ClassDef):
        for f in node.body:
            if isinstance(f, ast.FunctionDef) and f.name in ('_rubric_item_score', 'score_result', '_extract_meta_for_category', '_extract_answer'):
                f.decorator_list = []; exec(compile(ast.Module([f], []), 'amb', 'exec'), NS)
    if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == '_ANSWER_FIELDS' for t in node.targets): exec(compile(ast.Module([node], []), 'amb', 'exec'), NS)
class BeamStub:   # score_result calls self._rubric_item_score(...)
    _rubric_item_score = staticmethod(NS['_rubric_item_score'])
llm = GeminiREST()
SETS = {'canary-a': ('runs/a6/canary-a-other80-hive-r9/source/chats/1M', ['runs/a6/canary-a-screen20-hive-r9', 'runs/a6/canary-a-other80-hive-r9']),
        'canary-b': ('runs/canary-b-r9-20261011/canary-b/source/chats/1M', ['runs/canary-b-r9-20261011/canary-b'])}
TAG = ('-' + os.environ['AMB_TAG']) if os.environ.get('AMB_TAG') else ''
if os.environ.get('AMB_SETS'): SETS = {k: tuple(v) for k, v in json.loads(os.environ['AMB_SETS']).items()}   # score other runs
jobs = []
for name, (src, runs) in SETS.items():
    for run in runs:
        for f in sorted(os.listdir(ROOT / run / 'answer/responses')):
            q = f[:-5].replace('__', '/'); _, c, cat, i = q.split('/'); n = int(c.split('-')[1])
            obj = json.load(open(ROOT / src / str(n) / 'probing_questions/probing_questions.json'))[cat][int(i) - 1]
            gold = NS['_extract_answer'](obj)
            result = types.SimpleNamespace(query=obj['question'], answer=json.load(open(ROOT / run / 'answer/responses' / f))['output_text'],
                                           gold_answers=[gold] if gold else [], query_id=q, meta={'question_category': cat, **NS['_extract_meta_for_category'](cat, obj)})
            jobs.append((name, q, cat, result))
class Tracked:   # AMB's _rubric_item_score turns any failed call into 0.0; record failures so they are retried, never scored as 0
    def __init__(self): self.failed = []
    def generate(self, prompt, schema):
        try: return llm.generate(prompt, schema)
        except Exception as e: self.failed.append(str(e)[:200]); raise
def run(j):
    name, q, cat, result = j
    t = Tracked()
    try: score = NS['score_result'](BeamStub(), result, t)
    except Exception as e: return {'set': name, 'question_id': q, 'category': cat, 'error': str(e)[:300]}
    if t.failed: return {'set': name, 'question_id': q, 'category': cat, 'error': f'{len(t.failed)} judge call(s) failed: {t.failed[0]}'}
    return {'set': name, 'question_id': q, 'category': cat, 'score': score}
t0 = time.time()
with ThreadPoolExecutor(48) as ex: out = list(ex.map(run, jobs))
for attempt in range(3):   # retry questions whose judge calls failed
    bad = [i for i, r in enumerate(out) if 'error' in r]
    if not bad: break
    print(f'retrying {len(bad)} question(s) with failed judge calls'); time.sleep(10)
    with ThreadPoolExecutor(16) as ex: redo = list(ex.map(run, [jobs[i] for i in bad]))
    for i, r in zip(bad, redo): out[i] = r
(HERE / f'score-{MODEL}{TAG}.json').write_text(json.dumps({'judge_model': MODEL, 'n': len(out), 'rows': out}, indent=1))
ok = [r for r in out if 'error' not in r]
print(f'{len(out)} questions scored in {time.time() - t0:.0f}s with {MODEL}; errors {len(out) - len(ok)}')
m = lambda rs: f'{100 * sum(r["score"] for r in rs) / len(rs):5.1f}' if rs else '  -'
for s in ['canary-a', 'canary-b', None]: print(f"{s or 'combined':10} AMB score {m([r for r in ok if s is None or r['set'] == s])}")
by = collections.defaultdict(list)
for r in ok: by[r['category']].append(r)
for c, rs in sorted(by.items()): print(f'   {c:26} {m(rs)}  (n={len(rs)})')
