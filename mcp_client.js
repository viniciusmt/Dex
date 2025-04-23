// mcp_client.js
const { app, BrowserWindow, ipcMain } = require('electron');
const axios = require('axios');
const path = require('path');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  mainWindow.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Comunicação com o servidor MCP
ipcMain.handle('send-message', async (event, message) => {
  try {
    const response = await axios.post('http://localhost:3000/process', { message });
    return response.data;
  } catch (error) {
    console.error('Erro ao enviar mensagem para o servidor MCP:', error);
    return { error: 'Falha na comunicação com o servidor MCP' };
  }
});

// Interface HTML para o cliente
const fs = require('fs');
fs.writeFileSync(
  'index.html',
  `<!DOCTYPE html>
  <html>
  <head>
    <meta charset="UTF-8">
    <title>Claude Desktop Agent</title>
    <style>
      body {
        font-family: Arial, sans-serif;
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
      }
      .chat-container {
        border: 1px solid #ccc;
        border-radius: 5px;
        padding: 10px;
        height: 400px;
        overflow-y: auto;
        margin-bottom: 20px;
      }
      .input-container {
        display: flex;
      }
      #message-input {
        flex-grow: 1;
        padding: 10px;
        border: 1px solid #ccc;
        border-radius: 5px;
      }
      #send-button {
        margin-left: 10px;
        padding: 10px 20px;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
      }
      .message {
        margin-bottom: 10px;
        padding: 10px;
        border-radius: 5px;
      }
      .user-message {
        background-color: #e9e9e9;
        margin-left: 20%;
      }
      .agent-message {
        background-color: #f0f7ff;
        margin-right: 20%;
      }
    </style>
  </head>
  <body>
    <h1>Claude Desktop Agent</h1>
    <div class="chat-container" id="chat-container"></div>
    <div class="input-container">
      <input type="text" id="message-input" placeholder="Digite sua mensagem...">
      <button id="send-button">Enviar</button>
    </div>

    <script>
      const { ipcRenderer } = require('electron');
      
      const chatContainer = document.getElementById('chat-container');
      const messageInput = document.getElementById('message-input');
      const sendButton = document.getElementById('send-button');
      
      function addMessage(content, isUser) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.classList.add(isUser ? 'user-message' : 'agent-message');
        messageElement.textContent = content;
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
      
      async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;
        
        addMessage(message, true);
        messageInput.value = '';
        
        try {
          const response = await ipcRenderer.invoke('send-message', message);
          
          if (response.error) {
            addMessage(\`Erro: \${response.error}\`, false);
          } else if (response.claudeResponse && response.claudeResponse.content) {
            addMessage(response.claudeResponse.content[0].text, false);
          } else {
            addMessage('Resposta recebida, mas em formato inesperado.', false);
          }
        } catch (error) {
          addMessage(\`Erro ao processar a mensagem: \${error.message}\`, false);
        }
      }
      
      sendButton.addEventListener('click', sendMessage);
      messageInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
          sendMessage();
        }
      });
    </script>
  </body>
  </html>`
);