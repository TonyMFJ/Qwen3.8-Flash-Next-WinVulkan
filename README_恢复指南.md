# Qwen3.8-Flash-Next 本机部署 — 恢复指南（2026-09-08 定稿）

> **EN — Recovery quick reference** (the rest of this file is the original Chinese runbook; the
> `it_assist` / QwenPaw / LM Studio paragraphs are specific to the author's machine and can be
> ignored on yours):
>
> 1. **Start**: `schtasks /run /tn <your-task>` pointing at
>    `scripts\start_llamaserver_joined.cmd` (PLE table on disk + ub2048 + MTP + vision + metrics).
>    The legacy `QwenPawLlamaServer` task points at the old per-head 64K config — emergency rollback only.
> 2. **Wait ~2 minutes**, then verify: `curl http://127.0.0.1:1234/health` → `{"status":"ok"}`.
> 3. **Expect** (80 W power profile): prefill **299 t/s** @24K, generation **14.5 t/s** with MTP,
>    VRAM **71 / 96 GB**. Same machine on the per-head resident config: 370 t/s / 28 t/s / 93 GB.
>    → disk-offload trades ~20 % prefill for 22 GB of VRAM headroom.
> 4. **Config that produced those numbers**: `--ngram-on-disk --ngram-io-threads 12 --ngram-cache 8192`
>    + `-ubatch-size 2048` with the **JOINED** sidecar model. `-ubatch-size 4096` does not work here
>    (with vision → mmproj load failure; without → decode OOM).
> 5. **If start-up fails with plenty of free memory**: host RAM / VRAM fragmentation — the 862 MB
>    mmproj host-visible buffer can no longer be allocated. **Only a reboot fixes it.**
> 6. Detailed tuning levers and the full pitfall list: [TUNING_NOTES.md](TUNING_NOTES.md) /
>    [ENVIRONMENT.md](ENVIRONMENT.md).

## ⚡ 2026-09-08 最新定稿：PLE 磁盘化 + ub2048（JOINED sidecar）

**启动任务已切换：`schtasks /run /tn QwenPawLlamaServerJoined`（脚本 `start_llamaserver_joined.cmd`）**
（老任务 QwenPawLlamaServer 指向 per-head 64K 老配置，仅作应急回滚）

- **模型换成 JOINED sidecar**：`Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf`（同目录，92GB）+ `--ngram-on-disk` → PLE 表 20.86GB 走磁盘
- **收益：显存 93 → 71GB，腾出 22GB 余量**
- **参数组合实测（2026-09-08）：`--ngram-io-threads 12 --ngram-cache 8192 + ubatch 2048`**
  - prefill：200 → **299 t/s**（24K tok 实测，+50%）
  - 生成：10.65 → **14.5 t/s**（+36%，MTP 生效）
- **ub4096 实锤不可用**：带视觉 → mmproj 加载失败；无视觉 → decode OOM（1.28GB 分配失败）。ub2048 = 本机甜点
- ⚠️ **文件预热无效**：FreePhys 仅 ~7GB，Windows 不保留缓存数据（预热脚本 `warmup_ple.ps1` 保留备用，重启机器内存干净后可再试）
- ⚠️ **反复崩溃循环 → host RAM / 显存碎片化，mmproj 862MB host-visible buffer 分配失败连带服务起不来**。症状：FreePhys 充足但启动失败 → 只能重启机器根治。重启后第一件事：`schtasks /run /tn QwenPawLlamaServerJoined`

## 硬件
- ROG Flow Z13 GZ302EA / Ryzen AI MAX+ 395 / **128GB LPDDR5X**（BIOS carve 96GB 显存 → Windows 只见 31.6GB RAM）
- 87GB 权重驻留 96GB carve-out，不依赖 pagefile 硬撑

## 重启后恢复步骤（3 步）

### 1. 启动 llama-server（端口 1234）
```cmd
schtasks /run /tn QwenPawLlamaServerJoined
```
- 任务指向：`C:\llama-build\start_llamaserver_joined.cmd`
- 加载约 2 分钟，日志：`C:\llama-build\joined_mtp_log.txt`

### 2. 验证
```cmd
curl http://127.0.0.1:1234/health     → {"status":"ok"}
```
速度基准（PLE 磁盘版实测）：生成 14.5 t/s（MTP 生效）、prefill 299 t/s（24K tok）。
老对照（per-head 全显存版）：生成 28 t/s / prefill 370 t/s——磁盘化换 22GB 显存，全链路 -37~50%。

> ⚠️ **Benchmark conditions**: measured with the **APU package power limited to 80 W**. Environment details, driver/toolchain versions and build commands → [ENVIRONMENT.md](ENVIRONMENT.md).

### 3. it_assist 后端（已配好，无需动）
- `C:\Users\antho\.qwenpaw\workspaces\it_assist\agent.json` → `"active_model": {"provider_id": "lmstudio", "model": "qwen4exp-flash-next"}`
- QwenPaw 内置 lmstudio provider 固定指向 127.0.0.1:1234

## 回滚 it_assist（如需）
agent.json 改回：
```json
"active_model": { "provider_id": "zhipu-cn-codingplan", "model": "glm-5.3-flash" }
```

## ✅ 旧版配置存档（2026-09-01 定稿，per-head 全显存，已被 09-08 磁盘版取代）
- 64K 上下文（-c 65536）+ KV host（--no-kv-offload）+ ubatch 1024 + --parallel 1
- 实测：prefill 370 t/s、生成 15-16 t/s；显存 93GB 贴上限
- ⚠️ schtasks 任务被 /end 后会变"已禁用"，需 `schtasks /change /tn QwenPawLlamaServer /enable` 再 /run

## 注意事项
- ⚠️ **1234 = qwen4exp 专用**：LM Studio Developer Server 已被 antho 挪到 **1235**（别再抢 1234）
- ⚠️ **2026-09-01 深夜定稿参数：`--no-kv-offload`（KV 走 host）+ `-c 102400`（100K 上下文）+ --parallel 1 + ubatch 512 + --no-mmproj**：
  - 背景：96GB carve 被 87B+draft 顶满 → 请求期分配失败 → fork 的 GGML_ASSERT 带崩进程（APPCRASH ×3）。KV 挪 host 后显存解放，上下文开到 100K
  - 代价：生成速度 28.8 → **16.9 t/s**（KV host 路径损耗 ~40%，聊天仍比人读快）；会话越长生成越慢（attention 扫全量 KV）；100K 长文档投喂 prefill 需数分钟
  - 视觉功能暂缺（--no-mmproj），要加回：去掉该参数（显存余量 ~1.6GB，mmproj 0.8GB 可塞但紧）
  - if 嫌慢可回退：去 `--no-kv-offload` + `-c 16384` → 28.8 t/s 恢复，上下文缩回 16K
- 壳程序（LM Studio 风格 WebUI）：`C:\llama-build\lmstudio-shell.html`，浏览器直接打开即可（流式聊天 + 服务器状态 + tok/s 统计）
- ⚠️ QwenPaw execute_shell_command 沙箱会拦截 python 的 localhost 连接（curl/powershell 直通）——测试推理用 curl -d @body.json，别用 python urllib
- 崩溃后恢复三连：查进程 → schtasks /run /tn QwenPawLlamaServer → 等 ~2 分钟 curl /health
- 模型文件：
  - 主模型（09-08 定稿，PLE 磁盘 sidecar）：`C:\Users\antho\.lmstudio\models\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\`（**Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf** + mmproj-f16.gguf；老 per-head 版 -v2-ple16.gguf 保留作回滚）
  - MTP draft：`C:\Users\antho\.lmstudio\models\quimmedes\Qwen3.8-Flash-Next-MTP-GGUF\mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf`
- 本地性能测试脚本：`C:\llama-build\prefill_test.ps1`（24K tok prefill）、`tg_test.ps1`（128 tok 生成）、`warmup_ple.ps1`（PLE 区段预热，当前无效待内存干净重试）
- 源码/构建：`C:\llama-build\llama.cpp-vulkan-qwen4-rocmfpx`（fork LaurentZuijdwijk/llama.cpp 分支 vulkan/qwen4exp-rocmfpx，**含 MTP draft 35 张量补丁**：qwen4exp.cpp draft 循环加 NEXTN_SHARED_HEAD_NORM）
- 重建（如需）：`schtasks /run /tn QwenPawLlamaRebuild` 或看 build_log.txt
- 本地性能测试：`C:\llama-build\body.json` + curl POST /completion（python 被沙箱拦）

## 已知现象（非故障）
- 加载期间可能出现 WinError 1455（host 侧 commit 峰值），加载完成后系统恢复正常
- it_assist 首 token 慢（系统提示词 ~12K tokens 冷 prefill 约 50 秒），同会话缓存复用后变快
