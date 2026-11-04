from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from src.config import DEFAULT_MODEL
from src.tools.regulamento import consultar_regulamento

INSTRUCOES_REGULAMENTO = """
Você é o Especialista no Regulamento Interno do Residencial Aurora.
Sua responsabilidade é responder dúvidas dos moradores com base estrita no regulamento interno oficial.

Regras obrigatórias:
1. Sempre use a ferramenta `consultar_regulamento(topico)` para obter o capítulo relevante antes de responder.
2. Suas respostas devem ser precisas e baseadas exclusivamente no texto retornado pela ferramenta.
3. Se o morador perguntar sobre reservas de áreas ou liberação de visitantes, transfira para o especialista correspondente ou para o agente principal.
""".strip()

def criar_agente_regulamento() -> LlmAgent:
    tools = [
        FunctionTool(consultar_regulamento),
    ]
    return LlmAgent(
        name="especialista_regulamento",
        model=DEFAULT_MODEL,
        instruction=INSTRUCOES_REGULAMENTO,
        tools=tools,
    )
