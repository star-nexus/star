import {DisplayState, canEndTurn} from './state.js';
import {BattlefieldRenderer} from './renderer.js';

const nodes = new Map(), factionNodes = new Map();
const $ = id => {
  if (!nodes.has(id)) nodes.set(id, document.getElementById(id));
  return nodes.get(id);
};
const text = (id, value) => {
  const node = $(id), next = String(value);
  if (node.textContent !== next) node.textContent = next;
};
const factionNames = {wei: '魏', shu: '蜀', wu: '吴', spectator: '全局旁观'};
const unitNames = {infantry: '步兵', cavalry: '骑兵', archer: '弓箭兵'};
const store = new DisplayState(); const pending = new Map();
let selectedId = null, active = 'move', socket, reconnect, canControl = false, noticeTimer, renderer;
let token = new URLSearchParams(location.hash.slice(1)).get('token') || sessionStorage.getItem('star-view-token');
if (location.hash) history.replaceState(null, '', location.pathname + location.search);

function notice(text, error = false, persistent = false) {
  clearTimeout(noticeTimer); $('notice').textContent = text;
  $('notice').className = error ? 'error' : '';
  if (!persistent) noticeTimer = setTimeout(() => $('notice').classList.add('hide'), 2800);
}

function send(command, parameters = {}) {
  const snapshot = store.snapshot;
  if (!snapshot || !canControl || socket?.readyState !== WebSocket.OPEN || pending.size) return;
  const id = crypto.randomUUID(); pending.set(id, command);
  socket.send(JSON.stringify({kind: 'command', id, epoch: snapshot.epoch, command, parameters}));
  if (command === 'end_turn') {
    $('end-turn').classList.add('pressed');
    setTimeout(() => $('end-turn').classList.remove('pressed'), 180);
  }
  updateHud();
}

// Mouse button and Space share this exact input path.
function endTurn() { if (canEndTurn(store.snapshot, canControl)) send('end_turn'); }

function updateHud() {
  const s = store.snapshot; if (!s) return;
  const unit = s.units.find(row => row.id === selectedId);
  if (!unit) selectedId = null;
  text('view', `${factionNames[s.view] || s.view}${canControl ? ' · 指挥视角' : ' · 只读视角'}`);
  text('visual-version', s.visual_version);
  text('map-name', s.scene.map_id);
  text('mode', s.hud.mode === 'turn_based' ? '回合制' : '实时制');
  text('turn', s.hud.mode === 'turn_based' ? `回合 ${s.hud.turn_number}` : `${Math.floor(s.hud.elapsed)} 秒`);
  text('current-player', s.hud.game_over ? '对局结束' : `${factionNames[s.hud.current_player] || '—'} · 当前行动`);
  $('end-turn').disabled = !canEndTurn(s, canControl) || !!pending.size || socket?.readyState !== WebSocket.OPEN;
  $('end-turn').firstChild.textContent = [...pending.values()].includes('end_turn') ? '处理中 ' : '结束回合 ';
  text('turn-hint', s.hud.game_over ? '对局已结束' : !canControl ? '旁观视角不可操作' : s.hud.mode === 'real_time' ? '实时制无需结束回合'
    : s.hud.current_player === s.view ? '点击或按 Space 结束回合' : '等待己方回合');
  $('selection-empty').hidden = !!unit; $('selection').hidden = !unit;
  if (unit) {
    text('unit-name', `${factionNames[unit.faction]} · ${unitNames[unit.unit_type] || unit.unit_type}`);
    const asset = '/assets/' + unit.asset.split('/').map(encodeURIComponent).join('/');
    if ($('unit-art').getAttribute('src') !== asset) $('unit-art').src = asset;
    text('unit-pos', `坐标 ${unit.col}, ${unit.row}`);
    text('count', unit.count); text('ap', unit.ap == null ? '—' : `${unit.ap}/${unit.max_ap}`);
    text('mp', unit.mp ?? '—');
  }
  document.querySelectorAll('[data-command]').forEach(button => {
    button.classList.toggle('active', button.dataset.command === active);
    button.disabled = !unit || !canControl || unit.faction !== s.view || !!pending.size || s.hud.game_over ||
      !s.scene.commands?.includes(button.dataset.command) ||
      (s.hud.mode === 'turn_based' && s.hud.current_player !== s.view);
  });
  const factionRoot = $('factions'), counts = new Map(), ids = new Set();
  for (const u of s.units) counts.set(u.faction, (counts.get(u.faction) || 0) + 1);
  for (const f of s.scene.factions) {
    ids.add(f.id);
    if (!factionNodes.has(f.id)) {
      const row = document.createElement('div'); row.className = 'faction';
      const dot = document.createElement('i'), name = document.createElement('span'), count = document.createElement('small');
      name.textContent = factionNames[f.id]; row.append(dot, name, count); factionRoot.append(row);
      factionNodes.set(f.id, {row, dot, count});
    }
    const {dot, count} = factionNodes.get(f.id);
    const color = `rgb(${f.color.join(',')})`;
    if (dot.style.background !== color) dot.style.background = color;
    const value = `${counts.get(f.id) || 0} 可见部队`;
    if (count.textContent !== value) count.textContent = value;
  }
  for (const [id, node] of factionNodes) if (!ids.has(id)) { node.row.remove(); factionNodes.delete(id); }
  renderer?.update(s, selectedId);
  if (s.hud.game_over) notice(s.hud.winner ? `${factionNames[s.hud.winner] || s.hud.winner} 军获胜` : '对局结束 · 平局', false, true);
}

function pick({unit, tile}) {
  const s = store.snapshot; if (!s || pending.size) return;
  if (unit?.faction === s.view || (!canControl && unit)) {
    selectedId = unit.id; active = 'move'; updateHud(); return;
  }
  const selected = s.units.find(row => row.id === selectedId);
  if (!canControl || !selected) return;
  if (active === 'attack') {
    if (unit) send('attack', {unit_id: selected.id, target_id: unit.id});
    else notice('点击可见敌军作为攻击目标');
  } else if (tile) send(active, {unit_id: selected.id, position: [tile.col, tile.row]});
}

function connect() {
  clearTimeout(reconnect); sessionStorage.setItem('star-view-token', token);
  if (socket) { socket.onclose = null; socket.close(); }
  pending.clear(); canControl = false; store.clear(); selectedId = null;
  $('end-turn').disabled = true;
  socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/stream`);
  socket.onopen = () => socket.send(JSON.stringify({kind: 'hello', token}));
  socket.onmessage = event => {
    let packet; try { packet = JSON.parse(event.data); } catch { notice('显示数据无法解析', true); return; }
    if (packet.kind === 'welcome') {
      canControl = packet.can_control; $('connection').textContent = '已连接'; $('status-dot').className = 'connected'; return;
    }
    if (packet.kind === 'command_result') {
      pending.delete(packet.id); notice(packet.success ? '指令已执行' : packet.error, !packet.success);
      updateHud(); return;
    }
    if (!store.apply(packet)) { socket.send(JSON.stringify({kind: 'resync'})); return; }
    $('connection').textContent = '已连接'; $('status-dot').className = 'connected';
    if (packet.kind === 'snapshot') notice('战场已同步');
    updateHud();
  };
  socket.onclose = event => {
    pending.clear(); canControl = false; store.clear(); selectedId = null;
    $('connection').textContent = '连接中断'; $('status-dot').className = '';
    $('end-turn').disabled = true;
    if (event.code === 1008) {
      notice('凭据无效或请求被拒绝，请重新打开视角链接', true, true);
      sessionStorage.removeItem('star-view-token'); $('credential').showModal();
    } else {
      notice('连接中断，正在重新同步战场…', true, true); reconnect = setTimeout(connect, 1500);
    }
  };
  socket.onerror = () => notice('无法连接服务端', true);
}

try { renderer = new BattlefieldRenderer($('battlefield'), {onPick: pick, onError: notice}); }
catch (error) { notice('浏览器无法创建 WebGL2 画面：' + error.message, true, true); }
$('end-turn').addEventListener('click', endTurn);
$('fit').addEventListener('click', () => renderer?.fit());
document.querySelectorAll('[data-command]').forEach(button => button.addEventListener('click', () => {
  const command = button.dataset.command;
  if (['wait', 'garrison'].includes(command)) send(command, {unit_id: selectedId});
  else { active = command; notice(command === 'attack' ? '点击目标敌军' : '点击目标地格'); updateHud(); }
}));
document.addEventListener('keydown', event => {
  if (['INPUT', 'TEXTAREA'].includes(event.target.tagName) || event.repeat) return;
  if (event.code === 'Space') { event.preventDefault(); endTurn(); }
  if (event.code === 'KeyF') renderer?.fit();
  if (event.code === 'KeyA') { active = 'attack'; updateHud(); }
  if (event.code === 'KeyM') { active = 'move'; updateHud(); }
  if (event.code === 'Escape') { selectedId = null; active = 'move'; updateHud(); }
  const slot = {'Digit1': 'infantry', 'Digit2': 'cavalry', 'Digit3': 'archer', 'Digit4': 'archer', 'Digit5': 'archer'}[event.code];
  if (slot && store.snapshot) {
    const candidates = store.snapshot.units.filter(u => u.faction === store.snapshot.view && u.unit_type === slot);
    const current = candidates.findIndex(u => u.id === selectedId);
    selectedId = candidates[(current + 1) % candidates.length]?.id || null; updateHud();
  }
});
$('join').addEventListener('click', event => {
  if (!$('token').value.trim()) return;
  event.preventDefault(); token = $('token').value.trim(); $('credential').close(); connect();
});
window.addEventListener('pagehide', () => { clearTimeout(reconnect); clearTimeout(noticeTimer); socket?.close(); renderer?.close(); });
window.addEventListener('hashchange', () => {
  const next = new URLSearchParams(location.hash.slice(1)).get('token');
  if (!next) return;
  token = next; history.replaceState(null, '', location.pathname + location.search);
  $('credential').close(); connect();
});
if (token) connect(); else $('credential').showModal();
