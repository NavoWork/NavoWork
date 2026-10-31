import { ApiError } from './error';
import { mockRequest } from './mock';
export { ApiError } from './error';
export { setMockFault } from './mock';
export type * from './types';
export const mode: 'mock' | 'real' = import.meta.env.VITE_API_MODE === 'real' ? 'real' : 'mock';
const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
export interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  idempotencyKey?: string;
}
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (mode === 'mock') return mockRequest(path, options) as Promise<T>;
  const headers: Record<string, string> = { Accept: 'application/json' };
  const isForm = options.body instanceof FormData;
  if (options.body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
  if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey;
  const timeout = new AbortController();
  const timer = setTimeout(
    () => timeout.abort(new DOMException('请求超时，请重试', 'TimeoutError')),
    30000,
  );
  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, {
      method: options.method || 'GET',
      headers,
      credentials: 'include',
      body:
        options.body === undefined
          ? undefined
          : isForm
            ? (options.body as FormData)
            : JSON.stringify(options.body),
      signal: options.signal ? AbortSignal.any([options.signal, timeout.signal]) : timeout.signal,
    });
    const headerRequestId =
      response.headers.get('x-request-id') || response.headers.get('request-id') || undefined;
    if (response.status === 401) window.dispatchEvent(new CustomEvent('easywork:session-expired'));
    let json;
    try {
      json = response.status === 204 ? {} : await response.json();
    } catch {
      if (response.ok)
        throw new ApiError(
          'INVALID_RESPONSE',
          '服务返回了无法解析的内容，请稍后重试。',
          response.status,
          headerRequestId,
        );
      json = {};
    }
    if (!response.ok) {
      const error = new ApiError(
        json?.error?.code || (response.status === 401 ? 'SESSION_EXPIRED' : 'HTTP_ERROR'),
        json?.error?.message ||
          (response.status === 401 ? '会话已过期，请重新登录' : '请求失败，请稍后重试'),
        response.status,
        json?.requestId || headerRequestId,
        json?.error?.details,
        json?.error?.fieldErrors,
      );
      throw error;
    }
    return json as T;
  } catch (error) {
    if (error instanceof ApiError || (error instanceof DOMException && error.name === 'AbortError'))
      throw error;
    throw new ApiError('NETWORK_ERROR', '连接服务失败，请检查网络后重试。输入仍保留。', 0);
  } finally {
    clearTimeout(timer);
  }
}
export const api = {
  request,
  download: async (path: string): Promise<Blob> => {
    if (mode === 'mock') return (await mockRequest(path)) as Blob;
    const response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, {
      credentials: 'include',
    });
    if (!response.ok) {
      let json;
      try {
        json = await response.json();
      } catch {
        json = {};
      }
      if (response.status === 401)
        window.dispatchEvent(new CustomEvent('easywork:session-expired'));
      throw new ApiError(
        json?.error?.code || 'DOWNLOAD_ERROR',
        json?.error?.message || '下载失败',
        response.status,
        json?.requestId ||
          response.headers.get('x-request-id') ||
          response.headers.get('request-id') ||
          undefined,
      );
    }
    return response.blob();
  },
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown, idempotencyKey: string = crypto.randomUUID()) =>
    request<T>(path, { method: 'POST', body, idempotencyKey }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
