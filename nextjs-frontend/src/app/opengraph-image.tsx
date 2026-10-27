import { ImageResponse } from 'next/og'

export const runtime = 'edge'
export const alt = 'ffinn — describe what your business needs, ffinn ships it. Free, open-source SaaS foundation with an AI build agent.'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

const ink = '#0c0d10'
const paper = '#f7f6f2'
const accent = '#3641f5'
const mute = '#686c77'

const steps = ['Read', 'Plan', 'Write', 'Check', 'Pull request', 'Staging']

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '1200px',
          height: '630px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '64px 72px',
          background: paper,
          fontFamily: 'system-ui, sans-serif',
          color: ink,
          backgroundImage: 'linear-gradient(rgba(12,13,16,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(12,13,16,0.05) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', fontSize: '40px', fontWeight: 700, letterSpacing: '-2px' }}>ffinn</div>
          <div style={{ display: 'flex', fontSize: '20px', color: mute, letterSpacing: '1px' }}>FREE · OPEN SOURCE · MIT</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', fontSize: '84px', fontWeight: 700, letterSpacing: '-4px', lineHeight: 1 }}>
            Describe what your
          </div>
          <div style={{ display: 'flex', fontSize: '84px', fontWeight: 700, letterSpacing: '-4px', lineHeight: 1.05 }}>
            business needs.&nbsp;<span style={{ color: accent, fontStyle: 'italic', fontWeight: 500 }}>ffinn ships it.</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {steps.map(s => (
            <div key={s} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', borderRadius: '999px', background: ink, color: paper, fontSize: '20px' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '999px', background: '#4ade80' }} />
              {s}
            </div>
          ))}
          <div style={{ display: 'flex', alignItems: 'center', padding: '10px 18px', borderRadius: '999px', background: accent, color: '#fff', fontSize: '20px' }}>
            Production: your call
          </div>
        </div>
      </div>
    ),
    { ...size }
  )
}
