#!/bin/zsh
# Remaining 340 questions, frozen R9 configuration, fully fresh. Usage (repository root): zsh runs/final-700-r9-20261012/scripts/run.sh >> runs/final-700-r9-20261012/run.log 2>&1
set -u
ROOT=/Users/arnav/programming/projects/memory; CUR=$ROOT/src/agents/current; F=$ROOT/runs/final-700-r9-20261012; OUT=$F/remaining-340; PORT=8787
Q=$F/scripts/questions.json
say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
status() { echo "$1" > $F/STATUS; say "STATUS: $1"; }
status "starting"
(cd $ROOT && git rev-parse HEAD > $F/evidence/git-head.txt && git status --short > $F/evidence/git-status.txt && git diff > $F/evidence/git-diff-working-tree.patch)
cp $CUR/src/pipeline/a7/hive-proxy.mjs $F/evidence/hive-proxy.mjs; cp $CUR/src/pipeline/a6/FROZEN.json $F/evidence/FROZEN.json
(cd $CUR && shasum -a 256 src/pipeline/a7/hive-proxy.mjs src/pipeline/a6/FROZEN.json src/pipeline/a6/run.mjs src/pipeline/a6/stages/s07_fusion_jev.mjs src/jev/recursiveArtifacts.mjs $Q > $F/evidence/sha256.txt)
(cd $CUR && node --env-file=../../../.env --import tsx src/pipeline/a6/run.mjs verify > $F/evidence/frozen-verify.txt 2>&1) || { status "STOPPED: frozen verify failed"; exit 1; }
pkill -f "src/pipeline/a7/hive-proxy.mjs"; sleep 1
(cd $CUR && HIVE_PROXY_PORT=$PORT HIVE_LEDGER=$F/evidence/hive-ledger.jsonl HIVE_CAP_USD=120 HIVE_MAX_INFLIGHT=100 HIVE_RPS=4.8 HIVE_EFFORT_NOTES=none HIVE_EFFORT_LOW=low \
   nohup node --env-file=../../../.env src/pipeline/a7/hive-proxy.mjs >> $F/evidence/hive-proxy.log 2>&1 &)
sleep 3; say "translator: $(curl -s http://127.0.0.1:$PORT/health)"
pipeline() { (cd $CUR && OPENAI_API_KEY=dummy-not-openai OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1 node --env-file=../../../.env --import tsx \
   src/pipeline/a6/run.mjs run --questions $Q --out $OUT --mode fresh --answer-layer A2 --cap 400 --jev-cap 20 --no-judge "$@"); }
status "pipeline running"
if [ -f $OUT/manifest.json ]; then pipeline --resume >> $F/pipeline.log 2>&1; else pipeline >> $F/pipeline.log 2>&1; fi
for attempt in 1 2 3 4; do
  [ -f $OUT/predictions.jsonl ] && [ "$(wc -l < $OUT/predictions.jsonl)" -eq 340 ] && break
  if grep -q "TypeSafe HTTP 402" $F/pipeline.log; then status "PAUSED: TypeSafe credits ran out (HTTP 402)"; pkill -f "src/pipeline/a7/hive-proxy.mjs"; exit 2; fi
  if curl -s http://127.0.0.1:$PORT/health | grep -q '"blocked":"'; then status "PAUSED: Hive blocked (spend cap or 405)"; exit 2; fi
  say "incomplete; resume $attempt"; tail -3 $F/pipeline.log; sleep 30
  pipeline --resume >> $F/pipeline.log 2>&1
done
pkill -f "src/pipeline/a7/hive-proxy.mjs"
[ -f $OUT/predictions.jsonl ] && [ "$(wc -l < $OUT/predictions.jsonl)" -eq 340 ] || { status "STOPPED: not all 340 answered"; exit 1; }
status "judging"
(cd $ROOT && node --env-file=.env runs/final-all-deepseek-20261009/scripts/judge.mjs $OUT) || { status "STOPPED: judge error"; exit 1; }
python3 $ROOT/runs/final-all-deepseek-20261009/scripts/score.py $OUT > $F/score-remaining-340.txt
python3 $F/scripts/final700.py > $F/FINAL-700.txt
cat $F/FINAL-700.txt
status "DONE"
