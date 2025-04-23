"""
Script para depurar a versão e API do FastMCP
"""

import importlib.metadata
import inspect
import sys

def check_fastmcp_version():
    try:
        # Tenta obter versão do pacote
        try:
            version = importlib.metadata.version('mcp')
            print(f"Versão do MCP: {version}")
        except importlib.metadata.PackageNotFoundError:
            print("Pacote MCP não encontrado via metadata. Verificando pelo módulo...")
    
        # Importa o módulo FastMCP
        from mcp.server.fastmcp import FastMCP
        print(f"Módulo FastMCP encontrado: {FastMCP}")
        
        # Verifica os atributos e métodos disponíveis
        print("\nAtributos e métodos da classe FastMCP:")
        for name, obj in inspect.getmembers(FastMCP):
            if not name.startswith('_'):  # Exclui métodos privados
                print(f"- {name}: {type(obj)}")
        
        # Cria uma instância para verificar os atributos
        print("\nCriando instância de FastMCP...")
        mcp = FastMCP("debug-agent")
        
        print("\nAtributos da instância de FastMCP:")
        for name in dir(mcp):
            if not name.startswith('_'):  # Exclui atributos privados
                try:
                    attr = getattr(mcp, name)
                    print(f"- {name}: {type(attr)}")
                except Exception as e:
                    print(f"- {name}: ERRO ao acessar - {str(e)}")
        
        # Verificar o caminho do módulo
        print(f"\nLocalização do módulo: {inspect.getfile(FastMCP)}")
        
        # Verifica como FastAPI deve ser integrado
        print("\nVerificando documentação ou código fonte para integração com FastAPI...")
        doc = inspect.getdoc(FastMCP)
        if doc:
            print(f"Documentação da classe: {doc[:500]}...")
        else:
            print("Sem documentação disponível.")
            
        print("\nFastMCP debugging concluído.")
            
    except Exception as e:
        print(f"Erro durante a depuração: {str(e)}")

if __name__ == "__main__":
    print("Sistema Python:", sys.version)
    print("Caminho do Python:", sys.executable)
    print("Caminhos de módulos:", sys.path)
    print("\n" + "="*50 + "\n")
    check_fastmcp_version()
