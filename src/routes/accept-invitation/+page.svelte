<script>
  import { onMount } from 'svelte';
  import { getClerk } from '../../lib/auth/clerk-client.js';

  let host = $state(/** @type {HTMLDivElement | null} */ (null));
  let error = $state('');

  onMount(() => {
    /** @type {any} */ let clerk;
    void (async () => {
    const ticket = new URLSearchParams(window.location.search).get('__clerk_ticket');
    if (!ticket) { error = 'La invitación no es válida o ya venció.'; return; }
    clerk = await getClerk();
    if (!clerk) { error = 'Falta configurar PUBLIC_CLERK_PUBLISHABLE_KEY para aceptar invitaciones.'; return; }
    clerk.mountSignUp(host, {
      routing: 'hash',
      forceRedirectUrl: '/'
    });
    })();
    return () => { if (clerk && host) clerk.unmountSignUp(host); };
  });
</script>

<svelte:head><title>Aceptar invitación — SentriX</title></svelte:head>
<main class="auth-page"><section class="auth-card" aria-labelledby="invitation-title"><h1 id="invitation-title">Activa tu cuenta</h1><p>Define tu contraseña para acceder al panel SentriX.</p>{#if error}<p class="error" role="alert">{error}</p>{:else}<div class="clerk-host" bind:this={host} aria-label="Formulario para aceptar invitación"></div>{/if}</section></main>
<style>:global(body){margin:0;background:linear-gradient(135deg,#eef5fb,#f7faff);font-family:Inter,"Segoe UI",system-ui,sans-serif;color:#0b315e}.auth-page{min-height:100vh;display:grid;place-items:center;padding:24px}.auth-card{width:min(100%,440px);padding:38px;border:1px solid #d9e5ef;border-radius:16px;background:#fff;box-shadow:0 16px 45px #143b641a}h1{margin:0 0 8px;font-size:26px}p{color:#52708c;line-height:1.55}.error{padding:12px;border:1px solid #e8c5c7;border-radius:8px;background:#fff4f4;color:#a34249}.clerk-host{margin-top:24px}</style>
