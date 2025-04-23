// mcp_server.js
const express = require('express');
const cors = require('cors');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Carregar configuração do agente
const loadAgentConfig = () => {
  try {
    const configPath = path.join('C:\\Users\\Vinicius\\Projetos\\agent_mcp', 'hello_wolrd.json');
    const configData = fs.readFileSync(configPath, 'utf8');
    return JSON.parse(configData);
  } catch (error) {
    console.error('Erro ao carregar a configuração do agente:', error);
    return null;
  }
};

// Endpoint para processar mensagens
app.post('/process', async (req, res) => {
  try {
    const { message } = req.body;
    const agentConfig = loadAgentConfig();
    
    if (!agentConfig) {
      return res.status(500).json({ error: 'Configuração do agente não encontrada' });
    }
    
    // Chamada para a API do Claude
    const response = await axios.post(agentConfig.endpoint, {
      model: agentConfig.model,
      messages: [
        { role: 'system', content: agentConfig.system_prompt },
        { role: 'user', content: message }
      ],
      max_tokens: agentConfig.max_tokens,
      temperature: agentConfig.temperature
    }, {
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': agentConfig.api_key,
        'anthropic-version': '2023-06-01'
      }
    });
    
    // Acesso aos dados locais (exemplo)
    const localData = {
      // Aqui você pode adicionar código para acessar seus dados locais
      // Por exemplo:
      // files: fs.readdirSync('caminho/para/seus/dados')
    };
    
    // Combinar resposta da API com dados locais
    const result = {
      claudeResponse: response.data,
      localData: localData
    };
    
    res.json(result);
  } catch (error) {
    console.error('Erro ao processar mensagem:', error);
    res.status(500).json({ 
      error: 'Erro ao processar a mensagem',
      details: error.message
    });
  }
});

// Endpoint para acessar dados locais
app.get('/data/:folder', (req, res) => {
  try {
    const { folder } = req.params;
    const folderPath = path.join('C:\\Users\\Vinicius\\Projetos\\agent_mcp', folder);
    
    if (!fs.existsSync(folderPath)) {
      return res.status(404).json({ error: 'Pasta não encontrada' });
    }
    
    const files = fs.readdirSync(folderPath);
    res.json({ files });
  } catch (error) {
    console.error('Erro ao acessar dados locais:', error);
    res.status(500).json({ error: 'Erro ao acessar dados locais' });
  }
});

// Iniciar o servidor
app.listen(PORT, () => {
  console.log(`Servidor MCP rodando na porta ${PORT}`);
  console.log(`Configure o Claude desktop para acessar: http://localhost:${PORT}/process`);
});