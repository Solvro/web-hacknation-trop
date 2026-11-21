#!/bin/bash
# Serve an OpenAI-compatible vLLM endpoint on one H100 (lem-gpu).
# Usage (on ui.wcss.pl):
#   sbatch --export=ALL,MODEL=Qwen/Qwen2.5-VL-7B-Instruct,PORT=8000 ~/redpill/serve_vllm.sbatch
# The job writes   $RP_HOME/endpoint_<jobid>.txt   with "host:port model".
# IDLE WATCHDOG: the job cancels itself after IDLE_MIN minutes without requests (default 20) -> no idle GPU hours.
#SBATCH --job-name=rp-vllm
# account: pass  sbatch --account=<your grant>  (the default grant is the wrong one)
#SBATCH --partition=lem-gpu-short
#SBATCH --gres=gpu:hopper:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=03:00:00
#SBATCH --output=logs/%x-%j.out

set -euo pipefail
source ~/redpill/env.sh   # defines RP_HOME, VLLM_ENV, HF_HOME (site-specific, not in the repo)
MODEL=${MODEL:-Qwen/Qwen2.5-VL-7B-Instruct}
PORT=${PORT:-8000}
IDLE_MIN=${IDLE_MIN:-20}
MAXLEN=${MAXLEN:-16384}
EXTRA=${EXTRA:-}
HOST=$(hostname)
echo "$HOST:$PORT $MODEL" > $RP_HOME/endpoint_${SLURM_JOB_ID}.txt
echo "[rp] serving $MODEL on $HOST:$PORT (job $SLURM_JOB_ID)"

source $VLLM_ENV/bin/activate
vllm serve "$MODEL" --host 0.0.0.0 --port $PORT --dtype bfloat16 --max-model-len $MAXLEN \
  --gpu-memory-utilization 0.90 --limit-mm-per-prompt '{"image": 4}' --served-model-name rp-model $EXTRA &
VPID=$!

# idle watchdog: vLLM prometheus counter of finished requests; cancel job if it does not move for IDLE_MIN
last=-1; idle=0
sleep 120
while kill -0 $VPID 2>/dev/null; do
  cur=$(curl -s localhost:$PORT/metrics | awk '/^vllm:request_success_total/ {s+=$2} END {print s+0}')
  run=$(curl -s localhost:$PORT/metrics | awk '/^vllm:num_requests_running/ {s+=$2} END {print s+0}')
  if [[ "$cur" == "$last" && "${run%.*}" == "0" ]]; then idle=$((idle+1)); else idle=0; fi
  last=$cur
  if (( idle >= IDLE_MIN )); then echo "[rp] idle ${IDLE_MIN}m -> scancel"; rm -f $RP_HOME/endpoint_${SLURM_JOB_ID}.txt; scancel $SLURM_JOB_ID; fi
  sleep 60
done
rm -f $RP_HOME/endpoint_${SLURM_JOB_ID}.txt
