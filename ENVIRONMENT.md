# Environment Setup & Reproduction

> **⚠️ Power note (important)**: **every measured figure in this repository was taken with the APU package power limit set to 80 W** (AMD Ryzen AI MAX+ 395, ROG Flow Z13). Numbers shift noticeably with a different power profile — check the wattage before comparing against other people's results.

---

## 0. TL;DR

| What you want | What you need |
|---------------|---------------|
| **Just run it** (use the `bin/` executables) | An AMD GPU driver + a Vulkan runtime + the model files. **No** CUDA, **no** HIP, **no** VC++ redist — the exes are MinGW **statically linked** (zero extra DLLs) |
| **Rebuild from source** | MinGW-w64 (w64devkit) + CMake + Vulkan SDK + glslang — four commands (§3) |
| **Reproduce the numbers in this repo** | Additionally match the power profile: **80 W** |

---

## 1. Reference environment (the machine all figures came from)

| Item | Value |
|------|-------|
| Laptop | ASUS **ROG Flow Z13 GZ302EA** |
| APU | **AMD Ryzen AI MAX+ 395** (Strix Halo), Radeon 8060S iGPU (gfx1151), 16C/32T |
| RAM | 128 GB LPDDR5X unified, **96 GB carved out to VRAM in BIOS** → Windows sees only **31.6 GB** |
| VRAM | 96 GB carve-out (UMA — shares the same physical pool as system RAM) |
| **Power** | **APU package power limited to 80 W** — the basis of every benchmark in this repo |
| OS | Windows 11 (Chinese Home), build **10.0.26200**, x64 |
| GPU driver | AMD Radeon **32.0.31032.1003** (Adrenalin, 2026-07-29) |
| Vulkan loader | `vulkan-1.dll` **1.4.341.0** (installed by the driver) |
| Windows power plan | Turbo |

> 💡 **Why only 31.6 GB of RAM**: 96 GB is carved out to the iGPU, leaving 31.6 GB for Windows.
> This single constraint drives every trade-off in this project (PLE disk-offload, KV placement, ubatch ceiling) — see §7.

---

## 2. Runtime requirements (to run the prebuilt binaries)

### 2.1 Required

| Dependency | Notes |
|-----------|-------|
| AMD GPU driver | Provides the Vulkan ICD (official Adrenalin driver used here) |
| Vulkan runtime 1.4+ | Installed with the driver; verify with `vulkaninfo --summary` or the version of `C:\Windows\System32\vulkan-1.dll` |
| Disk space | Main model 93.48 GB (87.06 GiB) + MTP draft 2.79 GB (2.59 GiB) + mmproj 0.90 GB (0.84 GiB) + joined sidecar 22.40 GB (20.86 GiB) ≈ **119.57 GB (111.36 GiB)** (excluding backups) |

### 2.2 NOT required (don't waste time on these)

- ❌ CUDA, ROCm/HIP — the Vulkan path needs neither
- ❌ Visual C++ Redistributable / MSVC runtime — `bin/*.exe` are statically linked MinGW builds
- ❌ A Python runtime — only the GGUF tools under `tools/` need it (offline conversion)

### 2.3 Verify the runtime

```cmd
curl http://127.0.0.1:1234/health      → {"status":"ok"}
```

---

## 3. Build requirements (to rebuild from source)

### 3.1 Toolchain used

| Component | Version here | Notes |
|-----------|--------------|-------|
| **MinGW-w64** | **w64devkit 2.9.1 / GCC 16.2.0** | `C:\llama-build\w64devkit`; uses `cc.exe` / `c++.exe` |
| **CMake** | **4.4.0** | |
| Generator | **MinGW Makefiles** (`mingw32-make`) | What this repo was built with — **not** Ninja, **not** Visual Studio |
| **Vulkan SDK** | headers **1.4.309** (`VK_HEADER_VERSION 309`) | `C:\llama-build\vulkan-sdk`, provides `Include/` `Lib/` `Bin/` |
| glslang | `glslang.exe` | Compiles the Vulkan shaders at build time (CMake invokes it) |
| git / git-lfs | 2.55.0 / 3.7.1 | `bin/*.exe` in this repo live in **Git LFS** — install LFS before cloning |
| Python | 3.10 | Only for the GGUF tooling in `tools/` (`gguf-py`, `numpy`, `huggingface_hub` if pulling from HF) |

### 3.2 Configure + build (exactly what was used here)

```cmd
set PATH=C:\llama-build\w64devkit\bin;C:\llama-build\vulkan-sdk\Bin;%PATH%
set VULKAN_SDK=C:\llama-build\vulkan-sdk

cmake -B build -S . -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release ^
      -DGGML_VULKAN=ON -DGGML_NATIVE=OFF ^
      -DCMAKE_PREFIX_PATH=C:\llama-build\vulkan-sdk

cmake --build build -j 16
```

**Three build gotchas**

| Gotcha | Why it matters |
|--------|----------------|
| `-DGGML_NATIVE=OFF` is **mandatory** | Otherwise you get `-march=native` code that crashes on any other CPU (illegal instruction) |
| `-G "MinGW Makefiles"` | MSVC / Ninja builds are untested; every binary here came out of MinGW Makefiles |
| glslang must be on `PATH` | The Vulkan backend compiles shaders to SPIR-V at build time; configure fails without `glslang.exe` |

Output: `build/bin/llama-server.exe` — the very binary shipped in `bin/`.

### 3.3 Upstream sources

| Purpose | Source |
|---------|--------|
| Base fork (qwen4exp Vulkan branch) | `LaurentZuijdwijk/llama.cpp`, branch `vulkan/qwen4exp-rocmfpx` |
| The two modifications in this repo | `src-patches/qwen4exp.cpp` (MTP draft shared head-norm fix), `src-patches/llama-ple-disk.cpp` (PLE disk-offload: POSIX I/O → Windows) |

---

## 4. Model files and layout

See [`MODELS.md`](MODELS.md). Once in place the tree looks like this:

```
<models>\agentionai\Qwen3.8-Flash-Next-ROCmFP4-FAST-imatrix-GGUF\
├── Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16.gguf          <- main model, per-head PLE (original)
├── Qwen3.8-Flash-Next-ROCmFP4-FAST-v2-ple16-JOINED.gguf   <- main model, joined PLE (for --ngram-on-disk)
├── ple_sidecar_joined.gguf                                <- joined PLE sidecar (21 GB, used via --model-ple)
└── mmproj-Qwen3.8-Flash-Next-f16.gguf                     <- vision projector (0.84 GB, must stay on GPU)

<models>\quimmedes\Qwen3.8-Flash-Next-MTP-GGUF\
└── mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf                     <- MTP draft model (2.6 GB)
```

---

## 5. Launch and verify

```cmd
scripts\start_llamaserver_joined.cmd     :: the final config (PLE on disk + ub2048 + MTP + vision)
      or
scripts\install_schtasks.cmd             :: register as a scheduled task (auto-recovery on boot/crash)
```

Verification:

```cmd
curl http://127.0.0.1:1234/health                        :: {"status":"ok"}
scripts\prefill_test.ps1                                 :: 24K-token prefill benchmark
scripts\tg_test.ps1                                      :: 128-token generation benchmark
```

Loading takes about 2 minutes (≈93 GB of weights streamed off disk); logs go to the file each script redirects to.

---

## 6. Measured performance (**at the 80 W APU power setting**)

### 6.1 Final config (PLE on disk + ub2048 + MTP)

| Scenario | Result | Notes |
|----------|--------|-------|
| Prefill, 24K tokens | **299 t/s** | PLE table (20.86 GB) served from disk |
| Generation, short context | **14.5 t/s** | MTP active, acceptance ≈ 67% |
| VRAM usage | **71 GB / 96 GB** | 22 GB spare — enough for a 100K context |

### 6.2 Long context (same machine, same 80 W setting)

| Scenario | Result | Notes |
|----------|--------|-------|
| Prefill, 90K tokens | **≈ 219 t/s** | Normal decay with context length |
| Generation, 90K ctx (KV in host RAM, `--no-kv-offload`) | **14.4 t/s** | Saves VRAM, but attention walks the whole KV set in host memory |
| Generation, 90K ctx (**KV in VRAM**, `-ctk/-ctv q8_0`) | **≈ 30 t/s** | Roughly double, at the cost of VRAM |

> ⚠️ §6.1 and §6.2 come from **different sessions with different flag sets** — treat them as order-of-magnitude references.
> For a fair comparison, pin down: power profile (80 W), context length, KV placement, and whether MTP is on.

### 6.3 Control: per-head PLE, no disk-offload

| Scenario | Result | Notes |
|----------|--------|-------|
| Prefill, 24K tokens | 370 t/s | Without PLE disk-offload |
| Generation, short context, **KV in VRAM** | ≈ **28 t/s** | 93 GB VRAM — right at the ceiling |
| Generation, short context, **KV in host** (`--no-kv-offload`) | 15–16 t/s | Same VRAM footprint, slower attention path |
| VRAM usage | 93 GB / 96 GB | 3 GB left → no room for a 100K context plus vision |

> The two generation rows differ **only** in where the KV cache lives — that is the ~45% swing, and it is the same lever reported in §6.2.

**Takeaway**: PLE disk-offload trades roughly 20% prefill for 22 GB of VRAM headroom — which is what makes a 100K context *plus* vision possible without crashing.

---

## 7. Environment-level pitfalls (all hit in practice)

| # | Pitfall | Conclusion |
|---|---------|-----------|
| 1 | `--load-mode none` | **On Windows this fork requires `--load-mode auto`**; `none` kills the process |
| 2 | `--ubatch-size 4096` | Always fails with a 96 GB carve: with vision → mmproj load failure; without → `ggml.c: GGML_ASSERT(ctx->mem_buffer != NULL)` (host malloc failure). **2048 is the ceiling** |
| 3 | Windows sees only 31.6 GB RAM | The ~180 B model (≈93 GB of weights) + KV + draft can never all fit in host memory → PLE disk-offload is a *requirement*, not a tuning trick |
| 4 | KV in host vs VRAM | Host saves VRAM but 90K generation drops to 14 t/s; moving KV to VRAM (quantized q8_0) gives ≈ 30 t/s |
| 5 | Repeatedly loading the model (176.9 B tensor parameters) | Host RAM fragments → the 862 MB mmproj host-visible buffer fails to allocate → **reboot is the only fix** |
| 6 | Process management | Don't launch the server with `start /min` (it gets reaped with the parent session, leaving orphans). Use `schtasks /run` or WMI |
| 7 | File pre-warming | Useless when free physical RAM < 10 GB; Windows simply won't retain the cache |

---

## 8. Optional: the HIP backend path (experimental, not adopted)

ROCm/HIP was also evaluated on this machine. Recorded here so nobody repeats it:

| Item | Content |
|------|---------|
| Requirements | **AMD HIP SDK 7.2** (`HIP_PATH=C:\Program Files\AMD\ROCm\7.2\`) + `ggml-hip.dll` |
| Build | Official `b10868` sources + patches, `-DGGML_HIP=ON -DGGML_BACKEND_DL=ON`; 143 targets built, gfx1151 enumerated fine |
| Result | **Not recommended**: long-context attention at head_dim=256 is gated by the upstream `fattn` scheduler's ≤128 guard; forcing it through with a custom kernel hangs (observed). The expected compute win never materializes |
| Verdict | This model runs on the **Vulkan** path. HIP stays a lab note — full write-up in [HIP_NOTES.md](HIP_NOTES.md), artifacts attached to the [release](../../releases) for reproduction only |

---

## 9. Reproduction checklist

- [ ] A Strix Halo machine with the 96 GB VRAM carve (or equivalent unified-memory capacity)
- [ ] Windows 11 + a GPU driver exposing Vulkan 1.4+
- [ ] Power profile set to **80 W** (needed to compare against the numbers above)
- [ ] ≥ 130 GB free disk
- [ ] The four model files placed as in `MODELS.md`
- [ ] `git clone` with **git-lfs installed** (`bin/*.exe` are LFS pointers)
- [ ] Run `scripts\start_llamaserver_joined.cmd`, wait ~2 minutes
- [ ] `curl /health` returns ok → done
