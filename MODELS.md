# Models — files and placement / 模型清单与放置路径

> **EN** | All models live in the standard LM Studio directory (the absolute paths in the scripts
> assume this; if you unpack elsewhere, update the paths in `scripts/` accordingly).
>
> **中文** | 所有模型放在 LM Studio 标准目录（脚本里的绝对路径基于此；解压到其他位置请同步改 scripts 里的路径）：

```
C:\Users\antho\.lmstudio\models\
├── agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\
│   ├── Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf   ← main model, joined PLE (final config, 93.48 GB / 87.06 GiB)
│   │                                                            ← 主模型（定稿用）
│   ├── Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16.gguf          ← main model, per-head PLE (rollback, 93.48 GB / 87.06 GiB)
│   │                                                            ← 主模型（per-head 回滚用）
│   └── mmproj-Qwen3.8-Flash-Next-f16.gguf                     ← vision projector (~0.8 GB)
└── quimmedes\Qwen3.8-Flash-Next-MTP-GGUF\
    └── mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf                     ← MTP draft model (2.59 GB)
```

---

## Download sources / 下载源（HuggingFace）

### This project's mirror (easiest for a fresh machine) / 本机备份（换机恢复首选）

**[`TonyMFJ/Qwen3.8-Flash-Next-WinVulkan-GGUF`](https://huggingface.co/TonyMFJ/Qwen3.8-Flash-Next-WinVulkan-GGUF)** — 119.57 GB (111.36 GiB) of downloads, the companion mirror for this GitHub repo:

> **Model facts / 模型参数** — Qwen3.8-Flash-Next is a **~180 B** model: **125 B transformer (6 B activated
> per token) + a 51 B n-gram embedding table + a 4 B MTP draft**. Measured from the GGUF headers: the main
> file holds **176.94 B** tensor parameters (125.74 B backbone + 51.20 B n-gram table), the MTP draft **3.88 B**.
> **87.06 GiB / 93.48 GB is the size of the main quant file at 4.23 bpw — it is not a parameter count.**
> （早期文档写成 "87B 模型"，那是把文件体积当成了参数量，已更正。）
>
> 中文：Qwen3.8-Flash-Next 总参约 **180B** = 主干 125B（每 token 激活 6B）+ n-gram 表 51B + MTP 草稿 4B；
> 主模型文件实测 **176.94B** 张量参数（125.74B 主干 + 51.20B n-gram 表），草稿 **3.88B**。
> **87.06 GiB / 93.48 GB 是 4.23 bpw 量化文件的体积，不是参数量。**

| File / 文件 | Size / 大小 | Destination / 放置路径 |
|------|------|------------|
| `Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16.gguf` | 93.48 GB (87.06 GiB) | `agentionai\` directory (removed locally, still on HF) |
| `ple_sidecar_joined.gguf` | 22.40 GB (20.86 GiB) | `agentionai\` directory — the `--model-ple` sidecar (the same 51.2 B-parameter table in joined layout) |
| `mmproj-Qwen3.8-Flash-Next-f16.gguf` | 0.90 GB (0.84 GiB) | `agentionai\` directory |
| `mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf` | 2.79 GB (2.59 GiB) | `quimmedes\` directory |

### Upstream / 上游原仓

| Repo | Files |
|------|-------|
| [`agentionai/Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF`](https://huggingface.co/agentionai/Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF) | both main models + mmproj |
| [`quimmedes/Qwen3.8-Flash-Next-MTP-GGUF`](https://huggingface.co/quimmedes/Qwen3.8-Flash-Next-MTP-GGUF) | MTP draft |

---

## About the JOINED layout / JOINED 版本说明

**EN** | `-JOINED.gguf` is the per-head model with its 16 small PLE tensors (`ple_ngram_embd.0-15`)
losslessly concatenated into a single `per_layer_token_embd` tensor (quantized bytes copied as-is,
no requantization) — the fork's `--ngram-on-disk` only understands the joined layout. Converter:
[`tools/`](tools/), details in [`src-patches/PATCHES.md`](src-patches/PATCHES.md).

Without the JOINED build you can still start from the per-head model
(`scripts\start_llamaserver.cmd`, the rollback config) — the PLE table then stays fully in VRAM.

**中文** | `-JOINED.gguf` 是把 per-head 版的 16 个 PLE 小 tensor（`ple_ngram_embd.0-15`）无损拼接成
单个 `per_layer_token_embd` 大 tensor 的版本（量化字节原样拷贝，无重量化）——fork 的 `--ngram-on-disk`
只认 joined 布局。转换工具见 `tools/`，详见 `src-patches/PATCHES.md`。

没有 JOINED 版时可用 per-head 版启动（`scripts\start_llamaserver.cmd` 回滚脚本），PLE 表全进显存。
