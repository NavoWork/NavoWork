import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../api';
import { CanvasPersistence } from './canvas-persistence';
import { initialCanvas } from './inquiry-canvas-model';

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });
describe('server canvas persistence', () => {
  it('serializes saves and retains edits made while the first request is running', async () => {
    vi.useFakeTimers();
    let resolve!: (value: { editVersion: number }) => void;
    const put = vi.spyOn(api, 'put').mockImplementationOnce(() => new Promise(done => { resolve = done as typeof resolve; }))
      .mockResolvedValueOnce({ editVersion: 2 });
    const writer = new CanvasPersistence('/canvas');
    writer.initialize(0, initialCanvas());
    writer.enqueue({ ...initialCanvas(), active: 'one' });
    const first = writer.flush();
    writer.enqueue({ ...initialCanvas(), active: 'two' });
    expect(put).toHaveBeenCalledTimes(1);
    resolve({ editVersion: 1 });
    await first;
    expect(put).toHaveBeenNthCalledWith(2, '/canvas', expect.objectContaining({ editVersion: 1, state: expect.objectContaining({ active: 'two' }) }));
    expect(writer.pending).toBeNull();
    expect(writer.version).toBe(2);
  });
  it('preserves a rejected snapshot and never overwrites a conflicting server version on retry', async () => {
    vi.useFakeTimers();
    const put = vi.spyOn(api, 'put').mockRejectedValue(new ApiError('CANVAS_CONFLICT', 'conflict', 409));
    const writer = new CanvasPersistence('/canvas');
    writer.initialize(3, initialCanvas());
    const state = { ...initialCanvas(), active: 'my-unsaved-note' };
    writer.enqueue(state); await writer.flush(); writer.retry();
    expect(writer.pending).toEqual(state);
    expect(writer.version).toBe(3);
    expect(put).toHaveBeenCalledTimes(1);
  });
});
