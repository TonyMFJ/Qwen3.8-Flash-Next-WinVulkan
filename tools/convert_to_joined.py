#!/usr/bin/env python3
"""A1: convert per-head qwen4exp GGUF into a joined-layout GGUF, streaming.

The fork's gguf_split_ple_heads.py join() only OOMs on np.concatenate of the
22.4 GiB PLE table. This version streams the heads into a temp memmap file and
writes them back through the GGUFWriter, so peak RAM stays small. Everything
else (tensor plan, kv passthrough, ne ordering) matches the fork script: the
joined tensor keeps the first head's position and the writer's write_ti_data
reverses dims so ne[0] stays the per-row element count (160).

Output sets main-model PLE as one per_layer_token_embd; pair with
--ngram-on-disk so the 51B table reads from disk instead of VRAM.
"""
import sys, os
sys.path.insert(0, r'C:\llama-build\llama.cpp-vulkan-qwen4exp-rocmfpx\gguf-py')
import numpy as np, re, gguf

MODEL = r'C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16.gguf'
OUT   = r'C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf'
TMP   = r'C:\llama-build\joined_ple.bin'
JOINED = 'per_layer_token_embd.weight'
HEAD_RE = re.compile(r'ple_ngram_embd\.(\d+)\.weight$')

r = gguf.GGUFReader(MODEL)
offs = [int(x) for x in r.fields.get('qwen4exp.ple.head_offsets').contents()]
vocs = [int(x) for x in r.fields.get('qwen4exp.ple.head_vocab_sizes').contents()]
n_heads = len(offs)
total_rows = offs[-1] + vocs[-1]
print(f'heads={n_heads} total_rows={total_rows}')

tensors = list(r.tensors)
heads = {}
for t in tensors:
    m = HEAD_RE.match(t.name)
    if m:
        heads[int(m.group(1))] = t
print('per-head tensors found:', len(heads))

qtype = heads[0].tensor_type
h0 = heads[0]
row_bytes = h0.data.nbytes // h0.data.shape[0]
print('qtype=%s row_bytes=%d' % (qtype, row_bytes))
joined_nbytes = total_rows * row_bytes
print('joined bytes=%d =%.2f GiB' % (joined_nbytes, joined_nbytes/2**30))

# ---- stream the 16 heads into joined.bin, then memmap it ----
# reuse joined.bin if it already matches, so we don't re-read 22.4GiB
if os.path.exists(TMP) and os.path.getsize(TMP) == joined_nbytes:
    print('reusing existing joined.bin', os.path.getsize(TMP)/2**30, 'GiB', flush=True)
else:
    with open(TMP, 'wb') as out:
        for h in range(n_heads):
            if h not in heads:
                raise ValueError('missing head %d' % h)
            d = heads[h].data
            rows = d.shape[0]
            chunk_rows = 200000
            for s in range(0, rows, chunk_rows):
                e = min(s + chunk_rows, rows)
                out.write(np.asarray(d[s:e]).tobytes())
            print('streamed head %d (%d rows)' % (h, rows), flush=True)
        out.flush()
joined = np.memmap(TMP, dtype=np.uint8, mode='r')
assert joined.nbytes == joined_nbytes, 'joined.bin size mismatch %s vs %s' % (joined.nbytes, joined_nbytes)
print('joined memmap ready', joined.shape, '=%.2f GiB' % (joined.nbytes/2**30))

# ---- build output GGUF: kv passthrough + tensor plan ----
writer = gguf.GGUFWriter(OUT, arch=str(r.fields['general.architecture'].contents()), endianess=r.endianess)
for field in r.fields.values():
    if field.name.startswith('GGUF.') or field.name.startswith('split.'):
        continue
    vt = field.types[0]
    st = field.types[-1] if vt == gguf.GGUFValueType.ARRAY else None
    writer.add_key_value(field.name, field.contents(), vt, sub_type=st)

plan = []
inserted = False
for t in tensors:
    if HEAD_RE.match(t.name):
        if not inserted:
            plan.append((JOINED, (total_rows, row_bytes), joined_nbytes, joined, qtype))
            inserted = True
        continue
    plan.append((t.name, t.data.shape, t.data.nbytes, t.data, t.tensor_type))
print('plan tensors:', len(plan), 'joined inserted at head0 pos:', inserted)

for name, shape, nbytes, data, q in plan:
    if name == JOINED:
        writer.add_tensor_info(name, shape, np.uint8, nbytes, q)
    else:
        writer.add_tensor_info(name, shape, data.dtype, data.nbytes, q)

writer.write_header_to_file()
writer.write_kv_data_to_file()
writer.write_ti_data_to_file()

done = 0
total = sum(n for _, _, n, _, _ in plan)
for name, _, n, data, q in plan:
    if name == JOINED:
        writer.write_tensor_data(data, tensor_endianess=r.endianess)
    else:
        writer.write_tensor_data(data, tensor_endianess=r.endianess)
    done += n
    print('  wrote %.1f%%  %s' % (done/total*100, name), flush=True)

writer.close()
print('DONE ->', OUT)
