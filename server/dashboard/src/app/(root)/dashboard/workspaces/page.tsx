"use client";

import { useState } from "react";
import { format } from "date-fns";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/shared/data-table";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { EmptyState } from "@/components/self-hosted/empty-state";
import { toast } from "@/components/ui/use-toast";
import { UME_ENDPOINTS } from "@/utils/api-endpoints";
import { umeGet, umePost, UmeApiError, type UmePage } from "@/utils/ume-api";
import { useApiQuery } from "@/hooks/use-api-query";
import { UmeWorkspace } from "@/types/ume";

export default function WorkspacesPage() {
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  const {
    data: page,
    isLoading,
    error,
    refetch,
  } = useApiQuery<UmePage<UmeWorkspace>>(() => umeGet(UME_ENDPOINTS.WORKSPACES, { limit: 50 }));

  const workspaces = page?.items ?? [];

  const onCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      toast({ title: "Name is required", variant: "destructive" });
      return;
    }
    setCreating(true);
    try {
      await umePost<UmeWorkspace>(UME_ENDPOINTS.WORKSPACES, { name: trimmed });
      setName("");
      toast({ title: "Workspace created" });
      await refetch();
    } catch (err) {
      toast({
        title: "Could not create the workspace",
        description: err instanceof UmeApiError ? err.message : "Request failed",
        variant: "destructive",
      });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <Label htmlFor="workspace-name">New workspace</Label>
        <div className="mt-2 flex items-center gap-2">
          <Input
            id="workspace-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Workspace name"
            maxLength={255}
          />
          <Button onClick={onCreate} disabled={creating}>
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
      ) : workspaces.length === 0 ? (
        <EmptyState
          title="No workspaces yet"
          description="Create one to scope memories, projects and conversations."
        />
      ) : (
        <DataTable
          data={workspaces}
          getRowKey={(row) => row.id}
          columns={[
            { key: "name", label: "Name" },
            {
              key: "status",
              label: "Status",
              render: (value) => <Badge variant="outline">{String(value)}</Badge>,
            },
            {
              key: "description",
              label: "Description",
              render: (value) => (value === null ? "—" : String(value)),
            },
            {
              key: "created_at",
              label: "Created",
              render: (value) => format(new Date(String(value)), "yyyy-MM-dd HH:mm"),
            },
          ]}
        />
      )}
    </div>
  );
}