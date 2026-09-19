# Changelog

All notable changes to Recorded World will be documented in this file.

## [1.0.0] - 2026-09-19

### Added
- **UE5.8 Native Client**: Full C++ Unreal Engine 5.8 client with procedural world generation
  - Terrain heightmap (128x128, 4-octave sine)
  - Cross-shaped road network with sidewalks, curbs, lane markings
  - ~100 Art Deco buildings with windows, roofs, AC units
  - 12 tree clusters with 3-layer cone foliage
  - 8-ring mountain system with snow caps
  - Water feature with rock border
  - Street furniture (lampposts, benches, hydrants, trash cans)
- **GTA Vice City Visuals**: Warm Miami sunset lighting, post-process bloom/saturation/vignette
- **Player System**: 18-body-part articulated character with WASD movement, SpringArm camera, walk/run animation
- **Networking**: WebSocket connection to multiplayer server, remote player rendering with name billboards
- **UI/HUD**: Chat, minimap, player list, connection status

### Backend (1207 tests passing)
- JWT authentication with login/register endpoints
- User, Capture, Location, GameWorld models
- Spatial proximity search with grid-based index
- Video processing pipeline (OpenCV): frame extraction, blur/exposure analysis, SSIM deduplication
- 3D reconstruction: feature extraction (SIFT/ORB/AKAZE), camera pose estimation, point cloud, mesh generation
- WebSocket server: player join/leave, position relay, chat, spatial interest management
- Friend system with bidirectional relationships, blocking, visibility controls
- Content moderation: policy rules, review queue, approve/reject workflow
- Performance monitoring, rate limiting, input validation, audit logging
- Alembic database migrations, dual PostgreSQL/SQLite support

### PC Client (42 tests passing)
- Three.js scene with procedural terrain, roads, buildings, trees, mountains
- Articulated humanoid player with walk/run animation
- WASD keyboard controls, third-person camera with orbit
- Post-processing: SSAO, UnrealBloom, SMAA, color correction
- Atmospheric sky shader with day/night cycle
- OSM real-world building footprints (Overpass API)
- 23 Blender GLB models with runtime hot-swap
- Chat UI, player count, location markers, minimap

### Mobile App (36 tests passing)
- Expo Router navigation (4 tabs)
- Camera view with video recording
- GPS location tracking
- Upload with XHR progress, offline queue, auto-retry
- Capture gallery with status polling

### Infrastructure
- Docker Compose (3 services: backend, websocket, pc-client)
- GitHub Actions CI/CD
- Auto-build scripts (PowerShell, Bash)
