#!/usr/bin/env python3
import os

filepath = r"D:\software Projects\SIH\ibvap-full-project\modules\human_detection_tracking\main.py"

with open(filepath, "r") as f:
    content = f.read()

# The exact ending
old_end = '        print("Application terminated cleanly.")\n\n\nif __name__ == "__main__":\n    main()'

new_end = '''        print("Application terminated cleanly.")


# ---- FastAPI / MJPEG Streaming Setup ----
# Global frame variable accessible by the generator
global annotated_frame
# Initialize FastAPI app
app = FastAPI()

# Frame generator for MJPEG stream
def generate_frames():
    while running_mode["value"]:
        if annotated_frame is not None:
            (flag, buffer) = cv2.imencode(".jpg", annotated_frame)
            if flag:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        else:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'empty' + b'\r\n')

# FastAPI route for video feed
@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(),
                           media_type="multipart/x-mixed-replace; boundary=frame")

# Shared state for thread control
running_mode = {"value": True}

# Start FastAPI server in a daemon thread
api_thread = threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning"), daemon=True)
api_thread.start()

if __name__ == "__main__":
    main()'''

if old_end in content:
    content = content.replace(old_end, new_end)
    with open(filepath, "w") as f:
        f.write(content)
    print("Successfully updated main.py")
else:
    print("Could not find target section to replace")
    # Show what's at the end
    print("Last 150 chars:", repr(content[-150:]))