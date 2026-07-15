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
          justifyContent: 'center',
          gap: 22,
          padding: '58px',
          background: 'linear-gradient(135deg, #08111f, #0f1b2e)',
          color: '#fff',
          fontFamily: 'Arial',
        }}
      >
        <div style={{ display: 'flex', fontSize: 28, color: '#67e8f9' }}>Contract AI · by AI Verdict</div>
        <div style={{ display: 'flex', fontSize: 64, fontWeight: 700 }}>Анализ договоров с ИИ</div>
        <div style={{ display: 'flex', fontSize: 30, color: '#fbbf24' }}>3 договора в месяц бесплатно</div>
      </div>
    ),
    size,
  )
}
