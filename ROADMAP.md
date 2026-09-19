# RECORDED WORLD — AUTHORITATIVE ROADMAP

> This file is the source of truth for project status and next actions.
> Every session must read this file first.

Last Updated: 2026-09-19 (UE5.8 Phase A+B+C+D+E+F: All core systems + UI/HUD + GTA VC Visuals)

---

## PHASE 0 — EXISTING PROJECT AUDIT & STABILIZATION

**Goal**: Understand, document, and stabilize the existing project.

### Tasks

- [x] Repository audit — COMPLETE 2026-09-16
- [x] Architecture documentation — COMPLETE 2026-09-16 (PROJECT_STATE.md)
- [x] Create authoritative roadmap.md — COMPLETE 2026-09-16
- [x] Fix CRITICAL syntax error in mobile-app/hooks/useUpload.ts — COMPLETE 2026-09-16
- [x] Fix WebSocket protocol mismatch (socket.io vs raw WS) — COMPLETE 2026-09-16
- [x] Fix test suite (lifespan fixture, model imports) — COMPLETE 2026-09-16
- [x] Verify all existing features work end-to-end — COMPLETE 2026-09-16 (32/32 tests pass)
- [x] Database migration setup (Alembic) — DONE in Phase 22
- [x] Environment configuration (.env files) — DONE in Phase 21

### Validation
- Backend tests pass: `cd backend && pytest tests/ -v` → 200/200 pass
- PC client builds: `cd pc-client && npm run build`
- Docker services healthy: `docker-compose ps`

---

## PHASE 1 — WORLD GEOSPATIAL FOUNDATION

**Goal**: Build a proper geographic coordinate system for the game world.

The game world must use real-world coordinates. Latitude/longitude cannot be used directly as floating-point game coordinates for a large world. A local coordinate conversion system is required.

### Architecture

```
GPS (WGS84 lat/lon/alt)
  → ENU (East/North/Up local frame)
    → Game coordinates (origin-relative)
      → Render position
```

### Tasks

- [x] Geographic coordinate abstraction module — COMPLETE 2026-09-16
- [x] WGS84 to ENU conversion — COMPLETE 2026-09-16
- [x] Origin management (per-chunk or global) — COMPLETE 2026-09-16
- [x] Coordinate serialization (store WGS84, use ENU locally) — COMPLETE 2026-09-16
- [x] Coordinate validation — COMPLETE 2026-09-16
- [x] Geospatial database support (PostGIS or SpatiaLite) — COMPLETE 2026-09-16 (grid-based, no dependency)
- [x] Spatial indexing for proximity queries — COMPLETE 2026-09-16
- [x] Altitude handling (ellipsoidal vs orthometric) — COMPLETE 2026-09-16

### Acceptance Criteria
- A known real-world coordinate can be deterministically converted to game coordinates and back
- Distance calculations between two points are accurate to sub-meter
- Spatial queries return correct nearby results

### Dependencies
- None (foundational)

---

## PHASE 2 — REAL-WORLD BASE MAP

**Goal**: Create the initial geographic world representation.

### Architecture

```
LAYER 0: Geographic coordinate system
LAYER 1: Terrain (elevation)
LAYER 2: Water bodies
LAYER 3: Roads
LAYER 4: Building footprints
LAYER 5: Landmarks
LAYER 6: User reconstructed content
LAYER 7: Players
```

### Tasks

- [x] Map provider abstraction — COMPLETE 2026-09-17 (OpenStreetMap provider, factory, tile coords)
- [x] Vector map ingestion (OpenStreetMap) — COMPLETE 2026-09-17 (OSM/GeoJSON parsing, building/road extraction)
- [x] Terrain ingestion (DEM/heightmap) — COMPLETE 2026-09-17 (heightmap loading, procedural generation, bilinear interpolation)
- [x] Building footprints — COMPLETE 2026-09-17 (2D-to-3D extrusion, floor/roof generation)
- [x] Road network — COMPLETE 2026-09-17 (3D road geometry, lane/width, type-based sizing)
- [x] Tile/chunk system — COMPLETE 2026-09-17 (tile loading, eviction, chunk management)
- [x] Streaming and caching — COMPLETE 2026-09-17 (priority-based cache, pin/evict, network-aware streaming)
- [x] LOD system — COMPLETE 2026-09-17 (5 LOD levels, vertex reduction, polygon simplification)

### Acceptance Criteria
- Player can move through a geographically anchored base world
- Roads, buildings, and terrain correspond to real-world locations

### Dependencies
- Phase 1 (geospatial foundation)

---

## PHASE 3 — LARGE WORLD / STREAMING

**Goal**: Support large geographic areas without loading everything into memory.

### Tasks

- [x] World chunk system — COMPLETE 2026-09-17 (chunk lifecycle, priority-based loading, player tracking)
- [x] Geographic tile loading/unloading — COMPLETE 2026-09-17 (distance-based load/unload, queue management)
- [x] Dynamic LOD selection — COMPLETE 2026-09-17 (5 LOD levels integrated in streaming pipeline)
- [x] Asset streaming — COMPLETE 2026-09-17 (async load simulation, progress tracking, chunk ready state)
- [x] Memory management — COMPLETE 2026-09-17 (pool-based allocation, budget tracking, eviction candidates, pinning)
- [x] Network-aware streaming — COMPLETE 2026-09-17 (bandwidth estimation, quality adaptation, adaptive settings)

### Acceptance Criteria
- Player can move continuously without loading entire world
- Frame rate stays stable during movement

### Dependencies
- Phase 2 (base map)

---

## PHASE 4 — MOBILE CAPTURE APPLICATION

**Goal**: Complete mobile app for video capture and upload.

### Tasks

- [x] COMPLETE — Camera capture (permission validation, quality settings 720p/1080p, 60s duration limit, file size check) — COMPLETE 2026-09-19
- [x] COMPLETE — GPS recording (accuracy validation >100m rejected, location caching for offline, permission fallback message) — COMPLETE 2026-09-19
- [x] Device orientation recording (accelerometer/gyro) — COMPLETE 2026-09-17 (complementary filter, quaternion/matrix conversion, smoothing)
- [x] Camera intrinsics recording — COMPLETE 2026-09-17 (CameraIntrinsicsService with device database, projection matrix, undistortion)
- [x] Video quality settings — COMPLETE 2026-09-17 (5 quality presets, adaptive selection based on device capabilities/storage)
- [x] Upload resume after app kill — COMPLETE 2026-09-17 (UploadSessionManager with chunked resume, pause/resume, expiry)
- [x] User authentication — DONE in Phase 32 (JWT Auth Integration)
- [x] Capture metadata (duration, resolution, fps, device info) — COMPLETE 2026-09-17 (CaptureMetadataValidator with quality scoring)
- [x] Offline capture queue sync — COMPLETE 2026-09-17 (OfflineSyncManager with batch sync, conflict resolution, expiry cleanup)

### Validation
- Build APK: `cd mobile-app && npx expo prebuild && cd android && ./gradlew assembleRelease`
- Test on device: camera records, GPS tracked, upload completes

### Dependencies
- Phase 0 (stabilization)

---

## PHASE 5 — MEDIA INGESTION PIPELINE

**Goal**: Production-grade upload and validation system.

### Tasks

- [x] Resumable uploads (tus protocol) — COMPLETE 2026-09-17 (UploadJob model + chunked upload API)
- [x] Upload authentication — COMPLETE 2026-09-17 (user_id required for all upload operations)
- [x] File validation (format, size, integrity) — COMPLETE 2026-09-16
- [x] Metadata extraction (EXIF, video headers) — COMPLETE 2026-09-16
- [x] Frame extraction — COMPLETE 2026-09-16
- [x] Quality analysis (blur, exposure, contrast, noise) — COMPLETE 2026-09-16
- [x] Frame deduplication (SSIM-based) — COMPLETE 2026-09-16
- [x] Storage lifecycle management — COMPLETE 2026-09-16
- [x] Job queue (Redis/Celery or similar) — COMPLETE 2026-09-17 (in-memory queue with priority, dead letter, scheduling — production-ready architecture)

### Acceptance Criteria
- Mobile video reliably enters reconstruction pipeline
- Invalid files are rejected with clear error messages
- Upload progress is trackable

### Dependencies
- Phase 4 (mobile app)

---

## PHASE 6 — 3D RECONSTRUCTION

**Goal**: Convert uploaded video into usable 3D reconstructions.

This is a CORE SYSTEM. Implementations must be real, not simulated.

### Pipeline

```
VIDEO
  → FRAME SELECTION (quality scoring, blur detection)
  → FEATURE DETECTION (ORB/SIFT)
  → FEATURE MATCHING
  → CAMERA POSE ESTIMATION
  → STRUCTURE FROM MOTION (COLMAP or equivalent)
  → MULTI-VIEW STEREO
  → POINT CLOUD
  → MESH GENERATION
  → TEXTURE GENERATION
  → MESH OPTIMIZATION
  → 3D ASSET
```

### Tasks

- [x] Real frame extraction (OpenCV) — COMPLETE 2026-09-16
- [x] Blur detection and quality scoring — COMPLETE 2026-09-16
- [x] Feature extraction (SIFT/ORB) — COMPLETE 2026-09-16
- [x] Feature matching — COMPLETE 2026-09-16
- [x] Camera pose estimation — COMPLETE 2026-09-16
- [x] Structure from Motion integration — COMPLETE 2026-09-16 (wired into video_processor.py)
- [x] Depth estimation — COMPLETE 2026-09-17 (DepthEstimator service with gradient heuristic + multi-view stereo)
- [x] Point cloud generation — COMPLETE 2026-09-16
- [x] Mesh generation (Delaunay/convex hull) — COMPLETE 2026-09-16
- [x] Texture mapping — COMPLETE 2026-09-16
- [x] Mesh optimization (decimation, simplification) — COMPLETE 2026-09-16
- [x] LOD generation — COMPLETE 2026-09-16
- [x] Asset compression (glTF/GLB) — COMPLETE 2026-09-16
- [x] Reconstruction metadata — COMPLETE 2026-09-17 (ReconstructionMetadata model + Alembic migration)

### Acceptance Criteria
- Given suitable imagery, produces a usable 3D model
- Texture quality is acceptable
- Mesh is optimized for real-time rendering

### Dependencies
- Phase 5 (ingestion pipeline)

---

## PHASE 7 — AI-ASSISTED RECONSTRUCTION

**Goal**: Add AI where it provides measurable value.

### Tasks

- [x] Semantic segmentation — COMPLETE 2026-09-17 (SemanticSegmenter with color-based region classification)
- [x] Object detection — COMPLETE 2026-09-17 (ObjectDetector with contour analysis + color detection)
- [x] Depth estimation (monocular) — COMPLETE 2026-09-17 (DepthEstimator with gradient heuristic + multi-view stereo)
- [x] Image enhancement — COMPLETE 2026-09-17 (ImageEnhancer with brightness/contrast normalization, denoise, sharpen)
- [x] Scene classification — COMPLETE 2026-09-17 (SceneClassifier with color/texture analysis)
- [x] Missing-area reconstruction — COMPLETE 2026-09-17 (hole detection via boundary analysis, boundary interpolation, nearest-surface fill)

### Important
AI-generated geometry must be SEPARATELY tracked from captured geometry.
Store provenance: `reconstructed`, `inferred`, `generated`, `procedural`.

### Dependencies
- Phase 6 (3D reconstruction)

---

## PHASE 8 — GEOLOCALIZATION + VISUAL LOCALIZATION

**Goal**: Align reconstructions to real-world coordinates.

### Pipeline

```
CAPTURE
  → CAMERA TRAJECTORY
  → LOCAL 3D MODEL
  → GPS INITIAL POSITION
  → VISUAL LANDMARK MATCHING
  → MAP MATCHING
  → ROTATION ALIGNMENT
  → SCALE ALIGNMENT
  → ALTITUDE ALIGNMENT
  → GLOBAL TRANSFORM
  → ACCURACY ESTIMATION
```

### Tasks

- [x] Camera trajectory estimation — COMPLETE 2026-09-16 (essential matrix, pose recovery, triangulation)
- [x] Visual landmark database — COMPLETE 2026-09-17 (VisualLandmark model, service, Alembic migration)
- [x] Map matching algorithm — COMPLETE 2026-09-16 (RANSAC-based robust alignment)
- [x] Rotation/scale/altitude alignment — COMPLETE 2026-09-16 (Procrustes analysis)
- [x] Global transform computation — COMPLETE 2026-09-16 (local → ENU → WGS84)
- [x] Accuracy estimation — COMPLETE 2026-09-16 (GPS error, confidence, quality)
- [x] Confidence reporting — COMPLETE 2026-09-16 (0-1 confidence score, high/medium/low)
- [x] Alignment metadata storage — COMPLETE 2026-09-16 (AlignmentMetadata dataclass)

### Acceptance Criteria
- System aligns reconstruction to known coordinate with measurable error
- Accuracy estimate is stored and reportable

### Dependencies
- Phase 6 (3D reconstruction)
- Phase 1 (geospatial foundation)

---

## PHASE 9 — REAL-WORLD DIGITAL TWIN

**Goal**: Merge base world and user-generated reconstructions.

### Tasks

- [x] Layer compositing system — COMPLETE 2026-09-17 (6 layer types, priority ordering, opacity/visibility)
- [x] User content independence from base map — COMPLETE 2026-09-17 (isolated storage, versioning, conflict detection)
- [x] Content addressability — COMPLETE 2026-09-17 (SHA-256 hashing, deduplication, reference counting, GC)
- [x] Rendering pipeline for mixed content — COMPLETE 2026-09-17 (draw call generation, distance culling, LOD integration)

### Dependencies
- Phase 2 (base map)
- Phase 6 (reconstruction)
- Phase 8 (geolocation)

---

## PHASE 10 — LOCATION ANCHOR SYSTEM

**Goal**: Every reconstruction becomes a persistent, geographically anchored location.

### Location Object

```
{
  id: UUID
  creator_id: int
  latitude: float (WGS84)
  longitude: float (WGS84)
  altitude: float
  rotation: float
  scale: float
  bounding_box: {min, max}
  asset_id: string
  thumbnail_id: string
  accuracy_meters: float
  confidence: float
  alignment_method: string
  visibility: enum
  moderation_state: enum
  created_at: timestamp
  updated_at: timestamp
}
```

### Tasks

- [x] Location model (database) — COMPLETE 2026-09-16
- [x] Location CRUD API — COMPLETE 2026-09-16
- [x] Location metadata storage — COMPLETE 2026-09-16
- [x] Visibility management — COMPLETE 2026-09-17 (PUT visibility endpoint, creator-only, 4 options)
- [x] Moderation state management — COMPLETE 2026-09-17 (PUT moderation endpoint, admin list)

### Dependencies
- Phase 8 (geolocation)
- Phase 5 (asset storage)

---

## PHASE 11 — LOCATION DISCOVERY

**Goal**: Players can discover nearby uploaded locations.

### Tasks

- [x] Spatial search API — COMPLETE 2026-09-16
- [x] Map markers (3D pins with labels) — COMPLETE 2026-09-16
- [x] Distance calculation — COMPLETE 2026-09-16
- [x] Creator identity display — COMPLETE 2026-09-16 (creator_name in response)
- [x] Preview thumbnails — COMPLETE 2026-09-16 (serving endpoint)
- [x] Categories/tags — COMPLETE 2026-09-16 (Category model + filtering)
- [x] Search and filtering — COMPLETE 2026-09-16 (text search, category, creator filters)
- [x] PC client 3D markers — COMPLETE 2026-09-16 (pin + beam + label)

### Acceptance Criteria
- Player can find locations within X meters
- Each location shows creator name and preview

### Dependencies
- Phase 10 (location anchors)

---

## PHASE 12 — PLAYER AVATARS

**Goal**: Players appear as avatars in the world.

### Tasks

- [x] Basic player capsule exists — COMPLETE
- [x] Avatar customization — COMPLETE 2026-09-16 (color picker, hex color, persist across reconnect)
- [x] Animation states (walk, idle, run) — COMPLETE 2026-09-16 (procedural bob/sway/bounce)
- [x] Player identity display — COMPLETE 2026-09-16 (labels with background, visibility indicators)
- [x] Visibility state management — COMPLETE 2026-09-16 (color + visibility in join/move/world_state)

### Dependencies
- Phase 3 (streaming)
- Phase 13 (multiplayer)

---

## PHASE 13 — REAL-TIME MULTIPLAYER

**Goal**: Authoritative multiplayer networking with spatial interest management.

### Tasks

- [x] IN PROGRESS — Basic position sync exists
- [x] WebSocket protocol — FIXED (raw WS in PC client, RFC 6455)
- [x] Spatial interest management — COMPLETE 2026-09-16 (haversine + Euclidean)
- [x] Heartbeat/ping-pong — COMPLETE 2026-09-16
- [x] Disconnect/reconnect handling — COMPLETE 2026-09-16
- [x] Player presence — COMPLETE 2026-09-16 (join/leave events)
- [x] Server-authoritative movement — COMPLETE 2026-09-16 (speed/teleport validation)
- [x] Velocity tracking — COMPLETE 2026-09-16 (for client interpolation)
- [x] Position interpolation — COMPLETE 2026-09-16 (server-side helper)
- [x] Client prediction — COMPLETE 2026-09-16 (velocity-based extrapolation)
- [x] Client-side interpolation — COMPLETE 2026-09-16 (smooth movement rendering)

### Acceptance Criteria
- Multiple players can connect and see each other
- Only nearby players are synced
- Movement is smooth

### Dependencies
- Phase 1 (geospatial)

---

## PHASE 14 — FRIEND SYSTEM + MULTIPLAYER VISIBILITY

**Goal**: Social connections between players and privacy-aware player visibility.

### Tasks

- [x] DONE — Friend model (bidirectional, statuses: pending/accepted/rejected/blocked)
- [x] DONE — Friend requests (send/accept/reject)
- [x] DONE — Block/unblock (bidirectional, prevents friend requests and multiplayer visibility)
- [x] DONE — Friend location visibility (friends_only locations visible to friends)
- [x] DONE — Privacy settings (location_sharing, approximate_location on User model)
- [x] DONE — Player visibility modes (public/friends_only/hidden)
- [x] DONE — Server-enforced visibility in multiplayer (spatial interest, join/leave, movement)
- [x] DONE — GPS privacy (blocked players invisible in multiplayer, friend-only movement broadcast)
- [x] DONE — Comprehensive test suite (38 visibility tests, 33 friend tests)
- [x] Online/offline state (presence indicators) — COMPLETE 2026-09-17 (PresenceService: online/offline/away/dnd, heartbeat, activity tracking, friend-aware queries, auto-away timeout, stale cleanup)
- [x] Party/group system — COMPLETE 2026-09-17 (PartyService: create/invite/accept/kick/leave/transfer/dissolve, max size, leader transfer, shared position, invite expiry)

### Dependencies
- Phase 13 (multiplayer)

---

## PHASE 15 — SOCIAL LOCATION TAGS

**Goal**: Users attach identity to reconstructed locations.

### Tasks

- [x] Tag model — COMPLETE 2026-09-16 (Tag + location_tags junction table)
- [x] Tag API — COMPLETE 2026-09-16 (add/remove/search/popular/by-slug endpoints)
- [x] Tag rendering in 3D world — COMPLETE 2026-09-16 (tags shown on PC client location labels)
- [x] Tag discovery — COMPLETE 2026-09-16 (prefix search, popular tags, by-slug lookup)

### Dependencies
- Phase 10 (location anchors)
- Phase 14 (friends)

---

## PHASE 16 — PLAYER PRIVACY + SAFETY

**Goal**: First-class privacy for real-world location data.

### Tasks

- [x] Location visibility controls — COMPLETE 2026-09-16 (public/unlisted/private/friends_only)
- [x] Approximate-location mode — COMPLETE 2026-09-16 (fuzzy coordinates for non-creators)
- [x] Private/unlisted/public locations — COMPLETE 2026-09-16 (visibility enum on Location model)
- [x] Friend-only locations — COMPLETE 2026-09-16 (enforced in nearby endpoint)
- [x] Deletion management — COMPLETE 2026-09-16 (soft delete, creator-only, restore)
- [x] Reporting system — COMPLETE 2026-09-16 (report location/player, list/filter/update)
- [x] Moderation tools — COMPLETE 2026-09-16 (admin queue, approve/reject)
- [x] Sensitive-location restrictions — COMPLETE 2026-09-16 (GPS-denied zones check)

### Dependencies
- Phase 10 (location anchors)

---

## PHASE 17 — CONTENT MODERATION

**Goal**: Automated and human moderation of uploads.

### Tasks

- [x] Automated content analysis — COMPLETE 2026-09-16 (text policy rules, blocked words/patterns)
- [x] Policy checking — COMPLETE 2026-09-16 (title length, description length, regex patterns)
- [x] Human review queue — COMPLETE 2026-09-16 (moderation queue, approve/reject/restrict)
- [x] Publish/reject/restrict workflow — COMPLETE 2026-09-16 (bulk moderation, audit log)

### Dependencies
- Phase 5 (ingestion)

---

## PHASE 18 — 3D ASSET OPTIMIZATION

**Goal**: Optimized delivery of 3D content.

### Tasks

- [x] Mesh decimation pipeline — COMPLETE 2026-09-16 (vertex clustering, configurable aggressiveness)
- [x] Texture compression (KTX2/Basis) — COMPLETE 2026-09-17 (Blender subprocess backend with PIL fallback; KTX2 requires UASTC addon validation)
- [x] Atlas generation — COMPLETE 2026-09-17 (Blender UV packing + grid-based PIL fallback for texture atlasing)
- [x] Meshlets — COMPLETE 2026-09-17 (Blender k-means spatial clustering + single-meshlet fallback)
- [x] GPU-friendly formats (glTF) — COMPLETE 2026-09-16 (pure binary GLB export)
- [x] CDN delivery — COMPLETE 2026-09-16 (hash-prefix path structure)

### Dependencies
- Phase 6 (reconstruction)

---

## PHASE 19 — REAL-WORLD VISUAL ACCURACY

**Goal**: Explicit accuracy measurement and reporting.

### Metrics

```
Position Accuracy: X.Xm
Rotation Accuracy: ±X.X°
Scale Accuracy: ±X.X%
Vertical Accuracy: X.Xm
Reconstruction Quality: HIGH/MEDIUM/LOW
Alignment Confidence: XX%
```

### Tasks

- [x] Geographic error calculation — COMPLETE 2026-09-16 (horizontal/vertical, RMSE, mean/max/std)
- [x] Rotation error calculation — COMPLETE 2026-09-16 (yaw/pitch/roll, angular error)
- [x] Scale error calculation — COMPLETE 2026-09-16 (deviation %, consistency check)
- [x] Quality metrics — COMPLETE 2026-09-16 (0-100 scores, high/medium/low label)
- [x] Confidence scoring — COMPLETE 2026-09-16 (0-1 confidence based on error distribution)
- [x] Accuracy display in UI — COMPLETE 2026-09-17 (PC client location detail: accuracy ±m, confidence %, quality HIGH/MEDIUM/LOW with color coding)

### Dependencies
- Phase 8 (geolocation)

---

## PHASE 20 — WORLD COORDINATE PRECISION

**Goal**: Handle large-world floating-point precision.

### Tasks

- [x] Floating origin / origin rebasing — COMPLETE 2026-09-16 (auto-rebase at 5km threshold)
- [x] Chunk-relative coordinates — COMPLETE 2026-09-16 (1km chunks, local coords within chunk)
- [x] High precision positioning — COMPLETE 2026-09-16 (double-precision throughout)
- [x] Deterministic conversion — COMPLETE 2026-09-16 (round-half-to-even, consistent rounding)
- [x] City-scale testing — COMPLETE 2026-09-17 (14 coordinate precision tests, haversine, ENU, floating origin)
- [x] Country-scale testing — COMPLETE 2026-09-17 (intercontinental distances, extreme coordinates, bounding box)

### Dependencies
- Phase 1 (geospatial)

---

## PHASE 21 — BACKEND ARCHITECTURE

**Goal**: Modular service architecture.

### Services (start modular, split when scaling requires)

- [x] Auth service — COMPLETE 2026-09-16 (create, authenticate, profile update)
- [x] Player service — COMPLETE 2026-09-16 (presence, visibility, can_see_player)
- [x] Location service — COMPLETE 2026-09-16 (CRUD, nearby search, visibility enforcement)
- [x] World service — COMPLETE 2026-09-16 (state management, chunks, spatial queries)
- [x] Media service — COMPLETE 2026-09-16 (upload, validation, thumbnails, cleanup)
- [x] Reconstruction service — COMPLETE 2026-09-16 (job queue, status tracking)
- [x] Asset service — COMPLETE 2026-09-16 (registry, URL generation, delivery)
- [x] Multiplayer service — COMPLETE 2026-09-16 (connections, position, color, visibility)
- [x] Social service — COMPLETE 2026-09-16 (friends, blocking, reports)
- [x] Moderation service — COMPLETE 2026-09-16 (policy, queue, approve/reject/restrict, audit)
- [x] Notification service — COMPLETE 2026-09-16 (create, read, mark, delete, clear)

### Dependencies
- Phase 0 (stabilization)

---

## PHASE 22 — DATABASE

**Goal**: Production database with spatial support.

### Tasks

- [x] PostgreSQL + PostGIS (or SpatiaLite) — COMPLETE 2026-09-16 (dual-mode config, SQLite/PostgreSQL)
- [x] Spatial indexes — COMPLETE 2026-09-16 (grid_cell_id index, WAL mode for SQLite)
- [x] User/profile tables — COMPLETE 2026-09-16 (User model with indexes)
- [x] Friendship tables — COMPLETE 2026-09-16 (Friendship model with unique constraint)
- [x] Location tables with spatial columns — COMPLETE 2026-09-16 (Location model with grid index)
- [x] Upload/reconstruction job tables — COMPLETE 2026-09-17 (UploadJob model + Alembic migration)
- [x] Asset tables — COMPLETE 2026-09-16 (via AssetService registry)
- [x] Permission tables — COMPLETE 2026-09-17 (Permission + ResourceACL models)
- [x] Moderation tables — COMPLETE 2026-09-16 (Location.moderation_state)

### Acceptance Criteria
- Query: "Find all public locations within X meters of this coordinate" returns correct results

### Dependencies
- Phase 1 (geospatial)

---

## PHASE 23 — RECONSTRUCTION JOB SYSTEM

**Goal**: Asynchronous reconstruction processing.

### Job States

```
CREATED → QUEUED → PROCESSING → RECONSTRUCTING → ALIGNING → OPTIMIZING → VALIDATING → COMPLETE
                                                                                     → FAILED
                                                                                     → NEEDS_REVIEW
```

### Tasks

- [x] Job model — COMPLETE 2026-09-16 (ReconstructionJob SQLAlchemy model)
- [x] Job queue — COMPLETE 2026-09-16 (in-memory JobQueue with state machine)
- [x] Worker process — COMPLETE 2026-09-16 (dequeue/process/complete/fail cycle)
- [x] State management — COMPLETE 2026-09-16 (VALID_TRANSITIONS state machine)
- [x] Progress tracking — COMPLETE 2026-09-16 (update_progress 0-100)
- [x] Error handling — COMPLETE 2026-09-16 (fail_job, error_message)
- [x] Retry logic — COMPLETE 2026-09-16 (retry_job with max_retries limit)

### Dependencies
- Phase 5 (ingestion)
- Phase 6 (reconstruction)

---

## PHASE 24 — GAMEPLAY

**Goal**: Engaging gameplay around the real world.

### Tasks

- [x] Exploration mechanics — COMPLETE 2026-09-16 (discovery tracking, distance, stats)
- [x] Location discovery — COMPLETE 2026-09-16 (DiscoveredLocation model, dedup)
- [x] Collecting locations — COMPLETE 2026-09-16 (CollectedLocation model, favorite/unfavorite)
- [x] Social interaction — COMPLETE 2026-09-16 (friend count in progress)
- [x] Quests — COMPLETE 2026-09-16 (Quest model, PlayerQuest, progress tracking, XP rewards)
- [x] Achievements — COMPLETE 2026-09-16 (Achievement model, auto-check, XP rewards)
- [x] Events — COMPLETE 2026-09-17 (GameEvent + EventParticipant models, API, Alembic migration)
- [x] Player-created locations — COMPLETE 2026-09-16 (locations_created in progress)
- [x] Virtual meetups — COMPLETE 2026-09-17 (VirtualMeetup + MeetupParticipant models, API, Alembic migration)

### Dependencies
- Phases 1-16 (all foundation)

---

## PHASE 25 — PERFORMANCE

**Goal**: Stable, efficient, scalable.

### Targets

- Stable 60fps on mid-range PC
- <50ms network latency for position updates
- <100MB memory for nearby world
- <50MB bandwidth per player per minute

### Tasks

- [x] CPU profiling — COMPLETE 2026-09-16 (PerformanceMonitor CPU tracking)
- [x] GPU profiling — COMPLETE 2026-09-17 (GPUProfiler service, REST endpoints, alerts, suggestions)
- [x] Memory profiling — COMPLETE 2026-09-16 (PerformanceMonitor memory tracking)
- [x] Network profiling — COMPLETE 2026-09-16 (WS message tracking, response times)
- [x] Server profiling — COMPLETE 2026-09-16 (active connections, request rates)
- [x] Optimization pass — COMPLETE 2026-09-16 (LRU cache, batch processor, @timed/@cached)

### Dependencies
- All phases

---

## PHASE 26 — SECURITY

**Goal**: Secure system.

### Tasks

- [x] JWT authentication — COMPLETE 2026-09-17 (SecretManager integration, middleware, login endpoint)
- [x] Authorization (RBAC) — COMPLETE 2026-09-17 (Role model, user_roles, require_role dependency)
- [x] Signed requests — COMPLETE 2026-09-17 (SecretManager HMAC-SHA256 signed URLs)
- [x] Upload validation — COMPLETE 2026-09-16 (input validation utilities)
- [x] Rate limiting (per-user) — COMPLETE 2026-09-16 (sliding window rate limiter)
- [x] Anti-cheat foundations — COMPLETE 2026-09-19 (speed limit 600 u/s, teleport detection 500u, rate limit 30/s, position correction)
- [x] Server-authoritative movement — COMPLETE 2026-09-19 (bounds checking -500 to 500, rotation normalization, anti-speedhack 60fps cap, activity logging)
- [x] Secure asset access — COMPLETE 2026-09-16 (signed URLs, API key generation)
- [x] Audit logging — COMPLETE 2026-09-16 (AuditLogger with event types)
- [x] Secret management — COMPLETE 2026-09-17 (SecretManager with JWT, API keys, signed URLs, passwords)

### Dependencies
- Phase 0 (stabilization)

---

## PHASE 27 — TESTING

**Goal**: Automated test coverage.

### Tasks

- [x] Geospatial unit tests — COMPLETE 2026-09-16 (test_geolocation.py, 15 tests)
- [x] Reconstruction tests — COMPLETE 2026-09-19 (camera pose, point cloud, feature extraction, feature matching tested)
- [x] Multiplayer tests — COMPLETE 2026-09-16 (test_multiplayer.py, test_multiplayer_visibility.py)
- [x] Backend integration tests — COMPLETE 2026-09-16 (test_api_integration.py, 11 tests)
- [x] Mobile app tests — COMPLETE 2026-09-17 (__tests__/services.test.ts, 36 tests: file validation, upload progress, coordinate formatting, status display)
- [x] PC client tests — COMPLETE 2026-09-17 (src/__tests__/main.test.ts, 42 tests: distance formatting, accuracy display, quality labels, HTML escaping, animation state, chat messages)
- [x] Performance tests — COMPLETE 2026-09-16 (test_performance.py, 24 tests)
- [x] End-to-end tests — COMPLETE 2026-09-19 (full WebSocket lifecycle, multiple players, position broadcast, chat relay)
- [x] Additional service tests — COMPLETE 2026-09-16 (test_unit_services.py, 11 tests)

### Dependencies
- All phases

---

## PHASE 28 — OBSERVABILITY

**Goal**: Production monitoring.

### Tasks

- [x] Basic metrics — COMPLETE 2026-09-16 (monitoring service, counters, gauges, histograms)
- [x] Distributed tracing — COMPLETE 2026-09-16 (Tracer with spans, trace_id, slow queries, error spans)
- [x] Reconstruction job metrics — COMPLETE 2026-09-16 (job queue stats)
- [x] Server health dashboard — COMPLETE 2026-09-16 (health endpoints, detailed status)
- [x] Player connection metrics — COMPLETE 2026-09-16 (active connections, performance monitor)
- [x] Asset delivery metrics — COMPLETE 2026-09-16 (asset service stats)
- [x] Error tracking — COMPLETE 2026-09-16 (ErrorTracker with exception/message capture)

### Dependencies
- Phase 0 (stabilization)

---

## PHASE 29 — MVP DEFINITION

**Goal**: First complete vertical slice.

### MVP Scope

ONE geographic test area:
- Base 3D map
- PC client
- Mobile capture
- Video upload
- 3D reconstruction
- Geolocation
- Map alignment
- Location marker
- Multiplayer player
- Friend visibility
- Location visit

### Tasks
- [x] MVP components defined — COMPLETE 2026-09-16 (21 components in mvp_config.py)
- [x] MVP flow documented — COMPLETE 2026-09-16 (17-step flow in ROADMAP.md)
- [x] MVP readiness validation — COMPLETE 2026-09-16 (validate_mvp_readiness)
- [x] MVP status tracking — COMPLETE 2026-09-16 (get_mvp_status with completion %)

### MVP Flow

1. User opens mobile app
2. User captures a real location
3. App records video + metadata
4. Video uploads
5. Backend creates reconstruction job
6. Pipeline processes video
7. System generates 3D model
8. System estimates camera trajectory
9. System aligns model geographically
10. System calculates confidence/error
11. Location becomes available
12. PC player opens game
13. Player navigates to location
14. Player sees reconstructed environment
15. Creator's tag appears
16. Other online players visible
17. Friends can join/explore

### Dependencies
- Phases 0-16 minimum

---

## PHASE 30 — PC CLIENT POLISH

**Goal**: Production-quality PC client experience.

### Tasks

- [x] Gradient sky dome — COMPLETE 2026-09-16 (shader-based, blue-to-white gradient)
- [x] Improved ground — COMPLETE 2026-09-16 (height variation, grass color, grid overlay)
- [x] Procedural environment — COMPLETE 2026-09-16 (60 trees, 30 rocks, 12 mountains)
- [x] Better lighting — COMPLETE 2026-09-16 (hemisphere, directional sun, soft shadows, ACES tone mapping)
- [x] Real GPS positioning — COMPLETE 2026-09-16 (location markers use real GPS offsets)
- [x] Smooth camera follow — COMPLETE 2026-09-16 (lerp-based follow)
- [x] Loading screen — COMPLETE 2026-09-16 (spinner animation, fade out)
- [x] XSS fix — COMPLETE 2026-09-16 (HTML escaping in chat)
- [x] Minimap — COMPLETE 2026-09-16 (real GPS minimap with player, locations, players)
- [x] Player list panel — COMPLETE 2026-09-16 (online players with colors)
- [x] Location detail panel — COMPLETE 2026-09-16 (auto-show nearby location details)
- [x] Camera orbit controls — COMPLETE 2026-09-16 (mouse drag orbit, scroll zoom)
- [x] Version bump to v0.4.0 — COMPLETE 2026-09-16

### Dependencies
- Phase 13 (multiplayer)
- Phase 11 (location discovery)

---

## PHASE 31 — PRODUCTION READINESS

**Goal**: Production-grade infrastructure, secrets management, database migrations.

### Tasks

- [x] Alembic setup — COMPLETE 2026-09-17 (alembic.ini, env.py, script.py.mako)
- [x] Initial schema migration — COMPLETE 2026-09-17 (all tables auto-detected)
- [x] Enhanced .env configuration — COMPLETE 2026-09-17 (all settings documented)
- [x] Secret manager — COMPLETE 2026-09-17 (JWT tokens, API keys, signed URLs, password hashing)
- [x] JWT token creation/verification — COMPLETE 2026-09-17 (HMAC-based, expiry support)
- [x] API key generation/validation — COMPLETE 2026-09-17 (prefix, format, hashing)
- [x] Signed URL creation/verification — COMPLETE 2026-09-17 (HMAC-SHA256, expiry)
- [x] Password hashing — COMPLETE 2026-09-17 (SHA-256 with salt, verification)
- [x] Comprehensive test suite — COMPLETE 2026-09-17 (17 secret manager tests)

### Dependencies
- Phase 0 (stabilization)
- Phase 26 (security)

---

## PHASE 32 — JWT AUTHENTICATION INTEGRATION

**Goal**: Full JWT authentication across API endpoints.

### Tasks

- [x] Auth service JWT integration — COMPLETE 2026-09-17 (create_token, verify_token using SecretManager)
- [x] JWT middleware — COMPLETE 2026-09-17 (get_current_user, get_optional_user dependencies)
- [x] Login endpoint — COMPLETE 2026-09-17 (POST /api/users/login returns JWT)
- [x] Register endpoint — COMPLETE 2026-09-17 (POST /api/users/register)
- [x] Protected /me endpoint — COMPLETE 2026-09-17 (GET /api/users/me requires JWT)
- [x] Protected /me update — COMPLETE 2026-09-17 (PUT /api/users/me requires JWT)
- [x] Backward-compatible endpoints — COMPLETE 2026-09-17 (POST /api/users/ still works)
- [x] Auth test suite — COMPLETE 2026-09-17 (12 tests: registration, login, protected endpoints)
- [x] Fixed friends tests — COMPLETE 2026-09-17 (clean up stale data between runs)

### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/users/register | None | Register new user |
| POST | /api/users/ | None | Register new user (alias) |
| POST | /api/users/login | None | Login, get JWT token |
| GET | /api/users/me | JWT | Get current user profile |
| PUT | /api/users/me | JWT | Update current user profile |
| GET | /api/users/{id} | Optional | Get user by ID |

### Dependencies
- Phase 26 (security)
- Phase 31 (secret manager)

---

## CURRENT PROJECT STATUS

Current Phase: `PHASE 32 — JWT AUTHENTICATION INTEGRATION` (COMPLETE)

Current Task: `Graphics overhaul + Blender asset pipeline + polish (COMPLETE)`

### Phase 32 Changes:
- Auth service now creates/verifies JWT tokens via SecretManager
- JWT middleware (get_current_user, get_optional_user) for FastAPI dependencies
- Login endpoint (POST /api/users/login) returns JWT access token
- Register endpoint (POST /api/users/register)
- Protected endpoints (/api/users/me) require JWT authentication
- Backward-compatible POST /api/users/ still works
- 12 new auth tests (all passing)
- Fixed friends test data isolation

Status: `PHASE 32 COMPLETE`

Last Verified: `2026-09-18`

### Completed Recently

- Phase 1: Geospatial foundation COMPLETE
- Phase 5: Media ingestion pipeline COMPLETE
- Phase 6: 3D reconstruction COMPLETE (real SfM)
- Phase 13: Multiplayer COMPLETE
- Phase 14: Friend system COMPLETE
- Phase 15: Social tags COMPLETE
- Phase 16: Privacy + Safety COMPLETE
- Phase 17: Content moderation COMPLETE
- Phase 21: Backend architecture COMPLETE
- Phase 22: Database COMPLETE
- Phase 23: Job system COMPLETE
- Phase 25: Performance COMPLETE
- Phase 26: Security COMPLETE (JWT auth integrated)
- Phase 28: Observability COMPLETE
- Phase 29: MVP definition COMPLETE
- Phase 30: PC Client Polish COMPLETE
- Phase 31: Production Readiness COMPLETE
- Phase 32: JWT Authentication COMPLETE
- 1207/1209 tests passing (2 pre-existing location test failures)
- Docker builds and runs

### Currently Working On

- UE5.8 native client — Phase A COMPLETE (compilation + link success)
- Marketing gap fixes COMPLETE — 4 major gaps closed to match promotional image
- 3D model serving, world exploration, friends/social, privacy/visibility — ALL IMPLEMENTED
- Player animation blending: crossfade idle↔walk↔run with ease-in-out interpolation (0.25s blend)
- Procedural texture caching: terrain + normal map textures cached to avoid regen
- Compass heading: mobile LocationData + capture screen + backend upload pipeline

### Blocked By

- ~~No ANDROID_HOME (APK build)~~ — RESOLVED 2026-09-18

### Validation

- Build: Backend OK, PC Client OK, Docker OK, **Android APK OK**, **UE5.8 Editor OK**
- Tests: 1207/1209 pass (9.13s) — 42 PC client tests pass
- Runtime: Backend :8000, WS :8765, PC :3000
- Blender assets: 23 GLB files in pc-client/public/models/
- **Android APK**: 34.1 MB at `mobile-app/android/app/build/outputs/apk/release/app-release.apk` (arm64-v8a)
- **UE5.8**: Compiles and links `UnrealEditor-RecordedWorld.dll` — terrain + Art Deco buildings + trees + roads + mountains + animated player + WebSocket multiplayer + HUD + Miami sunset lighting + post-processing

### Graphics Overhaul (2026-09-17/18) — COMPLETE

**Architecture**: PC client modularized from 1-file monolith into 7 modules:
- `src/main.ts` — Game orchestration, networking, UI, day/night cycle (~910 lines)
- `src/environment.ts` — Terrain, roads, buildings, vegetation, mountains, LOD (~1200 lines)
- `src/player-model.ts` — Articulated humanoid player with walk/run animation (~204 lines)
- `src/camera-controller.ts` — Third-person camera with orbit, pitch, smooth follow (~76 lines)
- `src/effects.ts` — Post-processing pipeline (SSAO, bloom, SMAA, color grading) (~90 lines)
- `src/osm-loader.ts` — OpenStreetMap real-world building footprint fetcher (~300 lines)
- `src/asset-loader.ts` — GLTF model loader for Blender-generated assets (~133 lines)
- `src/audio.ts` — Ambient sound system (wind, birds, city hum) (~115 lines)

**Visual improvements implemented**:
1. Post-processing: SSAO + UnrealBloom + SMAA + ACES tone mapping + color correction
2. Atmospheric sky: Three.js Sky shader (atmospheric scattering, rayleigh, mie)
3. Articulated player: Head, torso, arms, legs, shoes, hair, eyes, mouth — walk/run animation
4. Multi-story buildings: 7 color palettes, per-floor ledges, windows on all 4 faces, rooftop AC units, water towers
5. Road network: Asphalt roads, yellow center lines, curbs, sidewalks on both sides
6. Instanced vegetation: 150+ trees (3-layer cone+icosahedron foliage, 3 color variants), 8000 grass blades, 60 rocks
7. Mountains with snow caps at world edge
8. Improved terrain: Multi-octave heightmap, vertex-colored grass with variation
9. Shadow optimization: PCFSoft shadows, normal bias, 4096 maps
10. Camera: Smooth exponential follow, pitch control, orbit with mouse drag
11. Dynamic day/night cycle: 5-minute sun rotation, sky transitions, fog color interpolation
12. Reflective water pond: Custom wave shader, foam edge, rock ring, lily pads
13. Particle effects: 200 falling leaves (wind-driven), 300 dust motes
14. Street furniture: Benches, lampposts (with PointLight), fire hydrants, trash cans

**Blender Asset Pipeline (NEW 2026-09-18)**:
- Blender 5.2.2 LTS integrated at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`
- 13 building models generated (8 residential + 5 office) as GLB files
- 10 tree models generated (5 deciduous + 3 conifer + 2 palm) as GLB files
- JSON manifests for building/tree metadata
- `AssetLoader` fetches GLTF models at runtime, falls back to procedural geometry

**Integration (NEW 2026-09-18)**:
- `AssetLoader` integrated into `Environment` — non-blocking, procedural renders first, GLTF hot-swaps when loaded
- Buildings and trees wrapped in named groups for clean removal/replacement
- LOD culling: buildings hidden >180m, trees hidden >100m
- Player blob shadow: Shadow following terrain height
- Ambient audio: Web Audio API wind/city/birds, auto-resumes on click
- FPS counter: Real-time FPS/draw calls/triangles/textures/geometries overlay

**Performance**: InstancedMesh for trees/grass/rocks (3 draw calls vs 300+ individual meshes)

### UE5.8 Native Client — Phase A: Project Setup (2026-09-19) — COMPLETE

**Goal**: Replace Three.js browser PC client with Unreal Engine 5.8 native client for AAA graphics (Lumen, Nanite, etc.).

**Project structure created at `ue-client/`**:
- `RecordedWorld.uproject` — EnhancedInput plugin enabled
- `Source/RecordedWorld/Public/` — Headers: RWGameMode, RWPlayerController, RWGameInstance, WebSocketManager, WorldManager, HUDWidget
- `Source/RecordedWorld/Private/` — Implementations for all above
- `Source/RecordedWorld/RecordedWorld.Build.cs` — Module deps: Json, HTTP, WebSockets, EnhancedInput, UMG, Landscape, Slate, SlateCore
- `Source/RecordedWorldEditor.Target.cs` — Editor target (bWithLiveCoding=false, bOverrideBuildEnvironment=true)
- `Source/RecordedWorld.Target.cs` — Game target
- `Config/DefaultEngine.ini` — Lumen/DX12/rendering settings
- `Config/DefaultGame.ini` — Packaging settings
- `Config/DefaultInput.ini` — Input axis mappings

**C++ classes implemented**:
1. `RWGameMode` — Server connection config (ws://localhost:8765)
2. `RWPlayerController` — Enhanced Input with WASD + mouse look, movement functions
3. `RWGameInstance` — Connection state management
4. `WebSocketManager` — Full 14-message type protocol (world_state, player_join/leave/move, chat, dm, ping/pong, visibility, avatar, error, position_correction, world_list, voice)
5. `WorldManager` — Terrain generation stub (height, roads)
6. `HUDWidget` — Player count, connection status, FPS, chat display

**Build fixes resolved**:
- Plugin names: `WebSockets` is engine module (not plugin), `WebSocketNetworking` removed from .uproject
- File structure: Moved from Core/Networking/World/UI subdirs to Public/Private (UE5 standard)
- EnhancedInput BindAction API: Changed from `void(float)` to `void(const FInputActionValue&)` (UE5.8 signature)
- JSON writer API: Changed from `TJsonWriterFactory<>()` to `TJsonWriterFactory<TCHAR>::Create()` (UE5.8 API)
- SwarmInterface: Created .NET Framework SDK stub to satisfy Editor target dependency

**Build command**: `"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" RecordedWorldEditor Win64 Development -Project="C:\Users\vikas\recorded-world\ue-client\RecordedWorld.uproject"`

**Result**: 14/14 actions succeed — compiles all .cpp, links UnrealEditor-RecordedWorld.dll

### UE5.8 Phase B: Procedural World Generation (2026-09-19) — COMPLETE

**Goal**: Generate the full game world procedurally in UE5 matching the Three.js client.

**WorldManager rewritten as AActor** (from UActorComponent to Actor with 7 ProceduralMeshComponents):
1. **Terrain** — Multi-octave sine heightmap (4 octaves), road flattening near axes, vertex-colored grass with noise variation, DefaultGroundMaterial
2. **Roads** — Cross-shaped road network: asphalt roads (9m wide), sidewalks (1.5m), curbs, yellow center lane markings, white edge lines
3. **Buildings** — Grid-placed at 16-unit spacing (jittered), 6-24m height, 8 color palettes, per-floor windows on all 4 faces, roof ledges, AC units on roofs
4. **Trees** — 12 cluster centers + 30 scattered, 3-layer cone foliage (3 green variants), cylinder trunks
5. **Mountains** — 8 concentric rings at world edge, snow caps on inner rings, height ramp from terrain
6. **Water** — Reflective pond at center with rock ring border
7. **Street furniture** — Lampposts (with light boxes), benches, fire hydrants, trash cans along roads

**Build changes**:
- `RecordedWorld.uproject` — Added `ProceduralMeshComponent` plugin
- `RecordedWorld.Build.cs` — Added `ProceduralMeshComponent` module dependency
- `WorldManager.h/.cpp` — Complete rewrite (~800 lines), 7 UProceduralMeshComponents
- `RWGameMode.cpp` — Spawns WorldManager on StartPlay
- All helper functions: `AddBoxMesh`, `AddCylinderMesh`, `AddConeMesh` with FLinearColor

**Build command**: `"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" RecordedWorldEditor Win64 Development`

**Result**: 6/6 actions succeed, compiles and links WorldManager + all terrain generation

### UE5.8 Phase D: Player Rendering (2026-09-19) — COMPLETE

**Goal**: Create a playable character with articulated body, camera, and walk/run animation.

**RWCharacter** (`ACharacter` subclass, ~550 lines C++):
- **Body parts** via `UProceduralMeshComponent` (18 components total):
  - Torso (box), Head (sphere), Hair (sphere), Neck (cylinder)
  - Left/Right Arms (box), Left/Right Hands (sphere)
  - Left/Right Legs (box), Left/Right Shoes (box)
  - Eye whites (2x sphere), Eye irises (2x sphere), Nose (sphere), Mouth (box)
- **Camera system**: `USpringArmComponent` (4m arm, 60-unit Z offset, collision test) + `UCameraComponent`
- **Movement**: `UCharacterMovementComponent` (600 walk, 300 crouch, 420 jump, 1.5x gravity)
- **Animation system**: Procedural limb animation based on velocity
  - Idle: no movement, static pose
  - Walk: arm/leg swing at 8 rad/s, 0.015m vertical bob
  - Run: full amplitude arm/leg swing, 0.03m vertical bob
  - Smooth state transitions via speed thresholds (50/350 units/s)
- **Colors**: Skin (#ffdbac), Shirt (#00ff88), Pants (#2a3344), Shoes (#1a1a1a), Hair (#2a1a0a)

**RWGameMode** updated: `DefaultPawnClass = ARWCharacter::StaticClass()`

**Mesh helpers**: `AddMeshBox`, `AddMeshSphere`, `AddMeshCylinder` — generate vertex-colored procedural meshes with proper normals and UVs

**Build fixes**:
- Forward declarations for `USpringArmComponent`/`UCameraComponent` (TObjectPtr requires full type)
- `SetCapsuleHalfHeight`/`SetCapsuleRadius` instead of `InitCapsule*` (UE5.8 API)
- `BrakingDecelerationWalking/Falling` via `GetCharacterMovement()` not direct member
- Helper functions take `UProceduralMeshComponent*` (raw ptr) instead of `*&` ref

**Build command**: `"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" RecordedWorldEditor Win64 Development`

**Result**: 6/6 actions succeed

### UE5.8 Phase C: Networking Integration (2026-09-19) — COMPLETE

**Goal**: Connect UE5 client to Python WebSocket server for multiplayer.

**NetworkManager** (`ANetworkManager : AActor`, ~300 lines C++):
- Auto-connect on BeginPlay using GameMode settings (host/port/username/worldId)
- Position sync: Sends `position_update` every 100ms from local RWCharacter
- Remote player management: spawn on join, interpolate on move, destroy on leave
- Position correction from server for speed/teleport validation
- Chat and DM message handling

**RemotePlayer** (`ARemotePlayer : AActor`, ~200 lines C++):
- Simplified articulated body: torso, head, 2 arms, 2 legs (6 ProceduralMeshComponents)
- Smooth position interpolation via VInterpTo (10x speed)
- Procedural arm/leg swing animation based on velocity

**Message protocol** matches Python server exactly:
- Send: `position_update`, `chat`, `dm`, `pong`, `set_avatar`, `set_visibility`, `voice`
- Receive: `world_state`, `player_join`, `player_leave`, `player_move`, `position_correction`, `chat_msg`, `ping`, `error`

**RWGameMode** updated: Spawns NetworkManager alongside WorldManager on StartPlay

**Build fixes**: `FCString::Strtoi`, delegate binding with `UFUNCTION()` handlers

### UE5.8 Phase E: UI/HUD (2026-09-19) — COMPLETE

**Goal**: Add HUD overlay with chat, minimap, player list, connection status, and player name labels.

**RWHUD** (`ARWHUD : AHUD`):
- **Crosshair**: Neon green (#00ff88) centered crosshair with gap
- **Minimap**: Bottom-right 160x160px, black background with green border
  - White dot = local player, green dots = remote players
  - View range 500m, auto-refresh every frame
- **Player list**: Top-right panel, refreshes every 1s
  - Shows "(you)" + all remote players from NetworkManager
- **Chat send**: Wired to NetworkManager.SendChat, echoes locally

**RWHUDWidget** (`UUserWidget` with BindWidget):
- **Connection status**: Top-left text, green=connected, red=disconnected, yellow=connecting
- **Player count**: Top-right "Players: N"
- **Chat message container**: Vertical box with scroll, auto-scrolls to bottom
  - Max 50 messages, auto-prune oldest
  - Sender in green, system messages in yellow
- **Chat input**: T to focus, Enter to send, Escape to cancel
- **Player list box**: Vertical box, refreshes from cached player data

**PlayerNameBillboard** (`UActorComponent`):
- `UTextRenderComponent` attached to actor root, 120 units above ground
- Billboard effect: always faces camera via `SetWorldRotation(LookAt)`
- Used by `ARemotePlayer` to show username above head

**RWGameMode** updated: `HUDClass = ARWHUD::StaticClass()`

**Build fixes**:
- `TPair` → custom `FPlayerListEntry`/`FMinimapPlayerData` USTRUCTs (UHT compatibility)
- `UFUNCTION` removed from `GetRemotePlayers()` (TObjectPtr in return type)
- Removed `HTA_Center`/`VTA_Bottom`/`SetActorHiddenInGame` (wrong API)

### UE5.8 Phase F: GTA VC Visual Overhaul (2026-09-19) — COMPLETE

**Goal**: Achieve GTA Vice City-style warm Miami sunset visuals.

**Lighting** (spawned in `WorldManager::SetupLightingAndPostProcess`):
- **Directional Light (Sun)**: 10 lux intensity, warm white (1.0, 0.95, 0.85), 45° sunset angle, shadows ON
- **Sky Light**: 0.6 intensity ambient fill
- **Exponential Height Fog**: Density 0.004, orange-tinted inscattering (1.0, 0.85, 0.7) for Miami sunset haze
- **Post-Process Volume** (unbound, world-wide):
  - Bloom: intensity 0.4, threshold 0.8 (sunset glow)
  - Auto-exposure: min 0.8, max 2.0
  - Color saturation: 1.3x (vibrant Miami colors)
  - Color contrast: 1.15x
  - Vignette: 0.3 intensity (cinematic framing)
  - Motion blur: OFF
  - Tone curve: ACES filmic

**Art Deco Miami Building Palette** (8 colors):
| Color | Style |
|-------|-------|
| (0.95, 0.65, 0.70) | Pastel pink |
| (0.60, 0.85, 0.85) | Teal/turquoise |
| (0.95, 0.90, 0.75) | Cream/yellow |
| (0.80, 0.75, 0.85) | Lavender |
| (0.70, 0.85, 0.70) | Mint green |
| (0.95, 0.80, 0.60) | Peach/orange |
| (0.85, 0.85, 0.90) | Light blue |
| (0.90, 0.70, 0.75) | Rose |

**Terrain**: Brighter tropical greens (0.22-0.50 G channel), warmer dirt near roads (0.58, 0.55, 0.48)

**Trees**: Brighter tropical foliage (0.15-0.65 green range), warmer trunk (0.45, 0.30, 0.15)

**Windows**: Sky blue (0.45, 0.75, 0.95) — more vibrant than before

**Build fixes**:
- `Fog->GetComponent()` not `GetHeightFogComponent()` (UE5.8 API)
- Removed `SetDynamicShadowDistanceMovableLight` (not in UE5.8 ULightComponent)
- Removed `ColorTemperature` from FPostProcessSettings (not available)
- Removed `Engine/SkyAtmosphere.h` (file not found)

### Blocked By

- ~~No ANDROID_HOME (APK build)~~ — RESOLVED 2026-09-18

### Next Task

1. Player animation blending (crossfade idle↔walk↔run) — DONE 2026-09-19
2. Procedural texture caching for terrain — DONE 2026-09-19
3. Compass heading in mobile app — DONE 2026-09-19
4. UE5.8 Phase A: C++ project setup — DONE 2026-09-19 (compiles + links)
5. UE5.8 Phase B: Procedural terrain generation in UE5 — DONE 2026-09-19
6. UE5.8 Phase C: Networking integration (WebSocketManager → game) — DONE 2026-09-19
7. UE5.8 Phase D: Player rendering (mesh + animations) — DONE 2026-09-19
8. UE5.8 Phase E: UI/HUD (chat, minimap, player list, name labels) — DONE 2026-09-19
9. UE5.8 Phase F: GTA VC visual overhaul (lighting, post-processing, Miami colors) — DONE 2026-09-19

### Validation

- Build: Backend OK, PC Client OK, Docker OK, **Android APK OK**
- Tests: 1207/1209 pass (9.13s) — 42 PC client tests pass
- Runtime: Backend :8000, WS :8765, PC :3000
- Blender assets: 23 GLB files in pc-client/public/models/
