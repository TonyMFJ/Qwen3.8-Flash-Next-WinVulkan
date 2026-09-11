# Source modifications / 原创改造说明（src-patches）

> **EN** | The two changes this kit makes on top of upstream
> [`LaurentZuijdwijk/llama.cpp`](https://github.com/LaurentZuijdwijk/llama.cpp) branch
> `vulkan/qwen4exp-rocmfpx`.
> Build environment: **w64devkit MinGW GCC 16.2.0 + CMake "MinGW Makefiles" + Vulkan backend**.
>
> **中文原文见文末**（内容一致，未删改）。

---

## 1. MTP draft patch — `qwen4exp.cpp`

**Problem**: among the MTP (Multi-Token Prediction) draft model's 35 tensor weights, the
`NEXTN_SHARED_HEAD_NORM` tensors are not handled by the qwen4exp draft forward loop — the draft model
either fails to load/infer, or loads with an acceptance rate of exactly 0.

**Change**: add a `NEXTN_SHARED_HEAD_NORM` handling branch to the draft loop in
`src/models/qwen4exp.cpp`.
(`src-patches/qwen4exp.cpp` is the complete post-change file — diff it against the upstream file of
the same name to see the modification.)

**Launch flags**:

```
-md <draft.gguf> --spec-type draft-mtp --spec-draft-adaptive \
   --spec-draft-n-min 2 --spec-draft-n-max 4 --n-gpu-layers-draft 99
```

**Verification**: draft acceptance shows up in the log (normal range 0.5–0.67); generation speed
+30–50 % versus no MTP. Measured gains and their cost → [TUNING_NOTES.md](TUNING_NOTES.md) §1.

## 2. PLE disk-offload, Windows I/O — `llama-ple-disk.cpp`

**Problem**: upstream `--ngram-on-disk` (keep the PLE n-gram table on disk instead of in VRAM) uses
POSIX I/O (`open` / `read` / `mmap`), which does not compile under Windows/MinGW — so the 20.86 GB
PLE table had to be resident in VRAM.

**Change**: every POSIX call in `src/llama-ple-disk.cpp` is replaced with the Windows CRT equivalent:
`_open` / `_read` / `_lseeki64` / `_aligned_malloc` (plus the matching aligned free). After the
change, `--ngram-on-disk` compiles and runs on Windows, reading the PLE table through a disk buffer.

**Prerequisite**: the model's PLE table must be in **joined layout** (a single `per_layer_token_embd`
tensor). A per-head layout (16 small tensors) is skipped outright by the fork
(`qwen4exp.cpp` ~L214), so disk-offload silently does nothing. Convert per-head → joined with the
[`tools/`](tools/) chain (gguf-py needs dtype 104 `Q3_0_ROCMFPX` registered first).

---

## PLE sidecar toolchain (`tools/`)

| Tool | Origin | Purpose |
|------|--------|---------|
| `gguf_split_ple_heads.py` | ships with the fork | reference `join()` implementation — **OOMs on a 31.6 GB machine, reference only** |
| `build_ple_sidecar.py` | **ours** | chunked/streaming per-head → joined converter, low memory peak (runs on 31.6 GB) |
| `convert_to_joined.py` | **ours** | conversion entry point |
| `verify_joined.py` | **ours** | post-conversion validation (tensor count / offsets / `ne` orientation) |
| `gguf_extract_ple.py` | ships with the fork | PLE extraction |

---

## Field notes / 本机部署关键经验（踩坑实录）

- `--load-mode none` is the crash culprit — **`--load-mode auto` is mandatory**（被污染成 `none`
  会把 87 GB 全读进 31.6 GB 内存后静默崩）
- Putting mmproj on the CPU is physically impossible here (the 862 MB host-visible buffer competes
  with the ~180 B model (≈93 GB of weights) inside the same 96 GB carve → guaranteed crash); on the GPU it works but sits at
  the VRAM ceiling
- KV cache as `-ctk q8_0 -ctv q8_0 --no-kv-offload` (host) ≈ 5–6 GB of host memory at 100K context —
  but see [TUNING_NOTES.md](TUNING_NOTES.md) §2 for the decode cost
- Windows double-layer SSH quoting always breaks → write complex PowerShell as a `.ps1` and run it
  with `-File`
- Kill services by **exact PID**; a blind batch `taskkill` / `for /f` sweep hits unrelated processes
- The log line `unused tensor per_layer_token_embd.weight ... -- ignoring` is a **false alarm** —
  disk-offload may well be working. Verification recipe → [TUNING_NOTES.md](TUNING_NOTES.md) §5

---

## 中文原文

本包相对上游 `LaurentZuijdwijk/llama.cpp` 分支 `vulkan/qwen4exp-rocmfpx` 的两大改造。
构建环境：w64devkit MinGW GCC 16.2.0 + CMake MinGW Makefiles + Vulkan 后端。

### 1. MTP draft 补丁 — `qwen4exp.cpp`

**问题**：MTP（Multi-Token Prediction）draft 模型的 35 张量权重里，`NEXTN_SHARED_HEAD_NORM`
类张量在 qwen4exp 架构的 draft 前向循环中未被处理，draft 模型加载/推理失败或 acceptance 为 0。

**改动**：`src/models/qwen4exp.cpp` draft 循环中加入 `NEXTN_SHARED_HEAD_NORM` 处理分支。
（`src-patches/qwen4exp.cpp` 为改后完整文件，对照上游同名文件 diff 即可看到改动点。）

**启动参数组合**：

```
-md <draft.gguf> --spec-type draft-mtp --spec-draft-adaptive --spec-draft-n-min 2 --spec-draft-n-max 4 --n-gpu-layers-draft 99
```

**验证**：日志出现 draft acceptance（正常 0.5-0.67）；生成速度相对无 MTP +30-50%。

### 2. PLE 磁盘化 Windows I/O — `llama-ple-disk.cpp`

**问题**：上游 `--ngram-on-disk`（PLE n-gram 表留磁盘不进显存）用 POSIX I/O（open/read/mmap），
Windows/MinGW 编译直接报错不可用 → 20.86GB PLE 表必须全进显存。

**改动**：`src/llama-ple-disk.cpp` 全部 POSIX 调用替换为 Windows CRT：
`_open` / `_read` / `_lseeki64` / `_aligned_malloc`（含对齐 free 对应）。
改后 `--ngram-on-disk` 在 Windows 正常编译运行，PLE 表走磁盘缓冲读。

**前置条件**：模型 GGUF 的 PLE 表必须是 **joined 布局**（单 `per_layer_token_embd` tensor）。
per-head 布局（16 个小 tensor）在 fork 源码里被直接 ignored（见 qwen4exp.cpp ~L214），
磁盘化无效。per-head → joined 转换用 `tools/` 工具链（gguf-py 需先注册 dtype 104 `Q3_0_ROCMFPX`）。

### PLE sidecar 转换工具链（tools/）

```
gguf_split_ple_heads.py   ← fork 自带：join() 逻辑参考实现（会 OOM，仅参考）
build_ple_sidecar.py      ← 自研：分块/流式 per-head → joined（低内存峰值，本机 31.6GB 可跑）
convert_to_joined.py      ← 自研：转换入口
verify_joined.py          ← 自研：转换后校验（tensor 数/offsets/ne 方向）
gguf_extract_ple.py       ← fork 自带：PLE 提取
```

### 本机部署关键经验（踩坑实录）

- `--load-mode none` 是崩溃元凶，**必须 `--load-mode auto`**（被污染成 none 会把 93GB 权重全读进 31.6GB 内存静默崩）
- mmproj 放 CPU 物理不可行（862MB host-visible buffer 与 180B 模型（≈93GB 权重）抢 96GB carve 必崩）；放 GPU 可行但贴上限
- KV 用 `-ctk q8_0 -ctv q8_0 --no-kv-offload`（host），100K 上下文约 5-6GB host 内存
- Windows 双层 SSH 引号必炸 → 复杂 PowerShell 写成 .ps1 用 `-File` 执行
- 精确杀服务按 PID；批量 taskkill / for /f 盲杀会误伤无关进程
