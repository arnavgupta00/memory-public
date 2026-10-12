#!/bin/zsh
# Canary B, R9 configuration, fully fresh. Usage (repository root): zsh runs/canary-b-r9-20261011/scripts/run.sh > runs/canary-b-r9-20261011/run.log 2>&1
set -u
ROOT=/Users/arnav/programming/projects/memory; CUR=$ROOT/src/agents/current; F=$ROOT/runs/canary-b-r9-20261011; OUT=$F/canary-b; PORT=8787
Q=$F/scripts/canary-b-questions.json
say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
status() { echo "$1" > $F/STATUS; say "STATUS: $1"; }
status "starting"
(cd $ROOT && git rev-parse HEAD > $F/evidence/git-head.txt && git status --short > $F/evidence/git-status.txt)
cp $CUR/src/pipeline/a7/hive-proxy.mjs $F/evidence/hive-proxy.mjs
(cd $CUR && shasum -a 256 src/pipeline/a7/hive-proxy.mjs src/pipeline/a6/FROZEN.json eval-slices/beam-1m/beam-1m-canary-b-certification-v1.json $Q > $F/evidence/sha256.txt)
(cd $CUR && node --env-file=../../../.env --import tsx src/pipeline/a6/run.mjs verify > $F/evidence/frozen-verify.txt 2>&1) || { status "STOPPED: frozen verify failed"; exit 1; }
pkill -f "src/pipeline/a7/hive-proxy.mjs"; sleep 1
(cd $CUR && HIVE_PROXY_PORT=$PORT HIVE_LEDGER=$F/evidence/hive-ledger.jsonl HIVE_CAP_USD=90 HIVE_MAX_INFLIGHT=100 HIVE_RPS=4.8 HIVE_EFFORT_NOTES=none HIVE_EFFORT_LOW=low \
   nohup node --env-file=../../../.env src/pipeline/a7/hive-proxy.mjs >> $F/evidence/hive-proxy.log 2>&1 &)
sleep 3; say "translator: $(curl -s http://127.0.0.1:$PORT/health)"
pipeline() { (cd $CUR && OPENAI_API_KEY=dummy-not-openai OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1 node --env-file=../../../.env --import tsx \
   src/pipeline/a6/run.mjs run --questions $Q --out $OUT --mode fresh --answer-layer A2 --cap 300 --jev-cap 20 --no-judge "$@"); }
status "pipeline running"
# first launch runs fresh; a relaunch (19:04 stop at the stage 8 spend guard) continues with --resume
if [ -f $OUT/manifest.json ]; then pipeline --resume >> $F/pipeline.log 2>&1; else pipeline >> $F/pipeline.log 2>&1; fi
for attempt in 1 2 3 4; do
  [ -f $OUT/predictions.jsonl ] && [ "$(wc -l < $OUT/predictions.jsonl)" -eq 260 ] && break
  if grep -q "TypeSafe HTTP 402" $F/pipeline.log; then status "PAUSED: TypeSafe credits ran out (HTTP 402); top up, then resume"; pkill -f "src/pipeline/a7/hive-proxy.mjs"; exit 2; fi
  if curl -s http://127.0.0.1:$PORT/health | grep -q '"blocked":"'; then status "PAUSED: Hive blocked (spend cap or 405)"; exit 2; fi
  say "incomplete; resume $attempt"; tail -3 $F/pipeline.log; sleep 30
  pipeline --resume >> $F/pipeline.log 2>&1
done
pkill -f "src/pipeline/a7/hive-proxy.mjs"
[ -f $OUT/predictions.jsonl ] && [ "$(wc -l < $OUT/predictions.jsonl)" -eq 260 ] || { status "STOPPED: not all 260 answered ($(wc -l < $OUT/predictions.jsonl 2>/dev/null))"; exit 1; }
status "judging"
(cd $ROOT && node --env-file=.env runs/final-all-deepseek-20261009/scripts/judge.mjs $OUT) || { status "STOPPED: judge error"; exit 1; }
python3 $ROOT/runs/final-all-deepseek-20261009/scripts/score.py $OUT > $F/score-official.txt
python3 $F/scripts/secondary.py > $F/score-secondary.txt
cat $F/score-official.txt | head -60; cat $F/score-secondary.txt
status "DONE"
