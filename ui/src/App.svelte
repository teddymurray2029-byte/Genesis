<script>
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { dataStore, websocketStore, connectedStore, lastSyncStore, connectionErrorStore } from './stores/websocket.js';
  import { effectiveConfigStore } from './stores/config.js';

  let selectedTable = '';
  let filterText = '';
  let selectedRowKey = null;
  let queryText = 'SELECT * FROM entries LIMIT 100';
  let queryStatus = null;
  let queryError = null;
  let isQueryRunning = false;
  let isSaving = false;
  let draftRow = {};
  let columnTypes = {};
  let lastQueryTable = 'entries';
  let dataStats = null;

  const rowKey = (row, columns = []) => row?.id ?? row?.[columns?.[0]?.name];
  const matchesFilter = (row, filter) =>
    !filter ||
    Object.values(row || {}).some((value) =>
      String(value ?? '')
        .toLowerCase()
        .includes(filter.toLowerCase())
    );

  const formatTimestamp = (value) => {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('en-US', {
      month: 'numeric',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  const normalizeRowValue = (value) =>
    value === null || value === undefined ? '' : String(value);

  const isSameValue = (left, right) => normalizeRowValue(left) === normalizeRowValue(right);
  const hasUnsavedChanges = (row, draft, tableColumns = []) =>
    !!row && tableColumns.some((column) => !isSameValue(draft?.[column.name], row?.[column.name]));

  $: genesisDb = $dataStore?.genesisDb;
  $: database = genesisDb?.database;
  $: tables = genesisDb?.tables ?? {};
  $: tableNames = Object.keys(tables);
  $: activeTable = tables[selectedTable] || tables[genesisDb?.activeTable] || tables[tableNames[0]];
  $: columns = activeTable?.columns ?? [];
  $: rows = activeTable?.rows ?? [];
  $: filteredRows = rows.filter((row) => matchesFilter(row, filterText));
  $: selectedRow =
    rows.find((row) => rowKey(row, columns) === selectedRowKey) ||
    rows.find((row) => rowKey(row, columns) === genesisDb?.selectedRow?.id) ||
    rows[0];
  $: isDirty = hasUnsavedChanges(selectedRow, draftRow, columns);
  $: if (selectedRow) {
    draftRow = { ...selectedRow };
  }
  $: if (genesisDb?.activeTable && !selectedTable) {
    selectedTable = genesisDb.activeTable;
  }

  const buildSqlApiUrl = (path) => {
    const { sqlApiBaseUrl } = get(effectiveConfigStore);
    const base = sqlApiBaseUrl?.trim() || '';
    if (!base) return path;
    const sanitized = base.replace(/\/$/, '');
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${sanitized}${normalizedPath}`;
  };

  const detectTableFromSql = (sql) => {
    if (!sql) return 'entries';
    return /\bfrom\s+logs\b/i.test(sql) || /\bupdate\s+logs\b/i.test(sql) || /\binto\s+logs\b/i.test(sql)
      ? 'logs'
      : 'entries';
  };

  const fetchSchema = async () => {
    const response = await fetch(buildSqlApiUrl('/schema'));
    if (!response.ok) {
      throw new Error(`Failed to load schema: ${response.status}`);
    }
    const data = await response.json();
    const types = {};
    (data.columns || []).forEach((column) => {
      types[column.name] = column.type;
    });
    columnTypes = types;
    return data;
  };

  const execSql = async (sql) => {
    const response = await fetch(buildSqlApiUrl('/query'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql, params: [] })
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail?.detail || `Query failed with status ${response.status}`);
    }
    return response.json();
  };

  const fetchHealth = async () => {
    const response = await fetch(buildSqlApiUrl('/health'));
    if (!response.ok) {
      return null;
    }
    return response.json();
  };

  const refreshGenesisDb = async (sql = queryText) => {
    isQueryRunning = true;
    queryError = null;
    queryStatus = 'Loading data from GenesisDB...';
    try {
      await fetchSchema();
      const health = await fetchHealth();
      const result = await execSql(sql);
      const tableName = detectTableFromSql(sql);
      lastQueryTable = tableName;
      dataStats = {
        execution_time_ms: result.execution_time_ms,
        row_count: result.row_count,
        time_complexity: result.time_complexity
      };
      const resolvedColumns = result.columns?.length
        ? result.columns
        : Object.keys(result.rows?.[0] || {});
      const columnDefs = resolvedColumns.map((name) => ({
        name,
        type: columnTypes[name] || 'TEXT'
      }));
      const genesisDb = {
        database: {
          name: 'genesis_db',
          description: 'GenesisDB entries loaded from the SQL API.',
          region: 'local',
          updated_at: new Date().toISOString()
        },
        tables: {
          [tableName]: {
            columns: columnDefs,
            rows: result.rows || []
          }
        },
        activeTable: tableName,
        selectedRow: result.rows?.[0] ? { table: tableName, id: rowKey(result.rows[0], columnDefs) } : null
      };
      if (health) {
        genesisDb.database = {
          ...genesisDb.database,
          name: 'genesis_db',
          description: `GenesisDB at ${health.db_path || 'unknown path'}`,
          updated_at: new Date().toISOString()
        };
      }
      websocketStore.data.set({
        ...get(dataStore),
        genesisDb
      });
      connectedStore.set(true);
      lastSyncStore.set(Date.now());
      connectionErrorStore.set(null);
      selectedTable = tableName;
      selectedRowKey = genesisDb.selectedRow?.id ?? null;
      queryStatus = `Loaded ${result.row_count} rows from ${tableName}.`;
    } catch (error) {
      console.error('Failed to load GenesisDB data:', error);
      queryError = error?.message || 'Failed to load GenesisDB data.';
      connectionErrorStore.set(queryError);
      queryStatus = null;
    } finally {
      isQueryRunning = false;
    }
  };

  const runQuery = async () => {
    await refreshGenesisDb(queryText);
  };

  const exportCsv = () => {
    if (!columns.length || !filteredRows.length) return;
    const headers = columns.map((column) => column.name);
    const escapeCell = (value) => {
      const text = value === null || value === undefined ? '' : String(value);
      if (text.includes('"') || text.includes(',') || text.includes('\n')) {
        return `"${text.replace(/"/g, '""')}"`;
      }
      return text;
    };
    const rowsCsv = filteredRows.map((row) =>
      headers.map((header) => escapeCell(row?.[header])).join(',')
    );
    const csvContent = [headers.join(','), ...rowsCsv].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${selectedTable || 'entries'}-export.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const backupGenesisDb = async () => {
    queryStatus = 'Creating backup...';
    queryError = null;
    try {
      const result = await execSql('SELECT * FROM entries');
      const payload = {
        created_at: new Date().toISOString(),
        rows: result.rows || []
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'genesisdb-backup.json';
      anchor.click();
      URL.revokeObjectURL(url);
      queryStatus = 'Backup downloaded.';
    } catch (error) {
      console.error('Backup failed:', error);
      queryError = error?.message || 'Backup failed.';
      queryStatus = null;
    }
  };

  const formatSqlValue = (value, type) => {
    if (value === null || value === undefined || value === '') {
      return 'NULL';
    }
    const normalizedType = (type || '').toUpperCase();
    if (normalizedType.includes('INT') || normalizedType.includes('REAL')) {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? String(numeric) : 'NULL';
    }
    const escaped = String(value).replace(/'/g, "''");
    return `'${escaped}'`;
  };

  const saveRow = async () => {
    if (!selectedRow || !columns.length) return;
    isSaving = true;
    queryError = null;
    queryStatus = null;
    try {
      const updates = columns
        .filter((column) => !isSameValue(draftRow?.[column.name], selectedRow?.[column.name]))
        .map((column) => `${column.name} = ${formatSqlValue(draftRow?.[column.name], column.type)}`);
      if (!updates.length) {
        queryStatus = 'No changes to save.';
        return;
      }
      const identifier = selectedRow?.entry_index ?? selectedRow?.id;
      if (identifier === undefined || identifier === null) {
        throw new Error('Missing identifier for update.');
      }
      const whereClause =
        selectedRow?.entry_index !== undefined && selectedRow?.entry_index !== null
          ? `entry_index = ${formatSqlValue(selectedRow.entry_index, 'INTEGER')}`
          : `id = ${formatSqlValue(selectedRow.id, 'TEXT')}`;
      const updateSql = `UPDATE entries SET ${updates.join(', ')} WHERE ${whereClause}`;
      await execSql(updateSql);
      await refreshGenesisDb(queryText);
      queryStatus = 'Changes saved.';
    } catch (error) {
      console.error('Save failed:', error);
      queryError = error?.message || 'Failed to save changes.';
    } finally {
      isSaving = false;
    }
  };

  const handleSelectTable = (name) => {
    selectedTable = name;
    selectedRowKey = null;
  };

  const handleSelectRow = (row) => {
    if (isDirty) {
      const confirmChange = window.confirm(
        'You have unsaved changes. Are you sure you want to switch rows and discard them?'
      );
      if (!confirmChange) return;
    }
    selectedRowKey = rowKey(row, columns);
  };

  onMount(() => {
    console.log('🎨 App.svelte mounted');
    document.title = 'Genesis Data Console';
    
    // Initialize WebSocket connection (disabled for now - using mock data)
    // websocketStore.connect('ws://localhost:8000/ws');
    
    const { websocketUrl } = get(effectiveConfigStore);
    websocketStore.connect(websocketUrl);
    refreshGenesisDb();
  });
</script>

<main class="crud-app">
  <header class="crud-header">
    <div class="crud-brand">
      <div class="brand-badge">DB</div>
      <div>
        <div class="brand-title">Genesis Data Console</div>
        <div class="brand-subtitle">Schema explorer · CRUD workspace</div>
      </div>
    </div>
    <div class="crud-actions">
      <button class="btn btn-primary">New Record</button>
      <button class="btn" on:click={exportCsv}>Export CSV</button>
      <button class="btn">Settings</button>
    </div>
  </header>

  <section class="crud-body">
    <aside class="crud-sidebar">
      <div class="sidebar-section">
        <h3>Databases</h3>
        <div class="database-card">
          <div class="database-name">{database?.name ?? '—'}</div>
          <div class="database-meta">{database?.description ?? 'No description available.'}</div>
          <div class="database-meta">
            {Object.keys(tables).length} tables · {database?.region ?? 'region unset'}
          </div>
        </div>
      </div>

      <div class="sidebar-section">
        <h3>Tables</h3>
        <ul>
          {#each tableNames as tableName}
            <li>
              <button
                class={`table-pill ${tableName === (selectedTable || genesisDb?.activeTable) ? 'active' : ''}`}
                on:click={() => handleSelectTable(tableName)}
              >
                <span>{tableName}</span>
                <span class="table-count">{tables[tableName]?.rows?.length ?? 0}</span>
              </button>
            </li>
          {/each}
        </ul>
      </div>

      <div class="sidebar-section quick-actions">
        <h3>Quick actions</h3>
        <button class="btn btn-small">Import CSV</button>
        <button class="btn btn-small" on:click={runQuery}>Run Query</button>
        <button class="btn btn-small" on:click={backupGenesisDb}>Backup</button>
      </div>
    </aside>

    <section class="crud-main">
      <div class="query-panel">
        <div class="query-header">
          <div>
            <div class="query-title">Query runner</div>
            <div class="query-subtitle">Execute SQL against GenesisDB entries and logs.</div>
          </div>
          <button class="btn btn-primary" on:click={runQuery} disabled={isQueryRunning}>
            {isQueryRunning ? 'Running...' : 'Run Query'}
          </button>
        </div>
        <textarea
          class="query-input"
          rows="3"
          placeholder="SELECT * FROM entries LIMIT 100"
          bind:value={queryText}
        ></textarea>
        {#if queryStatus || queryError}
          <div class={`query-status ${queryError ? 'error' : ''}`}>
            {queryError || queryStatus}
          </div>
        {/if}
        {#if dataStats}
          <div class="query-meta">
            <span>{dataStats.row_count} rows</span>
            <span>{dataStats.execution_time_ms?.toFixed?.(1) ?? dataStats.execution_time_ms} ms</span>
            {#if dataStats.time_complexity}
              <span>{dataStats.time_complexity}</span>
            {/if}
          </div>
        {/if}
      </div>

      <div class="table-header">
        <div>
          <div class="table-title">{selectedTable || genesisDb?.activeTable || 'Table'}</div>
          <div class="table-meta">{rows.length} records · {columns.length} fields</div>
        </div>
        <div class="table-actions">
          <input class="filter-input" type="text" placeholder="Filter rows" bind:value={filterText} />
          <button class="btn">Filter</button>
          <button class="btn">Columns</button>
        </div>
      </div>

      <div class="table-card">
        <table>
          <thead>
            <tr>
              {#each columns as column}
                <th>{column.name}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each filteredRows as row}
              <tr
                class:selected={rowKey(row, columns) === rowKey(selectedRow, columns)}
                on:click={() => handleSelectRow(row)}
              >
                {#each columns as column}
                  <td>{row?.[column.name] ?? '—'}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>

    <aside class="crud-detail">
      <div class="detail-card">
        <div class="detail-header">
          <h3>Update the selected row in {selectedTable || genesisDb?.activeTable}</h3>
          {#if isDirty}
            <span class="unsaved-badge">Unsaved changes</span>
          {/if}
        </div>
        <div class="detail-fields">
          {#each columns as column}
            <label>
              <span>{column.name.toUpperCase()}</span>
              <input
                type="text"
                bind:value={draftRow[column.name]}
                disabled={column.name === 'entry_index'}
              />
            </label>
          {/each}
        </div>
        <div class="detail-actions">
          <button class="btn btn-primary" on:click={saveRow} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
          <button class="btn">Delete</button>
        </div>
      </div>

      <div class="detail-card info-card">
        <div class="info-item">
          <span>Last updated</span>
          <strong>{formatTimestamp(database?.updated_at)}</strong>
        </div>
        <div class="info-item">
          <span>Active table</span>
          <strong>{selectedTable || genesisDb?.activeTable}</strong>
        </div>
        <div class="info-item">
          <span>Row visibility</span>
          <strong>{filteredRows.length} of {rows.length} rows</strong>
        </div>
        {#if lastQueryTable}
          <div class="info-item">
            <span>Query table</span>
            <strong>{lastQueryTable}</strong>
          </div>
        {/if}
      </div>
    </aside>
  </section>
</main>

<style>
  :global(body) {
    background: #0b1633;
    color: #1f2937;
    overflow: hidden;
  }

  .crud-app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    font-family: 'Inter', system-ui, sans-serif;
  }

  .crud-header {
    background: linear-gradient(90deg, #0f3a5f, #1f5f8b);
    color: #f8fafc;
    padding: 1.25rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 10px 30px rgba(15, 58, 95, 0.25);
  }

  .crud-brand {
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  .brand-badge {
    display: grid;
    place-items: center;
    width: 3rem;
    height: 3rem;
    background: #facc15;
    color: #0f172a;
    border-radius: 0.75rem;
    font-weight: 700;
  }

  .brand-title {
    font-size: 1.125rem;
    font-weight: 600;
  }

  .brand-subtitle {
    font-size: 0.875rem;
    color: rgba(248, 250, 252, 0.8);
  }

  .crud-actions {
    display: flex;
    gap: 0.75rem;
  }

  .btn {
    background: #f8fafc;
    color: #1f2937;
    border: 1px solid #cbd5f5;
    padding: 0.5rem 1rem;
    border-radius: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-primary {
    background: #facc15;
    border-color: #facc15;
    color: #1f2937;
  }

  .btn-small {
    width: 100%;
    text-align: left;
  }

  .crud-body {
    display: grid;
    grid-template-columns: 240px minmax(0, 1fr) 300px;
    gap: 1.5rem;
    padding: 1.5rem 2rem 2rem;
    flex: 1;
    background: radial-gradient(circle at top, rgba(59, 130, 246, 0.2), rgba(15, 23, 42, 0.95) 70%);
  }

  .crud-sidebar,
  .crud-detail {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .sidebar-section h3,
  .detail-card h3 {
    font-size: 0.9rem;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .database-card {
    background: #ffffff;
    padding: 1rem;
    border-radius: 0.75rem;
    box-shadow: 0 10px 20px rgba(15, 23, 42, 0.08);
  }

  .database-name {
    font-weight: 600;
  }

  .database-meta {
    font-size: 0.8rem;
    color: #64748b;
    margin-top: 0.25rem;
  }

  .crud-sidebar ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .table-pill {
    width: 100%;
    border: none;
    background: rgba(255, 255, 255, 0.15);
    color: #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0.8rem;
    border-radius: 0.75rem;
    font-size: 0.9rem;
    cursor: pointer;
  }

  .table-pill.active {
    background: rgba(30, 64, 175, 0.85);
    color: #f8fafc;
  }

  .table-count {
    background: rgba(255, 255, 255, 0.2);
    padding: 0.1rem 0.45rem;
    border-radius: 999px;
    font-size: 0.75rem;
  }

  .quick-actions .btn {
    background: rgba(255, 255, 255, 0.9);
  }

  .crud-main {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .query-panel {
    background: #f8fafc;
    padding: 1rem 1.5rem;
    border-radius: 1rem;
    box-shadow: 0 10px 20px rgba(15, 23, 42, 0.12);
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .query-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .query-title {
    font-size: 1rem;
    font-weight: 700;
    color: #0f172a;
  }

  .query-subtitle {
    font-size: 0.8rem;
    color: #64748b;
  }

  .query-input {
    border: 1px solid #cbd5f5;
    border-radius: 0.75rem;
    padding: 0.75rem;
    font-family: 'JetBrains Mono', 'SFMono-Regular', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.85rem;
    color: #0f172a;
    background: #ffffff;
  }

  .query-status {
    font-size: 0.85rem;
    color: #1f2937;
    background: rgba(15, 23, 42, 0.08);
    padding: 0.5rem 0.75rem;
    border-radius: 0.5rem;
  }

  .query-status.error {
    color: #b91c1c;
    background: rgba(185, 28, 28, 0.1);
  }

  .query-meta {
    display: flex;
    gap: 1rem;
    font-size: 0.8rem;
    color: #475569;
  }

  .table-header {
    background: #f8fafc;
    padding: 1rem 1.5rem;
    border-radius: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 10px 20px rgba(15, 23, 42, 0.12);
  }

  .table-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #0f172a;
  }

  .table-meta {
    font-size: 0.85rem;
    color: #64748b;
  }

  .table-actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  .filter-input {
    border: 1px solid #cbd5f5;
    padding: 0.4rem 0.75rem;
    border-radius: 0.5rem;
    min-width: 200px;
  }

  .table-card {
    background: #f8fafc;
    border-radius: 1rem;
    padding: 0.5rem;
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.15);
    overflow: hidden;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  thead th {
    text-align: left;
    padding: 0.8rem 1rem;
    color: #0f172a;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    border-bottom: 1px solid #e2e8f0;
  }

  tbody td {
    padding: 0.85rem 1rem;
    color: #1e293b;
    border-bottom: 1px solid #e2e8f0;
  }

  tbody tr {
    cursor: pointer;
  }

  tbody tr.selected {
    background: rgba(59, 130, 246, 0.12);
  }

  .detail-card {
    background: #f8fafc;
    border-radius: 1.25rem;
    padding: 1.25rem;
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.2);
  }

  .detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .detail-header h3 {
    margin-bottom: 0;
  }

  .unsaved-badge {
    background: rgba(245, 158, 11, 0.15);
    color: #b45309;
    padding: 0.2rem 0.5rem;
    border-radius: 999px;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    white-space: nowrap;
  }

  .detail-fields {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
  }

  .detail-fields label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.7rem;
    color: #64748b;
    letter-spacing: 0.08em;
  }

  .detail-fields input {
    border: 1px solid #cbd5f5;
    padding: 0.5rem 0.75rem;
    border-radius: 0.6rem;
    font-size: 0.9rem;
    color: #0f172a;
    background: #ffffff;
  }

  .detail-actions {
    margin-top: 1rem;
    display: flex;
    gap: 0.75rem;
  }

  .info-card {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    font-size: 0.85rem;
    color: #475569;
  }

  .info-item {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .info-item strong {
    color: #0f172a;
    font-size: 1rem;
  }
</style>
