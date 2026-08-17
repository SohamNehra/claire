# Claire

A local coding agent that runs entirely on your own machine. No cloud API, no
account, no per-token cost — it talks to a model you're running yourself via
[llama.cpp](https://github.com/ggerganov/llama.cpp), and it edits files, runs
shell commands, and reports back the same way a terminal coding assistant
would. Python standard library only — zero third-party dependencies.

```
  claire ❯ add tests for utils.py

  ◇ thinking
    Reading utils.py first to see what it actually does.

  ⏺ read_file utils.py 2s
    └ utils.py (lines 1-48 of 48):

  ⏺ write_file test_utils.py 6s
    └ Created test_utils.py (31 lines).

  ⏺ run_command python3 -m pytest test_utils.py 3s
    └ exit=0

  ✔ done 12s
```

Everything it does is confined to the directory you launch it from, and any
shell command it wants to run stops for your approval first (unless you opt
out with `--yolo`).

---

## Requirements

- **Python 3.9+**
- **A GGUF model file.** Anything compatible with llama.cpp works. This was
  built and tested against `Qwen3.8-27B-Uncensored-Q4_K_M.gguf`, but any
  reasonably capable instruct/coder model will work — smaller models will be
  less reliable at following the tool-call format.
- **llama.cpp**, specifically `llama-server` — the part of llama.cpp that
  serves an OpenAI-compatible API. This is the only supported backend: it's
  the one that honours per-request "thinking on/off," which Claire depends on
  to stay fast on simple steps and only pay for deep reasoning when a step
  actually fails. LM Studio can serve the same model but ignores that flag
  ([bug #1990](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1990)),
  so reasoning mode can't be toggled per-request there.

---

## 1. Clone it

```bash
git clone <your-repo-url> claire
cd claire
```

## 2. Get llama-server running

### macOS

```bash
brew install llama.cpp
```

This installs `llama-server` on your `PATH`, which is all the launcher script
needs — it starts the server for you.

### Windows

You have two options. **WSL is the easier, better-supported path** — Claire's
launcher script is bash, and the sticky status bar and colored output rely on
ANSI terminal escapes that a real POSIX terminal (or Windows Terminal) handles
correctly.

**Option A — WSL (recommended)**

1. Install WSL if you don't have it: `wsl --install` from an admin PowerShell,
   then restart.
2. Inside the WSL shell, follow the **macOS/Linux steps on this page exactly**
   — install llama.cpp there (build from source, or grab a Linux release from
   the [llama.cpp releases page](https://github.com/ggml-org/llama.cpp/releases)),
   clone the repo inside WSL's filesystem, and run `claire` as normal.

**Option B — native Windows (PowerShell / cmd), no WSL**

1. Download a Windows build from the
   [llama.cpp releases page](https://github.com/ggml-org/llama.cpp/releases)
   (a `...-bin-win-*.zip` containing `llama-server.exe`), or build it yourself
   with CMake. Put it somewhere on your `PATH`.
2. The `claire` launcher script is bash and won't run natively here, so start
   `llama-server` yourself instead of relying on autostart:

   ```powershell
   llama-server.exe --jinja -m C:\path\to\your-model.gguf -c 0 -ngl 999 --port 8080 --host 127.0.0.1
   ```

3. Run the agent directly with Python (see step 4 below) instead of via the
   `claire` script.
4. Use **Windows Terminal**, not the legacy `cmd.exe` console — the sticky
   status bar and colored output need real ANSI escape support, which
   Windows Terminal has on by default and the legacy console may not.

## 3. Point it at your model

Open `config.py` and set `MODEL_GGUF` to your model's path:

```python
MODEL_GGUF = "~/models/your-model.gguf"     # macOS/Linux/WSL, ~ is expanded
MODEL_GGUF = "C:/models/your-model.gguf"    # native Windows, forward slashes are fine
```

That's the one line most people need to change. Everything else in
`config.py` has a documented, sensible default — context window, GPU
offload, host/port, timeouts, where memory is stored. Run:

```bash
python3 config.py
```

at any time to see what every setting currently resolves to, and whether the
model file was actually found.

## 4. Run it

**macOS / Linux / WSL** — from the project directory:

```bash
./claire                       # interactive
./claire "add tests for utils.py"    # one-shot
```

The `claire` script starts `llama-server` automatically if nothing is
already listening on the configured port, then runs the agent. To run it
from any directory without the `./`, symlink it onto your `PATH`:

```bash
ln -s "$(pwd)/claire" ~/.local/bin/claire
```

Then `cd` into whatever project you want it working on and just run `claire`
— it can only read and write inside the directory you launch it from.

**Native Windows (no WSL)** — with `llama-server.exe` already running from
step 2:

```powershell
python claire.py                       # interactive
python claire.py "add tests for utils.py"   # one-shot
```

There's no autostart on this path, so start the server first each time (or
leave it running in its own window).

---

## Usage

```
claire                    interactive session
claire "task"             one-shot: run the task, print the result, exit
claire --yolo "task"      skip approval for shell commands (dangerous ones still prompt)
claire --thinking "task"  start in deep-reasoning mode (slower, smarter)
claire --model ID         use a different model than the one currently loaded
```

Interactive-only commands:

| Command | Effect |
|---|---|
| `/t` | Toggle thinking mode (fast ↔ deep) |
| `/y` | Toggle yolo mode (approval on ↔ off) |
| `reset` | Clear the conversation, keep long-term memory |
| `exit` / `quit` | Quit |
| Ctrl-C | Interrupt the current task; the session stays open |

Environment variables override `config.py` for a single run without editing
the file: `CLAIRE_API`, `CLAIRE_MODEL`, `CLAIRE_CTX`, `CLAIRE_THINKING=1`,
`CLAIRE_YOLO=1`, `CLAIRE_VAULT`. For example:

```bash
CLAIRE_CTX=65536 claire      # cap context for this run only
```

---

## Safety

- **File access is confined** to the directory you launched Claire from —
  every path is resolved and checked; `../` escapes are refused.
- **Shell commands stop for approval** by default (arrow keys or `y`/`n` to
  answer, Enter confirms the highlighted choice). `--yolo` skips this, except
  for commands matching a always-prompt pattern (`rm -rf`, `sudo`, `git push`,
  `git reset --hard`, `curl | sh`, and similar) — those prompt no matter what.
- Under `--yolo`, a command that would write **outside** the project
  directory is refused outright rather than silently allowed, since nothing
  can prompt you to catch it.
- These are pattern matches, not a real sandbox. For genuinely untrusted
  work, run Claire inside a VM or container.
- If you're running an uncensored model, treat `--yolo` accordingly — use it
  in throwaway directories and clean git working trees, not on anything you
  can't restore.

---

## Memory

Claire keeps long-term notes as plain markdown in `~/claire-vault` (override
with `CLAIRE_VAULT` or the `VAULT` setting in `config.py`). Open that folder
as an Obsidian vault to read, edit, or delete anything she's remembered —
she picks up your edits on the next run.

---

## Troubleshooting

Run `python3 config.py` first — it shows every setting, what it resolves to,
whether the model file exists, and whether a server is currently reachable.

| Symptom | Likely cause |
|---|---|
| `ERROR: model not found at: ...` | Fix `MODEL_GGUF` in `config.py` |
| `llama-server is not on your PATH` | Install llama.cpp, or set `AUTOSTART_SERVER = False` and run the server yourself |
| Hangs / empty replies with `--thinking` off | Some backends ignore the "disable reasoning" flag — this project targets `llama-server` specifically for that reason |
| Windows: sticky status bar looks broken/garbled | Use Windows Terminal, not the legacy `cmd.exe` console |
| `cannot reach the model server` | `llama-server` isn't running, or `API_BASE`/`HOST`/`PORT` in `config.py` don't match where it's listening |
