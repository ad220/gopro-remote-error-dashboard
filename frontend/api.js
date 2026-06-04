async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return null
  return res.json()
}

function toQuery(params) {
  const entries = Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)
  return entries.length ? '?' + new URLSearchParams(entries) : ''
}

export const api = {
  errors: {
    list: (params) => apiFetch(`/admin/errors${toQuery(params)}`),
  },
  stats: {
    get: () => apiFetch('/admin/stats'),
  },
  versions: {
    list:   ()       => apiFetch('/admin/versions'),
    create: (version) => apiFetch('/admin/versions', { method: 'POST', body: JSON.stringify({ version }) }),
    revoke: (id)     => apiFetch(`/admin/versions/${id}`, { method: 'DELETE' }),
  },
}
