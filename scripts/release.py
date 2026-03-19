#!/usr/bin/env python3
"""Release script for MCPScout.

Usage:
    python scripts/release.py patch   # 1.0.0 -> 1.0.1
    python scripts/release.py minor   # 1.0.0 -> 1.1.0
    python scripts/release.py major   # 1.0.0 -> 2.0.0
    python scripts/release.py 1.2.3   # explicit version
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION_FILE = ROOT / "mcpspider" / "version.py"
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"


def get_current_version() -> str:
    """Get current version from version.py."""
    content = VERSION_FILE.read_text()
    match = re.search(r'__version__ = "([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in version.py")
    return match.group(1)


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse version string to tuple."""
    parts = version.split(".")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump_version(current: str, bump_type: str) -> str:
    """Bump version based on type."""
    major, minor, patch = parse_version(current)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif re.match(r"^\d+\.\d+\.\d+$", bump_type):
        return bump_type
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")


def update_version_files(new_version: str) -> None:
    """Update version in version.py and pyproject.toml."""
    # Update version.py
    content = VERSION_FILE.read_text()
    content = re.sub(
        r'__version__ = "[^"]+"',
        f'__version__ = "{new_version}"',
        content
    )
    VERSION_FILE.write_text(content)

    # Update pyproject.toml
    content = PYPROJECT.read_text()
    content = re.sub(
        r'version = "[^"]+"',
        f'version = "{new_version}"',
        content
    )
    PYPROJECT.write_text(content)

    print(f"Version updated to {new_version}")


def get_commits_since_tag() -> list[str]:
    """Get commit messages since last tag."""
    # Find last tag
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        cwd=ROOT
    )

    last_tag = result.stdout.strip() if result.returncode == 0 else ""

    if last_tag:
        cmd = ["git", "log", f"{last_tag}..HEAD", "--pretty=format:%s"]
    else:
        cmd = ["git", "log", "--pretty=format:%s"]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def categorize_commits(commits: list[str]) -> dict[str, list[str]]:
    """Categorize commits by type."""
    categories = {
        "Added": [],
        "Changed": [],
        "Fixed": [],
        "Removed": [],
        "Other": []
    }

    for commit in commits:
        if not commit:
            continue
        commit = commit.strip()

        if commit.startswith("feat"):
            categories["Added"].append(commit)
        elif commit.startswith("fix"):
            categories["Fixed"].append(commit)
        elif commit.startswith("refactor"):
            categories["Changed"].append(commit)
        elif commit.startswith("docs"):
            categories["Changed"].append(commit)
        elif commit.startswith("perf"):
            categories["Changed"].append(commit)
        elif commit.startswith("remove"):
            categories["Removed"].append(commit)
        elif commit.startswith("break"):
            categories["Removed"].append(commit)
        else:
            categories["Other"].append(commit)

    return categories


def generate_changelog(version: str, categories: dict[str, list[str]]) -> str:
    """Generate changelog entry."""
    date = datetime.now().strftime("%Y-%m-%d")
    lines = [f"\n## [{version}] - {date}\n"]

    for category, commits in categories.items():
        if commits:
            lines.append(f"### {category}\n")
            for commit in commits:
                # Clean up conventional commit prefix
                clean = re.sub(r"^[a-z]+(\([^)]*\))?:\s*", "", commit)
                lines.append(f"- {clean}")
            lines.append("")

    return "\n".join(lines)


def update_changelog(new_entry: str) -> None:
    """Update CHANGELOG.md with new entry."""
    content = CHANGELOG.read_text()

    # Find insertion point (after header)
    header_end = content.find("## [")
    if header_end == -1:
        # No existing entries, add after header
        header_end = content.find("All notable changes")
        if header_end == -1:
            content += new_entry
        else:
            # Find end of header description
            next_section = content.find("\n\n", header_end)
            if next_section == -1:
                content += new_entry
            else:
                content = content[:next_section + 2] + new_entry + content[next_section + 2:]
    else:
        content = content[:header_end] + new_entry + "\n" + content[header_end:]

    CHANGELOG.write_text(content)
    print("Changelog updated")


def git_commit_and_tag(version: str) -> None:
    """Create git commit and tag."""
    # Add all changes
    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)

    # Commit
    subprocess.run(
        ["git", "commit", "-m", f"chore: release v{version}"],
        cwd=ROOT,
        check=True
    )

    # Tag
    subprocess.run(
        ["git", "tag", "-a", f"v{version}", "-m", f"Release v{version}"],
        cwd=ROOT,
        check=True
    )

    print(f"Created commit and tag v{version}")


def push_to_github(version: str) -> None:
    """Push to GitHub and create release."""
    # Push
    subprocess.run(["git", "push"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "--tags"], cwd=ROOT, check=True)

    # Create release using gh
    result = subprocess.run(
        ["gh", "release", "create", f"v{version}",
         "--title", f"MCPScout v{version}",
         "--generate-notes"],
        cwd=ROOT,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"GitHub release created: {result.stdout.strip()}")
    else:
        print(f"Release note: {result.stderr}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/release.py [patch|minor|major|X.Y.Z]")
        sys.exit(1)

    bump_type = sys.argv[1]
    current = get_current_version()
    new_version = bump_version(current, bump_type)

    print(f"Releasing: {current} -> {new_version}")

    # Get commits and generate changelog
    commits = get_commits_since_tag()
    categories = categorize_commits(commits)
    changelog_entry = generate_changelog(new_version, categories)

    # Update files
    update_version_files(new_version)
    update_changelog(changelog_entry)

    # Confirm
    input(f"\nVersion {new_version} ready. Press Enter to commit and push...")

    # Git operations
    git_commit_and_tag(new_version)
    push_to_github(new_version)

    print(f"\nDone! Released v{new_version}")


if __name__ == "__main__":
    main()
