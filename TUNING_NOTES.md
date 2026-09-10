# Tuning notes — what actually moves the needle

> Field notes from getting an **87B MoE (Qwen3.8-Flash-Next architecture)** to run well on a single
> **Ryzen AI MAX+ 395 (Strix Halo) / 96 GB VRAM carve-out / Windows + Vulkan** box.
> Every number below was measured at the **80 W APU package-power limit** — see [ENVIRONMENT.md](ENVIRONMENT.md).

There are only **four levers** that matter on this machine. Everything else is noise:

| Lever | Effect | Where |
|-------|--------|-------|
| **PLE n-gram table → disk** | frees ~22 GB VRAM (93 → 71 GB), costs ~20 % prefill | `--ngram-on-disk` |
| **KV cache placement** | ~2× long-context decode (host → VRAM) | `-ctk/-ctv q8_0` vs `--no-kv-offload` |
| **ubatch size** | hard ceiling at **2048** once MTP is on | `-ubatch-size` |
| **MTP draft (speculative)** | decode ×2.6–4.4 on the same config | `-md` + `--spec-type draft-mtp` |

---

## 1. MTP speculative decoding — the biggest single win

Decode on the same machine, same model, same launch config:

| | Decode (t/s) |
|---|---|
| No MTP | **8.0** |
| MTP on, short Q&A | **21.3** (acceptance 59 %) |
| MTP on, long-form text | **24–35** (acceptance 60–94 %) |

Acceptance rate is driven by **text type, not sampler temperature**: a concept explanation scored
0.58 at temp 0.5 / 0.7 / 0.9 alike, while free-form output (recommendations, summaries) drops to
0.22–0.35 and highly repetitive text reaches 0.9+. Net: expect ~60–80 % on natural text, and expect
the speedup to shrink on very open-ended generation.

**The price you pay.** Enabling MTP forces `-ubatch-size` down from 4096 to 2048 (see §3), which costs
~10 % prefill. On the same 90K-token document with 500 output tokens:

```
before MTP:  prefill 368 s + decode 85 s = 453 s
with MTP:    prefill 410 s + decode 19 s = 429 s
```

Longer context and longer answers make the trade better. Repeat the arithmetic for your own workload.

Required patch: the draft model's `NEXTN_SHARED_HEAD_NORM` tensors are not handled by the upstream
qwen4exp draft loop — without the patch the draft loads but acceptance stays at 0. See
[`src-patches/PATCHES.md`](src-patches/PATCHES.md).

## 2. KV cache placement — the long-context lever

Same model, same context length (90K), only the KV cache location changes:

| KV location | Decode @ 90K |
|---|---|
| Host RAM (`--no-kv-offload`) | **14.4 t/s** |
| **VRAM** (`-ctk q8_0 -ctv q8_0`) | **≈ 30 t/s** |

Host-resident KV looks attractive because it is free VRAM, but every attention step then walks the
whole KV set through host memory. If VRAM is available, **put the KV cache in VRAM** — it is the
single biggest long-context lever found here.

## 3. The ubatch ceiling is a real wall (2048)

| ubatch | Outcome |
|--------|---------|
| 1024 | Works, but prefill drops to ~200 t/s |
| **2048** | **Works — this is the ceiling with 100K context + MTP** |
| 3072 | Fails: `failed to allocate Vulkan_Host buffer of size 786542656` → `failed to create MTP context`, `ErrorOutOfDeviceMemory` |
| 4096 | Fails: `ggml_init()` host `malloc` failure (`GGML_ASSERT(ctx->mem_buffer != NULL)`) |

Note the two failure modes are **different resources**: 3072 dies on **Vulkan VRAM** (the MTP draft
context buffer is ≈ **256 KB per token × ubatch**: 524 MB at 2048 fits, 786 MB at 3072 does not),
while 4096 died on **host memory** before that. Both look like "OOM", neither is the same OOM.

## 4. Prefill decays with context — measured curve

100K-context config (`-c 102400 -b 2048 -ub 2048`, KV in VRAM, MTP on), 80 W:

| Prompt tokens | Prefill (t/s) | Decode (t/s) | MTP acceptance |
|---|---|---|---|
| 4.5K | **402.8** | 30.6 | 83 % |
| 8.4K | **381.3** | 35.0 | — |
| 21.8K | **344.4** | 24.7 | 88 % |
| 45.2K | **277.5** | 22.0 | 84 % |
| 90.4K | **220.6** | 25.7 | 94 % |

This is physics, not a tuning failure: at 90K every new token must attend to ~45K keys on average.
Typical single-document workloads land in the 8–20K region, i.e. **340–400 t/s prefill**.

> Measurement tip: randomise a unique prefix in every benchmark prompt, otherwise the prompt cache
> silently serves you a cached prefill and the numbers are meaningless.

## 5. Verifying that PLE disk-offload is actually working

The PLE table is **28.8 GB**. With `--ngram-on-disk` it should never enter VRAM — but the log is
actively misleading:

```
unused tensor per_layer_token_embd.weight (size = 28800138240 bytes) -- ignoring
```

That line is a **false alarm** from the tensor-skip path, not a failure. The real evidence
(`... stays on disk`) is emitted at **INFO level and suppressed at default verbosity**. Add a probe
and re-run with `-lv 4` to see it. Before doing that, we spent time believing disk-offload was a
no-op while it had been working all along.

Layout matters: disk-offload requires the PLE table to be a **single joined tensor**. A per-head
layout (16 small tensors) is skipped by the fork and silently defeats `--ngram-on-disk`
(see [`tools/`](tools/) for the low-memory per-head → joined converter).

## 6. Pitfalls that cost us days

| # | Symptom | Root cause / fix |
|---|---------|------------------|
| 1 | `cudaMalloc failed: out of memory` while **107 GB of VRAM is free** | On Windows, large GPU allocations count against the **system commit charge** (RAM + pagefile), not just VRAM. Ours was exhausted (120.8 / 127.6 GB) by a leaked process. Check commit charge, not just VRAM |
| 2 | A killed process stays visible and keeps holding memory | Driver-level leftovers can survive `taskkill /f` and `Stop-Process -Force` ("no running instance"). Terminating via `kernel32.TerminateProcess` from Python worked where the shells refused |
| 3 | Server dies as soon as the launching shell exits | `start /min` / `Start-Process` children are reaped with the launcher's job object. Launch detached: `schtasks /run /tn <task>` or WMI `Invoke-CimMethod Win32_Process Create` |
| 4 | No auto-start after reboot | Scheduled tasks created with an **in-the-past one-shot trigger** never fire. `schtasks /sc onlogon` needs admin rights; a per-user `HKCU\...\Run` key (calling a `.vbs` wrapper for a hidden window) works without it |
| 5 | Console hangs mid-generation | Single slot + client disconnect + a generation that never emits EOS = the slot never frees. Restart, or run more slots |
| 6 | `--load-mode none` | Crashes on this fork/Windows combination; **`auto` is mandatory** |
| 7 | mmproj refuses to load after a few reloads | Host RAM fragmentation — an 862 MB host-visible buffer can no longer be allocated contiguously even with plenty of free RAM. Reboot is the only fix |
| 8 | File pre-warming does nothing | With < 10 GB of free physical RAM, Windows will not retain the cache |

## 7. What did *not* help

- **HIP / ROCm path** — long-context attention at `head_dim = 256` is gated by the upstream `fattn`
  scheduler's ≤ 128 guard; forcing it with a custom kernel hangs. Full write-up in
  [ENVIRONMENT.md §8](ENVIRONMENT.md).
- **KV q4_0 instead of q8_0** — traded ~2.8 GB of VRAM for measurable long-context quality loss;
  not worth it for a 100K context when q8_0 already fits.
- **ubatch above 2048** — see §3: hard wall, two different OOMs.
- **Putting mmproj on the CPU** — the 862 MB host-visible buffer fights the model for the same
  unified pool and reliably crashes.

## 8. Reproducing these numbers

1. Match the machine and the **80 W** power profile ([ENVIRONMENT.md](ENVIRONMENT.md)).
2. Launch with `scripts\start_llamaserver_joined.cmd` (PLE on disk + ub2048 + MTP + KV in VRAM).
3. Wait ~90 s for the server to report ready, confirm `curl http://127.0.0.1:1234/health`.
4. Use a **unique random prefix** per prompt, and record context length + KV placement + MTP state
   with every figure — numbers measured under different flag sets are not comparable.
