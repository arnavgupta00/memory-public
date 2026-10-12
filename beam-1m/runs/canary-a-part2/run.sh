#!/bin/zsh
# R9, part 2 of 2 (2026-10-11): the R9 configuration on the other 80 Canary A questions; with part 1 (the 20) it makes Canary A 100.
# Same frozen pipeline + A2 layer, same translator settings as R9 (notes none, router/search/targeted low, planner/answerer max,
# packager's discarded answer none). Session notes and their Voyage index are per history: seeded unchanged from R9
# (runs/a6/canary-a-screen20-hive-r9, all 4,037 sessions of the 5 histories). Every per-question stage runs fresh here.
# Usage (repository root): zsh runs/a6/canary-a-other80-hive-r9/hive/run.sh > runs/a6/canary-a-other80-hive-r9/hive/run.log 2>&1
set -u
ROOT=/Users/arnav/programming/projects/memory; CUR=$ROOT/src/agents/current; OUT=$ROOT/runs/a6/canary-a-other80-hive-r9; H=$OUT/hive; PORT=8787
SEED=$ROOT/runs/a6/canary-a-screen20-hive-r9; Q=$ROOT/runs/expert-review-20260927/analysis/canary_a_other80.json
say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
cp $CUR/src/pipeline/a7/hive-proxy.mjs $H/hive-proxy.mjs
(cd $ROOT && git rev-parse HEAD > $H/git-head.txt; shasum -a 256 $CUR/src/pipeline/a7/hive-proxy.mjs $CUR/src/pipeline/a6/FROZEN.json $Q > $H/sha256.txt)
(cd $CUR && node --env-file=../../../.env --import tsx src/pipeline/a6/run.mjs verify > $H/frozen-verify.txt 2>&1) || { say "frozen verify failed"; exit 1; }
pkill -f "src/pipeline/a7/hive-proxy.mjs"; sleep 1
(cd $CUR && HIVE_PROXY_PORT=$PORT HIVE_LEDGER=$H/ledger.jsonl HIVE_CAP_USD=30 HIVE_MAX_INFLIGHT=64 HIVE_RPS=4.8 HIVE_EFFORT_NOTES=none HIVE_EFFORT_LOW=low \
   nohup node --env-file=../../../.env src/pipeline/a7/hive-proxy.mjs >> $H/proxy.log 2>&1 &)
sleep 3; say "translator: $(curl -s http://127.0.0.1:$PORT/health)"
pipeline() { (cd $CUR && OPENAI_API_KEY=dummy-not-openai OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1 node --env-file=../../../.env --import tsx \
   src/pipeline/a6/run.mjs run --questions $Q --out $OUT --mode fresh --answer-layer A2 --cap 100 --no-judge "$@"); }
if [ ! -f $OUT/manifest.json ]; then   # first launch only; a relaunch (after TypeSafe ran out of credits, 02:02) resumes
pipeline --stop-after dataset >> $H/pipeline.log 2>&1 || { say "dataset failed"; exit 1; }
cp -R $SEED/annotations $OUT/annotations && cp -R $SEED/semantic-index $OUT/semantic-index
python3 -c "
import json; i=json.load(open('$OUT/annotations/_index.json')); d=json.load(open('$OUT/input/dataset.json'))
need=sum(len(c['session_ids']) for c in d['conversations'])
json.dump({'seeded_from':'runs/a6/canary-a-screen20-hive-r9','what':'stage 2 session notes + voyage index (per history, question-independent)','sessions_needed':need,'notes_seeded':len(i['sessions'])},open('$OUT/SEEDED-FROM.json','w'),indent=1)"
say "seeded: $(cat $OUT/SEEDED-FROM.json | tr -d '\n')"
fi
for attempt in 1 2 3 4; do
  pipeline --resume >> $H/pipeline.log 2>&1
  [ -f $OUT/predictions.jsonl ] && [ "$(wc -l < $OUT/predictions.jsonl)" -eq 80 ] && break
  say "run incomplete after attempt $attempt"; tail -3 $H/pipeline.log
  curl -s http://127.0.0.1:$PORT/health | grep -q '"blocked":"' && { say "translator blocked"; break; }
  sleep 20
done
pkill -f "src/pipeline/a7/hive-proxy.mjs"
[ -f $OUT/predictions.jsonl ] || { say "STOPPED: no predictions"; exit 1; }
(cd $ROOT && node --env-file=.env runs/final-all-deepseek-20261009/scripts/judge.mjs $OUT) && python3 $ROOT/runs/final-all-deepseek-20261009/scripts/score.py $OUT > /dev/null
python3 - <<'PY'
import json, statistics as st, collections
R = '/Users/arnav/programming/projects/memory/runs/a6'
rows = json.load(open(f'{R}/canary-a-screen20-hive-r9/judge/judge.json'))['rows'] + json.load(open(f'{R}/canary-a-other80-hive-r9/judge/judge.json'))['rows']
assert len({r['question_id'] for r in rows}) == 100
by = collections.defaultdict(list); [by[r['ability']].append(r['score']) for r in rows]
out = {'runs': ['runs/a6/canary-a-screen20-hive-r9 (20)', 'runs/a6/canary-a-other80-hive-r9 (80)'], 'questions': 100,
       'score_pinned': round(100 * st.mean(r['score'] for r in rows), 2), 'by_ability': {k: round(100 * st.mean(v), 2) for k, v in sorted(by.items())}}
json.dump(out, open(f'{R}/canary-a-other80-hive-r9/canary-a-100-combined.json', 'w'), indent=1)
print('CANARY A 100 (R9: 20 + 80):', json.dumps(out, indent=1))
PY
say "DONE"
