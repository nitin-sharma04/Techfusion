# New-OSWorld

A clean, modular desktop environment benchmark for evaluating multimodal AI agents on real-world computer tasks.

## Architecture

```
New-OSWorld/
├── config.yaml                  # Unified configuration (single source of truth)
├── pyproject.toml               # Modern Python packaging
├── requirements.txt             # Flat dependency list
│
└── new_osworld/                 # Main package
    ├── cli.py                   # Unified CLI (evaluate, results, human, info)
    ├── config.py                # Pydantic config models + YAML loader
    ├── logging_setup.py         # Centralised logging (configured once)
    │
    ├── environment/             # Desktop VM environment (Gymnasium-compatible)
    │   ├── desktop_env.py       # Core DesktopEnv class
    │   ├── actions.py           # Action space definitions
    │   ├── controllers/         # HTTP controllers for the in-VM server
    │   │   ├── python_controller.py
    │   │   └── setup_controller.py
    │   ├── providers/           # VM providers (Docker, AWS, VMware, etc.)
    │   │   ├── base.py          # Abstract Provider + VMManager
    │   │   └── __init__.py      # Factory with lazy imports
    │   └── evaluators/          # Task evaluation (metrics + getters)
    │
    ├── agents/                  # LLM-powered automation agents
    │   ├── base.py              # Abstract BaseAgent
    │   ├── prompt_agent.py      # Main multi-turn prompt agent
    │   ├── prompts.py           # System prompts (deduplicated)
    │   ├── llm_clients/         # Per-provider LLM clients
    │   │   ├── base.py          # Abstract LLMClient
    │   │   ├── openai_client.py
    │   │   ├── anthropic_client.py
    │   │   ├── google_client.py
    │   │   ├── groq_client.py
    │   │   └── dashscope_client.py
    │   └── utils/               # Shared utilities
    │       ├── parsing.py       # Action/code extraction from LLM output
    │       ├── a11y_tree.py     # Accessibility tree processing
    │       └── image_utils.py   # Base64 encoding/decoding
    │
    ├── runner/                  # Task execution engines
    │   ├── single.py            # Single-task runner
    │   ├── batch.py             # Sequential batch runner (with progress bar)
    │   └── parallel.py          # Multi-process parallel runner
    │
    └── results/                 # Result aggregation
        └── analyzer.py          # Rich-formatted result tables
```

## Key Improvements Over OSWorld-SFT

| Area | Before | After |
|------|--------|-------|
| **Entry points** | 15+ separate `run_*.py` scripts | Single CLI: `osworld evaluate` |
| **Configuration** | CLI args scattered across files | `config.yaml` + Pydantic validation |
| **Logging** | Copy-pasted 30-line blocks in every file | `setup_logging()` called once |
| **LLM clients** | 1200-line if/elif chain in `agent.py` | Separate client classes per provider |
| **Error handling** | Bare `except:`, `type() ==` checks | Typed exceptions, `isinstance()` |
| **Code duplication** | `get_unfinished` copied 12 times | Single implementation in `batch.py` |
| **Progress reporting** | Inconsistent `tqdm` usage | Rich progress bars + colored output |
| **Output** | Plain `print()` statements | Rich console tables and formatting |
| **Prompts** | Massive repeated action-space text | Deduplicated, parameterised templates |
| **Packaging** | `setup.py` with inline deps | `pyproject.toml` with optional dep groups |

## Quick Start

### Installation

```bash
# Install core package
pip install -e .

# Install with all optional dependencies
pip install -e ".[all]"

# Or install specific groups
pip install -e ".[agents,eval,cloud]"
```

### Configuration

Edit `config.yaml` or override via CLI flags:

```bash
# Use config file defaults
osworld evaluate

# Override specific settings
osworld evaluate --model gpt-4o --provider docker --num-workers 4

# Point to a custom config
osworld evaluate --config /path/to/my-config.yaml
```

### Commands

```bash
# Run the full benchmark
osworld evaluate --model gpt-4o --provider docker

# Run a specific domain
osworld evaluate --domain libreoffice_calc

# Run with multiple parallel VMs
osworld evaluate --num-workers 4

# View results
osworld results --model gpt-4o

# Human-in-the-loop mode
osworld human evaluation_examples/examples/os/example.json

# Show configuration info
osworld info
```

### Environment Variables

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
| `OSWORLD_CONFIG` | Path to config file (overrides search) |

## Supported Providers

- **Docker** -- Containerised VMs (default, recommended for development)
- **VMware** -- VMware Workstation / Fusion
- **VirtualBox** -- Oracle VirtualBox
- **AWS** -- Amazon EC2 instances
- **Azure** -- Azure Virtual Machines
- **Aliyun** -- Alibaba Cloud ECS
- **Volcengine** -- ByteDance Volcengine

## Supported Models

- **OpenAI**: `gpt-4o`, `gpt-4-turbo`, `gpt-4-vision-preview`, etc.
- **Anthropic**: `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`, etc.
- **Google**: `gemini-pro`, `gemini-pro-vision`, `gemini-1.5-pro`, etc.
- **Groq**: `llama3-70b`
- **Alibaba**: `qwen-vl-plus`, `qwen-vl-max`, `qwen-max`, etc.
- **Together/Mistral**: `mistral-*` (via Together AI)

## Detailed Documentation

See [DOCUMENTATION.md](DOCUMENTATION.md) for the complete comparison between New-OSWorld and OSWorld-SFT, including:

- Architecture differences (flat scripts vs modular package)
- All bug fixes from the old repo
- SFT enriched coordinate system
- Command reference mapping (old to new)
- Design principles

## License

Apache 2.0
