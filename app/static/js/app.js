/* ============================================================
   AI Content Platform — Global Vanilla JS Utilities
   ============================================================ */

// ── API helper ────────────────────────────────────────────────

async function apiFetch(path, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body && method !== 'GET') opts.body = JSON.stringify(body);

  try {
    const res = await fetch(path, opts);
    if (res.status === 204) return {};           // DELETE success (no content)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || `Error ${res.status}`, 'danger');
      return null;
    }
    return await res.json();
  } catch (e) {
    showToast('Network error — is the API running?', 'danger');
    return null;
  }
}

// ── Toast notifications ───────────────────────────────────────

function showToast(message, type = 'info') {
  const toastEl = document.getElementById('appToast');
  const msgEl   = document.getElementById('toastMessage');
  if (!toastEl || !msgEl) return;

  const colorMap = { success: 'bg-success', danger: 'bg-danger', warning: 'bg-warning text-dark', info: 'bg-info text-dark' };
  toastEl.className = `toast align-items-center border-0 text-white ${colorMap[type] || 'bg-secondary'}`;
  msgEl.textContent = message;
  bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 3500 }).show();
}

// ── Global spinner ────────────────────────────────────────────

function showSpinner() {
  const el = document.getElementById('globalSpinner');
  if (el) el.classList.remove('d-none');
}

function hideSpinner() {
  const el = document.getElementById('globalSpinner');
  if (el) el.classList.add('d-none');
}

// ── DOM helpers ───────────────────────────────────────────────

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── Status badges ─────────────────────────────────────────────

function statusBadge(status) {
  const map = {
    COMPLETED:  'bg-success',
    PROCESSING: 'bg-warning text-dark',
    PENDING:    'bg-secondary',
    FAILED:     'bg-danger',
  };
  return `<span class="badge ${map[status] || 'bg-secondary'}">${status}</span>`;
}

// ── Date formatter ────────────────────────────────────────────

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

// ── Markdown → HTML (basic, no external lib) ─────────────────

function markdownToHtml(md) {
  if (!md) return '';
  return md
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,  '<h2>$1</h2>')
    .replace(/^# (.+)$/gm,   '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,   '<em>$1</em>')
    .replace(/\n\n/g,        '</p><p>')
    .replace(/^/,            '<p>')
    .replace(/$/,            '</p>')
    .replace(/\n/g,          '<br/>');
}

// ── Confirm + delete modal (reusable) ────────────────────────

function confirmDelete(message, onConfirm) {
  if (window.confirm(message)) onConfirm();
}

// ── Sidebar toggle ────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar   = document.getElementById('sidebar');
  const content   = document.querySelector('.main-content');
  const footer    = document.querySelector('.footer');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      if (content) content.classList.toggle('ms-collapsed');
    });
  }

  // Check API health
  fetch('/health')
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      const el = document.getElementById('systemStatus');
      if (el && data?.status === 'ok') {
        el.className = 'badge bg-success status-badge';
        el.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:0.5rem"></i>Online';
      }
    })
    .catch(() => {
      const el = document.getElementById('systemStatus');
      if (el) {
        el.className = 'badge bg-danger status-badge';
        el.innerHTML = '<i class="bi bi-circle-fill me-1" style="font-size:0.5rem"></i>Offline';
      }
    });
});