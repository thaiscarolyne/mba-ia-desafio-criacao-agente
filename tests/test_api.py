import asyncio
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.scripts.restore_data import restore
from src.database import (
    criar_reserva_db,
    cancelar_reserva_db,
    listar_reservas_apartamento,
    listar_visitantes_apartamento,
    salvar_confirmacao_pendente,
    consumir_confirmacao_pendente
)
from src.tools.regulamento import consultar_regulamento
from src.tools.reservas import (
    normalizar_area,
    _carregar_taxa_area,
    precisa_confirmacao_reserva,
    criar_reserva,
    cancelar_reserva,
    checar_disponibilidade_area
)

@pytest.fixture(autouse=True)
def setup_database():
    restore()

def test_verificacao_dados_iniciais():
    client = TestClient(app)
    # Passo 1
    r_101 = client.get("/apartamentos/101/reservas")
    assert r_101.status_code == 200
    reservas_101 = r_101.json()
    assert any(r["codigo"] == "RSV-1377" and r["area"] == "quadra" and r["data"] == "2030-03-09" for r in reservas_101)

    r_302 = client.get("/apartamentos/302/visitantes")
    assert r_302.status_code == 200
    visitantes_302 = r_302.json()
    assert any(v["nome"] == "Marina Duarte" and v["data"] == "2030-03-16" for v in visitantes_302)

def test_criar_sessao_e_consultar_eventos():
    client = TestClient(app)
    # Passo 2
    resp = client.post("/sessoes", json={"apartamento": "101"})
    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data
    session_id = data["session_id"]

    # Consulta eventos de sessão recém criada
    r_eventos = client.get(f"/sessoes/{session_id}/eventos")
    assert r_eventos.status_code == 200
    assert isinstance(r_eventos.json(), list)

    # Passo 9: Sessão inexistente -> 404
    r_404 = client.get("/sessoes/sessao-inexistente-12345/eventos")
    assert r_404.status_code == 404

def test_confirmacoes_validacoes_e_409():
    client = TestClient(app)
    resp = client.post("/sessoes", json={"apartamento": "101"})
    session_id = resp.json()["session_id"]

    # Passo 9: ID inexistente -> 409
    r_inexistente = client.post(
        f"/sessoes/{session_id}/confirmacoes",
        json={"id": "id-inexistente", "confirmado": True}
    )
    assert r_inexistente.status_code == 409

    # Simula gravação de uma confirmação pendente
    salvar_confirmacao_pendente(
        id_confirmacao="conf-teste-1",
        session_id=session_id,
        acao="criar_reserva",
        detalhes={"area": "salao-de-festas", "data": "2030-04-20"}
    )

    # Primeira resposta: consome com sucesso
    ok, dados = consumir_confirmacao_pendente("conf-teste-1", session_id)
    assert ok is True
    assert dados["detalhes"]["area"] == "salao-de-festas"

    # Passo 8: Reenvio do mesmo id -> deve falhar com 409
    ok_segunda_vez, _ = consumir_confirmacao_pendente("conf-teste-1", session_id)
    assert ok_segunda_vez is False

def test_garantia_5_dois_moradores_uma_reserva():
    """Garantia 5 (Passo 14): Dois moradores pedem a mesma data e aprovam simultaneamente."""
    # S3 (101) e S4 (201) disputam o salão em 2030-05-11
    res1 = criar_reserva_db("101", "salao-de-festas", "2030-05-11")
    res2 = criar_reserva_db("201", "salao-de-festas", "2030-05-11")

    # Uma deve vencer e a outra ser recusada sem erro de servidor
    assert (res1["sucesso"] and not res2["sucesso"]) or (res2["sucesso"] and not res1["sucesso"])

    # No banco, a soma de reservas para o salão nesta data deve ser exatamente 1
    reservas_101 = [r for r in listar_reservas_apartamento("101") if r["area"] == "salao-de-festas" and r["data"] == "2030-05-11"]
    reservas_201 = [r for r in listar_reservas_apartamento("201") if r["area"] == "salao-de-festas" and r["data"] == "2030-05-11"]
    assert len(reservas_101) + len(reservas_201) == 1

def test_garantia_4_regulamento_consultado_nao_carregado():
    """Garantia 4 (Passo 12): Horário da piscina aos domingos."""
    resultado = consultar_regulamento("Até que horas a piscina funciona aos domingos?")
    assert "Capítulo IV: Piscina" in resultado["capitulo_encontrado"]
    assert "20h" in resultado["conteudo"]
    # Nenhum outro capítulo deve estar no conteúdo
    assert "Capítulo I:" not in resultado["conteudo"]
    assert "Capítulo II:" not in resultado["conteudo"]
    assert "Capítulo III:" not in resultado["conteudo"]
    assert "Capítulo V:" not in resultado["conteudo"]
    assert "Capítulo VI:" not in resultado["conteudo"]
    assert "Capítulo VII:" not in resultado["conteudo"]
    assert "Capítulo VIII:" not in resultado["conteudo"]
    assert "Capítulo IX:" not in resultado["conteudo"]
    assert "Capítulo X:" not in resultado["conteudo"]
    assert "Capítulo XI:" not in resultado["conteudo"]
    assert "Capítulo XII:" not in resultado["conteudo"]

def test_codigos_reservas_unicos_nao_repetem():
    """Garantia 3: Códigos de reserva nunca repetem, mesmo após cancelamento."""
    res1 = criar_reserva_db("101", "quadra", "2030-04-06")
    assert res1["sucesso"]
    cod1 = res1["codigo"]

    # Cancela
    cancelar_reserva_db("101", codigo=cod1)

    # Cria outra
    res2 = criar_reserva_db("101", "salao-de-festas", "2030-04-20")
    assert res2["sucesso"]
    cod2 = res2["codigo"]

    assert cod1 != cod2
    assert cod1 not in ["RSV-1377", "RSV-4821", "RSV-2950"]
    assert cod2 not in ["RSV-1377", "RSV-4821", "RSV-2950"]

def test_normalizacao_area_e_recusa_area_desconhecida():
    """
    Validação da normalização de área antes de decidir confirmação e recusa de área desconhecida:
    - 'salao de festas', 'Salão de festas', 'salao-de-festas' normalizam para 'salao-de-festas' e exigem confirmação (taxa 150 > 0).
    - 'churrasqueira' exige confirmação (taxa 80 > 0).
    - 'quadra' e 'quadra poliesportiva' não exigem confirmação (taxa 0).
    - Áreas desconhecidas (ex: 'piscina', 'cinema') não geram confirmação prévia e são recusadas na tool.
    """
    # 1. Normalização pré-confirmação
    assert normalizar_area("salao de festas") == "salao-de-festas"
    assert normalizar_area("Salão de Festas") == "salao-de-festas"
    assert normalizar_area("salao-de-festas") == "salao-de-festas"
    assert normalizar_area("salão") == "salao-de-festas"
    assert normalizar_area("churrasqueira") == "churrasqueira"
    assert normalizar_area("quadra poliesportiva") == "quadra"
    assert normalizar_area("piscina") is None
    assert normalizar_area("desconhecido") is None

    # 2. Taxas carregadas corretamente mesmo com variações no texto
    assert _carregar_taxa_area("salao de festas") == 150.0
    assert _carregar_taxa_area("Salão de Festas") == 150.0
    assert _carregar_taxa_area("churrasqueira") == 80.0
    assert _carregar_taxa_area("quadra poliesportiva") == 0.0
    assert _carregar_taxa_area("piscina") is None

    # 3. Decisão de confirmação
    assert precisa_confirmacao_reserva("salao de festas", "2030-04-20") is True
    assert precisa_confirmacao_reserva("Salão de Festas", "2030-04-20") is True
    assert precisa_confirmacao_reserva("churrasqueira", "2030-04-20") is True
    assert precisa_confirmacao_reserva("quadra", "2030-04-20") is False
    assert precisa_confirmacao_reserva("quadra poliesportiva", "2030-04-20") is False
    assert precisa_confirmacao_reserva("piscina", "2030-04-20") is False

    # 4. Execução da tool: área normalizada grava corretamente
    ctx = MagicMock()
    ctx.state = {"apartamento": "101"}

    res_salao = criar_reserva("salao de festas", "2030-04-20", ctx)
    assert res_salao["sucesso"] is True
    assert res_salao["area"] == "salao-de-festas"

    # 5. Execução da tool: área desconhecida é recusada e não é gravada como taxa zero
    res_piscina = criar_reserva("piscina", "2030-04-25", ctx)
    assert res_piscina["sucesso"] is False
    assert "não é reconhecida" in res_piscina["mensagem"]

    # Confere que a piscina não foi para o banco de reservas
    reservas = listar_reservas_apartamento("101")
    assert not any(r["area"] == "piscina" for r in reservas)

    # 6. Checagem de disponibilidade para área desconhecida
    disp = checar_disponibilidade_area("piscina", "2030-04-25")
    assert disp["disponivel"] is False
    assert "não é reconhecida" in disp["mensagem"]
