# Testing the Visualization

## Quick Start

Both servers should now be running:

1. **Frontend**: http://localhost:5173
2. **Backend**: http://localhost:8000/ws (WebSocket)

## What You Should See

1. **Brain Space**: Cyan/blue particles representing memory clusters
2. **Control Panel**: Right sidebar with tabs (Logs, Monitors, Settings, Help)
3. **Chat Bar**: Bottom input for commands
4. **Waveform**: Orange activation line (when data is streaming)

## Test Commands

In the chat bar, try:
- `recall 0 0 0` - Recall clusters near origin
- `generate` - Trigger generation
- `optimize` - Start optimization

## Troubleshooting

### Frontend not loading
```bash
cd visualization
npm run dev
```

### Backend not connecting
```bash
genesis.js service --host 0.0.0.0 --port 8000
```

### Check logs
```bash
tail -f /tmp/genesis_vite.log      # Frontend
tail -f /tmp/genesis_server.log    # Backend
```

### WebSocket connection issues
- Open browser console (F12)
- Check for WebSocket errors
- Verify backend is running on port 8000

## Next Steps

1. Connect to real Genesis system (extend `src/visualization/server.py`)
2. Add more WebGL effects
3. Implement 3D camera controls
4. Add parameter time-series charts
