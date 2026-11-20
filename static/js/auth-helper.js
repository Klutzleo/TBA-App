/**
 * TBA Authentication Helper
 * Reusable functions for auth management across the app
 */

const AUTH_CONFIG = {
    API_URL: '/api',
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
        <a href="/profile.html"
            style="margin-left: 10px; padding: 8px 16px; background: transparent; color: #d4af37; border: 1px solid #3a3f54; border-radius: 8px; font-weight: 600; cursor: pointer; text-decoration: none; font-size: 0.9rem; transition: all 0.3s ease;"
            onmouseover="this.style.borderColor='#d4af37'; this.style.background='rgba(212,175,55,0.1)'"
            onmouseout="this.style.borderColor='#3a3f54'; this.style.background='transparent'">
            <i data-lucide="user" style="width:14px;height:14px;vertical-align:middle;margin-right:5px;"></i>Profile
        </a>
        <button
            onclick="logout()"
            onmouseover="this.style.background='#9d7c2f'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 6px rgba(0, 0, 0, 0.4)'"
            onmouseout="this.style.background='#d4af37'; this.style.transform='translateY(0)'; this.style.boxShadow='none'"
            style="margin-left: 8px; padding: 8px 16px; background: #d4af37; color: #13151f; border: none; border-radius: 8px; font-weight: 700; cursor: pointer; transition: all 0.3s ease;">
            Logout
        </button>
    `;
    if (window.lucide) lucide.createIcons({ el: container });
    addAdminLink(container);
    addVerifyBanner();
}

/**
 * A slim bar for accounts that have not confirmed their email yet, with a button to send the link again. Accounts that existed before
 * verification was introduced never see it. The page works fully either way; this is a nudge, not a wall.
 */
async function addVerifyBanner() {
    try {
        if (document.getElementById('verify-banner')) return;
        const r = await fetchWithAuth('/api/auth/me');
        if (!r || !r.ok) return;
        const me = await r.json();
        if (me.email_verified !== false) return;

        const bar = document.createElement('div');
        bar.id = 'verify-banner';
        bar.style.cssText = 'background:#3b2f0b;color:#f5d98a;border-bottom:1px solid #6b5416;padding:8px 14px;font-size:0.85rem;text-align:center;';
        const msg = document.createElement('span');
        msg.textContent = 'Please confirm your email address. We sent a link to ' + me.email + '. Check your junk folder if you do not see it. ';
        const btn = document.createElement('button');
        btn.textContent = 'Send it again';
        btn.style.cssText = 'margin-left:6px;background:#d4af37;color:#13151f;border:none;border-radius:6px;padding:4px 12px;font-weight:700;cursor:pointer;';
        btn.onclick = async () => {
            btn.disabled = true;
            try {
                const rr = await fetchWithAuth('/api/auth/resend-verification', { method: 'POST' });
                const d = rr && rr.ok ? await rr.json() : {};
                msg.textContent = d.status === 'too_soon' ? 'We just sent one. Give it a couple of minutes. '
                    : d.status === 'already_verified' ? 'Your email is already confirmed. '
                    : d.status === 'sent' ? 'Sent. Check your inbox and your junk folder. '
                    : 'Could not send it right now. Try again later. ';
                if (d.status === 'already_verified') bar.remove();
            } catch (e) { msg.textContent = 'Could not send it right now. Try again later. '; }
            btn.disabled = false;
        };
        bar.append(msg, btn);
        document.body.insertBefore(bar, document.body.firstChild);
    } catch (e) { /* a nudge only; never break the page */ }
}

/**
 * Show an Admin link, only to admins. The server decides (ADMIN_USER_IDS); anyone else sees nothing.
 */
async function addAdminLink(container) {
    try {
        const r = await fetchWithAuth('/api/moderation/am-i-admin');
        if (!r || !r.ok || !(await r.json()).admin) return;
        const a = document.createElement('a');
        a.href = '/admin.html';
        a.textContent = 'Admin';
        a.style.cssText = 'margin-left: 10px; padding: 8px 16px; color: #f87171; border: 1px solid #3a3f54; border-radius: 8px; font-weight: 600; text-decoration: none; font-size: 0.9rem;';
        const first = container.querySelector('button');
        container.insertBefore(a, first || null);
    } catch (e) { /* the link is a convenience; never break the page */ }
}