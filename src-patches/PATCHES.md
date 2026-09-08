# 原创改造说明（src-patches）

本包相对上游 `LaurentZuijdwijk/llama.cpp` 分支 `vulkan/qwen4exp-rocmfpx` 的两大改造。
构建环境：w64devkit MinGW GCC 16.2.0 + CMake MinGW Makefiles + Vulkan 后端。

## 1. MTP draft 补丁 — `qwen4exp.cpp`

**问题**：MTP（Multi-Token Prediction）draft 模型的 35 张量权重里，`NEXTN_SHARED_HEAD_NORM`
类张量在 qwen4exp 架构的 draft 前向循环中未被处理，draft 模型加载/推理失败或 acceptance 为 0。

**改动**：`src/models/qwen4exp.cpp` draft 循环中加入 `NEXTN_SHARED_HEAD_NORM` 处理分支。
（`src-patches/qwen4exp.cpp` 为改后完整文件，对照上游同名文件 diff 即可看到改动点。）

**启动参数组合**：
```
-md <draft.gguf> --spec-type draft-mtp --spec-draft-adaptive --spec-draft-n-min 2 --spec-draft-n-max 4 --n-gpu-layers-draft 99
```
**验证**：日志出现 draft acceptance（正常 0.5-0.67）；生成速度相对无 MTP +30-50%。

## 2. PLE 磁盘化 Windows I/O — `llama-ple-disk.cpp`

**问题**：上游 `--ngram-on-disk`（PLE n-gram 表留磁盘不进显存）用 POSIX I/O（open/read/mmap），
Windows/MinGW 编译直接报错不可用 → 20.86GB PLE 表必须全进显存。

**改动**：`src/llama-ple-disk.cpp` 全部 POSIX 调用替换为 Windows CRT：
`_open` / `_read` / `_lseeki64` / `_aligned_malloc`（含对齐 free 对应）。
改后 `--ngram-on-disk` 在 Windows 正常编译运行，PLE 表走磁盘缓冲读。

**前置条件**：模型 GGUF 的 PLE 表必须是 **joined 布局**（单 `per_layer_token_embd` tensor）。
per-head 布局（16 个小 tensor）在 fork 源码里被直接 ignored（见 qwen4exp.cpp ~L214），
磁盘化无效。per-head → joined 转换用 `tools/` 工具链（gguf-py 需先注册 dtype 104 `Q3_0_ROCMFPX`）。

## PLE sidecar 转换工具链（tools/）

```
gguf_split_ple_heads.py   ← fork 自带：join() 逻辑参考实现（会 OOM，仅参考）
build_ple_sidecar.py      ← 自研：分块/流式 per-head → joined（低内存峰值，本机 31.6GB 可跑）
convert_to_joined.py      ← 自研：转换入口
verify_joined.py          ← 自研：转换后校验（tensor 数/offsets/ne 方向）
gguf_extract_ple.py       ← fork 自带：PLE 提取
```

## 本机部署关键经验（踩坑实录）

- `--load-mode none` 是崩溃元凶，**必须 `--load-mode auto`**（被污染成 none 会把 87GB 全读进 31.6GB 内存静默崩）
- mmproj 放 CPU 物理不可行（862MB host-visible buffer 与 87B 抢 96GB carve 必崩）；放 GPU 可行但贴上限
- KV 用 `-ctk q8_0 -ctv q8_0 --no-kv-offload`（host），100K 上下文约 5-6GB host 内存
- Windows 双层 SSH 引号必炸 → 复杂 PowerShell 写成 .ps1 用 `-File` 执行
- 精确杀服务按 PID；批量 taskkill / for /f 盲杀会误伤无关进程
