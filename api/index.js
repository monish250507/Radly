/**
 * P0 FIX: This file previously imported the non-existent '../server/index.js',
 * causing a deployment blocker on Vercel.
 *
 * PaperBlast's backend is a FastAPI application (server/main.py), NOT a Node.js app.
 * This file is intentionally a no-op stub. The actual API routing is handled by
 * Vercel's Python runtime via vercel.json → server/main.py.
 *
 * DO NOT add Node.js Express/Fastify logic here. All /api/* routes are served
 * by the FastAPI ASGI application defined in server/main.py.
 *
 * Deployment checklist:
 *   1. vercel.json routes /api/(.*) to the Python runtime (see vercel.json)
 *   2. server/main.py is the FastAPI entrypoint
 *   3. requirements.txt lists all Python dependencies
 *   4. Set DATABASE_URL in Vercel env vars for persistent storage
 */

// This module intentionally exports nothing.
// The real backend is Python/FastAPI — see server/main.py.
export default null;
