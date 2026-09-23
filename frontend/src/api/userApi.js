import axiosInstance from './axiosInstance'

/**
 * POST /user/create-user
 * @param {{ first_name, last_name, email, password, confirm_password }} payload
 * @returns {Promise<UserResponse>}
 */
export const createUser = async (payload) => {
  const { data } = await axiosInstance.post('/user/create-user', payload)
  return data
}

/**
 * GET /user/me  (requires Bearer token)
 * @returns {Promise<UserResponse>}
 */
export const getMe = async () => {
  const { data } = await axiosInstance.get('/user/me')
  return data
}
