# Data File Structure

The thumbnail system uses a separate directory structure to isolate different
image variants and enable independent management policies:

Files are all datestamped and timestamped.

Content is grouped by timelapse.

```
data/
├── cameras/
│   ├── camera-{id}/                    # Database camera.id
│   │   ├── timelapse-{id}/            # Database timelapse.id
│   │   │   ├── frames/                # Captured images
│   │   │   │   ├── timelapse-{id}_20250422_143022.jpg  # ID + Datestamp + timestamp
│   │   │   │   ├── timelapse-{id}_20250422_143522.jpg
│   │   │   │   └── timelapse-{id}_20250423_064512.jpg
│   │   │   ├── overlays/                # generated frame overlays
│   │   │   │   ├── timelapse-{id}_20250422_143022_overlay.jpg  # ID + Datestamp + timestamp
│   │   │   │   ├── timelapse-{id}_20250422_143522_overlay.jpg
│   │   │   │   └── timelapse-{id}_20250423_064512_overlay.jpg
│   │   │   ├── thumbnails/            # Generated thumbnails
│   │   │   │   ├── timelapse-{id}_thumb_20250422_143022.jpg  # 200×150 dashboard optimized
│   │   │   │   ├── timelapse-{id}_thumb_20250422_143522.jpg
│   │   │   │   └── timelapse-{id}_thumb_20250423_064512.jpg
│   │   │   ├── smalls/                # Generated small images
│   │   │   │   ├── timelapse-{id}_small_20250422_143022.jpg  # 800×600 medium quality
│   │   │   │   ├── timelapse-{id}_small_20250422_143522.jpg
│   │   │   │   └── timelapse-{id}_small_20250423_064512.jpg
│   │   │   └── videos/                # Generated videos
│   │   │       ├── daily_v01.mp4
│   │   │       └── weekly_v02.mp4
│   │   ├── timelapse-{id2}/
│   │   │   ├── frames/
│   │   │       ├── ...
│   │   │   ├── overlays/
│   │   │       ├── ...
│   │   │   ├── thumbnails/
│   │   │       ├── ...
│   │   │   ├── smalls/
│   │   │       ├── ...
│   │   │   └── videos/
│   │   │       ├── ...
│   │   └── timelapse-{id3}/          # Historical timelapses
│   └── camera-{id2}/
│       └── timelapse-{id}/
│   │       ├── ...

```
