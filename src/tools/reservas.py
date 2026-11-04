import json
from typing import Any, Optional
from google.adk.tools import ToolContext
from src.config import DADOS_DIR
from src.database import (
    criar_reserva_db,
    cancelar_reserva_db,
    verificar_area_disponivel,
    listar_reservas_apartamento
)

def _carregar_taxa_area(area_id: str) -> float:
    """Carrega a taxa em reais da área comum a partir de dados/areas.json."""
    areas_path = DADOS_DIR / "areas.json"
    if areas_path.exists():
        with open(areas_path, "r", encoding="utf-8") as f:
            areas = json.load(f)
            for a in areas:
                if a["id"].lower() == area_id.lower() or a["nome"].lower() == area_id.lower():
                    return float(a.get("taxa", 0.0))
    return 0.0

def precisa_confirmacao_reserva(area: str, data: str, **kwargs: Any) -> bool:
    """
    Garantia 1: Toda ação que gera cobrança (taxa > 0) exige confirmação.
    Áreas com taxa zero (ex: quadra) não geram cobrança e não pedem confirmação.
    """
    taxa = _carregar_taxa_area(area)
    return taxa > 0.0

def criar_reserva(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
    """
    Cria uma reserva de área comum (ex: salao-de-festas, churrasqueira, quadra) para uma data (AAAA-MM-DD).
    O apartamento é obtido exclusivamente da sessão autenticada.
    """
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        return {"sucesso": False, "mensagem": "Apartamento não identificado na sessão."}
    
    # Padroniza id da área se necessário
    area_normalizada = area.lower().strip()
    if "salão" in area_normalizada or "salao" in area_normalizada:
        area_normalizada = "salao-de-festas"
    elif "churrasqueira" in area_normalizada:
        area_normalizada = "churrasqueira"
    elif "quadra" in area_normalizada:
        area_normalizada = "quadra"

    return criar_reserva_db(apartamento=apartamento, area=area_normalizada, data=data)

def cancelar_reserva(area: Optional[str] = None, data: Optional[str] = None, codigo: Optional[str] = None, tool_context: Optional[ToolContext] = None) -> dict[str, Any]:
    """
    Cancela reservas pertencentes ao apartamento da sessão autenticada.
    Não requer confirmação.
    """
    if not tool_context:
        return {"sucesso": False, "mensagem": "Contexto da sessão ausente."}
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        return {"sucesso": False, "mensagem": "Apartamento não identificado na sessão."}
        
    area_normalizada = None
    if area:
        area_normalizada = area.lower().strip()
        if "salão" in area_normalizada or "salao" in area_normalizada:
            area_normalizada = "salao-de-festas"
        elif "churrasqueira" in area_normalizada:
            area_normalizada = "churrasqueira"
        elif "quadra" in area_normalizada:
            area_normalizada = "quadra"

    return cancelar_reserva_db(apartamento=apartamento, area=area_normalizada, data=data, codigo=codigo)

def checar_disponibilidade_area(area: str, data: str) -> dict[str, Any]:
    """
    Verifica se uma área comum está disponível em determinada data (AAAA-MM-DD).
    Informa apenas se está livre ou ocupada, sem revelar reservas de outros apartamentos.
    """
    area_normalizada = area.lower().strip()
    if "salão" in area_normalizada or "salao" in area_normalizada:
        area_normalizada = "salao-de-festas"
    elif "churrasqueira" in area_normalizada:
        area_normalizada = "churrasqueira"
    elif "quadra" in area_normalizada:
        area_normalizada = "quadra"

    return verificar_area_disponivel(area=area_normalizada, data=data)

def listar_minhas_reservas(tool_context: ToolContext) -> dict[str, Any]:
    """
    Lista todas as reservas ativas pertencentes ao apartamento do morador autenticado.
    """
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        return {"sucesso": False, "mensagem": "Apartamento não identificado na sessão."}
    reservas = listar_reservas_apartamento(apartamento)
    return {"apartamento": apartamento, "reservas": reservas}
