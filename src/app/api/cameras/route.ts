import { NextRequest, NextResponse } from "next/server"
import { sql } from "@/lib/db"
import fs from "fs/promises"
import path from "path"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/app/api/events/route"

export async function GET() {
  try {
    // Assumes 'images' table has 'camera_id', 'captured_at', and 'file_name'
    // The TO_CHAR function formats the captured_at timestamp to 'YYYY-MM-DD' for the directory
    const cameras = await sql`
      SELECT 
        c.*,
        (
          SELECT 
            TO_CHAR(i.captured_at, \'YYYY-MM-DD\') || \'/\' || i.file_name
          FROM images i
          WHERE i.camera_id = c.id
          ORDER BY i.captured_at DESC
          LIMIT 1
        ) as last_image_relative_path 
      FROM cameras c
      ORDER BY c.created_at DESC
    `

    const camerasWithImagePaths = await Promise.all(
      cameras.map(async (camera: any) => {
        if (camera.last_image_relative_path) {
          const imageFileExistsPath = path.join(
            process.cwd(),
            "data",
            "cameras",
            `camera-${camera.id}`, // Assuming camera.id is the identifier for the folder
            "images",
            camera.last_image_relative_path
          )
          try {
            await fs.access(imageFileExistsPath)
            camera.last_image_path = `/data/cameras/camera-${
              camera.id
            }/images/${camera.last_image_relative_path}?t=${Date.now()}`
          } catch (error) {
            camera.last_image_path = null
          }
        } else {
          camera.last_image_path = null
        }
        // Keep the original relative path for clarity if needed, or remove if not
        // delete camera.last_image_relative_path;
        return camera
      })
    )

    return NextResponse.json(camerasWithImagePaths)
  } catch (error) {
    console.error("Database error:", error)
    return NextResponse.json(
      { error: "Failed to fetch cameras" },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const {
      name,
      rtsp_url,
      use_time_window,
      time_window_start,
      time_window_end,
    } = await request.json()

    if (!name || !rtsp_url) {
      return NextResponse.json(
        { error: "Name and RTSP URL are required" },
        { status: 400 }
      )
    }

    const timeWindowEnabled = use_time_window || false
    const startTime = time_window_start ? time_window_start + ":00" : "06:00:00"
    const endTime = time_window_end ? time_window_end + ":00" : "18:00:00"

    const result = await sql`
      INSERT INTO cameras (
        name, 
        rtsp_url, 
        status,
        use_time_window,
        time_window_start,
        time_window_end
      ) VALUES (
        ${name}, 
        ${rtsp_url}, 
        'active',
        ${timeWindowEnabled},
        ${startTime},
        ${endTime}
      ) RETURNING *
    `

    const newCamera = result[0]

    // Broadcast camera added event
    eventEmitter.emit({
      type: 'camera_added',
      camera: newCamera,
      timestamp: new Date().toISOString()
    })

    return NextResponse.json(newCamera, { status: 201 })
  } catch (error) {
    console.error("Database error:", error)
    return NextResponse.json(
      { error: "Failed to create camera" },
      { status: 500 }
    )
  }
}
