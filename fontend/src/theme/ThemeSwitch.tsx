import { useId, useSyncExternalStore } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';

type ThemePreference = 'system' | 'light' | 'dark';
interface ThemeSnapshot {
  preference: ThemePreference;
  resolved: 'light' | 'dark';
  storageAvailable: boolean;
}
declare global {
  interface Window {
    navoworkTheme: {
      getSnapshot: () => ThemeSnapshot;
      subscribe: (listener: () => void) => () => void;
      setPreference: (value: ThemePreference) => void;
    };
  }
}

export function ThemeSwitch() {
  const id = useId();
  const store = window.navoworkTheme;
  const theme = useSyncExternalStore(store.subscribe, store.getSnapshot);
  const Icon = theme.preference === 'system' ? Monitor : theme.preference === 'dark' ? Moon : Sun;
  return (
    <div className="theme-control">
      <label className="theme-switch" htmlFor={id}>
        <Icon size={15} aria-hidden="true" />
        <span className="sr-only">外观主题</span>
        <select
          id={id}
          value={theme.preference}
          onChange={(event) => store.setPreference(event.target.value as ThemePreference)}
        >
          <option value="system">跟随系统</option>
          <option value="light">浅色模式</option>
          <option value="dark">深色模式</option>
        </select>
      </label>
      {!theme.storageAvailable && (
        <small className="theme-storage-note" role="status">
          主题仅在当前页面生效
        </small>
      )}
    </div>
  );
}
