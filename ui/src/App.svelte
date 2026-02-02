<script>
  import { onMount } from 'svelte';
  import BrainSpace from './components/BrainSpace.svelte';
  import ControlPanel from './components/ControlPanel.svelte';
  import ChatBar from './components/ChatBar.svelte';
  import { websocketStore } from './stores/websocket.js';

  const dataTypes = ['uuid', 'text', 'varchar', 'integer', 'boolean', 'timestamp', 'jsonb'];

  const mockActiveSchema = {
    tables: [
      {
        name: 'users',
        columns: [
          {
            name: 'id',
            type: 'uuid',
            nullable: false,
            default: 'gen_random_uuid()',
            primaryKey: true,
            index: true
          },
          {
            name: 'email',
            type: 'varchar',
            nullable: false,
            default: '',
            primaryKey: false,
            index: true
          },
          {
            name: 'created_at',
            type: 'timestamp',
            nullable: false,
            default: 'now()',
            primaryKey: false,
            index: false
          }
        ],
        indexes: [
          {
            name: 'users_email_unique',
            columns: ['email'],
            unique: true
          }
        ]
      },
      {
        name: 'orders',
        columns: [
          {
            name: 'id',
            type: 'uuid',
            nullable: false,
            default: 'gen_random_uuid()',
            primaryKey: true,
            index: true
          },
          {
            name: 'user_id',
            type: 'uuid',
            nullable: false,
            default: '',
            primaryKey: false,
            index: true
          },
          {
            name: 'status',
            type: 'text',
            nullable: false,
            default: "'pending'",
            primaryKey: false,
            index: false
          }
        ],
        indexes: [
          {
            name: 'orders_user_id_idx',
            columns: ['user_id'],
            unique: false
          }
        ]
      }
    ]
  };

  const deepClone = (value) => JSON.parse(JSON.stringify(value));

  let activeSchema = deepClone(mockActiveSchema);
  let schemaDraft = deepClone(mockActiveSchema);
  let generatedSql = '';

  const diffSchemas = (active, draft) => {
    const changes = [];
    const activeTables = new Map(active.tables.map((table) => [table.name, table]));
    const draftTables = new Map(draft.tables.map((table) => [table.name, table]));

    for (const [name] of draftTables) {
      if (!activeTables.has(name)) {
        changes.push({ type: 'create', entity: 'table', table: name });
      }
    }

    for (const [name] of activeTables) {
      if (!draftTables.has(name)) {
        changes.push({ type: 'drop', entity: 'table', table: name });
      }
    }

    for (const [name, draftTable] of draftTables) {
      const activeTable = activeTables.get(name);
      if (!activeTable) continue;

      const activeColumns = new Map(activeTable.columns.map((column) => [column.name, column]));
      const draftColumns = new Map(draftTable.columns.map((column) => [column.name, column]));

      for (const [columnName, column] of draftColumns) {
        if (!activeColumns.has(columnName)) {
          changes.push({ type: 'create', entity: 'column', table: name, column: columnName });
        } else {
          const activeColumn = activeColumns.get(columnName);
          const updates = [];
          if (column.type !== activeColumn.type) updates.push('type');
          if (column.nullable !== activeColumn.nullable) updates.push('nullable');
          if ((column.default || '') !== (activeColumn.default || '')) updates.push('default');
          if (column.primaryKey !== activeColumn.primaryKey) updates.push('primary key');
          if (column.index !== activeColumn.index) updates.push('index');

          if (updates.length) {
            changes.push({
              type: 'alter',
              entity: 'column',
              table: name,
              column: columnName,
              updates
            });
          }
        }
      }

      for (const [columnName] of activeColumns) {
        if (!draftColumns.has(columnName)) {
          changes.push({ type: 'drop', entity: 'column', table: name, column: columnName });
        }
      }

      if (JSON.stringify(activeTable.indexes) !== JSON.stringify(draftTable.indexes)) {
        changes.push({ type: 'alter', entity: 'indexes', table: name });
      }
    }

    return changes;
  };

  const formatChange = (change) => {
    if (change.entity === 'table') {
      return `${change.type === 'create' ? 'Create' : 'Drop'} table ${change.table}`;
    }
    if (change.entity === 'column') {
      if (change.type === 'create') return `Add column ${change.table}.${change.column}`;
      if (change.type === 'drop') return `Drop column ${change.table}.${change.column}`;
      return `Alter column ${change.table}.${change.column} (${change.updates.join(', ')})`;
    }
    return `Update indexes for ${change.table}`;
  };

  const generateSqlStatement = (change) => {
    if (change.entity === 'table') {
      if (change.type === 'create') {
        return `CREATE TABLE ${change.table} (...);`;
      }
      return `DROP TABLE ${change.table};`;
    }
    if (change.entity === 'column') {
      if (change.type === 'create') {
        return `ALTER TABLE ${change.table} ADD COLUMN ${change.column} ...;`;
      }
      if (change.type === 'drop') {
        return `ALTER TABLE ${change.table} DROP COLUMN ${change.column};`;
      }
      return `ALTER TABLE ${change.table} ALTER COLUMN ${change.column}; -- ${change.updates.join(', ')}`;
    }
    return `-- Review indexes for ${change.table}`;
  };

  const getIndexSummary = (table) => {
    const summaries = table.indexes.map((index) => ({
      name: index.name,
      columns: index.columns.join(', '),
      unique: index.unique
    }));
    const columnIndexes = table.columns.filter((column) => column.index).map((column) => column.name);
    if (columnIndexes.length) {
      summaries.unshift({
        name: `${table.name}_column_idx`,
        columns: columnIndexes.join(', '),
        unique: false
      });
    }
    return summaries;
  };

  $: pendingChanges = diffSchemas(activeSchema, schemaDraft);

  const addTable = () => {
    const newTableCount = schemaDraft.tables.length + 1;
    schemaDraft = {
      ...schemaDraft,
      tables: [
        ...schemaDraft.tables,
        {
          name: `new_table_${newTableCount}`,
          columns: [
            {
              name: 'id',
              type: 'uuid',
              nullable: false,
              default: 'gen_random_uuid()',
              primaryKey: true,
              index: true
            }
          ],
          indexes: []
        }
      ]
    };
  };

  const removeTable = (tableIndex) => {
    schemaDraft = {
      ...schemaDraft,
      tables: schemaDraft.tables.filter((_, index) => index !== tableIndex)
    };
  };

  const updateTableName = (tableIndex, value) => {
    schemaDraft = {
      ...schemaDraft,
      tables: schemaDraft.tables.map((table, index) =>
        index === tableIndex ? { ...table, name: value } : table
      )
    };
  };

  const addColumn = (tableIndex) => {
    schemaDraft = {
      ...schemaDraft,
      tables: schemaDraft.tables.map((table, index) => {
        if (index !== tableIndex) return table;
        return {
          ...table,
          columns: [
            ...table.columns,
            {
              name: `column_${table.columns.length + 1}`,
              type: dataTypes[1],
              nullable: true,
              default: '',
              primaryKey: false,
              index: false
            }
          ]
        };
      })
    };
  };

  const removeColumn = (tableIndex, columnIndex) => {
    schemaDraft = {
      ...schemaDraft,
      tables: schemaDraft.tables.map((table, index) => {
        if (index !== tableIndex) return table;
        return {
          ...table,
          columns: table.columns.filter((_, colIndex) => colIndex !== columnIndex)
        };
      })
    };
  };

  const updateColumn = (tableIndex, columnIndex, field, value) => {
    schemaDraft = {
      ...schemaDraft,
      tables: schemaDraft.tables.map((table, index) => {
        if (index !== tableIndex) return table;
        return {
          ...table,
          columns: table.columns.map((column, colIndex) =>
            colIndex === columnIndex ? { ...column, [field]: value } : column
          )
        };
      })
    };
  };

  const applyChanges = () => {
    activeSchema = deepClone(schemaDraft);
    generatedSql = '';
  };

  const discardChanges = () => {
    schemaDraft = deepClone(activeSchema);
    generatedSql = '';
  };

  const generateSql = () => {
    if (!pendingChanges.length) {
      generatedSql = '-- No changes to apply.';
      return;
    }
    generatedSql = pendingChanges.map(generateSqlStatement).join('\n');
  };
  
  onMount(() => {
    console.log('🎨 App.svelte mounted');
    
    // Initialize WebSocket connection (disabled for now - using mock data)
    // websocketStore.connect('ws://localhost:8000/ws');
    
    console.log('📊 Setting mock data...');
    // Generate realistic memory brain data at scale
    // Each cluster represents a proto-identity with multiple memories
    const numClusters = 1000; // Number of proto-identities
    const clusters = [];
    const allMemories = []; // Flat list of all memory points for point cloud
    
    for (let i = 0; i < numClusters; i++) {
      // Each cluster has a centroid (proto-identity location)
      const centroid = [
        (Math.random() - 0.5) * 20,
        (Math.random() - 0.5) * 20,
        (Math.random() - 0.5) * 20
      ];
      
      // Each cluster contains multiple memories (memory_ids)
      // Realistic distribution: some clusters have many memories, some have few
      const memoryCount = Math.floor(Math.random() * 50) + 5; // 5-55 memories per cluster
      const memoryIds = Array.from({ length: memoryCount }, (_, j) => allMemories.length + j);
      
      // Generate memory points around the cluster centroid
      // Memories cluster around their proto-identity with some variance
      for (let m = 0; m < memoryCount; m++) {
        // Gaussian-like distribution around centroid
        const angle1 = Math.random() * Math.PI * 2;
        const angle2 = Math.random() * Math.PI;
        const radius = Math.random() * 2.0 + 0.5; // 0.5-2.5 units from centroid
        
        const memoryPos = [
          centroid[0] + Math.cos(angle1) * Math.sin(angle2) * radius,
          centroid[1] + Math.sin(angle1) * Math.sin(angle2) * radius,
          centroid[2] + Math.cos(angle2) * radius
        ];
        
        allMemories.push({
          memory_id: memoryIds[m],
          cluster_id: i,
          identity_id: i % 5, // 5 different identity types
          position: memoryPos,
          coherence: 0.7 + Math.random() * 0.3, // 0.7-1.0
          timestamp: Date.now() - Math.random() * 1000000
        });
      }
      
      clusters.push({
        cluster_id: i,
        identity_id: i % 5,
        centroid: centroid,
        memory_ids: memoryIds,
        memory_count: memoryCount,
        coherence: 0.8 + Math.random() * 0.2, // Cluster coherence
        metadata: {
          created_at: Date.now() - Math.random() * 2000000,
          access_count: Math.floor(Math.random() * 100)
        }
      });
    }
    
    console.log(`📦 Generated ${clusters.length} clusters with ${allMemories.length} total memories`);
    
    const mockData = {
      brainSpace: {
        clusters: clusters,
        memories: allMemories // Full point cloud data
      },
      activation: {
        waveform: Array.from({ length: 512 }, (_, i) => 
          Math.sin(i * 0.1) * (1 - Math.abs(i - 256) / 256) * 0.5
        ),
        sparks: Array.from({ length: 5 }, () => ({
          x: Math.random() * 512,
          y: Math.random() * 512,
          intensity: Math.random()
        })),
        energy: 0.7,
        morphism: 'gamma'
      },
      controls: {
        current_cycle: 'active',
        morphism_state: 'gamma',
        coherence: 0.85,
        gamma_params: { amplitude: 100.0 },
        tau_params: { projection_strength: 0.8 }
      },
      events: []
    };
    
    websocketStore.data.set(mockData);
    websocketStore.connected.set(true);
    console.log('✅ Mock data set, connected state: true');
    console.log('📦 Mock clusters:', mockData.brainSpace.clusters.length);
  });
</script>

<main class="h-screen w-screen flex flex-col relative">
  <!-- Main 3D Brain Space -->
  <div class="flex-1 relative">
    <BrainSpace />
  </div>
  
  <!-- Control Panel (Right Sidebar) -->
  <ControlPanel />

  <!-- Schema Editor (Right Panel) -->
  <section class="schema-editor">
    <header class="schema-header">
      <div>
        <h2 class="text-lg font-semibold text-white">Schema Editor</h2>
        <p class="text-xs text-slate-300">Draft changes are separate from the active schema.</p>
      </div>
      <div class="schema-actions">
        <button class="schema-button primary" on:click={applyChanges}>Apply Changes</button>
        <button class="schema-button" on:click={discardChanges}>Discard Changes</button>
        <button class="schema-button" on:click={generateSql}>Generate SQL</button>
      </div>
    </header>

    <div class="schema-body">
      <div class="schema-panel">
        <div class="schema-panel-header">
          <h3 class="text-sm font-semibold text-genesis-cyan">Schema Draft</h3>
          <button class="schema-button subtle" on:click={addTable}>Add Table</button>
        </div>

        {#each schemaDraft.tables as table, tableIndex}
          <div class="schema-card">
            <div class="schema-card-header">
              <input
                class="schema-input"
                value={table.name}
                on:input={(event) => updateTableName(tableIndex, event.target.value)}
              />
              <button class="schema-button danger" on:click={() => removeTable(tableIndex)}>Remove</button>
            </div>

            <div class="schema-columns">
              <div class="schema-columns-header">
                <span>Name</span>
                <span>Type</span>
                <span>Nullable</span>
                <span>Default</span>
                <span>PK</span>
                <span>Index</span>
                <span></span>
              </div>

              {#each table.columns as column, columnIndex}
                <div class="schema-column-row">
                  <input
                    class="schema-input"
                    value={column.name}
                    on:input={(event) => updateColumn(tableIndex, columnIndex, 'name', event.target.value)}
                  />
                  <select
                    class="schema-select"
                    value={column.type}
                    on:change={(event) => updateColumn(tableIndex, columnIndex, 'type', event.target.value)}
                  >
                    {#each dataTypes as dataType}
                      <option value={dataType}>{dataType}</option>
                    {/each}
                  </select>
                  <input
                    type="checkbox"
                    checked={column.nullable}
                    on:change={(event) => updateColumn(tableIndex, columnIndex, 'nullable', event.target.checked)}
                  />
                  <input
                    class="schema-input"
                    value={column.default}
                    placeholder="default"
                    on:input={(event) => updateColumn(tableIndex, columnIndex, 'default', event.target.value)}
                  />
                  <input
                    type="checkbox"
                    checked={column.primaryKey}
                    on:change={(event) => updateColumn(tableIndex, columnIndex, 'primaryKey', event.target.checked)}
                  />
                  <input
                    type="checkbox"
                    checked={column.index}
                    on:change={(event) => updateColumn(tableIndex, columnIndex, 'index', event.target.checked)}
                  />
                  <button class="schema-button danger" on:click={() => removeColumn(tableIndex, columnIndex)}>
                    Remove
                  </button>
                </div>
              {/each}
            </div>

            <div class="schema-card-footer">
              <button class="schema-button subtle" on:click={() => addColumn(tableIndex)}>Add Column</button>
              <div class="schema-indexes">
                <div class="text-xs uppercase tracking-wide text-slate-400">Indexes</div>
                {#each getIndexSummary(table) as indexInfo}
                  <div class="text-xs text-slate-300">
                    {indexInfo.name} ({indexInfo.columns}) {indexInfo.unique ? 'unique' : ''}
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {/each}
      </div>

      <div class="schema-panel">
        <div class="schema-panel-header">
          <h3 class="text-sm font-semibold text-genesis-cyan">Active Schema</h3>
          <span class="text-xs text-slate-400">Read-only snapshot</span>
        </div>
        {#each activeSchema.tables as table}
          <div class="schema-card muted">
            <div class="schema-card-header">
              <div class="text-sm text-white">{table.name}</div>
            </div>
            <div class="schema-columns">
              {#each table.columns as column}
                <div class="schema-column-summary">
                  <div>{column.name}</div>
                  <div class="text-slate-400">{column.type}</div>
                  <div class="text-slate-400">{column.nullable ? 'NULL' : 'NOT NULL'}</div>
                  <div class="text-slate-400">{column.default || '—'}</div>
                  <div class="text-slate-400">{column.primaryKey ? 'PK' : ''}</div>
                  <div class="text-slate-400">{column.index ? 'IDX' : ''}</div>
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </div>

      <div class="schema-panel">
        <div class="schema-panel-header">
          <h3 class="text-sm font-semibold text-genesis-cyan">Pending Changes</h3>
          <span class="text-xs text-slate-400">{pendingChanges.length} changes</span>
        </div>
        {#if pendingChanges.length}
          <ul class="schema-changes">
            {#each pendingChanges as change}
              <li class="schema-change-item">
                <span class="schema-badge {change.type}">{change.type}</span>
                <span>{formatChange(change)}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="text-xs text-slate-400">No pending changes. Draft matches active schema.</p>
        {/if}

        <div class="schema-sql">
          <div class="text-xs uppercase tracking-wide text-slate-400 mb-2">Generated SQL</div>
          <textarea class="schema-textarea" bind:value={generatedSql} readonly placeholder="SQL output will appear here."></textarea>
        </div>
      </div>
    </div>
  </section>
  
  <!-- Chat Bar (Bottom) -->
  <ChatBar />
</main>

<style>
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

  .schema-editor {
    position: fixed;
    right: 340px;
    top: 24px;
    bottom: 120px;
    width: 520px;
    z-index: 14;
    display: flex;
    flex-direction: column;
    background: rgba(8, 16, 32, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    backdrop-filter: blur(12px);
    color: #e2e8f0;
    padding: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  }

  .schema-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
  }

  .schema-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .schema-body {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    overflow: hidden;
    height: 100%;
  }

  .schema-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    background: rgba(12, 22, 40, 0.65);
    border-radius: 12px;
    padding: 12px;
    overflow-y: auto;
  }

  .schema-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .schema-card {
    background: rgba(15, 25, 45, 0.8);
    border-radius: 10px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .schema-card.muted {
    background: rgba(8, 14, 28, 0.7);
  }

  .schema-card-header {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    align-items: center;
  }

  .schema-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }

  .schema-indexes {
    display: flex;
    flex-direction: column;
    gap: 4px;
    text-align: right;
  }

  .schema-columns {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .schema-columns-header {
    display: grid;
    grid-template-columns: 1.2fr 1fr 0.6fr 1.2fr 0.5fr 0.6fr 0.8fr;
    gap: 6px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: rgba(148, 163, 184, 0.9);
  }

  .schema-column-row {
    display: grid;
    grid-template-columns: 1.2fr 1fr 0.6fr 1.2fr 0.5fr 0.6fr 0.8fr;
    gap: 6px;
    align-items: center;
  }

  .schema-column-summary {
    display: grid;
    grid-template-columns: 1fr 0.8fr 0.8fr 1fr 0.4fr 0.4fr;
    gap: 6px;
    font-size: 11px;
    color: #f8fafc;
  }

  .schema-input,
  .schema-select,
  .schema-textarea {
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 12px;
    color: #f8fafc;
  }

  .schema-input::placeholder,
  .schema-textarea::placeholder {
    color: rgba(148, 163, 184, 0.8);
  }

  .schema-select {
    appearance: none;
  }

  .schema-button {
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(15, 23, 42, 0.6);
    color: #f8fafc;
    font-size: 12px;
    padding: 6px 10px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .schema-button:hover {
    background: rgba(30, 41, 59, 0.8);
  }

  .schema-button.primary {
    background: rgba(14, 116, 144, 0.8);
    border-color: rgba(56, 189, 248, 0.5);
  }

  .schema-button.subtle {
    background: rgba(15, 23, 42, 0.4);
  }

  .schema-button.danger {
    background: rgba(239, 68, 68, 0.25);
    border-color: rgba(248, 113, 113, 0.4);
  }

  .schema-changes {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 12px;
  }

  .schema-change-item {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .schema-badge {
    text-transform: uppercase;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 999px;
    background: rgba(100, 116, 139, 0.4);
    color: #e2e8f0;
  }

  .schema-badge.create {
    background: rgba(34, 197, 94, 0.3);
  }

  .schema-badge.alter {
    background: rgba(59, 130, 246, 0.3);
  }

  .schema-badge.drop {
    background: rgba(239, 68, 68, 0.3);
  }

  .schema-sql {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .schema-textarea {
    min-height: 120px;
    resize: none;
  }
</style>
