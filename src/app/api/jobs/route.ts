import { NextResponse } from "next/server"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export async function GET() {
  try {
    // Fetch jobs data from the backend
    const response = await fetch(`${API_BASE_URL}/api/jobs/status`, {
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store'
    })

    if (!response.ok) {
      throw new Error(`Backend responded with status: ${response.status}`)
    }

    const data = await response.json()
    
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to fetch jobs:", error)
    
    // Return mock data for now if the backend endpoint doesn't exist yet
    return NextResponse.json({
      scheduled: [],
      running: [],
      recent: [],
      stats: {
        total_scheduled: 0,
        total_running: 0,
        total_completed_today: 0,
        total_failed_today: 0
      }
    })
  }
}