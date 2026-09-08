import sys, os
sys.path.insert(0, r'C:\llama-build\llama.cpp-vulkan-qwen4exp-rocmfpx\gguf-py')
import numpy as np, gguf
M = r'C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf'
r = gguf.GGUFReader(M)
ts = [t.name for t in r.tensors]
print('n_tensors=', len(ts))
ple_heads = [n for n in ts if n.startswith('ple_ngram_embd')]
joined = [n for n in ts if n.startswith('per_layer_token_embd')]
print('per_head_count=', len(ple_heads), 'joined_count=', len(joined), 'joined_names=', joined)
for t in r.tensors:
    if t.name.startswith('per_layer_token_embd'):
        print('joined: name=%s type=%s shape=%s dtype=%s nbytes=%s' % (t.name, getattr(t,'tensor_type',None), t.data.shape, t.data.dtype, t.data.nbytes))
# sanity: a couple non-PLE tensors present
print('has blk.0.attn_qkv:', any(n=='blk.0.attn_qkv.weight' for n in ts))
