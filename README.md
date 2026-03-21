<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=180&section=header&text=New-OSWorld&fontSize=70&fontColor=fff&animation=fadeIn&fontAlignY=32&desc=Multimodal%20AI%20Agent%20Benchmark%20for%20Real-World%20Desktop%20Tasks&descSize=18&descAlignY=55" />

<br>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white&labelColor=1a1a2e)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-00C853?style=for-the-badge&logo=apache&logoColor=white&labelColor=1a1a2e)](LICENSE)
[![VMware](https://img.shields.io/badge/VMware-607078?style=for-the-badge&logo=vmware&logoColor=white&labelColor=1a1a2e)](https://vmware.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white&labelColor=1a1a2e)](https://docker.com)

<br>

[🚀 Quick Start](#quick-start) • [📚 Documentation](#commands) • [🔧 Configuration](#configuration) • [🤖 Models](#supported-models) • [☁️ Providers](#supported-providers)

</div>

---

<div align="center">

### 🎯 **The Ultimate Desktop Environment Benchmark for Multimodal AI Agents**

<img src="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2F0d2Z0d2Z0d2Z0d2Z0d2Z0d2Z0d2Z0d2Z0d2Z0d2Z0d2Z0d2Z6ZgZ2ZgZ2Zg/26xBwdIuRJiAIqHwA/giphy.gif" width="0" height="0" />

</div>

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   AGENT                      VIRTUAL MACHINE                EVALUATION          │
│   ┌─────────┐               ┌─────────────────┐           ┌─────────────┐       │
│   │  LLM    │──Screenshot──>│  Ubuntu 22.04   │──Action──>│  Scoring    │       │
│   │  Model  │<──XML Tree────│  Desktop Env    │<─Result───│  Metrics    │       │
│   └─────────┘               └─────────────────┘           └─────────────┘       │
│        │                             │                                          │
│        └───────── pyautogui ─────────┘                                          │
│                                                                                 │
│   Real-time interaction  •  Vision + Accessibility Tree  •  Live VMs            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ What Makes New-OSWorld Revolutionary

<div align="center">

| 🔥 Feature | 💡 Innovation |
|:-----------|:--------------|
| **Unified CLI** | One command, 9 subcommands — evaluation, SFT, replay, validation, results |
| **Interactive SFT Collection** | Step through tasks, record golden trajectories with before/after screenshots |
| **Enriched Accessibility Tree** | Every step saves parsed TSV coordinate tables alongside raw XML |
| **Multi-Model Support** | GPT-4o, Claude 3, Gemini, Llama 3, Qwen, Mistral — all integrated |
| **7 VM Providers** | VMware, VirtualBox, Docker, AWS, Azure, Aliyun, Volcengine |
| **Parallel Evaluation** | Run multiple VM workers simultaneously for blazing-fast benchmarking |
| **Rich Terminal Output** | Progress bars, formatted tables, colored logs |
| **Auto Notebook Generation** | SFT trajectories → Jupyter notebooks automatically |

</div>

---

## 🚀 Quick Start

### Prerequisites

```bash
✅ Python 3.10+
✅ VMware Workstation / Fusion OR Docker
```

### Installation

```bash
# Clone the repository
git clone https://github.com/nitin-sharma04/Techfusion.git
cd Techfusion/New-OSWorld

# Install with all dependencies
pip install -e ".[all]"

# Or install only what you need
pip install -e .                 # Core only
pip install -e ".[agents]"      # + LLM libraries
pip install -e ".[eval]"        # + Evaluation dependencies
pip install -e ".[cloud]"       # + Cloud provider SDKs
```

### Start Your First VM

```bash
# Downloads ~12 GB VM image on first run, then starts the VM
python -m new_osworld start-vm --provider vmware

# Verify everything is working
python -m new_osworld info
```

---

## 📚 Commands

<div align="center">

### 🎮 `start-vm` — Download & Boot VM

</div>

```bash
python -m new_osworld start-vm --provider vmware
```

> Downloads the Ubuntu VM image (~12 GB) if not cached, starts it, and keeps it running until `Ctrl+C`.

---

<div align="center">

### 📝 `sft` — Interactive SFT Data Collection

</div>

```bash
python -m new_osworld sft --provider vmware --task-file manual_task.json --sft-output SFT
```

**Interactive workflow:**

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  Step 1/15 | Enter action (e.g., pg.click(100, 200)): pg.click(1901, 44)     ║
║    [OK] Saved: XML + coords.tsv + interactive.tsv (375 elements)             ║
║    [OK] Executed: pg.click(1901, 44)                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Step 2/15 | Enter action: pg.typewrite('hello')                             ║
║    [OK] Executed: pg.typewrite('hello')                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Step 3/15 | Enter action: done                                              ║
║    [OK] Task marked as done                                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Evaluation score: 1.00                                                      ║
║  Notebook saved:    SFT/chrome/bb5e.../osw.sft.ipynb                         ║
║  Trajectory saved:  SFT/chrome/bb5e.../trajectory.jsonl                      ║
║  Recording saved:   SFT/chrome/bb5e.../recording.mp4                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

**SFT Output Structure:**

| 📁 File | 📝 Description |
|:--------|:---------------|
| `step_N_before.png` | Screenshot before action N |
| `step_N_after.png` | Screenshot after action N |
| `step_N_before.xml` | Full accessibility tree XML |
| `step_N_coords.tsv` | All elements with coordinates |
| `step_N_interactive.tsv` | Clickable elements with coordinates |
| `trajectory.jsonl` | Complete action log |
| `recording.mp4` | Screen recording |
| `result.txt` | Evaluation score |
| `*.ipynb` | Auto-generated SFT notebook |

---

<div align="center">

### 🤖 `evaluate` — Automated Benchmark Evaluation

</div>

```bash
# Single worker evaluation
python -m new_osworld evaluate --model gpt-4o --provider vmware

# Parallel evaluation (4 VMs)
python -m new_osworld evaluate --model gpt-4o --provider docker --num-workers 4

# Domain-specific evaluation
python -m new_osworld evaluate --model claude-3-opus --domain libreoffice_calc
```

---

<div align="center">

### 📊 `results` — View Evaluation Results

</div>

```bash
python -m new_osworld results --model gpt-4o
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│           Results: gpt-4o / pyautogui / screenshot                          │
├──────────────────────┬─────────────┬────────────────────────────────────────┤
│ Domain               │ Completed   │ Success Rate                           │
├──────────────────────┼─────────────┼────────────────────────────────────────┤
│ chrome               │ 10          │ ████████████████████░░░░░░░░░░  50.0%  │
│ libreoffice_calc     │ 8           │ ███████████████░░░░░░░░░░░░░░░  37.5%  │
│ vs_code              │ 6           │ █████████████████████████░░░░░  66.7%  │
├──────────────────────┼─────────────┼────────────────────────────────────────┤
│ Office               │ 20          │ ██████████████████░░░░░░░░░░░░  45.0%  │
│ Daily                │ 15          │ █████████████████████░░░░░░░░░  53.3%  │
│ Professional         │ 10          │ ████████████████████████░░░░░░  60.0%  │
├──────────────────────┼─────────────┼────────────────────────────────────────┤
│ OVERALL              │ 45          │ █████████████████████░░░░░░░░░  51.1%  │
└──────────────────────┴─────────────┴────────────────────────────────────────┘
```

---

<div align="center">

### ✅ `validate` — Validate Task Delivery

</div>

```bash
python -m new_osworld validate ./Deliverable/my-task/
```

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  Validation: ./Deliverable/my-task/                                           │
├────────────────────────┬────────────┬─────────────────────────────────────────┤
│ Check                  │ Status     │ Details                                 │
├────────────────────────┼────────────┼─────────────────────────────────────────┤
│ Directory Structure    │ PASS       │ OK                                      │
│ JSON Schema            │ PASS       │ OK                                      │
│ Notebook Cells         │ PASS       │ OK                                      │
│ Evaluation Score       │ PASS       │ OK                                      │
├────────────────────────┼────────────┼─────────────────────────────────────────┤
│ Overall                │ ALL PASSED │                                         │
└────────────────────────┴────────────┴─────────────────────────────────────────┘
```

---

<div align="center">

### 🔄 `replay` — Replay Recorded Trajectory

</div>

```bash
python -m new_osworld replay trajectory.jsonl \
    --task-config evaluation_examples/examples/chrome/bb5e4c0d.json \
    --provider vmware
```

---

<div align="center">

### 🛠️ Additional Commands

</div>

```bash
# Convert trajectory to notebook
python -m new_osworld convert-trajectory trajectory.jsonl --task-config task.json

# Show configuration
python -m new_osworld info
```

---

## 🔧 Configuration

All settings live in `config.yaml`. CLI flags override any value.

```yaml
# ═══════════════════════════════════════════════════════════════════════════
# 🌍 New-OSWorld Configuration
# ═══════════════════════════════════════════════════════════════════════════

environment:
  provider: vmware          # vmware | docker | aws | azure | aliyun | volcengine
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

## 🎮 Supported Action Types

<div align="center">

| Action | Example | Description |
|:-------|:--------|:------------|
| 🖱️ Left Click | `pg.click(100, 200)` | Click at coordinates |
| 🖱️ Right Click | `pg.rightClick(100, 200)` | Right-click at coordinates |
| 🖱️ Double Click | `pg.doubleClick(100, 200)` | Double-click at coordinates |
| ⌨️ Type Text | `pg.typewrite('hello world')` | Type text |
| ⌨️ Press Key | `pg.press('enter')` | Press a single key |
| ⌨️ Key Combo | `pg.hotkey('ctrl', 'c')` | Press key combination |
| 📜 Scroll | `pg.scroll(-3)` | Scroll up/down |
| 🎯 Mouse Move | `pg.moveTo(100, 200)` | Move cursor |
| 🏃 Drag | `pg.drag(100, 200)` | Drag to coordinates |
| ⏳ Wait | `time.sleep(2)` | Pause execution |

</div>

---

## 📍 Enriched Coordinate System

Every SFT step generates a `step_N_interactive.tsv` file with ready-to-use click coordinates:

```tsv
tag          name           text              center_x  center_y  width  height
───────────  ─────────────  ────────────────  ────────  ────────  ─────  ──────
push-button  Close          Close             1901      44        38     35
push-button  Reload         Reload            164       90        34     34
page-tab     New Tab        Memory - 52 MB    226       47        256    41
entry        Address bar    https://...       560       90        700    34
link         Settings       Settings          960       400       80     20
```

> 💡 **Pro Tip:** Use `center_x` and `center_y` directly: `pg.click(1901, 44)` to click "Close".

---

## 🔐 Environment Variables

<div align="center">

| Variable | Description |
|:---------|:------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_BASE_URL` | Custom OpenAI-compatible endpoint |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GENAI_API_KEY` | Google Gemini API key |
| `GROQ_API_KEY` | Groq API key |
| `TOGETHER_API_KEY` | Together AI API key |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `OSWORLD_CONFIG` | Override path to config file |

</div>

---

## ☁️ Supported Providers

<div align="center">

| Provider | Type | Best For | Status |
|:---------|:-----|:---------|:-------|
| **VMware** | Local | Development, SFT collection | ✅ Ready |
| **Docker** | Local | CI/CD, lightweight testing | ✅ Ready |
| **VirtualBox** | Local | Free alternative to VMware | ✅ Ready |
| **AWS** | Cloud | Large-scale parallel evaluation | ✅ Ready |
| **Azure** | Cloud | Enterprise environments | ✅ Ready |
| **Aliyun** | Cloud | China region | ✅ Ready |
| **Volcengine** | Cloud | China region | ✅ Ready |

</div>

---

## 🤖 Supported Models

<div align="center">

| Provider | Models |
|:---------|:-------|
| **OpenAI** | `gpt-4o`, `gpt-4-turbo`, `gpt-4-vision-preview` |
| **Anthropic** | `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku` |
| **Google** | `gemini-1.5-pro`, `gemini-pro-vision` |
| **Groq** | `llama3-70b` |
| **Alibaba** | `qwen-vl-plus`, `qwen-vl-max`, `qwen-max` |
| **Together** | `mistral-*` |

</div>

---

## 📂 Task Domains

<div align="center">

| Domain | Application | Example Tasks |
|:-------|:------------|:--------------|
| 🌐 `chrome` | Google Chrome | Change search engine, delete cookies, manage extensions |
| 🎨 `gimp` | GIMP | Resize images, apply filters, change backgrounds |
| 📊 `libreoffice_calc` | Calc | Create charts, apply formulas, format tables |
| 📽️ `libreoffice_impress` | Impress | Edit slides, add transitions, change layouts |
| 📝 `libreoffice_writer` | Writer | Format documents, insert page breaks, edit headers |
| 🔗 `multi_apps` | Multiple | Cross-app tasks (copy from web to spreadsheet) |
| 🖥️ `os` | Ubuntu OS | Change wallpaper, manage files, configure settings |
| 📧 `thunderbird` | Thunderbird | Create filters, manage folders, configure accounts |
| 🎵 `vlc` | VLC | Change playback settings, configure audio |
| 💻 `vs_code` | VS Code | Edit settings, install extensions, run scripts |

</div>

---

## 🏗️ Architecture

```
New-OSWorld/
│
├── 📄 config.yaml                     # Unified configuration
├── 📄 manual_task.json                # SFT task selector
├── 📄 pyproject.toml                  # Modern Python packaging
│
└── 📁 new_osworld/
    │
    ├── 🖥️  cli.py                      # 9 CLI commands
    ├── ⚙️  config.py                   # Pydantic config models
    ├── 📋 logging_setup.py            # Centralized logging
    │
    ├── 📁 environment/
    │   ├── 🖥️  desktop_env.py          # Gymnasium-compatible DesktopEnv
    │   ├── 🎮 actions.py              # Action space definitions
    │   ├── 📁 controllers/
    │   │   ├── 🔌 python_controller.py  # VM HTTP communication
    │   │   └── 🛠️  setup_controller.py   # Task environment setup
    │   ├── 📁 providers/              # VMware, Docker, AWS, Azure, ...
    │   │   ├── 📄 base.py             # Abstract Provider + VMManager
    │   │   ├── 📄 vmware.py           # VMware Workstation / Fusion
    │   │   ├── 📄 docker.py           # Docker + QEMU
    │   │   └── 📄 ...
    │   └── 📁 evaluators/             # Metrics + Getters for scoring
    │
    ├── 📁 agents/
    │   ├── 🤖 base.py                 # Abstract BaseAgent
    │   ├── 🧠 prompt_agent.py         # Multi-turn vision agent
    │   ├── 📝 prompts.py              # System prompts
    │   ├── 📁 llm_clients/            # One file per LLM provider
    │   │   ├── 📄 openai_client.py
    │   │   ├── 📄 anthropic_client.py
    │   │   ├── 📄 google_client.py
    │   │   ├── 📄 groq_client.py
    │   │   └── 📄 dashscope_client.py
    │   └── 📁 utils/
    │       ├── 🔍 parsing.py          # Extract actions from LLM output
    │       ├── 🌳 a11y_tree.py        # Accessibility tree processing
    │       └── 🖼️  image_utils.py      # Base64 encoding / decoding
    │
    ├── 📁 runner/
    │   ├── ▶️  single.py               # Single task execution
    │   ├── 📊 batch.py                # Sequential evaluation
    │   ├── ⚡ parallel.py             # Multi-process worker pool
    │   ├── 📝 manual.py               # Interactive SFT collection
    │   └── 📍 a11y_enricher.py        # Coordinate extraction
    │
    ├── 📁 results/
    │   └── 📊 analyzer.py             # Rich-formatted result tables
    │
    └── 📁 tech_tooling/
        ├── 📓 notebook_builder.py     # Trajectory → SFT notebook
        ├── 🔄 trajectory_replayer.py  # Replay + evaluate trajectories
        ├── ✅ delivery_validator.py   # Schema validation
        └── 🔄 trajectory_converter.py # JSONL → notebook converter
```

---

## 📜 License

<div align="center">

**Apache 2.0** © 2024 New-OSWorld Contributors

[![License](https://img.shields.io/badge/License-Apache%202.0-00C853?style=for-the-badge&logo=apache&logoColor=white)](LICENSE)

</div>

---

<div align="center">

### 🌟 Star us on GitHub!

If you find New-OSWorld useful, please consider giving us a ⭐!

[![GitHub stars](https://img.shields.io/github/stars/nitin-sharma04/Techfusion?style=for-the-badge&logo=github&color=gold)](https://github.com/nitin-sharma04/Techfusion)

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=100&section=footer" />

</div>
