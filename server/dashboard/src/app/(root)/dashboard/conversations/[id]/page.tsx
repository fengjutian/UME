"use client";

import { use } from "react";
import { format } from "date-fns";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { EmptyState } from "@/components/self-hosted/empty-state";
import { UME_ENDPOINTS } from "@/utils/api-endpoints";
import { umeGet, type UmePage } from "@/utils/ume-api";
import { useApiQuery } from "@/hooks/use-api-query";
import { UmeConversation, UmeMessage } from "@/types/ume";

export default function ConversationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const { data: conversation, error: conversationError } = useApiQuery<UmeConversation>(() =>
    umeGet(UME_ENDPOINTS.CONVERSATION(id)),
  );

  const {
    data: page,
    isLoading,
    error,
    refetch,
  } = useApiQuery<UmePage<UmeMessage>>(() =>
    umeGet(UME_ENDPOINTS.MESSAGES(id), { limit: 200, order: "asc" }),
  );

  const messages = page?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <Link
        href="/dashboard/conversations"
        className="flex w-fit items-center gap-1.5 text-sm text-onSurface-default-secondary"
      >
        <ArrowLeft className="size-4" />
        Back to conversations
      </Link>

      {conversationError && (
        <Card className="p-4 text-sm text-destructive">{conversationError}</Card>
      )}

      {conversation && (
        <Card className="flex flex-col gap-2 p-4">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-medium">{conversation.title ?? "(untitled)"}</h2>
            <Badge variant="outline">{conversation.status}</Badge>
            <Badge variant="outline">{conversation.source_type}</Badge>
          </div>
          <div className="flex flex-wrap gap-4 text-sm text-onSurface-default-secondary">
            <span>Workspace: {conversation.workspace_id}</span>
            {conversation.project_id && <span>Project: {conversation.project_id}</span>}
            <span>
              Last message:{" "}
              {conversation.last_message_at
                ? format(new Date(conversation.last_message_at), "yyyy-MM-dd HH:mm:ss")
                : "—"}
            </span>
          </div>
        </Card>
      )}

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
      ) : messages.length === 0 ? (
        <EmptyState title="No messages" description="This conversation has no archived messages." />
      ) : (
        <div className="flex flex-col gap-2">
          {messages.map((message) => (
            <Card key={message.id} className="flex flex-col gap-1 p-3">
              <div className="flex items-center gap-2 text-xs text-onSurface-default-secondary">
                <Badge variant="outline">{message.role}</Badge>
                {message.sensitivity !== "normal" && (
                  <Badge variant="outline">{message.sensitivity}</Badge>
                )}
                <span>{format(new Date(message.message_at), "yyyy-MM-dd HH:mm:ss")}</span>
                {message.external_message_id && (
                  <span className="font-mono">{message.external_message_id}</span>
                )}
              </div>
              <p className="whitespace-pre-wrap text-sm">
                {message.content_text ?? "(no inline text — content is referenced externally)"}
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}