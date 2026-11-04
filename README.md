# Assistente Virtual do Residencial Aurora

Assistente virtual inteligente para o aplicativo dos moradores do **Residencial Aurora**, desenvolvido em Python 3.12 com **Google ADK (Agent Development Kit 2.9.1)** e **FastAPI**. O assistente permite reservas de áreas comuns, cancelamento de reservas próprias, autorização de visitantes e esclarecimento de dúvidas sobre o regulamento interno com rigoroso cumprimento das regras condominiais implementadas a nível de código determinístico.

---

## Arquitetura

O sistema adota uma arquitetura hierárquica baseada no padrão de coordenação e especialistas do Google ADK, com divisão clara de responsabilidades:

```
                      ┌──────────────────────┐
                      │   Agente Principal   │
                      │    (Coordenador)     │
                      └──────────┬───────────┘
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Especialista   │    │   Especialista   │    │   Especialista   │
│     Reservas     │    │    Visitantes    │    │   Regulamento    │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Tools Reservas  │    │ Tools Visitantes │    │ Tool Regulamento │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         └───────────────────────┼───────────────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │   SQLite Persistente  │
                     │  (condominio.db /     │
                     │  DatabaseSession)     │
                     └───────────────────────┘
```

### 1. `AgentePrincipal` (`src/agents/coordinator.py`)
- **Responsabilidade**: Ponto de entrada das mensagens do morador. Identifica a intenção (reservas, visitantes ou regras) e delega o atendimento para o especialista adequado.
- **Acionamento**: Configurado como `root_agent` da aplicação (`src/services/adk_runner.py`). Aciona os especialistas via transferência nativa do ADK (`sub_agents`).
- **Motivo**: Mantém a janela de contexto limpa e desacopla as responsabilidades de negócio. O agente principal **não contém o regulamento interno em suas instruções**, respeitando os limites de tokens e as diretrizes do desafio.

### 2. `EspecialistaReservas` (`src/agents/reservas.py`)
- **Responsabilidade**: Gestão do ciclo de vida das reservas das áreas comuns (salão de festas, churrasqueira e quadra poliesportiva).
- **Acionamento**: Subagente do coordenador (`sub_agents`).
- **Motivo**: Especializa o raciocínio em reservas, disponibilidade e cancelamentos. Conecta-se às tools determinísticas de persistência e validação de taxa.
- **Tools**:
  - `checar_disponibilidade_area`: Verifica se a data está livre sem revelar dados alheios.
  - `criar_reserva`: Cria a reserva usando o apartamento da sessão e valida taxa para confirmação.
  - `cancelar_reserva`: Cancela reservas do apartamento autenticado sem pedir confirmação.
  - `listar_minhas_reservas`: Lista apenas as reservas do apartamento autenticado.

### 3. `EspecialistaVisitantes` (`src/agents/visitantes.py`)
- **Responsabilidade**: Autorização de entrada de convidados e listagem de visitantes autorizados.
- **Acionamento**: Subagente do coordenador (`sub_agents`).
- **Motivo**: Isola as operações de segurança e concessão de acesso físico ao condomínio.
- **Tools**:
  - `autorizar_visitante`: Registra o visitante associado ao apartamento da sessão com confirmação obrigatória do morador.
  - `listar_meus_visitantes`: Lista visitantes autorizados do apartamento autenticado.

### 4. `EspecialistaRegulamento` (`src/agents/regulamento.py`)
- **Responsabilidade**: Responder dúvidas dos moradores com base exclusiva nas regras oficiais do condomínio.
- **Acionamento**: Subagente do coordenador (`sub_agents`).
- **Motivo**: Centraliza a consulta ao regulamento interno sem poluir o histórico com o texto integral do condomínio.
- **Tools**:
  - `consultar_regulamento`: Busca e retorna apenas o capítulo pertinente ao assunto questionado.

---

## Garantias

As cinco garantias exigidas pelo desafio foram implementadas a nível de código determinístico, impossibilitando que técnicas de prompt injection ou comportamentos estocásticos do modelo quebrem as regras do condomínio.

### Garantia 1: Cobrança ou acesso só com confirmação
- **Arquivo**: `src/tools/reservas.py`
  - **Trecho**: Linhas 24-30
    ```python
    def precisa_confirmacao_reserva(area: str, data: str, **kwargs: Any) -> bool:
        taxa = _carregar_taxa_area(area)
        return taxa > 0.0
    ```
    Associada à tool em `src/agents/reservas.py`:
    ```python
    FunctionTool(criar_reserva, require_confirmation=precisa_confirmacao_reserva)
    ```
- **Arquivo**: `src/agents/visitantes.py`
  - **Trecho**: Linhas 22-25
    ```python
    FunctionTool(autorizar_visitante, require_confirmation=True)
    ```
- **Arquivo**: `src/services/adk_runner.py` e `src/database.py`
  - **Trecho**: Método `responder_confirmacao` em `adk_runner.py` e função `consumir_confirmacao_pendente` em `database.py`.
- **Por que não depende do modelo**: A obrigatoriedade de confirmação é configurada no Python via `require_confirmation` nas instâncias de `FunctionTool`. Quando a ação envolve cobrança (`taxa > 0`) ou acesso físico (`autorizar_visitante`), o runtime do ADK intercepta a execução e suspende o fluxo emitindo `adk_request_confirmation`. Mesmo que o morador escreva *"já estou confirmando aqui"*, a gravação no banco só ocorre após o envio explícito via rota `POST /sessoes/{id}/confirmacoes`. Respostas com IDs inexistentes ou já respondidos recebem HTTP 409 por validação atômica no banco de dados.

---

### Garantia 2: Cada sessão pertence a um apartamento
- **Arquivo**: `src/services/adk_runner.py`
  - **Trecho**: Linhas 36-44 (`criar_sessao`)
    ```python
    await self.session_service.create_session(
        app_name=APP_NAME,
        user_id=DEFAULT_USER_ID,
        session_id=session_id,
        state={"apartamento": str(apartamento)}
    )
    ```
- **Arquivo**: `src/tools/reservas.py` e `src/tools/visitantes.py`
  - **Trecho**: `criar_reserva`, `cancelar_reserva`, `listar_minhas_reservas`, `autorizar_visitante`
    ```python
    apartamento = tool_context.state.get("apartamento")
    ```
- **Arquivo**: `src/database.py`
  - **Trecho**: Linhas 135-156 (`verificar_area_disponivel`)
    ```python
    cursor.execute(
        "SELECT 1 FROM reservas WHERE area = ? AND data = ? AND status = 'ativa'",
        (area, data)
    )
    # Retorna apenas se está disponível ou ocupada, sem expor apartamento ou códigos alheios
    ```
- **Por que não depende do modelo**: O parâmetro `apartamento` não faz parte da assinatura exposta ao modelo LLM no schema JSON da ferramenta. O valor é injetado diretamente pelo runtime do ADK via `tool_context.state["apartamento"]`. Consultas de cancelamento ou listagem filtram estritamente pelo apartamento da sessão. Consultas de disponibilidade checam a agenda sem jamais expor dados do apartamento ocupante ou códigos de reservas alheias.

---

### Garantia 3: Nada se perde no reinício
- **Arquivo**: `src/services/adk_runner.py`
  - **Trecho**: Linhas 20-33
    ```python
    self.session_service = DatabaseSessionService(db_url=DB_URL)
    self.app = App(
        name=APP_NAME,
        root_agent=self.root_agent,
        resumability_config=ResumabilityConfig(is_resumable=True)
    )
    ```
- **Arquivo**: `src/database.py`
  - **Trecho**: Linhas 64-73 (`gerar_codigo_reserva_unico`)
    ```python
    def gerar_codigo_reserva_unico(cursor: sqlite3.Cursor) -> str:
        while True:
            num = random.randint(1000, 9999)
            codigo = f"RSV-{num}"
            cursor.execute("SELECT 1 FROM codigos_reservas WHERE codigo = ?", (codigo,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO codigos_reservas (codigo) VALUES (?)", (codigo,))
                return codigo
    ```
- **Por que não depende do modelo**: Todas as sessões, mensagens e eventos do ADK são salvos em banco SQLite em disco (`condominio.db`) através do `DatabaseSessionService` com suporte a `greenlet`. As reservas, visitantes e códigos gerados residem em tabelas relacionais persistentes. Ao reiniciar a API, os eventos anteriores permanecem inalterados, novas mensagens continuam funcionando e a tabela `codigos_reservas` impede a repetição de códigos de reservas passadas ou canceladas.

---

### Garantia 4: O regulamento é consultado, não carregado
- **Arquivo**: `src/agents/coordinator.py`
  - **Trecho**: Linhas 7-18 (`INSTRUCOES_COORDENADOR`), comprovando a ausência do regulamento no agente principal.
- **Arquivo**: `src/tools/regulamento.py`
  - **Trecho**: Linhas 23-118 (`consultar_regulamento`)
    ```python
    # Particiona dados/regulamento.md por '## Capítulo ...'
    # Retorna apenas o capítulo correspondente ao assunto consultado
    ```
- **Por que não depende do modelo**: O documento `dados/regulamento.md` nunca é carregado no prompt do coordenador. Quando o morador tem dúvidas (ex: horário de domingo da piscina), o especialista aciona a ferramenta Python `consultar_regulamento`, que busca no arquivo e devolve **exclusivamente** o Capítulo IV (*Piscina*). Nenhum trecho de capítulos não relacionados é inserido no histórico ou nos eventos da sessão.

---

### Garantia 5: Dois moradores, uma reserva
- **Arquivo**: `src/database.py`
  - **Trecho**: Linhas 27-31 (`init_db`)
    ```sql
    CREATE UNIQUE INDEX IF NOT EXISTS uq_area_data_ativa 
    ON reservas (area, data) 
    WHERE status = 'ativa';
    ```
  - **Trecho**: Linhas 75-108 (`criar_reserva_db`)
    ```python
    try:
        cursor.execute(
            "INSERT INTO reservas (codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, 'ativa')",
            (codigo, apartamento, area, data)
        )
        return {"sucesso": True, "codigo": codigo, ...}
    except sqlite3.IntegrityError:
        return {"sucesso": False, "mensagem": f"A data {data} já está reservada por outro morador para a área {area}."}
    ```
- **Por que não depende do modelo**: A exclusividade de reserva é imposta pela restrição de integridade relacional única do motor do SQLite no momento exato do `INSERT`. Se dois moradores aprovarem a mesma área e data no mesmo instante, o SQLite serializa as transações: uma reserva é persistida e a outra dispara `sqlite3.IntegrityError`. A exceção é capturada em código Python e devolve uma resposta cordial com status HTTP 200 (sem erro 500 de servidor), garantindo exatamente uma reserva ativa no condomínio.

---

## Como rodar

### Pré-requisitos
- **Python 3.12** ou superior.
- **uv** instalado na máquina ([guia de instalação do uv](https://docs.astral.sh/uv/getting-started/installation/)).
- Chave de API do **Google AI Studio** (`GEMINI_API_KEY`).

### Variáveis de Ambiente
Copie o arquivo de exemplo para `.env`:
```bash
cp .env.example .env
```
Preencha a sua chave no arquivo `.env`:
```env
GEMINI_API_KEY=sua_chave_do_google_ai_studio_aqui
```

### Instalação de Dependências
Execute o `uv sync` para instalar as dependências com as versões exatas fixadas no `uv.lock`:
```bash
uv sync
```

### Comando para Restaurar os Dados Iniciais
Para inicializar ou restaurar as reservas e visitantes para o estado inicial dos arquivos em `dados/`:
```bash
uv run python -m src.scripts.restore_data
```

### Comando para Subir a API
Para iniciar o servidor FastAPI respondendo em `http://localhost:8000`:
```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### Execução dos Testes Automatizados
Para executar a suíte de testes de integração e validação das garantias:
```bash
uv run pytest -v
```
