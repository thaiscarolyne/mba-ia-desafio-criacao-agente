import json
import random
import sqlite3
from typing import Any, Optional
from src.config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db() -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reservas (
                    codigo TEXT PRIMARY KEY,
                    apartamento TEXT NOT NULL,
                    area TEXT NOT NULL,
                    data TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ativa'
                );
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_area_data_ativa 
                ON reservas (area, data) 
                WHERE status = 'ativa';
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS visitantes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    apartamento TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    data TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS codigos_reservas (
                    codigo TEXT PRIMARY KEY
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS confirmacoes_pendentes (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    acao TEXT NOT NULL,
                    detalhes TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pendente',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conf_session_status 
                ON confirmacoes_pendentes (session_id, status);
            """)
    finally:
        conn.close()

def gerar_codigo_reserva_unico(cursor: sqlite3.Cursor) -> str:
    """Gera um código de reserva no formato RSV-XXXX que nunca repete um código existente ou cancelado."""
    while True:
        num = random.randint(1000, 9999)
        codigo = f"RSV-{num}"
        cursor.execute("SELECT 1 FROM codigos_reservas WHERE codigo = ?", (codigo,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO codigos_reservas (codigo) VALUES (?)", (codigo,))
            return codigo

def criar_reserva_db(apartamento: str, area: str, data: str) -> dict[str, Any]:
    """
    Tenta criar uma reserva atômica para o apartamento na data informada.
    Garantia 5: Exclusividade garantida no instante da gravação através do índice único no SQLite.
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # Gera código único que nunca repete
            codigo = gerar_codigo_reserva_unico(cursor)
            try:
                cursor.execute(
                    "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, 'ativa')",
                    (codigo, apartamento, area, data)
                )
                return {
                    "sucesso": True,
                    "codigo": codigo,
                    "area": area,
                    "data": data,
                    "mensagem": f"Reserva {codigo} para {area} na data {data} realizada com sucesso para o apartamento {apartamento}."
                }
            except sqlite3.IntegrityError:
                # Conflito de unicidade (outra reserva ativa para a mesma área e data)
                return {
                    "sucesso": False,
                    "codigo": None,
                    "area": area,
                    "data": data,
                    "mensagem": f"A data {data} já está reservada por outro morador para a área {area}."
                }
    finally:
        conn.close()

def cancelar_reserva_db(apartamento: str, area: Optional[str] = None, data: Optional[str] = None, codigo: Optional[str] = None) -> dict[str, Any]:
    """
    Cancela reservas pertencentes EXCLUSIVAMENTE ao apartamento da sessão.
    Garantia 2: Nunca altera reservas de outros apartamentos.
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            query = "SELECT codigo, area, data FROM reservas WHERE apartamento = ? AND status = 'ativa'"
            params = [apartamento]
            
            if codigo:
                query += " AND codigo = ?"
                params.append(codigo)
            if area:
                query += " AND area = ?"
                params.append(area)
            if data:
                query += " AND data = ?"
                params.append(data)
                
            cursor.execute(query, params)
            reservas = cursor.fetchall()
            
            if not reservas:
                return {
                    "sucesso": False,
                    "mensagem": f"Nenhuma reserva ativa encontrada com esses dados para o apartamento {apartamento}."
                }
                
            for res in reservas:
                cursor.execute(
                    "UPDATE reservas SET status = 'cancelada' WHERE codigo = ?",
                    (res["codigo"],)
                )
                
            return {
                "sucesso": True,
                "canceladas": [r["codigo"] for r in reservas],
                "mensagem": f"Reserva cancelada com sucesso para o apartamento {apartamento}."
            }
    finally:
        conn.close()

def verificar_area_disponivel(area: str, data: str) -> dict[str, Any]:
    """
    Verifica se a área está livre ou ocupada na data informada.
    Garantia 2: Informa apenas se está livre ou ocupada, NUNCA expõe de quem é a reserva ou códigos de terceiros.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM reservas WHERE area = ? AND data = ? AND status = 'ativa'",
            (area, data)
        )
        row = cursor.fetchone()
        disponivel = row is None
        return {
            "area": area,
            "data": data,
            "disponivel": disponivel,
            "mensagem": "Área disponível para reserva nesta data." if disponivel else "A data solicitada já está ocupada para esta área."
        }
    finally:
        conn.close()

def listar_reservas_apartamento(apartamento: str) -> list[dict[str, Any]]:
    """Retorna todas as reservas ativas do apartamento informado."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT codigo, area, data FROM reservas WHERE apartamento = ? AND status = 'ativa' ORDER BY data",
            (apartamento,)
        )
        return [{"codigo": row["codigo"], "area": row["area"], "data": row["data"]} for row in cursor.fetchall()]
    finally:
        conn.close()

def adicionar_visitante_db(apartamento: str, nome: str, data: str) -> dict[str, Any]:
    """Adiciona uma autorização de entrada de visitante para o apartamento informado."""
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
                (apartamento, nome, data)
            )
            return {
                "sucesso": True,
                "apartamento": apartamento,
                "nome": nome,
                "data": data,
                "mensagem": f"Entrada de {nome} liberada para o dia {data} no apartamento {apartamento}."
            }
    finally:
        conn.close()

def listar_visitantes_apartamento(apartamento: str) -> list[dict[str, Any]]:
    """Retorna todos os visitantes autorizados para o apartamento informado."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT nome, data FROM visitantes WHERE apartamento = ? ORDER BY data",
            (apartamento,)
        )
        return [{"nome": row["nome"], "data": row["data"]} for row in cursor.fetchall()]
    finally:
        conn.close()

def salvar_confirmacao_pendente(id_confirmacao: str, session_id: str, acao: str, detalhes: dict[str, Any]) -> None:
    """Registra uma confirmação pendente no banco para validação idempotente."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO confirmacoes_pendentes (id, session_id, acao, detalhes, status) VALUES (?, ?, ?, ?, 'pendente')",
                (id_confirmacao, session_id, acao, json.dumps(detalhes, ensure_ascii=False))
            )
    finally:
        conn.close()

def obter_confirmacoes_pendentes(session_id: str) -> list[dict[str, Any]]:
    """Retorna todas as confirmações atualmente pendentes para a sessão."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, acao, detalhes FROM confirmacoes_pendentes WHERE session_id = ? AND status = 'pendente' ORDER BY created_at",
            (session_id,)
        )
        pendentes = []
        for row in cursor.fetchall():
            detalhes = json.loads(row["detalhes"]) if row["detalhes"] else {}
            pendentes.append({
                "id": row["id"],
                "acao": row["acao"],
                "detalhes": detalhes
            })
        return pendentes
    finally:
        conn.close()

def consumir_confirmacao_pendente(id_confirmacao: str, session_id: str) -> tuple[bool, Optional[dict[str, Any]]]:
    """
    Consome atomicamente uma confirmação pendente.
    Retorna (True, dados) se estava pendente e foi marcada como respondida.
    Retorna (False, None) se não existia como pendente (gerando HTTP 409).
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, acao, detalhes FROM confirmacoes_pendentes WHERE id = ? AND session_id = ? AND status = 'pendente'",
                (id_confirmacao, session_id)
            )
            row = cursor.fetchone()
            if not row:
                return False, None
            
            # Marca como respondida atomicamente
            cursor.execute(
                "UPDATE confirmacoes_pendentes SET status = 'respondida' WHERE id = ?",
                (id_confirmacao,)
            )
            detalhes = json.loads(row["detalhes"]) if row["detalhes"] else {}
            return True, {
                "id": row["id"],
                "acao": row["acao"],
                "detalhes": detalhes
            }
    finally:
        conn.close()
