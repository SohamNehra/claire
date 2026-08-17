# Claire

A fast local coding agent that runs directly on your machine.

No cloud, no tunnel, no proxy, no credits. Talks straight to LM Studio on
`127.0.0.1:1234`. Python stdlib only — zero dependencies.

```bash
cd ~/your-project
claire                          # interactive
claire "add tests for utils.py" # one-shot
claire --yolo "..."             # skip command approval
```

That's the whole workflow. The `claire` launcher starts llama-server automatically
if it isn't running, so there is nothing to turn on first.

Run it from the directory you want her to work in — she can only touch files inside
that directory.

**LM Studio is not required and should be closed.** It and llama-server each hold a
full ~17 GB copy of the model; running both wastes ~37 GB of RAM for no benefit.
LM Studio is only needed if you still want Cursor's Ask mode (which needs the
tunnel + proxy). For Claire, llama-server alone is better — it's the one that
supports per-request thinking control.

Installed at `~/.local/bin/claire` (symlink). Server log: `~/.claire-server.log`.

---

## Verified working

| Test | Result |
|---|---|
| Create a file, run it, verify | ✅ 3 steps, 18s on llama.cpp |
| Read → edit existing file → verify | ✅ 5 steps, exact-match edit |
| Recover from a failed command | ✅ `python` → exit 127 → retried `python3` unprompted |
| Write + self-verify correctness | ✅ `primes_up_to(30)` verified correct |
| Fetch live web data → save to file | ✅ GitHub API, 124135 stars, exact match |
| Auto-escalate on failure | ✅ `+think` engaged on exit=2, decayed after recovery |

---

## Flags

| Flag | Effect |
|---|---|
| `--yolo` | Skip approval for shell commands (dangerous ones still prompt) |
| `--thinking` | Enable Qwen reasoning mode — smarter, much slower |
| `--model ID` | Use a different loaded model |

Environment: `CLAIRE_API`, `CLAIRE_MODEL`, `CLAIRE_THINKING=1`, `CLAIRE_YOLO=1`.

Interactive commands:

| Command | Effect |
|---|---|
| `/t` | Toggle thinking (fast ↔ deep) |
| `/y` | Toggle yolo (approval on ↔ off) |
| `reset` | Clear conversation context |
| `exit` | Quit |
| Ctrl-C | Interrupt a running task, keep the session |
| ↑ / ↓ | Command history (persists in `~/.claire_history`) |
| ← / → | Line editing, including across wrapped lines |

A status bar above the prompt shows current mode, working directory, and model:

```
  ──────────────────────────────────────────────────────
  • fast │ approve │ my-project │ qwen3.8
  /t toggle thinking
  claire ❯
```

While a step runs, a live line shows a spinner, elapsed time, and a streaming
preview of the model's reasoning — so you can watch it think instead of staring at
a blank screen:

```
  ⠹ thinking 3s   `python` is not found. Try `python3`.
```

While writing a file it reports the line it's currently emitting, so a long
write shows real progress instead of a frozen label:

```
  ⠇ writing 4s   write_file box.html L8  * {
  ⠼ writing 9s   write_file box.html L23 height: 20
  ⠦ writing 18s  write_file box.html L40 .box:
```

Context usage shows in the status bar and after every completed task:

```
  ▰▰▰▰▰▰▱▱▱▱▱▱▱▱ 118k/262k 45.0%
```

Green under 50%, amber under 80%, red above — compaction fires at 70%. Counts
come from the server's own `prompt_tokens` when available, falling back to a
character estimate before the first response.

It collapses into the step result when done:

```
  ⏺ write_file rev.py 5s
    └ Created rev.py (11 lines).
  ⏺ run_command python rev.py 1s
    ✗ exit=127
  ⏺ run_command python3 rev.py ◆ 4s
    └ exit=0
  ✔ done ◆ 9s
```

`⏺` is a tool call, `└` its result, `✗` a failure, `◆` marks a step running with
reasoning auto-boosted.

---

## Tools

| Tool | Purpose |
|---|---|
| `read_file` | Read with line numbers |
| `write_file` | Create or fully overwrite |
| `edit_file` | Search/replace — preferred for existing files |
| `list_files` | Tree walk, skips `.git`/`node_modules`/etc |
| `search_files` | Regex across the project |
| `run_command` | Shell, with an approval gate |
| `git` | Read-only repo inspection: status, diff, staged, log, branch, show |
| `web_search` | Search the internet (DuckDuckGo, no API key) |
| `fetch_url` | Fetch a web page/API, HTML stripped to text |
| `think_harder` | Model escalates itself into reasoning mode |
| `done` | Finish with a summary |

---

## Design notes

Why it's built this way — each choice traces to a specific failure mode of local
models:

**Hand-written loop, no framework.** Production agents are mostly thin hand-written
loops. Frameworks add indirection that makes failures harder to see.

**XML tool calls, not JSON function calling.** This model build *hangs* when the
OpenAI `tools` parameter is present — verified twice, even with `tool_choice: "none"`.
That single fact is why Cursor Agent and Cline both failed. XML also degrades
gracefully: a missing closing tag is recoverable, a truncated JSON object is not.

**Reasoning is stripped before parsing.** Qwen emits `<think>` blocks and
`reasoning_content` deltas. LM Studio has an open bug where `enable_thinking: false`
is ignored via the API and reasoning consumes the whole token budget, leaving content
empty. Claire sends the flag *and* strips reasoning defensively, so the bug can't
break parsing.

**Tiered edit matching.** `edit_file` tries exact match first, then a
whitespace-flexible line match that re-indents automatically. Exact-match-only edits
are the most common failure point for local models. Non-unique search text is
rejected with a specific error rather than silently editing the wrong place.

**Retries change the prompt.** On a malformed reply Claire re-prompts with an
escalating hint rather than resending the same request. Two retries, then stop —
repeating an identical failed call just burns tokens.

**Bounded loop.** Hard cap of 25 steps so a confused model can't spin forever.

**Path confinement.** Every path is resolved and checked against the working
directory; `../` escapes are refused.

---

## Shell safety

Two layers guard `run_command`:

**Always prompt**, regardless of mode — `rm -rf`, `sudo`, `git push`/`reset --hard`/
`clean`, `curl|sh`, `chmod 777`, `chown`, `kill`/`pkill`, `find -delete`,
`pip install`, `npm publish`, `shutil.rmtree`, `os.remove`, `crontab`,
`launchctl`, `diskutil`, `shred`, `truncate`, writes to `/dev/`.

**Always refuse when unattended** — any command writing outside the working
directory (`> ~/…`, `rm /etc/…`, `mv … /usr/…`). The file tools were already
confined to the project; the shell used to be a hole straight through that
guarantee. Verified: `echo test > ~/file` is refused under `--yolo`, and the
file is not created.

⚠️ These are pattern matches, not a real sandbox. A determined command can still
evade them (base64 payloads, unusual interpreters, indirection through a script).
For genuinely untrusted work, run Claire in a VM or container.

## Context and compaction

Long sessions used to die with `HTTP 400 ... exceeds the available context size`.
Now Claire tracks usage and **auto-compacts at 70%** of the window — older turns
are summarised (files touched, decisions, failures, outstanding work) while recent
turns stay verbatim. If the server still rejects a request, she compacts and
retries once before giving up.

Default is **262144** — this model's architectural maximum — with q8_0 KV cache.

Measured cost on this machine:

| Context | KV cache | Weights (mmap) | Total RSS |
|---|---|---|---|
| 32768 | 2.1 GB | 15 GB | 17 GB |
| **262144** | **9.6 GB** | 15 GB | **25 GB** |

Only the KV cache is real dirty memory; the 15 GB of weights is file-backed and
evictable, which is why Activity Monitor's number looks larger than the true cost.

Lower it if you want the RAM back:

```bash
CLAIRE_CTX=65536 claire          # launcher passes it to llama-server too
```

**262144 is a hard ceiling, not a tuning knob.** It's the length the model's
positional encoding was trained for. Asking for more doesn't fail loudly — quality
degrades into incoherence past the trained range, and KV memory grows linearly
(2.5M tokens would need ~92 GB of cache alone, before the weights).

Writing a large file is what usually blows the window — a 400-line HTML file read
back into context is several thousand tokens on its own.

## Memory (Obsidian vault)

Claire keeps long-term memory as plain markdown in `~/claire-vault` — open that
folder as an Obsidian vault and you can read, edit, or delete anything she
remembers. She picks up your edits on the next run.

```
~/claire-vault/
  projects/<dir-name>.md   loaded automatically when run in that directory
  learned/<topic>.md       reusable facts; titles always visible to her
  sessions/<date>.md       what happened
```

At startup she loads the project note for the current directory in full, plus the
*titles* of every learned note as `[[wikilinks]]` — cheap in tokens, and enough
for her to know what's worth recalling.

| Tool | Use |
|---|---|
| `remember` | Save a durable fact (`kind`: project / learned / session) |
| `recall` | Search the vault — word-scored, so "llama-cpp" finds a note on llama-server |

Point it elsewhere with `CLAIRE_VAULT=~/Documents/MyVault claire` to use an
existing Obsidian vault. She only writes under the folders above.

Verified: a fact saved in one session was recalled correctly by a **fresh
process** with no exploration.

## Thinking control

Claire adjusts reasoning depth **per request** — fast by default, deeper when work
gets hard:

- **Auto-escalate.** A failed command, a tool error, or an unparsable reply turns
  reasoning on for the next 2 steps, then it decays back off.
- **Model-requested.** Claire can call `<think_harder>` when genuinely stuck,
  buying 3 deep steps.
- **Manual.** `/think` and `/nothink` in the REPL; `/think?` shows current state.
  `--thinking` starts in deep mode.

A `+think` tag appears next to any step running with reasoning boosted.

### This requires llama.cpp, not LM Studio

Measured on this machine, same weights, same prompt:

| Backend | `enable_thinking: true` | `enable_thinking: false` |
|---|---|---|
| LM Studio | 76 reasoning chars | **111** — ignored ❌ |
| llama.cpp | 62 reasoning chars | **0** — honoured ✅ |

LM Studio ignores the API flag ([bug #1990](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1990)),
and the Qwen `/no_think` prompt switch is ignored by this GGUF too — verified, it
produced *more* reasoning, not less. Its UI toggle is global-only, so an agent
cannot vary depth mid-task.

Run llama.cpp on the weights LM Studio already downloaded:

```bash
brew install llama.cpp

llama-server \
  -m ~/.lmstudio/models/JonathanColetti/Qwen3.8-27B-Uncensored-GGUF/Qwen3.8-27B-Uncensored-Q4_K_M.gguf \
  --jinja -c 16384 -ngl 999 --port 8080 --host 127.0.0.1

CLAIRE_API=http://127.0.0.1:8080/v1 python3 claire.py
```

`--jinja` is required — it's what enables `chat_template_kwargs`. Raise `-c` for
larger context (the model supports 262144; 64 GB leaves plenty of room since the
Q4 weights are ~17 GB).

## Speed

Same task, thinking off: **18s on llama.cpp vs 28s on LM Studio.** Typical steps
run 1–5s. Keep thinking off and let auto-escalation handle the hard parts — that's
the whole point of the design.

---

## Safety

Shell commands prompt for approval by default. Commands matching a dangerous
pattern (`rm -rf`, `sudo`, `git push`, `curl | sh`, `git reset --hard`, redirects to
`/dev/`, …) **always** prompt, even under `--yolo`.

Claire cannot read or write outside the directory you launched her from.

`--yolo` is genuinely risky on an uncensored model. Use it in throwaway directories
and git repos with clean working trees, not on anything you can't restore.

---

## Extending

Adding a tool takes three edits:

1. Document its XML shape in `SYSTEM_PROMPT`
2. Add the name to `TOOLS`
3. Write `tool_yourname(args)` and register it in `HANDLERS`

Good candidates: `git_diff`, `fetch_url`, `apply_patch`, `run_tests` with structured
output parsing.

---

## Known limits

- **No context compaction.** Long sessions eventually fill the window; use `reset`.
- **One tool per step.** Simple and reliable, but slower than parallel calls.
- **No streaming of assistant prose.** You see tool calls, not commentary.
- **Occasional malformed XML** on very long outputs — recovered, but costs a step.
