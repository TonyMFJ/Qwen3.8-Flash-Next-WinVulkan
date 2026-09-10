# Qwen3.8-Flash-Next · Windows Vulkan Deployment Kit / Windows Vulkan 适配全家桶

> **EN** | Complete local deployment kit for an **87B MoE** model on **ROG Flow Z13 (AMD Ryzen AI MAX+ 395 / 96 GB VRAM carve-out / Windows / Vulkan backend)**. Includes MTP speculative decoding, PLE n-gram table disk-offload (sidecar), fork binaries, startup scripts and a custom WebUI console. **This is original adaptation work — no off-the-shelf guide exists.**
>
> **中文** | 87B MoE 模型在 ROG Flow Z13（Ryzen AI MAX+ 395 / 96GB 显存 carve / Windows / Vulkan 后端）上的完整本地部署方案。含 MTP 投机解码、PLE 表磁盘化（sidecar）、定制 WebUI 控制台。**本包为原始适配，网上无现成方案。**
>
> ⚠️ **Benchmark conditions / 基准条件**: every speed figure below was measured with the **APU package power limited to 80 W** (Ryzen AI MAX+ 395). Full environment, driver/toolchain versions and reproduction steps → [**ENVIRONMENT.md**](ENVIRONMENT.md) · Tuning levers and hard limits → [**TUNING_NOTES.md**](TUNING_NOTES.md)

---

## 🚀 Quick start (5 steps) / 快速开始（5 步）

| # | EN | 中文 |
|---|----|------|
| 1 | Unpack to `C:\llama-build` (or any path — see "paths" below) | **解压** 到 `C:\llama-build`（或任意路径） |
| 2 | Place the GGUF files as described in `MODELS.md` (full set: [`TonyMFJ/Qwen3.8-Flash-Next-WinVulkan-GGUF`](https://huggingface.co/TonyMFJ/Qwen3.8-Flash-Next-WinVulkan-GGUF)) | **放模型** — 按 `MODELS.md` 把 GGUF 放到位（本机备份全套直下） |
| 3 | Right-click `scripts\install_schtasks.cmd` → Run as administrator (or just double-click `scripts\start_llamaserver_joined.cmd`) | **注册启动任务** — 右键 `scripts\install_schtasks.cmd` → 以管理员运行（或直接双击 `scripts\start_llamaserver_joined.cmd`） |
| 4 | Wait ~2 minutes, then verify: `curl http://127.0.0.1:1234/health` → `{"status":"ok"}` | **等 2 分钟**加载，验证 health |
| 5 | Open the console — double-click `webui\index.html` (auto-connects to port 1234) | **打开控制台** — 浏览器开 `webui\index.html` |

---

## 📁 Layout / 目录结构

```
├── README.md                 ← this file / 本文件
├── README_恢复指南.md         ← detailed deploy & recovery doc / 详细部署恢复文档
├── ENVIRONMENT.md            ← environment setup (hardware, driver, toolchain, build cmds, 80 W note)
├── TUNING_NOTES.md           ← what actually moves the needle: MTP, KV placement, ubatch ceiling, pitfalls
├── MODELS.md                 ← model files, download sources, placement / 模型清单与放置路径
├── bin/                      ← llama-server / cli / mtmd-cli (statically linked, no DLLs)
├── webui/index.html          ← custom console: chat + sampler panel + API snippets + status
├── scripts/
│   ├── start_llamaserver_joined.cmd   ← final config (PLE on disk + ub2048 + vision + metrics)
│   ├── start_llamaserver.cmd          ← per-head, fully-resident rollback config
│   ├── install_schtasks.cmd           ← register the Windows scheduled task
│   ├── prefill_test.ps1 / tg_test.ps1 ← benchmark scripts
│   └── warmup_ple.ps1                 ← PLE region pre-warm (only helps with spare memory)
├── tools/                    ← PLE sidecar toolchain (per-head → joined conversion)
└── src-patches/              ← the two original source modifications (+ PATCHES.md)
```

## ⚡ Measured performance / 性能基准（reference machine）

| Config / 配置 | Prefill (24K tok) | Generation | VRAM |
|------|------|------|------|
| **Final: PLE on disk + ub2048 + cache8192** | **299 t/s** | **14.5 t/s** (MTP active) | **71 GB** (22 GB spare) |
| per-head, fully resident, **KV in VRAM** | 370 t/s | 28 t/s | 93 GB (at the ceiling) |
| per-head, fully resident, **KV in host** (rollback) | 370 t/s | 15–16 t/s | 93 GB (at the ceiling) |
| per-head + ub1024 (older) | 200 t/s | 10.65 t/s | 93 GB |

> 磁盘化 = 拿 -20% 速度换 22GB 显存余量（可开 100K 上下文 + 视觉 + 不崩）。
>
> ⚠️ **All figures above were measured at an 80 W APU package-power limit.** Don't compare across different power profiles.
> Long-context data on the same setting: **prefill ≈ 219 t/s at 90K tokens**; generation at 90K goes from **~14 t/s** (KV in host RAM) to **~30 t/s** (KV in VRAM, `-ctk/-ctv q8_0`).
> Full environment (driver / toolchain / build commands / pitfalls) → [ENVIRONMENT.md](ENVIRONMENT.md) · tuning levers → [TUNING_NOTES.md](TUNING_NOTES.md)

## ⚠️ Known limits / 已知限制

- `-ubatch-size 4096` always OOMs on a 96 GB carve (with or without vision); **2048 is the ceiling** / ubatch 4096 在 96GB carve 上必然 OOM，2048 是上限
- Repeatedly loading the 87B model fragments host RAM → the 862 MB mmproj host-visible buffer fails to allocate → **only a reboot fixes it** / host RAM 碎片化后只能重启机器根治
- Windows only sees **31.6 GB of RAM** (96 GB is carved out to the iGPU), which is why PLE disk-offload is mandatory rather than optional / 本机 Windows 只见 31.6GB RAM
