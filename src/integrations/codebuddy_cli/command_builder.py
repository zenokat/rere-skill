"""Build audited CodeBuddy CLI commands for eval cases.

The command builder only prepares arguments and the visible prompt. It never
overrides CodeBuddy's own system prompt; WorkBuddy-like context is injected as
ordinary prompt text using observed `system-reminder` blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evals.cases.manifest_models import EvalCase, TargetConfig
from evals.shared.types import OutputFormat
from integrations.codebuddy_cli.safety_guard import SafetyDecision


def _current_time_gmt8() -> str:
    """Return the current wall-clock time formatted as a GMT+8 string.

    Args:
        None.

    Returns:
        str: Human-readable current time in Beijing time (UTC+8), e.g.
        ``"Sunday, June 29, 2026 at 16:37:25 GMT+8"``. WorkBuddy exposes the
        local time to the agent this way, so the eval mirrors that.
    """

    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)
    return now.strftime("%A, %B %d, %Y at %H:%M:%S GMT+8")


DEFAULT_IDENTITY_CONTEXT = """<identity_context>
The following identity files are included in Project Context for this turn.
Use them directly as context.

Injected workspace identity files:

## SOUL.md
Path: <default-workbuddy-identity>/SOUL.md
---
title: "SOUL.md Template"
summary: "Workspace template for SOUL.md"
read_when:
  - Bootstrapping a workspace manually
---

# SOUL.md - Who You Are

_You're not a chatbot. You're becoming someone._

## Core Truths

**Be genuinely helpful, not performatively helpful.** Skip filler and just help.

**Be resourceful before asking.** Read the files and inspect available context before asking the user to do work.

**Earn trust through competence.** Be careful with external actions and bold with internal analysis.

## Boundaries

- Private things stay private.
- When in doubt, ask before acting externally.
- Never send half-baked replies to messaging surfaces.

## IDENTITY.md
Path: <default-workbuddy-identity>/IDENTITY.md
---
summary: "Agent identity record"
read_when:
  - Bootstrapping a workspace manually
---

# IDENTITY.md - Who Am I?

- **Name:**
- **Creature:**
- **Vibe:**
- **Emoji:**

## USER.md
Path: <default-workbuddy-identity>/USER.md
---
summary: "User profile record"
read_when:
  - Bootstrapping a workspace manually
---

# USER.md - About Your Human

- **Name:**
- **What to call them:**
- **Pronouns:**
- **City:**
- **Notes:**
</identity_context>"""

CONNECTOR_STATUS = """<connector-status>
anydev AnyDev Cloud Development: disconnected
baidu-netdisk Baidu Netdisk: disconnected
bugly Bugly Quality Overview: disconnected
cloudbase Tencent CloudBase: disconnected
cnb-api CNB: disconnected
cnb-woa CNB Internal: disconnected
ctrip-wendao Ctrip Wendao: disconnected
dingtalk DingTalk: disconnected
edgeone-pages EdgeOne Pages: disconnected
feishu Feishu: disconnected
github GitHub: disconnected
ima-mcp ima Knowledge Base: disconnected
kdocs Kingsoft Docs: disconnected
km KM: disconnected
notion Notion: disconnected
qq-mail QQ Mail: disconnected
tapd TAPD: disconnected
tencent-docs Tencent Docs: disconnected
wecom WeCom: disconnected
</connector-status>"""


@dataclass(frozen=True)
class CodeBuddyCommand:
    """CodeBuddy command description.

    Args:
        args: Subprocess-ready arguments.
        display: Human-readable command for evidence.
        output_format: Requested CodeBuddy output format.
        stdin: Prompt text passed through stdin.

    Returns:
        Immutable command description.
    """

    args: list[str]
    display: str
    stdin: str | None = None
    output_format: OutputFormat = OutputFormat.JSON


class CodeBuddyCommandBuilder:
    """Build `codebuddy -p` headless commands.

    Docker mode is the default isolation boundary; CodeBuddy tool permissions
    remain auxiliary.
    """

    def build(
        self,
        *,
        target: TargetConfig,
        case: EvalCase,
        working_directory: Path,
        safety_decision: SafetyDecision,
    ) -> CodeBuddyCommand:
        """Build the command for one case.

        Args:
            target: Runtime target information.
            case: Current eval case.
            working_directory: Disposable sandbox directory.
            safety_decision: Safety guard decision.

        Returns:
            CodeBuddyCommand with arguments and display text.
        """

        prompt = self._build_prompt(case=case, target=target, working_directory=working_directory)
        args = [target.codebuddy_executable]
        if target.use_container_sandbox:
            args.extend(["--sandbox", "container", "--sandbox-new", "--sandbox-kill"])
        args.extend(["--permission-mode", safety_decision.permission_mode])
        if target.use_container_sandbox:
            args.extend(["--tools", "default"])
        else:
            allowed_tools = _workspace_allowed_tools(working_directory=working_directory, target=target)
            if allowed_tools:
                args.extend(["--allowedTools", " ".join(allowed_tools)])
        args.extend(["--disallowedTools", "Agent"])
        args.extend(["-p", "--output-format", OutputFormat.JSON.value])
        return CodeBuddyCommand(
            args=args,
            display=_quote_command([*args, "<prompt via stdin>"]),
            stdin=prompt,
            output_format=OutputFormat.JSON,
        )

    def _build_prompt(self, *, case: EvalCase, target: TargetConfig, working_directory: Path) -> str:
        """Build a visible WorkBuddy-style prompt.

        Args:
            case: Current eval case.
            target: Runtime target information.
            working_directory: Disposable sandbox directory.

        Returns:
            Prompt text passed to CodeBuddy via `-p`.
        """

        workspace_structure = _workspace_structure(target)
        manually_attached = _manually_attached_skills(case=case, target=target)
        user_context_sections = [
            '<system-reminder data-role="user-context">',
            "<user_info>",
            "OS Version: win32",
            "Shell: bash",
            "IDE Theme: light",
            "Note: Prefer paths inside the current sandbox workspace. Do not read or write outside this workspace.",
            "</user_info>",
            DEFAULT_IDENTITY_CONTEXT,
            "<product_identity>",
            "You are WorkBuddy, a powerful AI assistant.",
            "</product_identity>",
            "<project_context>",
            "<project_layout>",
            "Below is a snapshot of the current sandbox workspace file structure.",
            workspace_structure,
            "</project_layout>",
            "</project_context>",
            "<additional_data>",
            "<current_time>",
            _current_time_gmt8(),
            "</current_time>",
            CONNECTOR_STATUS,
            "</additional_data>",
            "<memory_and_skills_reminder>",
            "Memory and skill-management reminders are part of the visible WorkBuddy context. In this eval, any file read or write must stay inside the sandbox workspace.",
            "",
            "Workspace layout:",
            "- input/ contains the source files required by this task.",
            "- output/ is where all task artifacts should be written.",
            "- .workbuddy/skills/ contains available skill packages with SKILL.md (guidelines) and scripts/ (executable tools).",
            "</memory_and_skills_reminder>",
        ]
        if manually_attached:
            user_context_sections.extend(
                [
                    "<manually_attached_skills>",
                    *manually_attached,
                    "</manually_attached_skills>",
                ]
            )
        user_context_sections.extend(
            [
                "</system-reminder>",
                "<user_query>",
                case.instruction,
                "</user_query>",
            ]
        )
        return "\n".join(user_context_sections)


def _workspace_allowed_tools(*, working_directory: Path, target: TargetConfig) -> list[str]:
    """Build CodeBuddy tool allow rules scoped to the sandbox workspace.

    Args:
        working_directory: Sandbox workspace root.
        target: Runtime target information.

    Returns:
        Tool allow-list patterns for CodeBuddy CLI.
    """

    workspace = _tool_path(working_directory)
    output_dir = _tool_path(working_directory / "output")
    return [
        "Bash",
        "PowerShell",
        f"Read({workspace}/**)",
        f"Edit({output_dir}/**)",
        f"Write({output_dir}/**)",
    ]


def _workspace_structure(target: TargetConfig) -> str:
    """Describe the workspace layout shown to the evaluated agent.

    Args:
        target: Runtime target information.

    Returns:
        Human-readable workspace tree.
    """

    skill_lines = []
    for skill_name in target.skill_names:
        skill_lines.extend(
            [
                f"        - {skill_name}/",
                "          - SKILL.md",
                "          - references/",
                "          - scripts/",
            ]
        )
    if not skill_lines:
        skill_lines.append("        - (none)")
    return "\n".join(
        [
            "- input/           -- 本任务所需的源文件",
            "- output/          -- 本任务的所有产出",
            "- .workbuddy/",
            "  - skills/",
            *skill_lines,
        ]
    )


def _manually_attached_skills(*, case: EvalCase, target: TargetConfig) -> list[str]:
    """Infer slash-invoked WorkBuddy skills from the user instruction.

    Args:
        case: Current eval case.
        target: Runtime target information.

    Returns:
        Lines to include in `<manually_attached_skills>`. Empty means no manual
        skill attachment should be declared.
    """

    lines: list[str] = []
    instruction = case.instruction
    for skill_name, entry in zip(target.skill_names, _pad_entries(target.skill_entries, len(target.skill_names))):
        if f"/{skill_name}" not in instruction:
            continue
        lines.extend(
            [
                "Please use the use_skill tool to invoke this skill.",
                f"name: {skill_name}",
                f"description: Manually attached by slash command `/{skill_name}` in the user query.",
            ]
        )
        if entry:
            lines.append(f"fallback_path: {entry}")
    return lines


def _pad_entries(entries: list[str], length: int) -> list[str | None]:
    """Pad skill entry paths to align with skill names.

    Args:
        entries: Materialized SKILL.md paths.
        length: Desired output length.

    Returns:
        List of entry paths or None values.
    """

    padded: list[str | None] = list(entries)
    while len(padded) < length:
        padded.append(None)
    return padded[:length]


def _tool_path(path: Path) -> str:
    """Normalize a path for CodeBuddy tool pattern strings.

    Args:
        path: Host path.

    Returns:
        POSIX-style path string.
    """

    return path.resolve().as_posix()


def _quote_command(args: list[str]) -> str:
    """Create a human-readable command line.

    Args:
        args: Subprocess argument list.

    Returns:
        Display command with simple quoting.
    """

    quoted: list[str] = []
    for item in args:
        if any(char.isspace() for char in item):
            quoted.append('"' + item.replace('"', '\\"') + '"')
        else:
            quoted.append(item)
    return " ".join(quoted)