"""按项目作用域附加小型规则补丁。

这个注册器的目标不是承载所有业务逻辑，而是在“通用规则引擎覆盖不了的少量特例”
场景下，给我们一个可控、可追踪、可回归的小扩展点。
"""

from __future__ import annotations

from collections.abc import Callable

from models.domain import RuleBundle

ProjectPatch = Callable[[RuleBundle], RuleBundle]

_PATCH_REGISTRY: dict[str, list[ProjectPatch]] = {}


def register_project_patch(recog_id: str, patch: ProjectPatch) -> None:
    """注册某个项目的补丁函数。"""

    _PATCH_REGISTRY.setdefault(recog_id, []).append(patch)


def apply_project_patches(rule_bundle: RuleBundle) -> RuleBundle:
    """按顺序应用某个项目的所有补丁。"""

    patched_bundle = rule_bundle
    for patch in _PATCH_REGISTRY.get(rule_bundle.recog_id, []):
        patched_bundle = patch(patched_bundle)
    return patched_bundle

