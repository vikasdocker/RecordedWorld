# Recorded World

A cross-platform 3D social game where mobile users capture real-world video, processed via AI into 3D environments explored in real-time by PC and UE5 players.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Backend](https://img.shields.io/badge/Backend-Python%203.12-blue)](https://fastapi.tiangolo.com/)
[![UE5](https://img.shields.io/badge/Client-Unreal%20Engine%205.8-black)](https://www.unrealengine.com/)
[![Tests](https://img.shields.io/badge/Tests-1207%20passing-brightgreen)](#testing)

## Architecture

```
Mobile App (Expo/RN)     Map Data
     |                       |
 Video Upload            Base World
     |                       |
 Reconstruction     Visual Localization
     |                       |
     +----- GEO WORLD MODEL --+
                    |
          +--------+--------+
          |                 |
      Players          Locations
     (WebSocket)       (Database)
          |                 |
          +---- PC CLIENT --+
          |
     UE5 CLIENT
```

### Components

| Component | Tech Stack | Port | Status |
|-----------|-----------|------|--------|
| Backend REST API | Python 3.12, FastAPI, SQLAlchemy, SQLite | 8000 | Running |
| WebSocket Server | Python 3.12, FastAPI WebSocket | 8765 | Running |
| PC Client | TypeScript, Three.js, Vite | 3000 | Running |
| UE5 Client | C++, Unreal Engine 5.8 | - | Running |
| Mobile App | Expo 52, React Native 0.76 | - | Built |
| Database | SQLite (file-based) | - | Running |
| Docker | docker-compose (3 services) | - | Configured |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 24+ / npm 11+
- Docker & Docker Compose
- Unreal Engine 5.8 (for UE5 client)
- Android SDK (for mobile app)

### Docker (Recommended)

```bash
docker-compose up -d
```

Services:
- Backend API: http://localhost:8000
- WebSocket: ws://localhost:8765
- PC Client: http://localhost:3000

### Manual Setup

#### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

#### WebSocket Server

```bash
cd backend
python -m uvicorn app.websocket_server:app --port 8765
```

#### PC Client

```bash
cd pc-client
npm install
npm run dev
```

#### UE5 Client

```bash
# Build
"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" ^
  RecordedWorldEditor Win64 Development ^
  -Project="ue-client\RecordedWorld.uproject"

# Launch
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" ^
  "ue-client\RecordedWorld.uproject"
```

#### Mobile App

```bash
cd mobile-app
npm install
npx expo start
```

## Features

### Core Systems
- **Geospatial Foundation**: WGS84 coordinates, ENU local frame, Haversine distance, grid-based spatial index
- **Video Processing Pipeline**: Frame extraction, blur/exposure analysis, SSIM deduplication, feature extraction (SIFT/ORB/AKAZE)
- **3D Reconstruction**: Camera pose estimation, point cloud generation, mesh generation, texture mapping
- **Real-time Multiplayer**: WebSocket with spatial interest management, server-authoritative movement, position interpolation

### Gameplay
- **Procedural World Generation**: Terrain heightmap, cross-shaped road network, Art Deco buildings, tree clusters, mountains with snow caps, water features, street furniture
- **Player System**: WASD movement, third-person camera, procedural walk/run animation, 18 body part articulation
- **Social Features**: Friend system, chat, player visibility controls, location sharing with privacy modes

### UE5 Client
- **GTA Vice City Visuals**: Warm Miami sunset lighting, Art Deco building palette, post-process bloom/saturation/vignette
- **Procedural Mesh Generation**: Terrain, roads, buildings, trees, mountains, water, street furniture with vertex colors
- **Networking**: WebSocket connection to multiplayer server, remote player rendering with name billboards

### Mobile App
- **Video Capture**: Camera recording with viewfinder overlay
- **GPS Tracking**: Location recording with accuracy data
- **Upload System**: Progress tracking, offline queue with auto-retry

### Backend
- **REST API**: JWT authentication, user/capture/location CRUD, spatial search, pipeline control
- **WebSocket Server**: Player join/leave/position relay, chat, spatial interest management, heartbeat
- **Services**: Auth, Player, Location, World, Media, Reconstruction, Asset, Social, Moderation, Notification
- **Security**: Rate limiting, input validation, audit logging, signed asset URLs

## Testing

```bash
# Backend (1207 tests)
cd backend && pytest tests/ -v

# PC Client (42 tests)
cd pc-client && npx vitest run

# Mobile App (36 tests)
cd mobile-app && npx vitest run
```

## Project Structure

```
recorded-world/
├── backend/                  # Python FastAPI backend
│   ├── app/                  # Application code
│   │   ├── main.py           # FastAPI app entry
│   │   ├── websocket_server.py
│   │   ├── models/           # SQLAlchemy models
│   │   ├── routers/          # API routes
│   │   ├── services/         # Business logic
│   │   └── auth/             # JWT authentication
│   ├── tests/                # 1207 pytest tests
│   └── requirements.txt
├── pc-client/                # TypeScript Three.js client
│   ├── src/                  # Source modules
│   │   ├── main.ts
│   │   ├── environment.ts
│   │   ├── player-model.ts
│   │   ├── camera-controller.ts
│   │   └── effects.ts
│   └── public/models/        # 23 GLB Blender assets
├── mobile-app/               # React Native Expo app
│   ├── app/                  # Expo Router screens
│   ├── components/           # UI components
│   └── hooks/                # Custom hooks
├── ue-client/                # Unreal Engine 5.8 client
│   ├── Source/RecordedWorld/ # C++ source
│   │   ├── Public/           # Headers
│   │   └── Private/          # Implementation
│   ├── Content/              # Assets
│   └── RecordedWorld.uproject
├── shared/                   # Shared types
├── docker-compose.yml
└── ROADMAP.md                # Authoritative roadmap
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/users` | Create user |
| POST | `/api/users/login` | JWT login |
| GET | `/api/users/me` | Get current user |
| POST | `/api/captures` | Upload video |
| GET | `/api/captures` | List captures |
| POST | `/api/locations` | Create location |
| GET | `/api/locations/nearby` | Spatial search |
| GET | `/api/locations/cities/list` | World cities |
| GET | `/api/pipeline/process/{id}` | Process capture |
| GET | `/health` | Health check |
| GET | `/metrics` | System metrics |

## WebSocket Protocol

```json
// Join
{"type": "join", "username": "player1", "world_id": "world_1"}

// Position update
{"type": "move", "x": 100.0, "y": 200.0, "z": 0.0, "rotation": 45.0}

// Chat
{"type": "chat", "message": "Hello world!"}

// Player list
{"type": "world_state", "players": [...]}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./recorded_world.db` | Database connection |
| `SECRET_KEY` | (generated) | JWT signing key |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed origins |
| `WS_HOST` | `0.0.0.0` | WebSocket host |
| `WS_PORT` | `8765` | WebSocket port |

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full project roadmap and phase tracking.

### Completed Phases
- Phase 0: Project audit & stabilization
- Phase 1: Geospatial foundation
- Phase 4-8: Video processing, 3D reconstruction, alignment
- Phase 11-28: Location discovery, avatars, social, privacy, moderation, optimization
- Phase 29-32: MVP, backend architecture, database, JWT auth
- UE5 Phases A-F: C++ setup, procedural world, networking, player, HUD, GTA VC visuals

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Unreal Engine 5.8](https://www.unrealengine.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Three.js](https://threejs.org/)
- [Expo](https://expo.dev/)
- [OpenCV](https://opencv.org/)
