<div align="center">
<img src="docs/cert_icon4.svg" alt="CERT" width="20%" />
</div>

# CERT CODE

[![CI](https://github.com/Javihaus/cert-code/actions/workflows/ci.yml/badge.svg)](https://github.com/Javihaus/cert-code/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/cert-code.svg)](https://badge.fury.io/py/cert-code)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

`cert-code` is a Python package that collects and evaluates AI-generated code artifacts. It integrates with the CERT (Comprehensive Evaluation and Reasoning Traces) framework to provide metrics on code quality, test results, and type safety.

## Features

- **Git Integration**: Automatically extract diffs from git commits
- **Multi-language Support**: Python, JavaScript/TypeScript, Go, Rust, and more
- **Test Framework Integration**: Parse results from pytest, jest, go test, cargo test
- **Linting Integration**: Ruff, ESLint, golangci-lint, Clippy
- **Type Checking**: mypy, tsc, go vet
- **Git Hooks**: Automatic evaluation on commit or push
- **Context-aware Evaluation**: Include project context for SGI (Source-Grounded Index) calculation

## Installation

```bash
pip install cert-code
```

For development:

```bash
pip install cert-code[dev]
```

## Quick Start

### 1. Initialize Configuration

```bash
cert-code init
```

This creates a `.cert-code.toml` configuration file.

### 2. Set Your API Key

```bash
export CERT_CODE_API_KEY=your-api-key
```

Or add it to your `.cert-code.toml`:

```toml
[api]
key = "your-api-key"
```

### 3. Submit a Code Trace

```bash
# Submit the current commit
cert-code submit --task "Add user authentication feature"

# Submit a specific commit
cert-code submit --task "Fix pagination bug" --ref abc1234

# Run tests before submitting
cert-code submit --task "Add API endpoint" --run-tests

# Dry run to see what would be submitted
cert-code submit --task "Refactor code" --dry-run
```

## CLI Commands

### `cert-code submit`

Submit a code trace to CERT for evaluation.

```bash
cert-code submit [OPTIONS]

Options:
  -t, --task TEXT         Task description (required)
  -d, --diff TEXT         Diff string (if not using git)
  --ref TEXT              Git reference [default: HEAD]
  --base-ref TEXT         Base reference for comparison
  --run-tests/--no-tests  Run tests after collecting
  --run-lint/--no-lint    Run linter
  --run-typecheck         Run type checker
  -c, --context TEXT      Context files (can repeat)
  -l, --language TEXT     Override language detection
  --tool TEXT             Code generation tool name
  -p, --project TEXT      CERT project ID
  --config PATH           Path to config file
  --dry-run               Show what would be submitted
```

### `cert-code init`

Initialize a new configuration file.

```bash
cert-code init [--force]
```

### `cert-code hook`

Install or remove git hooks.

```bash
# Install post-commit hook
cert-code hook

# Install pre-push hook with tests
cert-code hook --type pre-push

# Remove hook
cert-code hook --uninstall
```

### `cert-code status`

Check configuration and connectivity.

```bash
cert-code status
```

## Configuration

The `.cert-code.toml` file supports the following options:

```toml
[api]
url = "https://cert-framework.dev/api/v1"
# key = "your-api-key"  # Or use CERT_CODE_API_KEY env var

[project]
id = "your-project-id"
name = "my-project"

[behavior]
auto_detect_language = true
auto_run_tests = false
auto_run_lint = false
auto_run_typecheck = false

[test]
command = "pytest"  # or "npm test", "go test ./..."
timeout = 300

[lint]
command = "ruff check"  # or "eslint"

[typecheck]
command = "mypy ."  # or "tsc --noEmit"

[context]
files = ["README.md", "docs/api.md"]
max_size = 100000

[git]
hook_enabled = false
hook_type = "post-commit"
```

## Python API

```python
from cert_code import CodeCollector, CertCodeConfig, CollectorOptions

# Load configuration
config = CertCodeConfig.load()

# Create collector
with CodeCollector(config) as collector:
    # Submit from git commit
    result = collector.from_commit(
        task="Add new feature",
        ref="HEAD",
        options=CollectorOptions(run_tests=True),
        tool="claude-code",
    )

    if result.success:
        print(f"Trace ID: {result.trace_id}")
        if result.evaluation:
            print(f"Score: {result.evaluation.get('score')}")
```

### Async API

```python
import asyncio
from cert_code import CertAsyncClient, CertCodeConfig

async def submit_traces():
    config = CertCodeConfig.load()

    async with CertAsyncClient(config) as client:
        results = await client.submit_batch(traces, concurrency=5)

    for result in results:
        print(f"Trace {result.trace_id}: {'Success' if result.success else result.error}")

asyncio.run(submit_traces())
```

## Supported Languages

| Language   | Extension(s)          | Test Framework | Linter        | Type Checker |
|------------|----------------------|----------------|---------------|--------------|
| Python     | .py, .pyi            | pytest         | ruff          | mypy         |
| JavaScript | .js, .jsx, .mjs      | jest           | eslint        | -            |
| TypeScript | .ts, .tsx            | jest           | eslint        | tsc          |
| Go         | .go                  | go test        | golangci-lint | go vet       |
| Rust       | .rs                  | cargo test     | clippy        | cargo check  |
| Java       | .java                | JUnit          | checkstyle    | -            |
| Ruby       | .rb                  | rspec          | rubocop       | sorbet       |
| PHP        | .php                 | phpunit        | phpcs         | phpstan      |

## Environment Variables

| Variable               | Description                    |
|-----------------------|--------------------------------|
| `CERT_CODE_API_KEY`    | CERT API authentication key    |
| `CERT_CODE_API_URL`    | Custom API URL                 |
| `CERT_CODE_PROJECT_ID` | Default project ID             |
| `CERT_CODE_TASK`       | Task description (for hooks)   |
| `CERT_CODE_SKIP`       | Set to "1" to skip hook        |

## Development

```bash
# Clone the repository
git clone https://github.com/ideami/cert-code.git
cd cert-code

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .

# Run type checking
mypy .
```

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.
