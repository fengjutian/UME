"use client";

import { useMemo, useState } from "react";
import { format } from "date-fns";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DataTable } from "@/components/shared/data-table";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { EmptyState } from "@/components/self-hosted/empty-state";
import { toast } from "@/components/ui/use-toast";
import { UME_ENDPOINTS } from "@/utils/api-endpoints";
import { umeGet, umePost, UmeApiError, type UmePage } from "@/utils/ume-api";
import { useApiQuery } from "@/hooks/use-api-query";
import { UmeProject, UmeWorkspace } from "@/types/ume";

const NONE = "__none__";

export default function ProjectsPage() {
  const [workspaceId, setWorkspaceId] = useState<string | undefined>(undefined);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  const { data: workspaces } = useApiQuery<UmePage<UmeWorkspace>>(
    () => umeGet(UME_ENDPOINTS.WORKSPACES, { limit: 50 }),
  );

  // Default to the first workspace once the list resolves, rather than making
  // the operator pick before the page is usable.
  const effectiveWorkspaceId = workspaceId ?? workspaces?.items[0]?.id;

  const {
    data: page,
    isLoading,
    error,
    refetch,
  } = useApiQuery<UmePage<UmeProject>>(
    () =>
      effectiveWorkspaceId
        ? umeGet(UME_ENDPOINTS.WORKSPACE_PROJECTS(effectiveWorkspaceId), { limit: 50 })
        : Promise.resolve({ items: [], next_cursor: null, has_more: false }),
    { enabled: Boolean(effectiveWorkspaceId) },
  );

  const projects = useMemo(() => page?.items ?? [], [page]);

  const onCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed || !effectiveWorkspaceId) {
      toast({ title: "Workspace and name are required", variant: "destructive" });
      return;
    }
    setCreating(true);
    try {
      await umePost<UmeProject>(UME_ENDPOINTS.WORKSPACE_PROJECTS(effectiveWorkspaceId), {
        name: trimmed,
      });
      setName("");
      toast({ title: "Project created" });
      await refetch();
    } catch (err) {
      toast({
        title: "Could not create the project",
        description: err instanceof UmeApiError ? err.message : "Request failed",
        variant: "destructive",
      });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="workspace-select">Workspace</Label>
          <Select value={effectiveWorkspaceId ?? NONE} onValueChange={setWorkspaceId}>
            <SelectTrigger id="workspace-select">
              <SelectValue placeholder="Select a workspace" />
            </SelectTrigger>
            <SelectContent>
              {(workspaces?.items ?? []).map((workspace) => (
                <SelectItem key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-end gap-2">
          <div className="flex-1">
            <Label htmlFor="project-name">New project</Label>
            <Input
              id="project-name"
              className="mt-2"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Project name"
              maxLength={255}
            />
          </div>
          <Button onClick={onCreate} disabled={creating || !effectiveWorkspaceId}>
            <Plus className="size-4" />
            Create
          </Button>
        </div>
      </Card>

      {error && (
        <Card className="p-4 text-sm text-destructive">
          {error}
          <Button variant="link" className="ml-2 px-0" onClick={() => refetch()}>
            Retry
          </Button>
        </Card>
      )}

      {isLoading ? (
        <TableSkeleton />
      ) : projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Projects group memories and conversations inside a workspace."
        />
      ) : (
        <DataTable
          data={projects}
          getRowKey={(row) => row.id}
          columns={[
            { key: "name", label: "Name" },
            {
              key: "status",
              label: "Status",
              render: (value) => <Badge variant="outline">{String(value)}</Badge>,
            },
            {
              key: "tags",
              label: "Tags",
              render: (value) => (value as string[]).join(", ") || "—",
            },
            {
              key: "last_activity_at",
              label: "Last activity",
              render: (value) =>
                value ? format(new Date(String(value)), "yyyy-MM-dd HH:mm") : "—",
            },
          ]}
        />
      )}
    </div>
  );
}