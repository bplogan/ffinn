
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.misc import FileUpload
from app.domain.models.projects import Project, ProjectFile, ProjectStatus
from app.schemas.projects_schemas import (
    FileAttachmentSchema,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)


class ProjectsService:
    """Business logic and DB access for Projects feature."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _project_query(self, tenant_id: Optional[uuid.UUID]):
        return select(Project).where(Project.tenant_id == tenant_id).options(
            selectinload(Project.attachments)
        )

    async def _load_project(
        self, tenant_id: Optional[uuid.UUID], project_id: uuid.UUID
    ) -> Optional[Project]:
        stmt = self._project_query(tenant_id).where(Project.id == project_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _build_attachments(
        self, project_files: list[ProjectFile]
    ) -> List[FileAttachmentSchema]:
        file_ids = [pf.file_id for pf in project_files if pf.file_id]
        file_map: dict[uuid.UUID, FileUpload] = {}
        if file_ids:
            rows = (await self.db.execute(
                select(FileUpload).where(FileUpload.id.in_(file_ids))
            )).scalars().all()
            file_map = {f.id: f for f in rows}

        attachments: List[FileAttachmentSchema] = []
        for pf in project_files:
            file_obj = file_map.get(pf.file_id) if pf.file_id else None
            attachments.append(
                FileAttachmentSchema(
                    id=pf.file_id,
                    file_name=getattr(file_obj, "file_name", None) if file_obj else None,
                    url=getattr(file_obj, "url", None) if file_obj else None,
                    label=pf.label,
                )
            )
        return attachments

    async def _to_read(self, project: Project) -> ProjectRead:
        attachments = await self._build_attachments(list(project.attachments))
        return ProjectRead.model_validate(project).model_copy(update={"attachments": attachments})

    async def list_projects(self, tenant_id: Optional[uuid.UUID]) -> List[ProjectRead]:
        stmt = self._project_query(tenant_id).order_by(Project.created_at.desc())
        rows = (await self.db.execute(stmt)).scalars().all()
        return [await self._to_read(p) for p in rows]

    async def get_project(
        self, tenant_id: Optional[uuid.UUID], project_id: uuid.UUID
    ) -> Optional[ProjectRead]:
        project = await self._load_project(tenant_id, project_id)
        if not project:
            return None
        return await self._to_read(project)

    async def _verify_file_tenant(
        self, tenant_id: Optional[uuid.UUID], file_id: uuid.UUID
    ) -> Optional[FileUpload]:
        file_obj = await self.db.get(FileUpload, file_id)
        if not file_obj or file_obj.tenant_id != tenant_id:
            return None
        return file_obj

    async def create_project(
        self, tenant_id: Optional[uuid.UUID], data: ProjectCreate
    ) -> ProjectRead:
        project = Project(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            title=data.title,
            description=data.description,
            status=(ProjectStatus(data.status) if data.status else ProjectStatus.DRAFT),
        )
        self.db.add(project)
        await self.db.flush()

        for fid in data.attachment_ids or []:
            if await self._verify_file_tenant(tenant_id, fid):
                self.db.add(ProjectFile(project_id=project.id, file_id=fid))

        await self.db.commit()

        loaded = await self._load_project(tenant_id, project.id)
        assert loaded is not None
        return await self._to_read(loaded)

    async def update_project(
        self,
        tenant_id: Optional[uuid.UUID],
        project_id: uuid.UUID,
        data: ProjectUpdate,
    ) -> Optional[ProjectRead]:
        project = await self._load_project(tenant_id, project_id)
        if not project:
            return None

        if data.title is not None:
            project.title = data.title
        if data.description is not None:
            project.description = data.description
        if data.status is not None:
            project.status = ProjectStatus(data.status)

        if data.attachment_ids is not None:
            await self.db.execute(delete(ProjectFile).where(ProjectFile.project_id == project.id))
            for fid in data.attachment_ids:
                if await self._verify_file_tenant(tenant_id, fid):
                    self.db.add(ProjectFile(project_id=project.id, file_id=fid))

        await self.db.commit()

        loaded = await self._load_project(tenant_id, project_id)
        assert loaded is not None
        return await self._to_read(loaded)

    async def delete_project(
        self, tenant_id: Optional[uuid.UUID], project_id: uuid.UUID
    ) -> bool:
        project = await self._load_project(tenant_id, project_id)
        if not project:
            return False
        await self.db.delete(project)
        await self.db.commit()
        return True

    async def attach_file(
        self,
        tenant_id: Optional[uuid.UUID],
        project_id: uuid.UUID,
        file_id: uuid.UUID,
        label: Optional[str] = None,
    ) -> bool:
        project = await self._load_project(tenant_id, project_id)
        if not project:
            return False
        file_obj = await self._verify_file_tenant(tenant_id, file_id)
        if not file_obj:
            return False
        self.db.add(ProjectFile(project_id=project_id, file_id=file_id, label=label))
        await self.db.commit()
        return True

    async def detach_file(
        self, tenant_id: Optional[uuid.UUID], project_id: uuid.UUID, file_id: uuid.UUID
    ) -> bool:
        stmt = select(ProjectFile).where(
            ProjectFile.project_id == project_id, ProjectFile.file_id == file_id
        )
        project_file = (await self.db.execute(stmt)).scalar_one_or_none()
        if not project_file:
            return False
        await self.db.delete(project_file)
        await self.db.commit()
        return True
