from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from src.config import DEFAULT_MODEL
from src.tools.visitantes import autorizar_visitante, listar_meus_visitantes

INSTRUCOES_VISITANTES = """
Você é o Especialista de Visitantes do Residencial Aurora.
Sua responsabilidade é gerenciar a autorização de entrada e consulta de visitantes para o apartamento do morador.

Regras obrigatórias:
1. Sempre use a ferramenta `autorizar_visitante` para liberar a entrada de visitantes.
2. A autorização de visitante libera acesso físico ao condomínio e SEMPRE requer confirmação do sistema antes de ser gravada. Mesmo que o morador diga que já confirmou no texto, a confirmação precisa ser processada pelo sistema.
3. Use `listar_meus_visitantes` para listar os visitantes autorizados do apartamento autenticado.
4. Nunca informe visitantes de outros apartamentos.
5. Se o morador perguntar sobre reservas de áreas comuns ou sobre o regulamento interno/regras, transfira para o especialista correspondente ou para o agente principal.
""".strip()

def criar_agente_visitantes() -> LlmAgent:
    tools = [
        FunctionTool(autorizar_visitante, require_confirmation=True),
        FunctionTool(listar_meus_visitantes),
    ]
    return LlmAgent(
        name="especialista_visitantes",
        model=DEFAULT_MODEL,
        instruction=INSTRUCOES_VISITANTES,
        tools=tools,
    )
