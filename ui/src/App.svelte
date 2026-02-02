<script>
  const databases = [
    {
      name: 'genesis_core',
      tables: [
        {
          name: 'users',
          rows: [
            { id: 1, name: 'Ada Lovelace', role: 'admin', status: 'active', last_login: '2024-04-12 14:32' },
            { id: 2, name: 'Grace Hopper', role: 'editor', status: 'active', last_login: '2024-04-10 09:17' },
            { id: 3, name: 'Alan Turing', role: 'viewer', status: 'suspended', last_login: '2024-03-29 18:42' },
            { id: 4, name: 'Katherine Johnson', role: 'editor', status: 'active', last_login: '2024-04-13 08:05' },
            { id: 5, name: 'Margaret Hamilton', role: 'admin', status: 'active', last_login: '2024-04-11 22:19' }
          ]
        },
        {
          name: 'orders',
          rows: [
            { id: 941, customer: 'Orion Labs', total: '$2,480.00', status: 'processing', updated_at: '2024-04-12 10:11' },
            { id: 942, customer: 'Kepler Systems', total: '$7,104.00', status: 'fulfilled', updated_at: '2024-04-11 16:28' },
            { id: 943, customer: 'Sagan Corp', total: '$980.00', status: 'on hold', updated_at: '2024-04-09 09:42' },
            { id: 944, customer: 'Nova Harbor', total: '$1,920.00', status: 'processing', updated_at: '2024-04-13 12:31' },
            { id: 945, customer: 'Aurora Insight', total: '$4,320.00', status: 'fulfilled', updated_at: '2024-04-12 15:54' }
          ]
        },
        {
          name: 'audit_logs',
          rows: [
            { id: 201, actor: 'system', action: 'backup', severity: 'info', timestamp: '2024-04-12 02:00' },
            { id: 202, actor: 'Ada Lovelace', action: 'user_update', severity: 'warning', timestamp: '2024-04-12 14:38' },
            { id: 203, actor: 'Grace Hopper', action: 'export', severity: 'info', timestamp: '2024-04-10 11:02' },
            { id: 204, actor: 'system', action: 'schema_migration', severity: 'critical', timestamp: '2024-04-09 20:25' },
            { id: 205, actor: 'Alan Turing', action: 'login_failed', severity: 'warning', timestamp: '2024-04-08 07:49' }
          ]
        }
      ]
    }
  ];

  let activeDatabase = databases[0];
  let activeTable = activeDatabase.tables[0];
  let search = '';
  let selectedRow = activeTable.rows[0];

  const setActiveTable = (table) => {
    activeTable = table;
    selectedRow = table.rows[0];
    search = '';
  };

  $: columns = activeTable.rows.length ? Object.keys(activeTable.rows[0]) : [];
  $: filteredRows = activeTable.rows.filter((row) =>
    Object.values(row).some((value) =>
      String(value).toLowerCase().includes(search.toLowerCase())
    )
  );
</script>

<main class="crud-app">
  <header class="crud-header">
    <div class="crud-brand">
      <span class="brand-badge">DB</span>
      <div>
        <p class="brand-title">Genesis Data Console</p>
        <p class="brand-subtitle">Schema explorer · CRUD workspace</p>
      </div>
    </div>
    <div class="crud-actions">
      <button class="btn btn-primary">New Record</button>
      <button class="btn">Export</button>
      <button class="btn">Settings</button>
    </div>
  </header>

  <div class="crud-body">
    <aside class="crud-sidebar">
      <div class="sidebar-section">
        <h3>Databases</h3>
        <div class="database-card">
          <p class="database-name">{activeDatabase.name}</p>
          <p class="database-meta">12 tables · 3.4 GB</p>
        </div>
      </div>

      <div class="sidebar-section">
        <h3>Tables</h3>
        <ul>
          {#each activeDatabase.tables as table}
            <li>
              <button
                type="button"
                class:selected={table.name === activeTable.name}
                on:click={() => setActiveTable(table)}
              >
                <span>{table.name}</span>
                <span class="table-count">{table.rows.length}</span>
              </button>
            </li>
          {/each}
        </ul>
      </div>

      <div class="sidebar-section">
        <h3>Quick Actions</h3>
        <div class="sidebar-actions">
          <button class="btn btn-small">Import CSV</button>
          <button class="btn btn-small">Run Query</button>
          <button class="btn btn-small">Backup</button>
        </div>
      </div>
    </aside>

    <section class="crud-main">
      <div class="toolbar">
        <div>
          <p class="toolbar-title">Table: {activeTable.name}</p>
          <p class="toolbar-subtitle">{filteredRows.length} records · {columns.length} fields</p>
        </div>
        <div class="toolbar-actions">
          <input class="search" type="search" placeholder="Filter rows" bind:value={search} />
          <button class="btn">Filter</button>
          <button class="btn">Columns</button>
        </div>
      </div>

      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              {#each columns as column}
                <th>{column}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each filteredRows as row}
              <tr class:selected={row.id === selectedRow?.id} on:click={() => (selectedRow = row)}>
                {#each columns as column}
                  <td>{row[column]}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>

    <aside class="crud-detail">
      <div class="detail-card">
        <h3>Record Editor</h3>
        <p class="detail-subtitle">Update the selected row in {activeTable.name}</p>
        {#if selectedRow}
          {#each columns as column}
            <label>
              <span>{column}</span>
              <input type="text" value={selectedRow[column]} readonly />
            </label>
          {/each}
          <div class="detail-actions">
            <button class="btn btn-primary">Save Changes</button>
            <button class="btn">Delete</button>
          </div>
        {:else}
          <p class="empty">Select a record to view details.</p>
        {/if}
      </div>

      <div class="detail-card">
        <h3>Table Insights</h3>
        <ul class="insights">
          <li>
            <span>Primary Key</span>
            <strong>id</strong>
          </li>
          <li>
            <span>Last optimized</span>
            <strong>2024-04-10</strong>
          </li>
          <li>
            <span>Storage</span>
            <strong>128 MB</strong>
          </li>
          <li>
            <span>Replication</span>
            <strong>Healthy</strong>
          </li>
        </ul>
      </div>
    </aside>
  </div>
</main>

<style>
  :global(body) {
    background: #e7edf3;
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
    grid-template-columns: 240px 1fr 280px;
    gap: 1.5rem;
    padding: 1.5rem 2rem 2rem;
    flex: 1;
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
  }

  .crud-sidebar ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .crud-sidebar button {
    width: 100%;
    border: 1px solid transparent;
    background: #f8fafc;
    padding: 0.65rem 0.75rem;
    border-radius: 0.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.9rem;
    cursor: pointer;
  }

  .crud-sidebar button.selected {
    background: #1f5f8b;
    color: #f8fafc;
    border-color: #1f5f8b;
  }

  .table-count {
    font-size: 0.75rem;
    background: rgba(15, 23, 42, 0.1);
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
  }

  .crud-sidebar button.selected .table-count {
    background: rgba(248, 250, 252, 0.3);
  }

  .sidebar-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .crud-main {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #ffffff;
    padding: 1rem 1.25rem;
    border-radius: 0.75rem;
    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
  }

  .toolbar-title {
    font-weight: 600;
  }

  .toolbar-subtitle {
    font-size: 0.85rem;
    color: #64748b;
  }

  .toolbar-actions {
    display: flex;
    gap: 0.75rem;
    align-items: center;
  }

  .search {
    padding: 0.5rem 0.75rem;
    border-radius: 0.5rem;
    border: 1px solid #cbd5f5;
    min-width: 200px;
  }

  .table-wrapper {
    background: #ffffff;
    border-radius: 0.75rem;
    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
    overflow: hidden;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }

  thead {
    background: #f1f5f9;
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.04em;
  }

  th,
  td {
    padding: 0.75rem 1rem;
    text-align: left;
  }

  tbody tr {
    border-top: 1px solid #e2e8f0;
    cursor: pointer;
  }

  tbody tr.selected {
    background: rgba(59, 130, 246, 0.12);
  }

  .crud-detail .detail-card {
    background: #ffffff;
    padding: 1.25rem;
    border-radius: 0.75rem;
    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .detail-subtitle {
    font-size: 0.85rem;
    color: #64748b;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.8rem;
    color: #475569;
  }

  label input {
    border: 1px solid #cbd5f5;
    border-radius: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: #f8fafc;
  }

  .detail-actions {
    display: flex;
    gap: 0.75rem;
  }

  .insights {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.75rem;
  }

  .insights li {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
  }

  .empty {
    color: #94a3b8;
    font-size: 0.9rem;
  }
</style>
