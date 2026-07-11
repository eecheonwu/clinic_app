import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { useAuth } from './contexts/AuthContext'
import { OfflineBanner } from './components/OfflineBanner'
import { LoginPage } from './pages/auth/LoginPage'
import { RegisterPage } from './pages/auth/RegisterPage'
import { VerifyOTPPage } from './pages/auth/VerifyOTPPage'
import { AppointmentListPage } from './pages/Appointments/AppointmentListPage'
import { BranchSelectionPage } from './pages/Appointments/BranchSelectionPage'
import { DoctorSelectionPage } from './pages/Appointments/DoctorSelectionPage'
import { SlotSelectionPage } from './pages/Appointments/SlotSelectionPage'
import { BookingConfirmationPage } from './pages/Appointments/BookingConfirmationPage'
import { ReschedulePage } from './pages/Appointments/ReschedulePage'
import { ReceptionistDashboardPage } from './pages/Staff/ReceptionistDashboardPage'
import { DoctorDashboardPage } from './pages/Doctor/DoctorDashboardPage'
import { ManagerDashboardPage } from './pages/Manager/ManagerDashboardPage'
import { AdminDashboardPage } from './pages/Admin/AdminDashboardPage'

// Protected route component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth()

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <div className="text-lg">Loading...</div>
            </div>
        )
    }

    if (!user) {
        return <Navigate to="/login" replace />
    }

    return <>{children}</>
}

// Public route component (redirects to dashboard if already logged in)
function PublicRoute({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth()

    if (isLoading) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <div className="text-lg">Loading...</div>
            </div>
        )
    }

    if (user) {
        return <Navigate to="/dashboard" replace />
    }

    return <>{children}</>
}

function App() {
    return (
        <AuthProvider>
            <div className="min-h-screen bg-gray-50">
                <OfflineBanner />
                <Routes>
                    {/* Public routes */}
                    <Route path="/login" element={
                        <PublicRoute>
                            <LoginPage />
                        </PublicRoute>
                    } />
                    <Route path="/register" element={
                        <PublicRoute>
                            <RegisterPage />
                        </PublicRoute>
                    } />
                    <Route path="/verify-otp" element={
                        <PublicRoute>
                            <VerifyOTPPage />
                        </PublicRoute>
                    } />

                    {/* Protected routes */}
                    <Route path="/dashboard" element={
                        <ProtectedRoute>
                            <div className="p-4">
                                <h1 className="text-2xl font-bold">Dashboard</h1>
                                <p>Welcome to CMP!</p>
                            </div>
                        </ProtectedRoute>
                    } />

                    {/* Appointment routes */}
                    <Route path="/appointments" element={
                        <ProtectedRoute>
                            <AppointmentListPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/appointments/new" element={
                        <ProtectedRoute>
                            <BranchSelectionPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/appointments/new/doctor" element={
                        <ProtectedRoute>
                            <DoctorSelectionPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/appointments/new/slot" element={
                        <ProtectedRoute>
                            <SlotSelectionPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/appointments/:appointmentId/confirm" element={
                        <ProtectedRoute>
                            <BookingConfirmationPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/appointments/:appointmentId/reschedule" element={
                        <ProtectedRoute>
                            <ReschedulePage />
                        </ProtectedRoute>
                    } />

                    {/* Staff routes */}
                    <Route path="/staff/dashboard" element={
                        <ProtectedRoute>
                            <ReceptionistDashboardPage />
                        </ProtectedRoute>
                    } />

                    {/* Doctor routes */}
                    <Route path="/doctor/dashboard" element={
                        <ProtectedRoute>
                            <DoctorDashboardPage />
                        </ProtectedRoute>
                    } />

                    {/* Manager routes */}
                    <Route path="/manager/dashboard" element={
                        <ProtectedRoute>
                            <ManagerDashboardPage />
                        </ProtectedRoute>
                    } />

                    {/* Admin routes */}
                    <Route path="/admin/dashboard" element={
                        <ProtectedRoute>
                            <AdminDashboardPage />
                        </ProtectedRoute>
                    } />

                    {/* Default redirect */}
                    <Route path="/" element={<Navigate to="/login" replace />} />
                </Routes>
            </div>
        </AuthProvider>
    )
}

export default App