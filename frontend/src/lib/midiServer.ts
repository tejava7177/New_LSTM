// src/lib/midiServer.ts
export async function renderMidiOnServer(file: File): Promise<{ wavUrl: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/audio/render-midi', { method: 'POST', body: form });
  if (!res.ok) throw new Error(`MIDI render failed: ${res.status}`);
  return res.json();
}

export async function ensureWavForJob(jobId: string): Promise<string> {
  // 1) 먼저 tracks의 wav 엔드포인트가 이미 준비돼 있는지 확인
  const url = `/api/tracks/${jobId}/wav`;
  const head = await fetch(url, { method: 'HEAD' });
  if (head.ok) return url;

  // 2) 준비 안돼 있으면 서버에 jobId로 렌더 요청(파일 업로드 없음)
  const res = await fetch(`/api/audio/render-midi?jobId=${encodeURIComponent(jobId)}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`render-by-job failed: ${res.status}`);
  const json = await res.json();
  return json.wavUrl || url;
}