import { derived, writable } from 'svelte/store';

const env = import.meta.env;
const STORAGE_KEY = 'genesis-ui-settings';

const defaultBackendBaseUrl = env.VITE_GENESISDB_HTTP_URL ?? 'http://localhost:8000';
const defaultSqlApiBaseUrl =
  env.VITE_GENESISDB_SQL_API_URL ?? env.VITE_GENESISDB_HTTP_URL ?? defaultBackendBaseUrl;

const defaultSettings = {
  backendBaseUrl: defaultBackendBaseUrl,
  sqlApiBaseUrl: defaultSqlApiBaseUrl
};

const useMockData = env.VITE_GENESISDB_USE_MOCK_DATA
  ? env.VITE_GENESISDB_USE_MOCK_DATA === 'true'
  : false;
const envWebsocketUrl = env.VITE_GENESISDB_WS_URL;
const envLogsWebsocketUrl = env.VITE_GENESISDB_LOGS_WS_URL;

const loadStoredSettings = () => {
  if (typeof localStorage === 'undefined') {
    return {};
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    return {
      backendBaseUrl: parsed.backendBaseUrl ?? defaultSettings.backendBaseUrl,
      sqlApiBaseUrl: parsed.sqlApiBaseUrl ?? defaultSettings.sqlApiBaseUrl
    };
  } catch (error) {
    console.warn('Failed to load settings from localStorage:', error);
    return {};
  }
};

const deriveWebsocketUrl = (backendBaseUrl) => {
  try {
    const url = new URL(backendBaseUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = url.pathname.replace(/\/$/, '');
    url.pathname = `${url.pathname}/ws`;
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch (error) {
    console.warn('Failed to derive WebSocket URL:', error);
    return envWebsocketUrl ?? 'ws://localhost:8000/ws';
  }
};

const deriveLogsWebsocketUrl = (backendBaseUrl) => {
  try {
    const url = new URL(backendBaseUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = url.pathname.replace(/\/$/, '');
    url.pathname = `${url.pathname}/ws/logs`;
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch (error) {
    console.warn('Failed to derive Logs WebSocket URL:', error);
    return envLogsWebsocketUrl ?? 'ws://localhost:8000/ws/logs';
  }
};

export const settingsStore = writable({
  ...defaultSettings,
  ...loadStoredSettings()
});

if (typeof localStorage !== 'undefined') {
  settingsStore.subscribe((settings) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  });
}

export const effectiveConfigStore = derived(settingsStore, ($settings) => {
  const backendBaseUrl = $settings.backendBaseUrl?.trim() || defaultSettings.backendBaseUrl;
  const sqlApiBaseUrl = $settings.sqlApiBaseUrl?.trim() || defaultSettings.sqlApiBaseUrl;
  const websocketUrl = envWebsocketUrl ?? deriveWebsocketUrl(backendBaseUrl);
  const logsWebsocketUrl = envLogsWebsocketUrl ?? deriveLogsWebsocketUrl(backendBaseUrl);

  return {
    backendBaseUrl,
    sqlApiBaseUrl,
    websocketUrl,
    logsWebsocketUrl,
    useMockData
  };
});

export const resetSettings = () => {
  settingsStore.set({ ...defaultSettings });
};
