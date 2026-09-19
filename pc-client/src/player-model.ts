import * as THREE from 'three'

const PLAYER_HEIGHT = 1.7
const BODY_WIDTH = 0.3

export interface ArticulatedPlayer {
  group: THREE.Group
  torso: THREE.Mesh
  head: THREE.Mesh
  leftArm: THREE.Group
  rightArm: THREE.Group
  leftLeg: THREE.Group
  rightLeg: THREE.Group
  leftEye: THREE.Mesh
  rightEye: THREE.Mesh
  hair: THREE.Mesh
  shoes: THREE.Mesh[]
  neck: THREE.Mesh
  leftEar: THREE.Mesh
  rightEar: THREE.Mesh
  nose: THREE.Mesh
  _blendState: {
    prevState: 'idle' | 'walk' | 'run'
    blendProgress: number
    prevPose: {
      leftArmX: number; rightArmX: number
      leftLegX: number; rightLegX: number
      torsoZ: number; headZ: number; posY: number
    }
  }
}

export function createArticulatedPlayer(skinColor = 0xffdbac, shirtColor: string | number = 0x00ff88): ArticulatedPlayer {
  const group = new THREE.Group()

  const skinMat = new THREE.MeshStandardMaterial({
    color: skinColor, roughness: 0.65, metalness: 0.0,
  })
  const shirtMat = new THREE.MeshStandardMaterial({
    color: shirtColor, roughness: 0.82, metalness: 0.0,
  })
  const pantsMat = new THREE.MeshStandardMaterial({
    color: 0x2a3344, roughness: 0.88, metalness: 0.0,
  })
  const shoeMat = new THREE.MeshStandardMaterial({
    color: 0x1a1a1a, roughness: 0.92, metalness: 0.05,
  })
  const hairMat = new THREE.MeshStandardMaterial({
    color: 0x2a1a0a, roughness: 0.95, metalness: 0.0,
  })
  const eyeWhiteMat = new THREE.MeshStandardMaterial({
    color: 0xf8f8f8, roughness: 0.3, metalness: 0.0,
  })
  const eyeIrisMat = new THREE.MeshStandardMaterial({
    color: 0x3a2a1a, roughness: 0.4, metalness: 0.0,
  })

  const neck = new THREE.Mesh(
    new THREE.CylinderGeometry(0.06, 0.07, 0.12, 8),
    skinMat
  )
  neck.position.y = 1.38
  group.add(neck)

  const torso = new THREE.Mesh(
    new THREE.BoxGeometry(BODY_WIDTH, 0.52, 0.18),
    shirtMat
  )
  torso.position.y = 1.1
  torso.castShadow = true
  group.add(torso)

  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.13, 16, 12),
    skinMat
  )
  head.position.y = 1.55
  head.castShadow = true
  group.add(head)

  const hair = new THREE.Mesh(
    new THREE.SphereGeometry(0.14, 14, 10, 0, Math.PI * 2, 0, Math.PI * 0.55),
    hairMat
  )
  hair.position.y = 1.57
  hair.castShadow = true
  group.add(hair)

  const leftEar = new THREE.Mesh(
    new THREE.SphereGeometry(0.03, 6, 6),
    skinMat
  )
  leftEar.position.set(-0.12, 1.53, 0)
  group.add(leftEar)
  const rightEar = new THREE.Mesh(
    new THREE.SphereGeometry(0.03, 6, 6),
    skinMat
  )
  rightEar.position.set(0.12, 1.53, 0)
  group.add(rightEar)

  const nose = new THREE.Mesh(
    new THREE.SphereGeometry(0.02, 6, 4),
    skinMat
  )
  nose.position.set(0, 1.5, 0.12)
  group.add(nose)

  const eyeWhiteGeo = new THREE.SphereGeometry(0.025, 8, 6)
  const leftEyeWhite = new THREE.Mesh(eyeWhiteGeo, eyeWhiteMat)
  leftEyeWhite.position.set(-0.045, 1.55, 0.11)
  group.add(leftEyeWhite)
  const rightEyeWhite = new THREE.Mesh(eyeWhiteGeo, eyeWhiteMat)
  rightEyeWhite.position.set(0.045, 1.55, 0.11)
  group.add(rightEyeWhite)

  const eyeIrisGeo = new THREE.SphereGeometry(0.015, 8, 6)
  const leftEye = new THREE.Mesh(eyeIrisGeo, eyeIrisMat)
  leftEye.position.set(-0.045, 1.55, 0.13)
  group.add(leftEye)
  const rightEye = new THREE.Mesh(eyeIrisGeo, eyeIrisMat)
  rightEye.position.set(0.045, 1.55, 0.13)
  group.add(rightEye)

  const mouthGeo = new THREE.BoxGeometry(0.05, 0.01, 0.01)
  const mouthMat = new THREE.MeshStandardMaterial({ color: 0xcc8877, roughness: 0.6 })
  const mouth = new THREE.Mesh(mouthGeo, mouthMat)
  mouth.position.set(0, 1.47, 0.12)
  group.add(mouth)

  const armGeo = new THREE.BoxGeometry(0.09, 0.42, 0.09)

  const leftArm = new THREE.Group()
  const leftArmMesh = new THREE.Mesh(armGeo, shirtMat)
  leftArmMesh.position.y = -0.21
  leftArmMesh.castShadow = true
  leftArm.add(leftArmMesh)
  const leftHand = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 6), skinMat)
  leftHand.position.y = -0.44
  leftArm.add(leftHand)
  leftArm.position.set(-BODY_WIDTH / 2 - 0.065, 1.28, 0)
  group.add(leftArm)

  const rightArm = new THREE.Group()
  const rightArmMesh = new THREE.Mesh(armGeo, shirtMat)
  rightArmMesh.position.y = -0.21
  rightArmMesh.castShadow = true
  rightArm.add(rightArmMesh)
  const rightHand = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 6), skinMat)
  rightHand.position.y = -0.44
  rightArm.add(rightHand)
  rightArm.position.set(BODY_WIDTH / 2 + 0.065, 1.28, 0)
  group.add(rightArm)

  const legGeo = new THREE.BoxGeometry(0.11, 0.48, 0.11)

  const leftLeg = new THREE.Group()
  const leftLegMesh = new THREE.Mesh(legGeo, pantsMat)
  leftLegMesh.position.y = -0.24
  leftLegMesh.castShadow = true
  leftLeg.add(leftLegMesh)
  const leftShoe = new THREE.Mesh(
    new THREE.BoxGeometry(0.12, 0.07, 0.17),
    shoeMat
  )
  leftShoe.position.set(0, -0.51, 0.02)
  leftLeg.add(leftShoe)
  leftLeg.position.set(-0.08, 0.82, 0)
  group.add(leftLeg)

  const rightLeg = new THREE.Group()
  const rightLegMesh = new THREE.Mesh(legGeo, pantsMat)
  rightLegMesh.position.y = -0.24
  rightLegMesh.castShadow = true
  rightLeg.add(rightLegMesh)
  const rightShoe = new THREE.Mesh(
    new THREE.BoxGeometry(0.12, 0.07, 0.17),
    shoeMat
  )
  rightShoe.position.set(0, -0.51, 0.02)
  rightLeg.add(rightShoe)
  rightLeg.position.set(0.08, 0.82, 0)
  group.add(rightLeg)

  return {
    group,
    torso,
    head,
    leftArm,
    rightArm,
    leftLeg,
    rightLeg,
    leftEye,
    rightEye,
    hair,
    shoes: [leftShoe, rightShoe],
    neck,
    leftEar,
    rightEar,
    nose,
    _blendState: {
      prevState: 'idle',
      blendProgress: 1,
      prevPose: {
        leftArmX: 0, rightArmX: 0,
        leftLegX: 0, rightLegX: 0,
        torsoZ: 0, headZ: 0, posY: 0,
      },
    },
  }
}

function computePose(
  state: 'idle' | 'walk' | 'run',
  animTime: number
): { leftArmX: number; rightArmX: number; leftLegX: number; rightLegX: number; torsoZ: number; headZ: number; posY: number } {
  switch (state) {
    case 'walk':
      return {
        leftArmX: Math.sin(animTime * 8) * 0.6,
        rightArmX: -Math.sin(animTime * 8) * 0.6,
        leftLegX: -Math.sin(animTime * 8) * 0.5,
        rightLegX: Math.sin(animTime * 8) * 0.5,
        torsoZ: Math.sin(animTime * 8) * 0.03,
        headZ: Math.sin(animTime * 8) * 0.02,
        posY: Math.sin(animTime * 16) * 0.015,
      }
    case 'run':
      return {
        leftArmX: Math.sin(animTime * 12) * 0.9,
        rightArmX: -Math.sin(animTime * 12) * 0.9,
        leftLegX: -Math.sin(animTime * 12) * 0.8,
        rightLegX: Math.sin(animTime * 12) * 0.8,
        torsoZ: Math.sin(animTime * 12) * 0.05,
        headZ: Math.sin(animTime * 12) * 0.03,
        posY: Math.abs(Math.sin(animTime * 24)) * 0.04,
      }
    default:
      return {
        leftArmX: 0,
        rightArmX: 0,
        leftLegX: 0,
        rightLegX: 0,
        torsoZ: 0,
        headZ: 0,
        posY: Math.sin(animTime * 2) * 0.005,
      }
  }
}

const BLEND_DURATION = 0.25

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * Math.min(1, Math.max(0, t))
}

function lerpPose(
  a: { leftArmX: number; rightArmX: number; leftLegX: number; rightLegX: number; torsoZ: number; headZ: number; posY: number },
  b: { leftArmX: number; rightArmX: number; leftLegX: number; rightLegX: number; torsoZ: number; headZ: number; posY: number },
  t: number
) {
  return {
    leftArmX: lerp(a.leftArmX, b.leftArmX, t),
    rightArmX: lerp(a.rightArmX, b.rightArmX, t),
    leftLegX: lerp(a.leftLegX, b.leftLegX, t),
    rightLegX: lerp(a.rightLegX, b.rightLegX, t),
    torsoZ: lerp(a.torsoZ, b.torsoZ, t),
    headZ: lerp(a.headZ, b.headZ, t),
    posY: lerp(a.posY, b.posY, t),
  }
}

export function animatePlayer(
  player: ArticulatedPlayer,
  animTime: number,
  state: 'idle' | 'walk' | 'run',
  deltaTime: number
): void {
  const bs = player._blendState

  if (state !== bs.prevState) {
    bs.prevPose = {
      leftArmX: player.leftArm.rotation.x,
      rightArmX: player.rightArm.rotation.x,
      leftLegX: player.leftLeg.rotation.x,
      rightLegX: player.rightLeg.rotation.x,
      torsoZ: player.torso.rotation.z,
      headZ: player.head.rotation.z,
      posY: player.group.position.y,
    }
    bs.blendProgress = 0
    bs.prevState = state
  }

  if (bs.blendProgress < 1) {
    bs.blendProgress = Math.min(1, bs.blendProgress + deltaTime / BLEND_DURATION)
  }

  const target = computePose(state, animTime)
  const from = bs.prevPose

  let final: typeof target
  if (bs.blendProgress >= 1) {
    final = target
  } else {
    const t = bs.blendProgress < 0.5
      ? 2 * bs.blendProgress * bs.blendProgress
      : 1 - Math.pow(-2 * bs.blendProgress + 2, 2) / 2
    final = lerpPose(from, target, t)
  }

  player.leftArm.rotation.x = final.leftArmX
  player.rightArm.rotation.x = final.rightArmX
  player.leftLeg.rotation.x = final.leftLegX
  player.rightLeg.rotation.x = final.rightLegX
  player.torso.rotation.z = final.torsoZ
  player.head.rotation.z = final.headZ
  player.group.position.y = final.posY
}

export function createLabel(text: string, color?: string, visibility?: string): THREE.Sprite {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 64
  const ctx = canvas.getContext('2d')!

  ctx.fillStyle = 'rgba(0, 0, 0, 0.8)'
  ctx.beginPath()
  ctx.roundRect(2, 2, 252, 60, 10)
  ctx.fill()

  ctx.strokeStyle = color || '#00ff88'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.roundRect(2, 2, 252, 60, 10)
  ctx.stroke()

  ctx.fillStyle = color || '#00ff88'
  ctx.font = 'bold 22px monospace'
  ctx.textAlign = 'center'

  let displayName = text
  if (visibility === 'hidden') displayName = '???'
  else if (visibility === 'friends_only') displayName = text + ' \uD83D\uDD12'
  ctx.fillText(displayName, 128, 40)

  const texture = new THREE.CanvasTexture(canvas)
  texture.minFilter = THREE.LinearFilter
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true })
  const sprite = new THREE.Sprite(material)
  sprite.scale.set(2, 0.5, 1)
  sprite.position.y = 2.0
  return sprite
}
