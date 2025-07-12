import tempfile
from pathlib import Path

from utils import discover_source_files


def test_discover_source_files_unit(monkeypatch):
    def mock_classify_file(_file_path, _content):
        return {
            "should_test": True,
            "test_type": "unit",
            "framework": "pytest",
            "priority": "high",
        }

    monkeypatch.setattr("utils.classify_file", mock_classify_file)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample Python file
        sample_file = Path(temp_dir) / "sample.py"
        sample_file.write_text("print('Hello, World!')")

        files, _ = discover_source_files(temp_dir, "unit")
        assert len(files) == 1


def test_discover_source_files_exclude(monkeypatch):
    def mock_classify_file(_file_path, _content):
        return {
            "should_test": True,
            "test_type": "unit",
            "framework": "pytest",
            "priority": "high",
        }

    monkeypatch.setattr("utils.classify_file", mock_classify_file)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample Python file
        sample_file = Path(temp_dir) / "sample.py"
        sample_file.write_text("print('Hello, World!')")

        # Create an exclude directory
        exclude_dir = Path(temp_dir) / "exclude"
        exclude_dir.mkdir()
        exclude_file = exclude_dir / "exclude.py"
        exclude_file.write_text("print('Exclude this file')")

        files, _ = discover_source_files(temp_dir, "unit", exclude_dirs=["exclude"])
        assert len(files) == 1
