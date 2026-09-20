// Vercel resolves rewrite destinations at build time from vercel.json, and the
// file has no environment-variable interpolation. So the EC2 origin is written
// into the committed config by this script rather than hand-edited, which keeps
// the ":path*" suffix and the /api prefix from drifting.
import { readFile, writeFile } from 'node:fs/promises'
import { argv, env, exit } from 'node:process'

const CONFIG = new URL('../vercel.json', import.meta.url)

const raw = argv[2] || env.AGENTGATE_BACKEND_ORIGIN
if (!raw) {
  console.error('Usage: npm run set:backend -- https://api.example.com')
  console.error('       (or set AGENTGATE_BACKEND_ORIGIN)')
  exit(1)
}

let origin
try {
  origin = new URL(raw)
} catch {
  console.error(`Not a URL: ${raw}`)
  exit(1)
}
if (origin.protocol !== 'http:' && origin.protocol !== 'https:') {
  console.error(`Backend origin must be http or https, got ${origin.protocol}`)
  exit(1)
}
if (origin.pathname !== '/' || origin.search || origin.hash) {
  console.error(`Pass only scheme, host and port. Got a path in: ${raw}`)
  exit(1)
}

const base = origin.origin
const config = JSON.parse(await readFile(CONFIG, 'utf8'))
const rewrite = config.rewrites?.find((entry) => entry.source === '/api/:path*')
if (!rewrite) {
  console.error('vercel.json no longer has an /api/:path* rewrite to update.')
  exit(1)
}

rewrite.destination = `${base}/api/:path*`
await writeFile(CONFIG, `${JSON.stringify(config, null, 2)}\n`, 'utf8')

console.log(`vercel.json now proxies /api -> ${base}/api`)
if (origin.protocol === 'http:') {
  console.warn(
    '\nWarning: the Vercel edge will reach your backend over plain HTTP.\n' +
      'Browsers stay happy because the proxy hop is server-side, but that hop\n' +
      'is unencrypted. Run deployment/enable-tls.sh before this is anything but a demo.',
  )
}
