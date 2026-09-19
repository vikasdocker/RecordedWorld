import * as THREE from 'three'

export class CameraController {
  camera: THREE.PerspectiveCamera
  angle: number = 0
  distance: number = 6
  height: number = 4
  private targetX: number = 0
  private targetY: number = 4
  private targetZ: number = 6
  private lookTarget: THREE.Vector3 = new THREE.Vector3(0, 1.2, 0)
  private isMouseDown: boolean = false
  private lastMouseX: number = 0
  private lastMouseY: number = 0
  private pitch: number = 0

  constructor(camera: THREE.PerspectiveCamera) {
    this.camera = camera
    this.setupInput()
  }

  private setupInput(): void {
    window.addEventListener('mousedown', (e) => {
      if (e.button === 0) {
        this.isMouseDown = true
        this.lastMouseX = e.clientX
        this.lastMouseY = e.clientY
      }
    })

    window.addEventListener('mouseup', () => {
      this.isMouseDown = false
    })

    window.addEventListener('mousemove', (e) => {
      if (this.isMouseDown) {
        const dx = e.clientX - this.lastMouseX
        const dy = e.clientY - this.lastMouseY
        this.angle += dx * 0.005
        this.pitch = THREE.MathUtils.clamp(this.pitch + dy * 0.003, -0.5, 0.8)
        this.lastMouseX = e.clientX
        this.lastMouseY = e.clientY
      }
    })

    window.addEventListener('wheel', (e) => {
      this.distance += e.deltaY * 0.005
      this.distance = THREE.MathUtils.clamp(this.distance, 3, 25)
      this.height = this.distance * 0.55
    })

    window.addEventListener('resize', () => {
      this.camera.aspect = window.innerWidth / window.innerHeight
      this.camera.updateProjectionMatrix()
    })
  }

  update(playerPosition: THREE.Vector3, deltaTime: number): void {
    const headY = playerPosition.y + 1.2
    this.targetX = playerPosition.x + Math.sin(this.angle) * this.distance
    this.targetZ = playerPosition.z + Math.cos(this.angle) * this.distance
    this.targetY = playerPosition.y + this.height + this.pitch * this.distance * 0.3

    const lerpFactor = 1 - Math.pow(0.001, deltaTime)
    this.camera.position.x += (this.targetX - this.camera.position.x) * lerpFactor
    this.camera.position.z += (this.targetZ - this.camera.position.z) * lerpFactor
    this.camera.position.y += (this.targetY - this.camera.position.y) * lerpFactor

    this.lookTarget.set(
      playerPosition.x,
      headY,
      playerPosition.z
    )
    this.camera.lookAt(this.lookTarget)
  }
}
