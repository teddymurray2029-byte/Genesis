import type { Context, Config } from "@netlify/functions";
import { getStore } from "@netlify/blobs";

interface LogEntry {
  id: number;
  message: string;
  level: string;
  createdAt: string;
}

interface LogCreate {
  message: string;
  level?: string;
}

async function getLogsStore(context: Context) {
  return getStore({ name: "genesis-logs", consistency: "strong" });
}

async function getAllLogs(store: ReturnType<typeof getStore>): Promise<LogEntry[]> {
  const { blobs } = await store.list();
  const logs: LogEntry[] = [];

  for (const blob of blobs) {
    if (blob.key.startsWith("log-")) {
      const data = await store.get(blob.key, { type: "json" });
      if (data) {
        logs.push(data as LogEntry);
      }
    }
  }

  return logs.sort((a, b) => a.id - b.id);
}

async function getNextId(store: ReturnType<typeof getStore>): Promise<number> {
  const counter = await store.get("_counter", { type: "json" }) as { value: number } | null;
  return counter?.value ?? 1;
}

async function incrementCounter(store: ReturnType<typeof getStore>, current: number): Promise<void> {
  await store.setJSON("_counter", { value: current + 1 });
}

export default async (req: Request, context: Context) => {
  const url = new URL(req.url);
  const method = req.method;

  // Extract log ID from path if present
  const pathMatch = url.pathname.match(/\/api\/logs\/(\d+)$/);
  const logId = pathMatch ? parseInt(pathMatch[1], 10) : null;

  const store = await getLogsStore(context);

  try {
    // GET /api/logs - List all logs
    if (method === "GET" && !logId) {
      const logs = await getAllLogs(store);
      return new Response(JSON.stringify(logs), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // GET /api/logs/:id - Get single log
    if (method === "GET" && logId) {
      const log = await store.get(`log-${logId}`, { type: "json" }) as LogEntry | null;
      if (!log) {
        return new Response(
          JSON.stringify({ detail: `Log ${logId} not found` }),
          { status: 404, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(JSON.stringify(log), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // POST /api/logs - Create log
    if (method === "POST") {
      const body = await req.json() as LogCreate;

      if (!body.message) {
        return new Response(
          JSON.stringify({ detail: "Message is required" }),
          { status: 400, headers: { "Content-Type": "application/json" } }
        );
      }

      const id = await getNextId(store);
      const entry: LogEntry = {
        id,
        message: body.message,
        level: body.level || "info",
        createdAt: new Date().toISOString()
      };

      await store.setJSON(`log-${id}`, entry);
      await incrementCounter(store, id);

      return new Response(JSON.stringify(entry), {
        status: 201,
        headers: { "Content-Type": "application/json" }
      });
    }

    // PUT /api/logs/:id - Update log
    if (method === "PUT" && logId) {
      const existing = await store.get(`log-${logId}`, { type: "json" }) as LogEntry | null;
      if (!existing) {
        return new Response(
          JSON.stringify({ detail: `Log ${logId} not found` }),
          { status: 404, headers: { "Content-Type": "application/json" } }
        );
      }

      const body = await req.json() as LogCreate;
      const updated: LogEntry = {
        ...existing,
        message: body.message || existing.message,
        level: body.level || existing.level
      };

      await store.setJSON(`log-${logId}`, updated);

      return new Response(JSON.stringify(updated), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // DELETE /api/logs/:id - Delete log
    if (method === "DELETE" && logId) {
      const existing = await store.get(`log-${logId}`, { type: "json" }) as LogEntry | null;
      if (!existing) {
        return new Response(
          JSON.stringify({ detail: `Log ${logId} not found` }),
          { status: 404, headers: { "Content-Type": "application/json" } }
        );
      }

      await store.delete(`log-${logId}`);

      return new Response(JSON.stringify({ status: "deleted" }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    return new Response(
      JSON.stringify({ detail: "Method not allowed" }),
      { status: 405, headers: { "Content-Type": "application/json" } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ detail: "Internal server error" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
};

export const config: Config = {
  path: ["/api/logs", "/api/logs/*", "/logs", "/logs/*"]
};
