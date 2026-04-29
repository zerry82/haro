<script lang="ts">
  import Router from 'svelte-spa-router';
  import Login from './routes/Login.svelte';
  import Register from './routes/Register.svelte';
  import Dashboard from './routes/Dashboard.svelte';
  import ProjectWorkspace from './routes/ProjectWorkspace.svelte';
  import Logs from './routes/Logs.svelte';
  import { checkAuth, isAuthenticated } from './stores/auth';
  import { push } from 'svelte-spa-router';
  import { onMount } from 'svelte';

  const routes = {
    '/login': Login,
    '/register': Register,
    '/projects': Dashboard,
    '/projects/:projectId': ProjectWorkspace,
    '/projects/:projectId/chats/:chatId': ProjectWorkspace,
    '/logs': Logs,
    '/logs/:sessionId': Logs,
    '*': Login,
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
