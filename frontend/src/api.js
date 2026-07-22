const BASE = `${
  import.meta.env.VITE_API_URL ||
  'https://groww-hdfc-faq-chatbot-final.onrender.com'
}/api`

export async function askChat(query) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })

  const text = await res.text()

  console.log('RAW RESPONSE:', text)

  if (!text) {
    throw new Error('Empty response from server')
  }

  let data

  try {
    data = JSON.parse(text)
  } catch {
    throw new Error(`Invalid JSON from backend: ${text}`)
  }

  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`)
  }

  return data
}

export async function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)

  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({
      detail: res.statusText,
    }))

    throw new Error(err.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

export async function fetchHealth() {
  const res = await fetch(`${BASE}/health`)

  if (!res.ok) {
    throw new Error('Backend offline')
  }

  return res.json()
}