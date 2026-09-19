import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

interface BuildingTemplate {
  name: string
  type: string
  width: number
  depth: number
  floors: number
  style: string
  file: string
  scene?: THREE.Group
}

interface TreeTemplate {
  name: string
  type: string
  height: number
  canopy_radius?: number
  file: string
  scene?: THREE.Group
}

interface AssetManifest {
  version: number
  buildings?: BuildingTemplate[]
  trees?: TreeTemplate[]
}

export class AssetLoader {
  private loader: GLTFLoader
  private buildingTemplates: BuildingTemplate[] = []
  private treeTemplates: TreeTemplate[] = []
  private loaded = false
  private basePath: string

  constructor() {
    this.loader = new GLTFLoader()
    this.basePath = '/models/'
  }

  async loadAll(): Promise<void> {
    try {
      const [buildingsResp, treesResp] = await Promise.allSettled([
        fetch(`${this.basePath}buildings.json`),
        fetch(`${this.basePath}trees.json`),
      ])

      if (buildingsResp.status === 'fulfilled' && buildingsResp.value.ok) {
        const data: AssetManifest = await buildingsResp.value.json()
        this.buildingTemplates = data.buildings || []
        await this.loadBuildingModels()
      }

      if (treesResp.status === 'fulfilled' && treesResp.value.ok) {
        const data: AssetManifest = await treesResp.value.json()
        this.treeTemplates = data.trees || []
        await this.loadTreeModels()
      }

      this.loaded = true
      console.log(`AssetLoader: ${this.buildingTemplates.length} buildings, ${this.treeTemplates.length} trees loaded`)
    } catch (e) {
      console.warn('AssetLoader: Failed to load manifests, using procedural fallback')
      this.loaded = false
    }
  }

  private async loadBuildingModels(): Promise<void> {
    const promises = this.buildingTemplates.map(async (tmpl) => {
      try {
        const gltf = await this.loader.loadAsync(`${this.basePath}${tmpl.file}`)
        tmpl.scene = gltf.scene
        tmpl.scene.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.castShadow = true
            child.receiveShadow = true
          }
        })
      } catch (e) {
        console.warn(`Failed to load building: ${tmpl.file}`)
      }
    })
    await Promise.all(promises)
  }

  private async loadTreeModels(): Promise<void> {
    const promises = this.treeTemplates.map(async (tmpl) => {
      try {
        const gltf = await this.loader.loadAsync(`${this.basePath}${tmpl.file}`)
        tmpl.scene = gltf.scene
        tmpl.scene.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.castShadow = true
          }
        })
      } catch (e) {
        console.warn(`Failed to load tree: ${tmpl.file}`)
      }
    })
    await Promise.all(promises)
  }

  isLoaded(): boolean {
    return this.loaded && (this.buildingTemplates.length > 0 || this.treeTemplates.length > 0)
  }

  getRandomBuilding(): THREE.Group | null {
    const loaded = this.buildingTemplates.filter(t => t.scene)
    if (loaded.length === 0) return null
    const tmpl = loaded[Math.floor(Math.random() * loaded.length)]
    return tmpl.scene!.clone()
  }

  getRandomTree(type?: string): THREE.Group | null {
    let candidates = this.treeTemplates.filter(t => t.scene)
    if (type) {
      const filtered = candidates.filter(t => t.type === type)
      if (filtered.length > 0) candidates = filtered
    }
    if (candidates.length === 0) return null
    const tmpl = candidates[Math.floor(Math.random() * candidates.length)]
    return tmpl.scene!.clone()
  }

  getBuildingCount(): number {
    return this.buildingTemplates.filter(t => t.scene).length
  }

  getTreeCount(): number {
    return this.treeTemplates.filter(t => t.scene).length
  }
}
