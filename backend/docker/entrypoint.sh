#!/bin/bash
set -euo pipefail

# Production Docker entrypoint for Timelapser v4
# Handles database initialization with hybrid approach

SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_NAME
readonly LOG_PREFIX="[${SCRIPT_NAME}]"

# Configuration
readonly MAX_DB_WAIT_TIME=60
readonly HEALTH_CHECK_INTERVAL=2

log() {
    echo "${LOG_PREFIX} [$(date +'%Y-%m-%d %H:%M:%S')] $*" >&2
}

error() {
    log "ERROR: $*"
    exit 1
}

check_required_env() {
    local missing_vars=()
    local required_vars=("DATABASE_URL")
    
    # Check required environment variables
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -ne 0 ]]; then
        error "Missing required environment variables: ${missing_vars[*]}"
    fi
    
    log "Environment variables validated"
}

wait_for_database() {
    log "Waiting for database connection..."
    
    local attempt=1
    local max_attempts=$((MAX_DB_WAIT_TIME / HEALTH_CHECK_INTERVAL))
    
    while [[ $attempt -le $max_attempts ]]; do
        if python3 -c "
import psycopg
import os
import sys
try:
    with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
    sys.exit(0)
except Exception:
    sys.exit(1)
" >/dev/null 2>&1; then
            log "Database connection established"
            return 0
        fi
        
        log "Database not ready (attempt $attempt/$max_attempts)"
        sleep $HEALTH_CHECK_INTERVAL
        ((attempt++))
    done
    
    error "Database connection timeout after ${MAX_DB_WAIT_TIME}s"
}

initialize_database() {
    log "Initializing database..."
    
    if ! python3 -m app.database.migrations; then
        error "Database initialization failed"
    fi
    
    log "Database initialization completed"
}

start_api_server() {
    log "Starting API server..."
    exec python3 -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "${API_PORT:-8000}" \
        --workers "${API_WORKERS:-1}" \
        --log-level "${LOG_LEVEL:-info}"
}

start_worker() {
    log "Starting background workers..."
    exec python3 worker.py
}

run_migrations_only() {
    log "Running database migrations only..."
    initialize_database
    log "Migrations completed - exiting"
    exit 0
}

show_help() {
    cat << EOF
Timelapser v4 Docker Entrypoint

Usage: $0 [COMMAND]

Commands:
  api        Start FastAPI web server (default)
  worker     Start background worker processes
  migrate    Run database migrations only and exit
  help       Show this help message

Environment Variables:
  DATABASE_URL    PostgreSQL connection URL (required)
  API_PORT        API server port (default: 8000)
  API_WORKERS     Number of API workers (default: 1)
  LOG_LEVEL       Logging level (default: info)

EOF
}

main() {
    local command="${1:-api}"
    
    case "$command" in
        "api"|"web"|"")
            check_required_env
            wait_for_database
            initialize_database
            start_api_server
            ;;
        "worker"|"background")
            check_required_env
            wait_for_database
            initialize_database
            start_worker
            ;;
        "migrate"|"migration")
            check_required_env
            wait_for_database
            run_migrations_only
            ;;
        "help"|"--help"|"-h")
            show_help
            exit 0
            ;;
        *)
            error "Unknown command: $command. Use 'help' for usage information."
            ;;
    esac
}

# Handle signals gracefully
trap 'log "Received termination signal"; exit 143' TERM INT

# Run main function
main "$@"