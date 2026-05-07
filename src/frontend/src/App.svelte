<script lang="ts">
  import Router from 'svelte-spa-router';
  import { wrap } from 'svelte-spa-router/wrap';
  import { checkAuth, isAuthenticated } from './stores/auth';
  import { push } from 'svelte-spa-router';
  import { onMount } from 'svelte';

  const routes = {
    '/login': wrap({ asyncComponent: () => import('./routes/Login.svelte') }),
    '/register': wrap({ asyncComponent: () => import('./routes/Register.svelte') }),
    '/projects': wrap({ asyncComponent: () => import('./routes/Dashboard.svelte') }),
    '/projects/:projectId': wrap({ asyncComponent: () => import('./routes/ProjectWorkspace.svelte') }),
    '/projects/:projectId/chats/:chatId': wrap({ asyncComponent: () => import('./routes/ProjectWorkspace.svelte') }),
    '/logs': wrap({ asyncComponent: () => import('./routes/Logs.svelte') }),
    '/logs/:sessionId': wrap({ asyncComponent: () => import('./routes/Logs.svelte') }),
    '*': wrap({ asyncComponent: () => import('./routes/Login.svelte') }),
  };

  onMount(async () => {
    const authed = await checkAuth();
    if (authed) {
      push('/projects');
    } else {
      push('/login');
    }
  });
</script>

<main>
  <Router {routes} />
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: var(--font-sans);
    background: var(--color-bg);
    color: var(--color-text);
  }
  :global(*) {
    box-sizing: border-box;
  }
  main {
    height: 100vh;
    width: 100vw;
    overflow: hidden;
  }
</style>
