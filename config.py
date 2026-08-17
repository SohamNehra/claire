"""Claire's configuration. Edit this file; you should not need to touch claire.py.

Precedence, highest first:

    1. command line flags   (--model, --thinking, --yolo)
    2. environment variables (CLAIRE_MODEL, CLAIRE_CTX, ...)
    3. this file
    4. what the server reports about the model it actually loaded

Every value below is read by both `claire.py` and the `claire` launcher script,
so there is exactly one place to change when you switch models.
"""

import os

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

# Path to the .gguf weights the launcher should load. This is the one line most
# people need to change. ~ is expanded.
MODEL_GGUF = "~/.lmstudio/models/JonathanColetti/Qwen3.8-27B-Uncensored-GGUF/Qwen3.8-27B-Uncensored-Q4_K_M.gguf"

# Display name shown in the header and sent as the API `model` field.
#   ""    -> ask the server what it loaded  <-- recommended
#   "..." -> force this label
# Leave it empty. A hardcoded name goes stale the moment you change MODEL_GGUF,
# and then the header confidently reports the wrong model. Run
# `python3 config.py` to see what "" currently resolves to.
MODEL_NAME = ""

# Context window in tokens.
#   0     -> use the model's own trained maximum  <-- recommended
#   N     -> force N, even if the model was not trained that long
# Going above the trained maximum needs RoPE scaling and degrades recall. Set
# too high by hand and compaction never fires, so every request overruns the
# window; too low and you waste the model. 0 cannot be wrong.
CONTEXT = 0

# Safety rail for CONTEXT = 0. A model advertising a huge window would otherwise
# try to allocate a KV cache larger than your RAM at startup. Raise it if you
# have the memory. As a rough guide, this model costs ~9.6 GB of KV cache at
# 262144 tokens with q8_0, and cost scales linearly with context.
CONTEXT_CEILING = 262144

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

HOST = "127.0.0.1"
PORT = 8080

# Full API base URL.
#   ""    -> http://HOST:PORT/v1, built from the two values above
#   "..." -> use this instead, e.g. LM Studio on :1234, ollama, a remote box
# Empty keeps HOST/PORT as the single source of truth; setting both is how they
# end up contradicting each other.
API_BASE = ""

# When true the launcher starts llama-server if nothing answers on PORT.
# Set false if you start the server yourself (LM Studio, ollama, a remote box).
AUTOSTART_SERVER = True

# Extra llama-server flags.
GPU_LAYERS = 999          # -ngl. 999 offloads everything it can.
KV_CACHE_TYPE = "q8_0"    # -ctk/-ctv. q8_0 roughly halves cache memory.
EXTRA_SERVER_ARGS = []    # e.g. ["--rope-scaling", "yarn", "--rope-scale", "2"]
SERVER_LOG = "~/.claire-server.log"

# ---------------------------------------------------------------------------
# Agent behaviour
# ---------------------------------------------------------------------------

# Which system prompt to use.
#   ""            -> the prompt built into claire.py
#   "claire_v2"   -> prompts/claire_v2.md
#   "/some/path"  -> that file
SYSTEM_PROMPT = ""

MAX_STEPS = 25            # hard cap on the agent loop for one task
COMPACT_AT = 0.70         # summarise older turns past this share of the context
COMMAND_TIMEOUT = 120     # seconds before run_command is killed
MAX_OUTPUT_CHARS = 15000  # truncate tool output past this

THINKING = False          # start in deep-reasoning mode
AUTO_APPROVE = False      # start in yolo mode (skip command approval)

# Directories never walked by list_files / search_files.
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "dist", "build", ".next", ".cache", ".idea"}

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

VAULT = "~/claire-vault"           # long-term notes
HISTORY_FILE = "~/.claire_history"  # readline history


# ---------------------------------------------------------------------------
# Plumbing. Nothing below here is meant to be edited.
# ---------------------------------------------------------------------------

def _path(value):
    return os.path.expanduser(str(value)) if value else value


def api_base():
    return API_BASE or f"http://{HOST}:{PORT}/v1"


def as_shell():
    """Emit the values the launcher needs, as shell assignments.

    The launcher runs `eval "$(python3 config.py --sh)"` so that bash and Python
    can never disagree about which model or port is in play.
    """
    quoted = lambda v: "'" + str(v).replace("'", "'\\''") + "'"
    lines = [
        f"CLAIRE_MODEL_GGUF={quoted(_path(MODEL_GGUF))}",
        f"CLAIRE_HOST={quoted(HOST)}",
        f"CLAIRE_PORT={quoted(PORT)}",
        f"CLAIRE_CTX_CONF={quoted(CONTEXT)}",
        f"CLAIRE_CTX_CEILING={quoted(CONTEXT_CEILING)}",
        f"CLAIRE_NGL={quoted(GPU_LAYERS)}",
        f"CLAIRE_KV={quoted(KV_CACHE_TYPE)}",
        f"CLAIRE_SERVER_LOG={quoted(_path(SERVER_LOG))}",
        f"CLAIRE_AUTOSTART={quoted('1' if AUTOSTART_SERVER else '0')}",
        f"CLAIRE_EXTRA_ARGS={quoted(' '.join(EXTRA_SERVER_ARGS))}",
    ]
    return "\n".join(lines)


def probe_server(api_base=None, timeout=5):
    """Ask the server what it actually loaded. Returns {} if it isn't up.

    Shared with claire.py so there is one implementation of "what is really
    running", rather than two that can drift.
    """
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"{api_base or api_base_default()}/models",
                                    timeout=timeout) as resp:
            entry = (json.load(resp).get("data") or [{}])[0]
    except Exception:
        return {}
    meta = dict(entry.get("meta") or {})
    meta["id"] = entry.get("id") or ""
    return meta


def api_base_default():
    return api_base()


def resolved():
    """What each setting actually evaluates to right now.

    Several fields are deliberately blank, meaning "derive this" -- blank is the
    correct value, not a missing one. This makes that visible instead of
    leaving the reader to guess.
    """
    meta = probe_server()
    live = bool(meta)
    name = MODEL_NAME or (os.path.basename(meta.get("id", "")).replace(".gguf", "")
                          if live else "?")
    trained = meta.get("n_ctx_train") or 0
    ctx = CONTEXT or min(trained or CONTEXT_CEILING, CONTEXT_CEILING)
    rows = [
        ("MODEL_GGUF", MODEL_GGUF, _path(MODEL_GGUF), "exists"
         if os.path.exists(_path(MODEL_GGUF)) else "MISSING"),
        ("MODEL_NAME", MODEL_NAME, name,
         "from server" if not MODEL_NAME and live else
         "server not running" if not MODEL_NAME else "forced"),
        ("CONTEXT", CONTEXT, ctx,
         f"model trained for {trained:,}" if (not CONTEXT and trained)
         else "capped by CONTEXT_CEILING" if not CONTEXT else "forced"),
        ("API_BASE", API_BASE, api_base(),
         "from HOST:PORT" if not API_BASE else "forced"),
        ("SYSTEM_PROMPT", SYSTEM_PROMPT, SYSTEM_PROMPT or "built-in",
         "compiled into claire.py" if not SYSTEM_PROMPT else "from prompts/"),
        ("EXTRA_SERVER_ARGS", EXTRA_SERVER_ARGS,
         " ".join(EXTRA_SERVER_ARGS) or "(none)", ""),
        ("VAULT", VAULT, _path(VAULT), ""),
    ]
    extra = []
    if live:
        if meta.get("n_params"):
            extra.append(f"parameters   {meta['n_params']:,}")
        if meta.get("size"):
            extra.append(f"file size    {meta['size'] / 2**30:.1f} GiB")
        if meta.get("ftype"):
            extra.append(f"quantisation {meta['ftype']}")
    return rows, extra, live


if __name__ == "__main__":
    import sys
    if "--sh" in sys.argv:
        print(as_shell())
        raise SystemExit(0)

    rows, extra, live = resolved()
    print("\nClaire configuration\n")
    print(f"  {'setting':<18} {'in config.py':<14} {'effective':<34} why")
    print("  " + "-" * 84)
    for key, raw, eff, why in rows:
        shown = '""' if raw == "" else ("[]" if raw == [] else str(raw))
        if len(str(eff)) > 33:
            eff = "..." + str(eff)[-30:]
        print(f"  {key:<18} {shown[:13]:<14} {str(eff):<34} {why}")
    print()
    if live:
        print("  loaded model")
        for line in extra:
            print(f"    {line}")
    else:
        print("  server is not running, so nothing could be detected.")
        print("  start it with `claire`, or set AUTOSTART_SERVER/API_BASE.")
    print('\n  A blank setting means "derive this" and is the recommended value.\n')


# Pin the status bar directly above the prompt and wipe it on submit, so it never
# accumulates in your scrollback. Set False for dumb terminals or if you want the
# old always-printed behaviour. Ignored when stdout is not a TTY.
STICKY_STATUS = True
