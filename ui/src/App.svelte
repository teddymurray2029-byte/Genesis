<script>
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { dataStore, websocketStore, connectedStore, lastSyncStore, connectionErrorStore } from './stores/websocket.js';
  import { effectiveConfigStore } from './stores/config.js';

  let selectedTable = '';
  let filterText = '';
  let selectedRowKey = null;

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
  $: if (genesisDb?.activeTable && !selectedTable) {
    selectedTable = genesisDb.activeTable;
  }

  const handleSelectTable = (name) => {
    selectedTable = name;
    selectedRowKey = null;
  };

  const handleSelectRow = (row) => {
    selectedRowKey = rowKey(row, columns);
  };

  onMount(() => {
    console.log('🎨 App.svelte mounted');
    document.title = 'Genesis Data Console';
    
    // Initialize WebSocket connection (disabled for now - using mock data)
    // websocketStore.connect('ws://localhost:8000/ws');
    
    const { useMockData, websocketUrl } = get(effectiveConfigStore);

    if (useMockData) {
      console.log('📊 Setting mock data...');
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
        brainSpace: { clusters: [], memories: [] },
        activation: { waveform: [], sparks: [], energy: 0.7, morphism: 'gamma' },
        controls: { current_cycle: 'active', morphism_state: 'gamma', coherence: 0.85 },
        events: [],
        genesisDb
      };
      
      websocketStore.data.set(mockData);
      connectedStore.set(true);
      lastSyncStore.set(Date.now());
      connectionErrorStore.set(null);
      console.log('✅ Mock data set, connected state: true');
      selectedTable = genesisDb.activeTable;
      selectedRowKey = genesisDb.selectedRow?.id ?? null;
    } else {
      websocketStore.connect(websocketUrl);
    }
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
      <button class="btn">Export</button>
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
        <button class="btn btn-small">Run Query</button>
        <button class="btn btn-small">Backup</button>
      </div>
    </aside>

    <section class="crud-main">
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
        <h3>Update the selected row in {selectedTable || genesisDb?.activeTable}</h3>
        <div class="detail-fields">
          {#each columns as column}
            <label>
              <span>{column.name.toUpperCase()}</span>
              <input type="text" readonly value={selectedRow?.[column.name] ?? ''} />
            </label>
          {/each}
        </div>
        <div class="detail-actions">
          <button class="btn btn-primary">Save Changes</button>
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
