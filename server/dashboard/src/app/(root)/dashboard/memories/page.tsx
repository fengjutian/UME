"use client";

import { useMemo, useState } from "react";
import { format } from "date-fns";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { UmeState } from "@/components/shared/ume-state";
import { UME_ENDPOINTS, UME_LIMITS } from "@/utils/api-endpoints";
import { umeGet, listMemories } from "@/utils/ume-api";
import type { UmePage } from "@/utils/ume-api";
import { useApiQuery } from "@/hooks/use-api-query";
import { useUmePage } from "@/hooks/use-ume-page";
import type { UmeMemory, UmeWorkspace } from "@/types/ume";

/**
 * Reads `/api/ume/v1/memories`, not the legacy engine `/memories`.
 *
 * The two return different identifiers — the engine id and the UME memory
 * record id — so a list built on one cannot link into a detail page built on the
 * other. It also means this page inherits the workspace filter and cursor
 * pagination the legacy route never had, instead of pulling `top_k: 1000` in
 * one shot.
 */
export default function MemoriesPage() {
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [status, setStatus] = useState<string>("");

  const { data: workspacePage, isLoading: loadingWorkspaces } = useApiQuery<
    UmePage<UmeWorkspace>
  >(() => umeGet(UME_ENDPOINTS.WORKSPACES, { limit: 100 }));

  const workspaces = useMemo(() => workspacePage?.items ?? [], [workspacePage]);
  const activeWorkspaceId = workspaceId || workspaces[0]?.id || "";

  const filters = useMemo(
    () => ({ workspace_id: activeWorkspaceId, status }),
    [activeWorkspaceId, status],
  );

  const {
    items: memories,
    isLoading,
    isLoadingMore,
    error,
    hasMore,
    loadMore,
    retry,
  } = useUmePage<UmeMemory>(UME_ENDPOINTS.MEMORIES, {
    filters,
    limit: UME_LIMITS.pageSize,
    enabled: Boolean(activeWorkspaceId),
  });

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold font-fustat">Memories</h1>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-4 pt-6">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="memory-workspace">Workspace</Label>
            <Select value={activeWorkspaceId} onValueChange={setWorkspaceId}>
              <SelectTrigger id="memory-workspace" className="w-72">
                <SelectValue placeholder="Select a workspace" />
              </SelectTrigger>
              <SelectContent>
                {workspaces.map((workspace) => (
                  <SelectItem key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="memory-status">Status</Label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger id="memory-status" className="w-40">
                <SelectValue placeholder="Any" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="archived">Archived</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {!loadingWorkspaces && workspaces.length === 0 ? (
        <UmeState
          isLoading={false}
          error={null}
          isEmpty
          emptyTitle="No workspaces yet"
          description="Create a workspace before listing memories."
        >
          <span />
        </UmeState>
      ) : (
        <UmeState
          isLoading={isLoading || loadingWorkspaces}
          error={error}
          isEmpty={memories.length === 0}
          onRetry={retry}
          emptyTitle="No memories"
          description={
            status
              ? "No memories match this status filter."
              : "This workspace has no memories yet."
          }
          loadingRows={6}
        >
          <Card>
            <CardContent className="pt-6">
              <ul className="flex flex-col divide-y">
                {memories.map((memory) => (
                  <li key={memory.id} className="flex items-start gap-3 py-3">
                    <div className="flex min-w-0 flex-1 flex-col gap-1">
                      <p className="line-clamp-2 text-sm">
                        {memory.current_text}
                      </p>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-onSurface-default-tertiary">
                        <Badge variant="outline">{memory.memory_type}</Badge>
                        <Badge variant="outline">{memory.status}</Badge>
                        {memory.engine_state !== "ready" && (
                          <Badge variant="destructive">
                            engine: {memory.engine_state}
                          </Badge>
                        )}
                        <span>
                          {format(
                            new Date(memory.updated_at),
                            "MMM d, yyyy HH:mm",
                          )}
                        </span>
                      </div>
                    </div>
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/dashboard/memories/${memory.id}`}>
                        Open
                        <ExternalLink className="size-3.5" />
                      </Link>
                    </Button>
                  </li>
                ))}
              </ul>

              {hasMore && (
                <div className="flex justify-center pt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isLoadingMore}
                    onClick={loadMore}
                  >
                    {isLoadingMore ? "Loading…" : "Load more"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </UmeState>
      )}
    </div>
  );
}
