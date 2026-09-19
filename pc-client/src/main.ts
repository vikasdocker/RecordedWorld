import * as THREE from 'three'
import { Sky } from 'three/addons/objects/Sky.js'
import { Environment } from './environment'
import {
  ArticulatedPlayer,
  createArticulatedPlayer,
  animatePlayer,
  createLabel,
} from './player-model'
import { CameraController } from './camera-controller'
import { PostProcessing } from './effects'
import { AudioSystem } from './audio'

interface RemotePlayerState {
  id: number
  username: string
  position: THREE.Vector3
  rotation: number
  mesh: THREE.Group
  label: THREE.Sprite
  color: string
  visibility: string
  targetPosition: THREE.Vector3
  targetRotation: number
  velocity: THREE.Vector3
  lastUpdate: number
  animState: 'idle' | 'walk' | 'run'
  animTime: number
  baseY: number
  player: ArticulatedPlayer
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

interface LocationMarker {
  id: number
  data: LocationData
  group: THREE.Group
  pin: THREE.Mesh
  label: THREE.Sprite
  beam: THREE.Mesh
}

const SERVER_HOST = 'equity-wrinkle-empirical.ngrok-free.dev'
const API_BASE = `https://${SERVER_HOST}`
const WS_BASE = `wss://${SERVER_HOST}/ws`
const LOCATION_FETCH_INTERVAL = 5000
const LOCATION_FETCH_RADIUS = 2000
const METERS_PER_UNIT = 1
const USER_ID = 1 // temporary user ID until auth is implemented

interface CityData {
  id: string
  name: string
  country: string
  lat: number
  lon: number
  description: string
}

interface FriendData {
  id: number
  username: string
  display_name: string | null
  avatar_url: string | null
  status: string
}

class MultiplayerGame {
  private scene: THREE.Scene
  private camera: THREE.PerspectiveCamera
  private renderer: THREE.WebGLRenderer
  private cameraCtrl: CameraController
  private postFX: PostProcessing

  private playerMesh!: ArticulatedPlayer
  private playerGroup: THREE.Group
  private remotePlayers: Map<number, RemotePlayerState> = new Map()
  private keys: Set<string> = new Set()
  private ws: WebSocket | null = null
  private username: string = ''
  private chatMessages: ChatMessage[] = []
  private lastFrameTime: number = Date.now()
  private locationMarkers: Map<number, LocationMarker> = new Map()
  private lastLocationFetch: number = 0
  private selectedLocation: LocationMarker | null = null
  private playerColor: string = '#00ff88'
  private playerLatitude: number = 40.785
  private playerLongitude: number = -73.968
  private sunLight: THREE.DirectionalLight | null = null
  private minimapCanvas: HTMLCanvasElement | null = null
  private minimapCtx: CanvasRenderingContext2D | null = null
  private minimapSize: number = 180
  private environment: Environment
  private sky: Sky
  private timeOfDay: number = 12 // 0-24 hours, start at noon
  private dayNightSpeed: number = 0.0005 // hours per ms (5 min for full cycle)
  private blobShadow: THREE.Mesh | null = null
  private audioSystem: AudioSystem | null = null
  private statsEl: HTMLElement | null = null
  private fpsFrames: number = 0
  private fpsLastTime: number = performance.now()
  private currentCity: CityData | null = null
  private cities: CityData[] = []
  private friends: FriendData[] = []
  private currentVisibility: string = 'public'
  private dmTarget: string = ''
  private capturedModels: Map<number, THREE.Group> = new Map()

  constructor() {

    this.scene = new THREE.Scene()

    this.camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      0.1,
      2000
    )

    this.renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance' })
    this.renderer.setSize(window.innerWidth, window.innerHeight)
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 0.85
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    this.renderer.info.autoReset = false
    document.body.appendChild(this.renderer.domElement)

    this.cameraCtrl = new CameraController(this.camera)

    this.sky = this.setupSky()

    this.addLights()

    this.environment = new Environment(this.scene, { size: 500, segments: 200 })
    this.environment.setLODCamera(this.camera)
    this.environment.buildAll()

    this.playerGroup = new THREE.Group()
    this.scene.add(this.playerGroup)
    this.playerMesh = createArticulatedPlayer(0xffdbac, this.playerColor)
    this.playerGroup.add(this.playerMesh.group)

    this.blobShadow = new THREE.Mesh(
      new THREE.CircleGeometry(0.35, 24),
      new THREE.MeshBasicMaterial({
        color: 0x000000,
        transparent: true,
        opacity: 0.25,
        depthWrite: false,
      })
    )
    this.blobShadow.rotation.x = -Math.PI / 2
    this.blobShadow.position.y = 0.02
    this.blobShadow.renderOrder = -1
    this.playerGroup.add(this.blobShadow)

    this.audioSystem = new AudioSystem()
    this.statsEl = document.getElementById('stats')

    this.postFX = new PostProcessing(
      this.renderer,
      this.scene,
      this.camera,
      window.innerWidth,
      window.innerHeight
    )

    window.addEventListener('resize', () => {
      this.renderer.setSize(window.innerWidth, window.innerHeight)
      this.postFX.resize(window.innerWidth, window.innerHeight)
    })

    this.camera.position.set(0, 4, 6)
    this.camera.lookAt(0, 1.2, 0)

    this.setupControls()
    this.setupColorPicker()
    this.setupMinimap()
    this.setupLocationDetail()
    this.setupCitySelector()
    this.setupFriendsPanel()
    this.setupVisibilityPanel()
    this.setupDMPanel()
    this.connectToServer()
    this.fetchCities()
    this.animate()
  }

  private setupSky(): Sky {
    const sky = new Sky()
    sky.scale.setScalar(10000)
    this.scene.add(sky)

    const skyUniforms = sky.material.uniforms
    skyUniforms['turbidity'].value = 2.5
    skyUniforms['rayleigh'].value = 2.0
    skyUniforms['mieCoefficient'].value = 0.004
    skyUniforms['mieDirectionalG'].value = 0.88

    const sun = new THREE.Vector3()
    const phi = THREE.MathUtils.degToRad(88)
    const theta = THREE.MathUtils.degToRad(180)
    sun.setFromSphericalCoords(1, phi, theta)
    skyUniforms['sunPosition'].value.copy(sun)

    this.scene.background = new THREE.Color(0x87ceeb)
    this.scene.fog = new THREE.FogExp2(0xc8dce8, 0.0018)

    return sky
  }

  private addLights(): void {
    const hemi = new THREE.HemisphereLight(0x87ceeb, 0x3a7d44, 0.6)
    this.scene.add(hemi)

    const ambient = new THREE.AmbientLight(0x404050, 0.25)
    this.scene.add(ambient)

    this.sunLight = new THREE.DirectionalLight(0xfff4e5, 1.4)
    this.sunLight.position.set(30, 50, 20)
    this.sunLight.castShadow = true
    this.sunLight.shadow.mapSize.width = 4096
    this.sunLight.shadow.mapSize.height = 4096
    this.sunLight.shadow.camera.near = 0.3
    this.sunLight.shadow.camera.far = 250
    this.sunLight.shadow.camera.left = -80
    this.sunLight.shadow.camera.right = 80
    this.sunLight.shadow.camera.top = 80
    this.sunLight.shadow.camera.bottom = -80
    this.sunLight.shadow.bias = -0.0002
    this.sunLight.shadow.normalBias = 0.025
    this.sunLight.shadow.radius = 3
    this.scene.add(this.sunLight)

    const fillLight = new THREE.DirectionalLight(0x8899bb, 0.3)
    fillLight.position.set(-20, 30, -15)
    this.scene.add(fillLight)
  }

  // =========================================================================
  // Location Discovery
  // =========================================================================

  private async fetchNearbyLocations(): Promise<void> {
    const now = Date.now()
    if (now - this.lastLocationFetch < LOCATION_FETCH_INTERVAL) return
    this.lastLocationFetch = now

    try {
      const url = `${API_BASE}/api/locations/nearby?latitude=${this.playerLatitude}&longitude=${this.playerLongitude}&radius_meters=${LOCATION_FETCH_RADIUS}`
      const resp = await fetch(url)
      if (!resp.ok) return
      const locations: LocationData[] = await resp.json()
      this.updateLocationMarkers(locations)
    } catch (e) {
      console.warn('Failed to fetch locations:', e)
    }
  }

  private updateLocationMarkers(locations: LocationData[]): void {
    const seenIds = new Set(locations.map(l => l.id))
    for (const [id, marker] of this.locationMarkers) {
      if (!seenIds.has(id)) {
        this.scene.remove(marker.group)
        this.locationMarkers.delete(id)
      }
    }
    for (const loc of locations) {
      if (this.locationMarkers.has(loc.id)) {
        this.updateLocationLabel(this.locationMarkers.get(loc.id)!, loc)
        continue
      }
      this.createLocationMarker(loc)
    }
  }

  private createLocationMarker(loc: LocationData): void {
    const group = new THREE.Group()

    const pinGeom = new THREE.ConeGeometry(0.2, 1.5, 8)
    const pinMat = new THREE.MeshStandardMaterial({ color: 0xff4444, emissive: 0x440000 })
    const pin = new THREE.Mesh(pinGeom, pinMat)
    pin.position.y = 1.5
    pin.castShadow = true
    group.add(pin)

    const headGeom = new THREE.SphereGeometry(0.3, 16, 16)
    const headMat = new THREE.MeshStandardMaterial({ color: 0xff6666, emissive: 0x660000 })
    const head = new THREE.Mesh(headGeom, headMat)
    head.position.y = 2.6
    head.castShadow = true
    group.add(head)

    const beamGeom = new THREE.CylinderGeometry(0.03, 0.15, 4, 8)
    const beamMat = new THREE.MeshStandardMaterial({
      color: 0xff8888,
      transparent: true,
      opacity: 0.3,
      emissive: 0xff4444,
    })
    const beam = new THREE.Mesh(beamGeom, beamMat)
    beam.position.y = 2
    group.add(beam)

    const label = this.createLocationLabel(loc)
    group.add(label)

    const latOffset = (loc.latitude - this.playerLatitude) * 111320
    const lonOffset = (loc.longitude - this.playerLongitude) * 111320 * Math.cos(this.playerLatitude * Math.PI / 180)
    group.position.set(lonOffset / METERS_PER_UNIT, 0, -latOffset / METERS_PER_UNIT)

    this.scene.add(group)
    this.locationMarkers.set(loc.id, {
      id: loc.id, data: loc, group, pin, label, beam,
    })
  }

  private createLocationLabel(loc: LocationData): THREE.Sprite {
    const canvas = document.createElement('canvas')
    canvas.width = 512
    canvas.height = 128
    const ctx = canvas.getContext('2d')!

    ctx.fillStyle = 'rgba(0, 0, 0, 0.8)'
    ctx.beginPath()
    ctx.roundRect(0, 0, 512, 128, 12)
    ctx.fill()

    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 28px monospace'
    ctx.textAlign = 'center'
    ctx.fillText(loc.title, 256, 40)

    ctx.fillStyle = '#aaaaaa'
    ctx.font = '20px monospace'
    const creator = loc.creator_name || 'Unknown'
    const cats = loc.categories.map(c => c.name).join(', ')
    ctx.fillText(`${creator} \u2022 ${cats || 'Uncategorized'}`, 256, 75)

    const tags = loc.tags || []
    if (tags.length > 0) {
      ctx.fillStyle = '#aaddff'
      ctx.font = '16px monospace'
      ctx.fillText(tags.map(t => `#${t.name}`).join(' '), 256, 100)
    }

    ctx.fillStyle = '#88aaff'
    ctx.font = 'bold 18px monospace'
    const dist = loc.distance_meters < 1000
      ? `${Math.round(loc.distance_meters)}m`
      : `${(loc.distance_meters / 1000).toFixed(1)}km`
    ctx.fillText(dist, 256, tags.length > 0 ? 120 : 115)

    const texture = new THREE.CanvasTexture(canvas)
    texture.minFilter = THREE.LinearFilter
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true })
    const sprite = new THREE.Sprite(material)
    sprite.scale.set(4, 1, 1)
    sprite.position.y = 5
    return sprite
  }

  private updateLocationLabel(marker: LocationMarker, loc: LocationData): void {
    marker.data = loc
    marker.group.remove(marker.label)
    const newLabel = this.createLocationLabel(loc)
    marker.group.add(newLabel)
    marker.label = newLabel
  }

  private setupColorPicker(): void {
    const colors = ['#ff6b6b', '#4ecdc4', '#ffe66d', '#95e1d3', '#f38181', '#00ff88', '#88aaff', '#ff88ff']
    const container = document.getElementById('color-picker')
    if (!container) return

    colors.forEach(color => {
      const btn = document.createElement('button')
      btn.className = 'color-btn'
      btn.style.backgroundColor = color
      btn.style.width = '24px'
      btn.style.height = '24px'
      btn.style.border = color === this.playerColor ? '3px solid white' : '2px solid #555'
      btn.style.borderRadius = '50%'
      btn.style.cursor = 'pointer'
      btn.style.padding = '0'
      btn.onclick = () => {
        this.playerColor = color
        const shirtMat = this.playerMesh.torso.material as THREE.MeshStandardMaterial
        shirtMat.color.set(color)
        this.sendMessage({ type: 'set_avatar', color })
        container.querySelectorAll('.color-btn').forEach(b => {
          (b as HTMLElement).style.border = '2px solid #555'
        })
        btn.style.border = '3px solid white'
      }
      container.appendChild(btn)
    })

    setTimeout(() => {
      this.sendMessage({ type: 'set_avatar', color: this.playerColor })
    }, 1000)
  }

  private setupMinimap(): void {
    const minimapDiv = document.getElementById('minimap')
    if (!minimapDiv) return
    this.minimapCanvas = document.createElement('canvas')
    this.minimapCanvas.width = this.minimapSize * 2
    this.minimapCanvas.height = this.minimapSize * 2
    this.minimapCanvas.style.width = '100%'
    this.minimapCanvas.style.height = '100%'
    this.minimapCtx = this.minimapCanvas.getContext('2d')!
    minimapDiv.appendChild(this.minimapCanvas)
  }

  private updateMinimap(): void {
    if (!this.minimapCtx || !this.minimapCanvas) return
    const ctx = this.minimapCtx
    const size = this.minimapSize
    const center = size

    ctx.clearRect(0, 0, size * 2, size * 2)
    ctx.beginPath()
    ctx.arc(center, center, center, 0, Math.PI * 2)
    ctx.clip()

    ctx.fillStyle = 'rgba(10, 20, 10, 0.8)'
    ctx.fillRect(0, 0, size * 2, size * 2)

    const scale = 0.5
    const px = center
    const py = center

    ctx.fillStyle = '#00ff88'
    ctx.beginPath()
    ctx.arc(px, py, 6, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 2
    ctx.stroke()

    ctx.fillStyle = '#ffffff'
    ctx.font = 'bold 10px monospace'
    ctx.textAlign = 'center'
    ctx.fillText('YOU', px, py + 18)

    this.locationMarkers.forEach((marker) => {
      const dx = (marker.group.position.x - this.playerGroup.position.x) * scale
      const dz = (marker.group.position.z - this.playerGroup.position.z) * scale
      const dist = Math.sqrt(dx * dx + dz * dz)
      if (dist > center - 10) return

      ctx.fillStyle = '#ff4444'
      ctx.beginPath()
      ctx.arc(px + dx, py - dz, 4, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 1
      ctx.stroke()
    })

    this.remotePlayers.forEach((player) => {
      const dx = (player.position.x - this.playerGroup.position.x) * scale
      const dz = (player.position.z - this.playerGroup.position.z) * scale
      const dist = Math.sqrt(dx * dx + dz * dz)
      if (dist > center - 10) return

      ctx.fillStyle = player.color || '#ff6b6b'
      ctx.beginPath()
      ctx.arc(px + dx, py - dz, 4, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 1
      ctx.stroke()
    })

    ctx.strokeStyle = 'rgba(0, 255, 136, 0.4)'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(center, center, center - 2, 0, Math.PI * 2)
    ctx.stroke()

    const coordEl = document.getElementById('coordinates')
    if (coordEl) {
      const lat = this.playerLatitude.toFixed(4)
      const lon = Math.abs(this.playerLongitude).toFixed(4)
      const dir = this.playerLongitude < 0 ? 'W' : 'E'
      coordEl.textContent = `${lat}\u00B0N, ${lon}\u00B0${dir}`
    }

    this.checkNearbyLocation()
  }

  private setupLocationDetail(): void {
    const closeBtn = document.getElementById('location-detail-close')
    if (closeBtn) {
      closeBtn.onclick = () => this.hideLocationDetail()
    }

    const teleportBtn = document.getElementById('btn-teleport')
    if (teleportBtn) {
      teleportBtn.onclick = () => {
        if (!this.selectedLocation) return
        const loc = this.selectedLocation.data
        this.teleportTo(loc.latitude, loc.longitude)
        this.hideLocationDetail()
      }
    }

    const loadModelBtn = document.getElementById('btn-load-model')
    if (loadModelBtn) {
      loadModelBtn.onclick = async () => {
        if (!this.selectedLocation) return
        const loc = this.selectedLocation.data
        if (this.capturedModels.has(loc.id)) {
          this.scene.remove(this.capturedModels.get(loc.id)!)
          this.capturedModels.delete(loc.id)
          return
        }
        const model = await this.environment.loadCapturedModel(
          loc.id, loc.latitude, loc.longitude,
          this.playerLatitude, this.playerLongitude
        )
        if (model) this.capturedModels.set(loc.id, model)
      }
    }
  }

  // =========================================================================
  // City Selector
  // =========================================================================

  private async fetchCities(): Promise<void> {
    try {
      const resp = await fetch(`${API_BASE}/api/locations/cities/list`)
      if (resp.ok) {
        this.cities = await resp.json()
      }
    } catch (e) {
      console.warn('Failed to fetch cities:', e)
      // Fallback cities
      this.cities = [
        { id: 'nyc', name: 'New York City', country: 'USA', lat: 40.785, lon: -73.968, description: 'Central Park & Manhattan' },
        { id: 'paris', name: 'Paris', country: 'France', lat: 48.8566, lon: 2.3522, description: 'Eiffel Tower & Champs-Élysées' },
        { id: 'tokyo', name: 'Tokyo', country: 'Japan', lat: 35.6762, lon: 139.6503, description: 'Shibuya & Tokyo Tower' },
        { id: 'london', name: 'London', country: 'UK', lat: 51.5074, lon: -0.1278, description: 'Big Ben & Westminster' },
        { id: 'dubai', name: 'Dubai', country: 'UAE', lat: 25.2048, lon: 55.2708, description: 'Burj Khalifa & Marina' },
        { id: 'sydney', name: 'Sydney', country: 'Australia', lat: -33.8688, lon: 151.2093, description: 'Opera House & Harbour Bridge' },
        { id: 'rio', name: 'Rio de Janeiro', country: 'Brazil', lat: -22.9068, lon: -43.1729, description: 'Christ the Redeemer' },
        { id: 'mumbai', name: 'Mumbai', country: 'India', lat: 19.0760, lon: 72.8777, description: 'Gateway of India' },
      ]
    }
    this.renderCityGrid()
  }

  private renderCityGrid(): void {
    const grid = document.getElementById('city-grid')
    if (!grid) return
    grid.innerHTML = this.cities.map(city => `
      <div class="city-card ${this.currentCity?.id === city.id ? 'active' : ''}" data-city-id="${city.id}">
        <div class="city-name">${city.name}</div>
        <div class="city-country">${city.country}</div>
        <div class="city-desc">${city.description}</div>
      </div>
    `).join('')

    grid.querySelectorAll('.city-card').forEach(card => {
      card.addEventListener('click', () => {
        const cityId = card.getAttribute('data-city-id')
        const city = this.cities.find(c => c.id === cityId)
        if (city) this.teleportToCity(city)
      })
    })
  }

  private setupCitySelector(): void {
    const btn = document.getElementById('btn-cities')
    const panel = document.getElementById('city-selector')
    const closeBtn = document.getElementById('city-close')

    if (btn && panel) {
      btn.onclick = () => {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none'
        this.renderCityGrid()
      }
    }
    if (closeBtn && panel) {
      closeBtn.onclick = () => { panel.style.display = 'none' }
    }
  }

  private async teleportToCity(city: CityData): Promise<void> {
    this.currentCity = city
    this.playerLatitude = city.lat
    this.playerLongitude = city.lon

    // Reset player position to origin
    this.playerGroup.position.set(0, 0, 0)

    // Reload OSM buildings for new location
    await this.environment.reloadOSMBuildings(city.lat, city.lon)

    // Re-fetch nearby locations
    this.lastLocationFetch = 0
    await this.fetchNearbyLocations()

    // Close city selector
    const panel = document.getElementById('city-selector')
    if (panel) panel.style.display = 'none'

    // Update coordinates display
    const coordEl = document.getElementById('coordinates')
    if (coordEl) {
      const lat = city.lat.toFixed(4)
      const lon = Math.abs(city.lon).toFixed(4)
      const dir = city.lon < 0 ? 'W' : 'E'
      coordEl.textContent = `${lat}\u00B0N, ${lon}\u00B0${dir} — ${city.name}`
    }

    console.log(`Teleported to ${city.name}`)
  }

  private teleportTo(lat: number, lon: number): void {
    this.playerLatitude = lat
    this.playerLongitude = lon
    this.playerGroup.position.set(0, 0, 0)

    // Reload OSM buildings
    this.environment.reloadOSMBuildings(lat, lon)

    // Re-fetch nearby locations
    this.lastLocationFetch = 0
    this.fetchNearbyLocations()
  }

  // =========================================================================
  // Friends Panel
  // =========================================================================

  private setupFriendsPanel(): void {
    const btn = document.getElementById('btn-friends')
    const panel = document.getElementById('friends-panel')
    const searchInput = document.getElementById('friend-search') as HTMLInputElement

    if (btn && panel) {
      btn.onclick = () => {
        const isVisible = panel.style.display !== 'none'
        panel.style.display = isVisible ? 'none' : 'block'
        if (!isVisible) this.fetchFriends()
      }
    }

    if (searchInput) {
      let searchTimeout: ReturnType<typeof setTimeout>
      searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout)
        searchTimeout = setTimeout(() => this.searchUsers(searchInput.value), 300)
      })
    }

    // Keyboard shortcut
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Tab' && !e.shiftKey) {
        e.preventDefault()
        if (panel) {
          panel.style.display = panel.style.display === 'none' ? 'block' : 'none'
          if (panel.style.display === 'block') this.fetchFriends()
        }
      }
    })
  }

  private async fetchFriends(): Promise<void> {
    try {
      const resp = await fetch(`${API_BASE}/api/friends/?user_id=${USER_ID}`)
      if (resp.ok) {
        this.friends = await resp.json()
        this.renderFriendsList()
      }
    } catch (e) {
      console.warn('Failed to fetch friends:', e)
    }
  }

  private async searchUsers(query: string): Promise<void> {
    if (!query || query.length < 1) {
      this.renderFriendsList()
      return
    }
    try {
      const resp = await fetch(`${API_BASE}/api/friends/search?q=${encodeURIComponent(query)}&user_id=${USER_ID}`)
      if (resp.ok) {
        const users = await resp.json()
        this.renderSearchResults(users)
      }
    } catch (e) {
      console.warn('Failed to search users:', e)
    }
  }

  private renderFriendsList(): void {
    const container = document.getElementById('friends-list')
    if (!container) return

    if (this.friends.length === 0) {
      container.innerHTML = '<div style="color:#666;font-size:11px;text-align:center;padding:10px;">No friends yet. Search above to add.</div>'
      return
    }

    container.innerHTML = this.friends.map(f => `
      <div class="friend-item">
        <div class="friend-info">
          <span class="friend-dot online"></span>
          <span class="friend-name">${f.display_name || f.username}</span>
        </div>
        <button class="friend-btn" data-action="dm" data-username="${f.username}">Message</button>
      </div>
    `).join('')

    container.querySelectorAll('.friend-btn[data-action="dm"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const username = btn.getAttribute('data-username') || ''
        this.openDM(username)
      })
    })
  }

  private renderSearchResults(users: any[]): void {
    const container = document.getElementById('friends-list')
    if (!container) return

    if (users.length === 0) {
      container.innerHTML = '<div style="color:#666;font-size:11px;text-align:center;padding:10px;">No users found.</div>'
      return
    }

    container.innerHTML = users.map(u => `
      <div class="friend-item">
        <div class="friend-info">
          <span class="friend-dot offline"></span>
          <span class="friend-name">${u.display_name || u.username}</span>
        </div>
        <button class="friend-btn" data-action="add" data-user-id="${u.id}">Add</button>
      </div>
    `).join('')

    container.querySelectorAll('.friend-btn[data-action="add"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const userId = parseInt(btn.getAttribute('data-user-id') || '0')
        if (userId) await this.sendFriendRequest(userId)
      })
    })
  }

  private async sendFriendRequest(targetUserId: number): Promise<void> {
    try {
      await fetch(`${API_BASE}/api/friends/request?user_id=${USER_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ addressee_id: targetUserId }),
      })
      this.fetchFriends()
    } catch (e) {
      console.warn('Failed to send friend request:', e)
    }
  }

  // =========================================================================
  // Visibility Panel
  // =========================================================================

  private setupVisibilityPanel(): void {
    const btn = document.getElementById('btn-visibility')
    const panel = document.getElementById('visibility-panel')

    if (btn && panel) {
      btn.onclick = () => {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none'
      }
    }

    // Keyboard shortcut
    window.addEventListener('keydown', (e) => {
      if (e.key === 'v' || e.key === 'V') {
        if (panel) {
          panel.style.display = panel.style.display === 'none' ? 'block' : 'none'
        }
      }
    })

    // Visibility option clicks
    if (panel) {
      panel.querySelectorAll('.vis-option').forEach(opt => {
        opt.addEventListener('click', () => {
          const vis = opt.getAttribute('data-vis')
          if (vis) this.setVisibility(vis)
        })
      })
    }
  }

  private setVisibility(visibility: string): void {
    this.currentVisibility = visibility
    this.sendMessage({ type: 'set_visibility', visibility })

    // Update UI
    const panel = document.getElementById('visibility-panel')
    if (panel) {
      panel.querySelectorAll('.vis-option').forEach(opt => {
        opt.classList.toggle('active', opt.getAttribute('data-vis') === visibility)
      })
    }
  }

  // =========================================================================
  // DM Panel
  // =========================================================================

  private setupDMPanel(): void {
    const closeBtn = document.getElementById('dm-close')
    const input = document.getElementById('dm-input') as HTMLInputElement

    if (closeBtn) {
      closeBtn.onclick = () => {
        const panel = document.getElementById('dm-panel')
        if (panel) panel.style.display = 'none'
        this.dmTarget = ''
      }
    }

    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && this.dmTarget) {
          this.sendDM(input.value.trim())
          input.value = ''
        }
      })
    }
  }

  private openDM(username: string): void {
    this.dmTarget = username
    const panel = document.getElementById('dm-panel')
    const nameEl = document.getElementById('dm-target-name')
    const messagesEl = document.getElementById('dm-messages')

    if (nameEl) nameEl.textContent = `DM — ${username}`
    if (messagesEl) messagesEl.innerHTML = ''
    if (panel) panel.style.display = 'block'
  }

  private sendDM(message: string): void {
    if (!message || !this.dmTarget) return
    this.sendMessage({ type: 'dm', to: this.dmTarget, message })

    // Show in DM panel
    const messagesEl = document.getElementById('dm-messages')
    if (messagesEl) {
      messagesEl.innerHTML += `<div><strong>You:</strong> ${message.replace(/</g, '&lt;')}</div>`
      messagesEl.scrollTop = messagesEl.scrollHeight
    }
  }

  private checkNearbyLocation(): void {
    const NEARBY_THRESHOLD = 10
    let closest: LocationMarker | null = null
    let closestDist = Infinity

    this.locationMarkers.forEach((marker) => {
      const dist = this.playerGroup.position.distanceTo(marker.group.position)
      if (dist < NEARBY_THRESHOLD && dist < closestDist) {
        closest = marker
        closestDist = dist
      }
    })

    if (closest && closest !== this.selectedLocation) {
      this.showLocationDetail(closest)
    } else if (!closest && this.selectedLocation) {
      this.hideLocationDetail()
    }
  }

  private showLocationDetail(marker: LocationMarker): void {
    this.selectedLocation = marker
    const panel = document.getElementById('location-detail')
    const content = document.getElementById('location-detail-content')
    if (!panel || !content) return

    const loc = marker.data
    const dist = loc.distance_meters < 1000
      ? `${Math.round(loc.distance_meters)}m`
      : `${(loc.distance_meters / 1000).toFixed(1)}km`
    const cats = loc.categories.map(c => c.name).join(', ') || 'Uncategorized'
    const tags = (loc.tags || []).map(t => `#${t.name}`).join(' ')
    const created = loc.created_at ? new Date(loc.created_at).toLocaleDateString() : 'Unknown'

    const accuracyText = loc.accuracy_meters
      ? `<span class="loc-accuracy">\u00B1${Math.round(loc.accuracy_meters)}m</span>` : ''
    const confidenceText = loc.confidence != null
      ? `<span class="loc-confidence">Confidence: ${Math.round(loc.confidence * 100)}%</span>` : ''
    const qualityLabel = loc.confidence != null
      ? loc.confidence >= 0.8 ? 'HIGH' : loc.confidence >= 0.5 ? 'MEDIUM' : 'LOW' : ''
    const qualityClass = qualityLabel === 'HIGH' ? 'quality-high'
      : qualityLabel === 'MEDIUM' ? 'quality-medium'
      : qualityLabel === 'LOW' ? 'quality-low' : ''
    const qualityText = qualityLabel
      ? `<span class="loc-quality ${qualityClass}">${qualityLabel}</span>` : ''

    content.innerHTML = `
      <div class="loc-title">${loc.title}</div>
      <div class="loc-creator">by ${loc.creator_name || 'Unknown'} \u2022 ${dist}</div>
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
    panel.style.display = 'block'
  }

  private hideLocationDetail(): void {
    this.selectedLocation = null
    const panel = document.getElementById('location-detail')
    if (panel) panel.style.display = 'none'
  }

  private connectToServer(): void {
    const worldId = 1
    this.ws = new WebSocket(`${WS_BASE}/${this.username}/${worldId}`)

    this.ws.onopen = () => {
      console.log('Connected to server')
      document.getElementById('status')!.textContent = `Connected as ${this.username}`
    }

    this.ws.onmessage = (event) => {
      try {
        this.handleMessage(JSON.parse(event.data))
      } catch (e) {
        console.error('Failed to parse message:', e)
      }
    }

    this.ws.onclose = () => {
      document.getElementById('status')!.textContent = 'Disconnected - Reconnecting...'
      setTimeout(() => this.connectToServer(), 3000)
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  private handleMessage(data: any): void {
    switch (data.type) {
      case 'player_join':
        if (data.player?.id) {
          this.addRemotePlayer(data.player)
          this.updatePlayerCount(data.player_count)
        }
        break
      case 'player_leave':
        if (data.player_id) {
          this.removeRemotePlayer(data.player_id)
          this.updatePlayerCount(data.player_count)
        }
        break
      case 'player_move':
        if (data.player_id && data.position) {
          this.updateRemotePlayer(
            data.player_id, data.position, data.rotation || 0,
            data.velocity, data.server_tick, data.color
          )
        }
        break
      case 'position_correction':
        if (data.position) {
          this.playerGroup.position.set(
            data.position.x || 0,
            data.position.y || 0,
            data.position.z || 0
          )
        }
        break
      case 'chat':
        if (data.username && data.message) {
          this.addChatMessage(data.username, data.message)
        }
        break
      case 'dm_msg':
        if (data.username && data.message) {
          if (data.to) {
            // This is our sent DM confirmation
            return
          }
          // Incoming DM
          const messagesEl = document.getElementById('dm-messages')
          if (messagesEl) {
            messagesEl.innerHTML += `<div><strong>${data.username}:</strong> ${data.message.replace(/</g, '&lt;')}</div>`
            messagesEl.scrollTop = messagesEl.scrollHeight
          }
          // Also open DM panel if closed
          if (!this.dmTarget) this.openDM(data.username)
        }
        break
      case 'visibility_changed':
        if (data.visibility) {
          this.currentVisibility = data.visibility
        }
        break
      case 'ping':
        this.sendMessage({ type: 'pong' })
        break
    }
  }

  private addRemotePlayer(data: { id: number; username: string; position: any; color?: string; visibility?: string }): void {
    if (this.remotePlayers.has(data.id)) return

    const color = data.color || '#ff6b6b'
    const player = createArticulatedPlayer(0xffdbac, color)
    const pos = data.position || { x: 0, y: 0, z: 0 }
    player.group.position.set(pos.x || 0, pos.y || 0, pos.z || 0)

    const label = createLabel(data.username, color, data.visibility || 'public')
    player.group.add(label)

    this.scene.add(player.group)

    this.remotePlayers.set(data.id, {
      id: data.id,
      username: data.username,
      position: player.group.position.clone(),
      rotation: 0,
      mesh: player.group,
      label,
      color,
      visibility: data.visibility || 'public',
      targetPosition: player.group.position.clone(),
      targetRotation: 0,
      velocity: new THREE.Vector3(),
      lastUpdate: Date.now(),
      animState: 'idle',
      animTime: 0,
      baseY: 0,
      player,
    })
  }

  private removeRemotePlayer(playerId: number): void {
    const player = this.remotePlayers.get(playerId)
    if (player) {
      this.scene.remove(player.mesh)
      this.remotePlayers.delete(playerId)
    }
  }

  private updateRemotePlayer(
    playerId: number,
    position: { x: number; y: number; z: number },
    rotation: number,
    velocity?: { x: number; y: number; z: number },
    _serverTick?: number,
    color?: string
  ): void {
    const player = this.remotePlayers.get(playerId)
    if (player) {
      player.targetPosition.set(position.x || 0, position.y || 0, position.z || 0)
      player.targetRotation = rotation
      if (velocity) player.velocity.set(velocity.x || 0, velocity.y || 0, velocity.z || 0)
      if (color && color !== player.color) {
        player.color = color
        const shirtMat = player.player.torso.material as THREE.MeshStandardMaterial
        shirtMat.color.set(color)
      }
      player.lastUpdate = Date.now()
    }
  }

  private updatePlayerCount(count: number): void {
    document.getElementById('player-count')!.textContent = `Players: ${count}`
    this.updatePlayerList()
  }

  private updatePlayerList(): void {
    const container = document.getElementById('player-list-content')
    if (!container) return
    const items: string[] = []
    items.push(`<div class="player-list-item">
      <span class="player-dot" style="background: ${this.playerColor}"></span>
      <span class="player-name">${this.username} (you)</span>
    </div>`)
    this.remotePlayers.forEach((player) => {
      items.push(`<div class="player-list-item">
        <span class="player-dot" style="background: ${player.color}"></span>
        <span class="player-name">${player.username}</span>
      </div>`)
    })
    container.innerHTML = items.join('')
  }

  private addChatMessage(username: string, message: string): void {
    this.chatMessages.push({ username, message })
    if (this.chatMessages.length > 20) this.chatMessages.shift()
    const chatDiv = document.getElementById('chat-messages')!
    chatDiv.innerHTML = this.chatMessages
      .map((m) => {
        const escaped = m.message.replace(/</g, '&lt;').replace(/>/g, '&gt;')
        const escapedName = m.username.replace(/</g, '&lt;').replace(/>/g, '&gt;')
        return `<div><strong>${escapedName}:</strong> ${escaped}</div>`
      })
      .join('')
    chatDiv.scrollTop = chatDiv.scrollHeight
  }

  private sendChat(): void {
    const input = document.getElementById('chat-input') as HTMLInputElement
    if (input.value.trim() && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'chat', message: input.value.trim() }))
      input.value = ''
    }
  }

  private sendMessage(data: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  private setupControls(): void {
    window.addEventListener('keydown', (e) => {
      this.keys.add(e.key.toLowerCase())
      if (e.key === 'Enter') this.sendChat()
      if (e.key === 'm' || e.key === 'M') {
        const minimap = document.getElementById('minimap')
        if (minimap) {
          minimap.style.display = minimap.style.display === 'none' ? 'block' : 'none'
        }
      }
    })
    window.addEventListener('keyup', (e) => this.keys.delete(e.key.toLowerCase()))
  }

  private updatePlayer(deltaTime: number): void {
    const speed = 0.08
    const direction = new THREE.Vector3()

    if (this.keys.has('w') || this.keys.has('arrowup')) direction.z -= 1
    if (this.keys.has('s') || this.keys.has('arrowdown')) direction.z += 1
    if (this.keys.has('a') || this.keys.has('arrowleft')) direction.x -= 1
    if (this.keys.has('d') || this.keys.has('arrowright')) direction.x += 1

    if (direction.length() > 0) {
      direction.normalize().multiplyScalar(speed)
      this.playerGroup.position.add(direction)

      const angle = Math.atan2(direction.x, direction.z)
      this.playerGroup.rotation.y = angle

      this.playerLatitude += (direction.z * METERS_PER_UNIT) / 111320
      this.playerLongitude += (direction.x * METERS_PER_UNIT) / (111320 * Math.cos(this.playerLatitude * Math.PI / 180))

      this.sendMessage({
        type: 'position_update',
        position: {
          x: this.playerGroup.position.x,
          y: this.playerGroup.position.y,
          z: this.playerGroup.position.z,
        },
        rotation: this.playerGroup.rotation.y,
      })
    }

    const terrainY = this.environment.getTerrainHeight(
      this.playerGroup.position.x,
      this.playerGroup.position.z
    )
    this.playerGroup.position.y += (terrainY - this.playerGroup.position.y) * 0.2

    const isMoving = direction.length() > 0
    const speedLen = isMoving ? 3.5 : 0
    const animState = speedLen > 3 ? 'run' : speedLen > 0.3 ? 'walk' : 'idle'
    animatePlayer(this.playerMesh, performance.now() / 1000, animState, deltaTime)

    this.cameraCtrl.update(this.playerGroup.position, deltaTime)

    if (this.sunLight) {
      this.sunLight.position.set(
        this.playerGroup.position.x + 30,
        50,
        this.playerGroup.position.z + 20
      )
      this.sunLight.target.position.copy(this.playerGroup.position)
    }
  }

  private interpolateRemotePlayers(deltaTime: number): void {
    const INTERPOLATION_SPEED = 10.0
    const MAX_INTERPOLATION = 0.3

    this.remotePlayers.forEach((rp) => {
      const diff = new THREE.Vector3().subVectors(rp.targetPosition, rp.position)
      const distance = diff.length()

      if (distance > 0.001) {
        const maxMove = INTERPOLATION_SPEED * deltaTime
        const moveAmount = Math.min(distance, maxMove, MAX_INTERPOLATION)
        if (distance > 0) {
          diff.normalize().multiplyScalar(moveAmount)
          rp.position.add(diff)
        }
      }

      const timeSinceUpdate = (Date.now() - rp.lastUpdate) / 1000
      if (timeSinceUpdate > 0.1 && rp.velocity.length() > 0.01) {
        rp.position.add(rp.velocity.clone().multiplyScalar(deltaTime * 0.5))
      }

      const rotationDiff = rp.targetRotation - rp.mesh.rotation.y
      if (Math.abs(rotationDiff) > 0.01) {
        rp.mesh.rotation.y += rotationDiff * Math.min(1, deltaTime * 10)
      }

      const speed = rp.velocity.length()
      const prevAnimState = rp.animState
      if (speed > 3.0) rp.animState = 'run'
      else if (speed > 0.3) rp.animState = 'walk'
      else rp.animState = 'idle'

      if (rp.animState !== prevAnimState) rp.animTime = 0
      rp.animTime += deltaTime

      animatePlayer(rp.player, rp.animTime, rp.animState, deltaTime)

      rp.mesh.position.copy(rp.position)
      rp.mesh.position.y = rp.baseY
    })
  }

  private animate(): void {
    requestAnimationFrame(() => this.animate())

    const now = Date.now()
    const deltaTime = Math.min((now - this.lastFrameTime) / 1000, 0.1)
    this.lastFrameTime = now

    this.updatePlayer(deltaTime)
    this.interpolateRemotePlayers(deltaTime)
    this.fetchNearbyLocations()
    this.updateMinimap()
    this.updateDayNight(deltaTime)
    this.updateBlobShadow()
    this.updateStats()
    this.environment.updateLOD()

    const time = now / 1000
    this.environment.updateGrass(time)
    this.environment.updateWater(time, this.renderer)
    this.environment.updateParticles(time, deltaTime)
    this.environment.setPlayerPosition(
      this.playerGroup.position.x,
      this.playerGroup.position.z
    )

    this.postFX.render()

    this.renderer.info.reset()
  }

  private updateDayNight(deltaTime: number): void {
    this.timeOfDay = (this.timeOfDay + deltaTime * this.dayNightSpeed * 60) % 24

    const sunAngle = ((this.timeOfDay - 6) / 12) * Math.PI
    const sunHeight = Math.sin(sunAngle)
    const isDay = sunHeight > -0.1

    if (this.sunLight) {
      const baseX = this.playerGroup.position.x + 30
      const baseZ = this.playerGroup.position.z + 20
      this.sunLight.position.set(
        baseX + Math.cos(sunAngle) * 40,
        Math.max(sunHeight * 50, 2),
        baseZ
      )
      this.sunLight.target.position.copy(this.playerGroup.position)

      const dayIntensity = THREE.MathUtils.clamp(sunHeight * 2.2 + 0.15, 0.05, 1.5)
      this.sunLight.intensity = dayIntensity

      const sunColorT = THREE.MathUtils.clamp(sunHeight, 0, 1)
      this.sunLight.color.setRGB(
        THREE.MathUtils.lerp(1.0, 1.0, sunColorT),
        THREE.MathUtils.lerp(0.55, 0.95, sunColorT),
        THREE.MathUtils.lerp(0.25, 0.88, sunColorT)
      )
    }

    const skyUniforms = this.sky.material.uniforms
    const turbidity = isDay ? 2.5 : 18
    const rayleigh = isDay ? 2.0 : 0.08
    skyUniforms['turbidity'].value = THREE.MathUtils.lerp(
      skyUniforms['turbidity'].value, turbidity, deltaTime * 0.5
    )
    skyUniforms['rayleigh'].value = THREE.MathUtils.lerp(
      skyUniforms['rayleigh'].value, rayleigh, deltaTime * 0.5
    )

    const skyAngle = ((this.timeOfDay - 6) / 12) * Math.PI
    const sunPos = new THREE.Vector3()
    sunPos.setFromSphericalCoords(1, Math.PI / 2 - skyAngle, 0)
    skyUniforms['sunPosition'].value.copy(sunPos)

    const dayFogColor = new THREE.Color(0xc8dce8)
    const nightFogColor = new THREE.Color(0x080818)
    const dawnFogColor = new THREE.Color(0xd4a574)
    const duskFogColor = new THREE.Color(0xc08050)
    let targetFogColor: THREE.Color
    if (sunHeight > 0.25) {
      targetFogColor = dayFogColor
    } else if (sunHeight > 0.0) {
      targetFogColor = new THREE.Color().copy(dawnFogColor).lerp(dayFogColor, sunHeight / 0.25)
    } else if (sunHeight > -0.1) {
      targetFogColor = new THREE.Color().copy(duskFogColor).lerp(dawnFogColor, (sunHeight + 0.1) / 0.1)
    } else {
      targetFogColor = nightFogColor
    }
    if (this.scene.fog instanceof THREE.FogExp2) {
      this.scene.fog.color.lerp(targetFogColor, deltaTime * 0.5)
    }
    if (this.scene.background instanceof THREE.Color) {
      this.scene.background.lerp(targetFogColor, deltaTime * 0.5)
    }
  }

  private updateBlobShadow(): void {
    if (!this.blobShadow) return
    const ty = this.environment.getTerrainHeight(
      this.playerGroup.position.x,
      this.playerGroup.position.z
    )
    this.blobShadow.position.y = ty + 0.02 - this.playerGroup.position.y
  }

  private updateStats(): void {
    if (!this.statsEl) return
    this.fpsFrames++
    const elapsed = performance.now() - this.fpsLastTime
    if (elapsed >= 1000) {
      const fps = Math.round((this.fpsFrames * 1000) / elapsed)
      this.fpsFrames = 0
      this.fpsLastTime = performance.now()
      const info = this.renderer.info
      const drawCalls = info.render.calls
      const triangles = info.render.triangles
      const textures = info.memory.textures
      const geometries = info.memory.geometries
      const visible = info.render.frame
      this.statsEl.textContent =
        `FPS: ${fps} | DC: ${drawCalls} | Tri: ${triangles.toLocaleString()} | Tex: ${textures} | Geo: ${geometries}`
    }
  }
}

const game = new MultiplayerGame()
