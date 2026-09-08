@echo off
cd /d C:\llama-build\llama.cpp-vulkan-qwen4exp-rocmfpx\build\bin
llama-server.exe ^
  -m "C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf" ^
  --mmproj "C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\mmproj-Qwen3.8-Flash-Next-f16.gguf" ^
  -md "C:\Users\antho\.lmstudio\models\quimmedes\Qwen3.8-Flash-Next-MTP-GGUF\mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf" ^
  --spec-type draft-mtp --spec-draft-adaptive --spec-draft-n-min 2 --spec-draft-n-max 4 ^
  --n-gpu-layers-draft 99 ^
  --ngram-on-disk --ngram-io-threads 12 --ngram-cache 8192 ^
  -ngl 99 -ctk q8_0 -ctv q8_0 -fa on --no-kv-offload --load-mode auto ^
  -c 102400 --parallel 1 --batch-size 2048 --ubatch-size 2048 --webui --metrics ^
  --path "C:\llama-build\llama.cpp-vulkan-qwen4exp-rocmfpx\build\tools\ui\dist" ^
  --host 127.0.0.1 --port 1234 ^
  > C:\llama-build\joined_mtp_log.txt 2>&1
