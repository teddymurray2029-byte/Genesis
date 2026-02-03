import { derived, get, writable } from 'svelte/store';
import { effectiveConfigStore } from './config.js';

const MAX_EVENTS = 100;

class WebSocketStore {
  constructor() {
    if (WebSocketStore.instance) {
      console.log('🔄 WebSocketStore: Returning existing singleton instance');
      return WebSocketStore.instance;
    }
    
    console.log('🆕 WebSocketStore: Creating new singleton instance');
    this.ws = null;
    this.data = writable({
      brainSpace: { clusters: [], memories: [] },
      activation: { waveform: [], sparks: [] },
      controls: {},
      events: [],
      genesisDb: {
        database: null,
        tables: {},
        activeTable: null,
        selectedRow: null
      }
    });
    this.connected = writable(false);
    this.lastSync = writable(null);
    this.connectionError = writable(null);
    this.lastUrl = null;
    
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
  
  handleMessage(message) {
    console.log('🔄 handleMessage:', message.type);
    this.lastSync.set(Date.now());
    this.data.update(current => {
      const appendEvent = event => ({
        ...current,
        events: [...current.events.slice(-MAX_EVENTS + 1), event]
      });
      const normalizeLogEvent = () => {
        const payload = message.log ?? message.event ?? message.payload ?? message;
        return {
          type: message.type,
          message: payload?.message ?? payload?.summary ?? 'Log update received.',
          timestamp: message.timestamp ?? new Date().toISOString(),
          payload
        };
      };
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
              morphism: message.morphism || current.activation.morphism
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
          updated = appendEvent(message.event);
          break;

        case 'log_created':
        case 'log_updated':
        case 'log_deleted':
          console.log('🧾 Processing log event:', message.type);
          updated = appendEvent(normalizeLogEvent());
          break;
        
        default:
          console.log('⚠️  Unknown message type:', message.type);
          updated = current;
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
export const lastSyncStore = websocketStore.lastSync;
export const connectionErrorStore = websocketStore.connectionError;
export const connectionStateStore = derived(
  [connectedStore, connectionErrorStore],
  ([$connected, $error]) => ({
    connected: $connected,
    error: $error
  })
);

// Derived stores for convenience
export const clustersStore = derived(dataStore, $data => $data?.brainSpace?.clusters || []);
export const memoriesStore = derived(dataStore, $data => $data?.brainSpace?.memories || []);
export const activationStore = derived(dataStore, $data => $data?.activation || { waveform: [], sparks: [], morphism: 'gamma' });
