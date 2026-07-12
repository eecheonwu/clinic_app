import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import apiClient from '../services/api'
import { setToken, setRefreshToken, clearAuth, getUser, setUser } from '../utils/storage'

// User type
export interface User {
    id: string
    phoneNumber: string
    email: string
    role: 'patient' | 'receptionist' | 'doctor' | 'manager' | 'admin' | 'executive'
    isVerified: boolean
}

// Auth context type
interface AuthContextType {
    user: User | null
    isLoading: boolean
    login: (email: string, password: string) => Promise<void>
    register: (data: RegisterData) => Promise<void>
    verifyOTP: (phoneNumber: string, otp: string) => Promise<void>
    logout: () => void
}

interface RegisterData {
    phone_number: string
    full_name: string
    date_of_birth?: string
    gender?: string
    emergency_contact?: string
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Provider component
export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUserState] = useState<User | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    // Check for existing user on mount
    useEffect(() => {
        const storedUser = getUser()
        if (storedUser) {
            setUserState(storedUser as User)
        }
        setIsLoading(false)
    }, [])

    const login = async (email: string, password: string): Promise<void> => {
        try {
            const response = await apiClient.post('/login', { email, password })
            const { access_token, refresh_token } = response.data

            setToken(access_token)
            setRefreshToken(refresh_token)

            // Fetch user data via /me endpoint
            const meResponse = await apiClient.get('/me')
            const userData = meResponse.data
            setUser(userData)
            setUserState(userData)
        } catch (error) {
            throw error
        }
    }

    const register = async (data: RegisterData): Promise<void> => {
        try {
            const response = await apiClient.post('/register', data)
            // Backend returns AuthResponse { user: {...}, tokens: { access_token, refresh_token, ... } }
            const { tokens } = response.data

            // Store tokens for OTP verification, but don't set user state yet
            // The user still needs to verify their phone number via OTP
            setToken(tokens.access_token)
            setRefreshToken(tokens.refresh_token)
        } catch (error) {
            throw error
        }
    }

    const verifyOTP = async (phoneNumber: string, otp: string): Promise<void> => {
        try {
            const response = await apiClient.post('/verify-code', {
                phone_number: phoneNumber,
                otp_code: otp,
            })
            const { access_token, refresh_token } = response.data

            setToken(access_token)
            setRefreshToken(refresh_token)

            // Fetch user data via /me endpoint
            const meResponse = await apiClient.get('/me')
            const userData = meResponse.data
            setUser(userData)
            setUserState(userData)
        } catch (error) {
            throw error
        }
    }

    const logout = (): void => {
        clearAuth()
        setUserState(null)
    }

    return (
        <AuthContext.Provider value={{ user, isLoading, login, register, verifyOTP, logout }}>
            {children}
        </AuthContext.Provider>
    )
}

// Hook to use auth context
export function useAuth() {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}