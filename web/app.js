const icons = {
  bluetooth:'m7 7 10 10-5 4V3l5 4L7 17',
  arrow:'M6 18 18 6M6 6h12v12', back:'m14 6-6 6 6 6',
  carplay:'M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4l-3 3-3-3H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2ZM10 8l5 3-5 3Z',
  settings:'m10 3-.8 2.4-2 .9-2.4-.5-2 3.4 1.6 1.9v2L2.8 15l2 3.4 2.4-.5 2 .9.8 2.2h4l.8-2.2 2-.9 2.4.5 2-3.4-1.6-1.9v-2l1.6-1.9-2-3.4-2.4.5-2-.9L14 3ZM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8',
  route:'M6 21V9a5 5 0 0 1 10 0v3M12 8l4 4 4-4M3 21h6',
  replay:'M4 10a8 8 0 1 1 1 7M4 4v6h6',
  audio:'M11 4 5 9H2v6h3l6 5ZM15 8a6 6 0 0 1 0 8M18 5a10 10 0 0 1 0 14',
  sun:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5',
  info:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M12 11v6M12 7v.1', plus:'M12 5v14M5 12h14'
};
document.querySelectorAll('[data-icon]').forEach(el => {
  el.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${icons[el.dataset.icon]}"></path></svg>`;
});
const $ = id => document.getElementById(id);
let state = null, bootTimer, toastTimer, refreshing = false;
let prefs = {theme:'dark', brightness:100};
try { prefs = {...prefs, ...JSON.parse(localStorage.getItem('drivesphere') || '{}')}; } catch {}
function applyPrefs() {
  prefs.brightness = Math.max(40, Math.min(100, Number(prefs.brightness) || 100));
  $('display').classList.toggle('light', prefs.theme === 'light');
  $('display').style.filter = `brightness(${prefs.brightness / 100})`;
  $('brightness').value = prefs.brightness;
  $('brightness-value').textContent = `${prefs.brightness} %`;
  document.querySelectorAll('[data-theme]').forEach(b => { b.classList.toggle('selected', b.dataset.theme === prefs.theme); b.setAttribute('aria-pressed', b.dataset.theme === prefs.theme); });
  try { localStorage.setItem('drivesphere', JSON.stringify(prefs)); } catch {}
}
applyPrefs();
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 6500); }
function screen(name) {
  document.querySelectorAll('.screen').forEach(s => s.hidden = s.id !== name);
  if (name === 'settings') refresh();
  const focus = $(name).querySelector('button');
  if ($('boot').hidden) focus?.focus({preventScroll:true});
}
function endBoot() { clearTimeout(bootTimer); $('boot').hidden = true; document.querySelector('.screen:not([hidden]) button')?.focus({preventScroll:true}); }
function boot() {
  screen('home'); $('boot').hidden = false;
  [...$('display').children].forEach(el => { if (el.id !== 'boot') el.inert = true; });
  const track = document.querySelector('.boot-track span'); track.style.animation = 'none'; void track.offsetWidth; track.style.animation = '';
  $('skip-boot').focus(); clearTimeout(bootTimer); bootTimer = setTimeout(finishBoot, matchMedia('(prefers-reduced-motion: reduce)').matches ? 400 : 3400);
}
function finishBoot() { [...$('display').children].forEach(el => el.inert = false); endBoot(); }
$('skip-boot').onclick = finishBoot;
$('replay').onclick = $('system-replay').onclick = boot;
document.querySelector('.brand').onclick = e => { e.preventDefault(); screen('home'); };
document.querySelectorAll('.back').forEach(b => b.onclick = () => screen('home'));
$('open-settings').onclick = () => screen('settings');
$('open-carplay').onclick = () => { screen('carplay'); refresh(); };
document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => {
  document.querySelectorAll('[data-tab]').forEach(x => { x.classList.toggle('active', x === b); x.setAttribute('aria-pressed', x === b); });
  document.querySelectorAll('[data-panel]').forEach(p => p.hidden = p.dataset.panel !== b.dataset.tab);
});
document.querySelectorAll('[data-theme]').forEach(b => b.onclick = () => { prefs.theme = b.dataset.theme; applyPrefs(); });
$('brightness').oninput = e => { prefs.brightness = Number(e.target.value); applyPrefs(); };
document.addEventListener('keydown', e => { if (e.key === 'Escape') { if (!$('boot').hidden) finishBoot(); else screen('home'); } });
function tick() { $('clock').textContent = new Date().toLocaleTimeString('de-AT', {hour:'2-digit', minute:'2-digit'}); }
tick(); setInterval(tick, 1000);
async function api(path, data) {
  const r = await fetch(`/api/${path}`, {method:data ? 'POST' : 'GET', headers:data ? {'Content-Type':'application/json','X-DriveSphere-Token':state?.token || ''} : {}, body:data ? JSON.stringify(data) : undefined, signal:AbortSignal.timeout(20000)});
  const result = await r.json(); if (!r.ok) throw Error(result.error || 'Aktion fehlgeschlagen.'); return result;
}
function render() {
  $('mode').textContent = state.preview ? 'VORSCHAU' : 'RASPBERRY PI';
  $('system-mode').textContent = state.preview ? 'Vorschau ohne Hardware' : 'Lokaler Hardwarezugriff';
  $('carplay-status').textContent = state.carplay.running ? 'CarPlay-Anwendung geöffnet' : state.carplay.configured && state.carplay.touch_home ? 'Anwendung startbereit' : 'Einrichtung erforderlich';
  $('connection-title').textContent = state.carplay.running ? 'CarPlay ist geöffnet.' : state.preview ? 'Dein iPhone. Auf deinem Bike.' : 'Deine Tour beginnt hier.';
  $('connection-message').textContent = state.preview ? 'Dies ist die Menüvorschau. Auf dem Raspberry Pi öffnet diese Taste eure eingerichtete CarPlay-Anwendung.' : state.carplay.running ? 'Tippe in CarPlay unten rechts auf Home, um zum Startmenü zurückzukehren.' : !state.carplay.configured ? 'Die CarPlay-Anwendung ist noch nicht eingerichtet. Hinterlege ihren Startbefehl in der DriveSphere-Konfiguration.' : !state.carplay.touch_home ? 'Touch-Home fehlt. Öffne Einstellungen → System für die Einrichtung.' : 'Starte CarPlay und verbinde dein iPhone. Die Home-Taste bleibt am Display erreichbar.';
  $('launch').disabled = state.preview || !state.carplay.configured || !state.carplay.touch_home || state.carplay.running;
  $('launch').firstChild.textContent = state.carplay.running ? 'CarPlay läuft ' : 'CarPlay starten ';
  $('stop-carplay').hidden = !state.carplay.running;
  $('pair').disabled = !state.bluetooth.manager;
  $('audio-manager').disabled = !state.audio.manager;
  $('volume').disabled = state.audio.volume === null;
  if (document.activeElement !== $('volume') && state.audio.volume !== null) $('volume').value = state.audio.volume;
  $('volume-value').textContent = state.audio.volume === null ? '—' : `${state.audio.volume} %`;
  $('audio-status').textContent = state.audio.volume === null ? 'Kein Audiozugriff. Die Lautstärke ist auf einem eingerichteten Raspberry Pi verfügbar.' : 'Steuert den Standardausgang von PipeWire. Wähle dein verbundenes Headset als Ausgabe.';
  const checks = $('checks'); checks.replaceChildren();
  if (state.preview) {
    checks.textContent = 'Hardwareprüfung ist nur auf dem Raspberry Pi verfügbar.';
  } else {
    state.checks.forEach(check => {
      const row = document.createElement('div'); row.className = `check ${check.ok ? 'ok' : 'issue'}`;
      const mark = document.createElement('span'); mark.textContent = check.ok ? '✓' : '!'; mark.setAttribute('aria-hidden', 'true');
      const info = document.createElement('span');
      const title = document.createElement('strong'); title.textContent = check.name;
      const detail = document.createElement('small'); detail.textContent = check.detail;
      info.append(title, detail); row.append(mark, info); checks.append(row);
    });
  }
  const devices = $('devices'); devices.replaceChildren();
  if (!state.bluetooth.devices.length) {
    const p = document.createElement('p'); p.textContent = state.preview ? 'In der Vorschau werden keine Bluetooth-Geräte verbunden.' : state.bluetooth.error || 'Noch kein gekoppeltes Headset. Schalte es in den Kopplungsmodus und wähle „Neues Gerät koppeln“.'; devices.append(p);
  }
  state.bluetooth.devices.forEach(device => {
    const row = document.createElement('div'); row.className = 'device';
    const label = document.createElement('span'); label.textContent = device.name;
    const sub = document.createElement('small'); sub.textContent = device.connected ? 'Verbunden' : 'Gekoppelt'; label.append(sub);
    const button = document.createElement('button'); button.textContent = device.connected ? 'Trennen' : 'Verbinden'; button.onclick = () => action(button, 'bluetooth', {address:device.address, connect:!device.connected});
    row.append(label,button); devices.append(row);
  });
}
async function refresh() {
  if (refreshing) return; refreshing = true;
  try { state = await api('status'); render(); }
  catch { $('mode').textContent = 'OFFLINE'; $('carplay-status').textContent = 'Menüserver nicht erreichbar'; $('devices').textContent = 'Menüserver nicht erreichbar. Starte server.py.'; $('launch').disabled = $('pair').disabled = $('volume').disabled = $('audio-manager').disabled = true; }
  finally { refreshing = false; }
}
async function action(button, endpoint, data = {}) {
  button.disabled = true;
  try { const result = await api(endpoint, data); if (result.message) toast(result.message); }
  catch(e) { toast(e.message); }
  finally { button.disabled = false; await refresh(); }
}
$('refresh').onclick = refresh;
$('check-refresh').onclick = refresh;
$('pair').onclick = () => action($('pair'), 'pair');
$('audio-manager').onclick = () => action($('audio-manager'), 'audio-manager');
$('launch').onclick = () => action($('launch'), 'carplay');
$('stop-carplay').onclick = () => action($('stop-carplay'), 'carplay/stop');
$('volume').oninput = e => $('volume-value').textContent = `${e.target.value} %`;
$('volume').onchange = () => action($('volume'), 'volume', {value:Number($('volume').value)});
if (new URLSearchParams(location.search).get('boot') === 'skip') {
  finishBoot();
} else {
  boot();
}
refresh(); setInterval(refresh, 10000);
