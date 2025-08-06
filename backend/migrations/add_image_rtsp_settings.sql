-- Add missing image quality and RTSP timeout settings
-- These settings control image capture quality and RTSP connection timeouts

-- Add image_quality setting (JPEG quality 1-100, default 90)
INSERT INTO settings (key, value, created_at, updated_at)
VALUES ('image_quality', '90', NOW(), NOW())
ON CONFLICT (key) DO NOTHING;

-- Add rtsp_timeout_seconds setting (timeout for RTSP connections, default 10)
INSERT INTO settings (key, value, created_at, updated_at)
VALUES ('rtsp_timeout_seconds', '10', NOW(), NOW())
ON CONFLICT (key) DO NOTHING;

-- Verify settings were added
SELECT key, value FROM settings 
WHERE key IN ('image_quality', 'rtsp_timeout_seconds')
ORDER BY key;