
from typing import Annotated
from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.core.exceptions import ForbiddenException, NotFoundException
from app.services.projects_service import ProjectsService
from app.schemas.projects_schemas import ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def _require_view_access(user: CurrentUser) -> None:
    # Tenants with the feature or users with permission should be allowed.
    if not user.is_admin() and not user.has_permission("Projects.View"):
        raise ForbiddenException("Projects.View permission required.")


def _require_manage_access(user: CurrentUser) -> None:
    if not user.is_admin() and not user.has_permission("Projects.Manage"):
        raise ForbiddenException("Projects.Manage permission required.")


@router.get("")
async def list_projects(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_view_access(current_user)
    return await ProjectsService(db).list_projects(current_user.tenant_id)


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_view_access(current_user)
    p = await ProjectsService(db).get_project(current_user.tenant_id, project_id)
    if not p:
        raise NotFoundException("Project not found")
    return p


@router.post("", status_code=201)
async def create_project(
    payload: ProjectCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_manage_access(current_user)
    return await ProjectsService(db).create_project(current_user.tenant_id, payload)


@router.put("/{project_id}")
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_manage_access(current_user)
    p = await ProjectsService(db).update_project(current_user.tenant_id, project_id, payload)
    if not p:
        raise NotFoundException("Project not found")
    return p


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_manage_access(current_user)
    ok = await ProjectsService(db).delete_project(current_user.tenant_id, project_id)
    if not ok:
        raise NotFoundException("Project not found")
    return {"success": True}


@router.post("/{project_id}/attachments/{file_id}")
async def attach_file(
    project_id: UUID,
    file_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_manage_access(current_user)
    ok = await ProjectsService(db).attach_file(current_user.tenant_id, project_id, file_id)
    if not ok:
        raise NotFoundException("Project or file not found")
    return {"success": True}


@router.delete("/{project_id}/attachments/{file_id}")
async def detach_file(
    project_id: UUID,
    file_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_manage_access(current_user)
    ok = await ProjectsService(db).detach_file(current_user.tenant_id, project_id, file_id)
    if not ok:
        raise NotFoundException("Attachment not found")
    return {"success": True}
