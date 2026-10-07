/**
 * Shared campaign display helpers: banner, genre/rating chips, "last post" time, "Based on" credit,
 * and the Report banner dialog. Used by campaigns.html and game.html so both look and behave the same.
 *
 * Everything user-controlled goes through cbEsc() or textContent, and a banner URL is only ever used
 * after cbSafeUrl() (https only, no quotes or angle brackets).
 */
(function () {
  'use strict';

  const GENRE_LABELS = {
    fantasy: 'Fantasy', horror: 'Horror', scifi: 'Sci-Fi', mystery: 'Mystery',
    political: 'Political', post_apocalyptic: 'Post-Apocalyptic', superhero: 'Superhero',
    western: 'Western', steampunk: 'Steampunk', survival: 'Survival', comedy: 'Comedy',
    slice_of_life: 'Slice of Life', other: 'Other',
  };
  const RATING_LABELS = { all_ages: 'All ages', teen: 'Teen', mature: 'Mature' };

  function cbEsc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Only our own https image URLs ever reach an <img src>.
  function cbSafeUrl(u) {
    return (typeof u === 'string' && /^https:\/\/[^\s"'<>]+$/i.test(u)) ? u : '';
  }

  // Server timestamps are naive UTC (no "Z"); treat them as UTC so "6 minutes ago" is right everywhere.
  function cbRelativeTime(iso) {
    if (!iso) return '';
    const t = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z').getTime();
    if (isNaN(t)) return '';
    const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (s < 60) return 'just now';
    const m = Math.floor(s / 60);
    if (m < 60) return m + (m === 1 ? ' minute ago' : ' minutes ago');
    const h = Math.floor(m / 60);
    if (h < 24) return h + (h === 1 ? ' hour ago' : ' hours ago');
    const d = Math.floor(h / 24);
    if (d < 30) return d + (d === 1 ? ' day ago' : ' days ago');
    const mo = Math.floor(d / 30);
    return mo < 12 ? mo + (mo === 1 ? ' month ago' : ' months ago') : 'over a year ago';
  }

  // Deterministic default art so a campaign without a banner still looks intentional.
  function cbDefaultBannerStyle(campaign) {
    const key = String(campaign.id || campaign.name || '');
    let h = 0;
    for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
    const hue = h % 360;
    return `background:linear-gradient(135deg,hsl(${hue},38%,22%),hsl(${(hue + 40) % 360},45%,14%));`;
  }

  /**
   * The banner area at the top of a card. opts.reportable shows the "..." menu (needs a real banner).
   */
  function cbBannerHtml(campaign, opts) {
    opts = opts || {};
    const url = cbSafeUrl(campaign.banner_url);
    const initial = cbEsc((campaign.name || '?').trim().charAt(0).toUpperCase());
    const inner = url
      ? `<img src="${cbEsc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : `<div class="cb-banner-default" style="${cbDefaultBannerStyle(campaign)}"><span>${initial}</span></div>`;
    const safeId = /^[0-9a-f-]{36}$/i.test(String(campaign.id)) ? String(campaign.id) : '';
    const menu = (opts.reportable && url && safeId)
      ? `<div class="cb-menu-wrap">
           <button type="button" class="cb-menu-btn" aria-label="More options" onclick="cbToggleMenu(event)">&#8943;</button>
           <div class="cb-menu" role="menu">
             <button type="button" role="menuitem" onclick="cbReportClick(event, '${safeId}')">Report campaign banner</button>
           </div>
         </div>`
      : '';
    return `<div class="cb-banner">${inner}${menu}</div>`;
  }

  function cbChipsHtml(campaign) {
    const chips = (campaign.genres || []).map(g => `<span class="cb-chip">${cbEsc(GENRE_LABELS[g] || g)}</span>`);
    if (campaign.content_rating) {
      chips.push(`<span class="cb-chip ${campaign.content_rating === 'mature' ? 'cb-chip-mature' : ''}">${cbEsc(RATING_LABELS[campaign.content_rating] || campaign.content_rating)}</span>`);
    }
    return chips.length ? `<div class="cb-chips">${chips.join('')}</div>` : '';
  }

  function cbActivityHtml(campaign) {
    const when = cbRelativeTime(campaign.last_activity_at);
    return when ? `<div class="campaign-meta-item cb-activity"><span>Last post ${cbEsc(when)}</span></div>` : '';
  }

  function cbSourceHtml(campaign) {
    if (!campaign.source_title) return '';
    const title = campaign.source_package_id
      ? `<a href="/lba.html?entry=${encodeURIComponent(campaign.source_package_id)}">${cbEsc(campaign.source_title)}</a>`
      : cbEsc(campaign.source_title);
    const by = campaign.source_author_username ? ` by @${cbEsc(campaign.source_author_username)}` : '';
    return `<div class="cb-source">Based on ${title}${by}</div>`;
  }

  // ---- "..." menu on a banner ------------------------------------------------------------------
  window.cbToggleMenu = function (ev) {
    ev.stopPropagation();
    const menu = ev.currentTarget.parentElement.querySelector('.cb-menu');
    const open = menu.classList.contains('open');
    document.querySelectorAll('.cb-menu.open').forEach(m => m.classList.remove('open'));
    if (!open) menu.classList.add('open');
  };
  document.addEventListener('click', () => document.querySelectorAll('.cb-menu.open').forEach(m => m.classList.remove('open')));
  window.cbReportClick = function (ev, campaignId) {
    ev.stopPropagation();
    document.querySelectorAll('.cb-menu.open').forEach(m => m.classList.remove('open'));
    window.openReportBannerModal(campaignId);
  };

  // ---- Report banner dialog --------------------------------------------------------------------
  function token() {
    return localStorage.getItem('tba_token') || sessionStorage.getItem('tba_token');
  }

  let reasonsCache = null;
  async function loadReasons() {
    if (reasonsCache) return reasonsCache;
    const resp = await fetch('/api/moderation/reasons', { headers: { Authorization: 'Bearer ' + token() } });
    if (!resp.ok) throw new Error('Could not load report options');
    reasonsCache = await resp.json();
    return reasonsCache;
  }

  function ensureModal() {
    let overlay = document.getElementById('cbReportOverlay');
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'cbReportOverlay';
    overlay.className = 'cb-overlay';
    overlay.innerHTML = `
      <div class="cb-dialog" role="dialog" aria-modal="true" aria-labelledby="cbReportTitle">
        <h3 id="cbReportTitle">Report campaign banner</h3>
        <p class="cb-dialog-sub">Tell us what's wrong with this banner. Reports are private. The campaign's Story Weaver is not told who reported it.</p>
        <label for="cbReportReason">Reason</label>
        <select id="cbReportReason"></select>
        <label for="cbReportNote" id="cbReportNoteLabel">Details (optional)</label>
        <textarea id="cbReportNote" maxlength="500" rows="3" placeholder="Anything that helps us review it"></textarea>
        <div class="cb-dialog-msg" id="cbReportMsg" aria-live="polite"></div>
        <div class="cb-dialog-actions">
          <button type="button" class="cb-btn cb-btn-ghost" id="cbReportCancel">Cancel</button>
          <button type="button" class="cb-btn cb-btn-danger" id="cbReportSend">Send report</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', e => { if (e.target === overlay) closeReport(); });
    overlay.querySelector('#cbReportCancel').addEventListener('click', closeReport);
    overlay.querySelector('#cbReportReason').addEventListener('change', syncNoteRequirement);
    overlay.querySelector('#cbReportReason').addEventListener('change', () => setMsg(''));
    overlay.querySelector('#cbReportNote').addEventListener('input', () => setMsg(''));
    return overlay;
  }

  function closeReport() {
    const o = document.getElementById('cbReportOverlay');
    if (o) o.classList.remove('open');
  }

  function syncNoteRequirement() {
    const isOther = document.getElementById('cbReportReason').value === 'other';
    document.getElementById('cbReportNoteLabel').textContent = isOther ? 'Details (required)' : 'Details (optional)';
  }

  function setMsg(text, kind) {
    const el = document.getElementById('cbReportMsg');
    el.textContent = text || '';
    el.className = 'cb-dialog-msg' + (kind ? ' ' + kind : '');
  }

  window.openReportBannerModal = async function (campaignId) {
    const overlay = ensureModal();
    const select = overlay.querySelector('#cbReportReason');
    const send = overlay.querySelector('#cbReportSend');
    const note = overlay.querySelector('#cbReportNote');
    note.value = '';
    setMsg('');
    send.disabled = true;
    send.textContent = 'Send report';
    overlay.classList.add('open');

    try {
      const reasons = await loadReasons();
      select.replaceChildren(...reasons.map(r => {
        const o = document.createElement('option');
        o.value = r.value;
        o.textContent = r.label;
        return o;
      }));
      syncNoteRequirement();
      send.disabled = false;
    } catch (e) {
      setMsg('Could not load report options. Please try again later.', 'err');
      return;
    }

    send.onclick = async () => {
      const reason = select.value;
      const text = note.value.trim();
      if (reason === 'other' && !text) { setMsg('Please add a short note when choosing Other.', 'err'); return; }
      send.disabled = true;
      send.textContent = 'Sending...';
      try {
        const resp = await fetch('/api/moderation/report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token() },
          body: JSON.stringify({ content_type: 'campaign_banner', content_id: campaignId, reason, note: text || null }),
        });
        if (resp.ok) {
          setMsg('Thanks. We will review it.', 'ok');
          send.textContent = 'Sent';
          setTimeout(closeReport, 1400);
          return;
        }
        const body = await resp.json().catch(() => ({}));
        const detail = typeof body.detail === 'string' ? body.detail : 'Could not send the report.';
        setMsg(resp.status === 404 ? 'That banner is no longer available.' : detail, 'err');
      } catch (e) {
        setMsg('Could not send the report. Please try again.', 'err');
      }
      send.disabled = false;
      send.textContent = 'Send report';
    };
  };


  // ---- Banner + tags editor (used by the SW settings on campaigns.html and in game.html) ---------
  // cfg.ids: element ids {preview, file, upload, remove, hint, msg, genres, rating, sourceGroup, showSource, sourceHint}
  // cfg.getCampaignId(): current campaign id.  cfg.onBannerChange(url|null): called after upload/remove.
  const BANNER_MAX_BYTES = 3 * 1024 * 1024;
  const MAX_GENRES = 5;
  const BANNER_HINT = 'JPEG, PNG or WebP, up to 3MB. Wide images work best (about 3:1). Banners can be seen by anyone browsing and can be reported, so keep them suitable for your content rating.';

  function createBannerTagsEditor(cfg) {
    const el = key => document.getElementById(cfg.ids[key]);
    const headers = () => ({ Authorization: 'Bearer ' + token() });
    let locked = false;

    function say(text, isErr) {
      const m = el('msg');
      m.textContent = text || '';
      m.style.color = isErr ? '#f87171' : '#34d399';
    }

    function renderPreview(banner_url, isLocked) {
      locked = !!isLocked;
      const box = el('preview');
      box.replaceChildren();
      const url = cbSafeUrl(banner_url);
      if (url) {
        const img = document.createElement('img');
        img.src = url;
        img.alt = 'Current banner';
        img.referrerPolicy = 'no-referrer';
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;display:block;';
        box.appendChild(img);
      } else {
        const none = document.createElement('div');
        none.textContent = 'No banner';
        none.style.cssText = 'height:100%;display:flex;align-items:center;justify-content:center;color:#6a7086;font-size:0.85rem;';
        box.appendChild(none);
      }
      el('remove').style.display = url ? '' : 'none';
      el('upload').disabled = locked;
      el('hint').textContent = locked ? 'Banner uploads are turned off for this campaign.' : BANNER_HINT;
    }

    function limitGenres() {
      const boxes = Array.from(el('genres').querySelectorAll('input'));
      const full = boxes.filter(b => b.checked).length >= MAX_GENRES;
      boxes.forEach(b => { b.disabled = full && !b.checked; });
    }

    function buildGenres(selected) {
      const wrap = el('genres');
      wrap.replaceChildren();
      Object.entries(GENRE_LABELS).forEach(([value, label]) => {
        const l = document.createElement('label');
        l.style.cssText = 'display:inline-flex;align-items:center;gap:6px;margin:0;font-weight:400;font-size:0.85rem;background:#1a1d29;border:1px solid #3a3f54;border-radius:14px;padding:4px 10px;cursor:pointer;text-transform:none;letter-spacing:normal;color:#e4e6eb;';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = value;
        cb.style.cssText = 'width:auto;padding:0;margin:0;';
        cb.checked = selected.includes(value);
        cb.addEventListener('change', limitGenres);
        l.appendChild(cb);
        l.appendChild(document.createTextNode(label));
        wrap.appendChild(l);
      });
      limitGenres();
    }

    async function upload(file) {
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { say('Please choose a JPEG, PNG or WebP image.', true); return; }
      if (file.size > BANNER_MAX_BYTES) { say('That image is over 3MB. Please choose a smaller one.', true); return; }
      say('Uploading...');
      const form = new FormData();
      form.append('file', file);
      try {
        const resp = await fetch(`/api/campaigns/${cfg.getCampaignId()}/banner`, { method: 'POST', headers: headers(), body: form });
        const body = await resp.json().catch(() => ({}));
        if (!resp.ok) { say(typeof body.detail === 'string' ? body.detail : 'Upload failed.', true); return; }
        renderPreview(body.banner_url, false);
        say('Banner updated.');
        if (cfg.onBannerChange) cfg.onBannerChange(body.banner_url);
      } catch (e) {
        say('Upload failed. Please try again.', true);
      }
    }

    async function remove() {
      try {
        const resp = await fetch(`/api/campaigns/${cfg.getCampaignId()}/banner`, { method: 'DELETE', headers: headers() });
        if (!resp.ok) { say('Could not remove the banner.', true); return; }
        renderPreview(null, locked);
        say('Banner removed.');
        if (cfg.onBannerChange) cfg.onBannerChange(null);
      } catch (e) {
        say('Could not remove the banner.', true);
      }
    }

    el('upload').addEventListener('click', () => el('file').click());
    el('remove').addEventListener('click', remove);
    el('file').addEventListener('change', ev => {
      const file = ev.target.files[0];
      ev.target.value = '';
      if (file) upload(file);
    });

    return {
      /** Fill the controls from a campaign response (the SW's view of it). */
      fill(c) {
        say('');
        renderPreview(c.banner_url, c.banner_locked);
        buildGenres(c.genres || []);
        el('rating').value = c.content_rating || '';
        const group = el('sourceGroup');
        if (c.source_title) {
          group.style.display = '';
          el('showSource').checked = !!c.show_source_in_game;
          el('sourceHint').textContent = 'This campaign is based on "' + c.source_title + '". Browse always shows the credit. Leave this off so players are not tempted to read the story ahead of time.';
        } else {
          group.style.display = 'none';
        }
      },
      /** The tag fields ready to send in a campaign PATCH/PUT. */
      getValues() {
        const out = {
          genres: Array.from(el('genres').querySelectorAll('input:checked')).map(i => i.value),
          content_rating: el('rating').value || null,
        };
        if (el('sourceGroup').style.display !== 'none') out.show_source_in_game = el('showSource').checked;
        return out;
      },
    };
  }

  // ---- Styles (scoped with the cb- prefix so they cannot clash with either page) -----------------
  const css = `
    .cb-banner { position: relative; height: 110px; margin: -20px -20px 14px; border-radius: 12px 12px 0 0; overflow: hidden; background: #13151f; }
    .cb-banner img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .cb-banner-default { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
    .cb-banner-default span { font-size: 3rem; font-weight: 800; color: rgba(255,255,255,0.22); }
    .cb-menu-wrap { position: absolute; top: 6px; right: 6px; }
    .cb-menu-btn { background: rgba(0,0,0,0.55); color: #fff; border: 1px solid rgba(255,255,255,0.25); border-radius: 6px; width: 30px; height: 28px; font-size: 1.1rem; line-height: 1; cursor: pointer; }
    .cb-menu { display: none; position: absolute; right: 0; top: 32px; background: #1c2130; border: 1px solid #3a3f54; border-radius: 8px; min-width: 190px; z-index: 5; box-shadow: 0 6px 16px rgba(0,0,0,0.5); }
    .cb-menu.open { display: block; }
    .cb-menu button { display: block; width: 100%; text-align: left; background: none; border: none; color: #e4e6eb; padding: 10px 12px; font-size: 0.85rem; cursor: pointer; }
    .cb-menu button:hover { background: #2a3048; }
    .cb-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 10px; }
    .cb-chip { font-size: 0.72rem; color: #c4c8d4; background: #2a3048; border: 1px solid #3a3f54; border-radius: 10px; padding: 2px 9px; }
    .cb-chip-mature { color: #fca5a5; border-color: #7c4a4a; }
    .cb-activity { color: #8ec5a0; }
    .cb-source { font-size: 0.8rem; color: #b0b3ba; margin: 0 0 10px; }
    .cb-source a { color: #d4af37; text-decoration: none; }
    .cb-source a:hover { text-decoration: underline; }
    .cb-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: none; align-items: center; justify-content: center; z-index: 10000; padding: 16px; }
    .cb-overlay.open { display: flex; }
    .cb-dialog { background: #1c2130; border: 1px solid #3a3f54; border-radius: 12px; padding: 20px; width: 100%; max-width: 420px; color: #e4e6eb; }
    .cb-dialog h3 { margin: 0 0 6px; color: #f87171; font-size: 1.1rem; }
    .cb-dialog-sub { margin: 0 0 14px; font-size: 0.82rem; color: #a2a7b8; }
    .cb-dialog label { display: block; font-size: 0.82rem; color: #a2a7b8; margin: 10px 0 4px; }
    .cb-dialog select, .cb-dialog textarea { width: 100%; background: #232838; border: 1px solid #3a3f54; color: #e4e6eb; border-radius: 6px; padding: 8px; font: inherit; font-size: 0.9rem; }
    .cb-dialog-msg { min-height: 20px; margin-top: 10px; font-size: 0.85rem; }
    .cb-dialog-msg.ok { color: #34d399; } .cb-dialog-msg.err { color: #f87171; }
    .cb-dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
    .cb-btn { border-radius: 6px; padding: 8px 14px; font-size: 0.85rem; font-weight: 600; cursor: pointer; border: 1px solid #3a3f54; }
    .cb-btn-ghost { background: #232838; color: #e4e6eb; }
    .cb-btn-danger { background: rgba(248,113,113,0.18); color: #f87171; border-color: #f87171; }
    .cb-btn:disabled { opacity: .55; cursor: default; }
  `;
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  window.CampaignShared = {
    GENRE_LABELS, RATING_LABELS, cbEsc, cbSafeUrl, cbRelativeTime,
    cbBannerHtml, cbChipsHtml, cbActivityHtml, cbSourceHtml, createBannerTagsEditor,
  };
})();
