export interface User {
  id: number;
  username: string;
  email: string;
  avatar_url?: string;
  created_at: string;
}

export interface Capture {
  id: number;
  user_id: number;
  title: string;
  description?: string;
  status: 'uploaded' | 'processing' | 'ready' | 'failed';
  video_path: string;
  model_3d_path?: string;
  thumbnail_path?: string;
  latitude?: string;
  longitude?: string;
  created_at: string;
  processed_at?: string;
}

export interface GameWorld {
  id: number;
  name: string;
  capture_id: number;
  spawn: { x: number; y: number; z: number };
  max_players: number;
  created_at: string;
}

export interface PlayerState {
  id: number;
  username: string;
  position: { x: number; y: number; z: number };
  rotation: number;
  avatar_url?: string;
}

export interface ChatMessage {
  user_id: number;
  username: string;
  message: string;
  timestamp: string;
}
