// src/lib/tracks.ts
export type GeneratePayload = {
  genre: string;
  progression: string[];
  tempo: number;
  options?: Record<string, any>;
};

export type JobResponse = { jobId: string };
export type StatusResponse = { status: 'PENDING'|'RUNNING'|'DONE'|'ERROR'; progress: number };

export async function generateTrack(body: GeneratePayload): Promise<JobResponse> {
  const res = await fetch('/api/tracks/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`generate failed: ${res.status}`);
  return res.json();
}

export async function getTrackStatus(jobId: string): Promise<StatusResponse> {
  const res = await fetch(`/api/tracks/status/${jobId}`);
  if (!res.ok) throw new Error(`status failed: ${res.status}`);
  return res.json();
}

export const midiUrl   = (jobId: string) => `/api/tracks/${jobId}/midi`;
export const xmlUrl    = (jobId: string) => `/api/tracks/${jobId}/musicxml`;