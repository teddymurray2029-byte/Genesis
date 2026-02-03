<script>
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import BrainSpace from './components/BrainSpace.svelte';
  import HeaderBar from './components/HeaderBar.svelte';
  import ControlPanel from './components/ControlPanel.svelte';
  import ChatBar from './components/ChatBar.svelte';
  import SettingsView from './components/SettingsView.svelte';
  import { websocketStore, connectedStore, lastSyncStore, connectionErrorStore } from './stores/websocket.js';
  import { effectiveConfigStore } from './stores/config.js';
  
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
    
    // Initialize WebSocket connection (disabled for now - using mock data)
    // websocketStore.connect('ws://localhost:8000/ws');
    
    const { useMockData, websocketUrl } = get(effectiveConfigStore);

    if (useMockData) {
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

      const genesisDb = {
        database: {
          name: 'hospital_core',
          description: 'Operational data for in-patient care, clinics, and diagnostics.',
          region: 'us-east-1',
          updated_at: new Date().toISOString()
        },
        tables: {
          patients: {
            columns: [
              { name: 'id', type: 'string' },
              { name: 'name', type: 'string' },
              { name: 'dob', type: 'date' },
              { name: 'gender', type: 'string' },
              { name: 'mrn', type: 'string' },
              { name: 'admit_date', type: 'datetime' },
              { name: 'diagnosis', type: 'string' },
              { name: 'attending_physician', type: 'string' },
              { name: 'status', type: 'string' },
              { name: 'room', type: 'string' }
            ],
            rows: [
              {
                id: 'PT-1001',
                name: 'Maya Patel',
                dob: '1983-04-18',
                gender: 'F',
                mrn: 'MRN-849201',
                admit_date: '2024-03-12T09:14:00Z',
                diagnosis: 'Community-acquired pneumonia',
                attending_physician: 'Dr. Alicia Nguyen',
                status: 'Stable',
                room: '3B-214'
              },
              {
                id: 'PT-1002',
                name: 'Marcus Reed',
                dob: '1975-11-02',
                gender: 'M',
                mrn: 'MRN-751044',
                admit_date: '2024-03-13T16:42:00Z',
                diagnosis: 'Type 2 diabetes with hyperglycemia',
                attending_physician: 'Dr. Isaiah Brooks',
                status: 'Monitoring',
                room: '4C-302'
              },
              {
                id: 'PT-1003',
                name: 'Elena García',
                dob: '1990-06-27',
                gender: 'F',
                mrn: 'MRN-663518',
                admit_date: '2024-03-11T22:05:00Z',
                diagnosis: 'Acute appendicitis (post-op)',
                attending_physician: 'Dr. Priya Shah',
                status: 'Recovering',
                room: '2A-118'
              },
              {
                id: 'PT-1004',
                name: 'Thomas Osei',
                dob: '1968-01-14',
                gender: 'M',
                mrn: 'MRN-538902',
                admit_date: '2024-03-10T08:30:00Z',
                diagnosis: 'CHF exacerbation',
                attending_physician: 'Dr. Claire Howard',
                status: 'Critical',
                room: 'ICU-07'
              },
              {
                id: 'PT-1005',
                name: 'Hannah Kim',
                dob: '2002-09-09',
                gender: 'F',
                mrn: 'MRN-905774',
                admit_date: '2024-03-14T13:55:00Z',
                diagnosis: 'Asthma flare',
                attending_physician: 'Dr. Liam Chen',
                status: 'Stable',
                room: '3A-204'
              },
              {
                id: 'PT-1006',
                name: 'Robert Hayes',
                dob: '1958-07-30',
                gender: 'M',
                mrn: 'MRN-447211',
                admit_date: '2024-03-09T19:20:00Z',
                diagnosis: 'Ischemic stroke (left MCA)',
                attending_physician: 'Dr. Sofia Morales',
                status: 'Rehab',
                room: 'Neuro-12'
              }
            ]
          },
          appointments: {
            columns: [
              { name: 'id', type: 'string' },
              { name: 'patient_id', type: 'string' },
              { name: 'physician_id', type: 'string' },
              { name: 'scheduled_time', type: 'datetime' },
              { name: 'visit_type', type: 'string' },
              { name: 'status', type: 'string' },
              { name: 'location', type: 'string' },
              { name: 'reason', type: 'string' }
            ],
            rows: [
              {
                id: 'APPT-3001',
                patient_id: 'PT-1001',
                physician_id: 'MD-201',
                scheduled_time: '2024-03-15T14:30:00Z',
                visit_type: 'Follow-up',
                status: 'Scheduled',
                location: 'Pulmonary Clinic',
                reason: 'Chest X-ray review'
              },
              {
                id: 'APPT-3002',
                patient_id: 'PT-1002',
                physician_id: 'MD-202',
                scheduled_time: '2024-03-15T09:00:00Z',
                visit_type: 'Consult',
                status: 'Checked In',
                location: 'Endocrinology',
                reason: 'Glucose management plan'
              },
              {
                id: 'APPT-3003',
                patient_id: 'PT-1003',
                physician_id: 'MD-203',
                scheduled_time: '2024-03-16T11:15:00Z',
                visit_type: 'Post-op',
                status: 'Scheduled',
                location: 'Surgery Suite 2',
                reason: 'Wound inspection'
              },
              {
                id: 'APPT-3004',
                patient_id: 'PT-1004',
                physician_id: 'MD-204',
                scheduled_time: '2024-03-15T18:00:00Z',
                visit_type: 'Rounds',
                status: 'In Progress',
                location: 'ICU',
                reason: 'Cardiac status update'
              },
              {
                id: 'APPT-3005',
                patient_id: 'PT-1005',
                physician_id: 'MD-205',
                scheduled_time: '2024-03-17T08:30:00Z',
                visit_type: 'Respiratory',
                status: 'Scheduled',
                location: 'Respiratory Lab',
                reason: 'Spirometry assessment'
              },
              {
                id: 'APPT-3006',
                patient_id: 'PT-1006',
                physician_id: 'MD-206',
                scheduled_time: '2024-03-15T13:00:00Z',
                visit_type: 'Rehab',
                status: 'Scheduled',
                location: 'Neuro Rehab Gym',
                reason: 'PT/OT evaluation'
              }
            ]
          },
          physicians: {
            columns: [
              { name: 'id', type: 'string' },
              { name: 'name', type: 'string' },
              { name: 'specialty', type: 'string' },
              { name: 'pager', type: 'string' },
              { name: 'phone', type: 'string' },
              { name: 'department', type: 'string' },
              { name: 'status', type: 'string' },
              { name: 'shift', type: 'string' }
            ],
            rows: [
              {
                id: 'MD-201',
                name: 'Dr. Alicia Nguyen',
                specialty: 'Pulmonology',
                pager: 'PGR-8821',
                phone: '(555) 410-2211',
                department: 'Medicine',
                status: 'On Service',
                shift: 'Day'
              },
              {
                id: 'MD-202',
                name: 'Dr. Isaiah Brooks',
                specialty: 'Endocrinology',
                pager: 'PGR-7745',
                phone: '(555) 410-3389',
                department: 'Medicine',
                status: 'On Service',
                shift: 'Day'
              },
              {
                id: 'MD-203',
                name: 'Dr. Priya Shah',
                specialty: 'General Surgery',
                pager: 'PGR-6650',
                phone: '(555) 410-5524',
                department: 'Surgery',
                status: 'On Call',
                shift: 'Evening'
              },
              {
                id: 'MD-204',
                name: 'Dr. Claire Howard',
                specialty: 'Cardiology',
                pager: 'PGR-4483',
                phone: '(555) 410-7872',
                department: 'Cardiology',
                status: 'On Service',
                shift: 'Night'
              },
              {
                id: 'MD-205',
                name: 'Dr. Liam Chen',
                specialty: 'Pulmonary Critical Care',
                pager: 'PGR-9914',
                phone: '(555) 410-6623',
                department: 'Critical Care',
                status: 'On Service',
                shift: 'Day'
              },
              {
                id: 'MD-206',
                name: 'Dr. Sofia Morales',
                specialty: 'Neurology',
                pager: 'PGR-1207',
                phone: '(555) 410-1147',
                department: 'Neurosciences',
                status: 'On Service',
                shift: 'Evening'
              }
            ]
          },
          wards: {
            columns: [
              { name: 'id', type: 'string' },
              { name: 'name', type: 'string' },
              { name: 'floor', type: 'string' },
              { name: 'charge_nurse', type: 'string' },
              { name: 'capacity', type: 'number' },
              { name: 'occupied_beds', type: 'number' },
              { name: 'status', type: 'string' },
              { name: 'phone', type: 'string' }
            ],
            rows: [
              {
                id: 'WARD-3B',
                name: 'Medical-Surgical West',
                floor: '3B',
                charge_nurse: 'Jordan Ellis, RN',
                capacity: 32,
                occupied_beds: 28,
                status: 'Busy',
                phone: '(555) 410-3300'
              },
              {
                id: 'WARD-4C',
                name: 'Telemetry',
                floor: '4C',
                charge_nurse: 'Renee Alvarez, RN',
                capacity: 24,
                occupied_beds: 21,
                status: 'At Capacity',
                phone: '(555) 410-4400'
              },
              {
                id: 'WARD-ICU',
                name: 'Intensive Care Unit',
                floor: 'ICU',
                charge_nurse: 'Samir Patel, RN',
                capacity: 18,
                occupied_beds: 17,
                status: 'Critical',
                phone: '(555) 410-7700'
              },
              {
                id: 'WARD-NEURO',
                name: 'Neuroscience Stepdown',
                floor: 'Neuro',
                charge_nurse: 'Alexis Grant, RN',
                capacity: 20,
                occupied_beds: 16,
                status: 'Available',
                phone: '(555) 410-5500'
              },
              {
                id: 'WARD-2A',
                name: 'Post-Op Recovery',
                floor: '2A',
                charge_nurse: 'Morgan Li, RN',
                capacity: 16,
                occupied_beds: 12,
                status: 'Open',
                phone: '(555) 410-2200'
              }
            ]
          },
          lab_results: {
            columns: [
              { name: 'id', type: 'string' },
              { name: 'patient_id', type: 'string' },
              { name: 'test', type: 'string' },
              { name: 'collected_at', type: 'datetime' },
              { name: 'result', type: 'string' },
              { name: 'unit', type: 'string' },
              { name: 'reference_range', type: 'string' },
              { name: 'status', type: 'string' },
              { name: 'ordering_physician', type: 'string' }
            ],
            rows: [
              {
                id: 'LAB-7001',
                patient_id: 'PT-1001',
                test: 'CBC',
                collected_at: '2024-03-13T06:30:00Z',
                result: 'WBC 11.2',
                unit: 'x10^3/uL',
                reference_range: '4.0-10.5',
                status: 'Flagged',
                ordering_physician: 'Dr. Alicia Nguyen'
              },
              {
                id: 'LAB-7002',
                patient_id: 'PT-1002',
                test: 'HbA1c',
                collected_at: '2024-03-12T10:15:00Z',
                result: '9.1',
                unit: '%',
                reference_range: '<7.0',
                status: 'High',
                ordering_physician: 'Dr. Isaiah Brooks'
              },
              {
                id: 'LAB-7003',
                patient_id: 'PT-1003',
                test: 'CRP',
                collected_at: '2024-03-12T18:45:00Z',
                result: '6.8',
                unit: 'mg/L',
                reference_range: '<5.0',
                status: 'High',
                ordering_physician: 'Dr. Priya Shah'
              },
              {
                id: 'LAB-7004',
                patient_id: 'PT-1004',
                test: 'BNP',
                collected_at: '2024-03-14T05:05:00Z',
                result: '1280',
                unit: 'pg/mL',
                reference_range: '<100',
                status: 'Critical',
                ordering_physician: 'Dr. Claire Howard'
              },
              {
                id: 'LAB-7005',
                patient_id: 'PT-1005',
                test: 'Peak Flow',
                collected_at: '2024-03-14T12:20:00Z',
                result: '350',
                unit: 'L/min',
                reference_range: '400-600',
                status: 'Low',
                ordering_physician: 'Dr. Liam Chen'
              },
              {
                id: 'LAB-7006',
                patient_id: 'PT-1006',
                test: 'Lipid Panel',
                collected_at: '2024-03-11T09:50:00Z',
                result: 'LDL 146',
                unit: 'mg/dL',
                reference_range: '<100',
                status: 'High',
                ordering_physician: 'Dr. Sofia Morales'
              },
              {
                id: 'LAB-7007',
                patient_id: 'PT-1001',
                test: 'Blood Culture',
                collected_at: '2024-03-13T07:15:00Z',
                result: 'No growth at 48h',
                unit: 'N/A',
                reference_range: 'Negative',
                status: 'Final',
                ordering_physician: 'Dr. Alicia Nguyen'
              }
            ]
          }
        },
        activeTable: 'patients',
        selectedRow: {
          table: 'patients',
          id: 'PT-1001'
        }
      };
      
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
        events: [],
        genesisDb
      };
      
      websocketStore.data.set(mockData);
      connectedStore.set(true);
      lastSyncStore.set(Date.now());
      connectionErrorStore.set(null);
      console.log('✅ Mock data set, connected state: true');
      console.log('📦 Mock clusters:', mockData.brainSpace.clusters.length);
    } else {
      websocketStore.connect(websocketUrl);
    }
  });
</script>

<main class="h-screen w-screen flex flex-col relative">
  <HeaderBar />
  <!-- Main 3D Brain Space -->
  <div class="flex-1 relative">
    <BrainSpace />
  </div>
  <SettingsView />
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
