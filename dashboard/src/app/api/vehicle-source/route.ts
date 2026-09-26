import { NextResponse } from "next/server";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

export const runtime = "nodejs";

const projectRoot = path.resolve(process.cwd(), "..");
const videoDirectory = path.join(projectRoot, "data", "sample_videos");
const sourceConfigPath = path.join(projectRoot, "data", "runtime", "cam_02_source.json");

async function availableSources() {
  const files = await readdir(videoDirectory);
  return files.filter((file) => file.toLowerCase().endsWith(".mp4"))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
    .map((file) => ({ value: `data/sample_videos/${file}`, label: `Video ${file.replace(/\.mp4$/i, "")}` }));
}

export async function GET() {
  try {
    const sources = await availableSources();
    let selectedSource = "data/sample_videos/3.1.mp4";
    try {
      const saved = JSON.parse(await readFile(sourceConfigPath, "utf8"));
      if (typeof saved.source === "string") selectedSource = saved.source;
    } catch { /* use default */ }
    return NextResponse.json({ sources, selectedSource });
  } catch {
    return NextResponse.json({ error: "Unable to load vehicle videos." }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { source } = await request.json();
    const sources = await availableSources();
    if (!sources.some((item) => item.value === source)) {
      return NextResponse.json({ error: "Invalid CAM-02 video source." }, { status: 400 });
    }
    await mkdir(path.dirname(sourceConfigPath), { recursive: true });
    await writeFile(sourceConfigPath, JSON.stringify({ source }), "utf8");
    return NextResponse.json({ success: true, source });
  } catch {
    return NextResponse.json({ error: "Unable to update vehicle source." }, { status: 500 });
  }
}
