<script>
  import { onMount } from 'svelte';
  import BrainSpace from './components/BrainSpace.svelte';
  import ControlPanel from './components/ControlPanel.svelte';
  import ChatBar from './components/ChatBar.svelte';
  import { websocketStore } from './stores/websocket.js';
  
  const API_BASE = import.meta.env.VITE_GENESIS_API_URL || 'http://localhost:8000';

  let databases = [];
  let tables = [];
  let selectedDatabase = '';
  let selectedTable = '';
  let rows = [];
  let schemaColumns = [];
  let schemaConstraints = [];
  let schemaIndexes = [];
  let schemaConstraintsDraft = '';
  let schemaIndexesDraft = '';
  let filterText = '';
  let page = 0;
  let pageSize = 25;
  let draftRow = {};
  let selectedRowKey = null;
  let isNewRecord = false;
  let errorMessage = '';
  let isLoadingDatabases = false;
  let isLoadingTables = false;
  let isLoadingRows = false;
  let isLoadingSchema = false;
  let isMutating = false;

  onMount(() => {
    console.log('🎨 App.svelte mounted');
    initializeGenesisDb();
  });

  async function apiRequest(path, options = {}) {
    errorMessage = '';
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed: ${response.status}`);
    }
    return response.json();
  }

  async function initializeGenesisDb() {
    try {
      await loadDatabases();
      await loadTablesAndSchema();
      await loadRows();
    } catch (error) {
      errorMessage = error.message;
    }
  }

  async function loadDatabases() {
    isLoadingDatabases = true;
    try {
      const health = await apiRequest('/health');
      databases = health?.db_path ? [health.db_path] : ['GenesisDB'];
      selectedDatabase = databases[0] || '';
    } finally {
      isLoadingDatabases = false;
    }
  }

  async function loadTablesAndSchema() {
    isLoadingTables = true;
    isLoadingSchema = true;
    try {
      const schema = await apiRequest('/schema');
      tables = schema?.table ? [schema.table] : ['entries'];
      selectedTable = tables[0] || '';
      schemaColumns = schema?.columns || [];
      schemaConstraints = schema?.constraints || [];
      schemaIndexes = schema?.indexes || [];
      schemaConstraintsDraft = schemaConstraints.join('\n');
      schemaIndexesDraft = schemaIndexes.join('\n');
    } finally {
      isLoadingTables = false;
      isLoadingSchema = false;
    }
  }

  function coerceValue(value, type) {
    if (value === '' || value === undefined) {
      return null;
    }
    if (type === 'INTEGER') {
      const parsed = Number.parseInt(value, 10);
      return Number.isNaN(parsed) ? null : parsed;
    }
    if (type === 'REAL') {
      const parsed = Number.parseFloat(value);
      return Number.isNaN(parsed) ? null : parsed;
    }
    return value;
  }

  function formatSqlValue(value) {
    if (value === null || value === undefined || value === '') {
      return 'NULL';
    }
    if (typeof value === 'number') {
      return `${value}`;
    }
    if (typeof value === 'boolean') {
      return value ? 'true' : 'false';
    }
    const escaped = String(value).replace(/'/g, "''");
    return `'${escaped}'`;
  }

  function buildSelectSql() {
    const safePageSize = Math.max(1, Number(pageSize) || 25);
    const offset = Math.max(0, page) * safePageSize;
    const conditions = [];
    if (filterText.trim()) {
      conditions.push(filterText.trim());
    }
    if (Number.isFinite(offset)) {
      conditions.push(`entry_index >= ${offset}`);
    }
    const whereClause = conditions.length ? ` WHERE ${conditions.join(' AND ')}` : '';
    return `SELECT * FROM ${selectedTable}${whereClause} ORDER BY entry_index LIMIT ${safePageSize}`;
  }

  function buildInsertSql(payload) {
    const columns = schemaColumns.map((column) => column.name);
    const values = columns.map((name) => formatSqlValue(payload[name]));
    return `INSERT INTO ${selectedTable} (${columns.join(', ')}) VALUES (${values.join(', ')})`;
  }

  function buildUpdateSql(payload) {
    const columns = schemaColumns
      .map((column) => column.name)
      .filter((name) => name !== 'entry_index');
    const assignments = columns.map((name) => `${name} = ${formatSqlValue(payload[name])}`);
    if (payload.entry_index === null || payload.entry_index === undefined) {
      if (!payload.id) {
        throw new Error('Cannot update row without entry_index or id');
      }
      return `UPDATE ${selectedTable} SET ${assignments.join(', ')} WHERE id = ${formatSqlValue(payload.id)}`;
    }
    return `UPDATE ${selectedTable} SET ${assignments.join(', ')} WHERE entry_index = ${payload.entry_index}`;
  }

  function buildDeleteSql(payload) {
    if (payload.entry_index === null || payload.entry_index === undefined) {
      if (!payload.id) {
        throw new Error('Cannot delete row without entry_index or id');
      }
      return `DELETE FROM ${selectedTable} WHERE id = ${formatSqlValue(payload.id)}`;
    }
    return `DELETE FROM ${selectedTable} WHERE entry_index = ${payload.entry_index}`;
  }

  function mapDraftToRow() {
    return schemaColumns.reduce((acc, column) => {
      acc[column.name] = coerceValue(draftRow[column.name], column.type);
      return acc;
    }, {});
  }

  function updateDraftField(name, value) {
    draftRow = { ...draftRow, [name]: value };
  }

  function selectRow(row) {
    selectedRowKey = row.entry_index ?? row.id ?? null;
    isNewRecord = false;
    draftRow = schemaColumns.reduce((acc, column) => {
      acc[column.name] = row[column.name] ?? '';
      return acc;
    }, {});
  }

  function startNewRecord() {
    selectedRowKey = null;
    isNewRecord = true;
    draftRow = schemaColumns.reduce((acc, column) => {
      acc[column.name] = '';
      return acc;
    }, {});
  }

  async function loadRows() {
    if (!selectedTable) {
      return;
    }
    isLoadingRows = true;
    try {
      const sql = buildSelectSql();
      const response = await apiRequest('/query', {
        method: 'POST',
        body: JSON.stringify({ sql, params: [] })
      });
      rows = response?.rows || [];
      syncBrainSpace(rows);
    } catch (error) {
      errorMessage = error.message;
    } finally {
      isLoadingRows = false;
    }
  }

  function syncBrainSpace(rowData) {
    const memories = rowData.map((row) => ({
      memory_id: row.entry_index ?? row.id,
      cluster_id: row.frequency_band ?? 0,
      identity_id: row.frequency_band ?? 0,
      position: [
        row.position_x ?? 0,
        row.position_y ?? 0,
        row.position_z ?? 0
      ],
      coherence: row.coherence ?? 0.7,
      timestamp: row.timestamp ?? Date.now()
    }));
    websocketStore.data.set({
      brainSpace: { clusters: [], memories },
      activation: { waveform: [], sparks: [], energy: 0.7, morphism: 'gamma' },
      controls: {
        current_cycle: 'active',
        morphism_state: 'gamma',
        coherence: 0.85,
        gamma_params: { amplitude: 100.0 },
        tau_params: { projection_strength: 0.8 }
      },
      events: []
    });
    websocketStore.connected.set(true);
  }

  async function refreshAfterMutation() {
    await loadRows();
    await loadTablesAndSchema();
  }

  async function saveChanges() {
    isMutating = true;
    try {
      const payload = mapDraftToRow();
      const sql = isNewRecord ? buildInsertSql(payload) : buildUpdateSql(payload);
      await apiRequest('/query', {
        method: 'POST',
        body: JSON.stringify({ sql, params: [] })
      });
      await refreshAfterMutation();
      isNewRecord = false;
    } catch (error) {
      errorMessage = error.message;
    } finally {
      isMutating = false;
    }
  }

  async function deleteRecord() {
    if (!draftRow || (!draftRow.entry_index && !draftRow.id)) {
      return;
    }
    isMutating = true;
    try {
      const payload = mapDraftToRow();
      const sql = buildDeleteSql(payload);
      await apiRequest('/query', {
        method: 'POST',
        body: JSON.stringify({ sql, params: [] })
      });
      startNewRecord();
      await refreshAfterMutation();
    } catch (error) {
      errorMessage = error.message;
    } finally {
      isMutating = false;
    }
  }

  async function applySchemaChanges() {
    isLoadingSchema = true;
    try {
      const constraints = schemaConstraintsDraft
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
      const indexes = schemaIndexesDraft
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
      await apiRequest('/schema', {
        method: 'POST',
        body: JSON.stringify({
          columns: schemaColumns,
          constraints,
          indexes
        })
      });
      await loadTablesAndSchema();
    } catch (error) {
      errorMessage = error.message;
    } finally {
      isLoadingSchema = false;
    }
  }

  function handleTableChange(event) {
    selectedTable = event.target.value;
    page = 0;
    startNewRecord();
    loadRows();
    loadTablesAndSchema();
  }

  function handleFilter() {
    page = 0;
    loadRows();
  }

  function handlePageSizeChange(event) {
    pageSize = Math.max(1, Number(event.target.value) || 1);
    page = 0;
    loadRows();
  }

  function nextPage() {
    page += 1;
    loadRows();
  }

  function prevPage() {
    page = Math.max(0, page - 1);
    loadRows();
  }
</script>

<main class="h-screen w-screen flex flex-col relative">
  <div class="db-panel glassmorphic">
    <header class="text-sm font-semibold text-genesis-cyan mb-2">GenesisDB Explorer</header>
    {#if errorMessage}
      <div class="text-xs text-red-300 mb-2">{errorMessage}</div>
    {/if}
    <section class="space-y-2 mb-3">
      <div class="flex items-center gap-2">
        <label class="text-xs text-gray-300 w-20" for="db-select">Database</label>
        <select
          id="db-select"
          class="flex-1 text-xs bg-black/30 border border-white/10 rounded px-2 py-1"
          bind:value={selectedDatabase}
          disabled={isLoadingDatabases}
        >
          {#each databases as db}
            <option value={db}>{db}</option>
          {/each}
        </select>
        {#if isLoadingDatabases}
          <span class="spinner" aria-label="Loading databases"></span>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        <label class="text-xs text-gray-300 w-20" for="table-select">Table</label>
        <select
          id="table-select"
          class="flex-1 text-xs bg-black/30 border border-white/10 rounded px-2 py-1"
          bind:value={selectedTable}
          on:change={handleTableChange}
          disabled={isLoadingTables}
        >
          {#each tables as table}
            <option value={table}>{table}</option>
          {/each}
        </select>
        {#if isLoadingTables}
          <span class="spinner" aria-label="Loading tables"></span>
        {/if}
      </div>
    </section>

    <section class="space-y-2 mb-3">
      <div class="flex items-center gap-2">
        <input
          type="text"
          class="flex-1 text-xs bg-black/30 border border-white/10 rounded px-2 py-1"
          placeholder="Filter (e.g. modality = 'text')"
          bind:value={filterText}
        />
        <button
          class="text-xs px-2 py-1 rounded bg-genesis-cyan/20 text-genesis-cyan"
          on:click={handleFilter}
          disabled={isLoadingRows}
        >
          Apply
        </button>
      </div>
      <div class="flex items-center gap-2 text-xs text-gray-300">
        <label class="w-20" for="page-size">Page size</label>
        <input
          id="page-size"
          type="number"
          min="1"
          class="w-20 text-xs bg-black/30 border border-white/10 rounded px-2 py-1"
          value={pageSize}
          on:change={handlePageSizeChange}
        />
        <button
          class="text-xs px-2 py-1 rounded bg-white/10"
          on:click={prevPage}
          disabled={page === 0 || isLoadingRows}
        >
          Prev
        </button>
        <span>Page {page + 1}</span>
        <button
          class="text-xs px-2 py-1 rounded bg-white/10"
          on:click={nextPage}
          disabled={isLoadingRows || rows.length < pageSize}
        >
          Next
        </button>
        {#if isLoadingRows}
          <span class="spinner" aria-label="Loading rows"></span>
        {/if}
      </div>
    </section>

    <section class="mb-3">
      <div class="text-xs text-gray-300 mb-1">Rows</div>
      <div class="table-container">
        <table class="text-[10px] w-full">
          <thead>
            <tr>
              {#each schemaColumns as column}
                <th class="text-left px-1 py-1 text-gray-400">{column.name}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each rows as row}
              <tr
                class:selected-row={selectedRowKey === (row.entry_index ?? row.id)}
                on:click={() => selectRow(row)}
              >
                {#each schemaColumns as column}
                  <td class="px-1 py-1">{row[column.name]}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>

    <section class="mb-3 space-y-2">
      <div class="flex items-center gap-2">
        <button
          class="text-xs px-2 py-1 rounded bg-genesis-cyan/20 text-genesis-cyan"
          on:click={startNewRecord}
          disabled={isMutating}
        >
          New Record
        </button>
        <button
          class="text-xs px-2 py-1 rounded bg-green-500/20 text-green-200"
          on:click={saveChanges}
          disabled={isMutating || !Object.keys(draftRow || {}).length}
        >
          Save Changes
        </button>
        <button
          class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-200"
          on:click={deleteRecord}
          disabled={isMutating || (!draftRow?.entry_index && !draftRow?.id)}
        >
          Delete
        </button>
        {#if isMutating}
          <span class="spinner" aria-label="Saving changes"></span>
        {/if}
      </div>
      <div class="grid grid-cols-2 gap-2 max-h-40 overflow-auto pr-1">
        {#each schemaColumns as column}
          <label class="text-[10px] text-gray-400 flex flex-col gap-1">
            {column.name}
            <input
              type="text"
              class="text-xs bg-black/30 border border-white/10 rounded px-2 py-1"
              value={draftRow[column.name] ?? ''}
              on:input={(event) => updateDraftField(column.name, event.target.value)}
            />
          </label>
        {/each}
      </div>
    </section>

    <section class="space-y-2">
      <div class="text-xs text-gray-300">Schema Editor</div>
      <div class="text-[10px] text-gray-400 space-y-1">
        {#each schemaColumns as column}
          <div>{column.name} <span class="text-gray-500">({column.type})</span></div>
        {/each}
      </div>
      <label class="text-[10px] text-gray-400 flex flex-col gap-1">
        Constraints
        <textarea
          rows="3"
          class="text-xs bg-black/30 border border-white/10 rounded px-2 py-1"
          bind:value={schemaConstraintsDraft}
        ></textarea>
      </label>
      <label class="text-[10px] text-gray-400 flex flex-col gap-1">
        Indexes
        <textarea
          rows="3"
          class="text-xs bg-black/30 border border-white/10 rounded px-2 py-1"
          bind:value={schemaIndexesDraft}
        ></textarea>
      </label>
      <button
        class="text-xs px-2 py-1 rounded bg-genesis-cyan/20 text-genesis-cyan"
        on:click={applySchemaChanges}
        disabled={isLoadingSchema}
      >
        Apply Changes
      </button>
      {#if isLoadingSchema}
        <span class="spinner" aria-label="Saving schema changes"></span>
      {/if}
    </section>
  </div>
  <!-- Main 3D Brain Space -->
  <div class="flex-1 relative">
    <BrainSpace />
  </div>
  
  <!-- Control Panel (Right Sidebar) -->
  <ControlPanel />
  
  <!-- Chat Bar (Bottom) -->
  <ChatBar />
</main>

<style>
  .db-panel {
    position: absolute;
    top: 16px;
    left: 16px;
    z-index: 30;
    width: 420px;
    max-height: calc(100vh - 32px);
    overflow: auto;
    padding: 16px;
    border-radius: 16px;
  }

  .table-container {
    max-height: 160px;
    overflow: auto;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
  }

  tbody tr {
    cursor: pointer;
  }

  tbody tr:hover {
    background: rgba(0, 255, 255, 0.08);
  }

  .selected-row {
    background: rgba(0, 255, 255, 0.16);
  }

  .spinner {
    width: 12px;
    height: 12px;
    border-radius: 999px;
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-top-color: rgba(0, 255, 255, 0.9);
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  main {
    background: #000011; /* Deep navy/black background */
    position: relative;
  }
  
  /* Vignette effect - radial gradient overlay (behind UI) */
  main::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(
      ellipse at center,
      transparent 0%,
      transparent 40%,
      rgba(0, 0, 17, 0.3) 70%,
      rgba(0, 0, 0, 0.8) 100%
    );
    pointer-events: none;
    z-index: 0;
  }
  
  /* Additional radial filter for depth */
  main::after {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(
      circle at 50% 50%,
      transparent 0%,
      rgba(0, 17, 34, 0.2) 50%,
      rgba(0, 0, 0, 0.6) 100%
    );
    pointer-events: none;
    z-index: 0;
  }
</style>
