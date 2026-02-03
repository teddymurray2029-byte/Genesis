<script>
  import { connectedStore, lastSyncStore, connectionErrorStore, websocketStore } from '../stores/websocket.js';

  const formatTime = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  function handleRetry() {
    websocketStore.retry();
  }
</script>

<header class="header-bar">
  <div class="header-left">
    <span class="brand">Genesis</span>
  </div>
  <div class="header-right">
    <div class="status-pill">
      <span class="status-dot {$connectedStore ? 'status-connected' : 'status-disconnected'}"></span>
      <span class="status-text">{$connectedStore ? 'Connected' : 'Disconnected'}</span>
      <span class="status-divider">•</span>
      <span class="status-sync">Last sync: {formatTime($lastSyncStore)}</span>
    </div>
  </div>
</header>

{#if $connectionErrorStore}
  <div class="connection-banner" role="status" aria-live="polite">
    <span class="banner-text">{$connectionErrorStore}</span>
    <button class="banner-button" type="button" on:click={handleRetry}>Retry</button>
  </div>
{/if}

<style>
  .header-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    background: rgba(5, 10, 24, 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(0, 255, 255, 0.2);
  }

  .brand {
    font-size: 14px;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.8);
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.15);
    font-size: 12px;
    color: rgba(255, 255, 255, 0.8);
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.4);
  }

  .status-connected {
    background: rgba(34, 197, 94, 0.9);
    box-shadow: 0 0 6px rgba(34, 197, 94, 0.8);
  }

  .status-disconnected {
    background: rgba(239, 68, 68, 0.9);
    box-shadow: 0 0 6px rgba(239, 68, 68, 0.8);
  }

  .status-divider {
    color: rgba(255, 255, 255, 0.4);
  }

  .connection-banner {
    position: fixed;
    top: 64px;
    right: 24px;
    z-index: 35;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: rgba(15, 20, 40, 0.9);
    border: 1px solid rgba(239, 68, 68, 0.5);
    border-radius: 12px;
    color: rgba(255, 255, 255, 0.9);
    font-size: 12px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  }

  .banner-button {
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid rgba(0, 255, 255, 0.4);
    background: rgba(0, 255, 255, 0.1);
    color: rgba(0, 255, 255, 0.9);
    font-size: 12px;
    cursor: pointer;
  }

  .banner-button:hover {
    background: rgba(0, 255, 255, 0.2);
  }
</style>
