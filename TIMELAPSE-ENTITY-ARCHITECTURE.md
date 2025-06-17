# Timelapse Entity-Based Architecture

**Document Version**: 1.0  
**Created**: June 17, 2025  
**Status**: Architecture Planning Phase

## 🎯 Overview

This document outlines the architectural shift from **status-based timelapses** to **entity-based timelapses** in Timelapser v4. This change transforms timelapses from simple status flags into concrete, trackable entities with dedicated storage organization.

## 🔄 Architectural Paradigm Shift

### Current Model (Status-Based)
```text
Camera ──► Single Timelapse Record ──► All Images
         (status changes: running/stopped/paused)
```

**Limitations:**
- One reusable timelapse record per camera
- No historical separation between recording sessions  
- Images from different time periods mixed together
- No clear boundaries for video generation scope
- Timelapse Library page lacks meaningful content

### New Model (Entity-Based)
```text
Camera ──► Multiple Timelapse Records ──► Scoped Image Collections
         (discrete recording sessions)
```

**Benefits:**
- Each "Start A New Timelapse" creates fresh timelapse entity
- Historical timelapses preserved as permanent records
- Clear data separation between recording periods
- Foundation for advanced timelapse management features
- Meaningful Timelapse Library with concrete entities

## 🗄️ Database Schema Evolution

### Current Schema
```sql
cameras (1) ──► timelapses (1) ──► images (many)
```

### New Schema
```sql
cameras (1) ──► timelapses (many) ──► images (many)
           └──► active_timelapse_id (FK to current timelapse)
```

### Required Database Changes

#### 1. Cameras Table Enhancement
```sql
-- Track which timelapse is currently active
ALTER TABLE cameras ADD COLUMN active_timelapse_id INTEGER;
ALTER TABLE cameras ADD CONSTRAINT fk_active_timelapse 
  FOREIGN KEY (active_timelapse_id) REFERENCES timelapses(id) ON DELETE SET NULL;
```

#### 2. Timelapses Status Expansion
```sql
-- Expand status options for lifecycle management
ALTER TABLE timelapses DROP CONSTRAINT timelapses_status_check;
ALTER TABLE timelapses ADD CONSTRAINT timelapses_status_check 
  CHECK (status IN ('running', 'paused', 'stopped', 'completed', 'archived'));

-- Ensure only one active timelapse per camera
CREATE UNIQUE INDEX idx_one_active_timelapse_per_camera 
  ON timelapses (camera_id) 
  WHERE status IN ('running', 'paused');
```

#### 3. Timelapse Lifecycle States
- **`running`**: Currently capturing images
- **`paused`**: Temporarily stopped, can be resumed
- **`stopped`**: User stopped, can be resumed or completed
- **`completed`**: Finished recording session, permanent historical record
- **`archived`**: Completed timelapse moved to long-term storage

## 📁 File Organization Architecture

### Current Structure (Date-Based)
```
data/
├── cameras/
│   └── camera-{id}/
│       └── images/
│           └── YYYY-MM-DD/
│               └── capture_YYYYMMDD_HHMMSS.jpg
└── videos/
    └── generated_video_files.mp4
```

### New Structure (Entity-Based)
```
data/
├── cameras/
│   ├── camera-{id}/                    # Database camera.id
│   │   ├── timelapse-{id}/            # Database timelapse.id
│   │   │   ├── frames/                # Captured images
│   │   │   │   ├── day001_143022.jpg  # Day number + timestamp
│   │   │   │   ├── day001_143522.jpg
│   │   │   │   └── day002_064512.jpg
│   │   │   └── videos/                # Generated videos
│   │   │       ├── daily_v01.mp4      # Version-controlled output
│   │   │       ├── daily_v02.mp4
│   │   │       └── weekly_v01.mp4
│   │   ├── timelapse-{id2}/           # Next timelapse session
│   │   │   ├── frames/
│   │   │   └── videos/
│   │   └── timelapse-{id3}/           # Historical timelapses
│   └── camera-{id2}/
│       └── timelapse-{id}/
└── archive/                           # Long-term storage
    └── cameras/
        └── camera-{id}/
            └── timelapse-{id}/
```

### File Naming Conventions

#### Frame Files
```
Format: day{XXX}_{HHMMSS}.jpg
Examples:
  - day001_143022.jpg  # Day 1 at 2:30:22 PM
  - day047_064512.jpg  # Day 47 at 6:45:12 AM
```

#### Video Files
```
Format: {type}_v{XX}.mp4
Examples:
  - daily_v01.mp4     # Daily compilation, version 1
  - weekly_v02.mp4    # Weekly compilation, version 2
  - custom_v01.mp4    # Custom date range, version 1
```

### Benefits of New Structure

1. **Perfect Isolation**: Each timelapse completely self-contained
2. **Clear Boundaries**: Obvious scope for video generation and cleanup
3. **Version Control**: Multiple video versions naturally organized
4. **Backup Granular**: Archive specific timelapses independently
5. **Self-Documenting**: File paths tell complete story
6. **Database Aligned**: Easy path construction from database IDs

## 🔄 Data Migration Strategy

### Phase 1: Schema Updates
```sql
-- 1. Add new columns and constraints
-- 2. Update existing timelapses to use new status options
-- 3. Set cameras.active_timelapse_id for running/paused timelapses
```

### Phase 2: File Structure Migration
```text
Current: data/cameras/camera-1/images/2025-06-17/capture_20250617_143022.jpg
New:     data/cameras/camera-1/timelapse-2/frames/day001_143022.jpg
```

**Migration Approach:**
1. **Preserve Current**: Keep existing structure intact during transition
2. **New Timelapses**: Use new structure for all newly created timelapses
3. **Background Migration**: Gradually move historical data to new structure
4. **Database Updates**: Update `images.file_path` to reflect new locations
5. **Validation**: Ensure all migrated files accessible and functional

### Phase 3: Legacy Cleanup
- Mark successfully migrated timelapses as "migrated"
- Remove old file structure after validation period
- Update all code references to use new path patterns

## 🎯 User Experience Evolution

### Camera Card Display Changes
```
Before: Total Images: 550

After:  Total Images: 1,250 (across all timelapses)
        Current Timelapse: "Storm Documentation" 
        Current Images: 47 (this session)
```

### New User Flow
1. **Start A New Timelapse**: Creates fresh timelapse entity with custom configuration
2. **Pause/Resume**: Updates status on current active timelapse
3. **Stop**: Temporarily stops, allows resume or completion
4. **Complete Timelapse**: Marks as permanent historical record
5. **Archive Timelapse**: Moves to long-term storage location

### Enhanced Features Enabled
- **Timelapse Library**: Browse historical recording sessions
- **Targeted Video Generation**: Create videos from specific timelapses
- **Timelapse Comparison**: Side-by-side analysis of different sessions
- **Granular Cleanup**: Delete specific timelapses with all associated files
- **Better Analytics**: Per-timelapse statistics and performance metrics

## 🛠️ Implementation Phases

### Phase 1: Database Foundation (Week 1)
- [ ] Create database migration for schema changes
- [ ] Update Pydantic models for new relationships
- [ ] Modify API endpoints for timelapse lifecycle management
- [ ] Update worker process to use active_timelapse_id

### Phase 2: File Organization (Week 2)
- [ ] Implement new file path generation logic
- [ ] Create directory structure for new timelapses
- [ ] Update image capture to use new file organization
- [ ] Migrate existing data to new structure

### Phase 3: UI/UX Updates (Week 3)
- [ ] Update camera cards to show total vs current timelapse images
- [ ] Enhance timelapse creation dialog with completion options
- [ ] Build timelapse history/library interface
- [ ] Update video generation to target specific timelapses

### Phase 4: Advanced Features (Week 4)
- [ ] Implement timelapse archival system
- [ ] Add timelapse comparison features
- [ ] Enhanced analytics and reporting
- [ ] Cleanup automation for completed timelapses

## 📊 Data Tracking Improvements

### Enhanced Metrics
- **Per-Camera**: Total timelapses created, total images captured, active recording days
- **Per-Timelapse**: Recording duration, image count, day count, storage usage
- **System-Wide**: Active vs completed timelapses, storage allocation, capture success rates

### Reporting Capabilities
- Timelapse completion rates and durations
- Storage usage trends per camera/timelapse
- Image capture consistency across different recording sessions
- Performance comparison between timelapses

## 🔒 Data Integrity & Cleanup

### Automatic Cleanup Policies
```yaml
completed_timelapses:
  retention_days: 365        # Keep completed timelapses for 1 year
  archive_after_days: 90     # Move to archive after 90 days
  
archived_timelapses:
  retention_days: 1825       # Keep archived timelapses for 5 years
  compression: enabled       # Compress frames for storage efficiency
```

### Data Validation
- Ensure active_timelapse_id references valid, active timelapses
- Validate file paths match database records
- Detect orphaned files and database records
- Monitor storage allocation per timelapse

## 🚀 Future Enhancement Opportunities

### Advanced Features Enabled by Entity Architecture
1. **Timelapse Templates**: Save configuration presets for common recording scenarios
2. **Collaborative Features**: Share specific timelapses with others
3. **Cloud Integration**: Sync individual timelapses to cloud storage
4. **AI Analysis**: Per-timelapse scene analysis and quality scoring
5. **Advanced Scheduling**: Chain multiple timelapses with automatic transitions

### Analytics & Insights
1. **Seasonal Patterns**: Compare timelapses across seasons/years
2. **Quality Metrics**: Track image quality and consistency per timelapse
3. **Usage Analytics**: Most successful timelapse configurations
4. **Predictive Cleanup**: Suggest timelapses ready for archival

## 📋 Migration Checklist

### Pre-Migration Validation
- [ ] Backup current database schema and data
- [ ] Document current file structure and sizes
- [ ] Test migration scripts on development data
- [ ] Validate new path generation logic

### Migration Execution
- [ ] Apply database schema changes
- [ ] Update backend code for new relationships
- [ ] Migrate existing timelapses to entity model
- [ ] Restructure files using new organization
- [ ] Update frontend to use new data model

### Post-Migration Validation
- [ ] Verify all existing functionality works
- [ ] Confirm file access and video generation
- [ ] Test new timelapse creation flow
- [ ] Validate data integrity and relationships

---

**This architecture represents a fundamental improvement in how Timelapser v4 manages and organizes time-lapse data, providing the foundation for advanced features while maintaining simplicity and clarity in the user experience.**
