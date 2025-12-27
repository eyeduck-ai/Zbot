
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

interface AuthContextType {
    token: string | null;
    login: (token: string, username: string, displayName: string, role: string, eipId?: string, eipPsw?: string) => void;
    logout: () => void;
    isAuthenticated: boolean;
    user: string | null;
    displayName: string | null;
    role: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// JWT 解碼函數
function parseJwt(token: string): any {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(
            atob(base64)
                .split('')
                .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
                .join('')
        );
        return JSON.parse(jsonPayload);
    } catch (e) {
        return null;
    }
}

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
    const [user, setUser] = useState<string | null>(localStorage.getItem('user'));
    const [displayName, setDisplayName] = useState<string | null>(localStorage.getItem('displayName'));
    const [role, setRole] = useState<string | null>(localStorage.getItem('role'));

    useEffect(() => {
        // 從 token 解析資訊
        if (token) {
            const payload = parseJwt(token);
            if (payload) {
                if (payload.sub && !user) setUser(payload.sub);
                // 注意: JWT 中 'role' 是 Supabase DB 角色 (authenticated)
                // Zbot 應用程式角色存在 'zbot_role' 中
                if (payload.zbot_role && !role) setRole(payload.zbot_role);
            }
        }
    }, [token]);

    const login = (newToken: string, username: string, newDisplayName: string, newRole: string, eipId?: string, eipPsw?: string) => {
        localStorage.setItem('token', newToken);
        localStorage.setItem('user', username);
        localStorage.setItem('displayName', newDisplayName || username);
        localStorage.setItem('role', newRole);  // 保留空字串，用於 IVI-only 權限
        // 儲存 EIP 帳密供爬蟲任務使用
        if (eipId) localStorage.setItem('eip_id', eipId);
        if (eipPsw) localStorage.setItem('eip_psw', eipPsw);
        setToken(newToken);
        setUser(username);
        setDisplayName(newDisplayName || username);
        setRole(newRole);  // 不預設為 basic
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        localStorage.removeItem('displayName');
        localStorage.removeItem('role');
        localStorage.removeItem('eip_id');
        localStorage.removeItem('eip_psw');
        setToken(null);
        setUser(null);
        setDisplayName(null);
        setRole(null);
    };

    return (
        <AuthContext.Provider value={{
            token,
            login,
            logout,
            isAuthenticated: !!token,
            user,
            displayName,
            role
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) throw new Error('useAuth must be used within an AuthProvider');
    return context;
};
