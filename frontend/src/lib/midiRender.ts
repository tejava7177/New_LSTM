// src/lib/midiRender.ts
import { Midi } from '@tonejs/midi'
import * as Soundfont from 'soundfont-player'
import { programToSfName } from './gm'

type Options = {
  sampleRate?: number
  soundfont?: 'MusyngKite' | 'FluidR3_GM'
  format?: 'mp3' | 'ogg'
  gain?: number
}

const CDN = 'https://gleitz.github.io/midi-js-soundfonts'
const nameToUrl = (base: string) => (name: string, sf: string, fmt: string) =>
  `${base}/${sf}/${name}-${fmt}.js`

// MIDI number -> "C#4"
function midiToNoteName(midi: number) {
  const names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
  const n = midi % 12, o = Math.floor(midi / 12) - 1
  return `${names[n]}${o}`
}

// === 새로 추가: 세트에 악기가 실제 있는지 names.json으로 확인 ===
const namesCache = new Map<string, Set<string>>()
async function hasInstrumentInSet(sf: 'MusyngKite'|'FluidR3_GM', name: string) {
  let set = namesCache.get(sf)
  if (!set) {
    const res = await fetch(`${CDN}/${sf}/names.json`)
    const arr = (await res.json()) as string[]
    set = new Set(arr)
    namesCache.set(sf, set)
  }
  return set.has(name)
}

export async function renderMidiToBuffer(
  midiArrayBuffer: ArrayBuffer,
  {
    sampleRate = 48000,
    soundfont = 'MusyngKite',
    format = 'mp3',
    gain = 1.0,
  }: Options = {}
): Promise<AudioBuffer> {
  const midi = new Midi(midiArrayBuffer)
  const duration = Math.max(0.001, midi.duration)
  const ctx = new OfflineAudioContext(2, Math.ceil(duration * sampleRate), sampleRate)

  const instCache = new Map<string, any>()
  async function loadInstrument(name: string, sf: 'MusyngKite'|'FluidR3_GM') {
    // 요청하려는 세트에 해당 악기가 없으면 세트/이름을 유효한 것으로 변경
    const exists = await hasInstrumentInSet(sf, name)
    let sfToUse: 'MusyngKite'|'FluidR3_GM' = sf
    let nameToUse = name

    if (!exists) {
      // 1) 같은 세트에 없으면 MusyngKite로 폴백
      if (await hasInstrumentInSet('MusyngKite', name)) {
        sfToUse = 'MusyngKite'
        nameToUse = name
      } else {
        // 2) 최후의 보루: 피아노
        sfToUse = sf
        nameToUse = 'acoustic_grand_piano'
      }
    }

    const key = `${sfToUse}:${format}:${nameToUse}`
    if (instCache.has(key)) return instCache.get(key)

    const inst = await Soundfont.instrument(ctx as unknown as AudioContext, nameToUse as any, {
      soundfont: sfToUse,
      format,
      nameToUrl: nameToUrl(CDN),
      gain,
    })
    instCache.set(key, inst)
    return inst
  }

  for (const track of midi.tracks) {
    const ch = track.channel ?? 0
    const isDrum = ch === 9 // GM 채널 10

    // 드럼은 무조건 MusyngKite/percussion (FluidR3_GM에는 없음)
    const program = track.instrument?.number ?? 0
    const instName = isDrum ? 'percussion' : (programToSfName(program) || 'acoustic_grand_piano')
    const setToUse: 'MusyngKite'|'FluidR3_GM' = isDrum ? 'MusyngKite' : soundfont

    const inst = await loadInstrument(instName, setToUse)

    for (const n of track.notes) {
      const note = midiToNoteName(n.midi)
      ;(inst as any).play(note, n.time, { duration: n.duration, gain: n.velocity })
    }
  }

  return ctx.startRendering()
}