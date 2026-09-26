import { NextResponse } from "next/server";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

export const runtime = "nodejs";

const projectRoot = path.resolve(process.cwd(), "..");
const videoDirectory = path.join(projectRoot, "data", "sample_videos");
const sourceConfigPath = path.join(projectRoot, "data", "runtime", "cam_01_source.json");

async function availableSources() {
  const files = await readdir(videoDirectory);
  return files
    .filter((file) => file.toLowerCase().endsWith(".mp4"))
    .sort((first, second) => first.localeCompare(second, undefined, { numeric: true }))
    .map((file) => ({
      value: `data/sample_videos/${file}`,
      label: `Video ${file.replace(/\.mp4$/i, "")}`,
    }));
}

export async function GET() {
  try {
    const sources = await availableSources();
    let selectedSource = "data/sample_videos/1.1.mp4";
    try {
      const saved = JSON.parse(await readFile(sourceConfigPath, "utf8"));
      if (typeof saved.source === "string") selectedSource = saved.source;
    } catch {
      // No runtime selection yet; CAM-01 defaults to 1.mp4.
    }
    return NextResponse.json({ sources, selectedSource });
  } catch (error) {
    console.error("Unable to load CAM-01 source videos:", error);
    return NextResponse.json({ error: "Unable to load source videos." }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const { source } = await request.json();
    const sources = await availableSources();
    if (!sources.some((item) => item.value === source)) {
      return NextResponse.json({ error: "Invalid CAM-01 video source." }, { status: 400 });
    }

    await mkdir(path.dirname(sourceConfigPath), { recursive: true });
    await writeFile(sourceConfigPath, JSON.stringify({ source }), "utf8");
    return NextResponse.json({ success: true, source });
  } catch (error) {
    console.error("Unable to update CAM-01 source:", error);
    return NextResponse.json({ error: "Unable to update source video." }, { status: 500 });
  }
}
