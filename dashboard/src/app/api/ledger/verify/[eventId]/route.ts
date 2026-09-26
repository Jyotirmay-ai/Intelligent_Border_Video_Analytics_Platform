import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Proxy /api/ledger/verify/{eventId} → http://localhost:8090/verify/{eventId}
 *
 * Keeps the dashboard's existing pattern of proxying to backend services so
 * the UI only ever talks to its own Next.js origin.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ eventId: string }> }
) {
  const { eventId } = await params;
  const upstream = `http://127.0.0.1:8090/verify/${encodeURIComponent(eventId)}`;

  try {
    const res = await fetch(upstream, { cache: "no-store" });
    const body = await res.json();
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json(
      {
        event_id: eventId,
        status: "UNAVAILABLE",
        detail: "Verification service is not reachable.",
      },
      { status: 503 }
    );
  }
}
