import { NextResponse } from 'next/server';
import Redis from 'ioredis';

export const runtime = 'nodejs';

// Store all proposals under "ibvap:proposals"
export async function GET() {
  const redis = new Redis('redis://localhost:6379');
  try {
    const data = await redis.get('ibvap:proposals');
    return NextResponse.json(data ? JSON.parse(data) : {});
  } catch (err) {
    console.error("Failed to read proposals from Redis:", err);
    return NextResponse.json({ error: "Failed to read proposals" }, { status: 500 });
  } finally {
    redis.quit();
  }
}

export async function POST(req: Request) {
  const redis = new Redis('redis://localhost:6379');
  try {
    const body = await req.json();
    const { cameraId, polygon, action } = body;

    if (cameraId !== "cam_05") {
      return NextResponse.json(
        { error: "Virtual-fence proposals are available only for CAM-05." },
        { status: 400 }
      );
    }
    
    const existingStr = await redis.get('ibvap:proposals');
    const proposals = existingStr ? JSON.parse(existingStr) : {};
    
    if (action === "propose") {
      proposals[cameraId] = { polygon };
    } else if (action === "clear") {
      delete proposals[cameraId];
    }
    
    await redis.set('ibvap:proposals', JSON.stringify(proposals));
    
    return NextResponse.json({ success: true, proposals });
  } catch (err) {
    console.error("Failed to write proposals to Redis:", err);
    return NextResponse.json({ error: "Failed to save proposal" }, { status: 500 });
  } finally {
    redis.quit();
  }
}
