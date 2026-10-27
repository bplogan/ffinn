import { ImageResponse } from 'next/og'

// Square home-screen / bookmark icon, drawn like the logo mark in the share image.
export const size = { width: 180, height: 180 }
export const contentType = 'image/png'

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          color: 'white',
          fontSize: 120,
          fontWeight: 800,
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        f
      </div>
    ),
    { ...size },
  )
}
