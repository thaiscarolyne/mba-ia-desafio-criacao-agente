from typing import Any
from google.adk.tools import ToolContext
from src.database import adicionar_visitante_db, listar_visitantes_apartamento

def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
    """
    Autoriza a entrada de um visitante no condomínio para uma data específica (AAAA-MM-DD).
    O apartamento é obtido exclusivamente da sessão autenticada.
    Esta ação concede acesso físico ao condomínio e SEMPRE exige confirmação do morador.
    """
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        return {"sucesso": False, "mensagem": "Apartamento não identificado na sessão."}
    
    return adicionar_visitante_db(apartamento=apartamento, nome=nome, data=data)

def listar_meus_visitantes(tool_context: ToolContext) -> dict[str, Any]:
    """
    Lista todos os visitantes autorizados para o apartamento do morador autenticado.
    """
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        return {"sucesso": False, "mensagem": "Apartamento não identificado na sessão."}
    
    visitantes = listar_visitantes_apartamento(apartamento)
    return {"apartamento": apartamento, "visitantes": visitantes}
