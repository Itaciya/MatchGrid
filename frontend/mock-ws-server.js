import { WebSocketServer } from 'ws';
const wss = new WebSocketServer({ port: 8090 });
console.log('Mock WS server on ws://localhost:8090');

wss.on('connection', (ws) => {
  console.log('client connected');
  ws.on('message', (raw) => {
    const m = JSON.parse(raw);
    if (m.type === 'ping') ws.send(JSON.stringify({ type: 'pong' }));
    if (m.type === 'auth') console.log('auth received');
  });
  const send = (type, payload) => ws.readyState === 1 && ws.send(JSON.stringify({ type, payload }));
  let n = 0;
  const t = setInterval(() => {
    n++;
    send('score:update', { matchId: 1, home: n % 5, away: n % 3 });
    if (n % 3 === 0) send('match:status', { matchId: 1, status: n % 2 ? 'live' : 'halftime' });
    if (n % 4 === 0) send('fixture:update', { fixtureId: 7, kickoff: new Date().toISOString() });
    if (n % 5 === 0) send('notification', { id: n, text: `Test notification ${n}`, read: false });
  }, 3000);
  ws.on('close', () => clearInterval(t));
});
