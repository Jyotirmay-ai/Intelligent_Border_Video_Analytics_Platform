import { NextResponse } from 'next/server';
import Redis from 'ioredis';

export const runtime = 'nodejs';

// Store all fences under a single Redis key "ibvap:fences"
// The format will be a JSON object: { "cam_05": { polygon: [...], severity: "critical" }, ... }

export async function GET() {
  const redis = new Redis('redis://localhost:6379');
  try {
    const data = await redis.get('ibvap:fences');
    if (!data) {
      // Default fallback if nothing is stored yet
      return NextResponse.json({
        cam_05: {
          polygon: [[10, 10], [90, 10], [90, 90], [10, 90]],
          severity: "critical"
        }
      });
    }
    return NextResponse.json(JSON.parse(data));
  } catch (err) {
    console.error("Failed to read fences from Redis:", err);
    return NextResponse.json({ error: "Failed to read fences" }, { status: 500 });
  } finally {
    redis.quit();
  }
}

export async function POST(req: Request) {
  const redis = new Redis('redis://localhost:6379');
  try {
    const body = await req.json();
    const { cameraId, polygon, severity = "critical" } = body;

    if (cameraId !== "cam_05") {
      return NextResponse.json(
        { error: "Virtual fences are available only for CAM-05." },
        { status: 400 }
      );
    }
    
    // Get existing fences
    const existingStr = await redis.get('ibvap:fences');
    const fences = existingStr ? JSON.parse(existingStr) : {};
    
    // Update the specific camera
    fences[cameraId] = {
      polygon,
      severity
    };
    
    // Save back to Redis
    const newStr = JSON.stringify(fences);
    await redis.set('ibvap:fences', newStr);
    
    // Broadcast the hot-reload message to the backend worker
    await redis.publish('ibvap_config_hotreload', newStr);
    
    return NextResponse.json({ success: true, fences });
  } catch (err) {
    console.error("Failed to write fences to Redis:", err);
    return NextResponse.json({ error: "Failed to save fences" }, { status: 500 });
  } finally {
    redis.quit();
  }
}
