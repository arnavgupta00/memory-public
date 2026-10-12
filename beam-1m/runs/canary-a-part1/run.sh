#!/bin/zsh
# R9 (2026-10-11): the frozen A6 pipeline + A2 layer, fully fresh, on the fixed 20-question Canary A screen, every GPT call on
# DeepSeek V4.1 Flash (Hive) through the translator, with per-stage reasoning:
#   2a session notes (pipeline asks gpt-5.4-nano, no reasoning)        -> reasoning_effort none   (HIVE_EFFORT_NOTES)
#   5 router, 6 search planning, 9 targeted plans (pipeline asks low)  -> reasoning_effort low    (HIVE_EFFORT_LOW)
#   11 planner + answerer (pipeline asks high)                         -> reasoning_effort max    (as R6-R8)
#   10a packager's discarded answer                                    -> none                    (as R6-R8)
# Voyage, JEV and the official judge unchanged; the judge runs on real OpenAI afterwards.
# Usage (repository root): zsh runs/a6/canary-a-screen20-hive-r9/hive/run.sh > runs/a6/canary-a-screen20-hive-r9/hive/run.log 2>&1
set -u
ROOT=/Users/arnav/programming/projects/memory; CUR=$ROOT/src/agents/current; OUT=$ROOT/runs/a6/canary-a-screen20-hive-r9; H=$OUT/hive; PORT=8787
Q=$ROOT/runs/expert-review-20260927/analysis/haiku_screen20_canary_a.json
say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
cp $CUR/src/pipeline/a7/hive-proxy.mjs $H/hive-proxy.mjs
(cd $ROOT && git rev-parse HEAD > $H/git-head.txt; shasum -a 256 $CUR/src/pipeline/a7/hive-proxy.mjs $CUR/src/pipeline/a6/FROZEN.json $Q > $H/sha256.txt)
(cd $CUR && node --env-file=../../../.env --import tsx src/pipeline/a6/run.mjs verify > $H/frozen-verify.txt 2>&1) || { say "frozen verify failed"; exit 1; }
pkill -f "src/pipeline/a7/hive-proxy.mjs"; sleep 1
(cd $CUR && HIVE_PROXY_PORT=$PORT HIVE_LEDGER=$H/ledger.jsonl HIVE_CAP_USD=20 HIVE_MAX_INFLIGHT=64 HIVE_RPS=4.8 HIVE_EFFORT_NOTES=none HIVE_EFFORT_LOW=low \
   nohup node --env-file=../../../.env src/pipeline/a7/hive-proxy.mjs >> $H/proxy.log 2>&1 &)
sleep 3; say "translator: $(curl -s http://127.0.0.1:$PORT/health)"
pipeline() { (cd $CUR && OPENAI_API_KEY=dummy-not-openai OPENAI_BASE_URL=http://127.0.0.1:$PORT/v1 node --env-file=../../../.env --import tsx \
   src/pipeline/a6/run.mjs run --questions $Q --out $OUT --mode fresh --answer-layer A2 --cap 100 --no-judge "$@"); }
pipeline >> $H/pipeline.log 2>&1
for attempt in 1 2 3; do
  [ -f $OUT/predictions.jsonl ] && [ "$(wc -l < $OUT/predictions.jsonl)" -eq 20 ] && break
  say "run incomplete; resume $attempt"; tail -3 $H/pipeline.log
  curl -s http://127.0.0.1:$PORT/health | grep -q '"blocked":"' && { say "translator blocked"; break; }
  sleep 20; pipeline --resume >> $H/pipeline.log 2>&1
done
pkill -f "src/pipeline/a7/hive-proxy.mjs"
[ -f $OUT/predictions.jsonl ] || { say "STOPPED: no predictions"; exit 1; }
(cd $ROOT && node --env-file=.env runs/final-all-deepseek-20261009/scripts/judge.mjs $OUT) && python3 $ROOT/runs/final-all-deepseek-20261009/scripts/score.py $OUT | head -45
say "DONE"
