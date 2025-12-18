"""LLM abstraction layer supporting multiple providers via LiteLLM and Claude Code CLI."""

import csv
import io
import json
import logging
import subprocess
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from litellm import completion

from groundtruth.config import (
    Decision,
    ExtractionResult,
    ParticipantConfig,
    TrackerConfig,
    build_extraction_prompt,
    build_json_extraction_prompt,
    decisions_to_csv_rows,
    get_json_schema_for_extraction,
)

logger = logging.getLogger(__name__)


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

    def log_summary(self):
        total_llm_time = self.participant_detection_time + self.decision_extraction_time
        logger.info(f"=== PERFORMANCE METRICS ===")
        logger.info(f"files_processed={self.files_processed}, total_llm_calls={self.llm_calls}")
        logger.info(f"participant_detection: calls={self.participant_detection_calls}, time={self.participant_detection_time:.1f}s")
        logger.info(f"decision_extraction: calls={self.decision_extraction_calls}, time={self.decision_extraction_time:.1f}s")
        logger.info(f"total_llm_time={total_llm_time:.1f}s, file_read_time={self.file_read_time:.1f}s, csv_parse_time={self.csv_parse_time:.1f}s")
        logger.info(f"total_transcript_chars={self.total_transcript_chars}")
        if self.files_processed > 0:
            avg_time = total_llm_time / self.files_processed
            logger.info(f"avg_llm_time_per_file={avg_time:.1f}s")


metrics = Metrics()


PARTICIPANT_DETECTION_PROMPT = """Analyze this transcript and identify decision-makers.

Return ONLY a JSON object with this structure:
{{
  "participants": [
    {{"name": "FirstName", "role": "inferred role if mentioned"}},
    {{"name": "FirstName2", "role": "inferred role if mentioned"}}
  ],
  "reasoning": "Brief explanation of how you identified these participants"
}}

Rules:
- Include only people who are ACTIVELY participating in decision-making discussions
- Use first names only (e.g., "Ryan" not "Ryan Smith")
- If a role is mentioned or can be inferred (CEO, CTO, PM, etc.), include it
- Do not include people who are only mentioned but not present
- If speaker names are labeled in the transcript (e.g., "Ryan:", "[Ryan]"), use those
- If no clear names, return {{"participants": [], "reasoning": "No named participants detected"}}

Transcript:
{transcript}

JSON response:"""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def extract_decisions(self, transcript: str, config: TrackerConfig) -> str:
        """
        Extract decisions from a transcript.

        Args:
            transcript: The meeting transcript text
            config: Tracker configuration with prompts and settings

        Returns:
            CSV string with extracted decisions
        """
        pass

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

    def extract_decisions(self, transcript: str, config: TrackerConfig) -> str:
        """Extract decisions using LiteLLM."""
        prompt = build_extraction_prompt(config, transcript)

        try:
            response = completion(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                max_tokens=8192,
                temperature=0.1,  # low temperature for consistent structured output
            )

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("LLM returned empty response")

            return self._clean_csv_response(content)

        except Exception as e:
            logger.error("LiteLLM extraction failed", exc_info=e)
            raise


    def detect_participants(self, transcript: str) -> list[ParticipantConfig]:
        """Detect participants using LiteLLM."""
        # use first ~4000 chars of transcript for detection (sufficient context)
        sample = transcript[:4000] if len(transcript) > 4000 else transcript
        prompt = PARTICIPANT_DETECTION_PROMPT.format(transcript=sample)

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

    def _clean_csv_response(self, content: str) -> str:
        """Clean LLM response to extract valid CSV."""
        # remove markdown code blocks if present
        content = content.strip()

        if content.startswith("```csv"):
            content = content[6:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        return content.strip()


class ClaudeCodeProvider(LLMProvider):
    """Provider using Claude Code CLI as the model."""

    def __init__(self, claude_code_path: str = "claude"):
        """
        Initialize Claude Code CLI provider.

        Args:
            claude_code_path: Path to claude CLI executable (default: "claude")
        """
        self.claude_code_path = claude_code_path

    def extract_decisions(self, transcript: str, config: TrackerConfig) -> str:
        """Extract decisions using Claude Code CLI."""
        prompt = build_extraction_prompt(config, transcript)
        prompt_len = len(prompt)
        logger.info(f"Starting decision extraction: prompt_length={prompt_len} chars")

        try:
            start_time = time.time()
            # use stdin for large prompts to avoid CLI argument length limits
            result = subprocess.run(
                [self.claude_code_path, "--print"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            elapsed = time.time() - start_time

            metrics.llm_calls += 1
            metrics.decision_extraction_calls += 1
            metrics.decision_extraction_time += elapsed
            logger.info(f"Decision extraction completed: elapsed={elapsed:.1f}s, response_length={len(result.stdout)} chars")

            if result.returncode != 0:
                logger.error(f"Claude Code CLI failed: {result.stderr}")
                raise RuntimeError(f"Claude Code CLI exited with code {result.returncode}")

            return self._clean_csv_response(result.stdout)

        except subprocess.TimeoutExpired as e:
            logger.error("Claude Code CLI timed out")
            raise RuntimeError("Claude Code CLI timed out after 5 minutes") from e
        except FileNotFoundError as e:
            logger.error(f"Claude Code CLI not found at: {self.claude_code_path}")
            raise RuntimeError(
                "Claude Code CLI not found. Install it or specify path with --claude-code-path"
            ) from e
        except Exception as e:
            logger.error("Claude Code extraction failed", exc_info=e)
            raise

    def detect_participants(self, transcript: str) -> list[ParticipantConfig]:
        """Detect participants using Claude Code CLI."""
        # use first ~4000 chars of transcript for detection
        sample = transcript[:4000] if len(transcript) > 4000 else transcript
        prompt = PARTICIPANT_DETECTION_PROMPT.format(transcript=sample)
        logger.info(f"Starting participant detection: sample_length={len(sample)} chars")

        try:
            start_time = time.time()
            # use stdin to avoid CLI argument length limits
            result = subprocess.run(
                [self.claude_code_path, "--print"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for detection
            )
            elapsed = time.time() - start_time

            metrics.llm_calls += 1
            metrics.participant_detection_calls += 1
            metrics.participant_detection_time += elapsed
            logger.info(f"Participant detection completed: elapsed={elapsed:.1f}s")

            if result.returncode != 0:
                logger.error(f"Claude Code CLI failed for participant detection: {result.stderr}")
                return []

            return self._parse_participant_response(result.stdout)

        except Exception as e:
            logger.error("Participant detection via Claude Code failed", exc_info=e)
            return []

    def extract_decisions_json(self, transcript: str, config: TrackerConfig) -> ExtractionResult:
        """Extract decisions using Claude Code CLI with JSON output."""
        prompt = build_json_extraction_prompt(config, transcript)
        prompt_len = len(prompt)
        logger.info(f"Starting JSON decision extraction: prompt_length={prompt_len} chars")

        # get participant names for parsing
        participant_names = config.participant_names or ["Ryan", "Ajit", "Milkana"]

        try:
            start_time = time.time()
            # use stdin for large prompts, request JSON output format
            # note: --json-schema causes empty results, so just use --output-format json
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
            logger.info(f"JSON decision extraction completed: elapsed={elapsed:.1f}s, response_length={len(result.stdout)} chars")

            if result.returncode != 0:
                logger.error(f"Claude Code CLI failed: {result.stderr}")
                raise RuntimeError(f"Claude Code CLI exited with code {result.returncode}")

            return self._parse_json_extraction_response(result.stdout, participant_names)

        except subprocess.TimeoutExpired as e:
            logger.error("Claude Code CLI timed out")
            raise RuntimeError("Claude Code CLI timed out after 5 minutes") from e
        except FileNotFoundError as e:
            logger.error(f"Claude Code CLI not found at: {self.claude_code_path}")
            raise RuntimeError(
                "Claude Code CLI not found. Install it or specify path with --claude-code-path"
            ) from e
        except Exception as e:
            logger.error("Claude Code JSON extraction failed", exc_info=e)
            raise

    def _parse_json_extraction_response(self, content: str, participant_names: list[str]) -> ExtractionResult:
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

    def _clean_csv_response(self, content: str) -> str:
        """Clean CLI response to extract valid CSV."""
        content = content.strip()

        # log raw response for debugging
        logger.debug(f"Raw Claude Code response (first 500 chars): {content[:500]}")

        # remove markdown code blocks - handle various formats
        lines = content.split("\n")
        cleaned_lines = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if not in_code_block or (in_code_block and "," in line):
                cleaned_lines.append(line)

        content = "\n".join(cleaned_lines)

        # find the CSV header line - try multiple patterns
        lines = content.split("\n")
        csv_start = -1
        header_patterns = ["Category,", "category,", "\"Category\""]

        for i, line in enumerate(lines):
            for pattern in header_patterns:
                if pattern in line and "," in line:
                    # verify it looks like a CSV header with multiple columns
                    if line.count(",") >= 5:
                        csv_start = i
                        break
            if csv_start >= 0:
                break

        if csv_start >= 0:
            content = "\n".join(lines[csv_start:])
            logger.debug(f"Found CSV starting at line {csv_start}")
        else:
            logger.warning(f"Could not find CSV header in response. First line: {lines[0] if lines else 'empty'}")

        return content.strip()


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


def parse_csv_response(csv_content: str, config: TrackerConfig) -> list[list[str]]:
    """
    Parse CSV response from LLM into rows.

    Args:
        csv_content: CSV string from LLM
        config: Tracker configuration

    Returns:
        List of rows (including header)
    """
    reader = csv.reader(io.StringIO(csv_content))
    rows = list(reader)

    if not rows:
        raise ValueError("Empty CSV response from LLM")

    # validate header has minimum expected columns
    header = rows[0]
    min_cols = 6 + len(config.participant_names)  # base cols + agreed cols
    if len(header) < min_cols:
        raise ValueError(
            f"Invalid CSV header: expected at least {min_cols} columns, got {len(header)}"
        )

    return rows


def extract_decisions_from_transcript(
    transcript_path: Path,
    config: TrackerConfig,
    meeting_date: str | None = None,
    auto_detect_participants: bool = True,
) -> list[list[str]]:
    """
    Extract decisions from a transcript file.

    Args:
        transcript_path: Path to transcript file
        config: Tracker configuration
        meeting_date: Optional meeting date (YYYY-MM-DD), extracted from filename if not provided
        auto_detect_participants: If True, detect participants from transcript if not explicitly set

    Returns:
        List of CSV rows (including header)
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
        # try to extract YYYY-MM-DD from filename
        stem = transcript_path.stem
        for part in stem.split("-"):
            if len(part) == 4 and part.isdigit():
                # found year, try to get full date
                idx = stem.find(part)
                if idx >= 0 and len(stem) >= idx + 10:
                    potential_date = stem[idx : idx + 10]
                    if len(potential_date.split("-")) == 3:
                        meeting_date = potential_date
                        break

    # step 1: ensure we have participants (detect if needed)
    if auto_detect_participants:
        config = ensure_participants(transcript, config)

    # step 2: get provider and extract decisions
    provider = get_provider(config)
    csv_content = provider.extract_decisions(transcript, config)

    # parse response
    parse_start = time.time()
    rows = parse_csv_response(csv_content, config)
    metrics.csv_parse_time += time.time() - parse_start

    # add meeting reference to rows if not present
    for row in rows[1:]:  # skip header
        # meeting reference is the last column
        if len(row) > 0:
            # ensure meeting date is set
            date_col_idx = 7 + len(config.participant_names)
            if len(row) > date_col_idx and not row[date_col_idx] and meeting_date:
                row[date_col_idx] = meeting_date

            # ensure meeting reference is set
            ref_col_idx = date_col_idx + 2
            if len(row) > ref_col_idx and not row[ref_col_idx]:
                row[ref_col_idx] = transcript_path.name

    metrics.files_processed += 1
    file_elapsed = time.time() - file_start_time
    logger.info(f"Completed {transcript_path.name}: total_time={file_elapsed:.1f}s, decisions={len(rows)-1}")

    return rows


def extract_decisions_from_folder(
    folder_path: Path,
    config: TrackerConfig,
    pattern: str = "*.txt",
) -> list[list[str]]:
    """
    Extract decisions from all transcripts in a folder.

    Args:
        folder_path: Path to folder containing transcripts
        config: Tracker configuration
        pattern: Glob pattern for transcript files

    Returns:
        Merged list of CSV rows (single header, all data rows)
    """
    # reset metrics for this batch
    metrics.reset()
    folder_start_time = time.time()

    transcript_files = sorted(folder_path.glob(pattern))

    if not transcript_files:
        raise ValueError(f"No transcript files found matching {pattern} in {folder_path}")

    logger.info(f"Found {len(transcript_files)} transcript files to process")
    all_rows: list[list[str]] = []
    header: list[str] | None = None

    for i, transcript_file in enumerate(transcript_files):
        logger.info(f"Processing ({i+1}/{len(transcript_files)}): {transcript_file.name}")
        rows = extract_decisions_from_transcript(transcript_file, config)

        if header is None:
            header = rows[0]
            all_rows.append(header)

        # add data rows (skip header)
        all_rows.extend(rows[1:])

    # log final metrics
    folder_elapsed = time.time() - folder_start_time
    logger.info(f"Folder processing complete: total_time={folder_elapsed:.1f}s, total_decisions={len(all_rows)-1}")
    metrics.log_summary()

    return all_rows


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

    # use JSON extraction if provider supports it
    if hasattr(provider, "extract_decisions_json"):
        result = provider.extract_decisions_json(transcript, config)
    else:
        # fallback to CSV-based extraction and convert
        csv_content = provider.extract_decisions(transcript, config)
        rows = parse_csv_response(csv_content, config)
        # convert CSV rows to Decision objects (simplified fallback)
        decisions = []
        participant_names = config.participant_names
        for row in rows[1:]:  # skip header
            if len(row) >= 6 + len(participant_names):
                agreements = {}
                for i, name in enumerate(participant_names):
                    agreements[name] = row[6 + i] if 6 + i < len(row) else "No"
                decisions.append(Decision(
                    category=row[0],
                    significance=int(row[1]) if row[1].isdigit() else 3,
                    status=row[2],
                    title=row[3],
                    description=row[4],
                    decision=row[5],
                    agreements=agreements,
                    notes=row[6 + len(participant_names)] if len(row) > 6 + len(participant_names) else "",
                    meeting_date=meeting_date or "",
                    meeting_reference=transcript_path.name,
                ))
        result = ExtractionResult(decisions=decisions, participants_detected=participant_names)

    # fill in meeting date and reference for all decisions
    for decision in result.decisions:
        if not decision.meeting_date and meeting_date:
            decision.meeting_date = meeting_date
        if not decision.meeting_reference:
            decision.meeting_reference = transcript_path.name

    metrics.files_processed += 1
    file_elapsed = time.time() - file_start_time
    logger.info(f"Completed {transcript_path.name}: total_time={file_elapsed:.1f}s, decisions={len(result.decisions)}")

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
    pattern: str = "*.txt",
    max_workers: int = 4,
    auto_detect_participants: bool = True,
) -> list[list[str]]:
    """
    Extract decisions from all transcripts in a folder using parallel processing.

    Args:
        folder_path: Path to folder containing transcripts
        config: Tracker configuration
        pattern: Glob pattern for transcript files
        max_workers: Maximum number of parallel workers
        auto_detect_participants: If True, detect participants from transcript if not explicitly set

    Returns:
        Merged list of CSV rows (single header, all data rows)
    """
    # reset metrics for this batch
    metrics.reset()
    folder_start_time = time.time()

    transcript_files = sorted(folder_path.glob(pattern))

    if not transcript_files:
        raise ValueError(f"No transcript files found matching {pattern} in {folder_path}")

    logger.info(f"Found {len(transcript_files)} transcript files to process in parallel (max_workers={max_workers})")

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
    participant_names = config.participant_names if config.participant_names else sorted(all_participants)
    rows = decisions_to_csv_rows(all_decisions, participant_names)

    # log final metrics
    folder_elapsed = time.time() - folder_start_time
    successful_files = len(transcript_files) - len(failed_files)
    logger.info(f"Parallel folder processing complete: total_time={folder_elapsed:.1f}s, files={successful_files}/{len(transcript_files)}, total_decisions={len(all_decisions)}")
    metrics.log_summary()

    return rows
