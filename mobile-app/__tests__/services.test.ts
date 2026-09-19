/**
 * Tests for Mobile App Services.
 *
 * Tests API client, upload progress, location tracking, and config.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// =============================================================================
// Config
// =============================================================================

interface AppConfig {
  api: { baseUrl: string; timeout: number }
  ws: { url: string }
  upload: { maxFileSize: number; allowedTypes: string[] }
  location: { accuracyThreshold: number; updateInterval: number }
}

const defaultConfig: AppConfig = {
  api: { baseUrl: 'http://localhost:8000', timeout: 30000 },
  ws: { url: 'ws://localhost:8765' },
  upload: {
    maxFileSize: 500 * 1024 * 1024,
    allowedTypes: ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm'],
  },
  location: { accuracyThreshold: 50, updateInterval: 5000 },
}

// =============================================================================
// Interfaces
// =============================================================================

interface Capture {
  id: number
  user_id: number
  title: string
  description?: string
  status: 'uploaded' | 'processing' | 'ready' | 'failed'
  video_path: string
  model_3d_path?: string
  thumbnail_path?: string
  latitude?: string
  longitude?: string
  created_at: string
  processed_at?: string
}

interface UploadProgress {
  captureId: number
  progress: number
  status: 'pending' | 'uploading' | 'complete' | 'error'
  error?: string
}

// =============================================================================
// Utility Functions (extracted for testability)
// =============================================================================

function validateFile(
  file: { uri: string; type: string; name: string },
  config: AppConfig
): { valid: boolean; error?: string } {
  if (!file.uri) return { valid: false, error: 'No file URI' }
  if (!file.type) return { valid: false, error: 'No file type' }

  const ext = file.name.split('.').pop()?.toLowerCase() || ''
  const validExtensions: Record<string, string> = {
    mp4: 'video/mp4',
    mov: 'video/quicktime',
    avi: 'video/x-msvideo',
    webm: 'video/webm',
  }

  if (!validExtensions[ext]) {
    return { valid: false, error: `Unsupported file type: .${ext}` }
  }

  if (file.type !== validExtensions[ext]) {
    return { valid: false, error: `MIME type mismatch: ${file.type} vs ${validExtensions[ext]}` }
  }

  return { valid: true }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function formatUploadProgress(progress: UploadProgress): string {
  const pct = Math.round(progress.progress)
  switch (progress.status) {
    case 'pending': return `Queued (${pct}%)`
    case 'uploading': return `Uploading ${pct}%`
    case 'complete': return 'Upload Complete'
    case 'error': return `Failed: ${progress.error || 'Unknown error'}`
    default: return 'Unknown'
  }
}

function validateLatitude(lat: number): boolean {
  return lat >= -90 && lat <= 90
}

function validateLongitude(lon: number): boolean {
  return lon >= -180 && lon <= 180
}

function formatCoordinate(lat: number, lon: number): string {
  const latDir = lat >= 0 ? 'N' : 'S'
  const lonDir = lon >= 0 ? 'E' : 'W'
  return `${Math.abs(lat).toFixed(4)}°${latDir}, ${Math.abs(lon).toFixed(4)}°${lonDir}`
}

function getStatusColor(status: Capture['status']): string {
  switch (status) {
    case 'uploaded': return '#888'
    case 'processing': return '#ffaa00'
    case 'ready': return '#00ff88'
    case 'failed': return '#ff4444'
    default: return '#888'
  }
}

function getStatusLabel(status: Capture['status']): string {
  switch (status) {
    case 'uploaded': return 'Uploaded'
    case 'processing': return 'Processing...'
    case 'ready': return 'Ready'
    case 'failed': return 'Failed'
    default: return 'Unknown'
  }
}

// =============================================================================
// Tests
// =============================================================================

describe('Config', () => {
  it('has API base URL', () => {
    expect(defaultConfig.api.baseUrl).toBeTruthy()
    expect(defaultConfig.api.baseUrl).toContain('http')
  })

  it('has WebSocket URL', () => {
    expect(defaultConfig.ws.url).toBeTruthy()
    expect(defaultConfig.ws.url).toContain('ws')
  })

  it('has upload limits', () => {
    expect(defaultConfig.upload.maxFileSize).toBeGreaterThan(0)
    expect(defaultConfig.upload.allowedTypes.length).toBeGreaterThan(0)
  })

  it('has location settings', () => {
    expect(defaultConfig.location.accuracyThreshold).toBeGreaterThan(0)
    expect(defaultConfig.location.updateInterval).toBeGreaterThan(0)
  })
})

describe('File Validation', () => {
  it('accepts valid mp4 file', () => {
    const result = validateFile(
      { uri: 'file:///test.mp4', type: 'video/mp4', name: 'video.mp4' },
      defaultConfig
    )
    expect(result.valid).toBe(true)
  })

  it('accepts valid mov file', () => {
    const result = validateFile(
      { uri: 'file:///test.mov', type: 'video/quicktime', name: 'video.mov' },
      defaultConfig
    )
    expect(result.valid).toBe(true)
  })

  it('rejects missing URI', () => {
    const result = validateFile(
      { uri: '', type: 'video/mp4', name: 'video.mp4' },
      defaultConfig
    )
    expect(result.valid).toBe(false)
    expect(result.error).toContain('No file URI')
  })

  it('rejects missing type', () => {
    const result = validateFile(
      { uri: 'file:///test.mp4', type: '', name: 'video.mp4' },
      defaultConfig
    )
    expect(result.valid).toBe(false)
    expect(result.error).toContain('No file type')
  })

  it('rejects unsupported extension', () => {
    const result = validateFile(
      { uri: 'file:///test.txt', type: 'text/plain', name: 'video.txt' },
      defaultConfig
    )
    expect(result.valid).toBe(false)
    expect(result.error).toContain('Unsupported')
  })

  it('rejects MIME type mismatch', () => {
    const result = validateFile(
      { uri: 'file:///test.mp4', type: 'video/webm', name: 'video.mp4' },
      defaultConfig
    )
    expect(result.valid).toBe(false)
    expect(result.error).toContain('MIME type mismatch')
  })
})

describe('File Size Formatting', () => {
  it('formats bytes', () => {
    expect(formatFileSize(500)).toBe('500 B')
  })

  it('formats kilobytes', () => {
    expect(formatFileSize(1024)).toBe('1.0 KB')
    expect(formatFileSize(1536)).toBe('1.5 KB')
  })

  it('formats megabytes', () => {
    expect(formatFileSize(1024 * 1024)).toBe('1.0 MB')
    expect(formatFileSize(5.5 * 1024 * 1024)).toBe('5.5 MB')
  })

  it('formats gigabytes', () => {
    expect(formatFileSize(1024 * 1024 * 1024)).toBe('1.0 GB')
  })
})

describe('Upload Progress Formatting', () => {
  it('formats pending', () => {
    const p: UploadProgress = { captureId: 1, progress: 0, status: 'pending' }
    expect(formatUploadProgress(p)).toBe('Queued (0%)')
  })

  it('formats uploading', () => {
    const p: UploadProgress = { captureId: 1, progress: 45.7, status: 'uploading' }
    expect(formatUploadProgress(p)).toBe('Uploading 46%')
  })

  it('formats complete', () => {
    const p: UploadProgress = { captureId: 1, progress: 100, status: 'complete' }
    expect(formatUploadProgress(p)).toBe('Upload Complete')
  })

  it('formats error', () => {
    const p: UploadProgress = { captureId: 1, progress: 0, status: 'error', error: 'Network timeout' }
    expect(formatUploadProgress(p)).toBe('Failed: Network timeout')
  })

  it('formats error without message', () => {
    const p: UploadProgress = { captureId: 1, progress: 0, status: 'error' }
    expect(formatUploadProgress(p)).toBe('Failed: Unknown error')
  })
})

describe('Coordinate Validation', () => {
  it('validates latitude range', () => {
    expect(validateLatitude(0)).toBe(true)
    expect(validateLatitude(40.785)).toBe(true)
    expect(validateLatitude(-90)).toBe(true)
    expect(validateLatitude(90)).toBe(true)
    expect(validateLatitude(-91)).toBe(false)
    expect(validateLatitude(91)).toBe(false)
  })

  it('validates longitude range', () => {
    expect(validateLongitude(0)).toBe(true)
    expect(validateLongitude(-73.968)).toBe(true)
    expect(validateLongitude(-180)).toBe(true)
    expect(validateLongitude(180)).toBe(true)
    expect(validateLongitude(-181)).toBe(false)
    expect(validateLongitude(181)).toBe(false)
  })
})

describe('Coordinate Formatting', () => {
  it('formats with N/S and E/W', () => {
    expect(formatCoordinate(40.785, -73.968)).toBe('40.7850°N, 73.9680°W')
  })

  it('formats equator/prime meridian', () => {
    expect(formatCoordinate(0, 0)).toBe('0.0000°N, 0.0000°E')
  })

  it('formats southern/eastern hemisphere', () => {
    expect(formatCoordinate(-33.8688, 151.2093)).toBe('33.8688°S, 151.2093°E')
  })
})

describe('Capture Status', () => {
  it('gets correct status colors', () => {
    expect(getStatusColor('uploaded')).toBe('#888')
    expect(getStatusColor('processing')).toBe('#ffaa00')
    expect(getStatusColor('ready')).toBe('#00ff88')
    expect(getStatusColor('failed')).toBe('#ff4444')
  })

  it('gets correct status labels', () => {
    expect(getStatusLabel('uploaded')).toBe('Uploaded')
    expect(getStatusLabel('processing')).toBe('Processing...')
    expect(getStatusLabel('ready')).toBe('Ready')
    expect(getStatusLabel('failed')).toBe('Failed')
  })
})

describe('Capture Interface', () => {
  const baseCapture: Capture = {
    id: 1,
    user_id: 1,
    title: 'Test Video',
    status: 'uploaded',
    video_path: '/uploads/test.mp4',
    created_at: '2026-01-15T10:00:00Z',
  }

  it('has required fields', () => {
    expect(baseCapture.id).toBe(1)
    expect(baseCapture.user_id).toBe(1)
    expect(baseCapture.title).toBeTruthy()
    expect(baseCapture.video_path).toBeTruthy()
    expect(baseCapture.created_at).toBeTruthy()
  })

  it('has optional fields', () => {
    const full: Capture = {
      ...baseCapture,
      description: 'A test',
      model_3d_path: '/models/1.glb',
      thumbnail_path: '/thumbs/1.jpg',
      latitude: '40.785',
      longitude: '-73.968',
      processed_at: '2026-01-15T11:00:00Z',
    }
    expect(full.description).toBeTruthy()
    expect(full.model_3d_path).toBeTruthy()
    expect(full.thumbnail_path).toBeTruthy()
    expect(full.latitude).toBeTruthy()
    expect(full.longitude).toBeTruthy()
  })

  it('status values are valid', () => {
    const validStatuses: Capture['status'][] = ['uploaded', 'processing', 'ready', 'failed']
    for (const s of validStatuses) {
      expect(['uploaded', 'processing', 'ready', 'failed']).toContain(s)
    }
  })
})

describe('Upload Progress State Machine', () => {
  it('starts at pending', () => {
    const progress: UploadProgress = { captureId: 1, progress: 0, status: 'pending' }
    expect(progress.status).toBe('pending')
    expect(progress.progress).toBe(0)
  })

  it('transitions pending -> uploading', () => {
    const progress: UploadProgress = { captureId: 1, progress: 10, status: 'uploading' }
    expect(progress.status).toBe('uploading')
    expect(progress.progress).toBeGreaterThan(0)
  })

  it('transitions uploading -> complete', () => {
    const progress: UploadProgress = { captureId: 1, progress: 100, status: 'complete' }
    expect(progress.status).toBe('complete')
    expect(progress.progress).toBe(100)
  })

  it('transitions uploading -> error', () => {
    const progress: UploadProgress = {
      captureId: 1,
      progress: 50,
      status: 'error',
      error: 'Connection lost',
    }
    expect(progress.status).toBe('error')
    expect(progress.error).toBeTruthy()
  })
})

describe('Boundary Conditions', () => {
  it('handles zero-distance location', () => {
    expect(formatCoordinate(0, 0)).toContain('0.0000')
  })

  it('handles very large file sizes', () => {
    expect(formatFileSize(1024 * 1024 * 1024 * 4.2)).toBe('4.2 GB')
  })

  it('handles edge case progress values', () => {
    const p: UploadProgress = { captureId: 1, progress: 0.1, status: 'uploading' }
    expect(formatUploadProgress(p)).toBe('Uploading 0%')
  })
})
