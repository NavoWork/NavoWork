import { useEffect, useState } from 'react';
import { openDB } from 'idb';
import { initialState, storageKey, type WorkbenchState } from './model';

export function readWorkbench(scope: string): WorkbenchState {
  const raw = localStorage.getItem(storageKey(scope));
  if (!raw) return initialState();
  const value = JSON.parse(raw) as WorkbenchState;
  if (
    value.schema !== 1 ||
    !value.current?.costs ||
    !value.current.specs ||
    !Array.isArray(value.history) ||
    !Array.isArray(value.sources) ||
    !Array.isArray(value.activity) ||
    !value.po
  )
    throw new Error('工作区草稿格式无效');
  return value;
}
export function useWorkbench(scope: string) {
  const [initial] = useState(() => {
    try {
      return { state: readWorkbench(scope), error: '' };
    } catch {
      return {
        state: initialState(),
        error: '无法读取本地草稿，当前使用临时演示数据。原存储未覆盖，请先导出当前成果。',
      };
    }
  });
  const [state, setState] = useState(initial.state);
  const [storageError, setStorageError] = useState(initial.error);
  useEffect(() => {
    if (initial.error) return;
    try {
      localStorage.setItem(storageKey(scope), JSON.stringify(state));
      setStorageError('');
      window.dispatchEvent(new Event('trade-workbench:changed'));
    } catch {
      setStorageError('浏览器无法保存草稿。当前修改仍在本页，请在离开前导出。');
    }
  }, [state, scope, initial.error]);
  return { state, setState, storageError };
}
async function fileStore() {
  return openDB('easywork-trade-files', 1, {
    upgrade(db) {
      db.createObjectStore('files');
    },
  });
}
export async function saveSourceFile(scope: string, id: string, file: File) {
  const db = await fileStore();
  await db.put('files', file, `${scope}:${id}`);
}
export async function getSourceFile(scope: string, id: string): Promise<File | undefined> {
  const db = await fileStore();
  return db.get('files', `${scope}:${id}`);
}
