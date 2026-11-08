export async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.status === 204 ? null : r.json()
}

export function qs(params) {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined) p.set(k, v)
  return p.toString()
}

// Token columns arrive in thousands of tokens
export function fmtTokens(kt) {
  const t = (kt || 0) * 1000
  if (t >= 1e8) return (t / 1e8).toFixed(2) + ' 亿'
  if (t >= 1e4) return (t / 1e4).toFixed(1) + ' 万'
  return Math.round(t).toLocaleString()
}

export function fmtInt(n) {
  const v = n || 0
  if (v >= 1e4) return (v / 1e4).toFixed(1) + ' 万'
  return v.toLocaleString()
}

export const fmtPct = (r, d = 1) => ((r || 0) * 100).toFixed(d) + '%'

export function change(cur, prev) {
  if (!prev) return cur ? { text: '新增', cls: 'up' } : { text: '—', cls: 'muted' }
  const r = (cur - prev) / prev
  return { text: (r >= 0 ? '↑' : '↓') + Math.abs(r * 100).toFixed(0) + '%', cls: r >= 0 ? 'up' : 'down' }
}

export function fmtMetric(metric, v) {
  return metric === 'tokens' ? fmtTokens(v) : fmtInt(v)
}

export function localDate(d = new Date()) {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return z.toISOString().slice(0, 10)
}

export function addDays(iso, n) {
  const d = new Date(iso + 'T00:00:00')
  d.setDate(d.getDate() + n)
  return localDate(d)
}
