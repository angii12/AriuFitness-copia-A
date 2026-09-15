from pathlib import Path

import cv2


def extract_clips(video_path, segments, output_dir):
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Impossibile aprire il video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    try:
        for segment in segments:
            rep = int(segment["rep"])
            start = int(segment["start_frame"])
            end = int(segment["end_frame"])
            out = output_dir / f"rep_{rep:02d}.mp4"
            writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            for _ in range(start, end + 1):
                ok, frame = cap.read()
                if not ok:
                    break
                writer.write(frame)
            writer.release()
    finally:
        cap.release()
