"use client";

import { AlertCircle, Lock, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TableSkeleton } from "@/components/shared/table-skeleton";
import { UmeApiError } from "@/utils/ume-api";

/**
 * The loading / empty / error / forbidden states every V1 page needs.
 *
 * A page picks exactly one of these rather than hand-rolling a spinner: the
 * four states are easy to get subtly wrong, and "looks like no data yet" for a
 * failed request is the specific bug this exists to prevent.
 *
 * Not-found and forbidden deliberately share one rendering. The server answers
 * a cross-workspace read with the same 404 it uses for a resource that does not
 * exist, so there is nothing truthful to distinguish them with.
 */

interface StateProps {
  title?: string;
  description?: string;
}

export function UmeLoading({
  rows = 5,
  columns = 5,
}: {
  rows?: number;
  columns?: number;
}) {
  return <TableSkeleton rows={rows} columns={columns} />;
}

export function UmeEmpty({ title = "No results", description }: StateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 py-12 text-center">
      <p className="text-sm font-medium text-onSurface-default-primary">
        {title}
      </p>
      {description && (
        <p className="max-w-sm text-xs text-onSurface-default-tertiary">
          {description}
        </p>
      )}
    </div>
  );
}

export function UmeErrorState({
  error,
  onRetry,
  title = "Something went wrong",
}: StateProps & { error: unknown; onRetry?: () => void }) {
  const notFound = error instanceof UmeApiError && error.isNotFound;
  const Icon = notFound ? Lock : AlertCircle;

  return (
    <Card className="border-memBorder-primary">
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
        <Icon className="size-5 text-onSurface-default-tertiary" aria-hidden />
        <div className="space-y-1">
          <p className="text-sm font-medium text-onSurface-default-primary">
            {notFound ? "Not found" : title}
          </p>
          <p className="max-w-md text-xs text-onSurface-default-tertiary">
            {error instanceof UmeApiError ? error.message : "Request failed"}
          </p>
        </div>
        {onRetry && !notFound && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="size-3.5" aria-hidden />
            Retry
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export interface UmeStateProps extends StateProps {
  isLoading: boolean;
  error?: unknown;
  isEmpty: boolean;
  onRetry?: () => void;
  loadingRows?: number;
  loadingColumns?: number;
  emptyTitle?: string;
  children: React.ReactNode;
}

/**
 * Renders exactly one of loading / error / empty / children.
 *
 * `error` is checked before `isEmpty` on purpose: an empty list and a failed
 * request both have zero items, and showing "no results" for a failed request
 * hides the only signal the user can act on.
 */
export function UmeState({
  isLoading,
  error,
  isEmpty,
  onRetry,
  loadingRows,
  loadingColumns,
  emptyTitle,
  title,
  description,
  children,
}: UmeStateProps) {
  if (isLoading) {
    return <UmeLoading rows={loadingRows} columns={loadingColumns} />;
  }
  if (error) {
    return (
      <UmeErrorState
        error={error}
        onRetry={onRetry}
        title={title}
        description={description}
      />
    );
  }
  if (isEmpty) {
    return (
      <UmeEmpty
        title={emptyTitle ?? title ?? "No results"}
        description={description}
      />
    );
  }
  return <>{children}</>;
}
