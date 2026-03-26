# Contributing to MCPSearch

Thank you for your interest in contributing to MCPSearch! This document provides guidelines for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/MCPSearch.git`
3. Create a branch: `git checkout -b feature/your-feature`
4. Install dependencies: `make dev`
5. Make your changes
6. Run tests: `pytest`
7. Run linter: `ruff check .`
8. Commit: `git commit -m "feat: your feature"`
9. Push: `git push origin feature/your-feature`
10. Open a Pull Request

## Development Setup

```bash
# Install in development mode
make dev

# Or manually
pip install -e ".[dev]"
playwright install chromium

# Run tests
pytest --cov=.

# Format code
ruff format .

# Lint code
ruff check --fix .
```

## Code Style

- Python 3.11+ type hints required
- Use `async`/`await` for all I/O operations
- Follow existing patterns in the codebase
- Add docstrings to public functions
- Prefer shared handler logic in `mcp_server/handlers.py` for unified actions
- Update docs when MCP tools or CLI commands change

## Project Structure

```
MCPSearch/
├── agents/            # Research orchestration
├── crawler/          # Web crawling engines
├── mcp_server/       # MCP protocol server and shared action handlers
├── search/           # Search aggregators
├── social/           # Social media scrapers
├── summarizer/       # AI summarization
├── tests/            # Unit and integration tests
├── utils/            # Utilities (rate limiter, cache, dedup, etc.)
├── cli.py            # CLI interface
└── docs/             # Project docs and implementation notes
```

## Adding a New Tool

1. Implement reusable logic in the appropriate module or in `mcp_server/handlers.py` if it is part of the unified action flow.
2. Add the MCP-facing tool in [`mcp_server/server.py`](mcp_server/server.py) with `@mcp.tool()`.
3. Include type hints for all parameters.
4. Add or extend tests in [`tests/`](tests).
5. Update [`README.md`](README.md) and any relevant docs under [`docs/`](docs).

## Running Useful Checks

```bash
make test
make test-cov
make lint
make format
python3 final_verification.py
```

## Documentation Expectations

- Keep README examples aligned with current tool names such as `mcpsearch`, `mcpsearch_multi`, `investigate`, `compare`, and `trending`.
- If a feature is optional at install time, say so clearly.
- If behavior changed but a legacy tool still exists, document which path is preferred.

## Reporting Issues

- Use the GitHub issue tracker
- Include Python version and OS
- Provide minimal reproduction steps
- Include error messages/tracebacks

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
