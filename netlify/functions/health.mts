import type { Context, Config } from "@netlify/functions";

export default async (req: Request, context: Context) => {
  return new Response(
    JSON.stringify({ status: "ok" }),
    {
      headers: { "Content-Type": "application/json" }
    }
  );
};

export const config: Config = {
  path: ["/api/health", "/health"]
};
