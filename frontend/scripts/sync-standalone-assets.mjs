import { cpSync, existsSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const standaloneDir = join(root, '.next', 'standalone')

if (!existsSync(standaloneDir)) {
  process.exit(0)
}

const copies = [
  [join(root, '.next', 'static'), join(standaloneDir, '.next', 'static')],
  [join(root, 'public'), join(standaloneDir, 'public')],
]

for (const [source, target] of copies) {
  if (!existsSync(source)) {
    continue
  }

  rmSync(target, { recursive: true, force: true })
  cpSync(source, target, { recursive: true })
}

