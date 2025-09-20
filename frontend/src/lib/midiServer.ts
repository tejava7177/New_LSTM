// src/lib/midiServer.ts
export async function renderMidiOnServer(file: File): Promise<{ wavUrl: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/audio/render-midi', { method: 'POST', body: form });
  if (!res.ok) throw new Error('MIDI render failed');
  return res.json();
}