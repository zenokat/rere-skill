"""Models for the eval suite and case-folder contract.

The evaluator-facing manifest is intentionally small: a suite id, a list of
grader ids, and a list of case folder names. The actual case materials live in
`cases/<case_id>/instruction.md`, `skills/`, and `input/`.
"""

from __future__ import annotations

from pathlib import Path
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class EvalCase(BaseModel):
    """A validated eval case folder.

    Args:
        case_id: Stable case folder name.
        case_dir: Absolute path to the case source folder.
        instruction_path: Absolute path to `instruction.md`.
        skills_dir: Absolute path to `skills/`.
        input_dir: Absolute path to `input/`.
        instruction: User-facing task text from `instruction.md`.
        suite_shared_input: Absolute path to suite-level shared input
            directory. Used when the case-level `input/` is empty.
        suite_shared_skills: Absolute path to suite-level shared skills
            directory. Used when the case-level `skills/` is empty.

    Returns:
        EvalCase instance used by the runner.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    case_id: str
    case_dir: Path
    instruction_path: Path
    skills_dir: Path
    input_dir: Path
    instruction: str
    suite_shared_input: Path | None = None
    suite_shared_skills: Path | None = None

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, value: str) -> str:
        """Validate that a case id is a safe folder name.

        Args:
            value: Raw case id.

        Returns:
            Cleaned case id.

        Raises:
            ValueError: If the id is empty or can escape the suite folder.
        """

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("case id cannot be empty")
        if not CASE_ID_PATTERN.match(cleaned):
            raise ValueError("case id must be a simple folder name")
        if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
            raise ValueError("case id cannot contain path traversal or path separators")
        return cleaned

    @property
    def prompt(self) -> str:
        """Return the instruction text for compatibility with older helpers.

        Args:
            None.

        Returns:
            The case instruction text.
        """

        return self.instruction

    def skill_names(self) -> list[str]:
        """List skill package names provided by this case.

        Args:
            None.

        Returns:
            Sorted skill folder names under `skills/`.
        """

        if not self.skills_dir.exists():
            return []
        return sorted(path.name for path in self.skills_dir.iterdir() if path.is_dir())


class TargetConfig(BaseModel):
    """Runtime target for the CodeBuddy runner.

    Args:
        skill_names: Skill names visible in the sandbox.
        skill_entries: Explicit fallback paths to sandbox `SKILL.md` files.
        codebuddy_executable: CLI executable name.
        use_container_sandbox: Whether CodeBuddy should run the case inside a Docker-backed sandbox. Docker is the default isolation boundary.
        env: Extra environment variables for the CodeBuddy process.

    Returns:
        TargetConfig instance used to build the CLI command.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skill_names: list[str] = Field(default_factory=list)
    skill_entries: list[str] = Field(default_factory=list)
    codebuddy_executable: str = "codebuddy"
    use_container_sandbox: bool = True
    env: dict[str, str] = Field(default_factory=dict)

    @property
    def skill_name(self) -> str:
        """Return the first skill name for legacy call sites.

        Args:
            None.

        Returns:
            First skill name, or a generic label when none exists.
        """

        return self.skill_names[0] if self.skill_names else "case-skill"

    @property
    def skill_entry(self) -> str | None:
        """Return the first explicit skill entry for legacy call sites.

        Args:
            None.

        Returns:
            First skill entry path, if any.
        """

        return self.skill_entries[0] if self.skill_entries else None


class EvalSuiteManifest(BaseModel):
    """Loaded eval suite manifest.

    Args:
        suite_id: Suite identifier.
        graders: Grader ids to execute for every case.
        cases: Resolved case folders.
        source_path: Absolute path to `suite.yaml`.

    Returns:
        EvalSuiteManifest instance used by the batch runner.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    suite_id: str
    graders: list[str] = Field(min_length=1)
    cases: list[EvalCase] = Field(min_length=1)
    source_path: Path | None = None
    suite_shared_input: Path | None = None
    suite_shared_skills: Path | None = None

    @field_validator("suite_id")
    @classmethod
    def validate_suite_id(cls, value: str) -> str:
        """Validate the suite id.

        Args:
            value: Raw suite id.

        Returns:
            Cleaned suite id.
        """

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("suite_id cannot be empty")
        return cleaned

    @field_validator("graders")
    @classmethod
    def validate_graders(cls, value: list[str]) -> list[str]:
        """Validate grader ids.

        Args:
            value: Raw grader id list.

        Returns:
            Cleaned grader id list.
        """

        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("graders must contain at least one grader id")
        return cleaned

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> "EvalSuiteManifest":
        """Ensure each case id appears once.

        Args:
            None.

        Returns:
            The validated manifest.

        Raises:
            ValueError: If duplicate case ids are found.
        """

        seen: set[str] = set()
        duplicates: list[str] = []
        for case in self.cases:
            if case.case_id in seen:
                duplicates.append(case.case_id)
            seen.add(case.case_id)
        if duplicates:
            raise ValueError(f"duplicate case ids: {', '.join(sorted(duplicates))}")
        return self

    def enabled_cases(self) -> list[EvalCase]:
        """Return all cases.

        Args:
            None.

        Returns:
            Case list. The first release has no enabled/disabled switch.
        """

        return list(self.cases)
