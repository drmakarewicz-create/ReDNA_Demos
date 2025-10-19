import { type ClassValue, clsx } from 'clsx';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export interface FetchRetryOptions {
  retries?: number;
  retryDelayMs?: number;
  timeoutMs?: number;
  retryOnStatuses?: number[];
}

export async function fetchWithRetry(
  input: RequestInfo | URL,
  init?: RequestInit,
  options?: FetchRetryOptions,
): Promise<Response> {
  const { retries = 2, retryDelayMs = 500, timeoutMs = 10000, retryOnStatuses = [502, 503, 504] } = options ?? {};
  let attempt = 0;

  while (true) {
    let controller: AbortController | null = null;
    let timer: NodeJS.Timeout | undefined;
    let requestInit = init;

    if (!init?.signal && timeoutMs) {
      controller = new AbortController();
      timer = setTimeout(() => controller?.abort(), timeoutMs);
      requestInit = { ...init, signal: controller.signal };
    }

    try {
      const response = await fetch(input, requestInit);
      if (!response.ok) {
        const shouldRetryStatus =
          retryOnStatuses.includes(response.status) || (response.status >= 500 && response.status < 600);
        if (shouldRetryStatus && attempt < retries) {
          attempt += 1;
          await delay(retryDelayMs * attempt);
          continue;
        }
      }
      return response;
    } catch (error) {
      const isAbortError = error instanceof DOMException && error.name === 'AbortError';
      const isNetworkError = error instanceof TypeError || isAbortError;
      if (!isNetworkError || attempt >= retries) {
        throw error;
      }
      attempt += 1;
      await delay(retryDelayMs * attempt);
    } finally {
      if (timer) {
        clearTimeout(timer);
      }
    }
  }
}

async function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
