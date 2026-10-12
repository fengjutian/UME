import pathlib

p = pathlib.Path("server/ume_app/services/connectors.py")
s = p.read_text(encoding="utf-8")
old = '''def list_for_workspace(access: WorkspaceAccess, *, limit: int, cursor: str | None) -> Page[Connector]:
    return ConnectorRepository(access.db).list_for_workspace(access.workspace_id, limit=limit, cursor=cursor)'''
new = '''def list_for_workspace(
    access: WorkspaceAccess,
    *,
    limit: int,
    cursor: str | None,
    include_revoked: bool = False,
) -> Page[Connector]:
    """Paged connector list.

    `include_revoked` filters in SQL: filtering after the page was taken would
    shrink a page without reporting it as truncated, so the caller would see a
    short page with `has_more` false and wrongly conclude the list was complete.
    """
    return ConnectorRepository(access.db).list_for_workspace(
        access.workspace_id, limit=limit, cursor=cursor, include_revoked=include_revoked
    )'''
assert old in s, "service anchor missing"
p.write_text(s.replace(old, new), encoding="utf-8")

r = pathlib.Path("server/ume_app/api/router.py")
t = r.read_text(encoding="utf-8")
t = t.replace(
    "from ume_app.api.routes import conversations, graph, memories, projects, workspaces",
    "from ume_app.api.routes import connectors, conversations, graph, memories, projects, workspaces",
)
t = t.replace(
    "    router.include_router(graph.router)\n    return router",
    "    router.include_router(graph.router)\n    router.include_router(connectors.router)\n    return router",
)
t = t.replace(
    '__all__ = ["API_PREFIX", "build_router", "conversations", "graph", "memories", "projects", "workspaces"]',
    '__all__ = [\n    "API_PREFIX",\n    "build_router",\n    "connectors",\n    "conversations",\n    "graph",\n    "memories",\n    "projects",\n    "workspaces",\n]',
)
r.write_text(t, encoding="utf-8")

c = pathlib.Path("server/tests/ume/test_api_contract.py")
u = c.read_text(encoding="utf-8")
u = u.replace(
    '    ("POST", "/context"),\n}',
    '    ("POST", "/context"),\n'
    '    ("GET", "/connectors"),\n'
    '    ("POST", "/connectors"),\n'
    '    ("GET", "/connectors/{connector_id}"),\n'
    '    ("PATCH", "/connectors/{connector_id}"),\n'
    '    ("POST", "/connectors/{connector_id}/revoke"),\n}',
)
c.write_text(u, encoding="utf-8")

m = pathlib.Path("server/tests/ume/test_migrations.py")
v = m.read_text(encoding="utf-8")
v = v.replace('assert script.get_heads() == ["012"]', 'assert script.get_heads() == ["013"]')
m.write_text(v, encoding="utf-8")
print("ok")