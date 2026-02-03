import { derived, get, writable } from 'svelte/store';
import { effectiveConfigStore } from './config.js';

class WebSocketStore {
  constructor() {
    if (WebSocketStore.instance) {
      console.log('🔄 WebSocketStore: Returning existing singleton instance');
      return WebSocketStore.instance;
    }
    
    console.log('🆕 WebSocketStore: Creating new singleton instance');
    this.ws = null;
    this.logsWs = null;
    this.data = writable({
      brainSpace: { clusters: [], memories: [] },
      activation: { waveform: [], sparks: [] },
      controls: {},
      events: [],
      logs: [],
      logEvents: [],
      timelinePoints: [],
      genesisDb: {
        database: null,
        tables: {},
        activeTable: null,
        selectedRow: null
      }
    });
    this.connected = writable(false);
    this.logsConnected = writable(false);
    this.lastSync = writable(null);
    this.connectionError = writable(null);
    this.lastUrl = null;
    this.logsLastUrl = null;
    
    WebSocketStore.instance = this;
  }
  
  connect(url) {
    const resolvedUrl = url ?? get(effectiveConfigStore).websocketUrl;
    console.log('🔌 WebSocketStore.connect() called with URL:', resolvedUrl);
    if (!resolvedUrl) {
      console.warn('⚠️  No WebSocket URL available to connect');
      this.connectionError.set('Missing WebSocket URL. Update settings and retry.');
      return;
    }
    try {
      console.log('📡 Creating WebSocket connection...');
      this.lastUrl = resolvedUrl;
      this.connectionError.set(null);
      this.ws = new WebSocket(resolvedUrl);
      
      this.ws.onopen = () => {
        console.log('✅ WebSocket connected to:', resolvedUrl);
        this.connected.set(true);
        this.connectionError.set(null);
      };
      
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('📨 WebSocket message received:', message.type, message);
          this.handleMessage(message);
        } catch (error) {
          console.error('❌ Failed to parse WebSocket message:', error, event.data);
        }
      };
      
      this.ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        this.connected.set(false);
        this.connectionError.set('Connection error. Please retry.');
      };
      
      this.ws.onclose = (event) => {
        console.log('🔌 WebSocket disconnected:', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        });
        this.connected.set(false);
        this.connectionError.set(
          event.reason
            ? `Disconnected: ${event.reason}`
            : 'Disconnected from server. Please retry.'
        );
        // Reconnect after 3 seconds
        console.log('⏳ Will reconnect in 3 seconds...');
        setTimeout(() => this.connect(resolvedUrl), 3000);
      };
    } catch (error) {
      console.error('❌ Failed to connect WebSocket:', error);
      this.connectionError.set('Failed to connect. Please retry.');
    }
  }

  connectLogs(url) {
    const resolvedUrl = url ?? get(effectiveConfigStore).logsWebsocketUrl ?? get(effectiveConfigStore).websocketUrl;
    console.log('📡 WebSocketStore.connectLogs() called with URL:', resolvedUrl);
    if (!resolvedUrl) {
      console.warn('⚠️  No Logs WebSocket URL available to connect');
      return;
    }
    if (this.ws && this.lastUrl === resolvedUrl) {
      this.logsConnected.set(true);
      return;
    }
    if (this.logsWs && this.logsLastUrl === resolvedUrl) {
      return;
    }
    try {
      this.logsLastUrl = resolvedUrl;
      this.logsWs = new WebSocket(resolvedUrl);
      this.logsWs.onopen = () => {
        console.log('✅ Logs WebSocket connected to:', resolvedUrl);
        this.logsConnected.set(true);
      };
      this.logsWs.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('📨 Logs WebSocket message received:', message.type, message);
          this.handleMessage(message);
        } catch (error) {
          console.error('❌ Failed to parse Logs WebSocket message:', error, event.data);
        }
      };
      this.logsWs.onerror = (error) => {
        console.error('❌ Logs WebSocket error:', error);
        this.logsConnected.set(false);
      };
      this.logsWs.onclose = (event) => {
        console.log('🔌 Logs WebSocket disconnected:', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        });
        this.logsConnected.set(false);
        console.log('⏳ Will reconnect logs in 3 seconds...');
        setTimeout(() => this.connectLogs(resolvedUrl), 3000);
      };
    } catch (error) {
      console.error('❌ Failed to connect Logs WebSocket:', error);
      this.logsConnected.set(false);
    }
  }
  
  handleMessage(message) {
    console.log('🔄 handleMessage:', message.type);
    this.lastSync.set(Date.now());
    this.data.update(current => {
      let updated;
      switch (message.type) {
        case 'initial_state':
          console.log('📦 Processing initial_state:', {
            brainSpaceClusters: message.brain_space?.clusters?.length || 0,
            controlsKeys: Object.keys(message.controls || {})
          });
          updated = {
            ...current,
            brainSpace: message.brain_space || current.brainSpace,
            controls: message.controls || current.controls
          };
          break;
        
        case 'activation_update':
          console.log('⚡ Processing activation_update:', {
            waveformLength: message.waveform?.length || 0,
            sparksCount: message.sparks?.length || 0,
            morphism: message.morphism
          });
          updated = {
            ...current,
            activation: {
              waveform: message.waveform || current.activation.waveform,
              sparks: message.sparks || current.activation.sparks,
              morphism: message.morphism || current.activation.morphism,
              energy: message.energy ?? current.activation.energy
            }
          };
          break;
        
        case 'brain_space_update':
          console.log('🧠 Processing brain_space_update:', {
            clustersCount: message.brain_space?.clusters?.length || 0
          });
          updated = {
            ...current,
            brainSpace: message.brain_space || current.brainSpace
          };
          break;
        
        case 'event':
          console.log('📝 Processing event:', message.event);
          updated = {
            ...current,
            events: [...current.events.slice(-99), message.event]
          };
          break;

        case 'timeline_update': {
          const points = message.points || message.timeline_points || message.timeline || [];
          console.log('📈 Processing timeline_update:', points.length);
          updated = {
            ...current,
            timelinePoints: points
          };
          break;
        }

        case 'timeline_point': {
          const point = message.point || message.timeline_point || message.data || message;
          console.log('📌 Processing timeline_point:', point);
          updated = {
            ...current,
            timelinePoints: [...current.timelinePoints.slice(-199), point]
          };
          break;
        }

        case 'logs_update': {
          const logs = message.logs || message.items || message.data || message.entries || [];
          console.log('📚 Processing logs_update:', logs.length);
          updated = {
            ...current,
            logs,
            logEvents: [
              ...current.logEvents.slice(-199),
              {
                type: 'logs_update',
                logs,
                total: message.total ?? message.total_count ?? message.count
              }
            ]
          };
          break;
        }
        
        default:
          if (message.type?.startsWith('log_')) {
            const logEntry = message.log || message.entry || message.data || message.payload;
            console.log('🧾 Processing log event:', message.type, logEntry);
            const logs = current.logs || [];
            const logId = logEntry?.id ?? logEntry?.log_id ?? logEntry?.logId;
            const matchesLog = (item) =>
              item?.id === logId || item?.log_id === logId || item?.logId === logId;
            let nextLogs = logs;

            if (message.type === 'log_deleted' || message.type === 'log_removed') {
              nextLogs = logs.filter((item) => !matchesLog(item));
            } else if (logEntry) {
              const existingIndex = logs.findIndex(matchesLog);
              if (existingIndex >= 0) {
                nextLogs = logs.map((item, index) =>
                  index === existingIndex ? { ...item, ...logEntry } : item
                );
              } else {
                nextLogs = [logEntry, ...logs];
              }
            }

            updated = {
              ...current,
              logs: nextLogs,
              logEvents: [
                ...current.logEvents.slice(-199),
                {
                  type: message.type,
                  log: logEntry
                }
              ]
            };
          } else {
            console.log('⚠️  Unknown message type:', message.type);
            updated = current;
          }
      }
      return updated;
    });
  }
  
  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('📤 Sending WebSocket message:', message);
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('⚠️  Cannot send message, WebSocket not open:', {
        ws: !!this.ws,
        readyState: this.ws?.readyState
      });
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    if (this.logsWs) {
      this.logsWs.close();
      this.logsWs = null;
      this.logsConnected.set(false);
    }
  }

  retry() {
    if (this.lastUrl) {
      this.connect(this.lastUrl);
    } else {
      console.warn('⚠️  No WebSocket URL available to retry');
    }
  }
}

// Singleton instance
let websocketStoreInstance = null;

export function getWebSocketStore() {
  if (!websocketStoreInstance) {
    websocketStoreInstance = new WebSocketStore();
  }
  return websocketStoreInstance;
}

// Export the singleton instance
export const websocketStore = getWebSocketStore();

// Export the stores directly for easier use in components
export const dataStore = websocketStore.data;
export const connectedStore = websocketStore.connected;
export const logsConnectedStore = websocketStore.logsConnected;
export const lastSyncStore = websocketStore.lastSync;
export const connectionErrorStore = websocketStore.connectionError;

// Derived stores for convenience
export const clustersStore = derived(dataStore, $data => $data?.brainSpace?.clusters || []);
export const memoriesStore = derived(dataStore, $data => $data?.brainSpace?.memories || []);
export const activationStore = derived(dataStore, $data => $data?.activation || { waveform: [], sparks: [], morphism: 'gamma' });
export const logsStore = derived(dataStore, $data => $data?.logs || []);
export const logEventsStore = derived(dataStore, $data => $data?.logEvents || []);
export const timelinePointsStore = derived(dataStore, $data => $data?.timelinePoints || []);
