/**
 * notification-drawer.js
 * Notification center — drawer + toast + bell icon.
 *
 * Usage: include this script on any page that needs the notification center.
 * Call initNotificationCenter() after the DOM is ready.
 *
 * Requires:
 *   - getAuthToken() from auth-helper.js
 *   - lucide.min.js for icons
 *   - notification-drawer.css
 */

(function () {
  'use strict';

  let _unreadCount = 0;
  let _drawerOpen  = false;
  let _pollInterval = null;

  // ── Public API ────────────────────────────────────────────────────────────

  window.initNotificationCenter = function () {
    _injectHTML();
    _bindEvents();
    _loadNotifications();
    // Poll for new notifications every 60s
    _pollInterval = setInterval(_loadNotifications, 60000);
  };

  window.destroyNotificationCenter = function () {
    if (_pollInterval) clearInterval(_pollInterval);
  };

  // Called by achievements system after earning something live
  window.notificationCenterRefresh = function () {
    _loadNotifications();
  };

  // ── DOM injection ─────────────────────────────────────────────────────────

  function _injectHTML() {
    // Bell icon — injected into .notif-bell-target on the page
    const target = document.querySelector('.notif-bell-target');
    if (target) {
      target.innerHTML = `
        <button class="notif-bell-btn" id="notifBellBtn" onclick="toggleNotificationDrawer()" title="Notifications">
          <i data-lucide="bell"></i>
          <span class="notif-badge" id="notifBadge" style="display:none;">0</span>
        </button>`;
    }

    // Drawer overlay
    if (!document.getElementById('notifDrawer')) {
      document.body.insertAdjacentHTML('beforeend', `
        <div class="notif-overlay" id="notifOverlay" onclick="toggleNotificationDrawer()"></div>
        <div class="notif-drawer" id="notifDrawer">
          <div class="notif-drawer-header">
            <span class="notif-drawer-title">Notifications</span>
            <div style="display:flex;gap:8px;align-items:center;">
              <button class="notif-clear-btn" id="notifClearBtn" onclick="clearNotifications()" title="Clear read notifications">Clear</button>
              <button class="notif-close-btn" onclick="toggleNotificationDrawer()">
                <i data-lucide="x"></i>
              </button>
            </div>
          </div>
          <div class="notif-drawer-body" id="notifDrawerBody">
            <div class="notif-loading">Loading…</div>
          </div>
        </div>`);
    }

    if (window.lucide) lucide.createIcons();
  }

  // ── Events ────────────────────────────────────────────────────────────────

  function _bindEvents() {
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && _drawerOpen) toggleNotificationDrawer();
    });
  }

  window.toggleNotificationDrawer = function () {
    const drawer  = document.getElementById('notifDrawer');
    const overlay = document.getElementById('notifOverlay');
    if (!drawer) return;
    _drawerOpen = !_drawerOpen;
    drawer.classList.toggle('open', _drawerOpen);
    overlay.classList.toggle('open', _drawerOpen);
    if (_drawerOpen) {
      _markAllRead();
    }
  };

  window.clearNotifications = async function () {
    const token = getAuthToken();
    if (!token) return;
    try {
      await fetch('/api/notifications/recent', {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      _loadNotifications();
    } catch (e) { /* silent */ }
  };

  // ── Data loading ──────────────────────────────────────────────────────────

  async function _loadNotifications() {
    const token = getAuthToken();
    if (!token) return;
    try {
      const resp = await fetch('/api/notifications', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!resp.ok) return;
      const data = await resp.json();
      _unreadCount = data.unread_count || 0;
      _updateBadge();
      if (_drawerOpen) _renderDrawer(data);
      else _cacheData(data);
    } catch (e) { /* silent */ }
  }

  let _cachedData = null;
  function _cacheData(data) { _cachedData = data; }

  // Re-render if drawer opens with cached data
  const _origToggle = window.toggleNotificationDrawer;
  window.toggleNotificationDrawer = function () {
    const wasOpen = _drawerOpen;
    _origToggle();
    if (!wasOpen && _cachedData) {
      _renderDrawer(_cachedData);
      _cachedData = null;
    }
  };

  async function _markAllRead() {
    const token = getAuthToken();
    if (!token) return;
    try {
      await fetch('/api/notifications/read-all', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      _unreadCount = 0;
      _updateBadge();
    } catch (e) { /* silent */ }
  }

  // ── Badge ─────────────────────────────────────────────────────────────────

  function _updateBadge() {
    const badge = document.getElementById('notifBadge');
    const bell  = document.getElementById('notifBellBtn');
    if (!badge || !bell) return;
    if (_unreadCount > 0) {
      badge.textContent = _unreadCount > 99 ? '99+' : _unreadCount;
      badge.style.display = 'flex';
      bell.classList.add('has-unread');
    } else {
      badge.style.display = 'none';
      bell.classList.remove('has-unread');
    }
  }

  // ── Drawer rendering ──────────────────────────────────────────────────────

  function _renderDrawer(data) {
    const body = document.getElementById('notifDrawerBody');
    if (!body) return;

    const hasAnything = (
      data.achievements.length ||
      data.recent.length ||
      data.hall_of_fame.length ||
      data.hall_of_shame.length
    );

    if (!hasAnything) {
      body.innerHTML = `<div class="notif-empty">Nothing here yet.<br>Go earn something.</div>`;
      return;
    }

    let html = '';

    // Achievements section — always expanded
    if (data.achievements.length) {
      html += _section('Achievements', data.achievements, 'achievement', true);
    }

    // Recent activity — clearable
    if (data.recent.length) {
      html += _section('Recent Activity', data.recent, 'recent', true);
    }

    // Hall of Fame — permanent
    if (data.hall_of_fame.length) {
      html += `<div class="notif-divider">Hall of Fame</div>`;
      html += data.hall_of_fame.map(_renderRow).join('');
    }

    // Hall of Shame — permanent
    if (data.hall_of_shame.length) {
      html += `<div class="notif-divider shame">Hall of Shame</div>`;
      html += data.hall_of_shame.map(_renderRow).join('');
    }

    body.innerHTML = html;
    if (window.lucide) lucide.createIcons({ context: body });
  }

  function _section(label, items, id, defaultOpen) {
    const open = defaultOpen ? 'open' : '';
    return `
      <details class="notif-section" ${open}>
        <summary class="notif-section-header">
          <span>${label}</span>
          <span class="notif-section-count">${items.length}</span>
        </summary>
        <div class="notif-section-body">
          ${items.map(_renderRow).join('')}
        </div>
      </details>`;
  }

  function _renderRow(n) {
    const time = _relativeTime(n.created_at);
    const unreadDot = !n.read ? '<span class="notif-unread-dot"></span>' : '';
    const pts = n.type === 'achievement' && n.data && n.data.points
      ? `<span class="notif-pts">${n.data.points} pts</span>`
      : '';
    return `
      <div class="notif-row ${n.read ? 'read' : 'unread'} ${n.shame ? 'shame' : ''}">
        ${unreadDot}
        <div class="notif-row-icon">
          <i data-lucide="${n.icon || 'bell'}"></i>
        </div>
        <div class="notif-row-content">
          <div class="notif-row-title">${_esc(n.title)}${pts}</div>
          ${n.body ? `<div class="notif-row-body">${_esc(n.body)}</div>` : ''}
          <div class="notif-row-time">${time}</div>
        </div>
      </div>`;
  }

  // ── Toast ─────────────────────────────────────────────────────────────────

  window.showAchievementToast = function (achievementId, title, icon, points, rarityDisplay, rarityLabel) {
    const container = _getOrCreateToastContainer();
    const toast = document.createElement('div');
    toast.className = `notif-toast rarity-${rarityLabel || 'common'}`;
    toast.innerHTML = `
      <div class="notif-toast-icon">
        <i data-lucide="${icon || 'award'}"></i>
      </div>
      <div class="notif-toast-content">
        <div class="notif-toast-label">Achievement Unlocked</div>
        <div class="notif-toast-title">${_esc(title)}</div>
        <div class="notif-toast-meta">
          ${rarityDisplay ? `<span class="notif-toast-rarity rarity-${rarityLabel}">${rarityDisplay}</span>` : ''}
          <span class="notif-toast-pts">${points} pts</span>
        </div>
      </div>
      <button class="notif-toast-close" onclick="this.closest('.notif-toast').remove()">
        <i data-lucide="x"></i>
      </button>`;
    container.appendChild(toast);
    if (window.lucide) lucide.createIcons({ context: toast });
    // Animate in
    requestAnimationFrame(() => toast.classList.add('visible'));
    // Auto-dismiss after 5s
    setTimeout(() => {
      toast.classList.remove('visible');
      setTimeout(() => toast.remove(), 400);
    }, 5000);
  };

  function _getOrCreateToastContainer() {
    let c = document.getElementById('notifToastContainer');
    if (!c) {
      c = document.createElement('div');
      c.id = 'notifToastContainer';
      c.className = 'notif-toast-container';
      document.body.appendChild(c);
    }
    return c;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function _relativeTime(iso) {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1)  return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 7)  return `${d}d ago`;
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  function _esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

})();
