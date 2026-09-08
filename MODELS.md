# 模型清单与放置路径

所有模型放在 LM Studio 标准目录（脚本里的绝对路径基于此；解压到其他位置请同步改 scripts 里的路径）：

```
C:\Users\antho\.lmstudio\models\
├── agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\
│   ├── Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf   ← 主模型（定稿用，~92GB）
│   ├── Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16.gguf          ← 主模型（per-head 回滚用，~93GB）
│   └── mmproj-Qwen3.8-Flash-Next-f16.gguf                     ← 视觉投影（~0.8GB）
└── quimmedes\Qwen3.8-Flash-Next-MTP-GGUF\
    └── mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf                     ← MTP draft 模型
```

## 下载源（HuggingFace）

### 本机备份（换机恢复首选，全套直连）

**`TonyMFJ/Qwen3.8-Flash-Next-WinVulkan-GGUF`** — 共 111.36GB，与 GitHub 仓库配套：

| 文件 | 大小 | 对应放置路径 |
|------|------|------------|
| `Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16.gguf` | 87.06GB | agentionai 目录（本机已删，云端有） |
| `ple_sidecar_joined.gguf` | 20.86GB | agentionai 目录（`--model-ple` 侧车） |
| `mmproj-Qwen3.8-Flash-Next-f16.gguf` | 0.84GB | agentionai 目录 |
| `mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf` | 2.59GB | quimmedes 目录 |

### 上游原仓

| 仓库 | 文件 |
|------|------|
| `agentionai/Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF` | 上面两个主模型 + mmproj |
| `quimmedes/Qwen3.8-Flash-Next-MTP-GGUF` | MTP draft |

## JOINED 版本说明

`-JOINED.gguf` 是把 per-head 版的 16 个 PLE 小 tensor（`ple_ngram_embd.0-15`）无损拼接成单个
`per_layer_token_embd` 大 tensor 的版本（量化字节原样拷贝，无重量化）——fork 的 `--ngram-on-disk`
只认 joined 布局。转换工具见 `tools/`，详见 `src-patches/PATCHES.md`。

没有 JOINED 版时可用 per-head 版启动（`scripts\start_llamaserver.cmd` 回滚脚本），PLE 表全进显存。
