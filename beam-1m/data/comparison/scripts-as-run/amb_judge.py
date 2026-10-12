"""Score our saved BEAM-1M answers with Vectorize's Agent Memory Benchmark (AMB) judge, the scorer behind Hindsight's
73.9% and HydraDB's 82% on BEAM 1M (12 Oct 2026).

Fidelity:
- The judge prompts are AMB's own. `get_judge_prompt_fn`, `_extract_meta_for_category`, `_extract_answer` and
  `_ANSWER_FIELDS` are executed verbatim from `amb_beam_reference.py` (vectorize-io/agent-memory-benchmark,
  src/memory_bench/dataset/beam.py, fetched 12 Oct 2026). They only build strings.
- Judge settings are AMB's (`amb_gemini_reference.py`, `GeminiLLM.generate`): gemini-3.5-flash (AMB's
  `default_judge_llm`), JSON output with the schema {correct: boolean, reason: string}, temperature 0, no seed (AMB's
  default unless OMB_SEED is set).
- Called through the Gemini REST API, which takes the same config as the SDK.
- Metric: accuracy = questions judged correct / questions, overall and per category, which is AMB's headline.

What differs from AMB's own runs:
- The answers are our system's own planner/answerer answers (R9 configuration), not AMB's fixed answer prompt over
  retrieved memories. This is a whole-system comparison.
- 360 questions (Canary A + Canary B), not all 700.

Usage: runs/.beam-official-judge-venv/bin/python runs/amb-judge-20261012/amb_judge.py [--limit N]"""
import ast, json, os, sys, time, pathlib, urllib.request, urllib.error, collections
from concurrent.futures import ThreadPoolExecutor
ROOT = pathlib.Path('/Users/arnav/programming/projects/memory'); HERE = ROOT / 'runs/amb-judge-20261012'
ref = (HERE / 'amb_beam_reference.py').read_text(); tree = ast.parse(ref); NS = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == '_ANSWER_FIELDS' for t in node.targets): exec(compile(ast.Module([node], []), 'amb', 'exec'), NS)
    if isinstance(node, ast.ClassDef):
        for f in node.body:
            if isinstance(f, ast.FunctionDef) and f.name in ('get_judge_prompt_fn', '_extract_meta_for_category', '_extract_answer'):
                f.decorator_list = []
                exec(compile(ast.Module([f], []), 'amb', 'exec'), NS)
get_judge_prompt_fn, extract_meta, extract_answer = NS['get_judge_prompt_fn'], NS['_extract_meta_for_category'], NS['_extract_answer']
KEY = next(l.split('=', 1)[1].strip().strip('"').strip("'") for l in open(ROOT / '.env') if l.startswith('GEMINI_API_KEY='))
MODEL = os.environ.get('OMB_JUDGE_MODEL') or 'gemini-3.5-flash'
URL = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}'
CONFIG = {'responseMimeType': 'application/json', 'temperature': 0.0,
          'responseSchema': {'type': 'OBJECT', 'properties': {'correct': {'type': 'BOOLEAN'}, 'reason': {'type': 'STRING'}}, 'required': ['correct', 'reason']}}
def gemini(prompt):
    body = json.dumps({'contents': [{'role': 'user', 'parts': [{'text': prompt}]}], 'generationConfig': CONFIG}).encode()
    for attempt in range(8):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json'}), timeout=300) as r:
                d = json.loads(r.read()); t = ''.join(p.get('text', '') for p in d['candidates'][0]['content']['parts'] if not p.get('thought'))
                return json.loads(t), d.get('usageMetadata', {})
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504): time.sleep(min(60, 2 ** attempt)); continue
            raise RuntimeError(f'HTTP {e.code}: {e.read()[:300]}')
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError): time.sleep(min(60, 2 ** attempt))
    raise RuntimeError('Gemini failed after retries')
SETS = {'canary-a': ('runs/a6/canary-a-other80-hive-r9/source/chats/1M', [('runs/a6/canary-a-screen20-hive-r9', 'answer'), ('runs/a6/canary-a-other80-hive-r9', 'answer')]),
        'canary-b': ('runs/canary-b-r9-20261011/canary-b/source/chats/1M', [('runs/canary-b-r9-20261011/canary-b', 'answer')])}
TAG = ('-' + os.environ['AMB_TAG']) if os.environ.get('AMB_TAG') else ''
if os.environ.get('AMB_SETS'): SETS = {k: tuple(v) for k, v in json.loads(os.environ['AMB_SETS']).items()}   # score other runs
jobs = []
for name, (src, runs) in SETS.items():
    for run, step in runs:
        for f in sorted(os.listdir(ROOT / run / step / 'responses')):
            q = f[:-5].replace('__', '/'); _, c, cat, i = q.split('/'); n = int(c.split('-')[1])
            obj = json.load(open(ROOT / src / str(n) / 'probing_questions/probing_questions.json'))[cat][int(i) - 1]
            answer = json.load(open(ROOT / run / step / 'responses' / f))['output_text']
            meta = {'question_category': cat, **extract_meta(cat, obj)}; gold = extract_answer(obj)
            prompt = get_judge_prompt_fn(None, cat, meta)(obj['question'], [gold] if gold else [], answer)
            jobs.append((name, q, cat, prompt))
if '--limit' in sys.argv: jobs = jobs[:int(sys.argv[sys.argv.index('--limit') + 1])]
def run(j):
    name, q, cat, prompt = j
    try: v, u = gemini(prompt); return {'set': name, 'question_id': q, 'category': cat, 'correct': bool(v['correct']), 'reason': v['reason'], 'usage': u}
    except Exception as e: return {'set': name, 'question_id': q, 'category': cat, 'error': str(e)[:300]}
t0 = time.time()
with ThreadPoolExecutor(64) as ex: out = list(ex.map(run, jobs))
(HERE / f"results{TAG}.json").write_text(json.dumps({'judge_model': MODEL, 'config': CONFIG, 'n': len(out), 'rows': out}, indent=1))
ok = [r for r in out if 'error' not in r]; print(f'{len(out)} judged in {time.time() - t0:.0f}s; errors {len(out) - len(ok)}; model {MODEL}')
tin = sum(r['usage'].get('promptTokenCount', 0) for r in ok); tout = sum(r['usage'].get('candidatesTokenCount', 0) + r['usage'].get('thoughtsTokenCount', 0) for r in ok)
print(f'tokens in {tin:,}, out+thinking {tout:,}')
def acc(rs): return f'{100 * sum(r["correct"] for r in rs) / len(rs):5.1f}% ({sum(r["correct"] for r in rs)}/{len(rs)})' if rs else '-'
for s in ['canary-a', 'canary-b', None]:
    rs = [r for r in ok if s is None or r['set'] == s]; print(f"{s or 'combined':10} accuracy {acc(rs)}")
by = collections.defaultdict(list)
for r in ok: by[r['category']].append(r)
for c, rs in sorted(by.items()): print(f'   {c:26} {acc(rs)}')
