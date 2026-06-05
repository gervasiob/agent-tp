const setupPanel = document.querySelector('#setupPanel');
const chatPanel = document.querySelector('#chatPanel');
const connectForm = document.querySelector('#connectForm');
const connectionType = document.querySelector('#connectionType');
const databaseField = document.querySelector('#databaseField');
const folderField = document.querySelector('#folderField');
const chatForm = document.querySelector('#chatForm');
const messages = document.querySelector('#messages');
const messageInput = document.querySelector('#messageInput');
const exportFormat = document.querySelector('#exportFormat');
const connectionTitle = document.querySelector('#connectionTitle');
const micButton = document.querySelector('#micButton');
const handsFreeButton = document.querySelector('#handsFreeButton');
let history = [];
let handsFree = false;

connectionType.addEventListener('change', () => {
  const database = connectionType.value === 'database';
  databaseField.hidden = !database;
  folderField.hidden = database;
});

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Error inesperado');
  }
  return response.json();
}

function showChat(connection) {
  setupPanel.hidden = true;
  chatPanel.hidden = false;
  connectionTitle.textContent = `${connection.name} · ${connection.type === 'database' ? 'Base de datos' : 'Carpeta'}`;
}

function showSetup() {
  chatPanel.hidden = true;
  setupPanel.hidden = false;
}

function appendMessage(role, content, downloads = []) {
  const bubble = document.createElement('div');
  bubble.className = `message ${role}`;
  bubble.textContent = content;
  if (downloads.length) {
    const links = document.createElement('div');
    links.className = 'downloads';
    downloads.forEach((download) => {
      const link = document.createElement('a');
      link.href = download.url;
      link.textContent = `Descargar ${download.name}`;
      link.target = '_blank';
      links.appendChild(link);
    });
    bubble.appendChild(links);
  }
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
  history.push({ role, content });
  if (role === 'assistant' && handsFree) speak(content);
}

connectForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(connectForm);
  const payload = Object.fromEntries(form.entries());
  try {
    const data = await api('/api/connect', { method: 'POST', body: JSON.stringify(payload) });
    showChat(data.connection);
  } catch (error) {
    alert(error.message);
  }
});

document.querySelector('#demoButton').addEventListener('click', async () => {
  const data = await api('/api/demo', { method: 'POST', body: '{}' });
  showChat(data.connection);
});

document.querySelector('#disconnectButton').addEventListener('click', async () => {
  await api('/api/connect', { method: 'DELETE' });
  history = [];
  messages.innerHTML = '';
  showSetup();
});

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  messageInput.value = '';
  appendMessage('user', message);
  appendMessage('assistant', 'Analizando datos locales...');
  const loading = messages.lastElementChild;
  try {
    const data = await api('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, history: history.slice(0, -1), export_format: exportFormat.value || null }),
    });
    loading.remove();
    history.pop();
    appendMessage('assistant', data.message, data.downloads);
  } catch (error) {
    loading.textContent = error.message;
  }
});

function speak(text) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'es-AR';
  window.speechSynthesis.speak(utterance);
}

function startDictation() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert('Este navegador no soporta dictado por Web Speech API.');
    return;
  }
  const recognition = new SpeechRecognition();
  recognition.lang = 'es-AR';
  recognition.interimResults = false;
  recognition.onstart = () => micButton.classList.add('listening');
  recognition.onend = () => micButton.classList.remove('listening');
  recognition.onresult = (event) => {
    messageInput.value = event.results[0][0].transcript;
    if (handsFree) chatForm.requestSubmit();
  };
  recognition.start();
}

micButton.addEventListener('click', startDictation);
handsFreeButton.addEventListener('click', () => {
  handsFree = !handsFree;
  handsFreeButton.textContent = handsFree ? 'Audio activo' : 'Modo audio';
  handsFreeButton.classList.toggle('listening', handsFree);
});

api('/api/status')
  .then((data) => data.configured ? showChat(data.connection) : showSetup())
  .catch(showSetup);
