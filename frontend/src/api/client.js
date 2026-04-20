/**
 * Centralized Axios instance.
 * All API calls in the app should use this instead of raw `axios`.
 * - Automatically attaches the JWT token from localStorage.
 * - Returns clear error messages for 401/403.
 */
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

// ── Request interceptor: attach token ──────────────────────────────────────
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor: normalize error messages ─────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (status === 401) {
      // Token expired or invalid — clear storage and redirect
      localStorage.removeItem("token");
      window.location.href = "/login";
      error.userMessage = "Session expired. Please log in again.";
    } else if (status === 403) {
      error.userMessage = detail || "Access denied. Insufficient credits or permissions.";
    } else if (status === 422) {
      error.userMessage = detail || "Invalid request data.";
    } else if (status === 500) {
      error.userMessage = "Server error. Please try again later.";
    } else {
      error.userMessage = detail || error.message || "An unexpected error occurred.";
    }

    return Promise.reject(error);
  }
);

export default api;
