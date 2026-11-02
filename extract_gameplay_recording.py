import os
import sys
import time
import json
import cv2
import numpy as np

def extract_gameplay_events(video_path, output_dir=None, progress_callback=None):
    """
    Mengekstrak momen-momen gameplay kunci dari file video recording Roblox Sambung Kata
    menggunakan jaring lebar (High-Recall Visual Motion & Color Spike Filter).
    
    Output:
    - Frame gambar PNG disimpan ke output_dir (default: deteksi-gameplay/unclassified/)
    - Metadata JSON tiap frame
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"File video tidak ditemukan: {video_path}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if output_dir is None:
        output_dir = os.path.join(base_dir, "deteksi-gameplay", "unclassified")
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Tidak dapat membuka file video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration_sec = total_frames / fps if fps > 0 else 0

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    # Bersihkan nama video dari karakter ilegal
    clean_vname = "".join(c for c in video_name if c.isalnum() or c in ('_', '-'))

    print(f"[*] Membuka video: {os.path.basename(video_path)}")
    print(f"[*] Durasi: {duration_sec:.1f} detik ({total_frames} frame, {fps:.1f} FPS)")
    print(f"[*] Menyimpan kandidat momen ke: {output_dir}")

    # Tentukan step sampling: target ~12-15 frame per detik
    step = max(1, int(round(fps / 15.0)))

    frame_idx = 0
    saved_count = 0
    cooldown_frames = int(fps * 1.5)  # Cooldown 1.5 detik antar-event
    last_trigger_frame = -cooldown_frames
    last_trigger_type = None

    prev_green = 0
    prev_red = 0
    prev_gray_roi = None

    t_start = time.time()
    last_reported_pct = -1

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        if frame_idx % step != 0:
            continue

        H, W = frame.shape[:2]

        # Area fokus gameplay (y: 15%..55%, x: 30%..70%)
        y1, y2 = int(H * 0.15), int(H * 0.55)
        x1, x2 = int(W * 0.30), int(W * 0.70)
        roi = frame[y1:y2, x1:x2]

        # 1. Hitung Redness Score (Kotak kata salah / sudah digunakan)
        b, g, r = cv2.split(roi.astype(np.int16))
        redness = r - np.maximum(b, g)
        red_score = int(np.count_nonzero((redness > 30) & (r > 90)))

        # 2. Hitung Greenness Score (Flash hijau jawaban benar)
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        green_mask = cv2.inRange(hsv_roi, np.array([35, 70, 70]), np.array([85, 255, 255]))
        green_score = int(np.count_nonzero(green_mask))

        # 3. Hitung Frame Difference Kasar
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if prev_gray_roi is not None:
            diff_score = int(np.count_nonzero(cv2.absdiff(gray_roi, prev_gray_roi) > 30))
        else:
            diff_score = 0
        prev_gray_roi = gray_roi

        # Evaluasi Trigger (Jaring Lebar)
        is_in_cooldown = (frame_idx - last_trigger_frame) < cooldown_frames
        trigger_type = None
        trigger_reason = ""

        # A. Trigger Merah (Kotak berubah merah)
        if not is_in_cooldown and red_score > 1000 and (red_score - prev_red > 400 or red_score > 2000):
            trigger_type = "RED_SPIKE"
            trigger_reason = f"Redness melonjak: {red_score} px (delta={red_score - prev_red})"

        # B. Trigger Hijau (Tubuh flash hijau)
        elif not is_in_cooldown and green_score > 6000 and (green_score - prev_green > 3000 or green_score > 12000):
            trigger_type = "GREEN_FLASH"
            trigger_reason = f"Greenness melonjak: {green_score} px (delta={green_score - prev_green})"

        if trigger_type:
            last_trigger_frame = frame_idx
            last_trigger_type = trigger_type
            saved_count += 1
            cur_sec = frame_idx / fps

            # Format nama file: rec_<vname>_sec<S>_<trigger>.png
            base_filename = f"rec_{clean_vname}_sec{int(cur_sec):04d}_frame{frame_idx}_{trigger_type}"
            img_path = os.path.join(output_dir, f"{base_filename}.png")
            meta_path = os.path.join(output_dir, f"{base_filename}.json")

            # Simpan full frame (resolusi penuh untuk kalibrasi & ROI ground truth)
            cv2.imwrite(img_path, frame)

            metadata = {
                "source_video": os.path.basename(video_path),
                "frame_index": frame_idx,
                "timestamp_sec": round(cur_sec, 2),
                "trigger_type": trigger_type,
                "trigger_reason": trigger_reason,
                "metrics": {
                    "red_score": red_score,
                    "green_score": green_score,
                    "diff_score": diff_score
                }
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4)

            print(f"  [+] Momen {saved_count:2d} terdeteksi di detik {cur_sec:6.1f}s ({trigger_type})")

        prev_red = red_score
        prev_green = green_score

        # Laporan progres
        pct = int((frame_idx / total_frames) * 100)
        if pct != last_reported_pct and pct % 10 == 0:
            last_reported_pct = pct
            elapsed = time.time() - t_start
            print(f"    Progres: {pct}% ({frame_idx}/{total_frames} frame, waktu: {elapsed:.1f}s)")
            if progress_callback:
                progress_callback(pct, saved_count)

    cap.release()
    total_time = time.time() - t_start
    print(f"\n[OK] Ekstraksi Selesai dalam {total_time:.1f} detik!")
    print(f"[OK] Total kandidat momen tersimpan: {saved_count} frame di {output_dir}")
    return saved_count, output_dir


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_video = sys.argv[1]
    else:
        # Cari file video terbaru di folder deteksi-gameplay/recordings/
        rec_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deteksi-gameplay", "recordings")
        valid_exts = ('.mp4', '.mkv', '.avi', '.mov', '.webm')
        found_videos = [
            os.path.join(rec_dir, f) for f in os.listdir(rec_dir)
            if f.lower().endswith(valid_exts)
        ] if os.path.exists(rec_dir) else []

        if found_videos:
            found_videos.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            target_video = found_videos[0]
            print(f"[*] Menggunakan video terbaru dari recordings/: {os.path.basename(target_video)}")
        else:
            print("Penggunaan: python extract_gameplay_recording.py <path_ke_file_video.mp4>")
            print(f"Atau taruh file video di folder: {rec_dir}")
            sys.exit(0)

    extract_gameplay_events(target_video)
