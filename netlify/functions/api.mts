import type { Context, Config } from "@netlify/functions";

export default async (req: Request, context: Context) => {
  const baseUrl = new URL(req.url).origin;

  const apiInfo = {
    name: "Genesis API",
    version: "1.0.0",
    status: "running",
    description: "Multi-octave hierarchical memory system API",
    endpoints: {
      health: {
        url: `${baseUrl}/api/health`,
        methods: ["GET"],
        description: "Health check endpoint"
      },
      logs: {
        url: `${baseUrl}/api/logs`,
        methods: ["GET", "POST"],
        description: "List all logs or create a new log entry"
      },
      log: {
        url: `${baseUrl}/api/logs/{id}`,
        methods: ["GET", "PUT", "DELETE"],
        description: "Get, update, or delete a specific log entry"
      }
    },
    documentation: {
      createLog: {
        method: "POST",
        url: "/api/logs",
        body: {
          message: "string (required)",
          level: "string (optional, default: 'info')"
        }
      },
      updateLog: {
        method: "PUT",
        url: "/api/logs/{id}",
        body: {
          message: "string (optional)",
          level: "string (optional)"
        }
      }
    }
  };

  return new Response(JSON.stringify(apiInfo, null, 2), {
    headers: { "Content-Type": "application/json" }
  });
};

export const config: Config = {
  path: ["/api", "/api/"]
};
