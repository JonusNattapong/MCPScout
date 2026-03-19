# Contributing to MCPScout

Thank you for your interest in contributing to MCPScout! This document provides guidelines for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/MCPScout.git`
3. Create a branch: `git checkout -b feature/your-feature`
4. Install dependencies: `pip install -e ".[dev]"`
5. Make your changes
6. Run tests: `pytest`
7. Run linter: `ruff check .`
8. Commit: `git commit -m "feat: your feature"`
9. Push: `git push origin feature/your-feature`
10. Open a Pull Request

## Development Setup

```bash
# Install in development mode
pip install -e ".[dev]"

# Install Playwright browsers
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
- Keep functions under 100 lines

## Project Structure

```
MCPScout/
├── crawler/          # Web crawling engines
├── search/           # Search aggregators
├── social/           # Social media scrapers
├── mcp_server/       # MCP protocol server
├── summarizer/       # AI summarization
├── utils/            # Utilities (rate limiter, etc.)
├── cli.py            # CLI interface
└── tests/            # Test suite
```

## Adding a New Tool

1. Implement the tool function in the appropriate module
2. Add to `mcp_server/server.py` with `@mcp.tool()` decorator
3. Include type hints for all parameters
4. Add tests in `tests/`
5. Update documentation

## Reporting Issues

- Use the GitHub issue tracker
- Include Python version and OS
- Provide minimal reproduction steps
- Include error messages/tracebacks

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
