# Integração com Copilot Studio

Este documento descreve as adaptações realizadas no projeto Dex para funcionar como servidor MCP compatível com Microsoft Copilot Studio.

## Mudanças Realizadas

### 1. Limpeza do Código
- **Removidas funcionalidades desnecessárias:**
  - YouTube Analytics
  - Google Drive/Sheets
  - Trello
- **Mantidas apenas:**
  - Google Analytics 4 (GA4)
  - Google Search Console

### 2. Novo Endpoint MCP

#### `/mcp` (POST)
Endpoint principal compatível com protocolo MCP streamable-1.0 para Copilot Studio.

**Métodos suportados:**
- `initialize` - Inicializa o servidor MCP
- `tools/list` - Lista as ferramentas disponíveis
- `tools/call` - Executa uma ferramenta específica

### 3. Ferramentas Disponíveis

#### Google Analytics 4
1. **`listar_contas_ga4`**
   - Lista todas as contas e propriedades GA4
   - Não requer parâmetros

2. **`consulta_ga4`** 
   - Consulta dados do GA4
   - Parâmetros: dimensão, métrica, período, data_fim, property_id, filtros

3. **`consulta_ga4_pivot`**
   - Consulta GA4 com tabela pivot
   - Parâmetros: dimensão, dimensão_pivot, métrica, período, data_fim, property_id, limite_linhas

#### Google Search Console
1. **`listar_sites_search_console`**
   - Lista sites disponíveis no Search Console
   - Não requer parâmetros

2. **`consulta_search_console_custom`**
   - Consulta customizada ao Search Console
   - Parâmetros: site_url (obrigatório), data_inicio, data_fim, dimensões, métricas, filtros

3. **`verificar_propriedade_site_search_console`**
   - Verifica se um site está disponível
   - Parâmetros: site_url (obrigatório)

### 4. Schema OpenAPI

Criado arquivo `swagger.yaml` seguindo especificações Swagger 2.0 com:
- Protocolo: `x-ms-agentic-protocol: mcp-streamable-1.0`
- Endpoint único: `/mcp` (POST)
- Host: `dex-mcp-server-1212.onrender.com`

### 5. Endpoints Adicionais

- **`/swagger.yaml`** - Serve o schema YAML
- **`/`** - Endpoint raiz com status do servidor

## Como Integrar no Copilot Studio

1. **URL do Servidor:** `https://dex-mcp-server-1212.onrender.com`
2. **Schema URL:** `https://dex-mcp-server-1212.onrender.com/swagger.yaml`
3. **Protocolo:** MCP Streamable 1.0
4. **Autenticação:** Nenhuma (para testes)

## Variáveis de Ambiente Necessárias

```
GOOGLE_CREDENTIALS=<json_da_conta_de_servico>
ANTHROPIC_API_KEY=<chave_opcional_para_nlp>
```

## Formato das Requisições MCP

### Inicialização
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "initialize",
  "params": {}
}
```

### Listar Ferramentas
```json
{
  "jsonrpc": "2.0", 
  "id": "2",
  "method": "tools/list",
  "params": {}
}
```

### Executar Ferramenta
```json
{
  "jsonrpc": "2.0",
  "id": "3", 
  "method": "tools/call",
  "params": {
    "name": "consulta_ga4",
    "arguments": {
      "dimensao": "country",
      "metrica": "sessions",
      "periodo": "7daysAgo"
    }
  }
}
```

## Status do Projeto

✅ Código limpo (apenas GA4 e Search Console)  
✅ Endpoint MCP implementado  
✅ Schema OpenAPI criado  
✅ Deployd no Render  
✅ Pronto para integração com Copilot Studio