"""Manifest tracking for idempotent regeneration."""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MANIFEST_VERSION = "1.0"
MANIFEST_FILENAME = ".groundtruth.json"


@dataclass
class FileEntry:
    """Tracked file entry in manifest."""

    hash: str
    size: int
    mtime: str
    decisions_count: int
    decisions: list[dict] = field(default_factory=list)


@dataclass
class Manifest:
    """Manifest for tracking processed files."""

    version: str
    generated_at: str
    output_file: str
    config_hash: str
    framework_hash: str
    files: dict[str, FileEntry] = field(default_factory=dict)


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of string content."""
    if not content:
        return "sha256:empty"
    sha256 = hashlib.sha256(content.encode("utf-8"))
    return f"sha256:{sha256.hexdigest()}"


def get_file_mtime(path: Path) -> str:
    """Get file modification time as ISO format string."""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat()


def load_manifest(folder: Path) -> Manifest | None:
    """
    Load manifest from folder.

    Args:
        folder: Folder containing .groundtruth.json

    Returns:
        Manifest if found and valid, None otherwise
    """
    manifest_path = folder / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)

        # validate version
        if data.get("version") != MANIFEST_VERSION:
            logger.warning(f"manifest version mismatch: {data.get('version')}")
            return None

        # parse file entries
        files: dict[str, FileEntry] = {}
        for filename, entry_data in data.get("files", {}).items():
            files[filename] = FileEntry(
                hash=entry_data["hash"],
                size=entry_data["size"],
                mtime=entry_data["mtime"],
                decisions_count=entry_data["decisions_count"],
                decisions=entry_data.get("decisions", []),
            )

        return Manifest(
            version=data["version"],
            generated_at=data["generated_at"],
            output_file=data["output_file"],
            config_hash=data.get("config_hash", ""),
            framework_hash=data.get("framework_hash", ""),
            files=files,
        )

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"failed to load manifest: {e}")
        return None


def save_manifest(folder: Path, manifest: Manifest) -> None:
    """
    Save manifest to folder.

    Args:
        folder: Folder to save .groundtruth.json
        manifest: Manifest to save
    """
    manifest_path = folder / MANIFEST_FILENAME

    # convert to dict for JSON serialization
    data: dict[str, Any] = {
        "version": manifest.version,
        "generated_at": manifest.generated_at,
        "output_file": manifest.output_file,
        "config_hash": manifest.config_hash,
        "framework_hash": manifest.framework_hash,
        "files": {
            filename: asdict(entry)
            for filename, entry in manifest.files.items()
        },
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_files_to_process(
    all_files: list[Path],
    manifest: Manifest | None,
    config_hash: str,
    framework_hash: str,
) -> tuple[list[Path], dict[str, list[dict]]]:
    """
    Determine which files need processing based on manifest.

    Args:
        all_files: All transcript files found
        manifest: Existing manifest (or None)
        config_hash: Hash of current config
        framework_hash: Hash of current framework

    Returns:
        Tuple of (files_to_process, cached_decisions)
        - files_to_process: Files that need LLM extraction
        - cached_decisions: Dict mapping filename to cached decision dicts
    """
    if manifest is None:
        # no manifest - process all files
        return all_files, {}

    # check if config or framework changed - reprocess all
    if manifest.config_hash != config_hash:
        logger.info("config changed, reprocessing all files")
        return all_files, {}

    if manifest.framework_hash != framework_hash:
        logger.info("framework changed, reprocessing all files")
        return all_files, {}

    files_to_process: list[Path] = []
    cached_decisions: dict[str, list[dict]] = {}

    # check each file
    for file_path in all_files:
        filename = file_path.name

        if filename not in manifest.files:
            # new file
            logger.debug(f"{filename}: new file")
            files_to_process.append(file_path)
            continue

        entry = manifest.files[filename]

        # compute current hash
        current_hash = compute_file_hash(file_path)
        if current_hash != entry.hash:
            # file changed
            logger.debug(f"{filename}: hash changed")
            files_to_process.append(file_path)
            continue

        # file unchanged - use cached decisions
        logger.debug(f"{filename}: unchanged, using cache")
        cached_decisions[filename] = entry.decisions

    return files_to_process, cached_decisions


def create_manifest(
    output_file: str,
    config_hash: str,
    framework_hash: str,
    file_entries: dict[str, FileEntry],
) -> Manifest:
    """
    Create a new manifest.

    Args:
        output_file: Name of generated output file
        config_hash: Hash of config used
        framework_hash: Hash of framework used
        file_entries: Dict of filename to FileEntry

    Returns:
        New Manifest
    """
    return Manifest(
        version=MANIFEST_VERSION,
        generated_at=datetime.now(tz=UTC).isoformat(),
        output_file=output_file,
        config_hash=config_hash,
        framework_hash=framework_hash,
        files=file_entries,
    )


def create_file_entry(
    path: Path,
    decisions: list[dict],
) -> FileEntry:
    """
    Create a FileEntry for a processed file.

    Args:
        path: Path to the file
        decisions: List of decision dicts extracted from file

    Returns:
        FileEntry for the file
    """
    return FileEntry(
        hash=compute_file_hash(path),
        size=path.stat().st_size,
        mtime=get_file_mtime(path),
        decisions_count=len(decisions),
        decisions=decisions,
    )
