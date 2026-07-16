import { Suspense } from 'react'
import DemoAccessClient from './DemoAccessClient'


export default function DemoPage() {
  return (
    <Suspense fallback={<main className="brand-surface min-h-screen" />}>
      <DemoAccessClient />
    </Suspense>
  )
}
