#!/usr/bin/env python3
"""
Bidirectional skill sync between .claude/skills/ and .agents/skills/.

Designed as a pre-commit hook: scans both skill directories, compares their
contents, and ensures both coding agents (Claude Code and Codex) always see
the same set of skills. After syncing, only git-tracked skills are staged
for commit; gitignored skills (e.g. speckit-*) remain untracked.

Dependencies: Python standard library only (os, sys, subprocess, shutil, pathlib, re).
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Force UTF-8 on Windows to avoid GBK decode errors in subprocess output.
os.environ["PYTHONIOENCODING"] = "utf-8"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path from this script's location: .claude/scripts/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"
CODEX_SKILLS = REPO_ROOT / ".agents" / "skills"

# Subdirectories that belong to one side only and must never be synced.
CODEX_ONLY_SUBDIRS = {"agents"}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_ls_files(*paths: str) -> set[str]:
    """Return the set of git-tracked files under the given paths."""
    result = subprocess.run(
        ["git", "ls-files", *paths],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    output = result.stdout.strip()
    return set(output.splitlines()) if output else set()


def git_add(path: str) -> None:
    """Stage a file or directory into the index."""
    subprocess.run(
        ["git", "add", path],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )


# ---------------------------------------------------------------------------
# Frontmatter / body parsing
# ---------------------------------------------------------------------------

def extract_raw_frontmatter(content: str) -> str:
    """Extract the raw frontmatter block (including --- delimiters)."""
    if not content.startswith("---"):
        return ""
    end = content.find("\n---", 3)
    if end == -1:
        return content
    return content[: end + 4]  # include the closing \n---


def extract_body(content: str) -> str:
    """Extract the body text after the frontmatter closing ---.

    Returns empty string if content is None or empty.
    """
    if not content:
        return ""
    if not content.startswith("---"):
        return content.strip()
    end = content.find("\n---", 3)
    if end == -1:
        return content.strip()
    return content[end + 4 :].strip()


def parse_frontmatter(content: str) -> dict[str, str]:
    """Parse simple YAML frontmatter into a flat dict.

    Only handles top-level scalar fields (name, description, compatibility).
    Nested structures like metadata are returned as raw string values.
    """
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    result: dict[str, str] = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def build_claude_frontmatter(name: str, description: str) -> str:
    """Build minimal frontmatter for the Claude Code side.

    Format: unquoted scalars, only name and description.
    """
    return f"---\nname: {name}\ndescription: {description}\n---"


def build_codex_frontmatter(name: str, description: str) -> str:
    """Build frontmatter for the Codex side when creating from scratch.

    Includes compatibility and metadata fields for new skills.
    """
    return (
        f"---\n"
        f'name: "{name}"\n'
        f'description: "{description}"\n'
        f'compatibility: "Claude Code / Codex shared skill"\n'
        f"metadata:\n"
        f'  author: "manual"\n'
        f"  source: \"synced from .claude/skills/{name}/SKILL.md\"\n"
        f"---"
    )


def update_fm_field(fm_text: str, key: str, new_value: str) -> str:
    """Update a top-level scalar field in raw frontmatter text.

    If the field does not exist, append it before the closing ---.
    """
    # Pattern: optional leading whitespace, then key: value
    pattern = re.compile(rf"^({re.escape(key)}:\s*).*$", re.MULTILINE)
    match = pattern.search(fm_text)
    if match:
        # Preserve the original quoting style of the value being replaced.
        old_value_full = match.group(0)[len(match.group(1)) :].strip()
        if old_value_full.startswith('"') and old_value_full.endswith('"'):
            new_value = f'"{new_value}"'
        elif old_value_full.startswith("'") and old_value_full.endswith("'"):
            new_value = f"'{new_value}'"
        return pattern.sub(rf"\g<1>{new_value}", fm_text)
    else:
        # Field not found -- insert before closing ---
        closing = fm_text.rfind("---")
        if closing != -1:
            # Find the actual closing --- (the second one)
            first_end = fm_text.find("---\n", 3)
            if first_end != -1:
                insert_pos = first_end
                return fm_text[:insert_pos] + f"{key}: {new_value}\n" + fm_text[insert_pos:]
        return fm_text


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def sync_references(src_dir: Path, dst_dir: Path) -> None:
    """Recursively copy references/ directory from source to destination.

    Uses clean replacement: deletes the target directory entirely before copying,
    ensuring the destination is an exact mirror of the source.
    """
    src_ref = src_dir / "references"
    dst_ref = dst_dir / "references"

    if not src_ref.is_dir():
        return

    if dst_ref.exists():
        shutil.rmtree(dst_ref)

    shutil.copytree(src_ref, dst_ref)


# ---------------------------------------------------------------------------
# Sync operations
# ---------------------------------------------------------------------------

def create_on_codex(skill_name: str) -> None:
    """Create a new skill on the Codex side from the Claude side."""
    claude_skill = CLAUDE_SKILLS / skill_name / "SKILL.md"
    content = claude_skill.read_text(encoding="utf-8")

    fm = parse_frontmatter(content)
    name = fm.get("name", skill_name)
    description = fm.get("description", "")
    body = extract_body(content)

    codex_dir = CODEX_SKILLS / skill_name
    codex_dir.mkdir(parents=True, exist_ok=True)

    codex_fm = build_codex_frontmatter(name, description)
    codex_skill = codex_dir / "SKILL.md"
    codex_skill.write_text(f"{codex_fm}\n\n{body}\n", encoding="utf-8")

    sync_references(CLAUDE_SKILLS / skill_name, codex_dir)


def create_on_claude(skill_name: str) -> None:
    """Create a new skill on the Claude side from the Codex side."""
    codex_skill = CODEX_SKILLS / skill_name / "SKILL.md"
    content = codex_skill.read_text(encoding="utf-8")

    fm = parse_frontmatter(content)
    name = fm.get("name", skill_name)
    description = fm.get("description", "")
    body = extract_body(content)

    claude_dir = CLAUDE_SKILLS / skill_name
    claude_dir.mkdir(parents=True, exist_ok=True)

    claude_fm = build_claude_frontmatter(name, description)
    claude_skill = claude_dir / "SKILL.md"
    claude_skill.write_text(f"{claude_fm}\n\n{body}\n", encoding="utf-8")

    sync_references(CODEX_SKILLS / skill_name, claude_dir)


def update_codex(skill_name: str) -> None:
    """Update the Codex side skill from the Claude side.

    Preserves the existing Codex frontmatter (including compatibility and
    metadata), only replaces the body and updates name/description if changed.
    """
    claude_content = (CLAUDE_SKILLS / skill_name / "SKILL.md").read_text(encoding="utf-8")
    codex_path = CODEX_SKILLS / skill_name / "SKILL.md"
    codex_content = codex_path.read_text(encoding="utf-8")

    claude_fm = parse_frontmatter(claude_content)
    claude_body = extract_body(claude_content)

    # Preserve Codex frontmatter verbatim, update name/description if changed
    codex_fm_raw = extract_raw_frontmatter(codex_content)
    codex_fm_raw = update_fm_field(codex_fm_raw, "name", claude_fm.get("name", skill_name))
    codex_fm_raw = update_fm_field(
        codex_fm_raw, "description", claude_fm.get("description", "")
    )

    codex_path.write_text(f"{codex_fm_raw}\n\n{claude_body}\n", encoding="utf-8")

    sync_references(CLAUDE_SKILLS / skill_name, CODEX_SKILLS / skill_name)


def update_claude(skill_name: str) -> None:
    """Update the Claude side skill from the Codex side.

    Regenerates the Claude minimal frontmatter entirely and replaces the body.
    """
    codex_content = (CODEX_SKILLS / skill_name / "SKILL.md").read_text(encoding="utf-8")
    claude_path = CLAUDE_SKILLS / skill_name / "SKILL.md"

    codex_fm = parse_frontmatter(codex_content)
    codex_body = extract_body(codex_content)

    claude_fm = build_claude_frontmatter(
        codex_fm.get("name", skill_name), codex_fm.get("description", "")
    )
    claude_path.write_text(f"{claude_fm}\n\n{codex_body}\n", encoding="utf-8")

    sync_references(CODEX_SKILLS / skill_name, CLAUDE_SKILLS / skill_name)


def delete_from_codex(skill_name: str) -> None:
    """Remove a skill entirely from the Codex side (including agents/)."""
    codex_dir = CODEX_SKILLS / skill_name
    if codex_dir.is_dir():
        shutil.rmtree(codex_dir)
    # Stage the deletion (even for paths that no longer exist)
    git_add(str(CLAUDE_SKILLS / skill_name))
    git_add(str(codex_dir))


def delete_from_claude(skill_name: str) -> None:
    """Remove a skill entirely from the Claude side."""
    claude_dir = CLAUDE_SKILLS / skill_name
    if claude_dir.is_dir():
        shutil.rmtree(claude_dir)
    git_add(str(claude_dir))
    git_add(str(CODEX_SKILLS / skill_name))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Scan both skill directories and sync differences.

    Simple logic:
    - If a skill exists on one side but not the other, create it on the
      missing side.
    - If a skill exists on both sides but body content differs, update
      the side whose body differs from the other.
    - If a skill exists on both sides and body content is identical, do
      nothing.

    After syncing, git add the changed files so they are included in the
    current commit.
    """
    os.chdir(REPO_ROOT)

    # 1. Enumerate skills on each side by scanning directories on disk.
    claude_skills: set[str] = set()
    codex_skills: set[str] = set()

    if CLAUDE_SKILLS.is_dir():
        for d in CLAUDE_SKILLS.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                claude_skills.add(d.name)

    if CODEX_SKILLS.is_dir():
        for d in CODEX_SKILLS.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                codex_skills.add(d.name)

    all_skills = sorted(claude_skills | codex_skills)

    # 2. Compare each skill and decide what to do.
    actions: list[tuple[str, str]] = []

    for name in all_skills:
        claude_body = _read_body(CLAUDE_SKILLS / name / "SKILL.md")
        codex_body = _read_body(CODEX_SKILLS / name / "SKILL.md")

        if claude_body is not None and codex_body is not None:
            # Both exist. If bodies match, nothing to do.
            if claude_body == codex_body:
                continue
            # Bodies differ -- pick the newer one based on file mtime.
            claude_mtime = (CLAUDE_SKILLS / name / "SKILL.md").stat().st_mtime
            codex_mtime = (CODEX_SKILLS / name / "SKILL.md").stat().st_mtime
            if claude_mtime >= codex_mtime:
                actions.append(("update_codex", name))
            else:
                actions.append(("update_claude", name))

        elif claude_body is not None and codex_body is None:
            # Only on Claude side -- create on Codex side.
            actions.append(("create_codex", name))

        elif claude_body is None and codex_body is not None:
            # Only on Codex side -- create on Claude side.
            actions.append(("create_claude", name))

    # 3. Execute sync actions.
    for action, name in actions:
        if action == "create_codex":
            create_on_codex(name)
            print(f"  SYNC: Created '{name}' on Codex side")
        elif action == "create_claude":
            create_on_claude(name)
            print(f"  SYNC: Created '{name}' on Claude side")
        elif action == "update_codex":
            update_codex(name)
            print(f"  SYNC: Updated '{name}' on Codex side")
        elif action == "update_claude":
            update_claude(name)
            print(f"  SYNC: Updated '{name}' on Claude side")

    # 4. Stage synced files, but only for git-tracked skills.
    #    Skills that are gitignored (e.g. speckit-*) should remain untracked.
    #    A skill is "tracked" if any file under its source-side directory
    #    appears in git ls-files.
    if actions:
        tracked = git_ls_files(str(CLAUDE_SKILLS), str(CODEX_SKILLS))
        claude_prefix = CLAUDE_SKILLS.relative_to(REPO_ROOT).as_posix()
        codex_prefix = CODEX_SKILLS.relative_to(REPO_ROOT).as_posix()

        # Determine which skill names are git-tracked on either side.
        tracked_skill_names: set[str] = set()
        for f in tracked:
            f_norm = f.replace("\\", "/")
            for prefix in (claude_prefix, codex_prefix):
                if f_norm.startswith(prefix + "/"):
                    parts = f_norm[len(prefix) + 1 :].split("/")
                    if parts:
                        tracked_skill_names.add(parts[0])
                    break

        for _, name in actions:
            if name not in tracked_skill_names:
                continue
            for skill_dir in [CLAUDE_SKILLS / name, CODEX_SKILLS / name]:
                if skill_dir.is_dir():
                    git_add(str(skill_dir))

    if actions:
        print(f"Skill sync complete ({len(actions)} skill(s) synced).")


def _read_body(path: Path) -> str | None:
    """Read a SKILL.md file and return its body (after frontmatter).

    Returns None if the file does not exist.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return extract_body(content)


if __name__ == "__main__":
    main()
