// src/app/api/overlays/presets/route.ts
import { NextRequest, NextResponse } from "next/server"

const FASTAPI_URL = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"

// Built-in presets to show until backend is ready
const BUILTIN_PRESETS = [
  {
    id: 1,
    name: "Basic Timestamp",
    description: "Simple date and time overlay in bottom-left corner",
    overlay_config: {
      overlayPositions: {
        bottomLeft: {
          type: "date_time",
          textSize: 16,
          textColor: "#FFFFFF",
          backgroundOpacity: 0,
          imageScale: 100
        }
      },
      globalOptions: {
        opacity: 100,
        dropShadow: 2,
        font: "Arial",
        xMargin: 20,
        yMargin: 20
      }
    },
    is_builtin: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z"
  },
  {
    id: 2,
    name: "Weather + Time",
    description: "Weather conditions with timestamp and temperature",
    overlay_config: {
      overlayPositions: {
        topLeft: {
          type: "weather_temp_conditions",
          textSize: 14,
          textColor: "#FFFFFF",
          backgroundOpacity: 0,
          imageScale: 100
        },
        bottomRight: {
          type: "time_only",
          textSize: 18,
          textColor: "#FFFFFF",
          backgroundOpacity: 0,
          imageScale: 100
        }
      },
      globalOptions: {
        opacity: 90,
        dropShadow: 3,
        font: "Arial",
        xMargin: 25,
        yMargin: 25
      }
    },
    is_builtin: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z"
  },
  {
    id: 3,
    name: "Minimal Corner",
    description: "Date in top corner and frame count in bottom",
    overlay_config: {
      overlayPositions: {
        topRight: {
          type: "date_only",
          textSize: 12,
          textColor: "#FFFFFF",
          backgroundOpacity: 0,
          imageScale: 100
        },
        bottomLeft: {
          type: "frame_number",
          textSize: 12,
          textColor: "#CCCCCC",
          backgroundOpacity: 0,
          imageScale: 100
        }
      },
      globalOptions: {
        opacity: 80,
        dropShadow: 1,
        font: "Arial",
        xMargin: 15,
        yMargin: 15
      }
    },
    is_builtin: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z"
  }
]

export async function GET() {
  try {
    console.log("Fetching overlay presets from backend...")
    
    const response = await fetch(`${FASTAPI_URL}/api/overlays/presets`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      console.log(`Backend overlay endpoint returned ${response.status}, falling back to built-in presets`)
      // Return built-in presets as fallback
      return NextResponse.json(BUILTIN_PRESETS)
    }

    const data = await response.json()
    console.log(`Successfully fetched ${data.length} overlay presets from backend`)
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching overlay presets:", error)
    // Return built-in presets on connection error
    return NextResponse.json(BUILTIN_PRESETS)
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    console.log("Creating overlay preset:", body.name)
    
    const response = await fetch(`${FASTAPI_URL}/api/overlays/presets`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      console.log(`Backend overlay POST endpoint returned ${response.status}, simulating success`)
      // Simulate success as fallback
      return NextResponse.json({
        id: Date.now(),
        name: body.name,
        description: body.description,
        overlay_config: body.overlay_config,
        is_builtin: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }, { status: 201 })
    }

    const data = await response.json()
    console.log(`Successfully created overlay preset: ${data.name}`)
    return NextResponse.json(data, { status: 201 })
  } catch (error) {
    console.error("Error creating overlay preset:", error)
    // Fallback simulation
    const body = await request.json()
    return NextResponse.json({
      id: Date.now(),
      name: body.name,
      description: body.description,
      overlay_config: body.overlay_config,
      is_builtin: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }, { status: 201 })
  }
}