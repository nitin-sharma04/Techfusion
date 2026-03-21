# New-OSWorld vs OSWorld-SFT: Complete Documentation

## Overview

**New-OSWorld** is a ground-up rewrite of the OSWorld-SFT desktop automation benchmark.
Same core concept -- LLM agents interacting with real desktop VMs -- but with a
completely different architecture, tooling, and developer experience.

---

## What is OSWorld?

A benchmark where AI agents control a real virtual machine (Ubuntu/Windows) through
screenshots, accessibility trees, and pyautogui commands.  Tasks include things like:

- "Make Bing the default search engine in Chrome"
- "Create a bar chart in LibreOffice Calc"
- "Delete all Amazon cookies"

The SFT (Supervised Fine-Tuning) workflow lets human annotators record golden
trajectories that are used to train agents.

---

## Architecture Comparison

### Old Repo (OSWorld-SFT): Flat Script-Based

```
OSWorld-SFT/
├── run.py                        # Entry point 1
├── run_multienv.py               # Entry point 2
├── run_multienv_aguvis.py        # Entry point 3
├── run_multienv_claude.py        # Entry point 4
├── run_multienv_gta1.py          # Entry point 5
├── run_multienv_o3.py            # Entry point 6
├── run_multienv_openaicua.py     # Entry point 7
├── run_multienv_opencua.py       # Entry point 8
├── run_multienv_qwen25vl.py      # Entry point 9
├── run_multienv_uitars.py        # Entry point 10
├── run_multienv_uitars15_v1.py   # Entry point 11
├── run_multienv_uitars15_v2.py   # Entry point 12
├── run_parallel_eval.py          # Entry point 13
├── main.py                       # Entry point 14
├── show_result.py                # Entry point 15
├── lib_run_single.py             # Shared runner (duplicated logic)
├── mm_agents/agent.py            # 1225-line god file (all LLM clients)
├── mm_agents/prompts.py          # 1600 lines of repeated prompts
├── Turing_tooling/               # 16 files, company-specific naming
└── 355 Python files total
```

### New Repo (New-OSWorld): Modular Package

```
New-OSWorld/
├── config.yaml                   # Single config file
├── pyproject.toml                # Modern packaging
├── manual_task.json              # SFT task selector
│
└── new_osworld/                  # Clean Python package
    ├── cli.py                    # ONE entry point, 9 commands
    ├── config.py                 # Pydantic-validated config
    ├── logging_setup.py          # Configured once, used everywhere
    │
    ├── environment/              # VM lifecycle
    │   ├── desktop_env.py        # Core Gym environment
    │   ├── actions.py            # Action space
    │   ├── controllers/          # VM HTTP communication
    │   ├── providers/            # 7 VM backends (VMware, Docker, AWS...)
    │   └── evaluators/           # Task evaluation
    │
    ├── agents/                   # LLM integration
    │   ├── base.py               # Abstract agent
    │   ├── prompt_agent.py       # Multi-turn agent
    │   ├── prompts.py            # Deduplicated prompts
    │   ├── llm_clients/          # Separate file per LLM provider
    │   └── utils/                # Parsing, image, a11y helpers
    │
    ├── runner/                   # Execution engines
    │   ├── single.py             # One task
    │   ├── batch.py              # Sequential with progress bars
    │   ├── parallel.py           # Multi-process
    │   ├── manual.py             # Interactive SFT collection
    │   └── a11y_enricher.py      # Coordinate extraction (NEW)
    │
    ├── results/                  # Result analysis
    │   └── analyzer.py           # Rich-formatted tables
    │
    └── tech_tooling/             # SFT pipeline tools
        ├── notebook_builder.py   # Trajectory → notebook
        ├── trajectory_replayer.py # Replay & verify trajectories
        ├── delivery_validator.py  # Validate deliverables
        └── trajectory_converter.py
```

---

## Key Differences

### 1. Single CLI vs 15 Scripts

**Old:** Choose from 15 different Python scripts, each with slightly different args:
```bash
python run.py --model gpt-4o --provider_name vmware ...
python run_multienv.py --model gpt-4o --num_envs 4 ...
python run_multienv_claude.py --model claude-3-opus ...
python Turing_tooling/run_manual.py --provider_name vmware ...
python show_result.py
```

**New:** One command, multiple subcommands:
```bash
python -m new_osworld evaluate --model gpt-4o --provider vmware
python -m new_osworld evaluate --model gpt-4o --num-workers 4
python -m new_osworld sft --provider vmware --task-file manual_task.json
python -m new_osworld results --model gpt-4o
python -m new_osworld start-vm --provider vmware
python -m new_osworld validate ./Deliverable/
python -m new_osworld replay trajectory.jsonl --task-config task.json
python -m new_osworld convert-trajectory trajectory.jsonl
python -m new_osworld info
```

### 2. Unified Config vs Scattered CLI Args

**Old:** Every script re-defines its own argparse with slightly different defaults:
```python
# run.py
parser.add_argument("--max_steps", type=int, default=15)
parser.add_argument("--provider_name", default="vmware")

# run_multienv.py (different defaults!)
parser.add_argument("--max_steps", type=int, default=15)
parser.add_argument("--provider_name", default="docker")

# Turing_tooling/run_manual.py (yet different!)
parser.add_argument("--max_steps", type=int, default=200)
parser.add_argument("--provider_name", default="virtualbox")
```

**New:** Single `config.yaml` + Pydantic validation:
```yaml
# config.yaml - one source of truth
environment:
  provider: vmware
  screen_width: 1920
  screen_height: 1080
agent:
  model: gpt-4o
  max_tokens: 1500
evaluation:
  max_steps: 15
```

CLI flags override the config: `--model gpt-4o --max-steps 30`

### 3. Modular LLM Clients vs 1200-line if/elif

**Old:** One massive `call_llm()` method in `agent.py` (1200 lines):
```python
def call_llm(self, payload):
    if self.model.startswith("azure-gpt"):
        # 50 lines of Azure code...
    elif self.model.startswith("gpt"):
        # 40 lines of OpenAI code...
    elif self.model.startswith("claude"):
        # 60 lines of Anthropic code...
    elif self.model.startswith("gemini"):
        # 80 lines of Google code...
    elif self.model.startswith("qwen"):
        # 70 lines of DashScope code...
    # ... 6 more elif blocks
```

**New:** Separate client classes, auto-selected by model name:
```
agents/llm_clients/
├── base.py              # Abstract LLMClient interface
├── openai_client.py     # OpenAI + Azure + Together
├── anthropic_client.py  # Claude
├── google_client.py     # Gemini
├── groq_client.py       # Llama via Groq
└── dashscope_client.py  # Qwen via DashScope
```
```python
# Usage: auto-picks the right client
from new_osworld.agents.llm_clients import create_llm_client
client = create_llm_client("gpt-4o")      # → OpenAIClient
client = create_llm_client("claude-3")     # → AnthropicClient
```

### 4. Centralized Logging vs Copy-Pasted Blocks

**Old:** 30 lines of logger setup duplicated in every single entry point:
```python
# Copied verbatim in run.py, run_multienv.py, main.py, and 12 more files
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
datetime_str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
file_handler = logging.FileHandler(os.path.join("logs", f"normal-{datetime_str}.log"))
debug_handler = logging.FileHandler(os.path.join("logs", f"debug-{datetime_str}.log"))
stdout_handler = logging.StreamHandler(sys.stdout)
# ... 20 more lines ...
```

**New:** One call, done:
```python
from new_osworld.logging_setup import setup_logging, get_logger
setup_logging()  # Called once at startup
logger = get_logger("mymodule")  # Used anywhere
```

### 5. Rich Output vs Plain print()

**Old:**
```
Current Success Rate: 45.5 %
Domain: chrome Runned: 10 Success Rate: 50.0 %
Domain: gimp Runned: 5 Success Rate: 40.0 %
```

**New:**
```
┌─────────────────────────────────────────────────┐
│     Results: gpt-4o / pyautogui / screenshot    │
├──────────────────┬───────────┬──────────────────┤
│ Domain           │ Completed │   Success Rate   │
├──────────────────┼───────────┼──────────────────┤
│ chrome           │        10 │            50.0% │
│ gimp             │         5 │            40.0% │
├──────────────────┼───────────┼──────────────────┤
│ OVERALL          │        15 │            46.7% │
└──────────────────┴───────────┴──────────────────┘
```

### 6. SFT Data Collection: Enriched Coordinates

**Old:** Saves raw XML file (one giant line, coordinates only for "visible+showing" elements):
```
SFT/domain/task_id/
├── step_0.png           # Screenshot
├── step_0_before.xml    # Raw XML (partial coordinates)
└── trajectory.jsonl
```

**New:** Saves enriched data with parsed coordinate tables:
```
SFT/domain/task_id/
├── step_0_before.png        # Screenshot before action
├── step_0_after.png         # Screenshot after action
├── step_0_before.xml        # Raw accessibility tree XML
├── step_0_coords.tsv        # ALL elements with coordinates (parseable)
├── step_0_interactive.tsv   # Only clickable elements (ready to use)
├── initial_state.png
├── initial_state.xml
├── initial_coords.tsv
├── initial_interactive.tsv
├── trajectory.jsonl          # Step-by-step action log
├── recording.mp4             # Screen recording
├── result.txt                # Evaluation score
└── osw.sft.*.ipynb           # Auto-generated SFT notebook
```

The `interactive.tsv` gives operators instant access to click coordinates:
```
tag          name       text       center_x  center_y  width  height
push-button  Close      Close      1901      44        38     35
push-button  Reload     Reload     164       90        34     34
page-tab     New Tab    ...        226       47        256    41
entry        Address    https://   560       90        700    34
```

### 7. Tech Tooling vs Turing_tooling

**Old** `Turing_tooling/` (16 files, ~4800 lines, company-branded):
- Duplicate `lib_run_manual.py` in TWO locations
- `notebook_generator.py` duplicated in TWO locations
- `validation_script_tencent.py` -- company-specific
- `assistant_response_formatter.py` -- LLM-dependent
- `run_viewport_sft.py` + `overlay_tool/` (4 files) -- pygame GUI

**New** `tech_tooling/` (5 files, ~700 lines, generic):
- `notebook_builder.py` -- fixed double-escaping bug, proper cell format
- `trajectory_replayer.py` -- rich progress, bounded retries
- `delivery_validator.py` -- returns structured `ValidationReport`
- `trajectory_converter.py` -- clean CLI wrapper
- All integrated into the unified CLI

### 8. Bug Fixes from Old Repo

| Bug | Old Repo | New Repo |
|-----|----------|----------|
| Bare `except:` clauses | 12+ instances in agent.py, show_result.py | All use typed exceptions |
| `type(action) == str` | desktop_env.py line 391, 411 | `isinstance(action, str)` |
| Global logger mutation | `PromptAgent.reset()` mutates `global logger` | Per-instance `self._logger` |
| Missing null checks | `obs['screenshot']` without None check | `obs.get("screenshot")` everywhere |
| Debug writes in production | `response.json` written on every Gemini call | Removed |
| Wildcard imports | `from wrapt_timeout_decorator import *` | Explicit imports |
| Duplicate `import time` | `lib_run_manual.py` lines 4 and 7 | No duplicates |
| `vmrun` not on PATH | Works on Linux/Mac, fails on Windows | `_find_vmrun()` resolves absolute path |
| `vmrun start` hangs | `while True` with no timeout | Fire-and-forget + polling |
| Download corruption | Append mode on full restart = double file | Detects 200 vs 206, validates zip |

### 9. Modern Packaging

**Old:**
```python
# setup.py (2019 style)
setup(
    name="desktop_env",
    install_requires=["numpy~=1.24.4", "torch~=2.5.0", ...]  # Pinned versions
)
```

**New:**
```toml
# pyproject.toml (modern standard)
[project]
name = "new-osworld"
dependencies = ["numpy>=1.26.0", "gymnasium>=0.29.0", ...]

[project.optional-dependencies]
agents = ["transformers>=4.38.0", "torch>=2.2.0", ...]
eval = ["opencv-python", "scikit-image", ...]
cloud = ["boto3", "azure-identity", ...]
all = ["new-osworld[agents,eval,cloud]"]

[project.scripts]
osworld = "new_osworld.cli:main"
```

Install only what you need: `pip install -e ".[agents]"` vs the old all-or-nothing.

---

## Numbers

| Metric | OSWorld-SFT | New-OSWorld | Change |
|--------|-------------|-------------|--------|
| Python files | 355 | 52 | -85% |
| Entry point scripts | 15 | 1 (9 commands) | Unified |
| Logger setup copies | 15 | 1 | -93% |
| LLM client code | 1 file, 1225 lines | 6 files, 450 lines | Modular |
| Prompts | 1600 lines (massive repetition) | 150 lines (deduplicated) | -91% |
| `get_unfinished()` copies | 12 | 1 | -92% |
| SFT tooling files | 16 (4800 lines) | 5 (700 lines) | -85% |
| Config system | None (CLI args only) | Pydantic + YAML | New |
| Progress bars | Inconsistent tqdm | Rich everywhere | New |
| Coordinate extraction | None | TSV tables per step | New |
| Delivery validation | Inline print() | Structured report | New |
| Auto-notebook generation | Manual only | Auto after SFT | New |

---

## Command Reference

| Purpose | Old Command | New Command |
|---------|-------------|-------------|
| Start VM | `python Turing_tooling/run_manual.py --provider_name vmware` | `python -m new_osworld start-vm --provider vmware` |
| SFT collection | `python Turing_tooling/run_manual.py --provider_name vmware --task_file manual_task.json --result_dir SFT` | `python -m new_osworld sft --provider vmware --task-file manual_task.json --sft-output SFT` |
| Auto evaluation | `python run_multienv.py --provider_name docker --num_envs 4 --model gpt-4o` | `python -m new_osworld evaluate --provider docker --num-workers 4 --model gpt-4o` |
| View results | `python show_result.py` (hardcoded args) | `python -m new_osworld results --model gpt-4o` |
| Validate delivery | `python Turing_tooling/validation_script.py --task_dir ./Deliverable` | `python -m new_osworld validate ./Deliverable` |
| Replay trajectory | `python Turing_tooling/verify_trajectory.py --trajectory_file traj.jsonl --task_config task.json` | `python -m new_osworld replay traj.jsonl --task-config task.json` |
| Convert to notebook | `python Turing_tooling/convert_trajectory_to_notebook.py traj.jsonl` | `python -m new_osworld convert-trajectory traj.jsonl` |
| Show info | *(none)* | `python -m new_osworld info` |

---

## Design Principles

1. **One way to do things** -- single CLI, single config, single logging setup
2. **No copy-paste** -- shared code lives in one place, imported everywhere
3. **Fail fast, fail clear** -- bounded retries, typed errors, rich error messages
4. **Works on Windows** -- absolute paths for vmrun, proper subprocess handling
5. **Install what you need** -- optional dependency groups instead of 67 packages
6. **SFT-first** -- enriched coordinates, auto-notebooks, before+after screenshots
7. **No company branding** -- generic naming, no Turing/Tencent references
