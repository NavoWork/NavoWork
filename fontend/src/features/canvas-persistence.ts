import { api, ApiError } from '../api';
import type { CanvasState } from './inquiry-canvas-model';

// One ordered writer per mounted canvas. A response can only acknowledge the
// snapshot it sent; edits made during a request stay in the queue.
export class CanvasPersistence {
  version = 0;
  saved = '';
  pending: CanvasState | null = null;
  saving = false;
  error: unknown;
  timer?: ReturnType<typeof setTimeout>;
  onStatus: (status: string) => void = () => {};
  onSaved: (state: CanvasState) => void = () => {};
  constructor(readonly path: string) {}
  initialize(version: number, state: CanvasState) {
    this.version = version;
    this.saved = JSON.stringify(state);
  }
  enqueue(state: CanvasState) {
    if (JSON.stringify(state) === this.saved && !this.saving) return;
    this.pending = state;
    if (this.error) return;
    this.onStatus('有修改待保存');
    clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.flush(), 250);
  }
  async flush() {
    clearTimeout(this.timer);
    if (this.saving || this.error || !this.pending) return;
    this.saving = true;
    try {
      while (this.pending) {
        const state: CanvasState = this.pending;
        const serialized = JSON.stringify(state);
        if (serialized === this.saved) { this.pending = null; break; }
        this.onStatus('正在保存…');
        const result = await api.put<{ editVersion: number }>(this.path, {
          editVersion: this.version, state,
        });
        this.version = result.editVersion;
        this.saved = serialized;
        if (this.pending === state) this.pending = null;
        this.onSaved(state);
      }
      this.onStatus('已保存到服务端');
    } catch (error) {
      this.error = error;
      this.onStatus(error instanceof ApiError && error.code === 'CANVAS_CONFLICT'
        ? '画板有版本冲突。请下载当前草稿，再刷新合并。'
        : '保存失败，修改仍在当前页面。请重试或下载草稿。');
    } finally { this.saving = false; }
  }
  retry() {
    if (this.error instanceof ApiError && this.error.code === 'CANVAS_CONFLICT') return;
    this.error = undefined;
    void this.flush();
  }
}
