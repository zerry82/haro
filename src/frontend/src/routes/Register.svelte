<script lang="ts">
  import { register } from '../stores/auth';
  import { push } from 'svelte-spa-router';

  let email = $state('');
  let password = $state('');
  let name = $state('');
  let error = $state('');
  let loading = $state(false);

  async function handleSubmit() {
    error = '';
    loading = true;
    try {
      await register(email, password, name);
      push('/login');
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="container">
  <div class="card">
    <h1>회원가입</h1>
    <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
      <input type="text" placeholder="이름" bind:value={name} required />
      <input type="email" placeholder="이메일" bind:value={email} required />
      <input type="password" placeholder="비밀번호" bind:value={password} required />
      {#if error}<p class="error">{error}</p>{/if}
      <button type="submit" disabled={loading}>{loading ? '가입 중...' : '회원가입'}</button>
    </form>
    <p class="link">이미 계정이 있으신가요? <a href="#/login">로그인</a></p>
  </div>
</div>

<style>
  .container { display: flex; align-items: center; justify-content: center; height: 100vh; }
  .card { background: #16213e; padding: 2.5rem; border-radius: 12px; width: 380px; text-align: center; }
  h1 { margin: 0 0 1.5rem; color: #e94560; }
  form { display: flex; flex-direction: column; gap: 0.75rem; }
  input { padding: 0.75rem; border: 1px solid #333; border-radius: 8px; background: #0f3460; color: #e0e0e0; font-size: 1rem; }
  input:focus { outline: none; border-color: #e94560; }
  button { padding: 0.75rem; border: none; border-radius: 8px; background: #e94560; color: white; font-size: 1rem; cursor: pointer; }
  button:disabled { opacity: 0.6; }
  .error { color: #e94560; font-size: 0.85rem; margin: 0; }
  .link { margin-top: 1rem; font-size: 0.85rem; color: #888; }
  .link a { color: #e94560; text-decoration: none; }
</style>
