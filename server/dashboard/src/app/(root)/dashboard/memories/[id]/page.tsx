"use client";

import { use, useCallback, useState } from "react";
import { format } from "date-fns";
import {
  ArrowLeft,
  Archive,
  RotateCcw,
  Trash2,
  RefreshCw,
  Pencil,
} from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { UmeState } from "@/components/shared/ume-state";
import DeleteConfirmationModal from "@/components/ui/delete-confirmation-modal";
import { useApiQuery } from "@/hooks/use-api-query";
import { UME_ENDPOINTS } from "@/utils/api-endpoints";
import {
  UmeApiError,
  archiveMemory,
  errorLabel,
  forgetMemory,
  getMemory,
  listMemorySources,
  listMemoryVersions,
  restoreMemoryVersion,
  retryMemoryWrite,
  updateMemory,
} from "@/utils/ume-api";
import { allowedActions, memoryStatusNote } from "@/lib/memory-actions";
import { toast } from "@/components/ui/use-toast";
import type { UmeMemory, UmeMemorySource, UmeMemoryVersion } from "@/types/ume";

/**
 * Everything on this page is keyed off the id in the URL and re-checked by the
 * server on every call. There is deliberately no workspace id in the URL and no
 * client-side membership test: hiding a button is not authorisation, and the
 * server answers a foreign or unknown id with the same 404 either way.
 */
export default function MemoryDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const [reloadKey, setReloadKey] = useState(0);
  const bump = useCallback(() => setReloadKey((value) => value + 1), []);

  const {
    data: memory,
    isLoading,
    error,
    refetch,
  } = useApiQuery<UmeMemory>(async () => getMemory(id), {
    refreshKey: reloadKey,
  });

  if (error || isLoading || !memory) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink />
        <UmeState
          isLoading={isLoading}
          error={error}
          isEmpty={false}
          onRetry={refetch}
          title="Could not load this memory"
        >
          <span />
        </UmeState>
      </div>
    );
  }

  const actions = allowedActions(memory);
  const note = memoryStatusNote(memory);

  return (
    <div className="flex flex-col gap-4">
      <BackLink />

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-medium">Memory</h1>
          <p className="font-mono text-xs text-onSurface-default-tertiary">
            {memory.id}
          </p>
        </div>
        <MemoryActions memory={memory} actions={actions} onDone={bump} />
      </div>

      {note && (
        <Alert
          variant={note.tone === "destructive" ? "destructive" : "default"}
        >
          <AlertTitle>{note.label}</AlertTitle>
          <AlertDescription>{note.detail}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Current text</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="whitespace-pre-wrap text-sm">{memory.current_text}</p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-onSurface-default-tertiary">
            <Badge variant="outline">{memory.memory_type}</Badge>
            <Badge variant="outline">{memory.status}</Badge>
            <Badge variant="outline">engine: {memory.engine_state}</Badge>
            <span>
              updated {format(new Date(memory.updated_at), "yyyy-MM-dd HH:mm")}
            </span>
            {memory.tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <SourcesPanel memoryId={id} reloadKey={reloadKey} />
      <VersionsPanel memory={memory} reloadKey={reloadKey} onRestored={bump} />
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/dashboard/memories"
      className="flex w-fit items-center gap-1.5 text-sm text-onSurface-default-secondary"
    >
      <ArrowLeft className="size-4" />
      Back to memories
    </Link>
  );
}

function MemoryActions({
  memory,
  actions,
  onDone,
}: {
  memory: UmeMemory;
  actions: ReturnType<typeof allowedActions>;
  onDone: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(memory.current_text);
  const [reason, setReason] = useState("");
  const [confirmForget, setConfirmForget] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

  const run = useCallback(
    async (name: string, call: () => Promise<unknown>) => {
      setBusy(name);
      try {
        await call();
        toast({ title: `${name} succeeded`, variant: "success" });
        onDone();
      } catch (caught) {
        toast({
          title: `${name} failed`,
          description: errorLabel(caught),
          variant: "destructive",
        });
      } finally {
        setBusy(null);
      }
    },
    [onDone],
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      {actions.edit && !editing && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setDraft(memory.current_text);
            setEditing(true);
          }}
        >
          <Pencil className="size-3.5" />
          Edit
        </Button>
      )}

      {actions.archive && (
        <Button
          variant="outline"
          size="sm"
          disabled={busy !== null}
          onClick={() => setConfirmArchive(true)}
        >
          <Archive className="size-3.5" />
          Archive
        </Button>
      )}

      {actions.retryEngine && (
        <Button
          variant="outline"
          size="sm"
          disabled={busy !== null}
          onClick={() =>
            run("retry", () =>
              retryMemoryWrite(memory.id, [
                { role: "user", content: memory.current_text },
              ]),
            )
          }
        >
          <RefreshCw className="size-3.5" />
          Retry engine write
        </Button>
      )}

      {actions.forget && (
        <Button
          variant="destructive"
          size="sm"
          disabled={busy !== null}
          onClick={() => setConfirmForget(true)}
        >
          <Trash2 className="size-3.5" />
          Forget
        </Button>
      )}

      {editing && (
        <Card className="w-full">
          <CardContent className="flex flex-col gap-3 pt-6">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="memory-draft">Text</Label>
              <Textarea
                id="memory-draft"
                value={draft}
                rows={6}
                onChange={(event) => setDraft(event.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="memory-reason">Change reason (optional)</Label>
              <Input
                id="memory-reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Why is this changing?"
              />
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={busy !== null || draft.trim().length === 0}
                onClick={() =>
                  run("update", async () => {
                    await updateMemory(memory.id, {
                      text: draft,
                      change_reason: reason || undefined,
                    });
                    setEditing(false);
                  })
                }
              >
                Save
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditing(false)}
              >
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <DeleteConfirmationModal
        isOpen={confirmForget}
        onClose={() => setConfirmForget(false)}
        onConfirm={() => {
          setConfirmForget(false);
          void run("forget", () =>
            forgetMemory(memory.id, reason || undefined),
          );
        }}
        title="Forget this memory"
        description="Deletes it from the memory engine and tombstones the record. This cannot be undone from the dashboard."
        itemName={memory.id}
        confirmButtonText="Forget"
      />

      {confirmArchive && (
        <Card className="w-full">
          <CardContent className="flex flex-col gap-3 pt-6">
            <p className="text-sm">
              Archiving hides this memory from retrieval but keeps the engine
              copy and the version history. You can restore it afterwards.
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={busy !== null}
                onClick={() => {
                  setConfirmArchive(false);
                  void run("archive", () =>
                    archiveMemory(memory.id, reason || undefined),
                  );
                }}
              >
                Confirm archive
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfirmArchive(false)}
              >
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function SourcesPanel({
  memoryId,
  reloadKey,
}: {
  memoryId: string;
  reloadKey: number;
}) {
  const { data, isLoading, error, refetch } = useApiQuery<UmeMemorySource[]>(
    () => listMemorySources(memoryId),
    { refreshKey: reloadKey },
  );

  const sources = data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Sources</CardTitle>
      </CardHeader>
      <CardContent>
        <UmeState
          isLoading={isLoading}
          error={error}
          isEmpty={sources.length === 0}
          onRetry={refetch}
          emptyTitle="No sources recorded"
          description="This memory was not derived from a conversation."
          loadingColumns={3}
        >
          <ul className="flex flex-col gap-2">
            {sources.map((source) => (
              <li key={source.id} className="flex flex-col gap-1 text-sm">
                <div className="flex flex-wrap items-center gap-2 text-xs text-onSurface-default-tertiary">
                  <Badge variant="outline">{source.source_type}</Badge>
                  <span>{source.extraction_method}</span>
                  {source.confidence !== null && (
                    <span>confidence {source.confidence.toFixed(2)}</span>
                  )}
                  {source.conversation_id && (
                    <Link
                      href={`/dashboard/conversations/${source.conversation_id}`}
                      className="underline"
                    >
                      open conversation
                    </Link>
                  )}
                </div>
                {source.evidence_excerpt && (
                  <p className="text-onSurface-default-secondary">
                    {source.evidence_excerpt}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </UmeState>
      </CardContent>
    </Card>
  );
}

function VersionsPanel({
  memory,
  reloadKey,
  onRestored,
}: {
  memory: UmeMemory;
  reloadKey: number;
  onRestored: () => void;
}) {
  const canRestore = allowedActions(memory).restoreVersion;
  const [busyVersion, setBusyVersion] = useState<number | null>(null);

  const { data, isLoading, error, refetch } = useApiQuery<UmeMemoryVersion[]>(
    () => listMemoryVersions(memory.id),
    { refreshKey: reloadKey },
  );

  const versions = data ?? [];

  const restore = useCallback(
    async (versionNo: number) => {
      setBusyVersion(versionNo);
      try {
        await restoreMemoryVersion(memory.id, versionNo);
        // Restoring appends a new version rather than rewriting history, so the
        // list has to be re-read — the row we just acted on is no longer last.
        toast({ title: `Restored version ${versionNo}`, variant: "success" });
        refetch();
        onRestored();
      } catch (caught) {
        toast({
          title: "Restore failed",
          description:
            caught instanceof UmeApiError && caught.isNotFound
              ? "That version no longer exists."
              : errorLabel(caught),
          variant: "destructive",
        });
      } finally {
        setBusyVersion(null);
      }
    },
    [memory.id, onRestored, refetch],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Version history</CardTitle>
      </CardHeader>
      <CardContent>
        <UmeState
          isLoading={isLoading}
          error={error}
          isEmpty={versions.length === 0}
          onRetry={refetch}
          emptyTitle="No versions recorded"
          loadingColumns={4}
        >
          <ol className="flex flex-col gap-3">
            {versions.map((version) => {
              const isCurrent = version.text === memory.current_text;
              return (
                <li
                  key={version.id}
                  className="flex flex-col gap-1 border-l pl-3"
                >
                  <div className="flex flex-wrap items-center gap-2 text-xs text-onSurface-default-tertiary">
                    <span className="font-mono">v{version.version_no}</span>
                    <Badge variant="outline">{version.change_type}</Badge>
                    <span>{version.actor_type}</span>
                    <span>
                      {format(new Date(version.created_at), "yyyy-MM-dd HH:mm")}
                    </span>
                    {isCurrent && (
                      <Badge variant="secondary">current text</Badge>
                    )}
                  </div>
                  {version.change_reason && (
                    <p className="text-xs text-onSurface-default-secondary">
                      {version.change_reason}
                    </p>
                  )}
                  <p
                    className={
                      isCurrent
                        ? "whitespace-pre-wrap text-sm"
                        : "whitespace-pre-wrap text-sm text-onSurface-default-secondary"
                    }
                  >
                    {version.text}
                  </p>
                  {canRestore && !isCurrent && (
                    <div>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busyVersion !== null}
                        onClick={() => void restore(version.version_no)}
                      >
                        <RotateCcw className="size-3.5" />
                        Restore this version
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </UmeState>
      </CardContent>
    </Card>
  );
}
