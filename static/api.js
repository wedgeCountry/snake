/* ApiClient — the only JS layer that talks to the backend. */
window.ApiClient = (function () {
  async function request(path, options) {
    const res = await fetch(path, options);
    if (!res.ok) throw new Error(path + ' -> ' + res.status);
    return res.json();
  }
  return {
    getState: () => request('/api/state'),
    newGame: (torus) => request('/api/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ torus }),
    }),
    setDirection: (direction) => request('/api/direction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ direction }),
    }),
    step: () => request('/api/step', { method: 'POST' }),
    gameOver: () => request('/api/gameover', { method: 'POST' }),
    setSettings: (s) => request('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(s),
    }),
  };
})();
