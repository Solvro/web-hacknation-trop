# Source me on WCSS:  source ~/redpill/env.sh
# PBR grant = "Projekt badawczo rozwojowy w inżynierii oprogramowania"
export RP_ACCOUNT=hpc-dawlin1140-1773687823
export RP_PD=/lustre/pd03/hpc-dawlin1140-1773687823
export RP_HOME=$RP_PD/redpill
export HF_HOME=$RP_PD/hf_cache            # shared HF cache on lustre (home is 96% full)
export HF_HUB_ENABLE_HF_TRANSFER=1
export UV_CACHE_DIR=$RP_PD/uv_cache
export UV_PYTHON_INSTALL_DIR=$RP_PD/uv_python
export PATH=$HOME/.local/bin:$PATH
export VLLM_ENV=$RP_HOME/venv-vllm
export ML_ENV=$RP_HOME/venv-ml
mkdir -p $RP_HOME/logs $RP_HOME/data $RP_HOME/out
