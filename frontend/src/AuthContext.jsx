import React, { createContext, useContext, useState, useEffect } from 'react';
import api from './api/client';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('token'));
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    useEffect(() => {
        if (token) {
            fetchMe();
        } else {
            setUser(null);
            setLoading(false);
        }
    }, [token]);

    const fetchMe = async () => {
        setRefreshing(true);
        try {
            const res = await api.get('/me');
            setUser(res.data);
        } catch (err) {
            if (err.response?.status !== 401) {
                logout();
            }
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    const login = (newToken) => {
        localStorage.setItem('token', newToken);
        setToken(newToken);
    };

    const logout = () => {
        localStorage.removeItem('token');
        setToken(null);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, token, login, logout, loading, refreshing, fetchMe }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
