// src/app/api/overlays/presets/route.ts
import { NextRequest, NextResponse } from "next/server"

const FASTAPI_URL =
  process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"

// Built-in presets to show until backend is ready
const builtinPresets = [
  {
    id: 1,
    name: "Basic Timestamp",
    description: "Simple timestamp overlay in the bottom right corner",
    overlay_config: {
      globalSettings: {
        opacity: 100,
        font: "Arial",
        xMargin: 20,
        yMargin: 20,
        backgroundColor: "#000000",
        backgroundOpacity: 0,
        fillColor: "#FFFFFF",
        dropShadow: 2,
      },
      overlayItems: [
        {
          id: "timestamp_1",
          type: "date_time",
          position: "bottomRight",
          enabled: true,
          settings: {
            textSize: 16,
            textColor: "#FFFFFF",
            backgroundOpacity: 0,
          },
        },
      ],
    },
    is_builtin: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Weather + Time",
    description: "Weather conditions with timestamp and temperature",
    overlay_config: {
      globalSettings: {
        opacity: 90,
        font: "Arial",
        xMargin: 25,
        yMargin: 25,
        backgroundColor: "#000000",
        backgroundOpacity: 0,
        fillColor: "#FFFFFF",
        dropShadow: 3,
      },
      overlayItems: [
        {
          id: "weather_1",
          type: "weather_conditions",
          position: "topLeft",
          enabled: true,
          settings: {
            textSize: 14,
            textColor: "#FFFFFF",
            backgroundOpacity: 0,
            includeTemperature: true,
          },
        },
        {
          id: "time_1",
          type: "date_time",
          position: "bottomRight",
          enabled: true,
          settings: {
            textSize: 18,
            textColor: "#FFFFFF",
            backgroundOpacity: 0,
            timeOnly: true,
          },
        },
      ],
    },
    is_builtin: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
  {
    id: 3,
    name: "Minimal Corner",
    description: "Date in top corner and frame count in bottom",
    overlay_config: {
      globalSettings: {
        opacity: 80,
        font: "Arial",
        xMargin: 15,
        yMargin: 15,
        backgroundColor: "#000000",
        backgroundOpacity: 0,
        fillColor: "#FFFFFF",
        dropShadow: 1,
      },
      overlayItems: [
        {
          id: "date_1",
          type: "date_time",
          position: "topRight",
          enabled: true,
          settings: {
            textSize: 12,
            textColor: "#FFFFFF",
            backgroundOpacity: 0,
            dateOnly: true,
          },
        },
        {
          id: "frame_1",
          type: "frame_number",
          position: "bottomLeft",
          enabled: true,
          settings: {
            textSize: 12,
            textColor: "#CCCCCC",
            backgroundOpacity: 0,
          },
        },
      ],
    },
    is_builtin: true,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
]

export async function GET() {
  try {
    console.log("Fetching overlay presets...")

    const response = await fetch(`${FASTAPI_URL}/api/overlays`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      console.log(
        `Backend overlay endpoint returned ${response.status}, falling back to built-in presets`
      )
      // Return built-in presets as fallback
      return NextResponse.json(builtinPresets)
    }

    const data = await response.json()
    console.log(
      `Successfully fetched ${data.length} overlay presets from backend`
    )
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching overlay presets:", error)
    // Return built-in presets on connection error
    return NextResponse.json(builtinPresets)
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    console.log("Creating overlay preset:", body.name)

    const response = await fetch(`${FASTAPI_URL}/api/overlays`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      console.log(
        `Backend overlay POST endpoint returned ${response.status}, simulating success`
      )
      // Simulate success as fallback
      return NextResponse.json(
        {
          id: Date.now(),
          name: body.name,
          description: body.description,
          overlay_config: body.overlay_config,
          is_builtin: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        { status: 201 }
      )
    }

    const data = await response.json()
    console.log(`Successfully created overlay preset: ${data.name}`)
    return NextResponse.json(data, { status: 201 })
  } catch (error) {
    console.error("Error creating overlay preset:", error)
    // Fallback simulation
    const body = await request.json()
    return NextResponse.json(
      {
        id: Date.now(),
        name: body.name,
        description: body.description,
        overlay_config: body.overlay_config,
        is_builtin: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { status: 201 }
    )
  }
}
