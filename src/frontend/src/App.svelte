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
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
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
