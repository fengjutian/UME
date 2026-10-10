"""UME API v1 router table."""

from ume_app.api.routes import conversations, memories, projects, workspaces

API_PREFIX = "/api/ume/v1"


def build_router():
    from fastapi import APIRouter

    router = APIRouter()
    router.include_router(workspaces.router)
    router.include_router(projects.router)
    router.include_router(conversations.router)
    router.include_router(memories.router)
    return router


__all__ = ["API_PREFIX", "build_router", "conversations", "memories", "projects", "workspaces"]
