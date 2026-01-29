/**
 * TBA Authentication Helper
 * Reusable functions for auth management across the app
 */

const AUTH_CONFIG = {
    API_URL: 'https://tba-app-production.up.railway.app/api',
    TOKEN_KEY: 'tba_token',
    USER_KEY: 'tba_user'
};

/**
 * Get the current auth token
 */
function getAuthToken() {
    return localStorage.getItem(AUTH_CONFIG.TOKEN_KEY) || 
           sessionStorage.getItem(AUTH_CONFIG.TOKEN_KEY);
}

/**
 * Get the current user data
 */
function getCurrentUser() {
    const userJson = localStorage.getItem(AUTH_CONFIG.USER_KEY) || 
                     sessionStorage.getItem(AUTH_CONFIG.USER_KEY);
    return userJson ? JSON.parse(userJson) : null;
}

/**
 * Check if user is logged in
 */
function isLoggedIn() {
    return !!getAuthToken();
}

/**
 * Logout user
 */
function logout() {
    localStorage.removeItem(AUTH_CONFIG.TOKEN_KEY);
    localStorage.removeItem(AUTH_CONFIG.USER_KEY);
    sessionStorage.removeItem(AUTH_CONFIG.TOKEN_KEY);
    sessionStorage.removeItem(AUTH_CONFIG.USER_KEY);
    window.location.href = '/auth.html';
}

/**
 * Make an authenticated API request
 * Handles token expiration automatically
 */
async function fetchWithAuth(url, options = {}) {
    const token = getAuthToken();
    
    if (!token) {
        window.location.href = '/auth.html';
        return null;
    }
    
    const response = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        }
    });
    
    // Handle token expiration
    if (response.status === 401) {
        localStorage.removeItem(AUTH_CONFIG.TOKEN_KEY);
        localStorage.removeItem(AUTH_CONFIG.USER_KEY);
        sessionStorage.removeItem(AUTH_CONFIG.TOKEN_KEY);
        sessionStorage.removeItem(AUTH_CONFIG.USER_KEY);
        window.location.href = '/auth.html?expired=true';
        return null;
    }
    
    return response;
}

/**
 * Require authentication
 * Redirect to login if not authenticated
 */
function requireAuth() {
    if (!isLoggedIn()) {
        window.location.href = '/auth.html';
        return false;
    }
    return true;
}

/**
 * Add user info to page (call this on main game page)
 */
function displayUserInfo(containerId = 'user-info') {
    const user = getCurrentUser();
    if (!user) return;
    
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = `
        <span>Logged in as: <strong>${user.username}</strong></span>
        <button onclick="logout()" style="margin-left: 10px;">Logout</button>
    `;
}