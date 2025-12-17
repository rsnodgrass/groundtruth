"""LLM abstraction layer supporting multiple providers via LiteLLM and Claude Code CLI."""

import csv
import io
import json
import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from litellm import completion

from groundtruth.config import ParticipantConfig, TrackerConfig, build_extraction_prompt

logger = logging.getLogger(__name__)


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

        try:
            # use --print flag for non-interactive output
            result = subprocess.run(
                [self.claude_code_path, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

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

        try:
            result = subprocess.run(
                [self.claude_code_path, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout for detection
            )

            if result.returncode != 0:
                logger.error(f"Claude Code CLI failed for participant detection: {result.stderr}")
                return []

            return self._parse_participant_response(result.stdout)

        except Exception as e:
            logger.error("Participant detection via Claude Code failed", exc_info=e)
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
        """Clean CLI response to extract valid CSV."""
        content = content.strip()

        # remove markdown code blocks if present
        if content.startswith("```csv"):
            content = content[6:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        # find the CSV header line and extract from there
        lines = content.split("\n")
        csv_start = -1
        for i, line in enumerate(lines):
            if line.startswith("Category,Type,Title"):
                csv_start = i
                break

        if csv_start >= 0:
            content = "\n".join(lines[csv_start:])

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
    # read transcript
    with open(transcript_path, encoding="utf-8") as f:
        transcript = f.read()

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
    rows = parse_csv_response(csv_content, config)

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
    transcript_files = sorted(folder_path.glob(pattern))

    if not transcript_files:
        raise ValueError(f"No transcript files found matching {pattern} in {folder_path}")

    all_rows: list[list[str]] = []
    header: list[str] | None = None

    for transcript_file in transcript_files:
        logger.info(f"Processing: {transcript_file.name}")
        rows = extract_decisions_from_transcript(transcript_file, config)

        if header is None:
            header = rows[0]
            all_rows.append(header)

        # add data rows (skip header)
        all_rows.extend(rows[1:])

    return all_rows
