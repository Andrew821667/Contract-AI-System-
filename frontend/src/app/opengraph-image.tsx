import { ImageResponse } from 'next/og'

export const runtime = 'edge'
export const alt = 'Contract AI System — анализ договоров с ИИ'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '58px',
          background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 65%, #433821 100%)',
          color: '#fff',
          fontFamily: 'Arial',
        }}
      >
        <div style={{ display: 'flex', fontSize: 30, color: '#f5d898' }}>Contract AI System</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ display: 'flex', maxWidth: 980, fontSize: 66, fontWeight: 700, lineHeight: 1.08 }}>
            Анализ договоров с ИИ
          </div>
          <div style={{ display: 'flex', maxWidth: 980, fontSize: 31, color: '#d6d3d1' }}>
            Риски, спорные условия и рекомендации по правкам
          </div>
        </div>
        <div style={{ display: 'flex', fontSize: 25, color: '#f5d898' }}>contract.ai-verdict.ru</div>
      </div>
    ),
    size,
  )
}
