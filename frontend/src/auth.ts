const TOKEN_KEY = 'dd_access_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function isLoggedIn(): boolean {
  return getToken() !== null
}

export interface JwtPayload {
  sub: string
  email: string
  tenant_id: number | null
  role: string
}

export function getCurrentUser(): JwtPayload | null {
  const token = getToken()
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload as JwtPayload
  } catch {
    return null
  }
}
