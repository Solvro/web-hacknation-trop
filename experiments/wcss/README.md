# WCSS for RED PILL — access, grant, jobs, tunnel

Status 2026-11-21 (experiments session). Everything below was tested unless marked *untested*.

## 1. Grant ("PBR") and hardware

| Item | Value |
|---|---|
| SLURM account (PBR = "Projekt badawczo rozwojowy w inżynierii oprogramowania") | `hpc-dawlin1140-1773687823` |
| Balance at 13:00 | GPU 4024 / 9000 h used (~4976 h left) · CPU 27725 / 80000 h used |
| Project dir (Lustre, 9.8 TB quota) | `/lustre/pd03/hpc-dawlin1140-1773687823` (`$RP_PD`) — our stuff in `$RP_PD/redpill` |
| HF cache (shared with the other team session) | `$RP_PD/hf_cache/hub` |
| GPU partitions | `lem-gpu-short` (≤3 d), `lem-gpu-normal` (≤7 d), `lem-gpu-interactive` (≤6 h, 1 node `r18-15`) |
| GPU node | 4× H100 94 GB (`--gres=gpu:hopper:N`), 64 CPU, ~1 TB RAM, 7 TB local NVMe (`$TMPDIR`) |
| CPU partitions (usually idle → instant start) | `bem2-cpu-short` (≤3 d), `lem-cpu-short` |
| Check balance | `service-balance --service hpc-dawlin1140-1773687823` · `sacctmgr show assoc user=$USER` · `sinfo -s` · `gpu-occupation` |

Other accounts on this user (do **not** use): `hpc-dawlin1140-1769424956` (PRIORITY/DFG-NCN, default!), `hpc-danbor2008-1756464546` (Koło Solvro, 99% GPU used).
**Always pass `--account=hpc-dawlin1140-1773687823`** — the default account is a different grant.

## 2. Access — read this first

* **WCSS rate-limits new SSH connections per source IP.** ~6 quick logins got this PC's IP filtered (port 22 timeout
  for >30 min), then the home PC's IP. **3 failed password logins = 24 h account lock** → always `BatchMode=yes`.
* Windows OpenSSH here cannot multiplex. Use the **ControlMaster on the home PC** (`dawid-home-pc`, host alias `wcss`,
  `ControlPath ~/.ssh/cm-%r@%h-%p`, key `~/.ssh/id_ed25519`) — zero new WCSS logins per command:

```bash
ssh home 'ssh wcss bash -s' < script.sh                    # run a script on the login node
tar cf - -C local_dir . | ssh home 'ssh wcss "tar xf - -C /lustre/pd03/hpc-dawlin1140-1773687823/redpill/data/x"'   # upload
ssh home 'ssh wcss "cat /lustre/.../file"' > file           # download
```
* The login node has internet (HF downloads OK); compute nodes run with `HF_HUB_OFFLINE=1`.
* The login node has no `module`, no pip — use **uv** (`~/.local/bin/uv` 0.9.5, installed from the official GitHub
  release) with a standalone CPython 3.12: `uv venv -p 3.12 …`. Inside jobs, `source /usr/local/sbin/modules.sh;
  module load Python/3.12.3-GCCcore-13.3.0 CUDA/13.0.0` also works (that is how the other session builds vLLM).

## 3. Environments and files (`~/redpill`, `$RP_PD/redpill`)

| Path | What |
|---|---|
| `~/redpill/env.sh` | exports `RP_ACCOUNT`, `RP_PD`, `RP_HOME`, `HF_HOME`, `ML_ENV`, `VLLM_ENV` |
| `$RP_HOME/venv-ml` | uv venv: torch 2.15 + CUDA 13.2, sentence-transformers 6.3, transformers, lightgbm (built by `setup_ml.sh`) |
| `$RP_PD/hacknation/llm-stack/vllm.tar` | **vLLM stack built by the other session** (unpacked to `$TMPDIR` per job) — reuse, do not rebuild |
| `$RP_HOME/data/<corpus>/` | uploaded inputs (`texts.jsonl`, `shots/` → screenshots) — organizer data stays on WCSS/Lustre only |
| `$RP_HOME/out/` | outputs (`vlm_<corpus>.jsonl`, `emb_<corpus>/`, `adj_*.jsonl`) |

Models already in the PBR HF cache (complete): Qwen3.6-35B-A3B, Qwen3.8-27B(+FP8), Qwen3.5-9B/4B, gemma-4-31B-it,
PLLuM-12B-instruct-2512, PLLuM-4B, Bielik-11B-v3.0-FP8, Bielik-One-4B/11B-r1, PaddleOCR-VL, GLM-OCR,
Qwen3-Embedding-0.6B, + ours: mmlw-roberta-base, bge-m3, siglip-base-patch16-224. (Bielik-11B-v3.1 is gated/empty.)

## 4. Jobs

| Script | Partition | Purpose | Measured |
|---|---|---|---|
| `serve_vllm.sbatch` | lem-gpu-short, 1×H100, 3 h | one OpenAI-compatible vLLM server; **idle watchdog cancels the job after `IDLE_MIN`=20 min without requests**; writes `$RP_HOME/endpoint_<jobid>.txt` | *untested — we reused the shared server instead* |
| `embed_batch.sbatch` + `embed_batch.py` | bem2-cpu-short, 32 CPU, 1 h | mmlw / bge-m3 / Qwen3-Embedding on landing + ad text; SigLIP on screenshot + creative crop | sample_v1: see RESULTS.md |
| `vlm_extract.py` | inside a serving allocation (`srun --jobid=<J> --overlap`) | structured ad-field extraction from screenshots (VLM JSON / OCR-VLM text) | 14 shots × 4 models, 0.5–10 s/shot unbatched |
| `adjudicate.py` | inside a serving allocation | LLM adjudicator over feature dossiers (+ optional raw excerpts) | 105 pairs, 8 workers |

**Shared multi-model server (preferred):** another session runs `~/hacknation-serve/serve.sbatch` (job name
`hn-serve`, 4×H100, models listed in `~/hacknation-serve/models.conf`: qwen3.6-35b-a3b, qwen3.8-27b-fp8, paddleocr-vl,
glm-ocr, pllum-12b, bielik-one-4b-r1, bielik-11b-v3.0-fp8, pllum-4b, qwen3-embedding) and an interactive one
(`hn-int`, r18-15: qwen38-27b-fp8:8002, qwen35-9b:8003, paddleocr-vl:8010, glm-ocr:8011). Endpoints are listed in
`$RP_PD/hacknation/endpoint.txt` / `$RP_PD/hacknation/serve/endpoint.txt`, API key in `$RP_PD/hacknation/.api_key`.
Servers bind to the node's localhost → call them from inside the allocation:

```bash
srun --jobid=<JOBID> --overlap -n1 -c2 --mem=2G python3 ~/redpill/vlm_extract.py <img_dir> <out.jsonl> qwen38-27b-fp8:8002
```
All our GPU work today ran this way → **0 extra GPU-hours** charged for our experiments.

## 5. Tunnel to vLLM from this PC (*for a server bound to 0.0.0.0, e.g. `serve_vllm.sbatch`*)

```bash
# 1) add a port-forward to the EXISTING master on the home PC (no new WCSS login)
ssh home 'ssh -O forward -L 18000:<node>:8000 wcss'          # <node> from endpoint_<jobid>.txt
# 2) forward this PC -> home
ssh -N -L 8000:localhost:18000 home
# 3) use it
curl -H "Authorization: Bearer $KEY" http://localhost:8000/v1/models
```
The other session also relays ports onto the Solvro VPN (`deploy/wcss/relay.sh`, not in this repo) — ask it before
building a second relay. Servers started by `serve.sbatch` bind to localhost on the node, so for those use `srun --overlap` (above) or
add an `ssh -L` hop from inside the allocation.

## 6. Thrift rules

* Prefer the shared server; if you must start one, use `serve_vllm.sbatch` (idle watchdog) and `scancel` when done.
* Embedding/indexing of ≤10k incidents → CPU partition (minutes); only the M2 contrastive fine-tune needs a GPU.
* Check before leaving: `squeue -u $USER` — nothing of ours (`rp-*`) may remain RUNNING idle.
