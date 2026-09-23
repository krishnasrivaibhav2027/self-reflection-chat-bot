import axiosInstance from './axiosInstance'

/**
 * POST /auth/login
 * @param {string} email
 * @param {string} password
 * @returns {Promise<{access_token: string, token_type: string}>}
 */
export const login = async (email, password) => {
  const { data } = await axiosInstance.post('/auth/login', { email, password })
  return data
}

/**
 * POST /auth/logout  (requires Bearer token via interceptor)
 * @returns {Promise<{message: string}>}
 */
export const logout = async () => {
  const { data } = await axiosInstance.post('/auth/logout')
  return data
}
