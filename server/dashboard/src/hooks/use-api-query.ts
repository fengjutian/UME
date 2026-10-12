import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "@/components/ui/use-toast";
import { getErrorMessage } from "@/lib/error-message";

interface UseApiQueryOptions<T> {
  enabled?: boolean;
  errorToast?: string;
  initialData?: T;
  /**
   * Bump to re-run the fetcher. Additive so existing call sites are unaffected:
   * a page that mutates something and needs the list re-read increments this
   * instead of remounting the component (which loses scroll and selection).
   */
  refreshKey?: number;
}

interface UseApiQueryResult<T> {
  data: T | undefined;
  isLoading: boolean;
  error: string;
  refetch: () => Promise<void>;
}

export function useApiQuery<T>(
  fetcher: () => Promise<T>,
  options: UseApiQueryOptions<T> = {},
): UseApiQueryResult<T> {
  const { enabled = true, errorToast, initialData, refreshKey } = options;

  const [data, setData] = useState<T | undefined>(initialData);
  const [isLoading, setIsLoading] = useState(enabled);
  const [error, setError] = useState("");

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      setData(await fetcherRef.current());
    } catch (err) {
      const message = getErrorMessage(err, errorToast || "Request failed");
      setError(message);
      if (errorToast) {
        toast({
          title: errorToast,
          description: message,
          variant: "destructive",
        });
      }
    } finally {
      setIsLoading(false);
    }
  }, [errorToast]);

  useEffect(() => {
    if (enabled) void run();
  }, [enabled, refreshKey, run]);

  return { data, isLoading, error, refetch: run };
}
