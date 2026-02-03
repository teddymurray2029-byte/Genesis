<script>
  import { onMount, onDestroy } from 'svelte';
  import { logEventsStore, websocketStore } from '../stores/websocket.js';

  const pageSizeOptions = [5, 10, 20];
  const levelOptions = ['info', 'warning', 'error', 'debug'];

  let logs = [];
  let page = 1;
  let pageSize = 10;
  let total = 0;
  let loading = false;
  let error = null;

  let selectedLog = null;
  let showDrawer = false;

  let showForm = false;
  let formMode = 'create';
  let formData = {
    message: '',
    level: 'info',
    source: '',
    metadata: ''
  };

  let showDeleteConfirm = false;
  let pendingDelete = null;
  let logEventUnsubscribe = null;
  let lastLogEventIndex = 0;

  function normalizeResponse(payload) {
    if (Array.isArray(payload)) {
      return { data: payload, total: payload.length };
    }

    if (payload?.data) {
      return {
        data: payload.data,
        total: payload.total ?? payload.total_count ?? payload.count ?? payload.data.length
      };
    }

    if (payload?.items) {
      return {
        data: payload.items,
        total: payload.total ?? payload.total_count ?? payload.count ?? payload.items.length
      };
    }

    return { data: [], total: 0 };
  }

  function getTotalPages() {
    if (!total && logs.length < pageSize) {
      return page;
    }

    return Math.max(1, Math.ceil(total / pageSize));
  }

  async function fetchLogs() {
    loading = true;
    error = null;

    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize)
      });
      const response = await fetch(`/logs?${params.toString()}`);

      if (!response.ok) {
        throw new Error('Failed to load logs');
      }

      const payload = await response.json();
      const normalized = normalizeResponse(payload);
      logs = normalized.data ?? [];
      total = normalized.total ?? logs.length;
    } catch (err) {
      error = err.message;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    fetchLogs();
    websocketStore.connectLogs();
    logEventUnsubscribe = logEventsStore.subscribe((events) => {
      if (!Array.isArray(events)) {
        return;
      }
      if (events.length <= lastLogEventIndex) {
        return;
      }
      const newEvents = events.slice(lastLogEventIndex);
      lastLogEventIndex = events.length;
      newEvents.forEach(mergeLogEvent);
    });
  });

  onDestroy(() => {
    if (logEventUnsubscribe) {
      logEventUnsubscribe();
    }
  });

  function openDrawer(log) {
    selectedLog = log;
    showDrawer = true;
  }

  function closeDrawer() {
    showDrawer = false;
  }

  function openCreateForm() {
    formMode = 'create';
    formData = {
      message: '',
      level: 'info',
      source: '',
      metadata: ''
    };
    showForm = true;
  }

  function openEditForm(log) {
    formMode = 'edit';
    formData = {
      message: log.message ?? '',
      level: log.level ?? 'info',
      source: log.source ?? '',
      metadata: log.metadata ? JSON.stringify(log.metadata, null, 2) : ''
    };
    selectedLog = log;
    showForm = true;
  }

  function closeForm() {
    showForm = false;
  }

  async function submitForm() {
    if (!formData.message.trim()) {
      error = 'Message is required.';
      return;
    }

    let parsedMetadata;
    if (formData.metadata) {
      try {
        parsedMetadata = JSON.parse(formData.metadata);
      } catch (parseError) {
        error = 'Metadata must be valid JSON.';
        return;
      }
    }

    const payload = {
      message: formData.message,
      level: formData.level,
      source: formData.source,
      metadata: parsedMetadata
    };

    if (formMode === 'create') {
      const tempId = `temp-${Date.now()}`;
      const tempLog = {
        id: tempId,
        timestamp: new Date().toISOString(),
        ...payload,
        status: 'pending'
      };

      logs = [tempLog, ...logs];
      total += 1;
      showForm = false;

      try {
        const response = await fetch('/logs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          throw new Error('Failed to create log');
        }

        const created = await response.json();
        logs = logs.map((log) => (log.id === tempId ? created : log));
      } catch (err) {
        logs = logs.filter((log) => log.id !== tempId);
        total = Math.max(0, total - 1);
        error = err.message;
      }

      return;
    }

    if (!selectedLog) {
      return;
    }

    const previousLog = { ...selectedLog };
    const updatedLog = { ...selectedLog, ...payload };

    logs = logs.map((log) => (log.id === selectedLog.id ? updatedLog : log));
    selectedLog = updatedLog;
    showForm = false;

    try {
      const response = await fetch(`/logs/${selectedLog.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Failed to update log');
      }

      const updated = await response.json();
      logs = logs.map((log) => (log.id === selectedLog.id ? updated : log));
      selectedLog = updated;
    } catch (err) {
      logs = logs.map((log) => (log.id === previousLog.id ? previousLog : log));
      selectedLog = previousLog;
      error = err.message;
    }
  }

  function requestDelete(log) {
    pendingDelete = log;
    showDeleteConfirm = true;
  }

  function closeDeleteConfirm() {
    showDeleteConfirm = false;
    pendingDelete = null;
  }

  async function confirmDelete() {
    if (!pendingDelete) {
      return;
    }

    const deletedLog = pendingDelete;
    logs = logs.filter((log) => log.id !== deletedLog.id);
    total = Math.max(0, total - 1);
    showDeleteConfirm = false;

    try {
      const response = await fetch(`/logs/${deletedLog.id}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error('Failed to delete log');
      }

      if (selectedLog?.id === deletedLog.id) {
        selectedLog = null;
        showDrawer = false;
      }
    } catch (err) {
      logs = [deletedLog, ...logs];
      total += 1;
      error = err.message;
    } finally {
      pendingDelete = null;
    }
  }

  function handlePageChange(direction) {
    const totalPages = getTotalPages();
    const nextPage = direction === 'next' ? Math.min(totalPages, page + 1) : Math.max(1, page - 1);
    if (nextPage === page) {
      return;
    }
    page = nextPage;
    fetchLogs();
  }

  function handlePageSizeChange(event) {
    pageSize = Number(event.target.value);
    page = 1;
    fetchLogs();
  }

  function getLogKey(log) {
    return String(log?.id ?? log?.log_id ?? log?.logId ?? log?.timestamp ?? '');
  }

  function mergeLogEvent(event) {
    if (!event) {
      return;
    }

    if (event.type === 'logs_update') {
      if (Array.isArray(event.logs)) {
        logs = event.logs;
        total = event.total ?? event.logs.length;
      }
      return;
    }

    const logEntry = event.log;
    if (!logEntry) {
      return;
    }

    const logKey = getLogKey(logEntry);
    if (!logKey) {
      return;
    }

    const existingIndex = logs.findIndex((log) => getLogKey(log) === logKey);

    if (event.type === 'log_deleted' || event.type === 'log_removed') {
      if (existingIndex >= 0) {
        logs = logs.filter((_, index) => index !== existingIndex);
        total = Math.max(0, total - 1);
      }
      return;
    }

    if (existingIndex >= 0) {
      logs = logs.map((log, index) => (index === existingIndex ? { ...log, ...logEntry } : log));
      return;
    }

    if (page === 1) {
      logs = [logEntry, ...logs];
    }
    total += 1;
  }
</script>

<section class="space-y-4">
  <header class="flex items-center justify-between gap-4">
    <div>
      <h3 class="text-sm font-semibold text-genesis-cyan">Logs</h3>
      <p class="text-xs text-gray-400">Track and manage operational logs from the service.</p>
    </div>
    <div class="flex items-center gap-2">
      <button class="px-3 py-1 text-xs rounded bg-white/10 text-white hover:bg-white/20" on:click={fetchLogs}>
        Refresh
      </button>
      <button class="px-3 py-1 text-xs rounded bg-genesis-cyan/80 text-black hover:bg-genesis-cyan" on:click={openCreateForm}>
        Create Log
      </button>
    </div>
  </header>

  {#if error}
    <div class="text-xs text-red-400 bg-red-500/10 p-2 rounded">{error}</div>
  {/if}

  <div class="bg-black/30 rounded-lg p-3">
    <div class="flex items-center justify-between text-xs text-gray-400 mb-3">
      <span>Showing page {page} of {getTotalPages()}</span>
      <div class="flex items-center gap-2">
        <label for="pageSize" class="text-[10px] uppercase">Rows</label>
        <select id="pageSize" class="bg-black/40 text-white text-xs rounded px-2 py-1" on:change={handlePageSizeChange}>
          {#each pageSizeOptions as size}
            <option value={size} selected={size === pageSize}>{size}</option>
          {/each}
        </select>
      </div>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-left text-gray-400 border-b border-white/10">
            <th class="py-2 pr-2">Timestamp</th>
            <th class="py-2 pr-2">Level</th>
            <th class="py-2 pr-2">Source</th>
            <th class="py-2">Message</th>
            <th class="py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#if loading}
            <tr>
              <td colspan="5" class="py-4 text-center text-gray-400">Loading logs...</td>
            </tr>
          {:else if logs.length === 0}
            <tr>
              <td colspan="5" class="py-4 text-center text-gray-500">No logs found.</td>
            </tr>
          {:else}
          {#each logs as log}
              <tr
                class="border-b border-white/5 hover:bg-white/5 cursor-pointer"
                role="button"
                tabindex="0"
                on:click={() => openDrawer(log)}
                on:keydown={(event) => event.key === 'Enter' && openDrawer(log)}
              >
                <td class="py-2 pr-2 text-gray-300">{log.timestamp ?? '—'}</td>
                <td class="py-2 pr-2 uppercase text-genesis-cyan">{log.level ?? 'info'}</td>
                <td class="py-2 pr-2 text-gray-300">{log.source ?? '—'}</td>
                <td class="py-2 text-gray-200 truncate max-w-[200px]">{log.message ?? 'No message'}</td>
                <td class="py-2 text-right">
                  <div class="flex items-center justify-end gap-2">
                    <button class="text-[10px] uppercase text-genesis-cyan" on:click|stopPropagation={() => openEditForm(log)}>
                      Edit
                    </button>
                    <button class="text-[10px] uppercase text-red-400" on:click|stopPropagation={() => requestDelete(log)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>

    <div class="flex items-center justify-between mt-3 text-xs">
      <button class="px-2 py-1 rounded bg-white/10 text-white disabled:opacity-40" on:click={() => handlePageChange('prev')} disabled={page === 1}>
        Previous
      </button>
      <span class="text-gray-400">Total logs: {total || logs.length}</span>
      <button class="px-2 py-1 rounded bg-white/10 text-white disabled:opacity-40" on:click={() => handlePageChange('next')} disabled={page >= getTotalPages()}>
        Next
      </button>
    </div>
  </div>
</section>

{#if showDrawer && selectedLog}
  <div class="fixed inset-0 z-30">
    <button
      class="absolute inset-0 bg-black/40"
      type="button"
      aria-label="Close log details"
      on:click={closeDrawer}
    ></button>
    <aside class="absolute right-0 top-0 h-full w-full max-w-sm bg-slate-900/95 text-white p-4 overflow-y-auto">
      <div class="flex items-start justify-between">
        <div>
          <h4 class="text-sm font-semibold">Log Details</h4>
          <p class="text-xs text-gray-400">{selectedLog.timestamp ?? 'Unknown time'}</p>
        </div>
        <button class="text-xs text-gray-400" on:click={closeDrawer}>Close</button>
      </div>

      <div class="mt-4 space-y-3 text-xs">
        <div>
          <div class="text-gray-400">Level</div>
          <div class="uppercase text-genesis-cyan">{selectedLog.level ?? 'info'}</div>
        </div>
        <div>
          <div class="text-gray-400">Source</div>
          <div>{selectedLog.source ?? '—'}</div>
        </div>
        <div>
          <div class="text-gray-400">Message</div>
          <div class="text-gray-200">{selectedLog.message ?? 'No message'}</div>
        </div>
        <div>
          <div class="text-gray-400">Metadata</div>
          <pre class="bg-black/40 p-2 rounded text-[10px] whitespace-pre-wrap">{JSON.stringify(selectedLog.metadata ?? {}, null, 2)}</pre>
        </div>
      </div>
    </aside>
  </div>
{/if}

{#if showForm}
  <div class="fixed inset-0 z-40 flex items-center justify-center">
    <button
      class="absolute inset-0 bg-black/50"
      type="button"
      aria-label="Close log form"
      on:click={closeForm}
    ></button>
    <div class="relative bg-slate-900 text-white rounded-lg w-full max-w-lg p-4">
      <h4 class="text-sm font-semibold mb-3">{formMode === 'create' ? 'Create Log' : 'Edit Log'}</h4>
      <form class="space-y-3" on:submit|preventDefault={submitForm}>
        <div>
          <label class="text-xs text-gray-400" for="log-message">Message</label>
          <textarea id="log-message" class="w-full bg-black/40 rounded p-2 text-xs" rows="3" bind:value={formData.message}></textarea>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-xs text-gray-400" for="log-level">Level</label>
            <select id="log-level" class="w-full bg-black/40 rounded p-2 text-xs" bind:value={formData.level}>
              {#each levelOptions as level}
                <option value={level}>{level}</option>
              {/each}
            </select>
          </div>
          <div>
            <label class="text-xs text-gray-400" for="log-source">Source</label>
            <input id="log-source" class="w-full bg-black/40 rounded p-2 text-xs" type="text" bind:value={formData.source} />
          </div>
        </div>
        <div>
          <label class="text-xs text-gray-400" for="log-metadata">Metadata (JSON)</label>
          <textarea id="log-metadata" class="w-full bg-black/40 rounded p-2 text-xs" rows="3" bind:value={formData.metadata}></textarea>
        </div>
        <div class="flex items-center justify-end gap-2">
          <button type="button" class="px-3 py-1 text-xs rounded bg-white/10" on:click={closeForm}>Cancel</button>
          <button type="submit" class="px-3 py-1 text-xs rounded bg-genesis-cyan/80 text-black">Save</button>
        </div>
      </form>
    </div>
  </div>
{/if}

{#if showDeleteConfirm}
  <div class="fixed inset-0 z-40 flex items-center justify-center">
    <button
      class="absolute inset-0 bg-black/50"
      type="button"
      aria-label="Close delete confirmation"
      on:click={closeDeleteConfirm}
    ></button>
    <div class="relative bg-slate-900 text-white rounded-lg w-full max-w-sm p-4">
      <h4 class="text-sm font-semibold">Delete Log</h4>
      <p class="text-xs text-gray-400 mt-2">Are you sure you want to delete this log entry?</p>
      <div class="flex items-center justify-end gap-2 mt-4">
        <button class="px-3 py-1 text-xs rounded bg-white/10" on:click={closeDeleteConfirm}>Cancel</button>
        <button class="px-3 py-1 text-xs rounded bg-red-500/80 text-white" on:click={confirmDelete}>Delete</button>
      </div>
    </div>
  </div>
{/if}
