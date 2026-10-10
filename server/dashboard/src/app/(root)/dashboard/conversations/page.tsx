"use client";

import { useState } from "react";
import { format } from "date-fns";
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
import { UME_ENDPOINTS } from "@/utils/api-endpoints";
import { umeGet, type UmePage } from "@/utils/ume-api";
import { useApiQuery } from "@/hooks/use-api-query";
import { UmeConversation, UmeWorkspace } from "@/types/ume";

const NONE = "__none__";

export default function ConversationsPage() {
  const [workspaceId, setWorkspaceId] = useState<string | undefined>(undefined);

  const { data: workspaces } = useApiQuery<UmePage<UmeWorkspace>>(() =>
    umeGet(UME_ENDPOINTS.WORKSPACES, { limit: 50 }),
  );

  const effectiveWorkspaceId = workspaceId ?? workspaces?.items[0]?.id;

  const {
    data: page,
    isLoading,
    error,
    refetch,
  } = useApiQuery<UmePage<UmeConversation>>(
    () =>
      effectiveWorkspaceId
        ? umeGet(UME_ENDPOINTS.CONVERSATIONS, {
            workspace_id: effectiveWorkspaceId,
            limit: 50,
          })
        : Promise.resolve({ items: [], next_cursor: null, has_more: false }),
    { enabled: Boolean(effectiveWorkspaceId) },
  );

  const conversations = page?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-2 p-4">
        <label htmlFor="conversation-workspace" className="text-sm font-medium">
          Workspace
        </label>
        <Select
          value={effectiveWorkspaceId ?? NONE}
          onValueChange={setWorkspaceId}
        >
          <SelectTrigger id="conversation-workspace">
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
      </Card>

      {error && (
        <Card className="p-4 text-sm text-destructive">
          {error}
          <button className="ml-2 underline" onClick={() => refetch()}>
            Retry
          </button>
        </Card>
      )}

      {isLoading ? (
        <TableSkeleton />
      ) : conversations.length === 0 ? (
        <EmptyState
          title="No conversations yet"
          description="Import a conversation to archive its messages."
        />
      ) : (
        <DataTable
          data={conversations}
          getRowKey={(row) => row.id}
          onRowClick={(row) => {
            window.location.href = `/dashboard/conversations/${row.id}`;
          }}
          columns={[
            {
              key: "title",
              label: "Title",
              render: (value) => value ?? "(untitled)",
            },
            {
              key: "source_type",
              label: "Source",
              render: (value) => (
                <Badge variant="outline">{String(value)}</Badge>
              ),
            },
            {
              key: "started_at",
              label: "Started",
              render: (value) =>
                value
                  ? format(new Date(String(value)), "yyyy-MM-dd HH:mm")
                  : "—",
            },
            {
              key: "last_message_at",
              label: "Last message",
              render: (value) =>
                value
                  ? format(new Date(String(value)), "yyyy-MM-dd HH:mm")
                  : "—",
            },
          ]}
        />
      )}
    </div>
  );
}
