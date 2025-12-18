# Groundtruth Test Suite

This directory contains the comprehensive test suite for the groundtruth package using pytest.

## Test Structure

```
tests/
├── __init__.py          - Package marker
├── conftest.py          - Common fixtures and test configuration
├── test_config.py       - Tests for config module
├── test_llm.py          - Tests for LLM provider classes
└── test_extraction.py   - Integration tests for extraction functions
```

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run with verbose output
```bash
pytest tests/ -v
```

### Run specific test file
```bash
pytest tests/test_config.py
pytest tests/test_llm.py
pytest tests/test_extraction.py
```

### Run specific test class
```bash
pytest tests/test_config.py::TestDecisionModel
pytest tests/test_llm.py::TestClaudeCodeProvider
```

### Run specific test
```bash
pytest tests/test_config.py::TestDecisionModel::test_valid_decision
```

### Run with markers
```bash
pytest tests/ -m integration
pytest tests/ -m "not slow"
```

## Test Coverage

### test_config.py (38 tests)
Tests for configuration management:
- Decision model validation (valid/invalid data)
- ExtractionResult model
- decisions_to_csv_rows conversion
- load_config with valid/invalid YAML
- save_config roundtrip
- merge_frameworks (YAML and markdown)
- get_default_config
- TrackerConfig properties
- get_json_schema_for_extraction
- build_json_extraction_prompt (skipped - uses external templates)

### test_llm.py (47 tests)
Tests for LLM provider classes:
- Metrics tracking
- LiteLLMProvider initialization and methods
- ClaudeCodeProvider initialization and methods
- JSON parsing for participant detection
- JSON parsing for decision extraction
- Subprocess mocking for Claude Code CLI
- Error handling and timeouts
- get_provider factory function
- detect_participants_from_transcript
- ensure_participants logic
- extract_decisions_from_transcript_json

### test_extraction.py (19 tests)
Integration-style tests:
- Single file extraction with mocked providers
- Missing file error handling
- Custom meeting dates
- Date extraction from filenames
- Multiple decisions from one file
- Parallel folder extraction
- Multiple file processing
- File pattern filtering
- Error handling during parallel processing
- Participant merging across files
- Decision sorting
- Worker pool configuration

## Fixtures

Common fixtures are defined in `conftest.py`:
- sample_decision_data: Sample decision dictionary
- sample_decision: Sample Decision object
- sample_participants: Sample participant configurations
- sample_categories: Sample category configurations
- sample_types: Sample type configurations
- sample_agreement_rules: Sample agreement rules
- sample_config: Complete TrackerConfig
- sample_transcript: Sample meeting transcript
- sample_yaml_config: Sample YAML configuration
- temp_transcript_file: Temporary transcript file
- temp_config_file: Temporary config file
- sample_json_response: Sample LLM JSON response
- sample_json_response_with_markdown: JSON with markdown blocks
- sample_participant_detection_response: Participant detection response

## Mocking Strategy

Tests use `unittest.mock` and `pytest-mock` for mocking external dependencies:
- External LLM API calls (litellm.completion)
- Subprocess calls to Claude Code CLI
- File I/O operations
- Prompt template loading

## Test Requirements

The test suite requires:
- pytest >= 7.0.0
- pytest-mock >= 3.12.0

Install with:
```bash
uv pip install -e ".[dev]"
```

## Configuration

Pytest configuration is in `pyproject.toml`:
- Test discovery patterns
- Verbose output by default
- Strict marker enforcement
- Custom markers: slow, integration

## Test Principles

1. Fast execution - All external calls are mocked
2. Isolated - Each test is independent
3. Comprehensive - Cover success paths, error paths, and edge cases
4. Maintainable - Use fixtures to reduce duplication
5. Descriptive - Clear test names and docstrings

## Current Status

- 96 tests passing
- 8 tests skipped (prompt template tests - tested indirectly)
- Test execution time: ~2 seconds
- All critical paths covered
