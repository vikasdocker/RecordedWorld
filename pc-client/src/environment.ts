import * as THREE from 'three'
import { OSMBuildingLoader } from './osm-loader'
import { AssetLoader } from './asset-loader'

const _terrainTexCache = new Map<string, THREE.Texture>()

export interface TerrainConfig {
  size: number
  segments: number
}

export class Environment {
  scene: THREE.Scene
  private terrainHeightData: Float32Array | null = null
  private terrainSize: number
  private terrainSegments: number
  private treeInstances: THREE.InstancedMesh | null = null
  private grassInstances: THREE.InstancedMesh | null = null
  private grassMaterial: THREE.ShaderMaterial | null = null
  private waterMaterial: THREE.ShaderMaterial | null = null
  private terrainMaterial: THREE.ShaderMaterial | null = null
  private leafParticles: THREE.Points | null = null
  private dustParticles: THREE.Points | null = null
  private leafVelocities: Array<{ vx: number; vy: number; vz: number; rotSpeed: number }> = []
  private _playerX: number = 0
  private _playerZ: number = 0
  private osmLoader: OSMBuildingLoader
  private osmBuildings: THREE.Group | null = null
  private assetLoader: AssetLoader
  private lodGroups: Map<string, THREE.Object3D[]> = new Map()
  private lodCamera: THREE.Camera | null = null

  constructor(scene: THREE.Scene, config: TerrainConfig) {
    this.scene = scene
    this.terrainSize = config.size
    this.terrainSegments = config.segments
    this.osmLoader = new OSMBuildingLoader(40.785, -73.968)
    this.assetLoader = new AssetLoader()
  }

  async init(): Promise<void> {
    await this.assetLoader.loadAll()
    if (this.assetLoader.isLoaded()) {
      console.log(`Environment: Using Blender assets (${this.assetLoader.getBuildingCount()} buildings, ${this.assetLoader.getTreeCount()} trees)`)
      this.replaceWithGLTFAssets()
    } else {
      console.log('Environment: No Blender assets, using procedural geometry')
    }
  }

  private replaceWithGLTFAssets(): void {
    const toRemove: THREE.Object3D[] = []
    this.scene.traverse((child) => {
      if (child.name === 'procedural_building' || child.name === 'procedural_tree') {
        toRemove.push(child)
      }
    })
    for (const obj of toRemove) {
      obj.parent?.remove(obj)
    }

    this.placeGLTFBuildings()
    this.placeGLTFTrees()
  }

  private placeGLTFBuildings(): void {
    const buildingConfigs: Array<{ x: number; z: number }> = []
    for (let bx = -5; bx <= 5; bx++) {
      for (let bz = -5; bz <= 5; bz++) {
        if (Math.abs(bx) <= 0 && Math.abs(bz) <= 0) continue
        const onRoadX = Math.abs(bx * 16) < 8
        const onRoadZ = Math.abs(bz * 16) < 8
        if (onRoadX || onRoadZ) continue
        const x = bx * 16 + (Math.random() - 0.5) * 3
        const z = bz * 16 + (Math.random() - 0.5) * 3
        buildingConfigs.push({ x, z })
      }
    }
    for (const cfg of buildingConfigs) {
      this.placeGLTFBuilding(cfg.x, cfg.z)
    }
  }

  private placeGLTFTrees(): void {
    const clusterCenters = [
      { x: 80, z: 80 }, { x: -100, z: 60 }, { x: 50, z: -120 },
      { x: -80, z: -90 }, { x: 140, z: -40 }, { x: -140, z: 120 },
      { x: 30, z: 160 }, { x: -60, z: -170 }, { x: 170, z: 150 },
      { x: -180, z: -60 }, { x: 200, z: 80 }, { x: -50, z: 200 },
    ]
    for (const center of clusterCenters) {
      const count = 10 + Math.floor(Math.random() * 12)
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2
        const dist = Math.random() * 30
        this.placeGLTFTree(
          center.x + Math.cos(angle) * dist,
          center.z + Math.sin(angle) * dist,
          0.6 + Math.random() * 0.8
        )
      }
    }
    for (let i = 0; i < 30; i++) {
      this.placeGLTFTree(
        (Math.random() - 0.5) * 400,
        (Math.random() - 0.5) * 400,
        0.5 + Math.random() * 0.7
      )
    }
  }

  getTerrainHeight(x: number, z: number): number {
    if (!this.terrainHeightData) return 0
    const halfSize = this.terrainSize / 2
    const gridX = ((x + halfSize) / this.terrainSize) * this.terrainSegments
    const gridY = ((z + halfSize) / this.terrainSize) * this.terrainSegments
    const ix = Math.floor(gridX)
    const iy = Math.floor(gridY)
    if (ix < 0 || ix >= this.terrainSegments || iy < 0 || iy >= this.terrainSegments) return 0
    const fx = gridX - ix
    const fy = gridY - iy
    const stride = this.terrainSegments + 1
    const i00 = iy * stride + ix
    const h00 = this.terrainHeightData[i00] || 0
    const h10 = this.terrainHeightData[i00 + 1] || 0
    const h01 = this.terrainHeightData[i00 + stride] || 0
    const h11 = this.terrainHeightData[i00 + stride + 1] || 0
    return (h00 + (h10 - h00) * fx) + ((h01 + (h11 - h01) * fx) - (h00 + (h10 - h00) * fx)) * fy
  }

  buildAll(): void {
    this.buildTerrain()
    this.buildRoads()
    this.buildInstancedTrees()
    this.buildInstancedGrass()
    this.buildRocks()
    this.buildMountains()
    this.buildStreetFurniture()
    this.buildWaterFeature()
    this.buildParticles()
    this.loadOSMBuildings()
  }

  private generateTerrainTexture(
    width: number, height: number,
    baseColor: [number, number, number],
    noiseColor: [number, number, number],
    scale: number, octaves: number
  ): THREE.Texture {
    const cacheKey = `tex_${width}_${height}_${baseColor.join(',')}_${noiseColor.join(',')}_${scale}_${octaves}`
    const cached = _terrainTexCache.get(cacheKey)
    if (cached) return cached

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')!
    const imageData = ctx.createImageData(width, height)

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        let noise = 0
        let amplitude = 1
        let frequency = scale
        for (let o = 0; o < octaves; o++) {
          noise += (Math.sin(x * frequency * 0.01 + y * frequency * 0.013) * 0.5 + 0.5) * amplitude
          noise += (Math.cos(x * frequency * 0.017 + y * frequency * 0.009 + o) * 0.5 + 0.5) * amplitude * 0.5
          amplitude *= 0.5
          frequency *= 2.1
        }
        noise = (noise / (1.5 * octaves)) * 0.3 + 0.7

        const detail = Math.sin(x * 0.8) * Math.cos(y * 0.7) * 0.04

        const idx = (y * width + x) * 4
        imageData.data[idx] = Math.floor((baseColor[0] + noiseColor[0] * noise + detail) * 255)
        imageData.data[idx + 1] = Math.floor((baseColor[1] + noiseColor[1] * noise + detail) * 255)
        imageData.data[idx + 2] = Math.floor((baseColor[2] + noiseColor[2] * noise + detail) * 255)
        imageData.data[idx + 3] = 255
      }
    }

    ctx.putImageData(imageData, 0, 0)
    const texture = new THREE.CanvasTexture(canvas)
    texture.wrapS = THREE.RepeatWrapping
    texture.wrapT = THREE.RepeatWrapping
    texture.repeat.set(12, 12)
    _terrainTexCache.set(cacheKey, texture)
    return texture
  }

  private generateTerrainNormalMap(
    width: number, height: number, scale: number
  ): THREE.Texture {
    const cacheKey = `nrm_${width}_${height}_${scale}`
    const cached = _terrainTexCache.get(cacheKey)
    if (cached) return cached

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')!
    const imageData = ctx.createImageData(width, height)

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const nx = Math.sin(x * scale * 0.05) * Math.cos(y * scale * 0.03) * 0.3
        const ny = Math.cos(x * scale * 0.03) * Math.sin(y * scale * 0.04) * 0.3
        const nz = 1.0
        const len = Math.sqrt(nx * nx + ny * ny + nz * nz)
        const idx = (y * width + x) * 4
        imageData.data[idx] = Math.floor(((nx / len) * 0.5 + 0.5) * 255)
        imageData.data[idx + 1] = Math.floor(((ny / len) * 0.5 + 0.5) * 255)
        imageData.data[idx + 2] = Math.floor(((nz / len) * 0.5 + 0.5) * 255)
        imageData.data[idx + 3] = 255
      }
    }

    ctx.putImageData(imageData, 0, 0)
    const texture = new THREE.CanvasTexture(canvas)
    texture.wrapS = THREE.RepeatWrapping
    texture.wrapT = THREE.RepeatWrapping
    texture.repeat.set(12, 12)
    _terrainTexCache.set(cacheKey, texture)
    return texture
  }

  private buildTerrain(): void {
    const segments = this.terrainSegments
    const size = this.terrainSize
    const geometry = new THREE.PlaneGeometry(size, size, segments, segments)
    const positions = geometry.attributes.position
    const uvAttr = geometry.attributes.uv
    this.terrainHeightData = new Float32Array(positions.count)

    const slopeData = new Float32Array(positions.count)

    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i)
      const y = positions.getY(i)

      const h1 = Math.sin(x * 0.008) * Math.cos(y * 0.008) * 4
      const h2 = Math.sin(x * 0.02 + 1.3) * Math.cos(y * 0.015 + 0.7) * 2
      const h3 = Math.sin(x * 0.05 + 2.1) * Math.cos(y * 0.04 + 1.9) * 0.8
      const h4 = Math.sin(x * 0.1) * Math.cos(y * 0.1) * 0.3
      let height = h1 + h2 + h3 + h4

      const roadHalfWidth = 4.5
      const sidewalkWidth = 1.5
      const inRoadX = Math.abs(x) < roadHalfWidth
      const inRoadY = Math.abs(y) < roadHalfWidth
      if (inRoadX || inRoadY) {
        height *= 0.02
      } else {
        const nearRoadX = Math.abs(x) < roadHalfWidth + sidewalkWidth
        const nearRoadY = Math.abs(y) < roadHalfWidth + sidewalkWidth
        if (nearRoadX || nearRoadY) {
          height *= 0.15
        }
      }

      positions.setZ(i, height)
      this.terrainHeightData[i] = height

      const ix = i % (segments + 1)
      const iy = Math.floor(i / (segments + 1))
      if (ix < segments && iy < segments) {
        const iR = iy * (segments + 1) + ix + 1
        const iU = (iy + 1) * (segments + 1) + ix
        const hR = this.terrainHeightData[iR] || height
        const hU = this.terrainHeightData[iU] || height
        const dx = hR - height
        const dy = hU - height
        slopeData[i] = Math.sqrt(dx * dx + dy * dy) * 10
      } else {
        slopeData[i] = 0
      }
    }

    const grassTex = this.generateTerrainTexture(256, 256, [0.18, 0.38, 0.14], [0.06, 0.12, 0.04], 3.0, 4)
    const dirtTex = this.generateTerrainTexture(256, 256, [0.35, 0.25, 0.15], [0.08, 0.05, 0.03], 2.5, 3)
    const rockTex = this.generateTerrainTexture(256, 256, [0.4, 0.38, 0.35], [0.1, 0.1, 0.1], 1.5, 3)
    const normalMap = this.generateTerrainNormalMap(256, 256, 2.0)

    geometry.setAttribute('slope', new THREE.BufferAttribute(slopeData, 1))

    geometry.computeVertexNormals()

    this.terrainMaterial = new THREE.ShaderMaterial({
      uniforms: {
        uGrassTex: { value: grassTex },
        uDirtTex: { value: dirtTex },
        uRockTex: { value: rockTex },
        uNormalMap: { value: normalMap },
        uSlopeThreshold: { value: 0.4 },
        uSlopeBlend: { value: 0.15 },
        uHeightThreshold: { value: 5.0 },
        uHeightBlend: { value: 1.5 },
        uRoadWidth: { value: 5.5 },
        uTime: { value: 0 },
      },
      vertexShader: /* glsl */ `
        attribute float slope;
        varying vec2 vUv;
        varying vec3 vWorldPos;
        varying vec3 vNormal;
        varying float vSlope;
        void main() {
          vUv = uv;
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWorldPos = wp.xyz;
          vNormal = normalize(normalMatrix * normal);
          vSlope = slope;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform sampler2D uGrassTex;
        uniform sampler2D uDirtTex;
        uniform sampler2D uRockTex;
        uniform sampler2D uNormalMap;
        uniform float uSlopeThreshold;
        uniform float uSlopeBlend;
        uniform float uHeightThreshold;
        uniform float uHeightBlend;
        uniform float uRoadWidth;
        uniform float uTime;
        varying vec2 vUv;
        varying vec3 vWorldPos;
        varying vec3 vNormal;
        varying float vSlope;

        void main() {
          vec2 tiledUV = vWorldPos.xz * 0.15;
          vec4 grassColor = texture2D(uGrassTex, tiledUV);
          vec4 dirtColor = texture2D(uDirtTex, tiledUV * 1.3);
          vec4 rockColor = texture2D(uRockTex, tiledUV * 0.8);

          float roadDist = min(abs(vWorldPos.x), abs(vWorldPos.z));
          float roadMask = 1.0 - smoothstep(uRoadWidth - 0.5, uRoadWidth + 0.5, roadDist);
          float sidewalkMask = smoothstep(uRoadWidth - 0.5, uRoadWidth + 0.5, roadDist);
          sidewalkMask *= 1.0 - smoothstep(uRoadWidth + 0.5, uRoadWidth + 2.0, roadDist);

          float slopeFactor = smoothstep(uSlopeThreshold - uSlopeBlend, uSlopeThreshold + uSlopeBlend, vSlope);
          float heightFactor = smoothstep(uHeightThreshold - uHeightBlend, uHeightThreshold + uHeightBlend, vWorldPos.y);

          vec3 terrainColor = mix(grassColor.rgb, dirtColor.rgb, heightFactor);
          terrainColor = mix(terrainColor, rockColor.rgb, slopeFactor);

          vec3 roadColor = vec3(0.22, 0.22, 0.22);
          vec3 sidewalkColor = vec3(0.65, 0.63, 0.58);
          vec3 laneColor = vec3(0.85, 0.8, 0.15);

          float laneDist = min(abs(vWorldPos.x), abs(vWorldPos.z));
          float laneMask = 1.0 - smoothstep(0.05, 0.12, laneDist - 0.0);

          vec3 finalColor = mix(terrainColor, roadColor, roadMask);
          finalColor = mix(finalColor, sidewalkColor, sidewalkMask * 0.6);
          finalColor = mix(finalColor, laneColor, roadMask * laneMask * 0.7);

          float detailNoise = sin(vWorldPos.x * 3.0) * cos(vWorldPos.z * 2.7) * 0.02;
          finalColor += detailNoise;

          vec3 normal = normalize(vNormal);
          vec3 lightDir = normalize(vec3(0.4, 0.8, 0.3));
          float diff = max(dot(normal, lightDir), 0.0) * 0.15;
          finalColor += diff;

          gl_FragColor = vec4(finalColor, 1.0);
        }
      `,
    })

    const ground = new THREE.Mesh(geometry, this.terrainMaterial)
    ground.rotation.x = -Math.PI / 2
    ground.receiveShadow = true
    ground.name = 'terrain'
    this.scene.add(ground)
  }

  private buildRoads(): void {
    const roadMat = new THREE.MeshStandardMaterial({
      color: 0x2a2a2a,
      roughness: 0.75,
      metalness: 0.02,
    })
    const sidewalkMat = new THREE.MeshStandardMaterial({
      color: 0x8a8a7a,
      roughness: 0.88,
      metalness: 0.0,
    })
    const laneMat = new THREE.MeshStandardMaterial({
      color: 0xdddd55,
      roughness: 0.5,
      emissive: 0x444400,
      emissiveIntensity: 0.15,
    })
    const curbMat = new THREE.MeshStandardMaterial({
      color: 0xaa9988,
      roughness: 0.82,
    })
    const edgeLineMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.4,
      emissive: 0xffffff,
      emissiveIntensity: 0.05,
    })

    const roadLen = 300

    const roadX = new THREE.Mesh(
      new THREE.BoxGeometry(9, 0.06, roadLen),
      roadMat
    )
    roadX.position.set(0, 0.03, 0)
    roadX.receiveShadow = true
    this.scene.add(roadX)

    const roadZ = new THREE.Mesh(
      new THREE.BoxGeometry(roadLen, 0.06, 9),
      roadMat
    )
    roadZ.position.set(0, 0.03, 0)
    roadZ.receiveShadow = true
    this.scene.add(roadZ)

    const dashLen = 3
    const gapLen = 2
    const lineCount = Math.floor(roadLen / (dashLen + gapLen))
    for (let i = 0; i < lineCount; i++) {
      const pos = -roadLen / 2 + i * (dashLen + gapLen) + dashLen / 2
      const dashX = new THREE.Mesh(
        new THREE.BoxGeometry(0.18, 0.06, dashLen),
        laneMat
      )
      dashX.position.set(0, 0.07, pos)
      this.scene.add(dashX)

      const dashZ = new THREE.Mesh(
        new THREE.BoxGeometry(dashLen, 0.06, 0.18),
        laneMat
      )
      dashZ.position.set(pos, 0.07, 0)
      this.scene.add(dashZ)
    }

    for (const side of [-1, 1]) {
      const edgeLineX = new THREE.Mesh(
        new THREE.BoxGeometry(0.12, 0.065, roadLen),
        edgeLineMat
      )
      edgeLineX.position.set(side * 4.3, 0.065, 0)
      this.scene.add(edgeLineX)

      const edgeLineZ = new THREE.Mesh(
        new THREE.BoxGeometry(roadLen, 0.065, 0.12),
        edgeLineMat
      )
      edgeLineZ.position.set(0, 0.065, side * 4.3)
      this.scene.add(edgeLineZ)

      const edgeX = new THREE.Mesh(
        new THREE.BoxGeometry(0.22, 0.14, roadLen),
        curbMat
      )
      edgeX.position.set(side * 4.5, 0.07, 0)
      this.scene.add(edgeX)

      const edgeZ = new THREE.Mesh(
        new THREE.BoxGeometry(roadLen, 0.14, 0.22),
        curbMat
      )
      edgeZ.position.set(0, 0.07, side * 4.5)
      this.scene.add(edgeZ)

      const swX = new THREE.Mesh(
        new THREE.BoxGeometry(1.5, 0.08, roadLen),
        sidewalkMat
      )
      swX.position.set(side * 5.25, 0.04, 0)
      swX.receiveShadow = true
      this.scene.add(swX)

      const swZ = new THREE.Mesh(
        new THREE.BoxGeometry(roadLen, 0.08, 1.5),
        sidewalkMat
      )
      swZ.position.set(0, 0.04, side * 5.25)
      swZ.receiveShadow = true
      this.scene.add(swZ)
    }

    const crosswalkMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.5,
      emissive: 0xffffff,
      emissiveIntensity: 0.03,
    })
    for (const crossPos of [-30, 30, -80, 80]) {
      for (let s = 0; s < 5; s++) {
        const stripeX = new THREE.Mesh(
          new THREE.BoxGeometry(0.3, 0.065, 1.8),
          crosswalkMat
        )
        stripeX.position.set(crossPos + s * 0.5 - 1, 0.065, 0)
        this.scene.add(stripeX)

        const stripeZ = new THREE.Mesh(
          new THREE.BoxGeometry(1.8, 0.065, 0.3),
          crosswalkMat
        )
        stripeZ.position.set(0, 0.065, crossPos + s * 0.5 - 1)
        this.scene.add(stripeZ)
      }
    }
  }

  private buildBuildings(): void {
    const useGLTF = this.assetLoader.isLoaded() && this.assetLoader.getBuildingCount() > 0

    const buildingConfigs: Array<{ x: number; z: number }> = []

    for (let bx = -5; bx <= 5; bx++) {
      for (let bz = -5; bz <= 5; bz++) {
        if (Math.abs(bx) <= 0 && Math.abs(bz) <= 0) continue
        const onRoadX = Math.abs(bx * 16) < 8
        const onRoadZ = Math.abs(bz * 16) < 8
        if (onRoadX || onRoadZ) continue

        const x = bx * 16 + (Math.random() - 0.5) * 3
        const z = bz * 16 + (Math.random() - 0.5) * 3
        buildingConfigs.push({ x, z })
      }
    }

    for (const cfg of buildingConfigs) {
      if (useGLTF) {
        this.placeGLTFBuilding(cfg.x, cfg.z)
      } else {
        const w = 5 + Math.random() * 6
        const d = 5 + Math.random() * 6
        const floors = 1 + Math.floor(Math.random() * 6)
        this.buildSingleBuilding(cfg.x, cfg.z, w, d, floors)
      }
    }
  }

  private placeGLTFBuilding(x: number, z: number): void {
    const model = this.assetLoader.getRandomBuilding()
    if (!model) return

    const terrainY = this.getTerrainHeight(x, z)
    model.position.set(x, terrainY, z)
    model.rotation.y = Math.random() * Math.PI * 2
    this.scene.add(model)
  }

  private buildSingleBuilding(
    x: number, z: number, w: number, d: number, floors: number,
  ): void {
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
    const palette = palettes[Math.floor(Math.random() * palettes.length)]
    const floorHeight = 3.0
    const totalHeight = floors * floorHeight
    const terrainY = this.getTerrainHeight(x, z)

    const bldg = new THREE.Group()
    bldg.name = 'procedural_building'

    const wallMat = new THREE.MeshStandardMaterial({
      color: palette.wall, roughness: 0.85, metalness: 0.02,
    })
    const body = new THREE.Mesh(new THREE.BoxGeometry(w, totalHeight, d), wallMat)
    body.position.set(x, terrainY + totalHeight / 2, z)
    body.castShadow = true
    body.receiveShadow = true
    bldg.add(body)

    const trimMat = new THREE.MeshStandardMaterial({ color: palette.trim, roughness: 0.7, metalness: 0.05 })
    const trimGeo = new THREE.BoxGeometry(w + 0.15, 0.2, d + 0.15)
    for (let f = 0; f <= floors; f++) {
      const trim = new THREE.Mesh(trimGeo, trimMat)
      trim.position.set(x, terrainY + f * floorHeight, z)
      bldg.add(trim)
    }

    const winMat = new THREE.MeshStandardMaterial({
      color: palette.window, roughness: 0.2, metalness: 0.6,
      emissive: palette.window, emissiveIntensity: 0.15,
    })
    const windowSpacingH = 2.0
    const windowSize = 0.7
    const windowHeight = 1.2
    for (const face of [
      { axis: 'x' as const, sign: 1, size: w },
      { axis: 'x' as const, sign: -1, size: w },
      { axis: 'z' as const, sign: 1, size: d },
      { axis: 'z' as const, sign: -1, size: d },
    ]) {
      const countH = Math.floor(face.size / windowSpacingH)
      for (let f = 0; f < floors; f++) {
        const yBase = terrainY + f * floorHeight + 0.6
        for (let wi = 0; wi < countH; wi++) {
          const offset = -face.size / 2 + windowSpacingH / 2 + wi * windowSpacingH
          const win = new THREE.Mesh(new THREE.PlaneGeometry(windowSize, windowHeight), winMat)
          const halfW = face.axis === 'x' ? w / 2 : d / 2
          if (face.axis === 'x') {
            win.position.set(x + offset, yBase + windowHeight / 2, z + face.sign * (halfW + 0.06))
            win.rotation.y = face.sign > 0 ? 0 : Math.PI
          } else {
            win.position.set(x + face.sign * (halfW + 0.06), yBase + windowHeight / 2, z + offset)
            win.rotation.y = face.sign > 0 ? Math.PI / 2 : -Math.PI / 2
          }
          bldg.add(win)
        }
      }
    }

    const roofMat = new THREE.MeshStandardMaterial({ color: 0x555555, roughness: 0.9, metalness: 0.1 })
    const roof = new THREE.Mesh(new THREE.BoxGeometry(w + 0.3, 0.15, d + 0.3), roofMat)
    roof.position.set(x, terrainY + totalHeight + 0.075, z)
    roof.castShadow = true
    bldg.add(roof)

    const ledgeMat = new THREE.MeshStandardMaterial({ color: palette.trim, roughness: 0.7 })
    const ledge = new THREE.Mesh(new THREE.BoxGeometry(w + 0.5, 0.3, d + 0.5), ledgeMat)
    ledge.position.set(x, terrainY + totalHeight - 0.15, z)
    bldg.add(ledge)

    if (floors >= 3 && Math.random() > 0.5) {
      const acGeo = new THREE.BoxGeometry(0.6, 0.4, 0.4)
      const acMat = new THREE.MeshStandardMaterial({ color: 0x888888, roughness: 0.6, metalness: 0.3 })
      const acCount = 1 + Math.floor(Math.random() * 3)
      for (let i = 0; i < acCount; i++) {
        const ac = new THREE.Mesh(acGeo, acMat)
        ac.position.set(x + (Math.random() - 0.5) * (w - 1), terrainY + totalHeight + 0.35, z + (Math.random() - 0.5) * (d - 1))
        ac.castShadow = true
        bldg.add(ac)
      }
    }

    if (floors >= 2 && Math.random() > 0.4) {
      const towerH = 1.5 + Math.random() * 1.5
      const tower = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.3, towerH, 8), new THREE.MeshStandardMaterial({ color: 0x8b6543, roughness: 0.9 }))
      tower.position.set(x + (Math.random() - 0.5) * (w - 1.5), terrainY + totalHeight + towerH / 2, z + (Math.random() - 0.5) * (d - 1.5))
      tower.castShadow = true
      bldg.add(tower)
    }

    this.scene.add(bldg)
  }

  private buildInstancedTrees(): void {
    const useGLTF = this.assetLoader.isLoaded() && this.assetLoader.getTreeCount() > 0

    const clusterCenters = [
      { x: 80, z: 80 }, { x: -100, z: 60 }, { x: 50, z: -120 },
      { x: -80, z: -90 }, { x: 140, z: -40 }, { x: -140, z: 120 },
      { x: 30, z: 160 }, { x: -60, z: -170 }, { x: 170, z: 150 },
      { x: -180, z: -60 }, { x: 200, z: 80 }, { x: -50, z: 200 },
    ]

    const treePositions: Array<{ x: number; z: number; scale: number }> = []

    for (const center of clusterCenters) {
      const count = 10 + Math.floor(Math.random() * 12)
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2
        const dist = Math.random() * 30
        treePositions.push({
          x: center.x + Math.cos(angle) * dist,
          z: center.z + Math.sin(angle) * dist,
          scale: 0.6 + Math.random() * 0.8,
        })
      }
    }
    for (let i = 0; i < 30; i++) {
      treePositions.push({
        x: (Math.random() - 0.5) * 400,
        z: (Math.random() - 0.5) * 400,
        scale: 0.5 + Math.random() * 0.7,
      })
    }

    if (useGLTF) {
      for (const tp of treePositions) {
        this.placeGLTFTree(tp.x, tp.z, tp.scale)
      }
    } else {
      this.buildProceduralTrees(treePositions)
    }
  }

  private placeGLTFTree(x: number, z: number, scale: number): void {
    const types = ['deciduous', 'conifer', 'palm']
    const type = types[Math.floor(Math.random() * types.length)]
    const model = this.assetLoader.getRandomTree(type)
    if (!model) return

    const terrainY = this.getTerrainHeight(x, z)
    model.position.set(x, terrainY, z)
    model.scale.set(scale, scale, scale)
    model.rotation.y = Math.random() * Math.PI * 2
    this.scene.add(model)
  }

  private buildProceduralTrees(treePositions: Array<{ x: number; z: number; scale: number }>): void {
    const treeGroup = new THREE.Group()
    treeGroup.name = 'procedural_tree'

    const trunkGeo = new THREE.CylinderGeometry(0.1, 0.16, 2.8, 6)
    const trunkMat = new THREE.MeshStandardMaterial({ color: 0x5a3015, roughness: 0.95 })

    const leafMat1 = new THREE.MeshStandardMaterial({ color: 0x2a7a2a, roughness: 0.8 })
    const leafMat2 = new THREE.MeshStandardMaterial({ color: 0x1e6e1e, roughness: 0.8 })
    const leafMat3 = new THREE.MeshStandardMaterial({ color: 0x4a9a35, roughness: 0.75 })

    const trunkInstances = new THREE.InstancedMesh(trunkGeo, trunkMat, treePositions.length)
    trunkInstances.castShadow = true
    trunkInstances.receiveShadow = true
    const dummy = new THREE.Object3D()
    for (let i = 0; i < treePositions.length; i++) {
      const tp = treePositions[i]
      const ty = this.getTerrainHeight(tp.x, tp.z)
      dummy.position.set(tp.x, ty + 1.4 * tp.scale, tp.z)
      dummy.scale.set(tp.scale, tp.scale, tp.scale)
      dummy.updateMatrix()
      trunkInstances.setMatrixAt(i, dummy.matrix)
    }
    trunkInstances.instanceMatrix.needsUpdate = true
    treeGroup.add(trunkInstances)

    const foliageMats = [leafMat1, leafMat2, leafMat3]

    const coneGeo1 = new THREE.ConeGeometry(1.0, 1.4, 8)
    const cone1 = new THREE.InstancedMesh(coneGeo1, foliageMats[0], treePositions.length)
    cone1.castShadow = true
    for (let i = 0; i < treePositions.length; i++) {
      const tp = treePositions[i]
      const ty = this.getTerrainHeight(tp.x, tp.z)
      dummy.position.set(tp.x, ty + 2.8 * tp.scale, tp.z)
      const ls = tp.scale * (0.9 + (i % 3) * 0.12)
      dummy.scale.set(ls, ls * 0.9, ls)
      dummy.updateMatrix()
      cone1.setMatrixAt(i, dummy.matrix)
    }
    cone1.instanceMatrix.needsUpdate = true
    treeGroup.add(cone1)

    const coneGeo2 = new THREE.ConeGeometry(0.7, 1.1, 7)
    const cone2 = new THREE.InstancedMesh(coneGeo2, foliageMats[1], treePositions.length)
    cone2.castShadow = true
    for (let i = 0; i < treePositions.length; i++) {
      const tp = treePositions[i]
      const ty = this.getTerrainHeight(tp.x, tp.z)
      dummy.position.set(tp.x, ty + 3.6 * tp.scale, tp.z)
      const ls = tp.scale * 0.7
      dummy.scale.set(ls, ls * 0.85, ls)
      dummy.updateMatrix()
      cone2.setMatrixAt(i, dummy.matrix)
    }
    cone2.instanceMatrix.needsUpdate = true
    treeGroup.add(cone2)

    const sphereGeo = new THREE.IcosahedronGeometry(0.5, 1)
    const canopy = new THREE.InstancedMesh(sphereGeo, foliageMats[2], treePositions.length)
    canopy.castShadow = true
    for (let i = 0; i < treePositions.length; i++) {
      const tp = treePositions[i]
      const ty = this.getTerrainHeight(tp.x, tp.z)
      dummy.position.set(
        tp.x + (Math.random() - 0.5) * 0.4,
        ty + 4.0 * tp.scale,
        tp.z + (Math.random() - 0.5) * 0.4
      )
      const ls = tp.scale * 0.55
      dummy.scale.set(ls, ls * 0.8, ls)
      dummy.updateMatrix()
      canopy.setMatrixAt(i, dummy.matrix)
    }
    canopy.instanceMatrix.needsUpdate = true
    treeGroup.add(canopy)
    this.scene.add(treeGroup)
  }

  private buildInstancedGrass(): void {
    const bladeGeo = new THREE.BufferGeometry()
    const verts = new Float32Array([
      -0.03, 0, 0,   0.03, 0, 0,   0.01, 0.25, 0,
      -0.03, 0, 0,   0.01, 0.25, 0,  -0.01, 0.2, 0,
    ])
    bladeGeo.setAttribute('position', new THREE.BufferAttribute(verts, 3))

    const grassCount = 8000

    const grassMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uWindStrength: { value: 0.35 },
        uWindFrequency: { value: 1.5 },
        uColor1: { value: new THREE.Color(0x1e4a12) },
        uColor2: { value: new THREE.Color(0x3a7a28) },
        uColor3: { value: new THREE.Color(0x4a9a32) },
      },
      vertexShader: /* glsl */ `
        uniform float uTime;
        uniform float uWindStrength;
        uniform float uWindFrequency;
        attribute vec3 instancePosition;
        varying float vHeight;
        varying vec3 vWorldPos;
        void main() {
          vec3 pos = position;
          float heightFactor = pos.y / 0.25;
          float windPhase = uTime * uWindFrequency + instancePosition.x * 0.3 + instancePosition.z * 0.2;
          float windX = sin(windPhase) * uWindStrength;
          float windZ = cos(windPhase * 0.7 + instancePosition.z * 0.15) * uWindStrength * 0.4;
          pos.x += windX * heightFactor * heightFactor;
          pos.z += windZ * heightFactor * heightFactor;
          vec4 worldPos = modelMatrix * instanceMatrix * vec4(pos, 1.0);
          vHeight = heightFactor;
          vWorldPos = worldPos.xyz;
          gl_Position = projectionMatrix * viewMatrix * worldPos;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor1;
        uniform vec3 uColor2;
        uniform vec3 uColor3;
        varying float vHeight;
        varying vec3 vWorldPos;
        void main() {
          float pattern = sin(vWorldPos.x * 0.5) * cos(vWorldPos.z * 0.4) * 0.5 + 0.5;
          vec3 color = mix(uColor1, uColor2, vHeight * 0.7);
          color = mix(color, uColor3, pattern * 0.3);
          float shadow = 0.65 + 0.35 * vHeight;
          color *= shadow;
          gl_FragColor = vec4(color, 1.0);
        }
      `,
      side: THREE.DoubleSide,
    })

    this.grassInstances = new THREE.InstancedMesh(bladeGeo, grassMat, grassCount)

    const dummy = new THREE.Object3D()
    const dummyPos = new Float32Array(grassCount * 3)
    for (let i = 0; i < grassCount; i++) {
      const gx = (Math.random() - 0.5) * 250
      const gz = (Math.random() - 0.5) * 250
      const gy = this.getTerrainHeight(gx, gz)

      const roadHalfWidth = 6
      if (Math.abs(gx) < roadHalfWidth && Math.abs(gz) < roadHalfWidth) {
        dummy.position.set(0, -100, 0)
        dummy.rotation.set(0, 0, 0)
        dummy.scale.set(0, 0, 0)
        dummy.updateMatrix()
        this.grassInstances.setMatrixAt(i, dummy.matrix)
        continue
      }

      dummy.position.set(gx, gy, gz)
      dummy.rotation.set(0, Math.random() * Math.PI * 2, 0)
      const s = 0.5 + Math.random() * 1.0
      dummy.scale.set(s, s, s)
      dummy.updateMatrix()
      this.grassInstances.setMatrixAt(i, dummy.matrix)

      dummyPos[i * 3] = gx
      dummyPos[i * 3 + 1] = gy
      dummyPos[i * 3 + 2] = gz
    }
    this.grassInstances.instanceMatrix.needsUpdate = true
    this.scene.add(this.grassInstances)
  }

  private buildRocks(): void {
    const rockGeo = new THREE.DodecahedronGeometry(0.3, 2)
    const rockMat = new THREE.MeshStandardMaterial({
      color: 0x5a5a5a,
      roughness: 0.92,
      metalness: 0.0,
      flatShading: true,
    })
    const rockCount = 80
    const rockInstances = new THREE.InstancedMesh(rockGeo, rockMat, rockCount)
    rockInstances.castShadow = true
    rockInstances.receiveShadow = true

    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    for (let i = 0; i < rockCount; i++) {
      const rx = (Math.random() - 0.5) * 350
      const rz = (Math.random() - 0.5) * 350
      const ry = this.getTerrainHeight(rx, rz)
      const size = 0.15 + Math.random() * 0.4

      dummy.position.set(rx, ry + size * 0.2, rz)
      dummy.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * 0.3)
      dummy.scale.set(size, size * (0.35 + Math.random() * 0.65), size)
      dummy.updateMatrix()
      rockInstances.setMatrixAt(i, dummy.matrix)

      const gray = 0.22 + Math.random() * 0.28
      const warmth = Math.random() * 0.05
      color.setHSL(warmth, 0.05, gray)
      rockInstances.setColorAt(i, color)
    }
    rockInstances.instanceMatrix.needsUpdate = true
    if (rockInstances.instanceColor) rockInstances.instanceColor.needsUpdate = true
    this.scene.add(rockInstances)
  }

  private buildMountains(): void {
    const mtMat = new THREE.MeshStandardMaterial({
      color: 0x4a5a6a,
      roughness: 0.95,
      flatShading: true,
    })
    const mtMat2 = new THREE.MeshStandardMaterial({
      color: 0x556655,
      roughness: 0.92,
      flatShading: true,
    })
    const snowMat = new THREE.MeshStandardMaterial({
      color: 0xe8e8f0,
      roughness: 0.45,
      flatShading: true,
    })
    const rockMat = new THREE.MeshStandardMaterial({
      color: 0x6a6a6a,
      roughness: 0.9,
      flatShading: true,
    })

    for (let i = 0; i < 10; i++) {
      const angle = (i / 10) * Math.PI * 2 + Math.random() * 0.3
      const dist = 350 + Math.random() * 120
      const radius = 25 + Math.random() * 25
      const height = 40 + Math.random() * 35

      const mat = i % 3 === 0 ? mtMat2 : mtMat
      const mountain = new THREE.Mesh(
        new THREE.ConeGeometry(radius, height, 10 + Math.floor(Math.random() * 4)),
        mat
      )
      mountain.position.set(Math.cos(angle) * dist, height / 2 - 5, Math.sin(angle) * dist)
      mountain.rotation.y = Math.random() * Math.PI
      mountain.castShadow = true
      this.scene.add(mountain)

      const capSize = radius * (0.3 + Math.random() * 0.1)
      const capHeight = height * (0.2 + Math.random() * 0.1)
      const cap = new THREE.Mesh(
        new THREE.ConeGeometry(capSize, capHeight, 10),
        snowMat
      )
      cap.position.set(Math.cos(angle) * dist, height * 0.42, Math.sin(angle) * dist)
      this.scene.add(cap)

      if (Math.random() > 0.5) {
        const cliffCount = 2 + Math.floor(Math.random() * 3)
        for (let c = 0; c < cliffCount; c++) {
          const cAngle = angle + (Math.random() - 0.5) * 0.5
          const cDist = dist + (Math.random() - 0.5) * 20
          const cliff = new THREE.Mesh(
            new THREE.DodecahedronGeometry(3 + Math.random() * 5, 1),
            rockMat
          )
          cliff.position.set(
            Math.cos(cAngle) * cDist,
            height * 0.1 + Math.random() * height * 0.3,
            Math.sin(cAngle) * cDist
          )
          cliff.rotation.set(Math.random() * 2, Math.random() * 2, 0)
          cliff.castShadow = true
          this.scene.add(cliff)
        }
      }
    }
  }

  private async loadOSMBuildings(): Promise<void> {
    const lat = 40.785
    const lon = -73.968
    const deltaLat = 0.008
    const deltaLon = 0.012

    this.osmBuildings = await this.osmLoader.fetchBuildings(
      lat - deltaLat, lon - deltaLon,
      lat + deltaLat, lon + deltaLon
    )
    this.scene.add(this.osmBuildings)

    if (this.osmBuildings.children.length === 0) {
      console.log('No OSM buildings loaded, using procedural fallback')
      this.buildProceduralBuildings()
    }
  }

  private buildProceduralBuildings(): void {
    const palettes = [
      { wall: 0xd4c5a9, window: 0x88aacc, trim: 0xbba888, frame: 0x999999 },
      { wall: 0x8c9eaf, window: 0x6688aa, trim: 0x7788aa, frame: 0x888888 },
      { wall: 0xc4b8a8, window: 0x7799bb, trim: 0xaa9977, frame: 0xaaaaaa },
      { wall: 0xa8b8c8, window: 0x5588aa, trim: 0x8899aa, frame: 0x777777 },
      { wall: 0xbaa88a, window: 0x889966, trim: 0x998866, frame: 0x999999 },
      { wall: 0xe0d8c8, window: 0x99aacc, trim: 0xccbbaa, frame: 0xbbbbbb },
      { wall: 0x7a8a9a, window: 0x5577aa, trim: 0x667799, frame: 0x888888 },
      { wall: 0xc8bca8, window: 0x778899, trim: 0xbbaa88, frame: 0xaaaaaa },
    ]

    for (let bx = -5; bx <= 5; bx++) {
      for (let bz = -5; bz <= 5; bz++) {
        if (Math.abs(bx) <= 0 && Math.abs(bz) <= 0) continue
        const onRoadX = Math.abs(bx * 16) < 8
        const onRoadZ = Math.abs(bz * 16) < 8
        if (onRoadX || onRoadZ) continue

        const x = bx * 16 + (Math.random() - 0.5) * 3
        const z = bz * 16 + (Math.random() - 0.5) * 3
        const w = 5 + Math.random() * 6
        const d = 5 + Math.random() * 6
        const floors = 1 + Math.floor(Math.random() * 6)
        const totalHeight = floors * 3.0

        const palette = palettes[Math.floor(Math.random() * palettes.length)]
        const terrainY = this.getTerrainHeight(x, z)

        const bldg = new THREE.Group()
        bldg.name = 'procedural_building'

        const wallMat = new THREE.MeshStandardMaterial({
          color: palette.wall, roughness: 0.88, metalness: 0.02,
        })
        const body = new THREE.Mesh(new THREE.BoxGeometry(w, totalHeight, d), wallMat)
        body.position.set(x, terrainY + totalHeight / 2, z)
        body.castShadow = true
        body.receiveShadow = true
        bldg.add(body)

        const trimMat = new THREE.MeshStandardMaterial({ color: palette.trim, roughness: 0.75 })
        for (let f = 0; f <= floors; f++) {
          const trim = new THREE.Mesh(new THREE.BoxGeometry(w + 0.2, 0.18, d + 0.2), trimMat)
          trim.position.set(x, terrainY + f * 3.0, z)
          bldg.add(trim)
        }

        const winMat = new THREE.MeshStandardMaterial({
          color: palette.window, roughness: 0.15, metalness: 0.7,
          emissive: palette.window, emissiveIntensity: 0.2,
        })
        const winFrameMat = new THREE.MeshStandardMaterial({
          color: palette.frame, roughness: 0.6, metalness: 0.3,
        })

        for (const face of [
          { axis: 'x' as const, sign: 1, size: w },
          { axis: 'x' as const, sign: -1, size: w },
          { axis: 'z' as const, sign: 1, size: d },
          { axis: 'z' as const, sign: -1, size: d },
        ]) {
          const countH = Math.floor(face.size / 2.2)
          for (let f = 0; f < floors; f++) {
            const yBase = terrainY + f * 3.0 + 0.5
            for (let wi = 0; wi < countH; wi++) {
              const offset = -face.size / 2 + 1.1 + wi * 2.2
              const winW = 0.65
              const winH = 1.1
              const halfW = face.axis === 'x' ? w / 2 : d / 2

              const frame = new THREE.Mesh(
                new THREE.BoxGeometry(winW + 0.08, winH + 0.08, 0.03),
                winFrameMat
              )
              if (face.axis === 'x') {
                frame.position.set(x + offset, yBase + winH / 2, z + face.sign * (halfW + 0.05))
                frame.rotation.y = face.sign > 0 ? 0 : Math.PI
              } else {
                frame.position.set(x + face.sign * (halfW + 0.05), yBase + winH / 2, z + offset)
                frame.rotation.y = face.sign > 0 ? Math.PI / 2 : -Math.PI / 2
              }
              bldg.add(frame)

              const win = new THREE.Mesh(new THREE.PlaneGeometry(winW, winH), winMat)
              win.position.copy(frame.position)
              win.position.y = frame.position.y
              if (face.axis === 'x') {
                win.position.z += face.sign * 0.015
                win.rotation.y = face.sign > 0 ? 0 : Math.PI
              } else {
                win.position.x += face.sign * 0.015
                win.rotation.y = face.sign > 0 ? Math.PI / 2 : -Math.PI / 2
              }
              bldg.add(win)
            }
          }
        }

        const roofMat = new THREE.MeshStandardMaterial({ color: 0x444444, roughness: 0.85, metalness: 0.15 })
        const roof = new THREE.Mesh(new THREE.BoxGeometry(w + 0.4, 0.2, d + 0.4), roofMat)
        roof.position.set(x, terrainY + totalHeight + 0.1, z)
        roof.castShadow = true
        bldg.add(roof)

        const ledgeMat = new THREE.MeshStandardMaterial({ color: palette.trim, roughness: 0.72 })
        const ledge = new THREE.Mesh(new THREE.BoxGeometry(w + 0.6, 0.35, d + 0.6), ledgeMat)
        ledge.position.set(x, terrainY + totalHeight - 0.15, z)
        bldg.add(ledge)

        if (floors >= 3 && Math.random() > 0.4) {
          const acGeo = new THREE.BoxGeometry(0.6, 0.4, 0.4)
          const acMat = new THREE.MeshStandardMaterial({ color: 0x777777, roughness: 0.6, metalness: 0.35 })
          const acCount = 1 + Math.floor(Math.random() * 4)
          for (let i = 0; i < acCount; i++) {
            const ac = new THREE.Mesh(acGeo, acMat)
            ac.position.set(x + (Math.random() - 0.5) * (w - 1), terrainY + totalHeight + 0.4, z + (Math.random() - 0.5) * (d - 1))
            ac.castShadow = true
            bldg.add(ac)
          }
        }

        if (floors >= 2 && Math.random() > 0.3) {
          const towerH = 1.5 + Math.random() * 1.5
          const tower = new THREE.Mesh(
            new THREE.CylinderGeometry(0.25, 0.3, towerH, 8),
            new THREE.MeshStandardMaterial({ color: 0x8b6543, roughness: 0.92 })
          )
          tower.position.set(x + (Math.random() - 0.5) * (w - 1.5), terrainY + totalHeight + towerH / 2, z + (Math.random() - 0.5) * (d - 1.5))
          tower.castShadow = true
          bldg.add(tower)
        }

        this.scene.add(bldg)
      }
    }
  }

  private buildStreetFurniture(): void {
    const benchMat = new THREE.MeshStandardMaterial({ color: 0x5a3a1a, roughness: 0.92 })
    const metalMat = new THREE.MeshStandardMaterial({ color: 0x4a4a4a, roughness: 0.45, metalness: 0.4 })
    const lampMat = new THREE.MeshStandardMaterial({ color: 0x3a3a3a, roughness: 0.35, metalness: 0.55 })
    const lightMat = new THREE.MeshStandardMaterial({
      color: 0xffffcc, emissive: 0xffffaa, emissiveIntensity: 0.6, roughness: 0.25,
    })

    const benchGeo = new THREE.Group()
    const seat = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.06, 0.4), benchMat)
    seat.position.y = 0.45
    benchGeo.add(seat)
    const back = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.3, 0.04), benchMat)
    back.position.set(0, 0.62, -0.18)
    back.rotation.x = -0.1
    benchGeo.add(back)
    for (const sx of [-0.5, 0.5]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.45, 0.35), metalMat)
      leg.position.set(sx, 0.225, 0)
      benchGeo.add(leg)
    }
    const armrest1 = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.12, 0.35), metalMat)
    armrest1.position.set(-0.58, 0.52, 0)
    benchGeo.add(armrest1)
    const armrest2 = armrest1.clone()
    armrest2.position.x = 0.58
    benchGeo.add(armrest2)

    const lampGeo = new THREE.Group()
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.045, 4.2, 10), lampMat)
    pole.position.y = 2.1
    pole.castShadow = true
    lampGeo.add(pole)
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.85, 0.04, 0.04), lampMat)
    arm.position.set(0.425, 4.1, 0)
    lampGeo.add(arm)
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.14, 10, 8), lightMat)
    bulb.position.set(0.85, 4.02, 0)
    lampGeo.add(bulb)
    const lightPoint = new THREE.PointLight(0xffffcc, 0.6, 10)
    lightPoint.position.set(0.85, 3.9, 0)
    lampGeo.add(lightPoint)

    const hydrantGeo = new THREE.Group()
    const hBody = new THREE.Mesh(
      new THREE.CylinderGeometry(0.08, 0.1, 0.5, 10),
      new THREE.MeshStandardMaterial({ color: 0xcc2222, roughness: 0.65, metalness: 0.1 })
    )
    hBody.position.y = 0.25
    hydrantGeo.add(hBody)
    const hTop = new THREE.Mesh(
      new THREE.SphereGeometry(0.09, 10, 8),
      new THREE.MeshStandardMaterial({ color: 0xcc2222, roughness: 0.6, metalness: 0.15 })
    )
    hTop.position.y = 0.52
    hydrantGeo.add(hTop)
    const hNozzle = new THREE.Mesh(
      new THREE.CylinderGeometry(0.025, 0.025, 0.08, 6),
      metalMat
    )
    hNozzle.position.set(0.08, 0.35, 0)
    hNozzle.rotation.z = Math.PI / 2
    hydrantGeo.add(hNozzle)

    const trashGeo = new THREE.Group()
    const tBody = new THREE.Mesh(
      new THREE.CylinderGeometry(0.2, 0.18, 0.6, 10),
      new THREE.MeshStandardMaterial({ color: 0x2a5530, roughness: 0.82 })
    )
    tBody.position.y = 0.3
    trashGeo.add(tBody)
    const tLid = new THREE.Mesh(
      new THREE.CylinderGeometry(0.22, 0.22, 0.04, 10),
      new THREE.MeshStandardMaterial({ color: 0x1a4420, roughness: 0.8 })
    )
    tLid.position.y = 0.62
    trashGeo.add(tLid)

    const furniturePositions = [
      { type: 'bench', x: 7, z: 12, ry: 0 },
      { type: 'bench', x: -7, z: 12, ry: Math.PI },
      { type: 'bench', x: 7, z: -12, ry: 0 },
      { type: 'bench', x: -7, z: -12, ry: Math.PI },
      { type: 'bench', x: 14, z: 7, ry: Math.PI / 2 },
      { type: 'lamp', x: 8, z: 8, ry: 0 },
      { type: 'lamp', x: -8, z: 8, ry: 0 },
      { type: 'lamp', x: 8, z: -8, ry: 0 },
      { type: 'lamp', x: -8, z: -8, ry: 0 },
      { type: 'lamp', x: 20, z: 20, ry: 0 },
      { type: 'lamp', x: -20, z: 20, ry: 0 },
      { type: 'lamp', x: 20, z: -20, ry: 0 },
      { type: 'lamp', x: -20, z: -20, ry: 0 },
      { type: 'hydrant', x: 10, z: 6, ry: 0 },
      { type: 'hydrant', x: -10, z: -6, ry: Math.PI },
      { type: 'trash', x: 12, z: 8, ry: 0 },
      { type: 'trash', x: -12, z: 8, ry: 0 },
      { type: 'trash', x: 12, z: -8, ry: 0 },
    ]

    for (const fp of furniturePositions) {
      let template: THREE.Group
      switch (fp.type) {
        case 'bench': template = benchGeo; break
        case 'lamp': template = lampGeo; break
        case 'hydrant': template = hydrantGeo; break
        case 'trash': template = trashGeo; break
        default: continue
      }

      const clone = template.clone()
      const ty = this.getTerrainHeight(fp.x, fp.z)
      clone.position.set(fp.x, ty, fp.z)
      clone.rotation.y = fp.ry
      this.scene.add(clone)
    }
  }

  updateGrass(time: number): void {
    if (this.grassMaterial) {
      this.grassMaterial.uniforms.uTime.value = time
    }
  }

  private buildWaterFeature(): void {
    const pondCenter = { x: -30, z: 40 }
    const pondRadius = 12
    const pondDepth = -0.5

    const cubeRenderTarget = new THREE.WebGLCubeRenderTarget(256, {
      format: THREE.RGBAFormat,
      generateMipmaps: true,
      minFilter: THREE.LinearMipmapLinearFilter,
    })
    this._waterCubeCamera = new THREE.CubeCamera(0.1, 100, cubeRenderTarget)

    const waterGeo = new THREE.CircleGeometry(pondRadius, 64)
    const waterMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: new THREE.Color(0x1a5276) },
        uDeepColor: { value: new THREE.Color(0x0e2f44) },
        uFoamColor: { value: new THREE.Color(0xaed6f1) },
        uEnvMap: { value: cubeRenderTarget.texture },
        uReflectionStrength: { value: 0.4 },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        varying vec3 vWorldPos;
        varying vec3 vViewDir;
        varying vec3 vNormal;
        void main() {
          vUv = uv;
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWorldPos = wp.xyz;
          vViewDir = normalize(cameraPosition - wp.xyz);
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uTime;
        uniform vec3 uColor;
        uniform vec3 uDeepColor;
        uniform vec3 uFoamColor;
        uniform samplerCube uEnvMap;
        uniform float uReflectionStrength;
        varying vec2 vUv;
        varying vec3 vWorldPos;
        varying vec3 vViewDir;
        varying vec3 vNormal;

        void main() {
          vec2 uv = vUv * 8.0;
          float wave1 = sin(uv.x * 2.0 + uTime * 0.8) * 0.015;
          float wave2 = cos(uv.y * 1.5 + uTime * 0.6) * 0.015;
          float wave3 = sin((uv.x + uv.y) * 1.8 + uTime * 1.1) * 0.008;
          float waves = wave1 + wave2 + wave3;

          float dist = length(vUv - 0.5) * 2.0;
          float depth = smoothstep(0.0, 1.0, dist);
          vec3 color = mix(uDeepColor, uColor, depth + waves);

          float foam = smoothstep(0.88, 1.0, dist) * (0.5 + 0.5 * sin(uTime * 2.0 + dist * 6.0));
          color = mix(color, uFoamColor, foam * 0.35);

          vec3 reflectDir = reflect(-vViewDir, vNormal);
          vec3 envColor = textureCube(uEnvMap, reflectDir).rgb;
          float fresnel = pow(1.0 - max(dot(vViewDir, vNormal), 0.0), 4.0);
          fresnel = clamp(fresnel, 0.0, 1.0);
          color = mix(color, envColor, fresnel * uReflectionStrength);

          float specular = pow(max(dot(reflectDir, normalize(vec3(0.4, 0.8, 0.3))), 0.0), 32.0);
          color += vec3(1.0, 0.98, 0.95) * specular * 0.2;

          float alpha = 0.85 + foam * 0.12;
          gl_FragColor = vec4(color, alpha);
        }
      `,
      transparent: true,
      side: THREE.DoubleSide,
    })

    this.waterMaterial = waterMat
    const water = new THREE.Mesh(waterGeo, waterMat)
    water.rotation.x = -Math.PI / 2
    water.position.set(pondCenter.x, pondDepth + 0.1, pondCenter.z)
    water.name = 'water'
    this.scene.add(water)

    const rimGeo = new THREE.RingGeometry(pondRadius - 0.3, pondRadius + 0.5, 64)
    const rimMat = new THREE.MeshStandardMaterial({
      color: 0x7a6a5a,
      roughness: 0.92,
      side: THREE.DoubleSide,
    })
    const rim = new THREE.Mesh(rimGeo, rimMat)
    rim.rotation.x = -Math.PI / 2
    rim.position.set(pondCenter.x, pondDepth + 0.15, pondCenter.z)
    this.scene.add(rim)

    const rockRingCount = 22
    for (let i = 0; i < rockRingCount; i++) {
      const angle = (i / rockRingCount) * Math.PI * 2
      const r = pondRadius + 0.3 + Math.random() * 0.6
      const rx = pondCenter.x + Math.cos(angle) * r
      const rz = pondCenter.z + Math.sin(angle) * r
      const rSize = 0.2 + Math.random() * 0.35
      const rock = new THREE.Mesh(
        new THREE.DodecahedronGeometry(rSize, 1),
        new THREE.MeshStandardMaterial({ color: 0x666666, roughness: 0.95 })
      )
      rock.position.set(rx, pondDepth + rSize * 0.2, rz)
      rock.rotation.set(Math.random() * 2, Math.random() * 2, 0)
      rock.castShadow = true
      rock.receiveShadow = true
      this.scene.add(rock)
    }

    const lilyCount = 6
    const lilyGeo = new THREE.CircleGeometry(0.28, 14)
    const lilyMat = new THREE.MeshStandardMaterial({
      color: 0x1e7722,
      roughness: 0.55,
      side: THREE.DoubleSide,
    })
    for (let i = 0; i < lilyCount; i++) {
      const angle = Math.random() * Math.PI * 2
      const dist = 3 + Math.random() * (pondRadius - 5)
      const lily = new THREE.Mesh(lilyGeo, lilyMat)
      lily.rotation.x = -Math.PI / 2
      lily.position.set(
        pondCenter.x + Math.cos(angle) * dist,
        pondDepth + 0.12,
        pondCenter.z + Math.sin(angle) * dist
      )
      lily.name = 'lily_pad'
      this.scene.add(lily)
    }

    this._waterCubeCamera.position.set(pondCenter.x, pondDepth + 0.5, pondCenter.z)
    this.scene.add(this._waterCubeCamera)
  }

  private _waterCubeCamera: THREE.CubeCamera | null = null

  private buildParticles(): void {
    const leafCount = 250
    const leafGeo = new THREE.BufferGeometry()
    const leafPositions = new Float32Array(leafCount * 3)
    const leafSizes = new Float32Array(leafCount)
    const leafColors = new Float32Array(leafCount * 3)
    const leafVelocities: Array<{ vx: number; vy: number; vz: number; rotSpeed: number }> = []

    const leafColorOptions = [
      new THREE.Color(0x8B4513),
      new THREE.Color(0x228B22),
      new THREE.Color(0xDAA520),
      new THREE.Color(0x556B2F),
      new THREE.Color(0xCD853F),
    ]

    for (let i = 0; i < leafCount; i++) {
      leafPositions[i * 3] = (Math.random() - 0.5) * 250
      leafPositions[i * 3 + 1] = 3 + Math.random() * 18
      leafPositions[i * 3 + 2] = (Math.random() - 0.5) * 250
      leafSizes[i] = 0.08 + Math.random() * 0.12
      leafVelocities.push({
        vx: (Math.random() - 0.5) * 0.3,
        vy: -0.15 - Math.random() * 0.25,
        vz: (Math.random() - 0.5) * 0.3,
        rotSpeed: (Math.random() - 0.5) * 2,
      })
      const lc = leafColorOptions[Math.floor(Math.random() * leafColorOptions.length)]
      leafColors[i * 3] = lc.r
      leafColors[i * 3 + 1] = lc.g
      leafColors[i * 3 + 2] = lc.b
    }

    leafGeo.setAttribute('position', new THREE.BufferAttribute(leafPositions, 3))
    leafGeo.setAttribute('size', new THREE.BufferAttribute(leafSizes, 1))
    leafGeo.setAttribute('color', new THREE.BufferAttribute(leafColors, 3))

    const leafMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
      },
      vertexShader: /* glsl */ `
        attribute float size;
        attribute vec3 color;
        varying float vAlpha;
        varying vec3 vColor;
        void main() {
          vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * (200.0 / -mvPos.z);
          gl_Position = projectionMatrix * mvPos;
          vAlpha = smoothstep(120.0, 10.0, -mvPos.z);
          vColor = color;
        }
      `,
      fragmentShader: /* glsl */ `
        varying float vAlpha;
        varying vec3 vColor;
        void main() {
          vec2 center = gl_PointCoord - 0.5;
          float d = length(center);
          if (d > 0.5) discard;
          float alpha = vAlpha * (1.0 - d * 2.0) * 0.85;
          gl_FragColor = vec4(vColor, alpha);
        }
      `,
      transparent: true,
      depthWrite: false,
    })

    this.leafParticles = new THREE.Points(leafGeo, leafMat)
    this.leafVelocities = leafVelocities
    this.scene.add(this.leafParticles)

    const dustCount = 300
    const dustGeo = new THREE.BufferGeometry()
    const dustPositions = new Float32Array(dustCount * 3)
    const dustSizes = new Float32Array(dustCount)

    for (let i = 0; i < dustCount; i++) {
      dustPositions[i * 3] = (Math.random() - 0.5) * 100
      dustPositions[i * 3 + 1] = 0.5 + Math.random() * 8
      dustPositions[i * 3 + 2] = (Math.random() - 0.5) * 100
      dustSizes[i] = 0.03 + Math.random() * 0.06
    }

    dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3))
    dustGeo.setAttribute('size', new THREE.BufferAttribute(dustSizes, 1))

    const dustMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
      },
      vertexShader: /* glsl */ `
        attribute float size;
        uniform float uTime;
        varying float vAlpha;
        void main() {
          vec3 pos = position;
          pos.x += sin(uTime * 0.3 + position.z * 0.5) * 0.5;
          pos.y += sin(uTime * 0.2 + position.x * 0.3) * 0.3;
          pos.z += cos(uTime * 0.25 + position.x * 0.4) * 0.4;
          vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);
          gl_PointSize = size * (100.0 / -mvPos.z);
          gl_Position = projectionMatrix * mvPos;
          vAlpha = smoothstep(80.0, 5.0, -mvPos.z) * 0.3;
        }
      `,
      fragmentShader: /* glsl */ `
        varying float vAlpha;
        void main() {
          float d = length(gl_PointCoord - 0.5);
          if (d > 0.5) discard;
          float alpha = vAlpha * (1.0 - d * 2.0);
          gl_FragColor = vec4(0.9, 0.85, 0.7, alpha);
        }
      `,
      transparent: true,
      depthWrite: false,
    })

    this.dustParticles = new THREE.Points(dustGeo, dustMat)
    this.scene.add(this.dustParticles)
  }

  updateParticles(time: number, deltaTime: number): void {
    if (this.leafParticles) {
      (this.leafParticles.material as THREE.ShaderMaterial).uniforms.uTime.value = time
      const positions = this.leafParticles.geometry.attributes.position
      for (let i = 0; i < positions.count; i++) {
        const vel = this.leafVelocities[i]
        let x = positions.getX(i)
        let y = positions.getY(i)
        let z = positions.getZ(i)

        x += vel.vx * deltaTime + Math.sin(time * 0.5 + i) * 0.01
        y += vel.vy * deltaTime
        z += vel.vz * deltaTime + Math.cos(time * 0.4 + i) * 0.01

        if (y < 0) {
          y = 10 + Math.random() * 14
          x = this._playerX + (Math.random() - 0.5) * 120
          z = this._playerZ + (Math.random() - 0.5) * 120
        }

        positions.setXYZ(i, x, y, z)
      }
      positions.needsUpdate = true
    }

    if (this.dustParticles) {
      (this.dustParticles.material as THREE.ShaderMaterial).uniforms.uTime.value = time
    }
  }

  updateWater(time: number, renderer?: THREE.WebGLRenderer): void {
    if (this.waterMaterial) {
      this.waterMaterial.uniforms.uTime.value = time
    }
    if (this._waterCubeCamera && renderer) {
      this._waterCubeCamera.visible = false
      this._waterCubeCamera.update(renderer, this.scene)
      this._waterCubeCamera.visible = true
    }
  }

  setPlayerPosition(x: number, z: number): void {
    this._playerX = x
    this._playerZ = z
  }

  setLODCamera(camera: THREE.Camera): void {
    this.lodCamera = camera
  }

  updateLOD(): void {
    if (!this.lodCamera) return
    const camPos = new THREE.Vector3()
    this.lodCamera.getWorldPosition(camPos)

    this.scene.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        if (child.name === 'procedural_building') {
          const d = camPos.distanceTo(child.position)
          child.visible = d < 180
        } else if (child.name === 'procedural_tree') {
          const d = camPos.distanceTo(child.position)
          child.visible = d < 100
        }
      }
    })

    for (const obj of this.scene.children) {
      if (obj.name === 'procedural_tree') {
        const d = camPos.distanceTo(obj.position)
        obj.visible = d < 100
      }
    }
  }

  // =========================================================================
  // Dynamic OSM Re-fetch (for city travel)
  // =========================================================================

  async reloadOSMBuildings(centerLat: number, centerLon: number): Promise<void> {
    // Remove old OSM buildings
    if (this.osmBuildings) {
      this.scene.remove(this.osmBuildings)
      this.osmBuildings = null
    }

    // Create new loader with updated center
    this.osmLoader = new OSMBuildingLoader(centerLat, centerLon)

    // Fetch new buildings
    const deltaLat = 0.008
    const deltaLon = 0.012
    this.osmBuildings = await this.osmLoader.fetchBuildings(
      centerLat - deltaLat, centerLon - deltaLon,
      centerLat + deltaLat, centerLon + deltaLon
    )
    this.scene.add(this.osmBuildings)

    console.log(`Environment: Reloaded OSM buildings for ${centerLat}, ${centerLon}`)
  }

  // =========================================================================
  // Load Captured 3D Model from Backend
  // =========================================================================

  async loadCapturedModel(
    locationId: number,
    latitude: number,
    longitude: number,
    centerLat: number,
    centerLon: number,
  ): Promise<THREE.Group | null> {
    const url = `https://equity-wrinkle-empirical.ngrok-free.dev/api/locations/${locationId}/model`
    try {
      const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js')
      const loader = new GLTFLoader()
      const gltf = await loader.loadAsync(url)

      const model = gltf.scene
      model.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.castShadow = true
          child.receiveShadow = true
        }
      })

      // Position model at the correct world coordinates
      const latToMeter = 111132.92
      const lonToMeter = 111132.92 * Math.cos(centerLat * Math.PI / 180)
      const x = (longitude - centerLon) * lonToMeter
      const z = -(latitude - centerLat) * latToMeter

      const terrainY = this.getTerrainHeight(x, z)
      model.position.set(x, terrainY, z)
      model.scale.setScalar(1.0)

      model.name = `captured-model-${locationId}`
      this.scene.add(model)

      console.log(`Environment: Loaded captured model for location ${locationId}`)
      return model
    } catch (e) {
      console.warn(`Failed to load captured model ${locationId}:`, e)
      return null
    }
  }
}
