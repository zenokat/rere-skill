"""列出确认项目的用例。"""

from __future__ import annotations

from core.catalog.project_catalog_repository import ProjectCatalogRepository
from models.cli_results import CatalogSuccessResponse


class ListProjectsUseCase:
    """面向 CLI 的项目目录读取用例。"""

    def __init__(self, repository: ProjectCatalogRepository) -> None:
        """初始化用例。"""

        self._repository = repository

    def execute(self) -> CatalogSuccessResponse:
        """读取项目目录并构造 CLI 输出。"""

        projects = self._repository.list_projects()
        return CatalogSuccessResponse(projects=projects, count=len(projects))

