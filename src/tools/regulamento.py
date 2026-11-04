import re
from typing import Any
from src.config import DADOS_DIR

def _carregar_capitulos_regulamento() -> dict[str, str]:
    """Lê dados/regulamento.md e segmenta o documento por capítulos."""
    regulamento_path = DADOS_DIR / "regulamento.md"
    if not regulamento_path.exists():
        return {}
        
    with open(regulamento_path, "r", encoding="utf-8") as f:
        conteudo = f.read()

    # Divide por títulos de capítulos '## Capítulo ...'
    partes = re.split(r"(## Capítulo [^\n]+)", conteudo)
    capitulos = {}
    
    # O primeiro elemento antes do primeiro capítulo é o cabeçalho geral
    for i in range(1, len(partes), 2):
        titulo = partes[i].strip()
        texto = partes[i + 1].strip() if i + 1 < len(partes) else ""
        capitulos[titulo] = f"{titulo}\n\n{texto}"
        
    return capitulos

def consultar_regulamento(topico: str) -> dict[str, Any]:
    """
    Garantia 4: O regulamento é consultado pontualmente por capítulo, nunca carregado por inteiro.
    Retorna apenas o capítulo pertinente ao tópico pesquisado, garantindo que nenhum trecho
    de outros capítulos seja inserido no histórico de eventos da sessão.
    """
    capitulos = _carregar_capitulos_regulamento()
    if not capitulos:
        return {"erro": "Regulamento interno não encontrado."}

    topico_lower = topico.lower()
    
    # Mapeamento semântico direto de palavras-chave para capítulos
    mapeamento = {
        "piscina": "Capítulo IV",
        "nadar": "Capítulo IV",
        "deck": "Capítulo IV",
        "academia": "Capítulo V",
        "fitness": "Capítulo V",
        "brinquedoteca": "Capítulo V",
        "playground": "Capítulo V",
        "festa": "Capítulo VI",
        "salão": "Capítulo VI",
        "salao": "Capítulo VI",
        "churrasqueira": "Capítulo VI",
        "quadra": "Capítulo VII",
        "esporte": "Capítulo VII",
        "garagem": "Capítulo VIII",
        "veículo": "Capítulo VIII",
        "veiculo": "Capítulo VIII",
        "carro": "Capítulo VIII",
        "vaga": "Capítulo VIII",
        "estacionamento": "Capítulo VIII",
        "animal": "Capítulo IX",
        "animais": "Capítulo IX",
        "pet": "Capítulo IX",
        "cachorro": "Capítulo IX",
        "gato": "Capítulo IX",
        "silêncio": "Capítulo III",
        "silencio": "Capítulo III",
        "barulho": "Capítulo III",
        "som": "Capítulo III",
        "obra": "Capítulo III",
        "mudança": "Capítulo X",
        "mudanca": "Capítulo X",
        "reforma": "Capítulo X",
        "entrega": "Capítulo X",
        "lixo": "Capítulo XI",
        "reciclagem": "Capítulo XI",
        "descarte": "Capítulo XI",
        "multa": "Capítulo XII",
        "penalidade": "Capítulo XII",
        "infração": "Capítulo XII",
        "infracao": "Capítulo XII",
        "advertência": "Capítulo XII",
        "advertencia": "Capítulo XII",
    }
    
    capitulo_alvo = None
    for palavra, cap in mapeamento.items():
        if palavra in topico_lower:
            capitulo_alvo = cap
            break
            
    if capitulo_alvo:
        for titulo, conteudo in capitulos.items():
            if capitulo_alvo in titulo:
                return {
                    "topico": topico,
                    "capitulo_encontrado": titulo,
                    "conteudo": conteudo
                }

    # Se não houver match direto no mapeamento, faz busca por frequência de palavras
    palavras_busca = set(re.findall(r"\w+", topico_lower))
    melhor_titulo = None
    maior_score = 0
    
    for titulo, conteudo in capitulos.items():
        texto_lower = conteudo.lower()
        score = sum(texto_lower.count(p) for p in palavras_busca if len(p) > 2)
        if score > maior_score:
            maior_score = score
            melhor_titulo = titulo
            
    if melhor_titulo and maior_score > 0:
        return {
            "topico": topico,
            "capitulo_encontrado": melhor_titulo,
            "conteudo": capitulos[melhor_titulo]
        }
        
    # Retorna disposições gerais se nenhum for encontrado
    primeiro_capitulo = next(iter(capitulos.keys()))
    return {
        "topico": topico,
        "capitulo_encontrado": primeiro_capitulo,
        "conteudo": capitulos[primeiro_capitulo]
    }
