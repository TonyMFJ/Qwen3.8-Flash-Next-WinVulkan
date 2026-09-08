#!/usr/bin/env python3
"""Build a joined PLE sidecar from a per-head qwen4exp GGUF.

The current qwen4exp GGUF stores the n-gram PLE table per-head
(ple_ngram_embd.N.weight). `--ngram-on-disk` is ignored for that layout
(fork qwen4exp.cpp:214). To get the PLE table off the GPU we rebuild it as
the joined single tensor `per_layer_token_embd.weight` in a standalone GGUF
and point `--model-ple` at it. The loader asks that sidecar only for that one
tensor (shape/type/offset), copying raw bytes: no dequantize, no requantize.
"""
import sys, os
sys.path.insert(0, r'C:\llama-build\llama.cpp-vulkan-qwen4exp-rocmfpx\gguf-py')
import numpy as np
import gguf

MODEL = r'C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16.gguf'
SIDECAR = r'C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\ple_sidecar_joined.gguf'
TMP = r'C:\llama-build\joined_ple.bin'

r = gguf.GGUFReader(MODEL)
arch = str(r.fields['general.architecture'].contents())
print('arch=', arch)

ple = {t.name: t for t in r.tensors if t.name.startswith('ple_ngram_embd')}
n_heads = len(ple)
print('ple heads:', n_heads)

# metadata: head_offsets / head_vocab_sizes
def arr(key):
    f = r.fields[key]
    # f.data lists the indices of parts holding scalar elements of the array
    vals = [int(np.asarray(f.parts[i]).flatten()[0]) for i in (f.data if f.data is not None else range(len(f.parts)))]
    return vals

offs = arr('qwen4exp.ple.head_offsets')
vocs = arr('qwen4exp.ple.head_vocab_sizes')
print('head_offsets[:3]=', offs[:3] if offs else None)
print('head_vocab_sizes[:3]=', vocs[:3] if vocs else None)
total_rows = offs[-1] + vocs[-1]
print('total_rows=', total_rows)

# per-head row bytes from first head's data
h0 = ple['ple_ngram_embd.0.weight']
row_bytes = h0.data.nbytes // h0.data.shape[0]
print('head0 data shape=', h0.data.shape, 'row_bytes=', row_bytes)
expected = total_rows * row_bytes
print('expected joined bytes=', expected, '=', expected/2**30, 'GiB')

# ---- Step 1: assemble joined.bin (streaming, per-head) ----
with open(TMP, 'wb') as out:
    for h in range(n_heads):
        t = ple['ple_ngram_embd.%d.weight' % h]
        d = t.data          # memmap
        # write in chunks of rows to bound memory
        rows = d.shape[0]
        chunk_rows = 200000   # ~14MB
        for s in range(0, rows, chunk_rows):
            e = min(s + chunk_rows, rows)
            out.write(np.asarray(d[s:e]).tobytes())
        print('wrote head %d, %d rows' % (h, rows), flush=True)
    out.flush()
print('joined.bin written, size=', os.path.getsize(TMP), '=', os.path.getsize(TMP)/2**30, 'GiB')

# ---- Step 2: memmap it as the joined tensor ----
mm = np.memmap(TMP, dtype=np.uint8, mode='r')
print('memmap shape=', mm.shape, 'nbytes=', mm.nbytes)

# ---- Step 3: write sidecar GGUF ----
writer = gguf.GGUFWriter(SIDECAR, arch=arch, endianess=r.endianess)
writer.add_tensor_info('per_layer_token_embd.weight',
                       (total_rows, row_bytes), np.uint8, mm.nbytes,
                       gguf.GGMLQuantizationType.Q3_0_ROCMFPX)
writer.write_header_to_file()
writer.write_kv_data_to_file()
writer.write_ti_data_to_file()
writer.write_tensor_data(mm, tensor_endianess=r.endianess)
writer.close()
print('sidecar written:', SIDECAR)
