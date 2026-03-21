# New-OSWorld

A modular desktop environment benchmark for evaluating and fine-tuning multimodal AI agents on real-world computer tasks.

Agents interact with live virtual machines through screenshots, accessibility trees, and pyautogui commands -- performing tasks like changing browser settings, editing spreadsheets, managing files, and configuring applications.

---

## Features

- **Unified CLI** -- One command with 9 subcommands replaces everything: evaluation, SFT collection, trajectory replay, validation, results
- **Interactive SFT Data Collection** -- Step through tasks manually, record golden trajectories with before/after screenshots, enriched coordinate tables, and auto-generated notebooks
- **Enriched Accessibility Tree** -- Every step saves parsed TSV coordinate tables alongside raw XML so you instantly know where to click
- **Multi-Model Support** -- GPT-4o, Claude 3, Gemini, Llama 3, Qwen, Mistral -- each with a dedicated client module
- **7 VM Providers** -- VMware, VirtualBox, Docker, AWS, Azure, Aliyun, Volcengine
- **Parallel Evaluation** -- Run multiple VM workers simultaneously for faster benchmarking
- **Rich Terminal Output** -- Progress bars, formatted tables, colored logs
- **Pydantic Config** -- Single `config.yaml` validated at startup, overridable via CLI flags
- **Auto Notebook Generation** -- SFT trajectories automatically converted to Jupyter notebooks
- **Delivery Validation** -- Validate task deliverables against the schema with structured reports

---

## Architecture

```
New-OSWorld/
├── config.yaml                     # Unified configuration
├── manual_task.json                # SFT task selector
├── pyproject.toml                  # Modern Python packaging
│
└── new_osworld/
    ├── cli.py                      # 9 CLI commands
    ├── config.py                   # Pydantic config models + YAML
    ├── logging_setup.py            # Centralized logging
    │
    ├── environment/
    │   ├── desktop_env.py          # Gymnasium-compatible DesktopEnv
    │   ├── actions.py              # Action space definitions
    │   ├── controllers/
    │   │   ├── python_controller.py  # VM HTTP communication
    │   │   └── setup_controller.py   # Task environment setup
    │   ├── providers/              # VMware, Docker, AWS, Azure, ...
    │   │   ├── base.py             # Abstract Provider + VMManager
    │   │   ├── vmware.py           # VMware Workstation / Fusion
    │   │   ├── docker.py           # Docker + QEMU
    │   │   └── ...
    │   └── evaluators/             # Metrics + Getters for scoring
    │
    ├── agents/
    │   ├── base.py                 # Abstract BaseAgent
    │   ├── prompt_agent.py         # Multi-turn vision agent
    │   ├── prompts.py              # System prompts
    │   ├── llm_clients/            # One file per LLM provider
    │   │   ├── openai_client.py
    │   │   ├── anthropic_client.py
    │   │   ├── google_client.py
    │   │   ├── groq_client.py
    │   │   └── dashscope_client.py
    │   └── utils/
    │       ├── parsing.py          # Extract actions from LLM output
    │       ├── a11y_tree.py        # Accessibility tree processing
    │       └── image_utils.py      # Base64 encoding / decoding
    │
    ├── runner/
    │   ├── single.py               # Single task execution
    │   ├── batch.py                # Sequential evaluation with progress
    │   ├── parallel.py             # Multi-process worker pool
    │   ├── manual.py               # Interactive SFT collection
    │   └── a11y_enricher.py        # Coordinate extraction + TSV tables
    │
    ├── results/
    │   └── analyzer.py             # Rich-formatted result tables
    │
    └── tech_tooling/
        ├── notebook_builder.py     # Trajectory → SFT notebook
        ├── trajectory_replayer.py  # Replay + evaluate trajectories
        ├── delivery_validator.py   # Schema validation
        └── trajectory_converter.py # JSONL → notebook converter
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- VMware Workstation / Fusion **or** Docker

### Installation

```bash
git clone https://github.com/your-org/New-OSWorld.git
cd New-OSWorld

# Install with all dependencies
pip install -e ".[all]"

# Or install only what you need
pip install -e .                 # Core only
pip install -e ".[agents]"      # + LLM libraries
pip install -e ".[eval]"        # + Evaluation dependencies
pip install -e ".[cloud]"       # + Cloud provider SDKs
```

### Download VM & Start

```bash
# Downloads ~12 GB VM image on first run, then starts the VM
python -m new_osworld start-vm --provider vmware
```

### Verify

```bash
python -m new_osworld info
```

---

## Commands

### `start-vm` -- Download and boot the VM

```bash
python -m new_osworld start-vm --provider vmware
```

Downloads the Ubuntu VM image (~12 GB) if not cached, starts it, and keeps it running until Ctrl+C.

### `sft` -- Interactive SFT data collection

```bash
python -m new_osworld sft --provider vmware --task-file manual_task.json --sft-output SFT
```

Steps through each task interactively. You type pyautogui commands:

```
Step 1/15 | Enter action (e.g., pg.click(100, 200)): pg.click(1901, 44)
  Saved: XML + coords.tsv + interactive.tsv (375 elements with coordinates)
  Executed: pg.click(1901, 44)

Step 2/15 | Enter action (e.g., pg.click(100, 200)): pg.typewrite('hello')
  Executed: pg.typewrite('hello')

Step 3/15 | Enter action (e.g., pg.click(100, 200)): done
  Task marked as done.

Evaluation score: 1.00
Notebook saved:    SFT/chrome/bb5e.../osw.sft.ipynb
Trajectory saved:  SFT/chrome/bb5e.../trajectory.jsonl
Recording saved:   SFT/chrome/bb5e.../recording.mp4
```

**SFT output per task:**

| File | Description |
|------|-------------|
| `step_N_before.png` | Screenshot before action N |
| `step_N_after.png` | Screenshot after action N |
| `step_N_before.xml` | Full accessibility tree XML |
| `step_N_coords.tsv` | All elements with coordinates |
| `step_N_interactive.tsv` | Clickable elements with click coordinates |
| `trajectory.jsonl` | Complete action log |
| `recording.mp4` | Screen recording |
| `result.txt` | Evaluation score |
| `*.ipynb` | Auto-generated SFT notebook |

**Selecting tasks:** Edit `manual_task.json`:

```json
{
  "chrome": ["bb5e4c0d-f964-439c-97b6-bdb9747de3f4"],
  "os": ["5ea617a3-0e86-4ba6-aab2-dac9aa2e8d57"],
  "vs_code": ["0ed39f63-6049-43d4-ba4d-5fa2fe04a951"]
}
```

### `evaluate` -- Automated benchmark evaluation

```bash
# Single worker
python -m new_osworld evaluate --model gpt-4o --provider vmware

# Parallel (4 VMs)
python -m new_osworld evaluate --model gpt-4o --provider docker --num-workers 4

# Specific domain
python -m new_osworld evaluate --model claude-3-opus --domain libreoffice_calc
```

### `results` -- View evaluation results

```bash
python -m new_osworld results --model gpt-4o
```

```
┌─────────────────────────────────────────────────────┐
│     Results: gpt-4o / pyautogui / screenshot        │
├──────────────────┬───────────┬─────────────────────┤
│ Domain           │ Completed │      Success Rate   │
├──────────────────┼───────────┼─────────────────────┤
│ chrome           │        10 │              50.0%  │
│ libreoffice_calc │         8 │              37.5%  │
│ vs_code          │         6 │              66.7%  │
├──────────────────┼───────────┼─────────────────────┤
│ Office           │        20 │              45.0%  │
│ Daily            │        15 │              53.3%  │
│ Professional     │        10 │              60.0%  │
├──────────────────┼───────────┼─────────────────────┤
│ OVERALL          │        45 │              51.1%  │
└──────────────────┴───────────┴─────────────────────┘
```

### `validate` -- Validate a task delivery

```bash
python -m new_osworld validate ./Deliverable/my-task/
```

```
┌──────────────────────────────────────────────────┐
│          Validation: ./Deliverable/my-task/       │
├────────────────────┬────────┬────────────────────┤
│ Check              │ Status │ Details            │
├────────────────────┼────────┼────────────────────┤
│ Directory Structure│  PASS  │ OK                 │
│ JSON Schema        │  PASS  │ OK                 │
│ Notebook Cells     │  PASS  │ OK                 │
│ Evaluation Score   │  PASS  │ OK                 │
├────────────────────┼────────┼────────────────────┤
│ Overall            │  ALL PASSED                 │
└────────────────────┴────────┴────────────────────┘
```

### `replay` -- Replay a recorded trajectory

```bash
python -m new_osworld replay trajectory.jsonl \
    --task-config evaluation_examples/examples/chrome/bb5e4c0d.json \
    --provider vmware
```

### `convert-trajectory` -- Convert trajectory to notebook

```bash
python -m new_osworld convert-trajectory trajectory.jsonl --task-config task.json
```

### `info` -- Show configuration

```bash
python -m new_osworld info
```

---

## Configuration

All settings live in `config.yaml`. CLI flags override any value.

```yaml
environment:
  provider: vmware          # vmware | docker | aws | azure | ...
  screen_width: 1920
  screen_height: 1080
  headless: false
  os_type: Ubuntu

agent:
  model: gpt-4o
  temperature: 1.0
  max_tokens: 1500
  max_trajectory_length: 3

evaluation:
  max_steps: 15
  result_dir: ./results
  test_meta_path: evaluation_examples/test_all.json

execution:
  num_workers: 1

logging:
  level: INFO
  colored_output: true
```

---

## Supported Action Types

| Action | Example |
|--------|---------|
| Left click | `pg.click(100, 200)` |
| Right click | `pg.rightClick(100, 200)` |
| Double click | `pg.doubleClick(100, 200)` |
| Type text | `pg.typewrite('hello world')` |
| Press key | `pg.press('enter')` |
| Key combo | `pg.hotkey('ctrl', 'c')` |
| Scroll | `pg.scroll(-3)` |
| Mouse move | `pg.moveTo(100, 200)` |
| Drag | `pg.drag(100, 200)` |
| Wait | `time.sleep(2)` |

---

## Enriched Coordinate System

Every SFT step generates a `step_N_interactive.tsv` file with ready-to-use click coordinates:

```
tag          name           text              center_x  center_y  width  height
push-button  Close          Close             1901      44        38     35
push-button  Reload         Reload            164       90        34     34
page-tab     New Tab        Memory - 52 MB    226       47        256    41
entry        Address bar    https://...       560       90        700    34
link         Settings       Settings          960       400       80     20
```

Use `center_x` and `center_y` directly: `pg.click(1901, 44)` to click "Close".

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_BASE_URL` | Custom OpenAI-compatible endpoint |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GENAI_API_KEY` | Google Gemini API key |
| `GROQ_API_KEY` | Groq API key |
| `TOGETHER_API_KEY` | Together AI API key |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `OSWORLD_CONFIG` | Override path to config file |

---

## Supported Providers

| Provider | Type | Best For |
|----------|------|----------|
| **VMware** | Local | Development, SFT collection |
| **Docker** | Local | CI/CD, lightweight testing |
| **VirtualBox** | Local | Free alternative to VMware |
| **AWS** | Cloud | Large-scale parallel evaluation |
| **Azure** | Cloud | Enterprise environments |
| **Aliyun** | Cloud | China region |
| **Volcengine** | Cloud | China region |

---

## Supported Models

| Provider | Models |
|----------|--------|
| **OpenAI** | gpt-4o, gpt-4-turbo, gpt-4-vision-preview |
| **Anthropic** | claude-3-opus, claude-3-sonnet, claude-3-haiku |
| **Google** | gemini-1.5-pro, gemini-pro-vision |
| **Groq** | llama3-70b |
| **Alibaba** | qwen-vl-plus, qwen-vl-max, qwen-max |
| **Together** | mistral-* |

---

## Task Domains

| Domain | Application | Example Tasks |
|--------|------------|---------------|
| `chrome` | Google Chrome | Change search engine, delete cookies, manage extensions |
| `gimp` | GIMP | Resize images, apply filters, change backgrounds |
| `libreoffice_calc` | Calc | Create charts, apply formulas, format tables |
| `libreoffice_impress` | Impress | Edit slides, add transitions, change layouts |
| `libreoffice_writer` | Writer | Format documents, insert page breaks, edit headers |
| `multi_apps` | Multiple | Cross-app tasks (e.g., copy from web to spreadsheet) |
| `os` | Ubuntu OS | Change wallpaper, manage files, configure settings |
| `thunderbird` | Thunderbird | Create filters, manage folders, configure accounts |
| `vlc` | VLC | Change playback settings, configure audio |
| `vs_code` | VS Code | Edit settings, install extensions, run scripts |

---

## License

Apache 2.0
