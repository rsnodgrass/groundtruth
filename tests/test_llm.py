"""Tests for groundtruth.llm module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from groundtruth.config import (
    Decision,
    ExtractionResult,
    ParticipantConfig,
    TrackerConfig,
)
from groundtruth.llm import (
    ClaudeCodeProvider,
    LiteLLMProvider,
    Metrics,
    detect_participants_from_transcript,
    ensure_participants,
    extract_decisions_from_transcript_json,
    get_provider,
)


class TestMetrics:
    """Tests for Metrics class."""

    def test_metrics_initialization(self) -> None:
        """Test metrics initializes with zero values."""
        metrics = Metrics()
        assert metrics.llm_calls == 0
        assert metrics.files_processed == 0
        assert metrics.participant_detection_time == 0.0
        assert metrics.decision_extraction_time == 0.0

    def test_metrics_reset(self) -> None:
        """Test metrics reset functionality."""
        metrics = Metrics()
        metrics.llm_calls = 5
        metrics.files_processed = 3
        metrics.participant_detection_time = 10.5

        metrics.reset()

        assert metrics.llm_calls == 0
        assert metrics.files_processed == 0
        assert metrics.participant_detection_time == 0.0

    def test_metrics_log_summary(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that log_summary outputs metrics."""
        metrics = Metrics()
        metrics.files_processed = 2
        metrics.llm_calls = 4
        metrics.participant_detection_time = 5.0
        metrics.decision_extraction_time = 10.0

        with caplog.at_level("INFO"):
            metrics.log_summary()

        # check that summary was logged
        assert "PERFORMANCE METRICS" in caplog.text
        assert "files_processed=2" in caplog.text
        assert "total_llm_calls=4" in caplog.text


class TestLiteLLMProvider:
    """Tests for LiteLLMProvider class."""

    def test_initialization_default_model(self) -> None:
        """Test LiteLLMProvider initializes with default model."""
        provider = LiteLLMProvider()
        assert provider.model == "claude-sonnet-4-20250514"

    def test_initialization_custom_model(self) -> None:
        """Test LiteLLMProvider initializes with custom model."""
        provider = LiteLLMProvider(model="gpt-4")
        assert provider.model == "gpt-4"

    def test_parse_participant_response_valid_json(self) -> None:
        """Test parsing valid participant detection JSON."""
        provider = LiteLLMProvider()
        json_response = """{
  "participants": [
    {"name": "Alice", "role": "CEO"},
    {"name": "Bob", "role": "CTO"}
  ],
  "reasoning": "Found two participants"
}"""

        participants = provider._parse_participant_response(json_response)

        assert len(participants) == 2
        assert participants[0].name == "Alice"
        assert participants[0].role == "CEO"
        assert participants[1].name == "Bob"
        assert participants[1].role == "CTO"

    def test_parse_participant_response_with_markdown(self) -> None:
        """Test parsing JSON wrapped in markdown code blocks."""
        provider = LiteLLMProvider()
        json_response = """```json
{
  "participants": [
    {"name": "Alice", "role": "CEO"}
  ],
  "reasoning": "Found one participant"
}
```"""

        participants = provider._parse_participant_response(json_response)

        assert len(participants) == 1
        assert participants[0].name == "Alice"

    def test_parse_participant_response_empty_list(self) -> None:
        """Test parsing response with no participants."""
        provider = LiteLLMProvider()
        json_response = """{
  "participants": [],
  "reasoning": "No participants detected"
}"""

        participants = provider._parse_participant_response(json_response)
        assert len(participants) == 0

    def test_parse_participant_response_invalid_json(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test parsing invalid JSON returns empty list."""
        provider = LiteLLMProvider()
        invalid_json = "This is not JSON"

        with caplog.at_level("ERROR"):
            participants = provider._parse_participant_response(invalid_json)

        assert len(participants) == 0
        assert "Failed to parse" in caplog.text

    def test_parse_participant_response_missing_name(self) -> None:
        """Test parsing response where participant has no name."""
        provider = LiteLLMProvider()
        json_response = """{
  "participants": [
    {"role": "CEO"},
    {"name": "Bob", "role": "CTO"}
  ]
}"""

        participants = provider._parse_participant_response(json_response)

        # only Bob should be included (has name)
        assert len(participants) == 1
        assert participants[0].name == "Bob"

    @patch("groundtruth.llm.get_participant_detection_prompt")
    @patch("groundtruth.llm.completion")
    def test_detect_participants_success(
        self,
        mock_completion: Mock,
        mock_get_prompt: Mock,
    ) -> None:
        """Test successful participant detection via LiteLLM."""
        provider = LiteLLMProvider()
        mock_get_prompt.return_value = "Detect participants from: {transcript}"

        # mock LiteLLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """{
  "participants": [
    {"name": "Alice", "role": "CEO"}
  ],
  "reasoning": "Test"
}"""
        mock_completion.return_value = mock_response

        transcript = "Alice: Let's discuss the project."
        participants = provider.detect_participants(transcript)

        assert len(participants) == 1
        assert participants[0].name == "Alice"

        # verify LiteLLM was called correctly
        mock_completion.assert_called_once()
        call_args = mock_completion.call_args
        assert call_args.kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_args.kwargs["temperature"] == 0.1

    @patch("groundtruth.llm.get_participant_detection_prompt")
    @patch("groundtruth.llm.completion")
    def test_detect_participants_truncates_long_transcript(
        self,
        mock_completion: Mock,
        mock_get_prompt: Mock,
    ) -> None:
        """Test that long transcripts are truncated for participant detection."""
        provider = LiteLLMProvider()
        mock_get_prompt.return_value = "Detect participants from: {transcript}"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"participants": []}'
        mock_completion.return_value = mock_response

        # create transcript longer than 4000 chars
        long_transcript = "A" * 5000

        provider.detect_participants(long_transcript)

        # verify the transcript was truncated
        call_args = mock_completion.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        # prompt should not contain full 5000 char transcript
        assert "A" * 5000 not in prompt

    @patch("groundtruth.llm.get_participant_detection_prompt")
    @patch("groundtruth.llm.completion")
    def test_detect_participants_handles_error(
        self,
        mock_completion: Mock,
        mock_get_prompt: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test error handling in participant detection."""
        provider = LiteLLMProvider()
        mock_get_prompt.return_value = "Detect participants from: {transcript}"
        mock_completion.side_effect = Exception("API error")

        with caplog.at_level("ERROR"):
            participants = provider.detect_participants("Test transcript")

        assert len(participants) == 0
        assert "Participant detection failed" in caplog.text

    @patch("groundtruth.llm.get_participant_detection_prompt")
    @patch("groundtruth.llm.completion")
    def test_detect_participants_empty_content(
        self,
        mock_completion: Mock,
        mock_get_prompt: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test handling of empty response content."""
        provider = LiteLLMProvider()
        mock_get_prompt.return_value = "Detect participants from: {transcript}"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_completion.return_value = mock_response

        with caplog.at_level("WARNING"):
            participants = provider.detect_participants("Test")

        assert len(participants) == 0
        assert "Empty response" in caplog.text


class TestClaudeCodeProvider:
    """Tests for ClaudeCodeProvider class."""

    def test_initialization_default_path(self) -> None:
        """Test ClaudeCodeProvider initializes with default CLI path."""
        provider = ClaudeCodeProvider()
        assert provider.claude_code_path == "claude"

    def test_initialization_custom_path(self) -> None:
        """Test ClaudeCodeProvider initializes with custom CLI path."""
        provider = ClaudeCodeProvider(claude_code_path="/usr/local/bin/claude")
        assert provider.claude_code_path == "/usr/local/bin/claude"

    def test_parse_participant_response(self) -> None:
        """Test parsing participant detection response."""
        provider = ClaudeCodeProvider()
        json_response = """{
  "participants": [
    {"name": "Alice", "role": "CEO"}
  ],
  "reasoning": "Test"
}"""

        participants = provider._parse_participant_response(json_response)
        assert len(participants) == 1
        assert participants[0].name == "Alice"

    def test_parse_json_extraction_response_envelope_with_string(self) -> None:
        """Test parsing JSON extraction response with envelope wrapper."""
        provider = ClaudeCodeProvider()
        envelope_response = """{
  "result": "{\\"decisions\\": [{\\"category\\": \\"Tech\\", \\"significance\\": 2, \\"status\\": \\"Agreed\\", \\"title\\": \\"Test\\", \\"description\\": \\"Test\\", \\"decision\\": \\"Test\\", \\"agreements\\": {\\"Alice\\": \\"Yes\\"}}]}"
}"""

        result = provider._parse_json_extraction_response(
            envelope_response,
            ["Alice"],
        )

        assert len(result.decisions) == 1
        assert result.decisions[0].category == "Tech"

    def test_parse_json_extraction_response_envelope_with_dict(self) -> None:
        """Test parsing JSON extraction response with dict result."""
        provider = ClaudeCodeProvider()
        envelope_response = """{
  "result": {
    "decisions": [
      {
        "category": "Tech",
        "significance": 2,
        "status": "Agreed",
        "title": "Test",
        "description": "Test",
        "decision": "Test",
        "agreements": {"Alice": "Yes"}
      }
    ]
  }
}"""

        result = provider._parse_json_extraction_response(
            envelope_response,
            ["Alice"],
        )

        assert len(result.decisions) == 1
        assert result.decisions[0].category == "Tech"

    def test_parse_json_extraction_response_direct_json(self) -> None:
        """Test parsing direct JSON response without envelope."""
        provider = ClaudeCodeProvider()
        direct_response = """{
  "decisions": [
    {
      "category": "Tech",
      "significance": 2,
      "status": "Agreed",
      "title": "Test",
      "description": "Test",
      "decision": "Test",
      "agreements": {"Alice": "Yes"}
    }
  ]
}"""

        result = provider._parse_json_extraction_response(direct_response, ["Alice"])

        assert len(result.decisions) == 1
        assert result.decisions[0].title == "Test"

    def test_parse_json_extraction_response_with_markdown(self) -> None:
        """Test parsing JSON with markdown code blocks in envelope."""
        provider = ClaudeCodeProvider()
        envelope_response = """{
  "result": "```json\\n{\\"decisions\\": []}\\n```"
}"""

        result = provider._parse_json_extraction_response(envelope_response, [])
        assert len(result.decisions) == 0

    def test_parse_json_extraction_response_invalid_decision(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that invalid decisions are skipped with warning."""
        provider = ClaudeCodeProvider()
        response = """{
  "decisions": [
    {
      "category": "Tech",
      "significance": 99,
      "status": "Agreed",
      "title": "Test",
      "description": "Test",
      "decision": "Test",
      "agreements": {"Alice": "Yes"}
    }
  ]
}"""

        with caplog.at_level("WARNING"):
            result = provider._parse_json_extraction_response(response, ["Alice"])

        assert len(result.decisions) == 0
        assert "Failed to parse decision" in caplog.text

    def test_parse_json_extraction_response_invalid_json(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test handling of invalid JSON in extraction response."""
        provider = ClaudeCodeProvider()
        invalid_response = "This is not JSON"

        with caplog.at_level("ERROR"):
            result = provider._parse_json_extraction_response(invalid_response, [])

        assert len(result.decisions) == 0
        assert "Failed to parse JSON response" in caplog.text

    @patch("groundtruth.llm.get_participant_detection_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_detect_participants_success(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
    ) -> None:
        """Test successful participant detection via Claude Code CLI."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Detect participants from: {transcript}"

        # Claude Code returns JSON envelope when using --output-format json
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"type":"result","result":"{\\"participants\\": [{\\"name\\": \\"Alice\\", \\"role\\": \\"CEO\\"}], \\"reasoning\\": \\"Test\\"}"}'
        mock_run.return_value = mock_result

        participants = provider.detect_participants("Alice: Hello")

        assert len(participants) == 1
        assert participants[0].name == "Alice"

        # verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args.args[0] == ["claude", "--print", "--output-format", "json"]
        assert call_args.kwargs["capture_output"] is True
        assert call_args.kwargs["text"] is True

    @patch("groundtruth.llm.get_participant_detection_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_detect_participants_cli_error(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test handling of CLI error in participant detection."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Detect participants from: {transcript}"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "CLI error"
        mock_run.return_value = mock_result

        with caplog.at_level("ERROR"):
            participants = provider.detect_participants("Test")

        assert len(participants) == 0
        assert "CLI failed" in caplog.text

    @patch("groundtruth.llm.get_participant_detection_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_detect_participants_timeout(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test handling of timeout in participant detection."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Detect participants from: {transcript}"
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 120)

        with caplog.at_level("ERROR"):
            participants = provider.detect_participants("Test")

        assert len(participants) == 0

    @patch("groundtruth.config.get_decision_extraction_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_extract_decisions_json_success(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test successful JSON decision extraction."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Extract decisions from: {transcript}"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """{
  "result": {
    "decisions": [
      {
        "category": "Tech",
        "significance": 2,
        "status": "Agreed",
        "title": "Test Decision",
        "description": "Test",
        "decision": "Test",
        "agreements": {"Alice": "Yes", "Bob": "Yes", "Carol": "No"}
      }
    ]
  }
}"""
        mock_run.return_value = mock_result

        result = provider.extract_decisions_json("Test transcript", sample_config)

        assert len(result.decisions) == 1
        assert result.decisions[0].title == "Test Decision"

        # verify CLI was called with correct arguments
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "--output-format" in call_args.args[0]
        assert "json" in call_args.args[0]

    @patch("groundtruth.config.get_decision_extraction_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_extract_decisions_json_cli_error(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test handling of CLI error in decision extraction."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Extract decisions from: {transcript}"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "CLI error"
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError, match="exited with code"):
            provider.extract_decisions_json("Test", sample_config)

    @patch("groundtruth.config.get_decision_extraction_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_extract_decisions_json_timeout(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test handling of timeout in decision extraction."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Extract decisions from: {transcript}"
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 300)

        with pytest.raises(RuntimeError, match="timed out"):
            provider.extract_decisions_json("Test", sample_config)

    @patch("groundtruth.config.get_decision_extraction_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_extract_decisions_json_not_found(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test handling of CLI not found error."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Extract decisions from: {transcript}"
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(RuntimeError, match="not found"):
            provider.extract_decisions_json("Test", sample_config)


class TestGetProvider:
    """Tests for get_provider function."""

    def test_get_claude_code_provider(self, sample_config: TrackerConfig) -> None:
        """Test getting Claude Code provider."""
        sample_config.model_provider = "claude-code"
        provider = get_provider(sample_config)

        assert isinstance(provider, ClaudeCodeProvider)

    def test_get_claude_code_provider_case_insensitive(
        self,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that provider type is case insensitive."""
        sample_config.model_provider = "CLAUDE-CODE"
        provider = get_provider(sample_config)

        assert isinstance(provider, ClaudeCodeProvider)

    def test_get_litellm_provider_anthropic(
        self,
        sample_config: TrackerConfig,
    ) -> None:
        """Test getting LiteLLM provider for Anthropic."""
        sample_config.model_provider = "anthropic"
        sample_config.model = "claude-sonnet-4-20250514"
        provider = get_provider(sample_config)

        assert isinstance(provider, LiteLLMProvider)
        assert provider.model == "claude-sonnet-4-20250514"

    def test_get_litellm_provider_openai(self, sample_config: TrackerConfig) -> None:
        """Test getting LiteLLM provider for OpenAI."""
        sample_config.model_provider = "openai"
        sample_config.model = "gpt-4"
        provider = get_provider(sample_config)

        assert isinstance(provider, LiteLLMProvider)
        assert provider.model == "gpt-4"


class TestDetectParticipantsFromTranscript:
    """Tests for detect_participants_from_transcript function."""

    @patch("groundtruth.llm.get_provider")
    def test_detect_participants_uses_provider(
        self,
        mock_get_provider: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that detect_participants_from_transcript uses the correct provider."""
        mock_provider = MagicMock()
        mock_provider.detect_participants.return_value = [
            ParticipantConfig(name="Alice", role="CEO")
        ]
        mock_get_provider.return_value = mock_provider

        participants = detect_participants_from_transcript("Test transcript", sample_config)

        assert len(participants) == 1
        assert participants[0].name == "Alice"
        mock_get_provider.assert_called_once_with(sample_config)
        mock_provider.detect_participants.assert_called_once_with("Test transcript")


class TestEnsureParticipants:
    """Tests for ensure_participants function."""

    def test_ensure_participants_uses_explicit_config(
        self,
        sample_config: TrackerConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that explicit participants in config are used."""
        with caplog.at_level("INFO"):
            result_config = ensure_participants("Test transcript", sample_config)

        assert result_config.participants == sample_config.participants
        assert "explicitly configured" in caplog.text

    @patch("groundtruth.llm.detect_participants_from_transcript")
    def test_ensure_participants_detects_when_default(
        self,
        mock_detect: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that participants are detected when using defaults."""
        config = TrackerConfig(
            participants=[
                ParticipantConfig(name="Ryan"),
                ParticipantConfig(name="Ajit"),
                ParticipantConfig(name="Milkana"),
            ]
        )

        mock_detect.return_value = [
            ParticipantConfig(name="Alice", role="CEO"),
            ParticipantConfig(name="Bob", role="CTO"),
        ]

        with caplog.at_level("INFO"):
            result_config = ensure_participants("Test transcript", config)

        assert len(result_config.participants) == 2
        assert result_config.participants[0].name == "Alice"
        assert "detecting from transcript" in caplog.text
        mock_detect.assert_called_once()

    @patch("groundtruth.llm.detect_participants_from_transcript")
    def test_ensure_participants_uses_defaults_on_detection_failure(
        self,
        mock_detect: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that defaults are used when detection fails."""
        config = TrackerConfig(
            participants=[
                ParticipantConfig(name="Ryan"),
                ParticipantConfig(name="Ajit"),
                ParticipantConfig(name="Milkana"),
            ]
        )

        mock_detect.return_value = []  # detection failed

        with caplog.at_level("WARNING"):
            result_config = ensure_participants("Test transcript", config)

        assert len(result_config.participants) == 3  # still has defaults
        assert "using defaults" in caplog.text


class TestExtractDecisionsFromTranscriptJSON:
    """Tests for extract_decisions_from_transcript_json function."""

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_decisions_success(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test successful decision extraction from file."""
        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=2,
                    status="Agreed",
                    title="Test",
                    description="Test",
                    decision="Test",
                    agreements={"Alice": "Yes"},
                )
            ],
            participants_detected=["Alice"],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
        )

        assert len(result.decisions) == 1
        assert result.decisions[0].meeting_reference == "meeting-2025-01-15.txt"

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_decisions_extracts_date_from_filename(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that meeting date is extracted from filename."""
        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=2,
                    status="Agreed",
                    title="Test",
                    description="Test",
                    decision="Test",
                    agreements={"Alice": "Yes"},
                )
            ],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
        )

        assert result.decisions[0].meeting_date == "2025-01-15"

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_decisions_no_auto_detect(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test extraction without auto-detecting participants."""
        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(decisions=[])
        mock_get_provider.return_value = mock_provider

        extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
            auto_detect_participants=False,
        )

        # ensure_participants should not be called
        mock_ensure_participants.assert_not_called()

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_decisions_provider_not_supported(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test error when provider doesn't support JSON extraction."""
        mock_ensure_participants.return_value = sample_config

        # mock provider without extract_decisions_json method
        mock_provider = MagicMock(spec=LiteLLMProvider)
        mock_get_provider.return_value = mock_provider

        with pytest.raises(NotImplementedError, match="does not support JSON extraction"):
            extract_decisions_from_transcript_json(
                temp_transcript_file,
                sample_config,
            )

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_decisions_fills_meeting_metadata(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that meeting date and reference are filled in."""
        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=2,
                    status="Agreed",
                    title="Test",
                    description="Test",
                    decision="Test",
                    agreements={"Alice": "Yes"},
                    meeting_date="",
                    meeting_reference="",
                )
            ],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
            meeting_date="2025-02-20",
        )

        assert result.decisions[0].meeting_date == "2025-02-20"
        assert result.decisions[0].meeting_reference == "meeting-2025-01-15.txt"
