// src/pages/UploadList.tsx
import { useEffect, useState } from 'react'
import { fetchList, deleteFile } from '../lib/api'

/** 백엔드 /api/audio/list 응답 구조 */
interface FileInfo {
  id: string
  size: number        // bytes
  created: string     // ISO timestamp
}

export default function UploadList() {
  const [files, setFiles] = useState<FileInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchList()
      .then(list => setFiles(list))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p>로딩 중…</p>
  if (!files.length) return <p>업로드된 파일이 없습니다.</p>

  return (
    <table>
      <thead>
        <tr>
          <th>파일 ID</th>
          <th>크기</th>
          <th>업로드 시각</th>
          <th>관리</th>
        </tr>
      </thead>
      <tbody>
        {files.map(f => (
          <tr key={f.id}>
            <td>
              <a href={`/api/audio/${f.id}`} target="_blank" rel="noreferrer">
                {f.id.slice(0, 12)}…
              </a>
            </td>
            <td>{(f.size / 1024).toFixed(1)} KB</td>
            <td>{new Date(f.created).toLocaleString()}</td>
            <td>
              <button
                onClick={() =>
                  deleteFile(f.id).then(() =>
                    setFiles(prev => prev.filter(x => x.id !== f.id))
                  )
                }
              >
                🗑
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}