import DeviceSelect from '../components/DeviceSelect'
import Recorder from '../components/Recorder'
import { useState } from 'react'

export default function RecordPage() {
  const [selectedId, setSelectedId] = useState<string>('')

  return (
    <div>
      <div style={{display:'flex', gap:8, alignItems:'center'}}>
        <DeviceSelect value={selectedId} onChange={setSelectedId} />
      </div>
      <div style={{marginTop:12}}>
        <Recorder deviceId={selectedId} />
      </div>
    </div>
  )
}
