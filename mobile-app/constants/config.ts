export const Colors = {
  primary: '#00ff88',
  secondary: '#0088ff',
  background: '#1a1a2e',
  surface: '#16213e',
  surfaceLight: '#1f2b47',
  text: '#ffffff',
  textSecondary: '#888888',
  error: '#ff4444',
  warning: '#ffaa00',
  success: '#00ff88',
  border: '#2a3a5c',
};

const SERVER_HOST = 'equity-wrinkle-empirical.ngrok-free.dev';

export const Config = {
  api: {
    baseUrl: `https://${SERVER_HOST}`,
    timeout: 30000,
  },
  ws: {
    url: `wss://${SERVER_HOST}/ws`,
  },
  camera: {
    quality: '1080p',
    maxDuration: 300, // 5 minutes
    fps: 30,
  },
  upload: {
    maxRetries: 3,
    chunkSize: 1024 * 1024, // 1MB chunks
  },
};
