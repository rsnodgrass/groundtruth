"""Integration-style tests for decision extraction."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from groundtruth.config import Decision, ExtractionResult, TrackerConfig
from groundtruth.llm import (
    extract_decisions_from_folder_parallel,
    extract_decisions_from_transcript_json,
)


class TestExtractDecisionsFromTranscriptJSON:
    """Integration tests for single file extraction."""

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_from_real_file(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test extracting decisions from actual file on disk."""
        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Technical Architecture",
                    significance=2,
                    status="Agreed",
                    title="Use PostgreSQL",
                    description="Database decision",
                    decision="Use PostgreSQL",
                    agreements={"Alice": "Yes", "Bob": "Yes"},
                )
            ],
            participants_detected=["Alice", "Bob"],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
        )

        assert len(result.decisions) == 1
        assert result.decisions[0].category == "Technical Architecture"
        assert result.participants_detected == ["Alice", "Bob"]

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_missing_file(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test error handling for missing file."""
        missing_file = Path("/nonexistent/file.txt")

        with pytest.raises(FileNotFoundError):
            extract_decisions_from_transcript_json(missing_file, sample_config)

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_with_custom_date(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test extraction with custom meeting date."""
        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=3,
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
            meeting_date="2025-12-25",
        )

        assert result.decisions[0].meeting_date == "2025-12-25"

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_file_with_no_date_in_filename(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test extraction from file without date in filename."""
        no_date_file = tmp_path / "meeting-notes.txt"
        no_date_file.write_text(sample_transcript, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=3,
                    status="Agreed",
                    title="Test",
                    description="Test",
                    decision="Test",
                    agreements={"Alice": "Yes"},
                )
            ],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(no_date_file, sample_config)

        # meeting_date should be empty since not extracted from filename
        assert result.decisions[0].meeting_date == ""
        assert result.decisions[0].meeting_reference == "meeting-notes.txt"

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_reads_file_content(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that file content is correctly read and passed to provider."""
        transcript_content = "Alice: I propose we use Rust.\nBob: Agreed!"
        transcript_file = tmp_path / "meeting.txt"
        transcript_file.write_text(transcript_content, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(decisions=[])
        mock_get_provider.return_value = mock_provider

        extract_decisions_from_transcript_json(transcript_file, sample_config)

        # verify the provider was called with the transcript content
        call_args = mock_provider.extract_decisions_json.call_args
        assert call_args.args[0] == transcript_content

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_multiple_decisions_from_one_file(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test extracting multiple decisions from single file."""
        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=1,
                    status="Agreed",
                    title="Decision 1",
                    description="First decision",
                    decision="Use Rust",
                    agreements={"Alice": "Yes"},
                ),
                Decision(
                    category="GTM",
                    significance=3,
                    status="Needs Clarification",
                    title="Decision 2",
                    description="Second decision",
                    decision="Launch in Q2",
                    agreements={"Alice": "Partial"},
                ),
            ],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
        )

        assert len(result.decisions) == 2
        assert result.decisions[0].title == "Decision 1"
        assert result.decisions[1].title == "Decision 2"


class TestExtractDecisionsFromFolderParallel:
    """Integration tests for parallel folder extraction."""

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_from_empty_folder(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test extracting from folder with no matching files."""
        with pytest.raises(ValueError, match="No transcript files found"):
            extract_decisions_from_folder_parallel(
                tmp_path,
                sample_config,
                pattern="*.txt",
            )

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_from_folder_single_file(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test extracting from folder with single file."""
        transcript_file = tmp_path / "meeting-2025-01-15.txt"
        transcript_file.write_text(sample_transcript, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=2,
                    status="Agreed",
                    title="Test Decision",
                    description="Test",
                    decision="Test",
                    agreements={"Alice": "Yes", "Bob": "Yes", "Carol": "Partial"},
                )
            ],
            participants_detected=["Alice", "Bob", "Carol"],
        )
        mock_get_provider.return_value = mock_provider

        rows = extract_decisions_from_folder_parallel(tmp_path, sample_config)

        # should have header + 1 data row
        assert len(rows) == 2
        assert rows[0][0] == "Category"  # header
        assert "Alice Agreed" in rows[0]
        assert rows[1][0] == "Tech"  # data

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_from_folder_multiple_files(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test extracting from folder with multiple files."""
        # create multiple transcript files
        for i in range(3):
            transcript_file = tmp_path / f"meeting-{i}.txt"
            transcript_file.write_text(sample_transcript, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        decision_count = 0

        def mock_extract_json(transcript: str, config: TrackerConfig) -> ExtractionResult:
            nonlocal decision_count
            decision_count += 1
            return ExtractionResult(
                decisions=[
                    Decision(
                        category="Tech",
                        significance=decision_count,
                        status="Agreed",
                        title=f"Decision {decision_count}",
                        description="Test",
                        decision="Test",
                        agreements={"Alice": "Yes"},
                    )
                ],
                participants_detected=["Alice"],
            )

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.side_effect = mock_extract_json
        mock_get_provider.return_value = mock_provider

        rows = extract_decisions_from_folder_parallel(
            tmp_path,
            sample_config,
            max_workers=2,
        )

        # should have header + 3 data rows
        assert len(rows) == 4
        assert rows[0][0] == "Category"

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_from_folder_with_pattern(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test extracting with custom file pattern."""
        # create files with different extensions
        txt_file = tmp_path / "meeting.txt"
        txt_file.write_text(sample_transcript, encoding="utf-8")

        md_file = tmp_path / "meeting.md"
        md_file.write_text(sample_transcript, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[],
            participants_detected=[],
        )
        mock_get_provider.return_value = mock_provider

        # extract only .md files
        rows = extract_decisions_from_folder_parallel(
            tmp_path,
            sample_config,
            pattern="*.md",
        )

        # should only process 1 file (the .md file)
        assert mock_provider.extract_decisions_json.call_count == 1

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_handles_file_errors(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that file processing errors are handled gracefully."""
        # create two files
        file1 = tmp_path / "meeting-1.txt"
        file1.write_text(sample_transcript, encoding="utf-8")

        file2 = tmp_path / "meeting-2.txt"
        file2.write_text(sample_transcript, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        call_count = 0

        def mock_extract_json(transcript: str, config: TrackerConfig) -> ExtractionResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Extraction failed")
            return ExtractionResult(
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

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.side_effect = mock_extract_json
        mock_get_provider.return_value = mock_provider

        with caplog.at_level("WARNING"):
            rows = extract_decisions_from_folder_parallel(tmp_path, sample_config)

        # should have header + 1 successful extraction
        assert len(rows) == 2

        # should log the failed file
        assert "Failed to process" in caplog.text

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_merges_participants_from_all_files(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that participants are merged from all processed files."""
        file1 = tmp_path / "meeting-1.txt"
        file1.write_text(sample_transcript, encoding="utf-8")

        file2 = tmp_path / "meeting-2.txt"
        file2.write_text(sample_transcript, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        call_count = 0

        def mock_extract_json(transcript: str, config: TrackerConfig) -> ExtractionResult:
            nonlocal call_count
            call_count += 1
            participants = ["Alice", "Bob"] if call_count == 1 else ["Bob", "Carol"]
            return ExtractionResult(
                decisions=[],
                participants_detected=participants,
            )

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.side_effect = mock_extract_json
        mock_get_provider.return_value = mock_provider

        rows = extract_decisions_from_folder_parallel(tmp_path, sample_config)

        # check that header includes all unique participants
        header = rows[0]
        # config has Alice, Bob, Carol so all should be in header
        assert "Alice Agreed" in header
        assert "Bob Agreed" in header
        assert "Carol Agreed" in header

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_with_max_workers(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test parallel extraction with different worker counts."""
        # create 5 files
        for i in range(5):
            file = tmp_path / f"meeting-{i}.txt"
            file.write_text(sample_transcript, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[],
            participants_detected=[],
        )
        mock_get_provider.return_value = mock_provider

        # test with different worker counts
        for workers in [1, 2, 4]:
            mock_provider.extract_decisions_json.reset_mock()
            rows = extract_decisions_from_folder_parallel(
                tmp_path,
                sample_config,
                max_workers=workers,
            )

            # all files should be processed regardless of worker count
            assert mock_provider.extract_decisions_json.call_count == 5

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_decisions_are_sorted(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that decisions in output are sorted by category and significance."""
        file1 = tmp_path / "meeting.txt"
        file1.write_text(sample_transcript, encoding="utf-8")

        mock_ensure_participants.return_value = sample_config

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Security",
                    significance=3,
                    status="Agreed",
                    title="D1",
                    description="D1",
                    decision="D1",
                    agreements={"Alice": "Yes"},
                ),
                Decision(
                    category="Go-to-Market",
                    significance=1,
                    status="Agreed",
                    title="D2",
                    description="D2",
                    decision="D2",
                    agreements={"Alice": "Yes"},
                ),
                Decision(
                    category="Security",
                    significance=1,
                    status="Agreed",
                    title="D3",
                    description="D3",
                    decision="D3",
                    agreements={"Alice": "Yes"},
                ),
            ],
            participants_detected=["Alice"],
        )
        mock_get_provider.return_value = mock_provider

        rows = extract_decisions_from_folder_parallel(tmp_path, sample_config)

        # check order: GTM (sig 1), Security (sig 1), Security (sig 3)
        assert rows[1][0] == "Go-to-Market"
        assert rows[2][0] == "Security"
        assert rows[2][1] == "1"
        assert rows[3][0] == "Security"
        assert rows[3][1] == "3"

    @patch("groundtruth.llm.get_provider")
    @patch("groundtruth.llm.ensure_participants")
    def test_extract_without_auto_detect_participants(
        self,
        mock_ensure_participants: Mock,
        mock_get_provider: Mock,
        tmp_path: Path,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test folder extraction without auto-detecting participants."""
        file1 = tmp_path / "meeting.txt"
        file1.write_text(sample_transcript, encoding="utf-8")

        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[],
            participants_detected=[],
        )
        mock_get_provider.return_value = mock_provider

        extract_decisions_from_folder_parallel(
            tmp_path,
            sample_config,
            auto_detect_participants=False,
        )

        # ensure_participants should not be called when auto_detect_participants=False
        mock_ensure_participants.assert_not_called()
