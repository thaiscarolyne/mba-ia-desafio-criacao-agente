import logging
import uuid
from typing import Any, Optional
from google.adk.apps import App
from google.adk.apps._configs import ResumabilityConfig
from google.adk.runners import Runner
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.adk.flows.llm_flows.functions import REQUEST_CONFIRMATION_FUNCTION_CALL_NAME
from google.genai import types

from src.config import APP_NAME, DB_URL, DEFAULT_USER_ID
from src.agents.coordinator import criar_agente_principal
from src.database import (
    salvar_confirmacao_pendente,
    obter_confirmacoes_pendentes,
    consumir_confirmacao_pendente
)

logger = logging.getLogger(__name__)

class ADKService:
    def __init__(self):
        self.session_service = DatabaseSessionService(db_url=DB_URL)
        self.root_agent = criar_agente_principal()
        self.app = App(
            name=APP_NAME,
            root_agent=self.root_agent,
            resumability_config=ResumabilityConfig(is_resumable=True)
        )
        self.runner = Runner(
            app=self.app,
            session_service=self.session_service
        )

    async def criar_sessao(self, apartamento: str) -> str:
        """Cria uma nova sessão no ADK associada ao apartamento informado."""
        session_id = str(uuid.uuid4())
        await self.session_service.create_session(
            app_name=APP_NAME,
            user_id=DEFAULT_USER_ID,
            session_id=session_id,
            state={"apartamento": str(apartamento)}
        )
        return session_id

    async def obter_sessao(self, session_id: str):
        """Retorna a sessão a partir do session_id, ou None se não existir."""
        return await self.session_service.get_session(
            app_name=APP_NAME,
            user_id=DEFAULT_USER_ID,
            session_id=session_id
        )

    async def obter_eventos(self, session_id: str) -> Optional[list[dict[str, Any]]]:
        """Retorna todos os eventos gravados na sessão em ordem cronológica."""
        session = await self.obter_sessao(session_id)
        if not session:
            return None
        return [event.model_dump(mode="json", exclude_none=True) for event in session.events]

    async def enviar_mensagem(self, session_id: str, texto: str) -> Optional[dict[str, Any]]:
        """Processa uma mensagem do usuário na sessão."""
        session = await self.obter_sessao(session_id)
        if not session:
            return None

        user_content = types.Content(
            role="user",
            parts=[types.Part(text=texto)]
        )

        resposta_partes: list[str] = []
        async for event in self.runner.run_async(
            user_id=DEFAULT_USER_ID,
            session_id=session_id,
            new_message=user_content
        ):
            self._extrair_confirmacoes_de_evento(event, session_id)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        resposta_partes.append(part.text)

        resposta_final = "".join(resposta_partes).strip()
        confirmacoes = obter_confirmacoes_pendentes(session_id)

        return {
            "resposta": resposta_final,
            "confirmacoes_pendentes": confirmacoes
        }

    async def responder_confirmacao(self, session_id: str, id_confirmacao: str, confirmado: bool) -> tuple[int, dict[str, Any]]:
        """
        Responde a uma confirmação pendente.
        Retorna (200, payload) se processada com sucesso.
        Retorna (409, payload) se id_confirmacao não estava pendente.
        Retorna (404, payload) se sessão não existir.
        """
        session = await self.obter_sessao(session_id)
        if not session:
            return 404, {"erro": "Sessão não encontrada."}

        # Consome atomicamente para evitar replays (Garantia 1)
        sucesso, dados = consumir_confirmacao_pendente(id_confirmacao, session_id)
        if not sucesso:
            return 409, {"erro": f"Confirmação '{id_confirmacao}' não encontrada ou já respondida."}

        # Constrói a mensagem de resposta à confirmação
        resume_content = types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=id_confirmacao,
                        name=REQUEST_CONFIRMATION_FUNCTION_CALL_NAME,
                        response={"confirmed": confirmado}
                    )
                )
            ]
        )

        resposta_partes: list[str] = []
        async for event in self.runner.run_async(
            user_id=DEFAULT_USER_ID,
            session_id=session_id,
            new_message=resume_content
        ):
            self._extrair_confirmacoes_de_evento(event, session_id)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        resposta_partes.append(part.text)

        resposta_final = "".join(resposta_partes).strip()
        confirmacoes = obter_confirmacoes_pendentes(session_id)

        return 200, {
            "resposta": resposta_final,
            "confirmacoes_pendentes": confirmacoes
        }

    def _extrair_confirmacoes_de_evento(self, event, session_id: str) -> None:
        """Extrai solicitações de confirmação do evento e as registra no banco."""
        function_calls = event.get_function_calls()
        for fc in function_calls:
            if fc.name == REQUEST_CONFIRMATION_FUNCTION_CALL_NAME:
                conf_id = fc.id
                args = fc.args or {}
                orig_fc = args.get("originalFunctionCall") or {}
                acao = orig_fc.get("name", "acao")
                detalhes = orig_fc.get("args") or {}
                if conf_id:
                    salvar_confirmacao_pendente(conf_id, session_id, acao, detalhes)

# Instância singleton do serviço
adk_service = ADKService()
