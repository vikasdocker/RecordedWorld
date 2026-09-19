import * as THREE from 'three'
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js'
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js'
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js'
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js'

const VignetteShader = {
  uniforms: {
    tDiffuse: { value: null },
    offset: { value: 1.0 },
    darkness: { value: 1.2 },
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float offset;
    uniform float darkness;
    varying vec2 vUv;
    void main() {
      vec4 texel = texture2D(tDiffuse, vUv);
      vec2 uv = (vUv - vec2(0.5)) * vec2(offset);
      float vignette = 1.0 - dot(uv, uv);
      texel.rgb *= mix(1.0 - darkness, 1.0, clamp(vignette, 0.0, 1.0));
      gl_FragColor = texel;
    }
  `,
}

const ColorGradingShader = {
  uniforms: {
    tDiffuse: { value: null },
    saturation: { value: 1.15 },
    contrast: { value: 1.08 },
    brightness: { value: 1.03 },
    temperature: { value: 0.02 },
    tint: { value: 0.0 },
    shadows: { value: new THREE.Color(0.0, 0.0, 0.02) },
    highlights: { value: new THREE.Color(0.01, 0.005, 0.0) },
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float saturation;
    uniform float contrast;
    uniform float brightness;
    uniform float temperature;
    uniform float tint;
    uniform vec3 shadows;
    uniform vec3 highlights;
    varying vec2 vUv;

    vec3 rgb2hsv(vec3 c) {
      vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
      vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
      vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
      float d = q.x - min(q.w, q.y);
      float e = 1.0e-10;
      return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
    }

    vec3 hsv2rgb(vec3 c) {
      vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
      vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
      return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }

    void main() {
      vec4 color = texture2D(tDiffuse, vUv);
      color.rgb *= brightness;

      color.r += temperature * 0.1;
      color.b -= temperature * 0.1;
      color.g += tint * 0.05;

      float luminance = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));
      vec3 shadowsColor = mix(vec3(0.0), shadows, smoothstep(0.0, 0.3, luminance));
      vec3 highlightsColor = mix(vec3(0.0), highlights, smoothstep(0.3, 1.0, luminance));
      color.rgb += shadowsColor + highlightsColor;

      vec3 hsv = rgb2hsv(color.rgb);
      hsv.y *= saturation;
      color.rgb = hsv2rgb(hsv);

      color.rgb = (color.rgb - 0.5) * contrast + 0.5;

      gl_FragColor = color;
    }
  `,
}

export class PostProcessing {
  composer: EffectComposer
  private ssaoPass: SSAOPass
  private vignettePass: ShaderPass
  private colorPass: ShaderPass

  constructor(
    renderer: THREE.WebGLRenderer,
    scene: THREE.Scene,
    camera: THREE.PerspectiveCamera,
    width: number,
    height: number,
  ) {
    this.composer = new EffectComposer(renderer)

    const renderPass = new RenderPass(scene, camera)
    this.composer.addPass(renderPass)

    this.ssaoPass = new SSAOPass(scene, camera, width, height)
    this.ssaoPass.kernelRadius = 0.8
    this.ssaoPass.minDistance = 0.0005
    this.ssaoPass.maxDistance = 0.12
    this.ssaoPass.output = SSAOPass.OUTPUT.Default
    this.composer.addPass(this.ssaoPass)

    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(width, height),
      0.2,
      0.5,
      0.82,
    )
    this.composer.addPass(bloomPass)

    const smaaPass = new SMAAPass(width, height)
    this.composer.addPass(smaaPass)

    this.vignettePass = new ShaderPass(VignetteShader)
    this.vignettePass.uniforms['offset'].value = 1.2
    this.vignettePass.uniforms['darkness'].value = 0.8
    this.composer.addPass(this.vignettePass)

    this.colorPass = new ShaderPass(ColorGradingShader)
    this.composer.addPass(this.colorPass)

    const outputPass = new OutputPass()
    this.composer.addPass(outputPass)
  }

  resize(width: number, height: number): void {
    this.composer.setSize(width, height)
    this.ssaoPass.setSize(width, height)
  }

  render(): void {
    this.composer.render()
  }
}
