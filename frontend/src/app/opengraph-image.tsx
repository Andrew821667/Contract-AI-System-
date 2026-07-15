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
          background: 'linear-gradient(135deg, #08111f 0%, #0f1b2e 62%, #172033 100%)',
          color: '#fff',
          fontFamily: 'Arial',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          <div style={{ display: 'flex', width: 54, height: 54, borderRadius: 14, border: '2px solid #67e8f9', color: '#fbbf24', alignItems: 'center', justifyContent: 'center', fontSize: 34, fontWeight: 800 }}>✓</div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', fontSize: 30, fontWeight: 700 }}>Contract AI</div>
            <div style={{ display: 'flex', fontSize: 16, color: '#67e8f9', letterSpacing: 4 }}>BY AI VERDICT</div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ display: 'flex', maxWidth: 980, fontSize: 66, fontWeight: 700, lineHeight: 1.08 }}>
            Анализ договоров с ИИ
          </div>
          <div style={{ display: 'flex', maxWidth: 980, fontSize: 31, color: '#d6d3d1' }}>
            Риски, спорные условия и рекомендации по правкам
          </div>
        </div>
        <div style={{ display: 'flex', fontSize: 25, color: '#fbbf24' }}>contract.ai-verdict.ru</div>
      </div>
    ),
    size,
  )
}
