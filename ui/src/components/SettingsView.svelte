<script>
  import { settingsStore, effectiveConfigStore, resetSettings } from '../stores/config.js';

  const handleBackendChange = (event) => {
    const value = event.target.value;
    settingsStore.update((current) => ({ ...current, backendBaseUrl: value }));
  };

  const handleSqlApiChange = (event) => {
    const value = event.target.value;
    settingsStore.update((current) => ({ ...current, sqlApiBaseUrl: value }));
  };
</script>

<section class="settings-panel" aria-label="Settings">
  <header class="settings-header">
    <div>
      <p class="settings-title">Settings</p>
      <p class="settings-subtitle">Persisted locally per browser.</p>
    </div>
    <button class="settings-reset" type="button" on:click={resetSettings}>Reset</button>
  </header>

  <div class="settings-body">
    <label class="field">
      <span>Backend base URL</span>
      <input
        type="url"
        value={$settingsStore.backendBaseUrl}
        placeholder="http://localhost:8080"
        on:input={handleBackendChange}
      />
    </label>

    <label class="field">
      <span>SQL API base URL</span>
      <input
        type="url"
        value={$settingsStore.sqlApiBaseUrl}
        placeholder="http://localhost:8080/sql"
        on:input={handleSqlApiChange}
      />
    </label>
  </div>

  <div class="settings-summary">
    <p class="summary-title">Effective config</p>
    <pre>{JSON.stringify($effectiveConfigStore, null, 2)}</pre>
  </div>
</section>

<style>
  .settings-panel {
    position: fixed;
    right: 24px;
    top: 88px;
    z-index: 20;
    width: 320px;
    padding: 16px;
    border-radius: 16px;
    background: rgba(5, 10, 24, 0.7);
    border: 1px solid rgba(0, 255, 255, 0.2);
    color: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
    font-size: 12px;
  }

  .settings-header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }

  .settings-title {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    margin: 0;
  }

  .settings-subtitle {
    margin: 4px 0 0;
    color: rgba(255, 255, 255, 0.6);
  }

  .settings-reset {
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.3);
    background: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.9);
    font-size: 11px;
    cursor: pointer;
  }

  .settings-reset:hover {
    background: rgba(255, 255, 255, 0.2);
  }

  .settings-body {
    display: grid;
    gap: 12px;
  }

  .field {
    display: grid;
    gap: 6px;
  }

  .field span {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.7);
  }

  .field input {
    width: 100%;
    padding: 8px 10px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(0, 0, 0, 0.35);
    color: rgba(255, 255, 255, 0.95);
    font-size: 12px;
  }

  .settings-summary {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.15);
  }

  .summary-title {
    margin: 0 0 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: rgba(255, 255, 255, 0.7);
  }

  pre {
    margin: 0;
    padding: 10px;
    background: rgba(0, 0, 0, 0.35);
    border-radius: 10px;
    font-size: 11px;
    color: rgba(204, 251, 241, 0.95);
    overflow: auto;
    max-height: 160px;
  }
</style>
