"""LLM abstraction layer supporting multiple providers via LiteLLM and Claude Code CLI."""

import json
import logging
import subprocess
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from litellm import completion

from groundtruth.config import (
    Decision,
    ExtractionResult,
    ParticipantConfig,
    TrackerConfig,
    build_json_extraction_prompt,
    decisions_to_csv_rows,
)
from groundtruth.prompts import get_participant_detection_prompt

logger = logging.getLogger(__name__)


# retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 1.0  # seconds
MIN_RESPONSE_LENGTH = 10  # minimum chars for a valid response


# metrics tracking
class Metrics:
    """Simple metrics collector for performance analysis."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.llm_calls = 0
        self.participant_detection_calls = 0
        self.decision_extraction_calls = 0
        self.participant_detection_time = 0.0
        self.decision_extraction_time = 0.0
        self.file_read_time = 0.0
        self.csv_parse_time = 0.0
        self.files_processed = 0
        self.total_transcript_chars = 0
        self.retry_count = 0

    def log_summary(self):
        total_llm_time = self.participant_detection_time + self.decision_extraction_time
        logger.info("=== PERFORMANCE METRICS ===")
        logger.info(f"files={self.files_processed}, llm_calls={self.llm_calls}, "
                    f"retries={self.retry_count}")
        logger.info(f"participant_detection: calls={self.participant_detection_calls}, "
                    f"time={self.participant_detection_time:.1f}s")
        logger.info(f"decision_extraction: calls={self.decision_extraction_calls}, "
                    f"time={self.decision_extraction_time:.1f}s")
        logger.info(f"total_llm={total_llm_time:.1f}s, file_read={self.file_read_time:.1f}s, "
                    f"csv_parse={self.csv_parse_time:.1f}s")
        logger.info(f"total_transcript_chars={self.total_transcript_chars}")
        if self.files_processed > 0:
            avg_time = total_llm_time / self.files_processed
            logger.info(f"avg_llm_time_per_file={avg_time:.1f}s")


metrics = Metrics()


class EmptyResponseError(Exception):
    """Raised when LLM returns an empty or invalid response."""

    pass


def validate_response(content: str, min_length: int = MIN_RESPONSE_LENGTH) -> bool:
    """Check if response content is valid (non-empty with minimum length)."""
    if not content:
        return False
    stripped = content.strip()
    return len(stripped) >= min_length


def retry_with_backoff(
    func,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    operation_name: str = "LLM call",
):
    """
    Retry a function with exponential backoff.

    Args:
        func: Callable that returns a result or raises an exception
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay in seconds (doubles each retry: 1s, 2s, 4s)
        operation_name: Name of operation for logging

    Returns:
        Result from successful function call

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            result = func()

            # validate the result if it's a string
            if isinstance(result, str) and not validate_response(result):
                raise EmptyResponseError(f"Empty or invalid response (length={len(result)})")

            return result

        except (EmptyResponseError, subprocess.TimeoutExpired) as e:
            last_exception = e
            if attempt < max_retries:
                delay = backoff_base * (2 ** attempt)
                metrics.retry_count += 1
                logger.warning(f"{operation_name} attempt {attempt + 1}/{max_retries + 1} failed: "
                               f"{e}. Retry in {delay:.1f}s...")
                time.sleep(delay)
            else:
                logger.error(f"{operation_name} failed after {max_retries + 1} attempts: {e}")

        except Exception:
            # don't retry on other exceptions (e.g., FileNotFoundError, auth errors)
            raise

    raise last_exception or RuntimeError(f"{operation_name} failed after retries")


def validate_decision(decision: Decision) -> Decision:
    """
    Ensure Status is logically consistent with individual agreements.

    Rules:
    - ALL "Yes" → Status must be "Agreed"
    - ANY "Partial" (no "No") → Status must be "Needs Clarification"
    - ANY "No" → Status must be "Unresolved"

    Args:
        decision: Decision object to validate

    Returns:
        Decision with corrected status if needed
    """
    agreements = list(decision.agreements.values())

    if not agreements:
        return decision

    has_no = "No" in agreements
    has_partial = "Partial" in agreements
    all_yes = all(a == "Yes" for a in agreements)

    # determine correct status based on agreements
    correct_status: Literal["Agreed", "Needs Clarification", "Unresolved"]
    if has_no:
        correct_status = "Unresolved"
    elif has_partial:
        correct_status = "Needs Clarification"
    elif all_yes:
        correct_status = "Agreed"
    else:
        # fallback for unexpected values
        correct_status = "Needs Clarification"

    # fix if inconsistent
    if decision.status != correct_status:
        logger.warning(
            f"Fixed status inconsistency: '{decision.title}' "
            f"changed from '{decision.status}' to '{correct_status}'"
        )
        decision.status = correct_status

    return decision


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def detect_participants(self, transcript: str) -> list[ParticipantConfig]:
        """
        Detect participants from a transcript.

        Args:
            transcript: The meeting transcript text

        Returns:
            List of detected participants
        """
        pass


class LiteLLMProvider(LLMProvider):
    """Provider using LiteLLM for multiple model support."""

    def __init__(self, model: str | None = None):
        """
        Initialize LiteLLM provider.

        Args:
            model: Model identifier (e.g., "claude-sonnet-4-20250514", "gpt-4").
                   Supports any model LiteLLM supports.
        """
        self.model = model or "claude-sonnet-4-20250514"

    def detect_participants(self, transcript: str) -> list[ParticipantConfig]:
        """Detect participants using LiteLLM."""
        # use first ~4000 chars of transcript for detection (sufficient context)
        sample = transcript[:4000] if len(transcript) > 4000 else transcript
        prompt_template = get_participant_detection_prompt()
        prompt = prompt_template.format(transcript=sample)

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.1,
            )

            content = response.choices[0].message.content
            if content is None:
                logger.warning("Empty response from participant detection")
                return []

            return self._parse_participant_response(content)

        except Exception as e:
            logger.error("Participant detection failed", exc_info=e)
            return []

    def _parse_participant_response(self, content: str) -> list[ParticipantConfig]:
        """Parse JSON response from participant detection."""
        content = content.strip()

        # remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            data = json.loads(content.strip())
            participants = []
            for p in data.get("participants", []):
                name = p.get("name", "").strip()
                if name:
                    participants.append(ParticipantConfig(
                        name=name,
                        role=p.get("role", ""),
                    ))
            logger.info(f"Detected participants: {[p.name for p in participants]}")
            if data.get("reasoning"):
                logger.debug(f"Detection reasoning: {data['reasoning']}")
            return participants
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse participant detection response: {e}")
            return []

class ClaudeCodeProvider(LLMProvider):
    """Provider using Claude Code CLI as the model."""

    def __init__(self, claude_code_path: str = "claude"):
        """
        Initialize Claude Code CLI provider.

        Args:
            claude_code_path: Path to claude CLI executable (default: "claude")
        """
        self.claude_code_path = claude_code_path

    def detect_participants(self, transcript: str) -> list[ParticipantConfig]:
        """Detect participants using Claude Code CLI with retry."""
        # use first ~4000 chars of transcript for detection
        sample = transcript[:4000] if len(transcript) > 4000 else transcript
        prompt_template = get_participant_detection_prompt()
        prompt = prompt_template.format(transcript=sample)
        logger.info(f"Starting participant detection: sample_length={len(sample)} chars")

        def _call_cli() -> str:
            """Inner function for retry wrapper - returns raw response."""
            start_time = time.time()
            result = subprocess.run(
                [self.claude_code_path, "--print", "--output-format", "json"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for detection
            )
            elapsed = time.time() - start_time

            metrics.llm_calls += 1
            metrics.participant_detection_calls += 1
            metrics.participant_detection_time += elapsed
            logger.info(f"Participant detection: {elapsed:.1f}s, {len(result.stdout)} chars")

            if result.returncode != 0:
                raise EmptyResponseError(f"CLI failed (code {result.returncode}): {result.stderr}")

            return result.stdout

        try:
            response = retry_with_backoff(
                _call_cli,
                operation_name="Participant detection",
            )
            return self._parse_participant_response(response)

        except Exception as e:
            logger.error("Participant detection via Claude Code failed", exc_info=e)
            return []

    def extract_decisions_json(self, transcript: str, config: TrackerConfig) -> ExtractionResult:
        """Extract decisions using Claude Code CLI with JSON output and retry."""
        prompt = build_json_extraction_prompt(config, transcript)
        prompt_len = len(prompt)
        logger.info(f"Starting JSON decision extraction: prompt_length={prompt_len} chars")

        # get participant names for parsing
        participant_names = config.participant_names or ["Ryan", "Ajit", "Milkana"]

        def _call_cli() -> str:
            """Inner function for retry wrapper - returns raw response."""
            start_time = time.time()
            result = subprocess.run(
                [
                    self.claude_code_path,
                    "--print",
                    "--output-format", "json",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            elapsed = time.time() - start_time

            metrics.llm_calls += 1
            metrics.decision_extraction_calls += 1
            metrics.decision_extraction_time += elapsed
            logger.info(f"Decision extraction: {elapsed:.1f}s, {len(result.stdout)} chars")

            if result.returncode != 0:
                raise EmptyResponseError(f"CLI failed (code {result.returncode}): {result.stderr}")

            return result.stdout

        try:
            response = retry_with_backoff(
                _call_cli,
                operation_name="Decision extraction",
            )
            return self._parse_json_extraction_response(response, participant_names)

        except FileNotFoundError as e:
            logger.error(f"Claude Code CLI not found at: {self.claude_code_path}")
            raise RuntimeError(
                "Claude Code CLI not found. Install it or specify path with --claude-code-path"
            ) from e
        except Exception as e:
            logger.error("Claude Code JSON extraction failed", exc_info=e)
            raise

    def _parse_json_extraction_response(
        self, content: str, participant_names: list[str]
    ) -> ExtractionResult:
        """Parse JSON response from decision extraction."""
        content = content.strip()
        logger.debug(f"Raw JSON response (first 200 chars): {content[:200]}")

        try:
            # Claude Code --output-format json wraps response in envelope
            envelope = json.loads(content)

            # extract the actual result string
            if "result" in envelope and isinstance(envelope["result"], str):
                inner_content = envelope["result"].strip()

                # remove markdown code blocks if present
                if inner_content.startswith("```json"):
                    inner_content = inner_content[7:]
                elif inner_content.startswith("```"):
                    inner_content = inner_content[3:]
                if inner_content.endswith("```"):
                    inner_content = inner_content[:-3]
                inner_content = inner_content.strip()

                # parse the actual JSON content
                data = json.loads(inner_content)
            elif "result" in envelope and isinstance(envelope["result"], dict):
                data = envelope["result"]
            elif "decisions" in envelope:
                # direct JSON response without wrapper
                data = envelope
            else:
                logger.error(f"Unexpected JSON envelope structure: {list(envelope.keys())}")
                return ExtractionResult(decisions=[], participants_detected=[])

            # parse decisions
            decisions = []
            for d in data.get("decisions", []):
                try:
                    decision = Decision(
                        category=d.get("category", ""),
                        significance=int(d.get("significance", 3)),
                        status=d.get("status", "Needs Clarification"),
                        title=d.get("title", ""),
                        description=d.get("description", ""),
                        decision=d.get("decision", ""),
                        agreements=d.get("agreements", {}),
                        notes=d.get("notes", ""),
                        meeting_date=d.get("meeting_date", ""),
                        meeting_reference=d.get("meeting_reference", ""),
                    )
                    # validate status/agreement consistency
                    decision = validate_decision(decision)
                    decisions.append(decision)
                except Exception as e:
                    logger.warning(f"Failed to parse decision: {e}")
                    continue

            logger.info(f"Parsed {len(decisions)} decisions from JSON response")
            return ExtractionResult(decisions=decisions, participants_detected=participant_names)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response (first 500 chars): {content[:500]}")
            # return empty result on parse failure
            return ExtractionResult(decisions=[], participants_detected=[])

    def _parse_participant_response(self, content: str) -> list[ParticipantConfig]:
        """Parse JSON response from participant detection."""
        content = content.strip()
        logger.debug(f"Raw participant response (first 300 chars): {content[:300]}")

        try:
            # Claude Code --output-format json wraps response in envelope
            envelope = json.loads(content)

            # extract the actual result string from envelope
            if "result" in envelope and isinstance(envelope["result"], str):
                inner_content = envelope["result"].strip()

                # remove markdown code blocks if present
                if inner_content.startswith("```json"):
                    inner_content = inner_content[7:]
                elif inner_content.startswith("```"):
                    inner_content = inner_content[3:]
                if inner_content.endswith("```"):
                    inner_content = inner_content[:-3]
                inner_content = inner_content.strip()

                data = json.loads(inner_content)
            elif "result" in envelope and isinstance(envelope["result"], dict):
                data = envelope["result"]
            elif "participants" in envelope:
                # direct JSON response without wrapper
                data = envelope
            else:
                logger.error(f"Unexpected participant response structure: {list(envelope.keys())}")
                return []

            participants = []
            for p in data.get("participants", []):
                name = p.get("name", "").strip()
                if name:
                    participants.append(ParticipantConfig(
                        name=name,
                        role=p.get("role", ""),
                    ))
            logger.info(f"Detected participants: {[p.name for p in participants]}")
            if data.get("reasoning"):
                logger.debug(f"Detection reasoning: {data['reasoning']}")
            return participants
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse participant detection response: {e}")
            logger.debug(f"Raw content (first 500 chars): {content[:500]}")
            return []

def get_provider(config: TrackerConfig) -> LLMProvider:
    """
    Get the appropriate LLM provider based on configuration.

    Args:
        config: Tracker configuration with model settings

    Returns:
        LLMProvider instance
    """
    provider_type = config.model_provider.lower()

    if provider_type == "claude-code":
        return ClaudeCodeProvider()
    else:
        # use LiteLLM for everything else (anthropic, openai, etc.)
        return LiteLLMProvider(model=config.model)


def detect_participants_from_transcript(
    transcript: str,
    config: TrackerConfig,
) -> list[ParticipantConfig]:
    """
    Detect participants from a transcript using LLM.

    This is the first step in processing - determine who the deciders are
    before extracting decisions.

    Args:
        transcript: The meeting transcript text
        config: Tracker configuration (for LLM provider settings)

    Returns:
        List of detected participants
    """
    provider = get_provider(config)
    return provider.detect_participants(transcript)


def ensure_participants(
    transcript: str,
    config: TrackerConfig,
) -> TrackerConfig:
    """
    Ensure config has participants, detecting from transcript if needed.

    This implements the workflow:
    1. If participants explicitly provided in config/framework, use those
    2. Otherwise, auto-detect from transcript

    Args:
        transcript: The meeting transcript text
        config: Tracker configuration

    Returns:
        Config with participants populated (may be modified copy)
    """
    # if participants are already set (not default), use them
    if config.participants and len(config.participants) > 0:
        # check if these look like explicit participants (not defaults)
        # defaults have specific names like Ryan, Ajit, Milkana
        default_names = {"Ryan", "Ajit", "Milkana"}
        current_names = {p.name for p in config.participants}

        # if not using defaults, participants were explicitly set
        if current_names != default_names:
            logger.info(f"Using explicitly configured participants: {list(current_names)}")
            return config

    # detect participants from transcript
    logger.info("No explicit participants configured, detecting from transcript...")
    detected = detect_participants_from_transcript(transcript, config)

    if detected:
        # create modified config with detected participants
        config.participants = detected
        logger.info(f"Detected {len(detected)} participants: {[p.name for p in detected]}")
    else:
        logger.warning("Failed to detect participants, using defaults")

    return config


def extract_decisions_from_transcript_json(
    transcript_path: Path,
    config: TrackerConfig,
    meeting_date: str | None = None,
    auto_detect_participants: bool = True,
) -> ExtractionResult:
    """
    Extract decisions from a transcript file using JSON format.

    Args:
        transcript_path: Path to transcript file
        config: Tracker configuration
        meeting_date: Optional meeting date (YYYY-MM-DD), extracted from filename if not provided
        auto_detect_participants: If True, detect participants from transcript if not explicitly set

    Returns:
        ExtractionResult with list of Decision objects
    """
    file_start_time = time.time()

    # read transcript
    read_start = time.time()
    with open(transcript_path, encoding="utf-8") as f:
        transcript = f.read()
    metrics.file_read_time += time.time() - read_start
    metrics.total_transcript_chars += len(transcript)
    logger.info(f"Read transcript: {transcript_path.name}, length={len(transcript)} chars")

    # extract date from filename if not provided
    if meeting_date is None:
        stem = transcript_path.stem
        for part in stem.split("-"):
            if len(part) == 4 and part.isdigit():
                idx = stem.find(part)
                if idx >= 0 and len(stem) >= idx + 10:
                    potential_date = stem[idx : idx + 10]
                    if len(potential_date.split("-")) == 3:
                        meeting_date = potential_date
                        break

    # step 1: ensure we have participants (detect if needed)
    if auto_detect_participants:
        config = ensure_participants(transcript, config)

    # step 2: get provider and extract decisions using JSON
    provider = get_provider(config)

    # use JSON extraction (required - CSV extraction has been removed)
    if not hasattr(provider, "extract_decisions_json"):
        raise NotImplementedError(
            f"Provider {type(provider).__name__} does not support JSON extraction. "
            "Use Claude Code (model_provider: claude-code) for decision extraction."
        )
    result = provider.extract_decisions_json(transcript, config)

    # fill in meeting date and reference for all decisions
    for decision in result.decisions:
        if not decision.meeting_date and meeting_date:
            decision.meeting_date = meeting_date
        if not decision.meeting_reference:
            decision.meeting_reference = transcript_path.name

    metrics.files_processed += 1
    file_elapsed = time.time() - file_start_time
    logger.info(f"Completed {transcript_path.name}: {file_elapsed:.1f}s, "
                f"{len(result.decisions)} decisions")

    return result


def _extract_single_file(
    transcript_file: Path,
    config: TrackerConfig,
    auto_detect_participants: bool,
) -> tuple[Path, ExtractionResult | None, str | None]:
    """
    Extract decisions from a single file. Used by parallel processing.

    Returns:
        Tuple of (file_path, result, error_message)
    """
    try:
        result = extract_decisions_from_transcript_json(
            transcript_file,
            config,
            auto_detect_participants=auto_detect_participants,
        )
        return (transcript_file, result, None)
    except Exception as e:
        logger.error(f"Failed to process {transcript_file.name}: {e}")
        return (transcript_file, None, str(e))


def extract_decisions_from_folder_parallel(
    folder_path: Path,
    config: TrackerConfig,
    files_or_pattern: list[Path] | str = "*.txt",
    max_workers: int = 4,
    auto_detect_participants: bool = True,
) -> list[list[str]]:
    """
    Extract decisions from all transcripts in a folder using parallel processing.

    Args:
        folder_path: Path to folder containing transcripts
        config: Tracker configuration
        files_or_pattern: Either a list of file paths or a glob pattern string
        max_workers: Maximum number of parallel workers
        auto_detect_participants: If True, detect participants from transcript if not explicitly set

    Returns:
        Merged list of CSV rows (single header, all data rows)
    """
    # reset metrics for this batch
    metrics.reset()
    folder_start_time = time.time()

    # accept either a list of files or a glob pattern
    if isinstance(files_or_pattern, list):
        transcript_files = sorted(files_or_pattern)
    else:
        transcript_files = sorted(folder_path.glob(files_or_pattern))

    if not transcript_files:
        raise ValueError(f"No transcript files found in {folder_path}")

    logger.info(f"Found {len(transcript_files)} transcript files (max_workers={max_workers})")

    # collect all decisions from all files
    all_decisions: list[Decision] = []
    all_participants: set[str] = set()
    failed_files: list[tuple[Path, str]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # submit all extraction tasks
        futures = {
            executor.submit(
                _extract_single_file,
                transcript_file,
                config,
                auto_detect_participants,
            ): transcript_file
            for transcript_file in transcript_files
        }

        # collect results as they complete
        for future in as_completed(futures):
            transcript_file = futures[future]
            try:
                file_path, result, error = future.result()
                if result is not None:
                    all_decisions.extend(result.decisions)
                    all_participants.update(result.participants_detected)
                    logger.info(f"Completed {file_path.name}: {len(result.decisions)} decisions")
                else:
                    failed_files.append((file_path, error or "Unknown error"))
            except Exception as e:
                logger.error(f"Unexpected error processing {transcript_file.name}: {e}")
                failed_files.append((transcript_file, str(e)))

    # report failed files
    if failed_files:
        logger.warning(f"Failed to process {len(failed_files)} files:")
        for file_path, error in failed_files:
            logger.warning(f"  - {file_path.name}: {error}")

    # convert decisions to CSV rows
    # use participant names from config if available, otherwise from detected
    participant_names = (
        config.participant_names if config.participant_names else sorted(all_participants)
    )
    rows = decisions_to_csv_rows(all_decisions, participant_names)

    # log final metrics
    folder_elapsed = time.time() - folder_start_time
    successful_files = len(transcript_files) - len(failed_files)
    total_files = len(transcript_files)
    logger.info(f"Folder complete: {folder_elapsed:.1f}s, files={successful_files}/{total_files}, "
                f"decisions={len(all_decisions)}")
    metrics.log_summary()

    return rows
