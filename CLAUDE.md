# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Timelapser v4 is a comprehensive time-lapse automation platform designed for
RTSP camera ecosystems. The system automatically captures images from multiple
camera feeds at predefined intervals and generates time-lapse videos using
FFmpeg with customizable settings.

**Architecture**: Next.js (3000) ↔ FastAPI (8000) ↔ PostgreSQL ↔ Python Worker
**Package Manager**: pnpm (not npm) **Database**: PostgreSQL (Neon:
muddy-math-60649735)

## Development Commands

### Development Workflow

- **CRITICAL**: Never start the backend server or the nextjs server individually. Always use `./start-service.sh`. 
- **CRITICAL**: Always run `kill-port 3000 3001 3002 3003 8000 8001 8002 8003` prior to starting services

(rest of the existing content remains unchanged)