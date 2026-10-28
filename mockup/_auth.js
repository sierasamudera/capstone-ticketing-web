/* Mockup auth — disimulasikan di localStorage.
 * Saat dijinjakan ke Flask: hapus file ini, ganti requireRole dengan
 * decorator @role_required('admin') di blueprint. */
const SESSION_KEY = 'mockup_session';

function login(username, role) {
  localStorage.setItem(SESSION_KEY, JSON.stringify({username, role, ts: Date.now()}));
}
function session() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY)); }
  catch (e) { return null; }
}
function requireRole() {
  var roles = Array.prototype.slice.call(arguments);
  var s = session();
  if (!s) { location.replace(APP_ROOT + 'login.html'); return; }
  if (roles.length && roles.indexOf(s.role) === -1) {
    location.replace(APP_ROOT + '403.html');
  }
}
function logout() {
  localStorage.removeItem(SESSION_KEY);
  location.replace(APP_ROOT + 'login.html');
}
function currentUser() {
  var s = session();
  return s ? s.username : null;
}

/* Status alur kerja tiket (Open -> In Progress -> Resolved).
 * USULAN: siklus ini tidak ada di mesin Excel; default Open, perubahan
 * disimpan client-side hanya untuk demo. */
var STATUS_KEY = 'mockup_ticket_status';
function ticketStatus(id, fallback) {
  try {
    var all = JSON.parse(localStorage.getItem(STATUS_KEY) || '{}');
    return all[id] || fallback || 'Open';
  } catch (e) { return fallback || 'Open'; }
}
function setTicketStatus(id, status) {
  var all = {};
  try { all = JSON.parse(localStorage.getItem(STATUS_KEY) || '{}'); } catch (e) {}
  all[id] = status;
  localStorage.setItem(STATUS_KEY, JSON.stringify(all));
}

/* Satu sumber status untuk SEMUA badge di semua halaman.
 *
 * Setiap badge status tiket di-render dengan atribut
 *   <span data-status data-ticket-id="T-001" data-default="Open">
 * dan fungsi ini mengganti isinya dengan ticketStatus(id) saat halaman dimuat.
 * Inilah yang membuat status konsisten: teknisi ubah status -> pelapor &
 * admin melihat nilai terbaru tanpa restart (localStorage dibaca tiap load).
 * Untuk no-JS, generator sudah menulis badge default di dalam span. */
var STATUS_BADGE_CLASSES = {
  'Open': 'bg-warn/10 text-warn dark:text-warn-dark',
  'In Progress': 'bg-accent/10 text-accent dark:text-accent-dark',
  'Resolved': 'bg-good/10 text-good dark:text-good-dark'
};
function statusBadgeHTML(s) {
  var cls = STATUS_BADGE_CLASSES[s] || 'bg-line/40 text-ink2 dark:text-ink2-dark';
  return '<span class="inline-block px-2 py-0.5 rounded-full text-[11px] ' + cls + '">' + s + '</span>';
}
function hydrateStatusBadges() {
  var nodes = document.querySelectorAll('[data-status][data-ticket-id]');
  for (var i = 0; i < nodes.length; i++) {
    var el = nodes[i];
    el.innerHTML = statusBadgeHTML(ticketStatus(el.getAttribute('data-ticket-id'),
                                                el.getAttribute('data-default') || 'Open'));
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', hydrateStatusBadges);
} else {
  hydrateStatusBadges();
}

/* KPI "Sedang dikerjakan" dll. dihitung ulang dari localStorage saat halaman
 * dimuat — tidak di-cache dari saat server start. Markup:
 *   <span data-count-status="In Progress" data-count-tickets="T-001,T-008,...">
 * Hitung hanya tiket yang listed yang statusnya cocok. */
function hydrateStatusCounts() {
  var nodes = document.querySelectorAll('[data-count-status]');
  for (var i = 0; i < nodes.length; i++) {
    var el = nodes[i];
    var match = el.getAttribute('data-count-status');
    var ids = (el.getAttribute('data-count-tickets') || '').split(',');
    var n = 0;
    for (var j = 0; j < ids.length; j++) {
      var id = ids[j].trim();
      if (id && ticketStatus(id, 'Open') === match) n++;
    }
    el.textContent = String(n);
  }
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', hydrateStatusCounts);
} else {
  hydrateStatusCounts();
}
