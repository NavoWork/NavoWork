import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
const fetchMock = vi.fn();
const dispatchEvent = vi.fn();
beforeEach(() => {
  vi.resetModules();
  vi.stubEnv('VITE_API_MODE', 'real');
  vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test/api/v1');
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('window', { dispatchEvent });
  fetchMock.mockReset();
  dispatchEvent.mockReset();
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
describe('real API adapter', () => {
  it('never falls back to fixture data for a failed network request', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const { api, mode } = await import('./index');
    expect(mode).toBe('real');
    await expect(api.get('/me')).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: 0 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('preserves server error codes and request IDs on 5xx without retry', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: 'TOOL_UNAVAILABLE',
            message: '资源服务不可用',
            details: { module: 'resources' },
          },
          requestId: 'req_failed',
        }),
        { status: 503 },
      ),
    );
    const { api } = await import('./index');
    await expect(api.get('/workspaces/ws_1/inquiries')).rejects.toMatchObject({
      code: 'TOOL_UNAVAILABLE',
      status: 503,
      requestId: 'req_failed',
      details: { module: 'resources' },
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it('notifies session expiry and does not call a rejected write successful', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: 'SESSION_EXPIRED', message: '登录已过期' },
          requestId: 'req_expired',
        }),
        { status: 401 },
      ),
    );
    const { api } = await import('./index');
    await expect(api.put('/draft', { text: 'unsaved' })).rejects.toMatchObject({
      code: 'SESSION_EXPIRED',
      status: 401,
    });
    expect(dispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'easywork:session-expired' }),
    );
  });
  it('preserves cancellation as AbortError for callers to discard stale reads', async () => {
    fetchMock.mockRejectedValue(new DOMException('Aborted', 'AbortError'));
    const { api } = await import('./index');
    const controller = new AbortController();
    controller.abort();
    await expect(api.get('/me', controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  });
  it('normalizes HTML proxy errors rather than exposing raw markup', async () => {
    fetchMock.mockResolvedValue(
      new Response('<html><body>502 Bad gateway</body></html>', {
        status: 502,
        headers: { 'Content-Type': 'text/html', 'X-Request-Id': 'req_gateway' },
      }),
    );
    const { api } = await import('./index');
    await expect(api.get('/me')).rejects.toMatchObject({
      code: 'HTTP_ERROR',
      status: 502,
      requestId: 'req_gateway',
    });
  });
  it('dispatches session expiry for a non-JSON 401 and preserves its request header', async () => {
    fetchMock.mockResolvedValue(
      new Response('Unauthorized', { status: 401, headers: { 'Request-Id': 'req_plain401' } }),
    );
    const { api } = await import('./index');
    await expect(api.put('/draft', { text: 'unsaved' })).rejects.toMatchObject({
      code: 'SESSION_EXPIRED',
      status: 401,
      requestId: 'req_plain401',
    });
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    expect(dispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'easywork:session-expired' }),
    );
  });
  it('rejects malformed successful JSON as an invalid response rather than a network failure', async () => {
    fetchMock.mockResolvedValue(
      new Response('<html>Unexpected login screen</html>', {
        status: 200,
        headers: { 'X-Request-Id': 'req_malformed' },
      }),
    );
    const { api } = await import('./index');
    await expect(api.get('/me')).rejects.toMatchObject({
      code: 'INVALID_RESPONSE',
      status: 200,
      requestId: 'req_malformed',
    });
  });
  it('uses credentialed requests and preserves body/idempotency contract', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ id: 'inq_real', requestId: 'req_success' }), { status: 201 }),
    );
    const { api } = await import('./index');
    expect(
      await api.post('/workspaces/ws_1/inquiries', { title: '真实询盘' }, 'stable-key'),
    ).toEqual({ id: 'inq_real', requestId: 'req_success' });
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/workspaces/ws_1/inquiries',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: '{"title":"真实询盘"}',
        headers: expect.objectContaining({
          'Idempotency-Key': 'stable-key',
          'Content-Type': 'application/json',
        }),
      }),
    );
  });
  it('authorizes downloads and rejects failed downloads as API errors', async () => {
    fetchMock.mockResolvedValue(new Response('denied', { status: 403 }));
    const { api } = await import('./index');
    await expect(
      api.download('/workspaces/ws_1/assets/a/versions/1/download'),
    ).rejects.toMatchObject({ code: 'DOWNLOAD_ERROR', status: 403 });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ credentials: 'include' }),
    );
  });
});
