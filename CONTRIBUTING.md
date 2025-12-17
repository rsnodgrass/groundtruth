# Contributing to Groundtruth

Thank you for your interest in contributing to Groundtruth!

## Getting Started

1. Fork the repository
2. Clone your fork
3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Development Workflow

1. Create a branch for your feature or fix
2. Make your changes
3. Run tests: `pytest`
4. Run linting: `ruff check src/`
5. Run type checking: `mypy src/`
6. Submit a pull request

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for public functions
- Keep functions focused and small

## Areas for Contribution

### High Priority
- Improve agreement detection heuristics
- Add support for more transcript formats (VTT, SRT, etc.)
- Better handling of multi-day discussions
- Visualization and reporting features

### Nice to Have
- Integration with calendar systems
- Slack/Teams notifications for unresolved decisions
- Web UI for reviewing Groundtruth reports
- AI-assisted decision extraction

## Commit Messages

Use conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Tests

## Questions?

Open an issue or start a discussion on GitHub.
