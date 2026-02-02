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
</style>
