<script>
  import { onMount } from 'svelte';
  import { getClerk } from '../../lib/auth/clerk-client.js';

  let host = $state(/** @type {HTMLDivElement | null} */ (null));
  let error = $state('');

  onMount(() => {
    /** @type {any} */ let clerk;
    void (async () => {
    clerk = await getClerk();
    if (!clerk) {
      error = 'Falta configurar PUBLIC_CLERK_PUBLISHABLE_KEY para habilitar el acceso.';
      return;
    }
    if (clerk.user) {
      window.location.replace('/');
      return;
    }
    clerk.mountSignIn(host, {
      routing: 'path',
      path: '/sign-in',
      withSignUp: false,
      forceRedirectUrl: '/'
    });
    })();
    return () => { if (clerk && host) clerk.unmountSignIn(host); };
  });
</script>

<svelte:head><title>Ingresar — SentriX</title></svelte:head>

<main class="auth-page">
  <section class="auth-card" aria-labelledby="sign-in-title">
    <div class="brand"><img src="/sentrix-logo-192.png" alt="" /><div><strong>Sentri<span>X</span></strong><small>Sistema de vigilancia inteligente</small></div></div>
    <h1 id="sign-in-title">Acceso al panel</h1>
    <p>Ingresa con la cuenta que recibiste por invitación.</p>
    {#if error}<p class="error" role="alert">{error}</p>{:else}<div class="clerk-host" bind:this={host} aria-label="Formulario de inicio de sesión"></div>{/if}
  </section>
</main>

<style>
  :global(body){margin:0;background:linear-gradient(135deg,#eef5fb,#f7faff);font-family:Inter,"Segoe UI",system-ui,sans-serif;color:#0b315e}.auth-page{min-height:100vh;display:grid;place-items:center;padding:24px}.auth-card{width:min(100%,440px);padding:38px;border:1px solid #d9e5ef;border-radius:16px;background:#fff;box-shadow:0 16px 45px #143b641a}.brand{display:flex;align-items:center;gap:12px}.brand img{width:48px;height:48px;object-fit:contain}.brand strong{display:block;font-size:24px}.brand strong span{color:#087bd3}.brand small{display:block;margin-top:3px;color:#54718f;font-size:10px}h1{margin:30px 0 8px;font-size:26px}p{color:#52708c;line-height:1.55}.error{padding:12px;border:1px solid #e8c5c7;border-radius:8px;background:#fff4f4;color:#a34249}.clerk-host{margin-top:24px}
</style>
