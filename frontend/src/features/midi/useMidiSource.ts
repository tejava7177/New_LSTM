import { useEffect, useMemo, useState } from 'react'
import { Midi } from '@tonejs/midi'
import type { ChordCue } from '../../lib/midiCues'
import { extractChordCuesFromMidi } from '../../lib/midiCues'
import { midiUrl, wavUrl } from '../../lib/tracks'
import { renderMidiOnServer } from '../../lib/midiServer'

type TrackMeta = { name: string; channel?: number; instrument?: string; notes: number }
type NavState = {
  source?: 'predict' | 'manual';
  jobId?: string;
  progression?: string[];
  tempo?: number;
  timeSig?: [number, number];
  preRollBeats?: number;
  barsPerChord?: number;
  midiUrl?: string;
  wavUrl?: string;
}

export function useMidiSource(navState: NavState) {
  const [midiFile, setMidiFile] = useState<File | null>(null)
  const [midiAudioUrl, setMidiAudioUrl] = useState<string | null>(null)
  const [midiBuffer, setMidiBuffer] = useState<AudioBuffer | null>(null)
  const [midiTracks, setMidiTracks] = useState<TrackMeta[]>([])
  const [tempoBpm, setTempoBpm] = useState<number>(navState.tempo ?? 100)
  const [timeSig, setTimeSig] = useState<[number, number]>(navState.timeSig ?? [4, 4])
  const [cuesFromMidi, setCuesFromMidi] = useState<ChordCue[]>([])
  const [rendering, setRendering] = useState(false)

  async function bootstrapFromJob(jobId: string) {
    try {
      const midiArr = await (await fetch(navState.midiUrl ?? midiUrl(jobId))).arrayBuffer()
      const cues = await extractChordCuesFromMidi(midiArr, { preRollSec: 0, windowBeats: 1 })
      if (cues.length) setCuesFromMidi(cues)
      const midi = new Midi(midiArr)
      setTempoBpm(navState.tempo ?? (midi.header.tempos?.[0]?.bpm ?? tempoBpm))
      const ts = (midi.header.timeSignatures?.[0]?.timeSignature as number[]) || [4, 4]
      setTimeSig([ts[0] ?? 4, ts[1] ?? 4])
      setMidiTracks(midi.tracks.map(t => ({
        name: t.name || '(no name)',
        channel: t.channel,
        instrument: t.instrument?.name || (t.instrument?.number != null ? `program ${t.instrument.number}` : undefined),
        notes: t.notes.length,
      })))
    } catch {}
    const wurl = navState.wavUrl ?? wavUrl(jobId)
    setMidiAudioUrl(wurl)
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    try {
      const wArr = await (await fetch(wurl)).arrayBuffer()
      setMidiBuffer(await ctx.decodeAudioData(wArr.slice(0)))
    } finally { await ctx.close() }
  }

  async function handleMidiFile(file: File) {
    setMidiFile(file)
    setMidiAudioUrl(null); setMidiBuffer(null)
    setMidiTracks([]); setCuesFromMidi([])
    setRendering(true)
    try {
      const arr = await file.arrayBuffer()
      const midi = new Midi(arr)
      const bpm = midi.header.tempos?.[0]?.bpm ?? 100
      setTempoBpm(bpm)
      const ts = (midi.header.timeSignatures?.[0]?.timeSignature as number[]) || [4, 4]
      setTimeSig([ts[0] ?? 4, ts[1] ?? 4])
      setMidiTracks(midi.tracks.map(t => ({
        name: t.name || '(no name)',
        channel: t.channel,
        instrument: t.instrument?.name || (t.instrument?.number != null ? `program ${t.instrument.number}` : undefined),
        notes: t.notes.length,
      })))

      const cues = await extractChordCuesFromMidi(arr, { preRollSec: 0, windowBeats: 1 })
      setCuesFromMidi(cues)

      const { wavUrl: wurl } = await renderMidiOnServer(file)
      setMidiAudioUrl(wurl)

      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const wavArr = await (await fetch(wurl)).arrayBuffer()
      setMidiBuffer(await ctx.decodeAudioData(wavArr.slice(0)))
      await ctx.close()
    } finally {
      setRendering(false)
    }
  }

  return {
    midiFile, setMidiFile,
    midiAudioUrl, midiBuffer,
    midiTracks, tempoBpm, timeSig,
    cuesFromMidi, setTempoBpm, setTimeSig,
    rendering,
    handleMidiFile, bootstrapFromJob
  }
}
