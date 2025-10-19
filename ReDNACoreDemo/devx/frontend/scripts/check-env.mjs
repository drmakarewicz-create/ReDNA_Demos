import { readdirSync, statSync, readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import path from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const ROOT = path.resolve(__dirname, '..', 'src')

const violations = []

const traverse = (dir) => {
  for (const entry of readdirSync(dir)) {
    if (entry.startsWith('.') || entry === 'node_modules') continue
    const fullPath = path.join(dir, entry)
    const stats = statSync(fullPath)
    if (stats.isDirectory()) {
      traverse(fullPath)
      continue
    }
    if (!/\.(t|j)sx?$/.test(entry)) continue
    const content = readFileSync(fullPath, 'utf8')
    if (content.includes('process.env')) {
      violations.push(path.relative(ROOT, fullPath))
    }
  }
}

traverse(ROOT)

if (violations.length > 0) {
  console.error('process.env references detected in frontend source:')
  for (const file of violations) {
    console.error(` - ${file}`)
  }
  console.error('Use import.meta.env.VITE_* variables instead.')
  process.exit(1)
}
