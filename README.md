# Qwen3.8-Flash-Next · Windows Vulkan 适配全家桶

> 87B MoE 模型在 ROG Flow Z13（Ryzen AI MAX+ 395 / 96GB 显存 carve / Windows / Vulkan 后端）上的完整本地部署方案。
> 含 MTP 投机解码、PLE 表磁盘化（sidecar）、定制 WebUI 控制台。**本包为原始适配，网上无现成方案。**

## 快速开始（5 步）

1. **解压** 到 `C:\llama-build`（或任意路径，见下方"路径说明"）
2. **放模型** — 按 `MODELS.md` 把 GGUF 放到位（本机备份 [`TonyMFJ/Qwen3.8-Flash-Next-WinVulkan-GGUF`](https://huggingface.co/TonyMFJ/Qwen3.8-Flash-Next-WinVulkan-GGUF) 全套直下）
3. **注册启动任务** — 右键 `scripts\install_schtasks.cmd` → 以管理员运行（或直接双击 `scripts\start_llamaserver_joined.cmd` 手动拉起）
4. **等 2 分钟** 加载，验证：`curl http://127.0.0.1:1234/health` → `{"status":"ok"}`
5. **打开控制台** — 浏览器开 `webui\index.html`（双击即可，自动连 1234；若同域部署由 llama-server 直接托管更佳）

## 目录结构

```
├── README.md                 ← 本文件
├── README_恢复指南.md         ← 详细部署/恢复文档（重启后照做即可）
├── MODELS.md                 ← 模型清单、下载源、放置路径
├── bin/                      ← llama-server / cli / mtmd-cli（静态链接，无 dll）
├── webui/index.html          ← 定制控制台：聊天 + 调参 + API 复制 + 状态读取
├── scripts/
│   ├── start_llamaserver_joined.cmd   ← 定稿启动（PLE 磁盘 + ub2048 + 视觉 + metrics）
│   ├── start_llamaserver.cmd          ← per-head 全显存回滚版
│   ├── install_schtasks.cmd           ← 注册 Windows 计划任务
│   ├── prefill_test.ps1 / tg_test.ps1 ← 性能基准脚本
│   └── warmup_ple.ps1                 ← PLE 区段预热（内存宽裕时有效）
├── tools/                    ← PLE sidecar 制作工具链（per-head → joined 转换）
└── src-patches/              ← 两大原创改造源码 + 说明（PATCHES.md）
```

## 性能基准（本机实测）

| 配置 | prefill (24K tok) | 生成 | 显存 |
|------|------|------|------|
| **定稿：PLE 磁盘 + ub2048 + cache8192** | **299 t/s** | **14.5 t/s**（MTP 生效） | **71GB**（余 22GB） |
| per-head 全显存（回滚版） | 370 t/s | 15-16 t/s | 93GB（贴上限） |
| per-head + ub1024（旧） | 200 t/s | 10.65 t/s | 93GB |

磁盘化 = 拿 -20% 速度换 22GB 显存余量（可开 100K 上下文 + 视觉 + 不崩）。

## 已知限制

- ubatch 4096 在 96GB carve 上必然 OOM（带/不带视觉都炸），2048 是上限
- host RAM 反复加载 87B 后碎片化 → mmproj 862MB host-visible buffer 分配失败 → 需重启机器根治
- 本机 Windows 只见 31.6GB RAM（96GB 已被 BIOS carve），文件预热在内存紧张时无效
