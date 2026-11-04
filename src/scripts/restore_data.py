import json
import sqlite3
from src.config import DADOS_DIR, DB_PATH
from src.database import get_connection, init_db

def restore() -> None:
    """Restaura o banco de dados para o estado inicial definido nos arquivos de dados/."""
    init_db()
    conn = get_connection()
    try:
        with conn:
            # Limpa dados operacionais
            conn.execute("DELETE FROM confirmacoes_pendentes;")
            conn.execute("DELETE FROM reservas;")
            conn.execute("DELETE FROM visitantes;")
            conn.execute("DELETE FROM codigos_reservas;")
            
            # Carrega reservas iniciais
            reservas_path = DADOS_DIR / "reservas.json"
            if reservas_path.exists():
                with open(reservas_path, "r", encoding="utf-8") as f:
                    reservas = json.load(f)
                    for r in reservas:
                        conn.execute(
                            "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, 'ativa')",
                            (r["codigo"], r["apartamento"], r["area"], r["data"])
                        )
                        conn.execute(
                            "INSERT OR IGNORE INTO codigos_reservas (codigo) VALUES (?)",
                            (r["codigo"],)
                        )
                        
            # Carrega visitantes iniciais
            visitantes_path = DADOS_DIR / "visitantes.json"
            if visitantes_path.exists():
                with open(visitantes_path, "r", encoding="utf-8") as f:
                    visitantes = json.load(f)
                    for v in visitantes:
                        conn.execute(
                            "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
                            (v["apartamento"], v["nome"], v["data"])
                        )
        print("Dados restaurados com sucesso a partir de dados/.")
    finally:
        conn.close()

def main():
    restore()

if __name__ == "__main__":
    main()
