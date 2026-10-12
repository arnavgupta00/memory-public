"""Level 4: re-score the 700 published answers with Vectorize's Agent Memory Benchmark (AMB) scorer, the method behind
Hindsight's 73.9 and HydraDB's 82 on BEAM 1M.

The scorer files are not redistributed here (the AMB repository has no license). This script downloads them from the
pinned commit, checks their sha256, and runs AMB's own functions `score_result` and `_rubric_item_score` unchanged. Those
functions call a Gemini judge with Mem0's nugget prompt, scoring each rubric item 0/0.5/1; the question score is the mean.

Needs network, GEMINI_API_KEY, and the BEAM source (clone https://github.com/mohammadtavakoli78/BEAM at 3e12035).
Usage (package root): python3 verify/rescore_vectorize.py --beam-root beam-official/chats/1M [--model gemini-3.5-flash-lite]
Expect about 78.2 with gemini-3.5-flash-lite, plus or minus about one point: Gemini is not fully reproducible at temperature 0.
"""
import ast, hashlib, json, os, pathlib, sys, time, types, urllib.request, urllib.error, logging, statistics as st
from concurrent.futures import ThreadPoolExecutor
PKG = pathlib.Path(__file__).resolve().parents[1]
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
BEAM = pathlib.Path(arg('--beam-root', 'beam-official/chats/1M')); MODEL = arg('--model', 'gemini-3.5-flash-lite')
COMMIT = '20751fa03d8795200a246cf4fc904605cf4a905a'
FILE, FILE_SHA = 'src/memory_bench/dataset/beam.py', '7202cb1e82377d5940f7a3990a9652ae64457fa90bace7b11d84fa92c851e80d'
src = urllib.request.urlopen(f'https://raw.githubusercontent.com/vectorize-io/agent-memory-benchmark/{COMMIT}/{FILE}', timeout=60).read()
assert hashlib.sha256(src).hexdigest() == FILE_SHA, 'AMB scorer file does not match the pinned hash'
KEY = os.environ.get('GEMINI_API_KEY') or sys.exit('set GEMINI_API_KEY')
URL = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}'
class Schema:
    def __init__(self, properties, required): self.properties, self.required = properties, required
T = {'number': 'NUMBER', 'string': 'STRING', 'boolean': 'BOOLEAN'}
class Gemini:   # same configuration as AMB's GeminiLLM.generate: JSON output, response schema, temperature 0, no seed
    def generate(self, prompt, schema):
        cfg = {'responseMimeType': 'application/json', 'temperature': 0.0, 'responseSchema': {'type': 'OBJECT', 'required': schema.required,
               'properties': {k: {'type': T[v['type']], **({'description': v['description']} if 'description' in v else {})} for k, v in schema.properties.items()}}}
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
NS = {'Schema': Schema, 'LLM': object, 'QueryResult': object, 'logger': logging.getLogger('amb')}
for node in ast.parse(src.decode()).body:
    if isinstance(node, ast.ClassDef):
        for f in node.body:
            if isinstance(f, ast.FunctionDef) and f.name in ('_rubric_item_score', 'score_result', '_extract_meta_for_category', '_extract_answer'):
                f.decorator_list = []; exec(compile(ast.Module([f], []), 'amb', 'exec'), NS)
    if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == '_ANSWER_FIELDS' for t in node.targets): exec(compile(ast.Module([node], []), 'amb', 'exec'), NS)
class Stub: _rubric_item_score = staticmethod(NS['_rubric_item_score'])
class Tracked:   # AMB turns a failed judge call into 0.0; record failures so they are retried, never scored as 0
    def __init__(self): self.failed = 0
    def generate(self, p, s):
        try: return Gemini().generate(p, s)
        except Exception: self.failed += 1; raise
answers = [json.loads(l) for l in (PKG / 'data/answers/answers.jsonl').read_text().splitlines()]
def run(r):
    _, c, cat, i = r['question_id'].split('/'); obj = json.loads((BEAM / str(int(c[5:])) / 'probing_questions/probing_questions.json').read_text())[cat][int(i) - 1]
    gold = NS['_extract_answer'](obj)
    res = types.SimpleNamespace(query=obj['question'], answer=r['answer'], gold_answers=[gold] if gold else [], query_id=r['question_id'],
                                meta={'question_category': cat, **NS['_extract_meta_for_category'](cat, obj)})
    for _ in range(4):
        t = Tracked(); s = NS['score_result'](Stub(), res, t)
        if not t.failed: return r['question_id'], s
        time.sleep(10)
    return r['question_id'], None
with ThreadPoolExecutor(32) as ex: out = dict(ex.map(run, answers))
ok = {q: s for q, s in out.items() if s is not None}
print(f'scored {len(ok)}/700 with {MODEL}; Vectorize rubric average = {100 * st.mean(ok.values()):.2f}')
claim = json.loads((PKG / 'claims.json').read_text())['results']['ALL 700']['vectorize_rubric_average']; print(f'package claim: {claim}')
