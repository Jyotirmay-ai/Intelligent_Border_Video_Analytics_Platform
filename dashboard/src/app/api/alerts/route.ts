import { NextResponse } from 'next/server';
import Redis from 'ioredis';

// Force Node.js runtime since ioredis relies on Node APIs
export const runtime = 'nodejs';
// Disable caching to keep the SSE stream alive
export const dynamic = 'force-dynamic';

export async function GET() {
  const encoder = new TextEncoder();
  const redis = new Redis('redis://localhost:6379');

  let pingInterval: ReturnType<typeof setInterval> | null = null;
  let cleaned = false;

  function cleanup() {
    if (cleaned) return;
    cleaned = true;
    if (pingInterval) clearInterval(pingInterval);
    redis.quit().catch(() => {});
  }

  const stream = new ReadableStream({
    start(controller) {
      redis.subscribe('ibvap_alerts', (err, count) => {
        if (err) {
          console.error("Failed to subscribe to Redis:", err);
          return;
        }
        console.log(`Subscribed successfully! Currently subscribed to ${count} channels.`);
      });

      redis.on('message', (channel, message) => {
        if (channel === 'ibvap_alerts') {
          try {
            // SSE format: data: {message}\n\n
            controller.enqueue(encoder.encode(`data: ${message}\n\n`));
          } catch (e) {
            console.warn("Stream closed, stopping alert push.");
            cleanup();
          }
        }
      });

      // Keep connection alive with pings every 30 seconds
      pingInterval = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(': ping\n\n'));
        } catch (e) {
          console.warn("Stream closed, stopping ping.");
          cleanup();
        }
      }, 30000);
    },
    cancel() {
      cleanup();
    }
  });

  return new NextResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
    },
  });
}

