<script>
  import { onMount } from 'svelte';
  import BrainSpace from './components/BrainSpace.svelte';
  import HeaderBar from './components/HeaderBar.svelte';
  import ControlPanel from './components/ControlPanel.svelte';
  import ChatBar from './components/ChatBar.svelte';
  import { websocketStore, connectedStore, lastSyncStore, connectionErrorStore } from './stores/websocket.js';
  import { genesisDbConfig } from './config/db.js';
  
  onMount(() => {
    console.log('🎨 App.svelte mounted');
    
    // Initialize WebSocket connection (disabled for now - using mock data)
    // websocketStore.connect('ws://localhost:8000/ws');
    
    if (genesisDbConfig.useMockData) {
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
      connectedStore.set(true);
      lastSyncStore.set(Date.now());
      connectionErrorStore.set(null);
      console.log('✅ Mock data set, connected state: true');
      console.log('📦 Mock clusters:', mockData.brainSpace.clusters.length);
    } else {
      websocketStore.connect(genesisDbConfig.websocketUrl);
    }
  });
</script>

<main class="h-screen w-screen flex flex-col relative">
  <HeaderBar />
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
</style>
