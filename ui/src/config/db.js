const env = import.meta.env;

export const genesisDbConfig = {
  httpUrl: env.VITE_GENESISDB_HTTP_URL ?? 'http://localhost:8080',
  websocketUrl: env.VITE_GENESISDB_WS_URL ?? 'ws://localhost:8000/ws',
  username: env.VITE_GENESISDB_USERNAME ?? '',
  password: env.VITE_GENESISDB_PASSWORD ?? '',
  apiKey: env.VITE_GENESISDB_API_KEY ?? '',
  useMockData: env.VITE_GENESISDB_USE_MOCK_DATA
    ? env.VITE_GENESISDB_USE_MOCK_DATA === 'true'
    : true
};
