import * as THREE from 'three'

const OVERPASS_URL = 'https://overpass-api.de/api/interpreter'

interface OSMWay {
  id: number
  nodes: number[]
  tags: Record<string, string>
}

interface OSMNode {
  id: number
  lat: number
  lon: number
}

interface OSMResponse {
  elements: Array<{
    type: string
    id: number
    lat?: number
    lon?: number
    nodes?: number[]
    tags?: Record<string, string>
  }>
}

export class OSMBuildingLoader {
  private nodeCache: Map<number, OSMNode> = new Map()
  private centerLat: number
  private centerLon: number
  private latToMeter: number
  private lonToMeter: number

  constructor(centerLat: number, centerLon: number) {
    this.centerLat = centerLat
    this.centerLon = centerLon
    this.latToMeter = 111132.92
    this.lonToMeter = 111132.92 * Math.cos(centerLat * Math.PI / 180)
  }

  latLonToLocal(lat: number, lon: number): { x: number; z: number } {
    return {
      x: (lon - this.centerLon) * this.lonToMeter,
      z: -(lat - this.centerLat) * this.latToMeter,
    }
  }

  async fetchBuildings(
    south: number, west: number, north: number, east: number
  ): Promise<THREE.Group> {
    const group = new THREE.Group()
    group.name = 'osm-buildings'

    const query = `
      [out:json][timeout:30];
      (
        way["building"](${south},${west},${north},${east});
        relation["building"](${south},${west},${north},${east});
      );
      out body;
      >;
      out skel qt;
    `.trim()

    try {
      const resp = await fetch(OVERPASS_URL, {
        method: 'POST',
        body: `data=${encodeURIComponent(query)}`,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })

      if (!resp.ok) {
        console.warn(`Overpass API returned ${resp.status}`)
        return group
      }

      const data: OSMResponse = await resp.json()
      return this.parseResponse(data, group)
    } catch (e) {
      console.warn('Failed to fetch OSM buildings:', e)
      return group
    }
  }

  private parseResponse(data: OSMResponse, group: THREE.Group): THREE.Group {
    this.nodeCache.clear()

    for (const el of data.elements) {
      if (el.type === 'node' && el.lat !== undefined && el.lon !== undefined) {
        this.nodeCache.set(el.id, { id: el.id, lat: el.lat, lon: el.lon })
      }
    }

    const palettes = [
      { wall: 0xd4c5a9, window: 0x88aacc, trim: 0xbba888 },
      { wall: 0x8c9eaf, window: 0x6688aa, trim: 0x7788aa },
      { wall: 0xc4b8a8, window: 0x7799bb, trim: 0xaa9977 },
      { wall: 0xa8b8c8, window: 0x5588aa, trim: 0x8899aa },
      { wall: 0xbaa88a, window: 0x889966, trim: 0x998866 },
      { wall: 0xe0d8c8, window: 0x99aacc, trim: 0xccbbaa },
      { wall: 0x7a8a9a, window: 0x5577aa, trim: 0x667799 },
      { wall: 0xc8bca8, window: 0x778899, trim: 0xbbaa88 },
    ]

    let buildingCount = 0

    for (const el of data.elements) {
      if (el.type === 'way' && el.nodes && el.tags?.building) {
        const footprint = this.getFootprint(el.nodes)
        if (!footprint || footprint.length < 3) continue

        const height = this.getBuildingHeight(el.tags)
        const palette = palettes[buildingCount % palettes.length]
        this.buildExtrudedBuilding(group, footprint, height, palette, el.tags)
        buildingCount++
      }
    }

    console.log(`Loaded ${buildingCount} OSM buildings`)
    return group
  }

  private getFootprint(nodeIds: number[]): THREE.Vector2[] | null {
    const points: THREE.Vector2[] = []
    for (const nid of nodeIds) {
      const node = this.nodeCache.get(nid)
      if (!node) return null
      const local = this.latLonToLocal(node.lat, node.lon)
      points.push(new THREE.Vector2(local.x, local.z))
    }
    return points
  }

  private getBuildingHeight(tags: Record<string, string>): number {
    if (tags.height) {
      const h = parseFloat(tags.height)
      if (!isNaN(h)) return Math.min(h, 200)
    }
    if (tags['building:height']) {
      const h = parseFloat(tags['building:height'])
      if (!isNaN(h)) return Math.min(h, 200)
    }
    if (tags['building:levels']) {
      const levels = parseInt(tags['building:levels'])
      if (!isNaN(levels)) return levels * 3.2
    }
    if (tags['building:min_level'] && tags['building:levels']) {
      const max = parseInt(tags['building:levels'])
      if (!isNaN(max)) return max * 3.2
    }

    const type = tags.building || ''
    if (type === 'skyscraper' || type === 'tower') return 60 + Math.random() * 40
    if (type === 'highrise') return 30 + Math.random() * 30
    if (type === 'apartments' || type === 'residential') return 10 + Math.random() * 15
    if (type === 'commercial' || type === 'office') return 12 + Math.random() * 20
    if (type === 'industrial') return 6 + Math.random() * 6
    if (type === 'retail' || type === 'shop') return 4 + Math.random() * 4
    if (type === 'house' || type === 'detached') return 6 + Math.random() * 4
    if (type === 'garage' || type === 'garages') return 3 + Math.random() * 2
    if (type === 'shed') return 2 + Math.random() * 1.5

    return 5 + Math.random() * 15
  }

  private buildExtrudedBuilding(
    group: THREE.Group,
    footprint: THREE.Vector2[],
    totalHeight: number,
    palette: { wall: number; window: number; trim: number },
    tags: Record<string, string>
  ): void {
    const wallMat = new THREE.MeshStandardMaterial({
      color: palette.wall,
      roughness: 0.85,
      metalness: 0.02,
    })

    const shape = new THREE.Shape()
    shape.moveTo(footprint[0].x, footprint[0].y)
    for (let i = 1; i < footprint.length; i++) {
      shape.lineTo(footprint[i].x, footprint[i].y)
    }
    shape.closePath()

    const extrudeSettings = {
      depth: totalHeight,
      bevelEnabled: false,
    }

    const geo = new THREE.ExtrudeGeometry(shape, extrudeSettings)
    geo.rotateX(-Math.PI / 2)

    const mesh = new THREE.Mesh(geo, wallMat)
    mesh.castShadow = true
    mesh.receiveShadow = true
    group.add(mesh)

    const trimMat = new THREE.MeshStandardMaterial({
      color: palette.trim,
      roughness: 0.7,
      metalness: 0.05,
    })

    const edgeGeo = new THREE.EdgesGeometry(geo)
    const edgeMat = new THREE.LineBasicMaterial({ color: palette.trim, linewidth: 1 })
    const edges = new THREE.LineSegments(edgeGeo, edgeMat)
    group.add(edges)

    const winMat = new THREE.MeshStandardMaterial({
      color: palette.window,
      roughness: 0.2,
      metalness: 0.6,
      emissive: palette.window,
      emissiveIntensity: 0.12,
    })

    const floors = Math.max(1, Math.floor(totalHeight / 3.2))
    const winGeo = new THREE.PlaneGeometry(0.6, 1.0)

    const bounds = this.getFootprintBounds(footprint)
    const perimeter = this.getFootprintPerimeter(footprint)
    const segments = Math.max(4, Math.floor(perimeter / 2.5))

    for (let f = 0; f < Math.min(floors, 20); f++) {
      const y = f * 3.2 + 0.8
      for (let s = 0; s < segments; s++) {
        const t = s / segments
        const idx = Math.floor(t * footprint.length)
        const nextIdx = (idx + 1) % footprint.length
        const p = footprint[idx]
        const pn = footprint[nextIdx]
        const frac = (t * footprint.length) - idx

        const wx = THREE.MathUtils.lerp(p.x, pn.x, frac)
        const wz = THREE.MathUtils.lerp(p.y, pn.y, frac)

        const edgeX = pn.x - p.x
        const edgeZ = pn.y - p.y
        const edgeLen = Math.sqrt(edgeX * edgeX + edgeZ * edgeZ)
        if (edgeLen < 0.5) continue

        const normalX = -edgeZ / edgeLen
        const normalZ = edgeX / edgeLen

        const win = new THREE.Mesh(winGeo, winMat)
        win.position.set(wx, y, wz)
        win.rotation.y = Math.atan2(normalX, normalZ)
        group.add(win)
      }
    }

    const roofMat = new THREE.MeshStandardMaterial({
      color: 0x555555,
      roughness: 0.9,
      metalness: 0.1,
    })

    const roofShape = new THREE.Shape()
    roofShape.moveTo(footprint[0].x, footprint[0].y)
    for (let i = 1; i < footprint.length; i++) {
      roofShape.lineTo(footprint[i].x, footprint[i].y)
    }
    roofShape.closePath()

    const roofGeo = new THREE.ShapeGeometry(roofShape)
    roofGeo.rotateX(-Math.PI / 2)
    const roof = new THREE.Mesh(roofGeo, roofMat)
    roof.position.y = totalHeight
    roof.castShadow = true
    group.add(roof)

    if (tags['building:roof:shape'] === 'peaked' || tags['building:roof:shape'] === 'gable') {
      const roofHeight = 3 + Math.random() * 3
      const peakGeo = new THREE.ConeGeometry(
        Math.max(bounds.width, bounds.depth) * 0.4,
        roofHeight,
        4
      )
      const peak = new THREE.Mesh(peakGeo, roofMat)
      peak.position.set(bounds.cx, totalHeight + roofHeight / 2, bounds.cz)
      peak.rotation.y = Math.PI / 4
      group.add(peak)
    }
  }

  private getFootprintBounds(points: THREE.Vector2[]) {
    let minX = Infinity, maxX = -Infinity
    let minZ = Infinity, maxZ = -Infinity
    for (const p of points) {
      minX = Math.min(minX, p.x)
      maxX = Math.max(maxX, p.x)
      minZ = Math.min(minZ, p.y)
      maxZ = Math.max(maxZ, p.y)
    }
    return {
      minX, maxX, minZ, maxZ,
      width: maxX - minX,
      depth: maxZ - minZ,
      cx: (minX + maxX) / 2,
      cz: (minZ + maxZ) / 2,
    }
  }

  private getFootprintPerimeter(points: THREE.Vector2[]): number {
    let perim = 0
    for (let i = 0; i < points.length; i++) {
      const a = points[i]
      const b = points[(i + 1) % points.length]
      perim += Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
    }
    return perim
  }
}
