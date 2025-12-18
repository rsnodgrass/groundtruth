"""Prompt loading and template management for Groundtruth."""

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=10)
def load_prompt(prompt_name: str) -> str:
    """
    Load a prompt template from the prompts directory.

    Args:
        prompt_name: Name of the prompt file (without .md extension)

    Returns:
        Prompt template string

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = _PROMPTS_DIR / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")


def get_participant_detection_prompt() -> str:
    """Get the participant detection prompt template."""
    return load_prompt("participant_detection")


def get_decision_extraction_prompt() -> str:
    """Get the decision extraction prompt template."""
    return load_prompt("decision_extraction")
