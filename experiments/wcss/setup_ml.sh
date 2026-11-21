#!/bin/bash
source ~/redpill/env.sh
set -x
date
uv venv -p 3.12 $ML_ENV
VIRTUAL_ENV=$ML_ENV uv pip install torch torchvision sentence-transformers transformers pillow lightgbm scikit-learn numpy pandas huggingface_hub hf_transfer safetensors sentencepiece protobuf
$ML_ENV/bin/python -c "import torch, sentence_transformers; print('torch', torch.__version__, torch.version.cuda, 'st', sentence_transformers.__version__)"
for m in sdadas/mmlw-roberta-base BAAI/bge-m3 google/siglip-base-patch16-224; do
  HF_HUB_ENABLE_HF_TRANSFER=1 $ML_ENV/bin/hf download $m --cache-dir $HF_HOME/hub --exclude "*.onnx" "onnx/*" "*.msgpack" "*.h5" "*.ot" "openvino/*" > /dev/null 2>&1 && echo "DONE $m" || echo "FAIL $m"
done
date
echo SETUP_FINISHED
