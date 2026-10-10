"""UME API v1 router table."""

from ume_app.api.routes import projects, workspaces

API_PREFIX = "/api/ume/v1"


def build_router():
    from fastapi import APIRouter

    router = APIRouter()
    router.include_router(workspaces.router)
    router.include_router(projects.router)
    return router


__all__ = ["API_PREFIX", "build_router", "projects", "workspaces"]
