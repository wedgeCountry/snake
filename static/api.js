/* ApiClient — the only JS layer that talks to the backend.
   Transport seam: poll() via REST, or subscribe() via WebSocket when the
   game advertises realTime. */
window.ApiClient = (function () {
  async function request(path, options) {
    const res = await fetch(path, options);
    if (!res.ok) throw new Error(path + ' -> ' + res.status);
    return res.json();
  }
  function post(path, body) {
    return request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
  }
  return {
    listGames: () => request('/api/games'),
    newGame: (gameId, torus, mode) => post('/api/games/' + gameId + '/new', { torus, mode: mode || 'single' }),
    getState: (gameId) => request('/api/games/' + gameId + '/state'),
    sendAction: (gameId, player, action) => post('/api/games/' + gameId + '/action', { player, action }),
    getLeaderboard: (gameId, mode) => request('/api/leaderboard/' + gameId + '/' + (mode || 'single')),
    setSettings: (s) => post('/api/settings', s),
    saveGame: (gameId, name) => post('/api/games/' + gameId + '/save', { name: name || '' }),
    listSavegames: (gameId) => request('/api/games/' + gameId + '/savegames'),
    loadGame: (gameId, saveId) => post('/api/games/' + gameId + '/load/' + saveId, {}),
    deleteSavegame: (gameId, saveId) => request('/api/games/' + gameId + '/savegames/' + saveId, { method: 'DELETE' }),
    poll: (gameId) => request('/api/games/' + gameId + '/state'),
    subscribe: (gameId, sessionId, onEnvelope) => {
      const proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
      const ws = new WebSocket(proto + location.host + '/ws/games/' + gameId + '?session=' + sessionId);
      ws.onmessage = (ev) => onEnvelope(JSON.parse(ev.data));
      return ws;
    },
  };
})();
