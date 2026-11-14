/**
 * Authentication Module
 * 
 * This module handles all authentication-related functionality
 * including login, logout, user session management, and auth guards.
 */

// Components

// Hooks
// Os hooks de autenticação ainda vivem em @/hooks/useDjangoAuth; esta pasta está vazia.

// Services
export * from './services'

// Types (o User da sessão é o de ./services; o de ./types descreve o perfil completo)
export * from './types'
export type { User } from './services'

// Re-export commonly used items with cleaner names
// These will be added as we migrate components
// export { DjangoSignIn as SignIn } from './components/SignIn'
// export { DjangoSignUp as SignUp } from './components/SignUp'
// export { useAuth } from './hooks/useAuth'
// export { authService } from './services/authService'