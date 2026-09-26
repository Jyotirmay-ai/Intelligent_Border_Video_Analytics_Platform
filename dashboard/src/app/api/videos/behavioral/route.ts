import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    // Path to the sample videos folder
    const videosDir = path.join(process.cwd(), 'public', 'videos');
    
    if (!fs.existsSync(videosDir)) {
      return NextResponse.json({ error: 'Videos directory not found' }, { status: 404 });
    }

    const files = fs.readdirSync(videosDir);
    
    // Filter for files that match the behavioral pattern (e.g., 4.1.mp4, 4.2.mp4)
    // We look for files starting with '4.' and ending with '.mp4'
    const behavioralVideos = files
      .filter(file => file.startsWith('4.') && file.endsWith('.mp4'))
      .sort();

    return NextResponse.json(behavioralVideos);
  } catch (error) {
    console.error('Error fetching behavioral videos:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
