import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  userId: number | null
  displayName: string | null
  userType: string | null
  isAuthenticated: boolean
  login: (token: string, userId: number, displayName: string, userType: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      displayName: null,
      userType: null,
      isAuthenticated: false,
      login: (token, userId, displayName, userType) => {
        localStorage.setItem('access_token', token)
        set({ token, userId, displayName, userType, isAuthenticated: true })
      },
      logout: () => {
        localStorage.removeItem('access_token')
        set({ token: null, userId: null, displayName: null, userType: null, isAuthenticated: false })
      },
    }),
    { name: 'auth-storage' }
  )
)
