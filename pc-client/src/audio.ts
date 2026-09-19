export class AudioSystem {
  private ctx: AudioContext | null = null
  private masterGain: GainNode | null = null
  private windOsc: OscillatorNode | null = null
  private cityOsc: OscillatorNode | null = null
  private birdInterval: ReturnType<typeof setInterval> | null = null
  private initialized = false

  constructor() {
    this.init()
  }

  private init(): void {
    try {
      this.ctx = new AudioContext()
      this.masterGain = this.ctx.createGain()
      this.masterGain.gain.value = 0.15
      this.masterGain.connect(this.ctx.destination)

      this.startWind()
      this.startCityHum()
      this.startBirds()

      document.addEventListener('click', () => {
        if (this.ctx?.state === 'suspended') this.ctx.resume()
      }, { once: true })

      this.initialized = true
    } catch {
      console.warn('AudioSystem: Web Audio API not available')
    }
  }

  private startWind(): void {
    if (!this.ctx || !this.masterGain) return
    const bufferSize = 2 * this.ctx.sampleRate
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate)
    const data = buffer.getChannelData(0)
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * 0.5
    }
    const source = this.ctx.createBufferSource()
    source.buffer = buffer
    source.loop = true

    const filter = this.ctx.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.value = 400
    filter.Q.value = 0.5

    const gain = this.ctx.createGain()
    gain.gain.value = 0.3

    source.connect(filter)
    filter.connect(gain)
    gain.connect(this.masterGain)
    source.start()

    const lfo = this.ctx.createOscillator()
    lfo.frequency.value = 0.15
    const lfoGain = this.ctx.createGain()
    lfoGain.gain.value = 150
    lfo.connect(lfoGain)
    lfoGain.connect(filter.frequency)
    lfo.start()
  }

  private startCityHum(): void {
    if (!this.ctx || !this.masterGain) return
    this.cityOsc = this.ctx.createOscillator()
    this.cityOsc.type = 'sawtooth'
    this.cityOsc.frequency.value = 55

    const filter = this.ctx.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.value = 120

    const gain = this.ctx.createGain()
    gain.gain.value = 0.06

    this.cityOsc.connect(filter)
    filter.connect(gain)
    gain.connect(this.masterGain)
    this.cityOsc.start()
  }

  private startBirds(): void {
    if (!this.ctx || !this.masterGain) return
    this.birdInterval = setInterval(() => {
      if (!this.ctx || !this.masterGain || this.ctx.state !== 'running') return
      if (Math.random() > 0.3) return
      this.chirp()
    }, 2000)
  }

  private chirp(): void {
    if (!this.ctx || !this.masterGain) return
    const now = this.ctx.currentTime
    const osc = this.ctx.createOscillator()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(1800 + Math.random() * 1200, now)
    osc.frequency.exponentialRampToValueAtTime(2200 + Math.random() * 800, now + 0.05)
    osc.frequency.exponentialRampToValueAtTime(1400 + Math.random() * 600, now + 0.1)

    const gain = this.ctx.createGain()
    gain.gain.setValueAtTime(0, now)
    gain.gain.linearRampToValueAtTime(0.08, now + 0.02)
    gain.gain.linearRampToValueAtTime(0, now + 0.12)

    osc.connect(gain)
    gain.connect(this.masterGain)
    osc.start(now)
    osc.stop(now + 0.15)
  }

  setVolume(v: number): void {
    if (this.masterGain) {
      this.masterGain.gain.value = Math.max(0, Math.min(1, v))
    }
  }

  dispose(): void {
    if (this.birdInterval) clearInterval(this.birdInterval)
    if (this.ctx) this.ctx.close()
  }
}
