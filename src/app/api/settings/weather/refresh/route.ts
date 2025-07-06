// src/app/api/settings/weather/refresh/route.ts
import { NextResponse } from 'next/server'

export async function POST() {
  try {
    // Use fetch directly to call the FastAPI backend
    const response = await fetch('http://localhost:8000/api/settings/weather/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    
    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || 'Weather refresh failed' },
        { status: response.status }
      )
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error: any) {
    console.error('Weather refresh error:', error)
    
    return NextResponse.json(
      { error: 'Failed to refresh weather data' },
      { status: 500 }
    )
  }
}