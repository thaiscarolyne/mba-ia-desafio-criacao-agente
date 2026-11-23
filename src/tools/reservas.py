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

def normalizar_area(area: Optional[str]) -> Optional[str]:
    """
    Normaliza o identificador da área para o ID oficial em dados/areas.json.
    Retorna None se a área for desconhecida.
    """
    if not area:
        return None
    area_clean = area.lower().strip()
    if "salão" in area_clean or "salao" in area_clean:
        return "salao-de-festas"
    elif "churrasqueira" in area_clean:
        return "churrasqueira"
    elif "quadra" in area_clean:
        return "quadra"
    return None

def _carregar_taxa_area(area: str) -> Optional[float]:
    """
    Carrega a taxa em reais da área comum a partir de dados/areas.json após normalização.
    Retorna None se a área for desconhecida.
    """
    area_normalizada = normalizar_area(area)
    if not area_normalizada:
        return None

    areas_path = DADOS_DIR / "areas.json"
    if areas_path.exists():
        with open(areas_path, "r", encoding="utf-8") as f:
            areas = json.load(f)
            for a in areas:
                if a["id"].lower() == area_normalizada.lower():
                    return float(a.get("taxa", 0.0))
    return None

def precisa_confirmacao_reserva(area: str, data: str, **kwargs: Any) -> bool:
    """
    Garantia 1: Toda ação que gera cobrança (taxa > 0) exige confirmação.
    Áreas com taxa zero (ex: quadra) não geram cobrança e não pedem confirmação.
    Normaliza a área usando a mesma regra da gravação.
    Áreas desconhecidas retornam False para serem recusadas imediatamente na execução da tool.
    """
    taxa = _carregar_taxa_area(area)
    if taxa is None:
        return False
    return taxa > 0.0

def criar_reserva(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
    """
    Cria uma reserva de área comum (ex: salao-de-festas, churrasqueira, quadra) para uma data (AAAA-MM-DD).
    O apartamento é obtido exclusivamente da sessão autenticada.
    Recusa áreas desconhecidas em vez de tratá-las com taxa zero.
    """
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        return {"sucesso": False, "mensagem": "Apartamento não identificado na sessão."}

    area_normalizada = normalizar_area(area)
    if not area_normalizada:
        return {
            "sucesso": False,
            "mensagem": f"Área '{area}' não é reconhecida ou não está disponível para reserva. As áreas reserváveis são: salão de festas, churrasqueira e quadra poliesportiva."
        }

    return criar_reserva_db(apartamento=apartamento, area=area_normalizada, data=data)

def cancelar_reserva(area: Optional[str] = None, data: Optional[str] = None, codigo: Optional[str] = None, tool_context: Optional[ToolContext] = None) -> dict[str, Any]:
    """
    Cancela reservas pertencentes ao apartamento da sessão autenticada.
    Não requer confirmação. Recusa áreas desconhecidas se informadas.
    """
    if not tool_context:
        return {"sucesso": False, "mensagem": "Contexto da sessão ausente."}
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        return {"sucesso": False, "mensagem": "Apartamento não identificado na sessão."}

    area_normalizada = None
    if area:
        area_normalizada = normalizar_area(area)
        if not area_normalizada:
            return {
                "sucesso": False,
                "mensagem": f"Área '{area}' não é reconhecida. As áreas reserváveis são: salão de festas, churrasqueira e quadra poliesportiva."
            }

    return cancelar_reserva_db(apartamento=apartamento, area=area_normalizada, data=data, codigo=codigo)

def checar_disponibilidade_area(area: str, data: str) -> dict[str, Any]:
    """
    Verifica se uma área comum está disponível em determinada data (AAAA-MM-DD).
    Informa apenas se está livre ou ocupada, sem revelar reservas de outros apartamentos.
    Recusa áreas desconhecidas.
    """
    area_normalizada = normalizar_area(area)
    if not area_normalizada:
        return {
            "area": area,
            "data": data,
            "disponivel": False,
            "mensagem": f"Área '{area}' não é reconhecida. As áreas disponíveis para reserva são: salão de festas, churrasqueira e quadra poliesportiva."
        }

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
