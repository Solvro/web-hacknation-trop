#!/bin/bash
# Batch embeddings (approach b). CPU partition by default (bem2-cpu-short usually has idle nodes -> starts at once);
# for >10k incidents switch to GPU:  sbatch -p lem-gpu-short --gres=gpu:hopper:1 embed_batch.sbatch <corpus>
# Usage: sbatch --export=ALL,CORPUS=sample_v1 ~/redpill/embed_batch.sbatch
#SBATCH --job-name=rp-embed
#SBATCH --account=hpc-dawlin1140-1773687823
#SBATCH --partition=bem2-cpu-short
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=/lustre/pd03/hpc-dawlin1140-1773687823/redpill/logs/%x-%j.out
set -euo pipefail
source ~/redpill/env.sh
CORPUS=${CORPUS:-sample_v1}
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK HF_HUB_OFFLINE=1
D=$RP_HOME/data/$CORPUS
$ML_ENV/bin/python ~/redpill/embed_batch.py $D/texts.jsonl $D/shots $RP_HOME/out/emb_$CORPUS --models ${MODELS:-mmlw,bgem3,qwen3emb} --siglip
