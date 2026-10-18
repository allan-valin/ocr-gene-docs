# Desembarque — Windows test report

**Date:** 2026-10-17
**Tester:** Allan (developing on Linux, testing on Windows 11 Home)
**How installed:** downloaded the repo as a ZIP (simulating a non-programmer who does not use a terminal), then double-clicked `Desembarque.bat`.
**Repo:** https://github.com/allan-valin/ocr-gene-docs
**Audience for this report:** the Linux Claude that will do the fixes.

This is a hand-off from the Windows side. It pairs each observed symptom with
the exact code that causes it, so the fix can start from the file and line, not
from a repro. File references are `path:line`.

**Verified against the running server** (`http://127.0.0.1:8765`, 2026-10-17):
`/api/engine` reports paddle + kraken second-reading both ready; the cached
transcription for `BR_APESP_MI_LP_010999.pdf` p.6 holds **46 rows** (42 with text),
re-rowed by the PP-OCRv6 page-column pass — i.e. the page finishes and is **not**
empty. The "empty table" is a mid-run appearance, not the result (see §3–§4).

---

## TL;DR — what to change, in priority order

1. **Ship a real Windows installer** that bundles/fetches Python itself, builds
   `.venv-ocr`, and installs all three tiers — so the user never edits PATH and
   never watches a 30-minute blank-ish window. (Keep the current GUI installer as
   the fallback for other platforms.)
2. **Add an uninstaller.** Everything already lives in `.venv-ocr` plus one model
   cache — removing those two leaves no trace. This is almost free given the venv
   design; it just needs a button/script.
3. **Fix the per-page progress box** so it (a) is driven by *countable steps*
   (bands cut, names read), not by a hard-coded 20-second clock, and (b) does **not**
   auto-minimize to the corner until the page is actually finished. Today it hides
   itself the moment the first band arrives, which reads as "done" while the table
   is still empty.
4. **The band/line detector found only 5 of ~33 lines** on hospedaria p.6 — this is
   already logged in `PROGRESS.md` (2026-10-17: "the bands were wrong (5 for 33
   lines)"). It is the root cause of both the empty table *and* the slow/misleading
   progress. Worth confirming it's on the backlog.
5. **The GPU is idle for the wrong reason.** This laptop has an NVIDIA RTX 4050 (6 GB),
   but the launcher installed **CPU-only** `torch` and `paddlepaddle`, so both engines
   run on the CPU — hence ~4 min/page instead of ~30 s. Fix: the installer should
   detect the GPU and install the matching accelerated wheels (device selection is
   already automatic). **Requirement (Allan): if a GPU is present it must be usable** —
   NVIDIA/CUDA fully (ship now), Apple/MPS and AMD/Intel via the best path each stack
   allows (even accelerating just the kraken reader is ~73% of a page); CPU is the
   fallback, never the ceiling. Add a **CPU/GPU toggle** showing a calibrated per-page
   estimate per device. (Full analysis in §5.)
6. **Warm up the readers on "Ligar," with a toggle.** The ~4 min was a *cold* run —
   model load counted inside the first page. Warm the engines at startup and show the
   progress box saying "aquecendo o leitor…", so the first read isn't mysteriously
   slower. Make it a toggle: a search-only/lookup session doesn't need the readers
   loaded. (§6)
7. **Feature idea — "read only this area/column."** For double-page scans and tables
   with no ruled lines, let the user draw/define the column(s) to read and OCR just
   those, with a tab separating the custom read from the full-page read. (§7)

---

## 1. Installation

### What happens today

- `Desembarque.bat:3-10` looks for `pyw`/`pythonw`/`py`/`python` on PATH. If none is
  found it prints "install Python 3.11/3.12 from python.org and tick *Add
  python.exe to PATH*". **This is the exact step a non-programmer cannot do.**
- `README.md:120` repeats it: "Windows — python.org 3.12 with *Add python.exe to
  PATH*".
- Once Python is on PATH and the launcher opens, `launcher/core.py:89-116`
  (`install_command`) builds the venv and pip-installs the tiers:
  - `python -m venv .venv-ocr`
  - `pip install --upgrade pip`
  - viewer: `requirements.txt` (~100 MB)
  - engine: `requirements-ocr.txt` (paddleocr, ~1.5 GB)
  - handwriting: CPU torch + `requirements-kraken.txt`, then fetches the kraken
    model to `~/.cache/kraken` (~1 GB)
- The install runs as subprocesses and streams stdout into the log box
  (`launcher/desembarque_launcher.py:226-236`). **There is no progress bar** — just a
  scrolling log — and the status line only says "leva alguns minutos"
  (`desembarque_launcher.py:222-223`).

### Problems observed

1. **"Add python to PATH" is a dealbreaker for the target user.** The whole point
   (per the design spec and `launcher/core.py:1-8`) is "no terminal, no venv, no
   commands." Requiring a manual PATH edit in the python.org installer breaks that
   promise on the very first step.
2. **~30 minutes to finish, with no progress bar.** Large downloads (paddle ~1.5 GB,
   torch+kraken ~2 GB) over the streaming log look like a hang. `core.py:12-13`
   even acknowledges "a blank window for ten minutes looks broken" — but the cure
   (showing *what* is installing) is there without the cure for *how far along* it is.

### Recommendation (what the user asked for)

- **A native installer with a GUI is acceptable even if it downloads components at
  install time** rather than bundling everything. Priorities, in the user's words:
  "just so that we have a native installer GUI at least."
- The installer **must prepare everything** so the user does nothing manual:
  - Fetch/embed a known-good Python (3.11/3.12) — do **not** rely on a
    system Python or on PATH. Candidates:
    - **Inno Setup** (free, native Win32 GUI, good progress UI) driving a bundled
      *embeddable* CPython zip, or downloading the python.org installer and running
      it silently with `InstallAllUsers=0 PrependPath=0 Include_launcher=1`.
    - **WiX/MSI** if a corporate-friendly MSI is wanted.
    - A **PyInstaller/Briefcase one-folder build** of the launcher + a pinned Python,
      with the heavy tiers (paddle/torch/kraken) fetched post-install into `.venv-ocr`.
  - After laying down Python, run the existing `install_command` logic
    (`core.py:89-116`) to build `.venv-ocr` and install the tiers — that logic is
    already correct and reusable; the installer just needs to call it with the
    bundled interpreter as `sys.executable`.
  - **Show a progress bar during download/install** (see §3 on how; even pip's
    per-package count is better than nothing).
- Keep `Desembarque.bat` and the python.org path as the documented *fallback* for
  Linux/macOS and for advanced users, but it should not be the primary Windows path.

---

## 2. Uninstall — "no traces left behind"

### What happens today

- There is **no uninstaller** and no uninstall entry in Add/Remove Programs (because
  there is no installer).
- The good news, already true by design: **almost everything lives in one place.**
  - `launcher/core.py:25` — `VENV = ROOT / ".venv-ocr"`. The viewer, engine, and
    handwriting Python packages all go here (`core.py:94-113`).
  - The **only** thing outside the folder is the kraken model cache:
    `launcher/core.py:55` — `~/.cache/kraken/ppocrv6-hist/medium.safetensors`
    (and pip's download cache, which is shared and should probably be left alone).
  - Settings live in-tree at `launcher/core.py:26` (`launcher/settings.json`).
  - Transcriptions live in a `transcriptions/` subfolder next to the user's PDFs
    (per the help text, `core.py:263-266`) — user data, must **not** be deleted by an
    uninstall.

### Recommendation

- Add an **"Uninstall / Remove everything installed"** action. Because of the venv
  design, a clean uninstall is essentially:
  1. delete `.venv-ocr/`
  2. delete `~/.cache/kraken/ppocrv6-hist/` (the model)
  3. optionally delete `launcher/settings.json`
  4. **leave** the user's PDFs and their `transcriptions/` folder untouched
- If a native installer is adopted, wire this into its standard uninstaller
  (Add/Remove Programs). Offer a checkbox "also remove the downloaded models
  (~2.5 GB)" so a reinstall can reuse them if the user prefers.
- Nice touch: the launcher could expose "free up space / remove the engine" that
  just removes a tier's packages from `.venv-ocr`, mirroring the per-tier install.

### Migration from the old manual/ZIP install — reuse or scrub, never duplicate (user request)

After this Windows test there is **already a `.venv-ocr` on disk** from the current
ZIP/manual path — on this machine it's ~2.5 GB of **CPU-only** wheels inside the
unzipped folder on the Desktop (`C:\Users\allan\Desktop\ocr-gene-docs-main\.venv-ocr`).
When the new native installer ships, it **must account for that pre-existing venv** so
the user doesn't end up with two copies wasting several GB, or a stale CPU venv shadowing
a new GPU one. Concretely, the new installer/launcher should, on first run:

1. **Detect any existing `.venv-ocr`** — both in the install directory *and* in the old
   locations a tester/early user is likely to have (the unzipped ZIP folder, the
   Desktop, Downloads). `readiness()`/`_site_has()` (`core.py:58-75`) already know how
   to inspect a venv; reuse that to validate one found elsewhere.
2. **Decide: reuse vs. scrub.** If the found venv is valid *and* matches the wanted
   device (e.g. GPU install but the old venv is CPU-only — detectable via
   `torch.version.cuda` / `paddle.is_compiled_with_cuda()`, see §5), either **reuse it
   in place** or **re-point** the new install at it; otherwise **scrub it** (delete the
   whole `.venv-ocr`) and build fresh. Do not build a second venv next to a usable one.
3. **Never leave an orphan.** If the install moves to a canonical location (e.g.
   `%LOCALAPPDATA%\Desembarque`), the installer must remove the old `.venv-ocr` it
   migrated from, so there's exactly one venv afterward. Same rule for the model cache
   (`~/.cache/kraken`), which is already shared and location-independent — reuse it,
   don't re-download.
4. **De-dupe on repeat installs/upgrades.** Running the installer again must detect the
   existing venv and reuse/upgrade it (the current `install_command` is already
   idempotent — `core.py:96-99` only builds the venv "when it is not there" and pip
   skips cached packages), not create a parallel one. The CPU→GPU switch (§5) is the
   one case that should *replace* wheels in the existing venv rather than make a new one.

The uninstall rules above still apply to whichever single `.venv-ocr` survives
migration, so "no traces left behind" holds end-to-end.

---

## 3. The progress bar — drive it by steps, not by a clock

This is the richest area and maps directly to the user's two complaints: the
"estimated 20 s" that became 51 s, and the box minimizing to the corner before the
page was actually done.

### How the per-page progress works today

- The box is `#progress` in `prototype/review.html` (CSS at `:255-279`, markup at
  `:327-331`). It has three bars: **folder**, **document**, **page**.
- Driving code: `renderProgress()` at `review.html:1154-1201`, fed by two pollers —
  `pollJob()` (`:1254-1274`, every 600 ms) and `pollLive()` (`:1248-1253`).
- **The page bar is the problem.** `review.html:1181-1187`:
  - If live data reports `total` names cut, it shows `done of total` — this is the
    *good* path, a real step count.
  - **But before any band/name is cut**, it falls back to a **hard-coded clock**:
    `setBar(pg, Math.min(mine.page_s, 19), 20, "...lendo há N s (uma página leva uns
    20 s)")` — i.e. it fills the bar against a fixed 20-second expectation.
    `review.html:1184-1186`.
- The "~20 s" number is baked in several places as prose too: `core.py:250-251`
  (help), `review.html:1186`, `:1193`.

### Why "estimated 20 s → actual 51 s"

The 20 s is a **constant**, not a measurement. On hospedaria p.6 the first phase
(band/line detection + the first reads) took 51 s, so the clock-driven bar pinned at
~95% ("lendo há 19 s" capped) and then *sat there* for 30+ extra seconds — the
classic "stuck progress bar." Time-based estimation cannot work when the time isn't
reliable, which is exactly the user's point.

### Why "5 of 30+ lines" during the read — and why the table *looked* empty mid-run

**Important framing (corrected after re-testing live):** the page is **not** empty
when it finishes. The stored result for p.6 has **46 rows** (42 with text) — verified
against the running server, cached at
`transcriptions/016bdc178258…json`. The "empty table" is a **transient state during
the run**, not the end state. This section is about the *progress timeline* the user
saw, which is what confuses: an empty table + a minimized box reads as "finished"
while work is still going.

The sequence the user described, step by step:

1. The first phase ("initial read") reports only **5 bands for ~33 lines** and takes
   ~51 s — not 20. The 5-band miscut is **already a known, logged defect**:
   `docs/PROGRESS.md` (2026-10-17 entry) says verbatim *"the bands were wrong (5 for
   33 lines), so a band's name would be the wrong neighbour's."*
2. The page bar is driven against a fake 20 s clock, so it pins near the end and sits
   there for the extra ~31 s (see above).
3. The moment those first bands arrive, the progress box **auto-minimizes to the
   corner** (see §4) — but the table on screen is **still empty**, because names
   haven't been read into rows yet.
4. User reads "box in the corner + empty table" as **done**. It isn't. The read
   continues and eventually fills in (the engine re-rows via the kraken
   page-column pass — `second_reading.rerowed:[6]` in the cache — producing the 46
   whole-line rows).

So there are two independent defects stacked on top of each other: the **miscut
grid** (5 vs 33) and the **premature minimize**. Either one alone would be
confusing; together they strongly read as "finished and empty."

- **Fix the detector and the step count becomes meaningful**, because `done/total`
  stops being "0 of 5" on a page that really has ~33 lines.
- **Fix the minimize (§4) and the empty-looking table stops masquerading as a final
  result**, regardless of the detector.

### Recommendation — count the steps you already have

The backend already knows the steps; the UI just needs them surfaced consistently:

1. **Expose a determinate step model per page** from the engine/live endpoint. Good
   candidate phases, each countable:
   - rasterize page (1 step)
   - detect table grid / cut bands → yields **N bands** (this N is the denominator)
   - read each band → `done/total` (already present as `mine.done/mine.total`,
     `review.html:1174,1182`)
   - post-process/fields
   Weight the bar across phases (e.g. grid=10%, reads=85%, fields=5%) so the first
   51-second phase advances the bar instead of pinning it.
2. **Delete the 20-second fallback** at `review.html:1184-1186`. When there is no
   countable step yet (grid not done), show an **indeterminate/busy bar**
   (`.bar.none` already exists and animates, CSS `:271`) with a truthful label like
   "procurando as linhas da tabela…" — not a fake percentage against a fixed clock.
3. The `Job` dataclass (`desembarque/jobs.py:24-49`) currently tracks only
   `page`/`total` (pages). Consider adding per-page step fields (`phase`,
   `step`, `steps`) so `pollJob` has a real denominator even before live bands
   arrive. `pollJob` at `review.html:1257` computes `pct` from `page/total` (pages),
   which is coarse for a single-page job (`total=1` → jumps 5% → 100%).

---

## 4. The "it looks finished" bug — box minimizes mid-run while the table is still empty

This is the user's core UX complaint: *"the progress bar box was minimized/hidden on
the corner, so you get confused that it is finished, but only an empty table is
shown — so only hide progress when all is finished."* It is about the **sequence**
of the progress UI during a run, not the final output (the page does finish; §3).

### Cause (found in code)

`review.html:1196-1198`:

```js
const liveHere = lv && D && lv.file===D.file && lv.page && (lv.bands||[]).length;
const mini = PG.user==="mini" || (PG.user!=="full" && liveHere);
el.classList.toggle("mini", !!mini);
```

The box **auto-minimizes to the corner as soon as the first band arrives**
(`liveHere` becomes true when `lv.bands.length > 0`). The intent is documented at
`review.html:1143-1146` ("Hidden to a corner ... by itself when the open document is
the one being read: its rows arriving are the progress"). The `.mini` CSS parks it at
`inset:auto 14px auto auto; top:46px` and hides the hint (`:274-279`).

The assumption — "rows arriving in the table *are* the progress, so the big box can
step aside" — breaks during the run: the moment the first bands arrive the box jumps
to the corner, but the rows haven't been read into the table yet, so the screen is
"corner box + empty table" while work continues. The user reasonably reads that as
"finished." (The miscut 5 bands make it worse, but the timing bug exists regardless
of how many bands are found.)

### Recommendation

- **Do not auto-minimize based on `bands.length > 0`.** Only minimize when the user
  explicitly clicks "Esconder" (`PG.user==="mini"`, handled at `review.html:1203`), or
  — if auto-minimize is kept — only once the page is *actually complete*
  (`job.status==="done"` / live `done===total` and `total>0`).
- Keep the box visible (not `hidden`, not `mini`) until the whole task finishes.
  Per the user: **"only hide progress when all is finished."** The teardown already
  happens correctly on completion in `finishTranscription()`
  (`review.html:1275-1276`) and when `renderProgress` sees nothing running
  (`:1158`) — the bug is purely the premature `mini` toggle.
- While a page is mid-read with a visible-but-incomplete table, show a clear
  "lendo… X de Y linhas" state (the `#stat` line at `review.html:1245` already does
  this for live reads) so a partial table never reads as a final one.

---

## 5. Transcription speed — the GPU is present but unused (root cause found)

### The finding, verified in the venv on this machine

The user's hypothesis is essentially correct, with a sharper cause: it is **not that
Windows can't use the GPU** — it's that **the launcher installed CPU-only wheels**, so
both engines run on the CPU even though a capable GPU is sitting right there.

Measured on the test machine (`.venv-ocr/Scripts/python.exe`):

| Component | Installed build | GPU visible to it? |
|---|---|---|
| **GPU hardware** | NVIDIA GeForce **RTX 4050 Laptop, 6 GB** (`nvidia-smi`) | — |
| **torch** (kraken second reading) | `2.14.0+cpu` | `torch.cuda.is_available() == False` |
| **paddlepaddle** (engine) | `3.3.1`, `is_compiled_with_cuda() == False` | no |

`torch.backends.{cuda,mps,xpu}` all report `False`, `paddle.is_compiled_with_{cuda,
rocm,xpu}` all `False` — the CPU wheels expose **no accelerator backend at all**. So
`device_for()` for both engines returns `"cpu"`:
- paddle: `engine_paddle.py:730-745` (`gpu:0` only if `is_compiled_with_cuda()` and a
  CUDA device is counted)
- kraken: `secondreading.py:41-56` (`cuda:0` only if `torch.cuda.is_available()`)

**Why the CPU wheels got installed:** the launcher's install step is hard-wired to CPU
torch (`core.py:111-113`, `--extra-index-url https://download.pytorch.org/whl/cpu`) and
to the default CPU `paddlepaddle` (`requirements-ocr.txt`). The CUDA install path
*exists* but is a manual, commented recipe in `requirements-kraken.txt:15-24` that no
non-programmer will ever run. The code picks the device "by what the install can see,
never by a flag" — so the install is the only lever, and it's set to CPU.

### Where the ~4 minutes goes (measured)

Measured by re-reading p.6 on the **warm** server (models already loaded), polling
`/api/job` + `/api/live` with wall-clock timestamps:

| Phase | What runs | Time |
|---|---|---|
| **0 → 48 s** | **paddle** detection + recognition — `eng.transcribe_page()` (`serve.py:559`). Produced the 5 (miscut) bands. | **~48 s** — matches the user's "51 s initial read" |
| **48 → 181 s** | **kraken** second reading, re-rowing ~46 lines one at a time on CPU torch — `secondreading.read_record()` (`serve.py:615`) | **~133 s (~73% of the page)** |
| **Total** | one page, warm | **181 s (~3 min)** |

A second run from a **freshly started (cold) server** measured **183 s total**
(paddle ~46 s, kraken ~137 s) — i.e. **cold ≈ warm** on this machine. That was a
surprise worth recording honestly: the model-load tax was negligible here because the
OS **disk cache still held the model files** from the session minutes earlier (the
process was cold, the disk was warm). A truly cold first run — first launch after a
reboot, model files read from SSD for the first time, possibly a one-time paddle
compile (the venv even warns "No ccache found") — is what plausibly produced the user's
**~4 min**: the extra ~1 min over the measured 3 min is that cold-disk/first-run
model load, which I did **not** reproduce here and so cannot quantify precisely.

Takeaways:
- **The kraken CPU second-reading is the dominant cost** (~133–137 s, ~73% of the
  page), because it reads every line serially on CPU torch. This is the phase a GPU
  would help most.
- **The steady-state page is ~3 min on CPU, warm or process-cold.** The first run after
  a reboot is slower by a model-load/compile tax (the ~1 min the user likely saw);
  warming up (§6) moves that tax off the first *read* and onto startup where it's
  explained.
- Both phases are serial and both on CPU; there is no GPU work at all (§ above).

Contributing factors beyond raw CPU:
- the miscut grid (§3) can cause extra/duplicate work;
- first-call model warm-up (paddle + kraken load) is counted inside the first page;
- `PROGRESS.md` (2026-10-17) notes kraken + paddle together are heavy ("two workers on
  a card, four on the CPU").

### Fix 1 — the installer should detect an NVIDIA GPU and install CUDA wheels

The device selection is already automatic; only the *install* needs to change. The
installer (see §1) should run `nvidia-smi` / check for an NVIDIA driver and, if found,
install the CUDA builds instead of the CPU ones — the recipe already exists at
`requirements-kraken.txt:15-24`:
- `torch==2.14.0` + `torchvision==0.29.1` from the default (CUDA) index
- `paddlepaddle-gpu==3.4.0` from the PaddlePaddle CUDA index
Then `device_for()` returns `gpu:0`/`cuda:0` with no code change. On a 6 GB card,
`index_workers()` already caps to 2 GPU workers (`PROGRESS.md` 2026-10-17).

### Fix 2 — a CPU/GPU toggle in the launcher, with an estimated per-page time (user request)

Add a control in the launcher window (and/or the check window) letting the user choose
**how to read**, so they understand the trade before committing to a long run:

- **A radio/dropdown: "Ler usando: GPU (NVIDIA) · CPU".**
  - Disable/grey the GPU option when no CUDA build is installed, with a one-line
    "instalar suporte a GPU" that triggers the CUDA reinstall from Fix 1.
  - Persist the choice in `launcher/settings.json` (alongside `folder`/`port`) and pass
    it to the server as an env override — `DESEMBARQUE_WORKERS` already exists
    (`serve.py:169-174`); add a `DESEMBARQUE_DEVICE=cpu|gpu` that forces
    `device_for()` instead of auto-detect, so the toggle has teeth even when both
    builds are present.
- **Show an estimated time per page next to each option**, e.g.
  *"GPU: ~X s por página · CPU: ~Y s por página"*, and multiply by the page count of
  the chosen document/folder so the user sees "~N min para 9 páginas". Numbers should
  come from a cheap calibration (time the first page, then extrapolate) rather than a
  hard-coded constant — the hard-coded "20 s" is exactly what misled the user (§3).
  Until calibration exists, seed with the **measured CPU figure (~180 s/page on this
  RTX-4050-class laptop — warm and process-cold both ~181–183 s, §5)** and fill in the
  GPU figure from a CUDA run. The real number is **~3 min/page**, i.e. ~9× the "20 s"
  the help text and progress bar currently promise — the estimate must be honest or it
  recreates the same "it looks stuck/finished" confusion. (A first run after reboot is
  ~1 min slower from model load; that's the §6 warm-up case, not steady state.)

### Any present GPU must be usable (user directive — requirement, not nice-to-have)

**Allan's call, on the record:** *"it's not the point of being practical or not, it is
needed … obviously CPU is the universal fallback, but if a GPU is presented it must be
usable."* So the requirement is: **detect whatever GPU is present and use it through
the best path the stack supports**, with CPU only as the last resort. The matrix below
is therefore *how to make each GPU usable*, not whether to bother — honest about each
path's current ceiling so Linux Claude knows the real engineering cost per family.

| GPU type | kraken (PyTorch) path | engine (paddle) path | How usable today |
|---|---|---|---|
| **NVIDIA (CUDA)** | ✅ `torch` CUDA wheels | ✅ `paddlepaddle-gpu` | **Fully — ship this now (Fix 1).** Both engines accelerate. |
| **Apple Silicon (MPS)** | ✅ `torch` MPS backend works | ❌ paddle = CPU on Mac | **Partial** — kraken (the 73% phase) on GPU, paddle on CPU. Still a big win since kraken dominates. |
| **AMD discrete** | ROCm (`torch` ROCm wheels) — **Linux only**, select cards | paddle ROCm is datacenter-only | **Linux: best-effort** (kraken on ROCm). **Windows: via DirectML, see below.** |
| **Intel Arc / iGPU** | `torch` XPU (IPEX) or DirectML | none native | **Best-effort via DirectML / XPU** (kraken only). |
| **Any DX12 GPU (AMD/Intel iGPU, Windows)** | `torch-directml` device — works for many models, lags mainline, kraken/Lightning path needs testing | paddle has no DirectML | **Best-effort** — accelerates kraken where it runs; validate per card. |
| **CPU** | ✅ | ✅ | Universal fallback. |

**What this means for the build:**

1. **NVIDIA is the mandatory, fully-supported case — implement it now (Fix 1).** This
   alone covers the test machine (RTX 4050) and most gaming/workstation laptops.
2. **Make acceleration general, not NVIDIA-hardcoded.** `device_for()` already picks
   `cuda` / `mps` by capability (`secondreading.py:49-56` already checks CUDA; extend
   it to also return `mps`, `xpu`, or a DirectML device when present). The installer
   should detect the GPU vendor (`nvidia-smi`, `wmi path win32_VideoController`, Apple
   arch) and install the matching accelerated wheels — CUDA, MPS (default mac torch),
   ROCm (Linux AMD), or `torch-directml` (Windows AMD/Intel) — falling through to CPU
   only if none can be installed.
3. **Even partial acceleration is worth it**, because the kraken second reading is
   ~73% of a page (measured). Getting *that* phase onto any GPU (MPS/DirectML/ROCm)
   roughly matches or beats a full-CPU run even when paddle stays on CPU.
4. **Be honest in the toggle (Fix 2):** label the option with the detected device
   (e.g. "GPU (DirectML — AMD Radeon)") and whether it accelerates both engines or just
   the reader, and show the calibrated per-page estimate for each so the user picks
   with real numbers. The toggle should offer **whatever accelerated device was
   detected and installed**, plus CPU — never hide a present GPU.

Engineering-cost honesty for the hand-off: NVIDIA/CUDA and Apple/MPS are low-risk
(upstream-supported, a wheel choice). AMD/Intel on Windows via DirectML is real but
needs a validation pass on the kraken/Lightning code path — budget time to test it on
an actual AMD/Intel machine, since neither of us has verified that path yet.

### Note on perceived vs. real slowness

Even after acceleration, be honest in the UI: fixing the progress bar (§3/§4) matters
regardless, so a 4-minute CPU run *feels* like visible work rather than a hang, and a
faster GPU run still shows truthful steps.

---

## 6. Warm up the readers on "Ligar" — with a toggle (user request)

### Why

paddle + kraken load their models on the *first* `transcribe_page` / `read_record`
call (lazy init), so that model-load time is silently charged to the first page.
Measured here: warm ~181 s and process-cold ~183 s were **the same**, because the OS
disk cache held the model files (§5). The warm-up tax shows up on a **true** cold run —
first launch after a reboot, or the very first run ever — when the models are read from
disk (and possibly compiled) for the first time; that is the extra ~1 min that plausibly
made the user's run ~4 min. A user who reboots, reads one page slowly, then reads faster
ones, experiences this with no explanation.

Note the server already *reports* ready immediately — `/api/engine` returns
`"available": true` the instant the process binds — but "available" means "the engine
is registered," **not** "models are resident in RAM." So nothing today tells the user
the first read will pay a warm-up tax.

### Proposed behaviour (as the user described it)

1. Click **Ligar** → the browser opens → the **progress box is shown immediately**,
   saying *"aquecendo o leitor… (carregando os modelos)"* with an indeterminate bar
   (reuse `.bar.none`, §3). This replaces the current silence while models load.
2. The server warms the engines in the background on startup (a cheap dummy
   detect+recognise so paddle and kraken both page their weights in).
3. When warm, the box either (a) **closes**, if nothing is queued, or (b) **rolls
   straight into indexing** if the "ler ao ligar" option is on
   (`desembarque_launcher.py:400-402` already kicks off indexing after start — hook the
   warm-up in front of it).

### The toggle (and why)

Add **"Aquecer os leitores ao ligar"**, on by default, in the launcher next to "Ler os
PDFs da pasta ao ligar" (`desembarque_launcher.py:107-108`). Off = a **search/lookup
session**: the user only wants to browse and search already-transcribed records (the
"viewer" tier alone, §1), so loading ~2.5 GB of models is pure waste and startup should
be instant. On = any session that will transcribe.

Implementation notes:
- Persist in `launcher/settings.json` (alongside `folder`/`index`,
  `core.py:162-165`).
- Pass as a flag/env to `serve.py`; expose a `/api/warmup` (POST) the page can call and
  poll, or have the server emit warm-up state through the existing `/api/live` channel
  so the progress box can render it with the same code path as a read.
- Warm-up should respect the device choice from §5 (warm the GPU engines if GPU is
  selected).

---

## 7. Feature proposal — "read only this area / column" (user idea)

### The problem it solves

Two real failure modes the user named:
- **Double-page scans**: one image holds two physical pages, each with its own columns.
- **Tables with no visible rules**: a clear column structure the detector can't find
  because there are no drawn lines — e.g. a left column filled in and a right column
  left blank for later corrections. The whole-page read returns gibberish (exactly the
  p.6 "5 bands for ~33 lines" miscut, §3).

When geometric detection fails, the user currently has no recourse but to accept the
garbage. Give them a manual override: **tell the reader where to look.**

### The idea (as described)

- Add a **selection tool to the scan toolbar** (`#scantools`, `review.html:426-436`,
  where Zoom/enhance live). There is already precedent: a **"Coluna do nome"** crop
  button (`#crop`, `review.html:375`) and `#nameBox`/`#bandBox` overlays on the scan
  (`review.html:439-440`) — this feature generalises that from one hard-coded column to
  **user-defined regions**.
- Rather than a single rectangular marquee, the tool is **"adicionar uma coluna a
  ler"**: the user draws one or more regions (position, width, and ideally skew/shape to
  match a tilted scan), each becoming a column to read. Multiple regions = multiple
  columns on a double-page or ruleless table.
- On read, **crop the selected region(s)** (a temp image per region, or pass
  normalized bboxes to the engine) and run detection/recognition **only on those**, so a
  document that returned gibberish full-page can be salvaged region by region.
- **Right pane gets tabs** to separate the **"Leitura completa"** (full-page OCR) from
  the **"Leitura personalizada"** (the region read), so the user can compare and keep
  whichever is better without one clobbering the other.

### Why it fits the codebase

- Geometry is already first-class: rows/columns are normalized fractions
  (`review.html:1240` stores `{rows, columns}`; the engine emits `res.geometry`,
  `serve.py:574-575`), and there is a shapes/geometry layer (`serve_shapes.py`,
  `tablegrid.py`, `rowcut.py`, `sheetbands.py`, `bandcrops.py`). A user-drawn region is
  just another normalized bbox fed to the same cut-and-read path.
- A region read is a smaller job than a full page, so it also **reads faster** —
  helpful while the CPU/GPU story (§5) is being sorted.

### Scope note

This is a **new feature**, larger than the bug fixes above — flagged for the backlog,
not the Windows-polish pass. But it's the right structural answer to "the detector
can't see the table," which is the same defect behind §3's miscut grid. Worth a short
design spike: region model (store with the document? per-read only?), crop vs. bbox,
and how the custom read merges into the stored record.

---

## Appendix — architecture note for context

The design spec (`docs/superpowers/specs/2026-07-23-desembarque-design.md`) describes
a **hosted** Next.js + FastAPI + Postgres product. What actually ships and what I
tested is the **local-first** path: a Tkinter launcher
(`launcher/desembarque_launcher.py`) that starts a localhost Python HTTP server
(`scripts/serve.py`) serving a single static page (`prototype/review.html`), with all
transcription happening on the user's machine in `.venv-ocr`. All of this report
concerns that local path — which is the one a non-programmer on Windows will use.

Files most relevant to the fixes above:
- Install/uninstall logic: `launcher/core.py:30-116`
- Launcher GUI + install worker: `launcher/desembarque_launcher.py:216-236`
- Windows entry point: `Desembarque.bat`
- Per-page progress UI: `prototype/review.html:1140-1220`
- Live-read view: `prototype/review.html:1222-1253`
- Job model: `desembarque/jobs.py:24-49`
- Known band-detection defect: `docs/PROGRESS.md` (2026-10-17 entries)
