"""Tests for manifest module."""

import json
from pathlib import Path

from groundtruth.manifest import (
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    FileEntry,
    Manifest,
    compute_content_hash,
    compute_file_hash,
    create_file_entry,
    create_manifest,
    get_file_mtime,
    get_files_to_process,
    load_manifest,
    save_manifest,
)


class TestComputeFileHash:
    """Tests for compute_file_hash."""

    def test_hash_consistent(self, tmp_path: Path) -> None:
        """Same content produces same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = "hello world"
        file1.write_text(content)
        file2.write_text(content)

        assert compute_file_hash(file1) == compute_file_hash(file2)

    def test_hash_different_content(self, tmp_path: Path) -> None:
        """Different content produces different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("hello")
        file2.write_text("world")

        assert compute_file_hash(file1) != compute_file_hash(file2)

    def test_hash_format(self, tmp_path: Path) -> None:
        """Hash has expected format."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        hash_val = compute_file_hash(test_file)
        assert hash_val.startswith("sha256:")
        assert len(hash_val) == 7 + 64  # "sha256:" + 64 hex chars


class TestComputeContentHash:
    """Tests for compute_content_hash."""

    def test_empty_content(self) -> None:
        """Empty content returns special value."""
        assert compute_content_hash("") == "sha256:empty"

    def test_none_like_empty(self) -> None:
        """None-like values return empty hash."""
        assert compute_content_hash("") == "sha256:empty"

    def test_consistent_hash(self) -> None:
        """Same content produces same hash."""
        content = "test content"
        assert compute_content_hash(content) == compute_content_hash(content)

    def test_different_content(self) -> None:
        """Different content produces different hash."""
        assert compute_content_hash("hello") != compute_content_hash("world")


class TestGetFileMtime:
    """Tests for get_file_mtime."""

    def test_returns_iso_format(self, tmp_path: Path) -> None:
        """Returns ISO format timestamp."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        mtime = get_file_mtime(test_file)
        # should be ISO format with timezone
        assert "T" in mtime
        assert "+" in mtime or "Z" in mtime or mtime.endswith("+00:00")


class TestLoadManifest:
    """Tests for load_manifest."""

    def test_no_manifest(self, tmp_path: Path) -> None:
        """Returns None when no manifest exists."""
        assert load_manifest(tmp_path) is None

    def test_load_valid_manifest(self, tmp_path: Path) -> None:
        """Loads valid manifest correctly."""
        manifest_data = {
            "version": MANIFEST_VERSION,
            "generated_at": "2025-12-17T10:00:00+00:00",
            "output_file": "test.xlsx",
            "config_hash": "sha256:abc",
            "framework_hash": "sha256:def",
            "files": {
                "meeting.txt": {
                    "hash": "sha256:123",
                    "size": 100,
                    "mtime": "2025-12-16T10:00:00+00:00",
                    "decisions_count": 5,
                    "decisions": [{"category": "Tech"}],
                }
            },
        }
        manifest_path = tmp_path / MANIFEST_FILENAME
        manifest_path.write_text(json.dumps(manifest_data))

        manifest = load_manifest(tmp_path)
        assert manifest is not None
        assert manifest.version == MANIFEST_VERSION
        assert manifest.output_file == "test.xlsx"
        assert "meeting.txt" in manifest.files
        assert manifest.files["meeting.txt"].decisions_count == 5

    def test_load_wrong_version(self, tmp_path: Path) -> None:
        """Returns None for wrong version."""
        manifest_data = {
            "version": "0.1",
            "generated_at": "2025-12-17T10:00:00+00:00",
            "output_file": "test.xlsx",
            "files": {},
        }
        manifest_path = tmp_path / MANIFEST_FILENAME
        manifest_path.write_text(json.dumps(manifest_data))

        assert load_manifest(tmp_path) is None

    def test_load_corrupted_json(self, tmp_path: Path) -> None:
        """Returns None for corrupted JSON."""
        manifest_path = tmp_path / MANIFEST_FILENAME
        manifest_path.write_text("not valid json {{{")

        assert load_manifest(tmp_path) is None

    def test_load_missing_fields(self, tmp_path: Path) -> None:
        """Returns None for missing required fields."""
        manifest_data = {"version": MANIFEST_VERSION}
        manifest_path = tmp_path / MANIFEST_FILENAME
        manifest_path.write_text(json.dumps(manifest_data))

        assert load_manifest(tmp_path) is None


class TestSaveManifest:
    """Tests for save_manifest."""

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Saved manifest can be loaded back."""
        file_entry = FileEntry(
            hash="sha256:abc",
            size=100,
            mtime="2025-12-16T10:00:00+00:00",
            decisions_count=3,
            decisions=[{"category": "Tech", "title": "Test"}],
        )
        manifest = Manifest(
            version=MANIFEST_VERSION,
            generated_at="2025-12-17T10:00:00+00:00",
            output_file="output.xlsx",
            config_hash="sha256:cfg",
            framework_hash="sha256:fw",
            files={"test.txt": file_entry},
        )

        save_manifest(tmp_path, manifest)
        loaded = load_manifest(tmp_path)

        assert loaded is not None
        assert loaded.output_file == "output.xlsx"
        assert loaded.config_hash == "sha256:cfg"
        assert "test.txt" in loaded.files
        assert loaded.files["test.txt"].decisions_count == 3


class TestGetFilesToProcess:
    """Tests for get_files_to_process."""

    def test_no_manifest_processes_all(self, tmp_path: Path) -> None:
        """Without manifest, all files need processing."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        to_process, cached = get_files_to_process(
            [file1, file2], None, "sha256:cfg", "sha256:fw"
        )

        assert len(to_process) == 2
        assert len(cached) == 0

    def test_unchanged_files_cached(self, tmp_path: Path) -> None:
        """Unchanged files use cached decisions."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        file1_hash = compute_file_hash(file1)

        manifest = Manifest(
            version=MANIFEST_VERSION,
            generated_at="2025-12-17T10:00:00+00:00",
            output_file="output.xlsx",
            config_hash="sha256:cfg",
            framework_hash="sha256:fw",
            files={
                "file1.txt": FileEntry(
                    hash=file1_hash,
                    size=100,
                    mtime="2025-12-16T10:00:00+00:00",
                    decisions_count=2,
                    decisions=[{"category": "Tech"}],
                )
            },
        )

        to_process, cached = get_files_to_process(
            [file1], manifest, "sha256:cfg", "sha256:fw"
        )

        assert len(to_process) == 0
        assert "file1.txt" in cached
        assert len(cached["file1.txt"]) == 1

    def test_changed_file_reprocessed(self, tmp_path: Path) -> None:
        """Changed files need reprocessing."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("original content")
        old_hash = compute_file_hash(file1)

        # modify file
        file1.write_text("modified content")

        manifest = Manifest(
            version=MANIFEST_VERSION,
            generated_at="2025-12-17T10:00:00+00:00",
            output_file="output.xlsx",
            config_hash="sha256:cfg",
            framework_hash="sha256:fw",
            files={
                "file1.txt": FileEntry(
                    hash=old_hash,  # old hash
                    size=100,
                    mtime="2025-12-16T10:00:00+00:00",
                    decisions_count=2,
                    decisions=[{"category": "Tech"}],
                )
            },
        )

        to_process, cached = get_files_to_process(
            [file1], manifest, "sha256:cfg", "sha256:fw"
        )

        assert len(to_process) == 1
        assert file1 in to_process
        assert len(cached) == 0

    def test_new_file_processed(self, tmp_path: Path) -> None:
        """New files need processing."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")
        file1_hash = compute_file_hash(file1)

        manifest = Manifest(
            version=MANIFEST_VERSION,
            generated_at="2025-12-17T10:00:00+00:00",
            output_file="output.xlsx",
            config_hash="sha256:cfg",
            framework_hash="sha256:fw",
            files={
                "file1.txt": FileEntry(
                    hash=file1_hash,
                    size=100,
                    mtime="2025-12-16T10:00:00+00:00",
                    decisions_count=2,
                    decisions=[{"category": "Tech"}],
                )
            },
        )

        to_process, cached = get_files_to_process(
            [file1, file2], manifest, "sha256:cfg", "sha256:fw"
        )

        assert len(to_process) == 1
        assert file2 in to_process
        assert "file1.txt" in cached

    def test_config_change_reprocesses_all(self, tmp_path: Path) -> None:
        """Config change forces reprocessing all files."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        file1_hash = compute_file_hash(file1)

        manifest = Manifest(
            version=MANIFEST_VERSION,
            generated_at="2025-12-17T10:00:00+00:00",
            output_file="output.xlsx",
            config_hash="sha256:old_cfg",  # different
            framework_hash="sha256:fw",
            files={
                "file1.txt": FileEntry(
                    hash=file1_hash,
                    size=100,
                    mtime="2025-12-16T10:00:00+00:00",
                    decisions_count=2,
                    decisions=[{"category": "Tech"}],
                )
            },
        )

        to_process, cached = get_files_to_process(
            [file1], manifest, "sha256:new_cfg", "sha256:fw"
        )

        assert len(to_process) == 1
        assert len(cached) == 0

    def test_framework_change_reprocesses_all(self, tmp_path: Path) -> None:
        """Framework change forces reprocessing all files."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        file1_hash = compute_file_hash(file1)

        manifest = Manifest(
            version=MANIFEST_VERSION,
            generated_at="2025-12-17T10:00:00+00:00",
            output_file="output.xlsx",
            config_hash="sha256:cfg",
            framework_hash="sha256:old_fw",  # different
            files={
                "file1.txt": FileEntry(
                    hash=file1_hash,
                    size=100,
                    mtime="2025-12-16T10:00:00+00:00",
                    decisions_count=2,
                    decisions=[{"category": "Tech"}],
                )
            },
        )

        to_process, cached = get_files_to_process(
            [file1], manifest, "sha256:cfg", "sha256:new_fw"
        )

        assert len(to_process) == 1
        assert len(cached) == 0


class TestCreateManifest:
    """Tests for create_manifest."""

    def test_creates_manifest(self) -> None:
        """Creates manifest with correct structure."""
        file_entry = FileEntry(
            hash="sha256:abc",
            size=100,
            mtime="2025-12-16T10:00:00+00:00",
            decisions_count=3,
            decisions=[],
        )

        manifest = create_manifest(
            output_file="output.xlsx",
            config_hash="sha256:cfg",
            framework_hash="sha256:fw",
            file_entries={"test.txt": file_entry},
        )

        assert manifest.version == MANIFEST_VERSION
        assert manifest.output_file == "output.xlsx"
        assert manifest.config_hash == "sha256:cfg"
        assert manifest.framework_hash == "sha256:fw"
        assert "test.txt" in manifest.files
        assert manifest.generated_at  # should be set


class TestCreateFileEntry:
    """Tests for create_file_entry."""

    def test_creates_entry(self, tmp_path: Path) -> None:
        """Creates file entry with correct data."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        decisions = [{"category": "Tech", "title": "Test"}]

        entry = create_file_entry(test_file, decisions)

        assert entry.hash.startswith("sha256:")
        assert entry.size == test_file.stat().st_size
        assert entry.decisions_count == 1
        assert entry.decisions == decisions
