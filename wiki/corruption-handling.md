# Image Corruption Detection System

The Timelapser system automatically detects and handles corrupted images from
your RTSP cameras to ensure professional-quality timelapses. This system runs
behind the scenes on every captured image, preventing corrupted frames from
ruining your videos.

## How It Works

Every image captured from your cameras receives a **corruption score** from
0-100:

- **90-100**: Excellent quality (always saved)
- **70-89**: Good quality (saved)
- **50-69**: Acceptable quality (saved)
- **30-49**: Poor quality (flagged for review)
- **0-29**: Severely corrupted (auto-discarded if enabled)

The system uses two detection methods that work together to analyze image
quality.

## Detection Methods

### Fast Detection (Always Enabled)

**File Validation** checks that images aren't corrupted during transmission.
This catches completely failed captures, files that are too small (indicating
transmission errors), or files that are unusually large (suggesting camera
malfunction).

**Pixel Analysis** examines the basic properties of the image data. It detects
images that are too dark (all black), too bright (all white), or lack sufficient
contrast variation that would indicate a functioning camera sensor.

**Uniformity Testing** identifies images where most pixels are identical, which
typically indicates camera hardware failure or transmission corruption. This
catches "stuck" cameras that output solid colors or repeated patterns.

**Format Verification** ensures the image has valid dimensions and proper file
structure. This prevents corrupted files from being processed by the video
generation system.

### Heavy Detection (Optional Per Camera)

**Blur Detection** uses computer vision to measure image sharpness. It
identifies images that are severely out of focus, which can indicate camera lens
problems, vibration issues, or autofocus failures. This keeps your timelapses
crisp and professional.

**Edge Analysis** examines the amount of detail and structure in the image. Too
few edges suggest solid color corruption or extreme overexposure, while too many
edges can indicate electrical interference or compression artifacts corrupting
the image data.

**Noise Detection** identifies excessive random pixel variations that don't
represent real image content. This catches electrical interference, poor
lighting conditions causing sensor noise, or transmission errors that add random
artifacts to your images.

**Histogram Analysis** evaluates how pixel brightness values are distributed
across the image. Poor distribution suggests exposure problems, sensor
malfunction, or compression errors that have flattened the image's tonal range.

**Pattern Detection** looks for unnatural repetitive patterns that indicate JPEG
corruption, transmission errors, or camera sensor problems. This prevents
artifact-filled images from appearing in your final timelapses.

## Settings & Configuration

### Global Settings

- **Enable/disable** corruption detection system-wide
- **Quality threshold** (default: 70) - images below this score are flagged
- **Auto-discard** severely corrupted images automatically
- **Degraded mode** - automatically disable cameras with persistent issues

### Per-Camera Settings

- **Heavy detection** can be enabled individually per camera
- Useful for problematic cameras or critical monitoring locations
- Adds ~50ms processing time per capture when enabled

### Camera Health Monitoring

The system tracks camera performance over time:

- **Degraded mode** triggers when cameras consistently produce poor images
- **Auto-disable** option prevents bad cameras from affecting system performance
- **Recovery detection** automatically re-enables cameras when they improve

## Testing Your Setup

Use the **Test Corruption Detection** tool in Settings to upload sample images
and see exactly how the system analyzes them. This helps you understand why
certain images pass or fail detection, and allows you to adjust thresholds for
your specific environment.

## When to Adjust Settings

- **Lower the threshold** (60-65) for stricter quality control
- **Enable heavy detection** on cameras with frequent issues
- **Disable auto-discard** if you want to manually review flagged images
- **Adjust degraded mode** settings based on your camera reliability

The system is designed to work automatically with minimal configuration while
giving you control when needed.
