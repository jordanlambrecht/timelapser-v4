import { NextResponse } from 'next/server';

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    
    const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_URL}/api/cameras/${id}/resume-timelapse`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      return NextResponse.json(
        { error: errorData.message || 'Failed to resume timelapse' },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error resuming timelapse:', error);
    return NextResponse.json(
      { error: 'Failed to resume timelapse' },
      { status: 500 }
    );
  }
}