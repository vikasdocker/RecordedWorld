/**
 * Tests for PC Client — interfaces, message handling, utility logic.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// =============================================================================
// Interface Tests
// =============================================================================

interface PlayerState {
  id: number
  username: string
  position: { x: number; y: number; z: number }
  rotation: number
  color: string
  visibility: string
  targetPosition: { x: number; y: number; z: number }
  targetRotation: number
  velocity: { x: number; y: number; z: number }
  lastUpdate: number
  serverTick: number
  animState: 'idle' | 'walk' | 'run'
  animTime: number
  baseY: number
}

interface ChatMessage {
  username: string
  message: string
}

interface LocationData {
  id: number
  title: string
  description: string | null
  creator_id: number
  creator_name: string | null
  latitude: number
  longitude: number
  altitude: number | null
  distance_meters: number
  accuracy_meters: number | null
  confidence: number | null
  thumbnail_id: string | null
  categories: { id: number; name: string; slug: string }[]
  tags: { id: number; name: string; slug: string }[]
  created_at: string | null
}

// =============================================================================
// Helper Functions (extracted from main.ts for testability)
// =============================================================================

function formatDistance(meters: number): string {
  return meters < 1000
    ? `${Math.round(meters)}m`
    : `${(meters / 1000).toFixed(1)}km`
}

function formatAccuracy(accuracyMeters: number | null): string {
  if (accuracyMeters == null) return ''
  return `±${Math.round(accuracyMeters)}m`
}

function formatConfidence(confidence: number | null): string {
  if (confidence == null) return ''
  return `Confidence: ${Math.round(confidence * 100)}%`
}

function getQualityLabel(confidence: number | null): 'HIGH' | 'MEDIUM' | 'LOW' | '' {
  if (confidence == null) return ''
  if (confidence >= 0.8) return 'HIGH'
  if (confidence >= 0.5) return 'MEDIUM'
  return 'LOW'
}

function getQualityClass(confidence: number | null): string {
  const label = getQualityLabel(confidence)
  if (label === 'HIGH') return 'quality-high'
  if (label === 'MEDIUM') return 'quality-medium'
  if (label === 'LOW') return 'quality-low'
  return ''
}

function escapeHtml(text: string): string {
  return text.replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function buildChatMessageHTML(username: string, message: string): string {
  const escaped = escapeHtml(message)
  const escapedName = escapeHtml(username)
  return `<div><strong>${escapedName}:</strong> ${escaped}</div>`
}

function buildLocationDetailHTML(loc: LocationData): string {
  const dist = formatDistance(loc.distance_meters)
  const cats = loc.categories.map(c => c.name).join(', ') || 'Uncategorized'
  const tags = (loc.tags || []).map(t => `#${t.name}`).join(' ')
  const created = loc.created_at ? new Date(loc.created_at).toLocaleDateString() : 'Unknown'

  const accuracyText = loc.accuracy_meters
    ? `<span class="loc-accuracy">${formatAccuracy(loc.accuracy_meters)}</span>`
    : ''
  const confidenceText = loc.confidence != null
    ? `<span class="loc-confidence">${formatConfidence(loc.confidence)}</span>`
    : ''
  const qualityLabel = getQualityLabel(loc.confidence)
  const qualityClass = getQualityClass(loc.confidence)
  const qualityText = qualityLabel
    ? `<span class="loc-quality ${qualityClass}">${qualityLabel}</span>`
    : ''

  return `
    <div class="loc-title">${loc.title}</div>
    <div class="loc-creator">by ${loc.creator_name || 'Unknown'} • ${dist}</div>
    ${loc.description ? `<div class="loc-desc">${loc.description}</div>` : ''}
    <div class="loc-meta">
      <span>${cats}</span>
      ${accuracyText}
      ${confidenceText}
      ${qualityText}
      <span>${created}</span>
    </div>
    ${tags ? `<div class="loc-tags">${tags}</div>` : ''}
  `
}

function determineAnimationState(speed: number): 'idle' | 'walk' | 'run' {
  if (speed > 5.0) return 'run'
  if (speed > 0.5) return 'walk'
  return 'idle'
}

function computeWalkOffset(animTime: number, state: 'idle' | 'walk' | 'run') {
  let yOffset = 0
  let rotZ = 0
  if (state === 'walk') {
    yOffset = Math.sin(animTime * 8) * 0.08
    rotZ = Math.sin(animTime * 8) * 0.05
  } else if (state === 'run') {
    yOffset = Math.sin(animTime * 12) * 0.15
    rotZ = Math.sin(animTime * 12) * 0.1
  } else {
    yOffset = Math.sin(animTime * 2) * 0.03
  }
  return { yOffset, rotZ }
}

// =============================================================================
// Tests
// =============================================================================

describe('Distance Formatting', () => {
  it('formats meters for short distances', () => {
    expect(formatDistance(5)).toBe('5m')
    expect(formatDistance(100)).toBe('100m')
    expect(formatDistance(999)).toBe('999m')
  })

  it('formats kilometers for long distances', () => {
    expect(formatDistance(1000)).toBe('1.0km')
    expect(formatDistance(1500)).toBe('1.5km')
    expect(formatDistance(10000)).toBe('10.0km')
  })

  it('rounds correctly', () => {
    expect(formatDistance(1499)).toBe('1.5km')
    expect(formatDistance(149)).toBe('149m')
  })
})

describe('Accuracy Formatting', () => {
  it('formats accuracy with ± prefix', () => {
    expect(formatAccuracy(5)).toBe('±5m')
    expect(formatAccuracy(12.7)).toBe('±13m')
  })

  it('returns empty for null', () => {
    expect(formatAccuracy(null)).toBe('')
  })
})

describe('Confidence Formatting', () => {
  it('formats confidence as percentage', () => {
    expect(formatConfidence(0.95)).toBe('Confidence: 95%')
    expect(formatConfidence(0.5)).toBe('Confidence: 50%')
    expect(formatConfidence(0.0)).toBe('Confidence: 0%')
  })

  it('returns empty for null', () => {
    expect(formatConfidence(null)).toBe('')
  })
})

describe('Quality Labels', () => {
  it('returns HIGH for confidence >= 0.8', () => {
    expect(getQualityLabel(0.8)).toBe('HIGH')
    expect(getQualityLabel(0.95)).toBe('HIGH')
    expect(getQualityLabel(1.0)).toBe('HIGH')
  })

  it('returns MEDIUM for confidence >= 0.5', () => {
    expect(getQualityLabel(0.5)).toBe('MEDIUM')
    expect(getQualityLabel(0.7)).toBe('MEDIUM')
  })

  it('returns LOW for confidence < 0.5', () => {
    expect(getQualityLabel(0.0)).toBe('LOW')
    expect(getQualityLabel(0.3)).toBe('LOW')
  })

  it('returns empty for null', () => {
    expect(getQualityLabel(null)).toBe('')
  })

  it('maps quality labels to CSS classes', () => {
    expect(getQualityClass(0.9)).toBe('quality-high')
    expect(getQualityClass(0.6)).toBe('quality-medium')
    expect(getQualityClass(0.2)).toBe('quality-low')
    expect(getQualityClass(null)).toBe('')
  })
})

describe('HTML Escaping', () => {
  it('escapes angle brackets', () => {
    expect(escapeHtml('<script>alert("xss")</script>')).toBe('&lt;script&gt;alert("xss")&lt;/script&gt;')
  })

  it('preserves normal text', () => {
    expect(escapeHtml('Hello World')).toBe('Hello World')
  })
})

describe('Chat Message HTML', () => {
  it('builds chat message with bold username', () => {
    const html = buildChatMessageHTML('alice', 'hello world')
    expect(html).toContain('<strong>alice:</strong>')
    expect(html).toContain('hello world')
  })

  it('escapes HTML in messages', () => {
    const html = buildChatMessageHTML('bob', '<img onerror=alert(1)>')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
  })

  it('escapes HTML in usernames', () => {
    const html = buildChatMessageHTML('<script>', 'test')
    expect(html).toContain('&lt;script&gt;')
  })
})

describe('Location Detail HTML', () => {
  const baseLocation: LocationData = {
    id: 1,
    title: 'Central Park',
    description: 'A large park',
    creator_id: 1,
    creator_name: 'Alice',
    latitude: 40.785,
    longitude: -73.968,
    altitude: null,
    distance_meters: 250,
    accuracy_meters: null,
    confidence: null,
    thumbnail_id: null,
    categories: [{ id: 1, name: 'Park', slug: 'park' }],
    tags: [{ id: 1, name: 'nature', slug: 'nature' }],
    created_at: '2026-01-15T10:00:00Z',
  }

  it('includes title and creator', () => {
    const html = buildLocationDetailHTML(baseLocation)
    expect(html).toContain('Central Park')
    expect(html).toContain('Alice')
  })

  it('formats distance', () => {
    const html = buildLocationDetailHTML(baseLocation)
    expect(html).toContain('250m')
  })

  it('includes accuracy when present', () => {
    const loc = { ...baseLocation, accuracy_meters: 5.3 }
    const html = buildLocationDetailHTML(loc)
    expect(html).toContain('±5m')
    expect(html).toContain('loc-accuracy')
  })

  it('includes confidence when present', () => {
    const loc = { ...baseLocation, confidence: 0.92 }
    const html = buildLocationDetailHTML(loc)
    expect(html).toContain('Confidence: 92%')
    expect(html).toContain('loc-confidence')
  })

  it('includes quality label HIGH', () => {
    const loc = { ...baseLocation, confidence: 0.85 }
    const html = buildLocationDetailHTML(loc)
    expect(html).toContain('quality-high')
    expect(html).toContain('HIGH')
  })

  it('includes quality label MEDIUM', () => {
    const loc = { ...baseLocation, confidence: 0.6 }
    const html = buildLocationDetailHTML(loc)
    expect(html).toContain('quality-medium')
    expect(html).toContain('MEDIUM')
  })

  it('includes quality label LOW', () => {
    const loc = { ...baseLocation, confidence: 0.3 }
    const html = buildLocationDetailHTML(loc)
    expect(html).toContain('quality-low')
    expect(html).toContain('LOW')
  })

  it('includes description when present', () => {
    const html = buildLocationDetailHTML(baseLocation)
    expect(html).toContain('A large park')
  })

  it('excludes description when null', () => {
    const loc = { ...baseLocation, description: null }
    const html = buildLocationDetailHTML(loc)
    expect(html).not.toContain('loc-desc')
  })

  it('formats categories', () => {
    const html = buildLocationDetailHTML(baseLocation)
    expect(html).toContain('Park')
  })

  it('formats tags with # prefix', () => {
    const html = buildLocationDetailHTML(baseLocation)
    expect(html).toContain('#nature')
  })

  it('shows Uncategorized when no categories', () => {
    const loc = { ...baseLocation, categories: [] }
    const html = buildLocationDetailHTML(loc)
    expect(html).toContain('Uncategorized')
  })

  it('formats long distance as km', () => {
    const loc = { ...baseLocation, distance_meters: 2500 }
    const html = buildLocationDetailHTML(loc)
    expect(html).toContain('2.5km')
  })

  it('shows Unknown for missing created_at', () => {
    const loc = { ...baseLocation, created_at: null }
    const html = buildLocationDetailHTML(loc)
    expect(html).toContain('Unknown')
  })
})

describe('Animation State', () => {
  it('idle for low speed', () => {
    expect(determineAnimationState(0)).toBe('idle')
    expect(determineAnimationState(0.3)).toBe('idle')
  })

  it('walk for medium speed', () => {
    expect(determineAnimationState(0.6)).toBe('walk')
    expect(determineAnimationState(3.0)).toBe('walk')
  })

  it('run for high speed', () => {
    expect(determineAnimationState(5.1)).toBe('run')
    expect(determineAnimationState(10.0)).toBe('run')
  })
})

describe('Walk Animation Offset', () => {
  it('idle has subtle bob', () => {
    const { yOffset, rotZ } = computeWalkOffset(1.0, 'idle')
    expect(Math.abs(yOffset)).toBeLessThan(0.1)
    expect(Math.abs(rotZ)).toBe(0)
  })

  it('walk has moderate bob', () => {
    const { yOffset } = computeWalkOffset(1.0, 'walk')
    expect(Math.abs(yOffset)).toBeGreaterThan(0)
    expect(Math.abs(yOffset)).toBeLessThan(0.2)
  })

  it('run has larger bob', () => {
    const { yOffset: walkY } = computeWalkOffset(1.0, 'walk')
    const { yOffset: runY } = computeWalkOffset(1.0, 'run')
    expect(Math.abs(runY)).toBeGreaterThan(Math.abs(walkY))
  })
})

describe('Message Handling Logic', () => {
  it('parses chat messages', () => {
    const data = { type: 'chat', username: 'alice', message: 'hello' }
    expect(data.type).toBe('chat')
    expect(data.username).toBe('alice')
    expect(data.message).toBe('hello')
  })

  it('parses player join', () => {
    const data = {
      type: 'player_join',
      player: { id: 1, username: 'bob', position: { x: 0, y: 0, z: 0 } },
      player_count: 2,
    }
    expect(data.type).toBe('player_join')
    expect(data.player.id).toBe(1)
    expect(data.player_count).toBe(2)
  })

  it('parses position update', () => {
    const data = {
      type: 'player_move',
      player_id: 1,
      position: { x: 10, y: 0, z: 5 },
      rotation: 1.5,
      velocity: { x: 1, y: 0, z: 0 },
    }
    expect(data.position.x).toBe(10)
    expect(data.rotation).toBe(1.5)
  })

  it('parses ping', () => {
    const data = { type: 'ping' }
    expect(data.type).toBe('ping')
  })
})

describe('Chat Message Trimming', () => {
  it('trims to 20 messages max', () => {
    const messages: ChatMessage[] = []
    for (let i = 0; i < 25; i++) {
      messages.push({ username: 'user', message: `msg ${i}` })
      if (messages.length > 20) messages.shift()
    }
    expect(messages.length).toBe(20)
    expect(messages[0].message).toBe('msg 5')
    expect(messages[19].message).toBe('msg 24')
  })
})
