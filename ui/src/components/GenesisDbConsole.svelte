<script>
  import { dataStore } from '../stores/websocket.js';

  let filterText = '';
  let selectedTable = '';
  let selectedRowId = '';

  $: genesisDb = $dataStore?.genesisDb ?? { database: null, tables: {}, activeTable: null, selectedRow: null };
  $: tables = genesisDb.tables ? Object.entries(genesisDb.tables) : [];
  $: defaultTableName = genesisDb.activeTable || (tables[0] ? tables[0][0] : '');
  $: activeTableName = selectedTable || defaultTableName;
  $: activeTable = genesisDb.tables?.[activeTableName] ?? { columns: [], rows: [] };
  $: rows = activeTable.rows ?? [];
  $: columns = activeTable.columns ?? [];
  $: tableSummary = `${rows.length} records · ${columns.length} fields`;
  $: filteredRows = rows.filter((row) => {
    if (!filterText) return true;
    return JSON.stringify(row).toLowerCase().includes(filterText.toLowerCase());
  });

  $: if (!selectedTable && defaultTableName) {
    selectedTable = defaultTableName;
  }

  $: if (!selectedRowId && rows[0]?.id) {
    selectedRowId = rows[0].id;
  }

  $: selectedRow = rows.find((row) => row.id === selectedRowId) ?? rows[0] ?? {};

  const formatColumnLabel = (name) => name.replace(/_/g, ' ');
</script>

<section class="console-shell">
  <header class="console-header">
    <div class="brand">
      <div class="brand-badge">DB</div>
      <div>
        <div class="brand-title">Genesis Data Console</div>
        <div class="brand-subtitle">Schema explorer · CRUD workspace</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn btn-primary">New Record</button>
      <button class="btn">Export</button>
      <button class="btn">Settings</button>
    </div>
  </header>

  <div class="console-body">
    <aside class="sidebar">
      <section class="sidebar-section">
        <h3>Databases</h3>
        <div class="database-card">
          <div class="database-name">{genesisDb.database?.name ?? 'GenesisDB'}</div>
          <div class="database-meta">
            {genesisDb.database?.description ?? 'Unified operational storage'}
          </div>
          <div class="database-meta">
            {tables.length} tables · {genesisDb.database?.region ?? 'global'}
          </div>
        </div>
      </section>

      <section class="sidebar-section">
        <h3>Tables</h3>
        <ul class="table-list">
          {#each tables as [tableName, tableData]}
            <li>
              <button
                class:active={tableName === activeTableName}
                on:click={() => {
                  selectedTable = tableName;
                  selectedRowId = tableData.rows?.[0]?.id ?? '';
                }}
              >
                <span>{tableName}</span>
                <span class="table-count">{tableData.rows?.length ?? 0}</span>
              </button>
            </li>
          {/each}
        </ul>
      </section>

      <section class="sidebar-section">
        <h3>Quick Actions</h3>
        <div class="quick-actions">
          <button class="btn btn-soft">Import CSV</button>
          <button class="btn btn-soft">Run Query</button>
          <button class="btn btn-soft">Backup</button>
        </div>
      </section>
    </aside>

    <main class="data-panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">{activeTableName}</div>
          <div class="panel-subtitle">{tableSummary}</div>
        </div>
        <div class="panel-controls">
          <input
            class="filter-input"
            type="text"
            placeholder="Filter rows"
            bind:value={filterText}
          />
          <button class="btn btn-outline">Filter</button>
          <button class="btn btn-outline">Columns</button>
        </div>
      </div>

      <div class="table-wrapper">
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
              <tr class:selected={row.id === selectedRowId} on:click={() => (selectedRowId = row.id)}>
                {#each columns as column}
                  <td>{row[column.name]}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </main>

    <aside class="detail-panel">
      <div class="detail-card">
        <h3>Record Editor</h3>
        <p class="detail-subtitle">Update the selected row in {activeTableName}</p>
        <div class="form-grid">
          {#each columns as column}
            <label>
              <span>{formatColumnLabel(column.name)}</span>
              <input type="text" value={selectedRow?.[column.name] ?? ''} readonly />
            </label>
          {/each}
        </div>
        <div class="detail-actions">
          <button class="btn btn-primary">Save Changes</button>
          <button class="btn btn-outline">Delete</button>
        </div>
      </div>

      <div class="detail-card">
        <h3>Table Insights</h3>
        <ul class="insights">
          <li>
            <span class="insight-label">Last updated</span>
            <span>{genesisDb.database?.updated_at ? new Date(genesisDb.database.updated_at).toLocaleString() : 'Just now'}</span>
          </li>
          <li>
            <span class="insight-label">Active table</span>
            <span>{activeTableName}</span>
          </li>
          <li>
            <span class="insight-label">Row visibility</span>
            <span>{filteredRows.length} of {rows.length} rows</span>
          </li>
        </ul>
      </div>
    </aside>
  </div>
</section>

<style>
  .console-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: radial-gradient(circle at top left, #1b4f7a, #0c1b3a 55%, #050512 100%);
    color: #f8fafc;
    font-family: 'Inter', system-ui, sans-serif;
  }

  .console-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem 2.5rem;
    background: linear-gradient(90deg, #0f3a5f, #1f5f8b);
    box-shadow: 0 12px 30px rgba(12, 20, 50, 0.45);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .brand-badge {
    width: 3rem;
    height: 3rem;
    border-radius: 0.75rem;
    display: grid;
    place-items: center;
    background: #facc15;
    color: #0b1220;
    font-weight: 700;
  }

  .brand-title {
    font-weight: 600;
    font-size: 1.1rem;
  }

  .brand-subtitle {
    font-size: 0.85rem;
    color: rgba(248, 250, 252, 0.7);
  }

  .header-actions {
    display: flex;
    gap: 0.75rem;
  }

  .btn {
    border: 1px solid rgba(148, 163, 184, 0.5);
    background: rgba(248, 250, 252, 0.9);
    color: #0f172a;
    padding: 0.55rem 1.1rem;
    border-radius: 0.7rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-primary {
    background: #facc15;
    border-color: #facc15;
  }

  .btn-soft {
    width: 100%;
    text-align: left;
    background: rgba(248, 250, 252, 0.95);
  }

  .btn-outline {
    background: rgba(15, 23, 42, 0.15);
    color: #f8fafc;
    border-color: rgba(148, 163, 184, 0.4);
  }

  .console-body {
    display: grid;
    grid-template-columns: 240px minmax(0, 1fr) 300px;
    gap: 1.75rem;
    padding: 2rem 2.5rem 2.5rem;
    flex: 1;
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 1.75rem;
  }

  .sidebar-section h3,
  .detail-card h3 {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.75rem;
    font-weight: 600;
    color: rgba(248, 250, 252, 0.7);
    margin-bottom: 0.85rem;
  }

  .database-card {
    background: #f8fafc;
    color: #0f172a;
    padding: 1rem;
    border-radius: 0.9rem;
    box-shadow: 0 15px 30px rgba(15, 23, 42, 0.3);
  }

  .database-meta {
    font-size: 0.8rem;
    color: #64748b;
    margin-top: 0.3rem;
  }

  .table-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.5rem;
  }

  .table-list button {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.65rem 0.9rem;
    border-radius: 0.75rem;
    border: none;
    background: rgba(15, 23, 42, 0.5);
    color: #e2e8f0;
    font-weight: 600;
    cursor: pointer;
  }

  .table-list button.active {
    background: #1f5f8b;
  }

  .table-count {
    background: rgba(248, 250, 252, 0.25);
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    font-size: 0.75rem;
  }

  .quick-actions {
    display: grid;
    gap: 0.6rem;
  }

  .data-panel {
    display: flex;
    flex-direction: column;
    gap: 1.2rem;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(248, 250, 252, 0.95);
    color: #0f172a;
    padding: 1rem 1.5rem;
    border-radius: 0.9rem;
  }

  .panel-title {
    font-size: 1rem;
    font-weight: 600;
  }

  .panel-subtitle {
    font-size: 0.8rem;
    color: #64748b;
  }

  .panel-controls {
    display: flex;
    gap: 0.6rem;
    align-items: center;
  }

  .filter-input {
    padding: 0.55rem 0.9rem;
    border-radius: 0.6rem;
    border: 1px solid rgba(148, 163, 184, 0.4);
    min-width: 220px;
  }

  .table-wrapper {
    background: rgba(248, 250, 252, 0.97);
    border-radius: 1rem;
    padding: 0.8rem;
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.35);
    overflow: hidden;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    color: #0f172a;
  }

  thead {
    background: #e2e8f0;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
  }

  th,
  td {
    padding: 0.75rem 0.7rem;
    text-align: left;
  }

  tbody tr {
    border-bottom: 1px solid rgba(148, 163, 184, 0.3);
    cursor: pointer;
  }

  tbody tr.selected {
    background: rgba(191, 219, 254, 0.55);
  }

  .detail-panel {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .detail-card {
    background: #f8fafc;
    color: #0f172a;
    padding: 1.2rem;
    border-radius: 1rem;
    box-shadow: 0 18px 35px rgba(15, 23, 42, 0.3);
  }

  .detail-subtitle {
    margin: 0.4rem 0 1rem;
    color: #64748b;
    font-size: 0.85rem;
  }

  .form-grid {
    display: grid;
    gap: 0.75rem;
  }

  label span {
    display: block;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #475569;
    margin-bottom: 0.35rem;
  }

  input {
    width: 100%;
    padding: 0.55rem 0.75rem;
    border-radius: 0.6rem;
    border: 1px solid rgba(148, 163, 184, 0.5);
    background: rgba(248, 250, 252, 0.98);
  }

  .detail-actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.2rem;
  }

  .insights {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.75rem;
  }

  .insight-label {
    display: block;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748b;
  }

  @media (max-width: 1100px) {
    .console-body {
      grid-template-columns: 1fr;
    }

    .detail-panel {
      flex-direction: row;
      flex-wrap: wrap;
    }

    .detail-card {
      flex: 1 1 260px;
    }
  }
</style>
