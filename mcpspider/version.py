"""Version management for MCPSearch."""

__version__ = "1.1.0"

VERSION = tuple(int(x) for x in __version__.split("."))


def bump_major() -> str:
    """Bump major version (1.0.0 -> 2.0.0)."""
    return f"{VERSION[0] + 1}.0.0"


def bump_minor() -> str:
    """Bump minor version (1.0.0 -> 1.1.0)."""
    return f"{VERSION[0]}.{VERSION[1] + 1}.0"


def bump_patch() -> str:
    """Bump patch version (1.0.0 -> 1.0.1)."""
    return f"{VERSION[0]}.{VERSION[1]}.{VERSION[2] + 1}"


def set_version(new_version: str) -> None:
    """Update version in version.py and pyproject.toml."""
    import re
    from pathlib import Path

    # Update version.py
    version_file = Path(__file__)
    content = version_file.read_text()
    content = re.sub(
        r'__version__ = "[^"]+"',
        f'__version__ = "{new_version}"',
        content
    )
    version_file.write_text(content)

    # Update pyproject.toml
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        content = re.sub(
            r'version = "[^"]+"',
            f'version = "{new_version}"',
            content
        )
        pyproject.write_text(content)

    print(f"Version updated to {new_version}")
