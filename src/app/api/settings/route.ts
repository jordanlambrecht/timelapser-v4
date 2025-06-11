import { NextRequest, NextResponse } from "next/server"
import { sql } from "@/lib/db"

export async function GET() {
  try {
    const settings = await sql`
      SELECT * FROM settings 
      ORDER BY key
    `

    // Convert to key-value object for easier frontend consumption
    const settingsObj = settings.reduce((acc: any, setting: any) => {
      acc[setting.key] = setting.value
      return acc
    }, {})

    return NextResponse.json(settingsObj)
  } catch (error) {
    console.error("Database error:", error)
    return NextResponse.json(
      { error: "Failed to fetch settings" },
      { status: 500 }
    )
  }
}

export async function PUT(request: NextRequest) {
  try {
    const { key, value } = await request.json()

    if (!key || value === undefined) {
      return NextResponse.json(
        { error: "Key and value are required" },
        { status: 400 }
      )
    }

    const result = await sql`
      INSERT INTO settings (key, value) 
      VALUES (${key}, ${value})
      ON CONFLICT (key) 
      DO UPDATE SET value = ${value}, updated_at = CURRENT_TIMESTAMP
      RETURNING *
    `

    return NextResponse.json(result[0])
  } catch (error) {
    console.error("Database error:", error)
    return NextResponse.json(
      { error: "Failed to update setting" },
      { status: 500 }
    )
  }
}
