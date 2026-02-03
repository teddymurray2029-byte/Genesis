<script>
  import { dataStore, connectionStateStore } from '../stores/websocket.js';

  const MAX_EVENTS = 8;

  $: events = $dataStore?.events || [];
  $: connectionState = $connectionStateStore;
  $: statusLabel = connectionState.connected ? 'Connected' : 'Disconnected';
  $: statusColor = connectionState.connected ? 'bg-emerald-500' : 'bg-rose-500';
</script>

<section class="absolute right-6 top-20 z-20 w-72 rounded-2xl border border-white/10 bg-black/70 p-4 text-xs text-slate-100 shadow-xl backdrop-blur">
  <header class="flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class={`h-2 w-2 rounded-full ${statusColor}`}></span>
      <span class="font-semibold">{statusLabel}</span>
    </div>
    {#if connectionState.error}
      <span class="max-w-[140px] truncate text-rose-200" title={connectionState.error}>
        {connectionState.error}
      </span>
    {/if}
  </header>

  <div class="mt-4 space-y-2">
    <div class="text-[11px] uppercase tracking-wide text-slate-300">
      Recent Events
    </div>
    {#if events.length === 0}
      <div class="rounded-lg border border-white/10 bg-white/5 p-2 text-slate-300">
        Waiting for events...
      </div>
    {:else}
      {#each events.slice(-MAX_EVENTS).reverse() as event}
        <div class="rounded-lg border border-white/10 bg-white/5 p-2">
          <div class="flex items-center justify-between">
            <span class="font-medium text-genesis-cyan">{event.type ?? 'event'}</span>
            <span class="text-[10px] text-slate-400">{event.timestamp ?? ''}</span>
          </div>
          <div class="mt-1 text-[11px] text-slate-200">
            {event.message ?? event.payload?.message ?? event.payload?.summary ?? 'Update received.'}
          </div>
        </div>
      {/each}
    {/if}
  </div>
</section>
