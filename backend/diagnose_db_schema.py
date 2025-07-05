#!/usr/bin/env python3
"""
Database Schema Diagnostic Script

This script checks for missing columns that are causing database errors.
Run this to diagnose schema issues before applying migrations.
"""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.append(str(backend_dir))

try:
    from app.config import Settings
    from app.database.core import AsyncDatabase
    import asyncio
    import psycopg
    
    # Load settings to get database URL
    settings = Settings()
    DATABASE_URL = settings.database_url
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the backend directory and virtual environment is activated")
    sys.exit(1)
except Exception as e:
    print(f"Configuration error: {e}")
    print("Make sure environment variables are set correctly")
    sys.exit(1)


async def check_database_schema():
    """Check database schema for expected columns"""
    
    print("🔍 Checking database schema...")
    print(f"Database URL: {DATABASE_URL[:50]}...")
    
    try:
        # Test basic connection
        conn = await psycopg.AsyncConnection.connect(DATABASE_URL)
        async with conn:
            print("✅ Database connection successful")
            
            async with conn.cursor() as cur:
                # Check cameras table columns
                await cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'cameras' 
                    ORDER BY ordinal_position;
                """)
                camera_columns = await cur.fetchall()
                
                print(f"\n📊 Cameras table has {len(camera_columns)} columns:")
                for col in camera_columns:
                    print(f"  • {col[0]}: {col[1]} (nullable: {col[2]})")
                
                # Check specifically for problematic columns
                expected_camera_columns = [
                    'video_automation_mode',
                    'generation_schedule',
                    'milestone_config',
                    'video_generation_mode'
                ]
                
                camera_column_names = [col[0] for col in camera_columns]
                missing_camera_columns = []
                
                print(f"\n🎯 Checking for expected automation columns in cameras table:")
                for col in expected_camera_columns:
                    if col in camera_column_names:
                        print(f"  ✅ {col} - EXISTS")
                    else:
                        print(f"  ❌ {col} - MISSING")
                        missing_camera_columns.append(col)
                
                # Check timelapses table columns  
                await cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'timelapses' 
                    ORDER BY ordinal_position;
                """)
                timelapse_columns = await cur.fetchall()
                
                print(f"\n📊 Timelapses table has {len(timelapse_columns)} columns:")
                
                expected_timelapse_columns = [
                    'video_automation_mode',
                    'generation_schedule',
                    'milestone_config',
                    'video_generation_mode'
                ]
                
                timelapse_column_names = [col[0] for col in timelapse_columns]
                missing_timelapse_columns = []
                
                print(f"\n🎯 Checking for expected automation columns in timelapses table:")
                for col in expected_timelapse_columns:
                    if col in timelapse_column_names:
                        print(f"  ✅ {col} - EXISTS")
                    else:
                        print(f"  ❌ {col} - MISSING")
                        missing_timelapse_columns.append(col)
                
                # Check alembic version
                try:
                    await cur.execute("SELECT version_num FROM alembic_version;")
                    version = await cur.fetchone()
                    if version:
                        print(f"\n📋 Current Alembic migration: {version[0]}")
                    else:
                        print("\n❌ No Alembic version found - migrations may not be initialized")
                except Exception as e:
                    print(f"\n❌ Could not read Alembic version: {e}")
                
                # Test the problematic query
                print(f"\n🧪 Testing the problematic query...")
                try:
                    await cur.execute("""
                        SELECT 
                            t.id,
                            COALESCE(t.generation_schedule, c.generation_schedule) as schedule
                        FROM timelapses t
                        JOIN cameras c ON t.camera_id = c.id
                        WHERE t.status = 'running'
                        LIMIT 1
                    """)
                    print("  ✅ Query executed successfully")
                except Exception as e:
                    print(f"  ❌ Query failed: {e}")
                
                # Summary
                total_missing = len(missing_camera_columns) + len(missing_timelapse_columns)
                if total_missing == 0:
                    print(f"\n🎉 All expected columns are present!")
                else:
                    print(f"\n⚠️  Found {total_missing} missing columns")
                    if missing_camera_columns:
                        print(f"   Missing from cameras: {', '.join(missing_camera_columns)}")
                    if missing_timelapse_columns:
                        print(f"   Missing from timelapses: {', '.join(missing_timelapse_columns)}")
                    print(f"\n💡 Run 'alembic upgrade head' to apply missing migrations")
                
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("📋 Database Schema Diagnostic Tool")
    print("=" * 50)
    
    # Run the async function
    success = asyncio.run(check_database_schema())
    
    if success:
        print("\n✅ Diagnostic completed successfully")
    else:
        print("\n❌ Diagnostic failed")
        sys.exit(1)