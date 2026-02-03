# Visualization WebSocket Events

The visualization service exposes a WebSocket endpoint at `/ws`. Clients receive an initial JSON payload on connect and then event messages. Event messages use the following envelope:

```json
{
  "type": "event",
  "event_type": "<event name>",
  "data": { }
}
```

## Event types and payloads

### `log.created`
Emitted when a log entry is created.

```json
{
  "type": "event",
  "event_type": "log.created",
  "data": {
    "id": 42,
    "timestamp": "2024-04-22T18:25:43.511Z",
    "type": "info",
    "message": "Log message",
    "payload": { "extra": "context" },
    "tags": ["tag-a", "tag-b"]
  }
}
```

### `log.updated`
Emitted when a log entry is updated.

```json
{
  "type": "event",
  "event_type": "log.updated",
  "data": {
    "id": 42,
    "timestamp": "2024-04-22T18:25:43.511Z",
    "type": "warning",
    "message": "Updated message",
    "payload": null,
    "tags": []
  }
}
```

### `log.deleted`
Emitted when a log entry is deleted.

```json
{
  "type": "event",
  "event_type": "log.deleted",
  "data": {
    "id": 42
  }
}
```

### `heartbeat`
Emitted when the connection is idle to keep the client in sync.

```json
{
  "type": "event",
  "event_type": "heartbeat",
  "data": {
    "timestamp": "2024-04-22T18:25:43.511Z"
  }
}
```
