import { AxiosError } from "axios";
import { api } from "@/utils/api";

/** Envelope every `/api/ume/v1` response is wrapped in. */
export interface UmeEnvelope<T> {
  data: T;
  request_id: string;
}

export interface UmeErrorEnvelope {
  error: {
    code: string;
    message: string;
    details: unknown;
  };
  request_id: string;
}

export interface UmePage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

/** A UME failure, carrying the server's machine code. */
export class UmeApiError extends Error {
  readonly code: string;
  readonly details: unknown;
  readonly status: number;
  readonly requestId: string | undefined;

  constructor(
    code: string,
    message: string,
    status: number,
    details: unknown,
    requestId?: string,
  ) {
    super(message);
    this.name = "UmeApiError";
    this.code = code;
    this.details = details;
    this.status = status;
    this.requestId = requestId;
  }
}

/**
 * Unwrap a success envelope.
 *
 * Throws `UmeApiError` when the body is an error envelope rather than returning
 * `undefined` — a failed request that resolves to `undefined` is how a page
 * ends up rendering a convincing "no data yet" instead of showing the error.
 */
export function unwrap<T>(body: unknown): T {
  if (body && typeof body === "object" && "error" in body) {
    const envelope = body as UmeErrorEnvelope;
    throw new UmeApiError(
      envelope.error.code,
      envelope.error.message,
      0,
      envelope.error.details,
      envelope.request_id,
    );
  }
  return (body as UmeEnvelope<T>).data;
}

function toUmeError(error: unknown): UmeApiError {
  if (error instanceof UmeApiError) return error;
  const axiosError = error as AxiosError<unknown>;
  const body = axiosError?.response?.data;
  if (body && typeof body === "object" && "error" in body) {
    const envelope = body as UmeErrorEnvelope;
    return new UmeApiError(
      envelope.error.code,
      envelope.error.message,
      axiosError.response?.status ?? 0,
      envelope.error.details,
      envelope.request_id,
    );
  }
  return new UmeApiError(
    "REQUEST_FAILED",
    error instanceof Error ? error.message : "Request failed",
    axiosError?.response?.status ?? 0,
    null,
  );
}

export const umeGet = async <T>(url: string, params?: Record<string, unknown>) => {
  try {
    return unwrap<T>((await api.get(url, { params })).data);
  } catch (error) {
    throw toUmeError(error);
  }
};

export const umePost = async <T>(url: string, body?: unknown, headers?: Record<string, string>) => {
  try {
    return unwrap<T>((await api.post(url, body, { headers })).data);
  } catch (error) {
    throw toUmeError(error);
  }
};

export const umePatch = async <T>(url: string, body: unknown) => {
  try {
    return unwrap<T>((await api.patch(url, body)).data);
  } catch (error) {
    throw toUmeError(error);
  }
};

export const umeDelete = async <T>(url: string) => {
  try {
    return unwrap<T>((await api.delete(url)).data);
  } catch (error) {
    throw toUmeError(error);
  }
};

export const errorLabel = (error: unknown): string => {
  if (error instanceof UmeApiError) return error.message;
  return error instanceof Error ? error.message : "Request failed";
};