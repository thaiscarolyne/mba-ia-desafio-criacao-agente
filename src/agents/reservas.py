from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from src.config import DEFAULT_MODEL
from src.tools.reservas import (
    criar_reserva,
    cancelar_reserva,
    checar_disponibilidade_area,
    listar_minhas_reservas,
    precisa_confirmacao_reserva
)

INSTRUCOES_RESERVAS = """
Você é o Especialista de Reservas do Residencial Aurora.
Sua responsabilidade é gerenciar reservas de áreas comuns (salão de festas, churrasqueira e quadra poliesportiva).

Regras obrigatórias:
1. Sempre use as ferramentas disponíveis para consultar, criar ou cancelar reservas. Nunca invente dados ou códigos de reserva.
2. Cada morador só pode consultar e cancelar as reservas do próprio apartamento (o apartamento é gerenciado pelo sistema).
3. Ao verificar se uma data está disponível, informe apenas se está livre ou ocupada. NUNCA revele quem reservou a data nem códigos de reserva de outros apartamentos.
4. Se o morador solicitar cancelamento de uma reserva que não pertence a ele ou que não existe para o seu apartamento, informe cordialmente que não foi encontrada nenhuma reserva ativa dele naquela data/área.
5. Se o morador perguntar sobre autorização de visitantes ou sobre o regulamento interno/regras do condomínio, faça a transferência para o especialista adequado ou para o agente principal.
""".strip()

def criar_agente_reservas() -> LlmAgent:
    tools = [
        FunctionTool(criar_reserva, require_confirmation=precisa_confirmacao_reserva),
        FunctionTool(cancelar_reserva),
        FunctionTool(checar_disponibilidade_area),
        FunctionTool(listar_minhas_reservas),
    ]
    return LlmAgent(
        name="especialista_reservas",
        model=DEFAULT_MODEL,
        instruction=INSTRUCOES_RESERVAS,
        tools=tools,
    )
