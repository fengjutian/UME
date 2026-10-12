import { useCallback, useEffect, useRef, useState } from "react";
import { query as buildQuery } from "@/utils/api-endpoints";
import {
  UmeApiError,
  UmePage,
  UmeRequestOptions,
  umePage,
} from "@/utils/ume-api";

export interface UseUmePageOptions {
  /** Re-fetches when any value here changes identity (primives only). */
  filters: Record<string, string | number | boolean | null | undefined>;
  limit?: number;
  enabled?: boolean;
}

/**
 * Cursor pagination state for the routes that actually return
 * `{ items, next_cursor, has_more }`.
 *
 * Accumulated pages are kept in one list rather than swapped per page so
 * "load more" does not drop what is already on screen. A filter change clears
 * both the accumulator and the cursor — otherwise the next cursor belongs to
 * the old filter and the second page silently comes from the wrong query.
 *
 * Not for `/timeline`: it returns a plain array with no cursor.
 */
export interface UseUmePageResult<T> {
  items: T[];
  isLoading: boolean;
  isLoadingMore: boolean;
  error: UmeApiError | null;
  hasMore: boolean;
  loadMore: () => void;
  retry: () => void;
}

export function useUmePage<T>(
  url: string,
  { filters, limit, enabled = true }: UseUmePageOptions,
  options: UmeRequestOptions = {},
): UseUmePageResult<T> {
  const [items, setItems] = useState<T[]>([]);
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(enabled);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<UmeApiError | null>(null);
  const [attempt, setAttempt] = useState(0);

  const controllerRef = useRef<AbortController | null>(null);
  const filterKey = JSON.stringify(filters);

  const run = useCallback(
    async (nextCursor: string | undefined, append: boolean) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      if (append) setIsLoadingMore(true);
      else setIsLoading(true);
      setError(null);

      try {
        const page: UmePage<T> = await umePage<T>(
          url,
          buildQuery({ ...filters, limit, cursor: nextCursor }),
          { signal: controller.signal, headers: options.headers },
        );
        // An aborted request is not a failure: the cleanup already reset state.
        if (controller.signal.aborted) return;
        setItems((previous) =>
          append ? [...previous, ...page.items] : page.items,
        );
        setCursor(page.next_cursor ?? undefined);
        setHasMore(page.has_more);
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof UmeApiError
            ? caught
            : new UmeApiError("REQUEST_FAILED", "Request failed", 0, null),
        );
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
          setIsLoadingMore(false);
        }
      }
    },
    // `filterKey` stands in for the filters object, which is a new reference on
    // every render; depending on `filters` itself would refetch forever.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [url, filterKey, limit, enabled, attempt],
  );

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }
    setItems([]);
    setCursor(undefined);
    setHasMore(false);
    void run(undefined, false);
    return () => controllerRef.current?.abort();
  }, [enabled, run]);

  const loadMore = useCallback(() => {
    if (!cursor || isLoadingMore) return;
    void run(cursor, true);
  }, [cursor, isLoadingMore, run]);

  const retry = useCallback(() => {
    setCursor(undefined);
    setItems([]);
    setAttempt((value) => value + 1);
  }, []);

  return { items, isLoading, isLoadingMore, error, hasMore, loadMore, retry };
}
