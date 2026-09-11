# HIP notes — the ROCm path we brought up and then abandoned

> **EN** | Everything below was measured on the same 80 W reference machine as the rest of this repo
> (ROG Flow Z13, Ryzen AI MAX+ 395 / gfx1151, 96 GB VRAM carve-out). The HIP path **works**, but it
> does **not** beat the Vulkan path for this architecture — it is published so nobody has to repeat
> the experiment. **Verdict: stay on Vulkan.** Artifacts are attached to the
> [release](../../releases) for reproduction, not for production use.
>
> **一句话**：HIP 路我们能跑通（PLE 磁盘化移植成功、prefill 418.7 t/s），但这颗 APU 上**快不过 Vulkan**——
> 根因是 head_dim=256 让 FlashAttention 掉进 tile 退化路径（~11 TFLOPS），而绕过上游保护会让 kernel
> 直接死锁。**结论：生产继续用 Vulkan**，HIP 产物只作实验记录发布。

---

## 1. What works (measured)

PLE n-gram table disk-offload ported to the official `b10868` ROCm build — the port itself is a
success, the performance is not:

| Scenario | Lazy (table mapped) | `--ngram-on-disk` |
|---|---|---|
| 2.6K prompt, default flags | 335 t/s | 335 t/s |
| 2.6K prompt, `ub4096` + KV `q8_0` | — | **418.7 t/s** |
| 90K long context, tuned flags | 206.7 t/s | 207.9 t/s |
| Model load time | ~**116 s** | **0.35 s** |

Disk-offload costs nothing in throughput here and saves the 28.8 GB PLE table from ever being read
into VRAM. The official static exe with the same table on disk measured **222.9 t/s prefill at 90K**
(the Vulkan fork reaches 220–250 t/s in the same region — i.e. no meaningful HIP advantage).

Porting recipe (9 files, 309 lines, diff included in
[`src-patches/hip/ple-disk-hip-port-b10868.diff`](src-patches/hip/ple-disk-hip-port-b10868.diff)):
`qwen4exp.cpp` dual-path disk gather, `llama.h` model params, 4 CLI args, an `fname()` accessor on
`llama_file`, plus the Windows I/O swap from
[`llama-ple-disk.cpp`](src-patches/llama-ple-disk.cpp).

## 2. Why HIP does not win here (root cause, with evidence)

| Step | Finding |
|---|---|
| Scheduler | `ggml/src/ggml-cuda/fattn.cu:645` dispatches the MMA kernel only when `Q->ne[0] <= 128`. This model has **head_dim = 256** → the WMMA/MMA path is refused even though RDNA 256×256 configs exist in `fattn-mma-f16.cuh` |
| Fallback | FlashAttention lands on `BEST_FATTN_KERNEL_TILE` — **~11 TFLOPS** vs ~73 TFLOPS for the GEMM baseline (~15 %) |
| Prediction | Using the MMA path should have added **~50 %** (207 → ~315 t/s). Patch all 4 dispatch sites (`<=128` → `<=256`) → the kernel is selected… |
| Reality | …and **hangs**: a 56K prompt timed out, a 91K prompt never finished in 30 minutes |
| True cause | `fattn-mma-f16.cuh:1826`: under `AMD_WMMA_AVAILABLE`, `DKQ > 128 → NO_DEVICE_CODE`. For RDNA the MMA kernel for head_dim > 128 is an **empty kernel stub** — never implemented upstream. The `<=128` guard is protection, not conservatism |
| Collateral | The hang is **not killable** — GPU kernel-level deadlock; `taskkill /f`, `Stop-Process -Force` and `TerminateProcess` all report "no running instance". Only a **machine reboot** clears it |

Useful probe for anyone continuing: **Qwen3.6-35B-A3B** (`key_length = 256`, single-file GGUF)
exercises the same FA-256 path and runs at 916 t/s with the official DLL — a cheap way to separate
"wrong kernel" from "wrong flags".

## 3. Traps we hit bringing HIP up (each cost hours)

| # | Symptom | Cause / fix |
|---|---------|-------------|
| 1 | Exe reports **no usable GPU** even with a working backend DLL | The backend must be built with **`-DGGML_BACKEND_DL=ON`**, which exports the unified `ggml_backend_init`. Without it the DLL only exports `ggml_backend_cuda_reg` and the loader skips it. Note `GGML_NATIVE` and `GGML_BACKEND_DL` are mutually exclusive → use `GGML_CPU_ALL_VARIANTS` |
| 2 | `LoadLibrary` fails with **error 126** on `ggml-hip.dll` | Broken recursive dependency chain: `rocsolver.dll`, `libomp.dll`, and the `hipblaslt\` + `rocblas\` **kernel subdirectories** are easy to miss — the DLL loads from the same folder, not from PATH |
| 3 | AMD's HIP SDK 7.2 installer finishes with **0 files installed** | The GUI/silent installer silently did nothing. What worked: unpack the installer, install the MSIs directly, verify with `oclc_isa_version_1151.bc` + clang 21 |
| 4 | MinGW-built exe appears hung when launched through a tool pipe | Launched detached (`cmd /c start`, WMI `Win32_Process Create`) it returns immediately — the official build does not show this, another reason to keep the toolchain consistent |
| 5 | "OOM" while 107 GB of VRAM is free | It was **System Commit** exhaustion, not VRAM: `CommitLimit` 127.6 GB, large GPU allocations count against commit, and a zombie process was holding ~90 GB of it. Probe with `hipMemGetInfo` before blaming VRAM |
| 6 | `taskkill /f` on a stuck llama-server "succeeds" but the PID stays | The kill was intercepted by the sandbox. `TerminateProcess` via `ctypes` worked (except in the case of a GPU deadlock, which needs a reboot — §2) |

## 4. Release assets (what each file is)

| Asset | What it is | How to use |
|-------|-----------|------------|
| `llama-hip-ple-disk-mingw-core-b10868.zip` | **Our** MinGW build of the llama.cpp `b10868` core with the PLE-disk port (llama-server + libllama/ggml DLLs; **no** AMD runtime included) | Take the official llama.cpp `b10868` **ROCm 7.2 Windows** release (it brings `ggml-hip.dll` + the AMD runtime + `hipblaslt\`/`rocblas\`), unzip both into one folder, then `llama-server.exe --ngram-on-disk …` |
| `ple-disk-hip-port-b10868.patch` | The 9-file / 309-line port of the PLE disk-offload to the official `b10868` tree | `git apply` against llama.cpp `b10868` |
| `ggml-hip-fattn256-experimental.dll` | **Our** self-built HIP backend with the fattn `<=128 → <=256` guard bypassed at all 4 dispatch sites (75.8 MB) | **Research only.** It hangs at head_dim = 256 (§2) and can require a reboot to recover |
| `ggml-hip-rocm7.2-b10868-official.dll` | The **unmodified** official backend, mirrored for convenience (938.9 MB) | Identical to the file inside the official llama.cpp `b10868` ROCm 7.2 Windows release — verify the hash before trusting a mirror |

## 5. Bottom line

- HIP is **viable** on Strix Halo (PLE disk-offload works, model loads in 0.35 s, no crash in normal operation)
- HIP is **not faster** for head_dim = 256 models on gfx1151, and the only route to more prefill
  throughput (MMA) is dead upstream (empty kernel stub)
- The Vulkan path in this repo remains the recommendation: same numbers, no ROCm install, no
  938 MB of runtime DLLs

---

## 中文摘要

- **能跑通**：PLE 磁盘化成功移植到官方 `b10868` HIP 版——2.6K prompt + ub4096 + KV q8_0 实测 **418.7 t/s**，
  90K 长上下文 207.9 t/s（与 lazy 持平），模型加载 **116s → 0.35s**（28.8GB PLE 表不进显存）
- **不划算**：本架构 head_dim=256，`fattn.cu:645` 的 `<=128` 把 MMA kernel 拒之门外，FA 掉进 tile
  退化路径（~11 TFLOPS，约 GEMM 基线 73 的 15%）；把 4 处调度点改成 `<=256` → kernel 直接 **hang**
  （56K 超时、91K 三十分钟没跑完），根因是 `fattn-mma-f16.cuh:1826` 在 RDNA 上对 head_dim>128 是
  **空壳 kernel**（上游从未实现）；且死锁杀不掉，只能重启机器
- **结论**：**继续用 Vulkan**；HIP 产物（自编 core / 补丁 / 实验 dll / 官方 dll 镜像）随 Release 发布，
  只作实验记录与复现用途
- 附带排掉的坑：`GGML_BACKEND_DL=ON` 不开就"没有可用 GPU"；LoadLibrary 126 = `rocsolver/libomp/hipblaslt\rocblas\`
  依赖链断；官方 HIP SDK 安装器静默装 0 文件需拆包装 MSI；"OOM" 实为 System Commit 耗尽
