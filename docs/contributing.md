# Contributing

Contributions welcome! This guide covers development setup, testing, and contribution guidelines.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/rsnodgrass/groundtruth.git
cd groundtruth

# Install dev dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=groundtruth

# Run specific test file
pytest tests/test_extraction.py
```

## Linting

```bash
# Check code style
ruff check src/

# Auto-fix issues
ruff check src/ --fix
```

## Project Structure

```
groundtruth/
├── src/
│   └── groundtruth/
│       ├── __init__.py
│       ├── cli.py          # CLI commands
│       ├── extract.py      # Decision extraction
│       ├── process.py      # Batch processing
│       ├── formats.py      # CSV/XLSX output
│       └── providers/      # LLM providers
├── tests/
├── docs/
└── examples/
```

## Contribution Guidelines

### Before You Start

1. Check existing issues for similar work
2. Open an issue to discuss significant changes
3. Fork the repository
4. Create a feature branch from `main`

### Pull Request Process

1. Write clear, focused commits
2. Include tests for new functionality
3. Update documentation as needed
4. Ensure all tests pass
5. Request review from maintainers

### Code Style

- Follow PEP 8
- Use type hints
- Keep functions focused and small
- Write clear docstrings for public APIs
- Use descriptive variable names

### Commit Messages

- Use present tense ("Add feature" not "Added feature")
- Be descriptive but concise
- Reference issues when relevant

## Key Areas for Contribution

- **Agreement detection heuristics** - Improve accuracy of agreement assessment
- **Transcript format support** - Add support for more transcription services
- **Multi-day discussions** - Better handling of decisions that span meetings
- **Visualization features** - Charts, dashboards, trend analysis

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/rsnodgrass/groundtruth/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rsnodgrass/groundtruth/discussions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## See Also

- **[Decision Frameworks](decision-frameworks.md)** - Define who must agree on what for your team
- [Getting Started](getting-started.md) - Installation and first extraction
- [CLI Reference](cli-reference.md) - Command documentation
