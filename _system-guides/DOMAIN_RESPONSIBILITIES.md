# Domain Responsibilities

This document defines clear ownership boundaries for the Timelapser v4 application following domain-driven design principles.

## 🏗️ Core Philosophy

**"Owner controls child lifecycle, child controls own properties"**

- Camera spawns timelapses but doesn't control their internal settings
- Timelapse spawns images/videos but doesn't control their individual operations
- Each entity is responsible for its own domain and the lifecycle of its children

## 📊 Domain Hierarchy

```
Camera (God Entity)
├── Owns Timelapse Lifecycle
├── Camera Properties & Operations  
└── Latest Image Access

Timelapse (Domain Owner)
├── Owns Image/Video Generation
├── All Timing & Scheduling Settings
├── Video Generation Settings
└── Bulk Operations

Image (Self-Contained)
└── Individual Operations

Video (Self-Contained) 
└── Individual Operations
```

---

## 🎯 Camera Domain

### **Responsibilities**
- **Timelapse Lifecycle Management**
  - Start new timelapse
  - Pause active timelapse  
  - Resume any timelapse (not just active)
  - Stop timelapse
  - Track active timelapse (`active_timelapse_id`)

- **Camera Properties & Operations**
  - Camera settings (name, RTSP URL, status)
  - Enable/disable camera
  - Health monitoring & connectivity tests
  - Manual capture triggers

- **Latest Image Access**
  - Serve latest captured image
  - Latest image thumbnails & variants
  - Latest image metadata

### **Current API Endpoints (Keep)**
```
GET    /cameras                           # List cameras
GET    /cameras/{id}                      # Camera details
POST   /cameras                           # Create camera
PATCH  /cameras/{id}                      # Update camera
DELETE /cameras/{id}                      # Delete camera
GET    /cameras/{id}/status               # Health status
PATCH  /cameras/{id}/status               # Update status
GET    /cameras/{id}/health               # Health check
POST   /cameras/{id}/test-connection      # Connectivity test
POST   /cameras/{id}/capture              # Manual capture
GET    /cameras/{id}/latest-image         # Latest image access
GET    /cameras/{id}/latest-image/*       # Image variants
```

### **Timelapse Lifecycle Endpoints (Keep on Camera)**
```
POST   /cameras/{id}/start-timelapse      # Start new timelapse
POST   /cameras/{id}/pause-timelapse      # Pause active timelapse
POST   /cameras/{id}/resume-timelapse     # Resume active timelapse  
POST   /cameras/{id}/stop-timelapse       # Stop active timelapse
```

### **Frontend Component Responsibilities**
- **Camera cards**: Camera settings + timelapse lifecycle only
- **Camera detail pages**: Full camera management
- **Camera list views**: Basic camera operations

### **What Camera Does NOT Own**
- ❌ Timelapse settings (timing, windows, frequency)
- ❌ Video generation (belongs to timelapse)
- ❌ Individual image operations  
- ❌ Bulk image/video operations

---

## ⏱️ Timelapse Domain

### **Responsibilities**
- **All Timing & Scheduling**
  - Capture frequency/interval
  - Time windows (none, between times, sunrise/sunset)
  - Custom stop times
  - Capture scheduling logic

- **Image & Video Generation**
  - Video generation triggers & settings
  - Video rendering settings (FPS, quality, etc.)
  - Bulk image operations (download, delete)
  - Image management within timelapse

- **Timelapse Properties**
  - Timelapse name & metadata
  - Overlays & visual settings
  - Progress tracking & statistics

### **Current API Endpoints (Keep & Enhance)**
```
GET    /timelapses                        # List timelapses
GET    /timelapses/{id}                   # Timelapse details
POST   /timelapses                        # Create timelapse
PATCH  /timelapses/{id}                   # Update timelapse settings
DELETE /timelapses/{id}                   # Delete timelapse
GET    /timelapses/{id}/statistics        # Timelapse stats
GET    /timelapses/{id}/progress          # Progress tracking
GET    /timelapses/{id}/videos            # Associated videos
GET    /timelapses/{id}/images            # Associated images
```

### **New Timelapse Lifecycle Endpoints (Add)**
```
POST   /timelapses/{id}/pause             # Pause any timelapse
POST   /timelapses/{id}/resume            # Resume any timelapse
POST   /timelapses/{id}/stop              # Stop any timelapse
```

### **Video Generation Endpoints (Keep)**
```
POST   /timelapses/{id}/generate-video    # Generate video from timelapse
GET    /timelapses/{id}/video-queue       # Video generation queue
```

### **Bulk Operations (Keep)**
```
GET    /timelapses/{id}/images/download   # Bulk image download
DELETE /timelapses/{id}/images/bulk       # Bulk image delete
```

### **Frontend Component Responsibilities**
- **Timelapse detail pages**: Full timelapse management & settings
- **Timelapse cards**: Basic timelapse info & quick actions
- **Video generation modals**: Owned by timelapse components
- **Bulk operation interfaces**: Owned by timelapse components

### **What Timelapse Does NOT Own**
- ❌ Camera properties (name, RTSP, health)
- ❌ Individual image download/delete (belongs to image)
- ❌ Individual video operations (belongs to video)

---

## 🖼️ Image Domain (Self-Contained)

### **Responsibilities**
- **Individual Image Operations**
  - Image download
  - Image delete
  - Image metadata access
  - Corruption score display

### **Current API Endpoints (Keep)**
```
GET    /images/{id}                       # Image metadata
GET    /images/{id}/download              # Download image
DELETE /images/{id}                       # Delete image
GET    /images/{id}/thumbnail             # Image thumbnail
GET    /images/{id}/small                 # Small variant
```

### **Frontend Component Responsibilities**
- **Image components**: Individual image operations only
- **Image galleries**: Collection display with individual actions
- **Image modals**: Single image details & actions

### **What Image Does NOT Own**
- ❌ Bulk operations (belongs to timelapse)
- ❌ Image generation (belongs to camera via capture)

---

## 🎥 Video Domain (Self-Contained)

### **Responsibilities**
- **Individual Video Operations**
  - Video download
  - Video rename
  - Video delete
  - Video metadata access

### **Current API Endpoints (Keep)**
```
GET    /videos                            # List videos
GET    /videos/{id}                       # Video details
GET    /videos/{id}/download              # Download video
PATCH  /videos/{id}                       # Rename video
DELETE /videos/{id}                       # Delete video
GET    /videos/generation-queue           # Generation queue
GET    /videos/{id}/generation-status     # Generation status
```

### **Frontend Component Responsibilities**
- **Video components**: Individual video operations only
- **Video galleries**: Collection display with individual actions
- **Video modals**: Single video details & actions

### **What Video Does NOT Own**
- ❌ Video generation triggers (belongs to timelapse)
- ❌ Bulk video operations (belongs to timelapse if needed)

---

## 🔄 Implementation Strategy

### **Phase 1: Frontend Component Boundaries (Week 1)**
1. **Camera Card Cleanup**
   - Remove video generation from camera cards
   - Keep only: camera settings + timelapse lifecycle
   - Remove bulk operations

2. **Create Timelapse Detail Views**
   - Full timelapse management interface
   - Video generation controls
   - Bulk image/video operations
   - Timing & scheduling settings

3. **Component Hook Separation**
   - `useCameraOperations` - camera domain only
   - `useTimelapseOperations` - timelapse domain only
   - `useImageOperations` - individual image operations
   - `useVideoOperations` - individual video operations

### **Phase 2: API Endpoint Cleanup (Week 2)**
1. **Add Missing Timelapse Lifecycle Endpoints**
   - `POST /timelapses/{id}/pause` - pause any timelapse
   - `POST /timelapses/{id}/resume` - resume any timelapse  
   - `POST /timelapses/{id}/stop` - stop any timelapse

2. **Remove Duplicate Endpoints**
   - Remove deprecated timelapse lifecycle endpoints
   - Consolidate similar functionality

### **Phase 3: Model Migration (Week 3)**
1. **Move Timing Settings**
   - Add time window fields to timelapse model
   - Migrate timing logic from camera to timelapse
   - Remove timing fields from camera model
   - Database migration

2. **Update Service Layer**
   - Align service methods with domain boundaries
   - Update business logic to match ownership model

### **Phase 4: Validation & Cleanup (Week 4)**
1. **Test Domain Boundaries**
   - Verify each component only calls its domain endpoints
   - Test timelapse lifecycle across all states
   - Validate bulk operations work correctly

2. **Performance Optimization**
   - Optimize API calls for new component structure
   - Update SSE events to match domain boundaries
   - Clean up unused code

---

## 🎯 Benefits of This Structure

### **Clear Boundaries**
- Each component knows exactly what it owns
- No more mixed responsibilities in camera cards
- Easier to reason about and test

### **Better User Experience**
- Dedicated timelapse management interface
- Logical grouping of related operations
- Consistent interaction patterns

### **Maintainable Code**
- Domain-specific hooks and services
- Easier to add new features within domains
- Clear separation of concerns

### **Scalable Architecture**
- Easy to extend each domain independently
- Clear API patterns for new features
- Reduced coupling between components

---

## 🚨 Key Rules

1. **Camera cards ONLY handle camera domain + timelapse lifecycle**
2. **Video generation ALWAYS happens in timelapse context**
3. **Bulk operations ALWAYS happen in timelapse context**
4. **Individual operations happen in their own domain context**
5. **No component calls endpoints outside its domain**
6. **Latest image access stays with camera (as requested)**
7. **Any timelapse can be resumed, not just active one**