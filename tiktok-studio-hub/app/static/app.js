const fmt = (n) => {
  if (n == null || Number.isNaN(n)) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
};

const fmtDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
};

const initials = (name) => (name || '?').slice(0, 1).toUpperCase();

function avatarHtml(account) {
  if (account.avatar_url) {
    return `<img class="avatar" src="${account.avatar_url}" alt="">`;
  }
  return `<div class="avatar placeholder">${initials(account.display_name)}</div>`;
}

function showBanner(message, type = 'info') {
  const el = document.getElementById('banner');
  el.textContent = message;
  el.className = `banner ${type}`;
}

function hideBanner() {
  document.getElementById('banner').className = 'banner hidden';
}

async function loadConfig() {
  const resp = await fetch('/api/config');
  const cfg = await resp.json();
  const hint = document.getElementById('config-hint');
  const connectBtn = document.getElementById('connect-btn');

  if (cfg.demo_mode && !cfg.oauth_configured) {
    hint.textContent = 'Mode démo : comptes fictifs préchargés. Ajoutez vos clés TikTok dans .env pour connecter vos vrais comptes.';
    connectBtn.classList.add('hidden');
  } else if (!cfg.oauth_configured) {
    hint.textContent = 'Copiez .env.example vers .env et renseignez TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET.';
    connectBtn.classList.add('hidden');
    showBanner('Configurez l’API TikTok (developers.tiktok.com) pour connecter vos comptes.', 'info');
  } else {
    hint.textContent = 'Connectez chaque compte TikTok via OAuth.';
  }
  return cfg;
}

function renderDashboard(data) {
  const t = data.totals;
  document.getElementById('total-views').textContent = fmt(t.views);
  document.getElementById('total-followers').textContent = fmt(t.followers);
  document.getElementById('total-likes').textContent = fmt(t.likes);
  document.getElementById('total-comments').textContent = fmt(t.comments);
  document.getElementById('total-shares').textContent = fmt(t.shares);
  document.getElementById('total-videos').textContent = fmt(t.videos);
  document.getElementById('total-profile-likes').textContent = fmt(t.profile_likes);
  document.getElementById('total-accounts').textContent = fmt(t.accounts);

  const tbody = document.getElementById('accounts-table-body');
  if (!data.accounts.length) {
    tbody.innerHTML = `
      <tr><td colspan="7" style="text-align:center;color:#888;padding:32px">
        Aucun compte connecté — cliquez « + Ajouter un compte » pour commencer.
      </td></tr>`;
  } else {
    tbody.innerHTML = data.accounts.map((a) => `
    <tr>
      <td>
        <div class="account-cell">
          ${avatarHtml(a)}
          <span>@${a.display_name}${a.is_demo ? '<span class="tag-demo">démo</span>' : ''}</span>
        </div>
      </td>
      <td>${fmt(a.follower_count)}</td>
      <td>${fmt(a.total_views)}</td>
      <td>${fmt(a.total_video_likes)}</td>
      <td>${fmt(a.total_comments)}</td>
      <td>${fmt(a.video_count)}</td>
      <td>${fmtDate(a.last_synced_at)}</td>
    </tr>
  `).join('');
  }

  const cards = document.getElementById('accounts-cards');
  if (!data.accounts.length) {
    cards.innerHTML = `
      <article class="account-card" style="grid-column:1/-1;text-align:center;color:#888;padding:40px">
        Aucun compte TikTok connecté.<br><br>
        <a class="btn-primary" href="/auth/login" style="display:inline-block;width:auto;padding:12px 24px">+ Ajouter un compte</a>
      </article>`;
  } else {
    cards.innerHTML = data.accounts.map((a) => `
    <article class="account-card" data-id="${a.id}">
      <div class="account-card-head">
        ${avatarHtml(a)}
        <div>
          <h3>@${a.display_name}</h3>
          <span class="tag-demo">${a.is_demo ? 'Compte démo' : 'Connecté'}</span>
        </div>
      </div>
      <div class="account-card-stats">
        <div class="mini-stat"><span>Abonnés</span><b>${fmt(a.follower_count)}</b></div>
        <div class="mini-stat"><span>Vues</span><b>${fmt(a.total_views)}</b></div>
        <div class="mini-stat"><span>J'aime</span><b>${fmt(a.total_video_likes)}</b></div>
        <div class="mini-stat"><span>Vidéos</span><b>${fmt(a.video_count)}</b></div>
      </div>
      <div class="card-actions">
        <button class="btn-sm" data-action="refresh" data-id="${a.id}">Sync</button>
        <button class="btn-sm danger" data-action="delete" data-id="${a.id}">Retirer</button>
      </div>
    </article>
  `).join('');
  }
}

async function refreshDashboard() {
  const btn = document.getElementById('refresh-btn');
  btn.disabled = true;
  btn.textContent = 'Actualisation…';
  try {
    const resp = await fetch('/api/refresh-all', { method: 'POST' });
    const data = await resp.json();
    renderDashboard(data);
    if (data.errors?.length) {
      showBanner(data.errors.join(' · '), 'error');
    } else {
      hideBanner();
    }
  } catch (e) {
    showBanner('Erreur lors de l’actualisation.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Actualiser';
  }
}

async function loadDashboard() {
  const resp = await fetch('/api/dashboard');
  const data = await resp.json();
  renderDashboard(data);
}

function switchView(view) {
  document.querySelectorAll('.nav-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.view === view);
  });
  document.querySelectorAll('.view').forEach((el) => {
    el.classList.toggle('active', el.id === `view-${view}`);
  });
  document.getElementById('page-title').textContent =
    view === 'accounts' ? 'Comptes' : 'Analytiques';
}

document.querySelectorAll('.nav-item').forEach((btn) => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

document.getElementById('refresh-btn').addEventListener('click', refreshDashboard);

document.getElementById('accounts-cards').addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const id = btn.dataset.id;
  if (btn.dataset.action === 'delete') {
    if (!confirm('Retirer ce compte du hub ?')) return;
    await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
    await loadDashboard();
    return;
  }
  if (btn.dataset.action === 'refresh') {
    btn.disabled = true;
    await fetch(`/api/accounts/${id}/refresh`, { method: 'POST' });
    await loadDashboard();
  }
});

const params = new URLSearchParams(window.location.search);
if (params.get('connected') === '1') {
  showBanner('Compte TikTok connecté avec succès.', 'success');
  history.replaceState({}, '', '/');
}
if (params.get('auth_error')) {
  showBanner(`Connexion échouée : ${params.get('auth_error')}`, 'error');
  history.replaceState({}, '', '/');
}

loadConfig();
loadDashboard();
