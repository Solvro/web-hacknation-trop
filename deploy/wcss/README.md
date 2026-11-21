# WCSS (Bem2/Lem) — batch only, never in the live path

The live product runs on Gemini + OpenRouter (`backend/trop/media/gateway.py`). WCSS is used for **bulk re-runs** of the
ad-screenshot VLM and the pair adjudicator, because it is cheaper there and the raw organizer material may stay on WCSS.

| file | what |
|---|---|
| `serve_vllm.sbatch` | one H100, OpenAI-compatible vLLM endpoint, 20 min idle watchdog. `sbatch --account=<grant> --export=ALL,MODEL=Qwen/Qwen3.6-35B-A3B,PORT=8000 serve_vllm.sbatch` |
| `vlm_extract.py` | `srun --overlap ... python3 vlm_extract.py <img_dir> <out.jsonl> name:port` — structured ad fields (same prompt as the gateway's `AD_PROMPT`) |
| `adjudicate.py` | `srun --overlap ... python3 adjudicate.py dossiers.jsonl out.jsonl name:port [features\|raw] [workers]` |

Set `WCSS_API_KEY_FILE` to the file holding the vLLM `--api-key`. Account ids, Lustre paths and SSH details are
site-specific and kept out of the repo (see the wcss-slurm notes). Outputs (`vlm_*.jsonl`) can be dropped into
`data/experiments/*/` and replayed into the gateway cache with `trop media seed-cache`.
