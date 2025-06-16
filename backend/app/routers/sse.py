from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import asyncio
import json
from loguru import logger

from ..database import async_db
from ..models.camera import transform_camera_with_image_row

router = APIRouter()


class SSEManager:
    """Manage Server-Sent Events connections"""

    def __init__(self):
        self.connections = set()

    def add_connection(self, generator):
        """Add a new SSE connection"""
        self.connections.add(generator)

    def remove_connection(self, generator):
        """Remove an SSE connection"""
        self.connections.discard(generator)

    async def broadcast(self, data: dict):
        """Broadcast data to all connected clients"""
        if not self.connections:
            return

        message = f"data: {json.dumps(data)}\n\n"
        dead_connections = set()

        for connection in self.connections.copy():
            try:
                await connection.asend(message)
            except Exception:
                dead_connections.add(connection)

        # Remove dead connections
        for connection in dead_connections:
            self.connections.discard(connection)


# Global SSE manager
sse_manager = SSEManager()


async def camera_status_stream() -> AsyncGenerator[str, None]:
    """Generate camera status updates via SSE"""
    try:
        # Send initial data
        cameras_data = await async_db.get_cameras_with_images()
        cameras = [
            transform_camera_with_image_row(camera).model_dump()
            for camera in cameras_data
        ]
        yield f"data: {json.dumps({'type': 'cameras', 'data': cameras})}\n\n"

        # Keep connection alive and send periodic updates
        while True:
            await asyncio.sleep(5)  # Update every 5 seconds

            try:
                cameras_data = await async_db.get_cameras_with_images()
                cameras = [
                    transform_camera_with_image_row(camera).model_dump()
                    for camera in cameras_data
                ]
                yield f"data: {json.dumps({'type': 'cameras', 'data': cameras})}\n\n"
            except Exception as e:
                logger.error(f"Error in SSE stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    except asyncio.CancelledError:
        logger.info("SSE connection cancelled")
    except Exception as e:
        logger.error(f"SSE stream error: {e}")


@router.get("/camera-status")
async def camera_status_sse():
    """Server-Sent Events endpoint for real-time camera status"""

    async def generate():
        async for data in camera_status_stream():
            yield data

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )
