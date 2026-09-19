export const config = {
  api: {
    baseUrl: process.env.API_URL || 'http://localhost:8000',
  },
  ws: {
    url: process.env.WS_URL || 'ws://localhost:8765',
  },
  game: {
    maxPlayersPerWorld: 20,
    worldSize: 100,
    playerSpeed: 0.15,
    viewDistance: 100,
  },
  upload: {
    maxFileSize: 500 * 1024 * 1024, // 500MB
    allowedTypes: ['video/mp4', 'video/quicktime', 'video/webm'],
  },
};
