<script>
  import { onMount } from 'svelte';
  import { getClerk, getSessionToken, signOutAndRedirect } from '../../lib/auth/clerk-client.js';

  /** @typedef {{ id: string, email: string, display_name?: string, role: 'admin' | 'operator', is_active: boolean }} User */
  /** @type {User | null} */ let profile = $state(null);
  /** @type {User[]} */ let users = $state([]);
  let loading = $state(true);
  let error = $state('');
  let notice = $state('');
  let email = $state('');
  let displayName = $state('');
  let role = $state('operator');
  let sending = $state(false);

  /** @param {string} path @param {RequestInit} [options] */
  async function api(path, options = {}) {
    const token = await getSessionToken();
    const headers = new Headers(options.headers);
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(path, { ...options, headers });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) { window.location.assign('/sign-in'); throw new Error('Tu sesión expiró.'); }
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  async function loadUsers() {
    const data = await api('/api/users?limit=20&offset=0');
    users = data.items ?? [];
  }
  /** @param {SubmitEvent} event */
  async function invite(event) {
    event.preventDefault(); error = ''; notice = ''; sending = true;
    try {
      await api('/api/auth/invitations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, display_name: displayName, role }) });
      notice = `Invitación enviada a ${email}.`;
      email = ''; displayName = ''; role = 'operator';
      await loadUsers();
    } catch (reason) { error = reason instanceof Error ? reason.message : String(reason); }
    finally { sending = false; }
  }
  onMount(() => {
    void (async () => {
      try {
        const clerk = await getClerk();
        if (!clerk?.user) { window.location.replace('/sign-in'); return; }
        const currentProfile = /** @type {User} */ (await api('/api/auth/me'));
        profile = currentProfile;
        if (currentProfile.role !== 'admin') { error = 'Acceso denegado: esta sección es solo para administradores.'; return; }
        await loadUsers();
      } catch (reason) { error = reason instanceof Error ? reason.message : String(reason); }
      finally { loading = false; }
    })();
  });
</script>

<svelte:head><title>Usuarios — SentriX</title></svelte:head>
<main class="page">
  <header><a href="/">← Volver al panel</a><button type="button" onclick={signOutAndRedirect}>Cerrar sesión</button></header>
  <h1>Usuarios e invitaciones</h1><p class="subtitle">Administración de acceso del panel SentriX.</p>
  {#if error}<p class="message error" role="alert">{error}</p>{/if}
  {#if notice}<p class="message success" role="status">{notice}</p>{/if}
  {#if profile?.role === 'admin'}
    <section class="card"><h2>Invitar usuario</h2><form onsubmit={invite}><label>Correo<input type="email" required bind:value={email} placeholder="operador@sentrix.pe" /></label><label>Nombre visible<input required maxlength="100" bind:value={displayName} placeholder="Nombre del operador" /></label><label>Rol<select bind:value={role}><option value="operator">Operador</option><option value="admin">Administrador</option></select></label><button disabled={sending}>{sending ? 'Enviando…' : 'Enviar invitación'}</button></form></section>
    <section class="card"><h2>Usuarios registrados</h2>{#if loading}<p>Cargando usuarios…</p>{:else if !users.length}<p>No hay usuarios para mostrar.</p>{:else}<div class="table"><table><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Estado</th></tr></thead><tbody>{#each users as user (user.id)}<tr><td>{user.display_name ?? '—'}</td><td>{user.email}</td><td>{user.role}</td><td>{user.is_active ? 'Activo' : 'Inactivo'}</td></tr>{/each}</tbody></table></div>{/if}</section>
  {/if}
</main>

<style>:global(body){margin:0;background:#f4f7fb;color:#173b65;font-family:Inter,"Segoe UI",system-ui,sans-serif}.page{max-width:1040px;margin:auto;padding:36px 24px 70px}header{display:flex;justify-content:space-between;align-items:center}a{color:#0969b5;font-weight:700;text-decoration:none}button{border:0;border-radius:7px;background:#075dad;color:#fff;padding:10px 14px;font:inherit;font-weight:700;cursor:pointer}button:disabled{opacity:.6}h1{margin:30px 0 6px}.subtitle{margin:0 0 25px;color:#59728d}.card{margin-top:20px;padding:22px;border:1px solid #dce6ef;border-radius:12px;background:#fff}h2{margin:0 0 18px;font-size:18px}form{display:grid;grid-template-columns:1fr 1fr 160px auto;gap:12px;align-items:end}label{display:grid;gap:6px;font-size:12px;font-weight:700}input,select{padding:10px;border:1px solid #cbd9e6;border-radius:6px;font:inherit}.table{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left}th{background:#0b4277;color:#fff;font-size:11px;text-transform:uppercase}th,td{padding:12px;border-bottom:1px solid #e5edf4}.message{padding:12px 14px;border-radius:8px}.error{background:#fff0f0;color:#9d3540}.success{background:#e9f8f1;color:#186a4f}@media(max-width:720px){form{grid-template-columns:1fr}.page{padding:24px 14px}}</style>
