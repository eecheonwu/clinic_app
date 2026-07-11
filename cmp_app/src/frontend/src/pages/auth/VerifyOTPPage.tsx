import { useState, type FormEvent, useRef, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'

export function VerifyOTPPage() {
    const [otp, setOtp] = useState(['', '', '', '', '', ''])
    const [error, setError] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [phoneNumber, setPhoneNumber] = useState('')
    const inputRefs = useRef<(HTMLInputElement | null)[]>([])
    const navigate = useNavigate()
    const { verifyOTP } = useAuth()

    // Get phone number from session storage (set during registration)
    useEffect(() => {
        const storedPhone = sessionStorage.getItem('verify_phone')
        if (storedPhone) {
            setPhoneNumber(storedPhone)
        }
    }, [])

    const handleChange = (index: number, value: string) => {
        if (value.length > 1) return

        const newOtp = [...otp]
        newOtp[index] = value
        setOtp(newOtp)

        // Auto-focus next input
        if (value && index < 5) {
            inputRefs.current[index + 1]?.focus()
        }
    }

    const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace' && !otp[index] && index > 0) {
            inputRefs.current[index - 1]?.focus()
        }
    }

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault()
        setError(null)
        setIsLoading(true)

        const otpCode = otp.join('')
        if (otpCode.length !== 6) {
            setError('Please enter the complete 6-digit code')
            setIsLoading(false)
            return
        }

        try {
            await verifyOTP(phoneNumber, otpCode)
            navigate('/dashboard')
        } catch (err) {
            setError('Invalid OTP code. Please try again.')
            setOtp(['', '', '', '', '', ''])
            inputRefs.current[0]?.focus()
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
            <div className="w-full max-w-md space-y-8">
                <div className="text-center">
                    <h1 className="text-3xl font-bold text-gray-900">
                        Verify Your Phone
                    </h1>
                    <p className="mt-2 text-sm text-gray-600">
                        Enter the 6-digit code sent to {phoneNumber}
                    </p>
                </div>

                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    {error && (
                        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
                            {error}
                        </div>
                    )}

                    <div className="flex justify-center space-x-2">
                        {otp.map((digit, index) => (
                            <input
                                key={index}
                                ref={(el) => (inputRefs.current[index] = el)}
                                type="text"
                                inputMode="numeric"
                                pattern="[0-9]*"
                                maxLength={1}
                                value={digit}
                                onChange={(e) => handleChange(index, e.target.value)}
                                onKeyDown={(e) => handleKeyDown(index, e)}
                                className="h-12 w-12 rounded-md border border-gray-300 text-center text-2xl font-bold shadow-sm focus:border-primary-500 focus:outline-none focus:ring-primary-500"
                                disabled={isLoading}
                            />
                        ))}
                    </div>

                    <button
                        type="submit"
                        disabled={isLoading || otp.join('').length !== 6}
                        className="flex w-full justify-center rounded-md border border-transparent bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50"
                    >
                        {isLoading ? 'Verifying...' : 'Verify Code'}
                    </button>

                    <div className="text-center text-sm">
                        <span className="text-gray-600">Didn't receive the code? </span>
                        <Link to="/register" className="font-medium text-primary-600 hover:text-primary-500">
                            Resend
                        </Link>
                    </div>
                </form>
            </div>
        </div>
    )
}