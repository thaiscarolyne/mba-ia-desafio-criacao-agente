from contextlib import asynccontextmanager
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from src.database import (
    init_db,
    listar_reservas_apartamento,
    listar_visitantes_apartamento
)
from src.services.adk_runner import adk_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa o banco de dados na inicialização da aplicação
    init_db()
    yield

app = FastAPI(
    title="Assistente Virtual do Residencial Aurora",
    description="API com Google ADK para atendimento dos moradores do Residencial Aurora",
    version="1.0.0",
    lifespan=lifespan
)

# Modelos de Requisição e Resposta
class CriarSessaoRequest(BaseModel):
    apartamento: str

class CriarSessaoResponse(BaseModel):
    session_id: str

class EnviarMensagemRequest(BaseModel):
    texto: str

class ConfirmacaoItem(BaseModel):
    id: str
    acao: str
    detalhes: dict[str, Any]

class MensagemResponse(BaseModel):
    resposta: str
    confirmacoes_pendentes: list[ConfirmacaoItem]

class ResponderConfirmacaoRequest(BaseModel):
    id: str
    confirmado: bool

# Rotas de Sessão e Atendimento

@app.post(
    "/sessoes",
    status_code=status.HTTP_201_CREATED,
    response_model=CriarSessaoResponse,
    summary="Cria uma nova sessão vinculada a um apartamento"
)
async def criar_sessao(request: CriarSessaoRequest):
    session_id = await adk_service.criar_sessao(request.apartamento)
    return {"session_id": session_id}

@app.post(
    "/sessoes/{session_id}/mensagens",
    status_code=status.HTTP_200_OK,
    response_model=MensagemResponse,
    summary="Envia uma mensagem na sessão"
)
async def enviar_mensagem(session_id: str, request: EnviarMensagemRequest):
    resultado = await adk_service.enviar_mensagem(session_id, request.texto)
    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_id}' não encontrada."
        )
    return resultado

@app.post(
    "/sessoes/{session_id}/confirmacoes",
    status_code=status.HTTP_200_OK,
    response_model=MensagemResponse,
    summary="Responde a uma confirmação pendente"
)
async def responder_confirmacao(session_id: str, request: ResponderConfirmacaoRequest):
    status_code, resultado = await adk_service.responder_confirmacao(
        session_id=session_id,
        id_confirmacao=request.id,
        confirmado=request.confirmado
    )
    if status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=resultado.get("erro", f"Sessão '{session_id}' não encontrada.")
        )
    if status_code == 409:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=resultado.get("erro", f"Confirmação '{request.id}' inválida ou já respondida.")
        )
    return resultado

@app.get(
    "/sessoes/{session_id}/eventos",
    status_code=status.HTTP_200_OK,
    summary="Retorna todos os eventos gravados na sessão"
)
async def obter_eventos(session_id: str):
    eventos = await adk_service.obter_eventos(session_id)
    if eventos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_id}' não encontrada."
        )
    return eventos

# Rotas de Verificação Administrativa

@app.get(
    "/apartamentos/{apartamento}/reservas",
    status_code=status.HTTP_200_OK,
    summary="Lista reservas ativas de um apartamento"
)
async def ver_reservas_apartamento(apartamento: str):
    return listar_reservas_apartamento(apartamento)

@app.get(
    "/apartamentos/{apartamento}/visitantes",
    status_code=status.HTTP_200_OK,
    summary="Lista visitantes autorizados de um apartamento"
)
async def ver_visitantes_apartamento(apartamento: str):
    return listar_visitantes_apartamento(apartamento)
