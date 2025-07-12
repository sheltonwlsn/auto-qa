from pathlib import Path
from typing import Dict, List, Tuple

import click

from common.agent import classify_file


def write_output_file(output_dir: str, filename: str, content: str):
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / filename

    with open(file_path, "w") as f:
        f.write(content)

    return str(file_path)


def clean_code_fences(text: str) -> str:
    """
    Remove markdown code fences from generated content.
    """
    lines = text.strip().split("\n")
    cleaned = [line for line in lines if not line.strip().startswith("```")]
    return "\n".join(cleaned)


def discover_source_files(
    project_root: str,
    test_type: str,
    include_dirs: List[str] = None,
    exclude_dirs: List[str] = None,
    file_glob: str = None,
) -> Tuple[List[Path], Dict[str, dict]]:
    """
    Recursively discovers files relevant for the test_type.
    """
    exts = []
    if test_type == "unit":
        exts = [".py"]
    elif test_type == "e2e":
        exts = [".js", ".jsx", ".ts", ".tsx"]
    elif test_type == "manual":
        exts = [".md", ".txt"]
    else:
        raise ValueError(f"Unsupported test type: {test_type}")

    files = []
    project_root = Path(project_root)
    exclude_paths = [project_root / d for d in exclude_dirs or []]

    def is_excluded(path: Path):
        return any(excluded in path.parents for excluded in exclude_paths)

    files = []

    if include_dirs:
        dirs_to_scan = [project_root / d for d in include_dirs]
    else:
        dirs_to_scan = [project_root]

    for base_dir in dirs_to_scan:
        if file_glob:
            # Only apply file_glob ONCE per base_dir
            for f in base_dir.rglob(file_glob):
                if not is_excluded(f):
                    files.append(f)
        else:
            # If no file_glob, loop over extensions
            for ext in exts:
                for f in base_dir.rglob(f"*{ext}"):
                    if not is_excluded(f):
                        files.append(f)

    # 🟢 Agent-based filtering
    file_metadata = {}
    filtered = []
    for f in files:
        skip_classification = test_type == "manual"
        if skip_classification:
            click.echo(f"[AutoQA] [Agent]: Skipping classification for manual test type: {f}")
            info = {
                "should_test": True,
                "test_type": "manual",
                "framework": None,
                "priority": "low",
            }
            filtered.append(f)
            file_metadata[str(f)] = info
            click.echo(f"[AutoQA] [Manual Mode]: Including {f}")
            continue
        with open(f, "r") as fp:
            content = fp.read()
        info = classify_file(str(f), content)
        if info["should_test"]:
            click.echo(
                f"[AutoQA] [Agent]: ✅ YES - {f} (Type: {info['test_type']}, Priority: {info['priority']})"
            )
            filtered.append(f)
            file_metadata[str(f)] = info
        else:
            click.echo(f"[AutoQA] [Agent]: ❌ NO - {f}")

    return list(sorted(set(filtered))), file_metadata


def resolve_output_path(
    project_root: Path,
    output_project_root: Path,
    source_file: Path,
    test_type: str,
    framework: str,
    strip_prefix: str = None,
) -> Path:
    """
    Creates the output file path for the generated test.
    For unit tests, if output_project_root is None, place next to source.
    """
    if strip_prefix:
        strip_path = project_root / strip_prefix
        relative_path = source_file.relative_to(strip_path)
    else:
        relative_path = source_file.relative_to(project_root)

    # Determine filename and subdir
    if framework == "pytest":
        test_filename = f"test_{relative_path.stem}.py"
    elif framework == "jest":
        test_filename = f"{relative_path.stem}.test.js"
    elif framework == "playwright":
        test_filename = f"test_{relative_path.stem}.py"
    elif framework == "cypress":
        test_filename = f"{relative_path.stem}.spec.js"
    else:
        test_filename = f"manual_{relative_path.stem}.txt"

    # Decide output location
    if test_type == "unit" and output_project_root is None:
        # Write next to source file
        output_path = source_file.parent / test_filename
    else:
        # Mirror structure under output_project_root
        if framework == "pytest" or framework == "jest":
            subdir = "" if project_root == output_project_root else "unit"
        elif framework == "playwright":
            subdir = "playwright"
        elif framework == "cypress":
            subdir = "cypress/e2e"
        else:
            subdir = "manual"

        output_path = output_project_root / subdir / relative_path.parent / test_filename

    return output_path
