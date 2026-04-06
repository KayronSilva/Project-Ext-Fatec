# 📊 GUIA VISUAL & RESUMO EXECUTIVO

## Sumário Executivo

### O Projeto em 30 Segundos

```
╔═══════════════════════════════════════════════════════════════╗
║        🎯 SISTEMA DE GERENCIAMENTO DE DEVOLUÇÕES             ║
║                                                               ║
║  Permite que clientes façam solicitações de devolução de     ║
║  produtos, com validação de prazos, quantidades e logging    ║
║  completo de auditoria.                                       ║
║                                                               ║
║  ✅ Autenticação por Email                                   ║
║  ✅ Suporta PF (CPF) e PJ (CNPJ)                             ║
║  ✅ Cálculo automático de prazos                             ║
║  ✅ Logging estruturado em JSON                              ║
║  ✅ Rate limiting contra abuso                               ║
║  ✅ Paginação otimizada                                       ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## 🔄 Fluxo Visual Completo

### Fluxo de Usuário (User Journey)

```
┌─────────────────────────────────────────────────────────────┐
│                    NOVO ACESSO                              │
└─────────────────────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
      [LOGIN]        [CADASTRO]      [HOME]
         │               │               │
         ├───────────────┴───────────────┤
         │                               │
         └─────────┬─────────────────────┘
                   │
      ▼ [Autenticado]
┌─────────────────────────────────────────────────────────────┐
│          DASHBOARD (Histórico de Devoluções)               │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Minhas Devoluções                          [Carregar] │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ Status │ Data      │ NF      │ Motivo    │ Ações    │  │
│  ├────────┼───────────┼─────────┼───────────┼──────────┤  │
│  │ ✓      │ 05/03/26  │ NF-001  │ Danificado│ [Ver]    │  │
│  │ ⏳     │ 04/03/26  │ NF-002  │ Defeito   │ [Ver]    │  │
│  │ ◉      │ 03/03/26  │ NF-003  │ Troca     │ [Ver]    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  [← Anterior] ◉ 1 ◉ 2 ◉ 3 [Próximo →]                     │
│                                                             │
│                   [+ NOVA DEVOLUÇÃO]                       │
└─────────────────────────────────────────────────────────────┘
                         │
                    [Clica em botão]
                         │
      ▼ [Novo formulário]
┌─────────────────────────────────────────────────────────────┐
│        FORMULÁRIO DE DEVOLUÇÃO (Tela Interativa)           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. BUSCAR CLIENTE                                    │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ CPF/CNPJ: [11111111111____________] [BUSCAR] 🔍     │  │
│  │                                                      │  │
│  │ ✓ João Silva (CPF: 111.111.111-11)                 │  │
│  │   Email: joao@email.com                            │  │
│  │   Tel: (11) 99999-9999                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2. SELECIONAR NOTA FISCAL                            │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ [BUSCAR NOTAS] 🔍                                   │  │
│  │                                                      │  │
│  │ ◉ NF-001-2025   | Emitida: 01/12/25 | ✓ DISPONÍVEL │  │
│  │                 | Vence em: 15 dias                 │  │
│  │                                                      │  │
│  │ ○ NF-002-2025   | Emitida: 15/10/25 | ✗ EXPIRADA   │  │
│  │                 | Vencimento: -20 dias               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 3. ITENS DA NOTA                                     │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ [BUSCAR ITENS] 🔍                                   │  │
│  │                                                      │  │
│  │ Produto          │ Orig. │ Devolvido │ Disponível   │  │
│  │ Camiseta XL      │ 100   │ 20        │ 80           │  │
│  │ [Qtd a devolver: |_5____|                           │  │
│  │                                                      │  │
│  │ Calça Jeans      │ 50    │ 10        │ 40           │  │
│  │ [Qtd a devolver: |_3____|                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 4. MOTIVO & ANEXOS                                  │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │ Motivo: [Produto danificado    ▼]                   │  │
│  │                                                      │  │
│  │ Fotos:       [Selecionar arquivo] [📸📸]           │  │
│  │ Documento:   [Selecionar arquivo] [PDF]             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│              [CANCELAR]    [ENVIAR DEVOLUÇÃO]             │
└─────────────────────────────────────────────────────────────┘
                         │
                    [POST /devolucao/]
                         │
      ▼ [Validações + Criação]
┌─────────────────────────────────────────────────────────────┐
│                    PROCESSAMENTO                            │
│                                                             │
│  ✓ Prazo dentro de limite (15 dias restantes)             │
│  ✓ Quantidades disponíveis (80 disp., 5 solicitado)       │
│  ✓ Motivo válido ("Produto danificado")                   │
│  ✓ Arquivos processados (5.2 MB de fotos + PDF)           │
│  ✓ Devolução criada (ID: 42)                              │
│  ✓ Log registrado em JSON                                  │
│                                                             │
│  STATUS: ✓ TUDO OK! Redirecionando...                     │
└─────────────────────────────────────────────────────────────┘
                         │
                   ▼ [Sucesso]
┌─────────────────────────────────────────────────────────────┐
│       CONFIRMAÇÃO & RETORNO AO DASHBOARD                   │
│                                                             │
│  ✅ Devolução criada com sucesso!                          │
│                                                             │
│  Número Devolução: DIE-000042                              │
│  Data: 05/03/2026 às 10:30                                │
│  Status: PENDENTE (⏳ Aguardando processamento)            │
│                                                             │
│  [Voltar ao Dashboard]                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏛️ Arquitetura em Camadas

### Vista de Cima para Baixo

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                   🌐 NAVEGADOR DO USUÁRIO                  │
│              (HTML + JavaScript + CSS)                      │
│                                                              │
│  Templates:                                                 │
│  • login.html            → Tela de login                   │
│  • cadastro.html        → Formulário de cadastro           │
│  • devolucao.html       → Formulário de devolução (AJAX)   │
│  • acompanhar_devolucoes.html → Dashboard com histórico    │
│                                                              │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTP Requests
                     │ (GET, POST, AJAX)
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│              🔧 DJANGO (Views + Forms)                      │
│           Controladores e Manipuladores de Entrada          │
│                                                              │
│  Routes (urls.py):                                         │
│  └─ /login                    → login_view()               │
│  └─ /cadastro                → cadastro_view()             │
│  └─ /                         → acompanhar_devolucoes()    │
│  └─ /devolucao               → tela_devolucao()            │
│  └─ /ajax/buscar-cliente      → buscar_cliente() [AJAX]   │
│  └─ /ajax/buscar-notas        → buscar_notas() [AJAX]      │
│  └─ /ajax/buscar-itens        → buscar_itens() [AJAX]      │
│                                                              │
│  Forms (forms.py):                                          │
│  ├─ LoginForm           → Validação de email+senha        │
│  ├─ CadastroForm        → Validação de novo usuário        │
│  ├─ DevolucaoForm       → Validação de devolução           │
│  └─ ClienteForm         → Validação de dados cliente       │
│                                                              │
└────────────────────┬─────────────────────────────────────────┘
                     │ Chamadas de método
                     │ Queries SQL
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│          📦 SERVICE LAYER (Lógica de Negócio)              │
│                                                              │
│  DevolutionService                                          │
│  ├─ criar()              → Cria devolução com validações   │
│  └─ _validar_...()       → Validações de negócio           │
│                                                              │
│  ClienteService                                             │
│  └─ buscar_por_documento() → CPF/CNPJ                      │
│                                                              │
│  PrazoService                                               │
│  ├─ calcular_prazo()     → Calcula limite de devolução     │
│  ├─ esta_expirado()      → Verifica se venceu             │
│  └─ status_prazo()       → Status (dias_restantes)         │
│                                                              │
│  NotaService                                                │
│  └─ obter_notas()        → Retorna notas do cliente        │
│                                                              │
│  PaginationService         (devolucao/pagination_service.py)│
│  └─ paginar()            → Página com limit/offset         │
│                                                              │
│  Logging & Auditoria      (devolucao/logging_utils.py)     │
│  └─ log_event()          → Registra em JSON                │
│                                                              │
└────────────────────┬─────────────────────────────────────────┘
                     │ ORM (Object-Relational Mapping)
                     │ Queries otimizadas
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│            🗄️ MODELOS (ORM Django)                          │
│          Representação de Tabelas do BD                     │
│                                                              │
│  Usuario              → Autenticação (email login)          │
│  Cliente              → PF (CPF) ou PJ (CNPJ)              │
│  NotaFiscal          → Documentos fiscais (NF)             │
│  Produto              → Itens vendáveis                     │
│  ItemNotaFiscal      → Linha de NF (Produto+Qtd)           │
│  Devolucao           → Solicitação de devolução            │
│  ItemDevolucao       → Itens sendo devolvidos              │
│  ConfiguracaoSistema → Parametrizações globais             │
│                                                              │
└────────────────────┬─────────────────────────────────────────┘
                     │ SQL Queries
                     │ Transações (@atomic)
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│           💾 BANCO DE DADOS (MySQL)                         │
│                                                              │
│  Tabelas:                                                   │
│  ├─ tb_usuario          → Usuários do sistema              │
│  ├─ tb_cliente          → Clientes (PF/PJ)                 │
│  ├─ tb_notafiscal       → Notas fiscais                    │
│  ├─ tb_produto          → Produtos/Itens                   │
│  ├─ tb_itens_nota       → Items de NF                      │
│  ├─ tb_devolucao        → Devoluções solicitadas           │
│  ├─ tb_item_devolucao   → Itens de devolução              │
│  └─ tb_configuracao     → Configurações do sistema         │
│                                                              │
│  Índices (Otimização):                                      │
│  ├─ idx_cliente_documento        → CPF/CNPJ (10-100x)     │
│  ├─ idx_notafiscal_numero        → NF rápida               │
│  ├─ idx_devolucao_status_data    → Filtros rápidos        │
│  ├─ idx_itemdev_produto          → Validação de qtd        │
│  └─ idx_itemnotafiscal_produto   → Queries de items        │
│                                                              │
│  Storage:                                                   │
│  ├─ uploads/fotos_devolucao/     → Imagens (max 2MB)      │
│  ├─ uploads/pdfs/                 → PDFs (max 5MB)         │
│  └─ logs/                         → Logs JSON              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔐 Fluxo de Segurança

### Autenticação & Autorização

```
┌─────────────────────────────────────────────────────────────┐
│                NOVO USUÁRIO CHEGA                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────────┐
         │   Email já existe?        │
         └────┬────────────────┬─────┘
         NÃO  │              SIM│
             │                 │
      ▼ [Novo]              ▼ [Existente]
   [CADASTRO]           [LOGIN]
      │                     │
      ├─► Email validado    ├─► Email validado
      ├─► Senha hash SHA256 └─► Busca usuario
      │   (salvo no BD)          │
      └─► Usuario criado    ├─► Senha comparada
                            │   (SHA256)
                            │
                    ┌───────┴──────┐
                    │              │
              [OK]  │          [ERRO]
                    │              │
                 ▼                 ▼
          [Session criada]  [Erro 401]
          [Redirecionado]   [Acessos negados]


┌─────────────────────────────────────────────────────────────┐
│              USUARIO AUTENTICADO                            │
└────────────────────┬────────────────────────────────────────┘
                     │
         Cada view com @login_required:
                     │
      ▼ [Session válida?]
         │
    SIM │     NÃO
         │     │
      ▼     ▼
   [Continue]  [401 Unauthorized - Redirecionado]
      │
      ├─► Acesso a dados do usuário
      ├─► CRUD de devoluções
      ├─► Upload de arquivos
      └─► Logging de auditoría


┌─────────────────────────────────────────────────────────────┐
│           PROTEÇÕES AGAINST ATTACKS                         │
└─────────────────────────────────────────────────────────────┘

1. CSRF (Cross-Site Request Forgery)
   ├─► Todos os forms têm {% csrf_token %}
   └─► Django valida automaticamente

2. SQL Injection
   ├─► ORM (QuerySet) protegido
   └─► Parametrized queries

3. Rate Limiting (DoS Protection)
   ├─► @ratelimit(max=3, window=60)
   └─► Bloqueia se >3 req/min

4. Secrets Management
   ├─► Credenciais em .env
   ├─► .env no .gitignore
   └─► DEBUG=False em produção

5. File Upload
   ├─► Validação de extensão
   ├─► Limite de tamanho (2MB fotos, 5MB PDF)
   └─► Renomeação automática
```

---

## 📈 Fluxo de Dados

### Criação de Devolução (Passo a Passo)

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONT-END (HTML)                        │
│                                                             │
│  <form method="POST" action="/devolucao/">                 │
│    CSRF Token ✓                                             │
│    Cliente_ID: 1                                            │
│    Nota_Fiscal_ID: 1                                        │
│    Motivo: "Danificado"                                     │
│    Itens: [                                                 │
│      {produto_id: 1, qtd: 5},                              │
│      {produto_id: 2, qtd: 3}                               │
│    ]                                                        │
│    Fotos: [File_1, File_2]                                 │
│    Documento: [PDF_File]                                    │
│  </form>                                                    │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTP POST
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            DJANGO VIEW (criar_devolucao)                    │
│                                                             │
│  1. Extrai dados do request                                │
│  2. Valida CSRF token (@csrf_protect automático)          │
│  3. Verifica autenticação (@login_required)               │
│  4. Rate limiting (@ratelimit)                            │
│                                                             │
│  5. DevolucaoForm.is_valid()                              │
│     ├─► Campo obrigatório?                                │
│     ├─► CPF/CNPJ válido?                                  │
│     └─► Dados na forma correta?                            │
│                                                             │
│  6. Chama SERVICE LAYER                                    │
│     └─► devolution_service.criar()                        │
│         (Transação + Validações)                           │
│                                                             │
└────────────────────┬─────────────────────────────────────────┘
                     │
           ▼ [transaction.atomic()]
┌─────────────────────────────────────────────────────────────┐
│           SERVICE LAYER (Lógica)                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ VALIDAÇÃO #1: Prazo Expirado?                      │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ nota = notafiscal (data: 01/12/25)                 │   │
│  │ prazo = ConfiguracaoSistema.prazo() → 30 dias      │   │
│  │ limite = 01/12/25 + 30 = 31/12/25                 │   │
│  │ hoje = 05/03/26                                    │   │
│  │ 05/03/26 > 31/12/25? SIM → PrazoExpiradoError()   │   │
│  │                                                     │   │
│  │ Se EXPIRADO:                                        │   │
│  │   └─► raise PrazoExpiradoError()                   │   │
│  │        (Rollback automático)                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ VALIDAÇÃO #2: Quantidade Disponível?               │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Para cada item na solicitação:                      │   │
│  │                                                     │   │
│  │ Item 1: {produto_id: 1, qtd: 5}                    │   │
│  │   original = ItemNotaFiscal.qtd → 100              │   │
│  │   devolvido = ItemDevolucao.sum('qtd') → 20        │   │
│  │   disponivel = 100 - 20 = 80                       │   │
│  │   solicitado = 5                                    │   │
│  │   5 > 80? NÃO → OK ✓                               │   │
│  │                                                     │   │
│  │ Item 2: {produto_id: 2, qtd: 3}                    │   │
│  │   original = 50                                     │   │
│  │   devolvido = 10                                    │   │
│  │   disponivel = 40                                   │   │
│  │   solicitado = 3                                    │   │
│  │   3 > 40? NÃO → OK ✓                               │   │
│  │                                                     │   │
│  │ Se INSUFICIENTE:                                    │   │
│  │   └─► raise QuantidadeIndisponível()               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ VALIDAÇÃO #3: Motivo Válido?                       │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ motivo_solicitado = "Danificado"                    │   │
│  │ motivos_validos = ["Danificado", "Defeito",        │   │
│  │                    "Troca", "Insatisfação"]         │   │
│  │ "Danificado" in validos? SIM → OK ✓                │   │
│  │                                                     │   │
│  │ Se INVÁLIDO:                                        │   │
│  │   └─► raise MotivoInválido()                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ✓ TODAS VALIDAÇÕES PASSARON!                              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ PROCESSAR ARQUIVOS                                 │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │                                                     │   │
│  │ Fotos: [File_1.jpg (1.5MB), File_2.png (2MB)]     │   │
│  │   ├─► Validar extensão (.jpg, .png OK)            │   │
│  │   ├─► Validar tamanho (< 2MB OK)                   │   │
│  │   ├─► Renomear: devolucao_42_foto1.jpg             │   │
│  │   └─► Salvar em uploads/fotos_devolucao/           │   │
│  │                                                     │   │
│  │ Documento: [File.pdf (3.5MB)]                       │   │
│  │   ├─► Validar extensão (.pdf OK)                   │   │
│  │   ├─► Validar tamanho (< 5MB OK)                   │   │
│  │   ├─► (OPCIONAL) Ler texto com pdfplumber         │   │
│  │   └─► Salvar em uploads/pdfs/                      │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ INSERIR NO BANCO (TRANSAÇÃO)                        │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │                                                     │   │
│  │ BEGIN TRANSACTION                                   │   │
│  │                                                     │   │
│  │   INSERT INTO tb_devolucao (                        │   │
│  │     id_cliente,      → 1                           │   │
│  │     id_notafiscal,   → 1                           │   │
│  │     id_usuario,      → 5 (request.user)            │   │
│  │     motivo,          → "Danificado"                │   │
│  │     status,          → "pendente"                  │   │
│  │     dt_criacao       → NOW()                       │   │
│  │   )                                                 │   │
│  │   RETURNING id → devolucao_id = 42                 │   │
│  │                                                     │   │
│  │   INSERT INTO tb_item_devolucao (                   │   │
│  │     id_devolucao,       → 42                       │   │
│  │     id_produto,         → 1                        │   │
│  │     qtd_devolvida,      → 5                        │   │
│  │     dt_item             → NOW()                    │   │
│  │   )                                                 │   │
│  │                                                     │   │
│  │   INSERT INTO tb_item_devolucao (                   │   │
│  │     id_devolucao,       → 42                       │   │
│  │     id_produto,         → 2                        │   │
│  │     qtd_devolvida,      → 3                        │   │
│  │     dt_item             → NOW()                    │   │
│  │   )                                                 │   │
│  │                                                     │   │
│  │ COMMIT (se tudo OK)                                │   │
│  │ ou                                                 │   │
│  │ ROLLBACK (se erro)                                 │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  return devolucao (ID: 42)                                 │
│                                                             │
└────────────────────┬─────────────────────────────────────────┘
                     │
           ▼ [Volta a view]
┌─────────────────────────────────────────────────────────────┐
│             LOGGING & RESPOSTA                              │
│                                                             │
│  logging_utils.log_event('devolucao.criada', {            │
│    'usuario_id': 5,                                        │
│    'devolucao_id': 42,                                     │
│    'cliente_id': 1,                                        │
│    'nota_fiscal_id': 1,                                    │
│    'itens_count': 2,                                       │
│    'motivo': 'Danificado',                                 │
│    'quantidade_total': 8,                                  │
│    'timestamp': '2026-03-05T10:30:45.123456Z'             │
│  })                                                        │
│                                                             │
│  └─► Escriba em JSON em logs/app.log                       │
│                                                             │
│  return JsonResponse({                                      │
│    'success': True,                                        │
│    'devolucao_id': 42,                                     │
│    'message': 'Devolução criada com sucesso!'             │
│  })                                                        │
│                                                             │
└────────────────────┬─────────────────────────────────────────┘
                     │ HTTP 200 + JSON
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              RESPOSTA AO NAVEGADOR                          │
│                                                             │
│  JavaScript recebe JSON:                                    │
│  {                                                          │
│    "success": true,                                         │
│    "devolucao_id": 42,                                      │
│    "message": "Devolução criada com sucesso!"             │
│  }                                                          │
│                                                             │
│  JavaScript trata:                                          │
│    1. Mostra toast green (✓ Sucesso)                      │
│    2. Redireciona para /acompanhar-devolucoes            │
│    3. Atualiza histórico                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Modelo de Dados

### Diagrama E/R (Entidade Relacionamento)

```
┌──────────────────┐
│    USUARIO       │
├──────────────────┤
│ PK id            │
│    email*        │──────┐
│    password      │      │
│    is_active     │      │
│    date_joined   │      │ 1:1
│    is_staff      │      │
└──────────────────┘      │
                          │
                          │
                    ┌─────▼──────────┐
                    │    CLIENTE     │
                    ├────────────────┤
                    │ PK id          │
                    │ FK usuario_id  │◄──────┐
                    │    tipo (PF/PJ)│       │
                    │    cpf*        │       │
                    │    cnpj*       │       │
                    │    nome        │       │
                    │    razao_social│       │
                    │    email       │       │
                    │    telefone    │       │
                    │    endereco    │       │
                    │    cep         │       │
                    │    cidade      │       │
                    │    bairro      │       │
                    │    estado      │       │
                    └────┬───────────┘       │
                         │                  │
              ┌──────────┴──┬───────────┐   │
              │             │           │   │
              │ 1:N         │ 1:N      │   │
              │             │           │   │
    ┌─────────▼────┐  ┌────▼────────┐ │   │
    │ NOTAFISCAL   │  │  DEVOLUCAO  │ │   │
    ├──────────────┤  ├─────────────┤ │   │
    │PK id         │  │PK id        │ │   │
    │FK cliente_id*│  │FK cliente_id│─┘   │
    │   numero*    │  │FK notafiscal│     │
    │   data_emissao │ │FK usuario_id│────┘
    │   arquivo_pdf│  │   motivo    │
    │              │  │   status    │
    │          1:N │  │   data_criac│
    │              │  │   foto      │
    └──────┬───────┘  │   arquivo_pdf
           │          └────┬────────┘
           │               │
           │          ┌────▼──────────────┐
      ┌────▼──────┐   │ ITEM_DEVOLUCAO   │
      │PRODUTO    │   ├──────────────────┤
      ├───────────┤   │PK id             │
      │PK id      │   │FK devolucao_id   │
      │   codigo  │   │FK produto_id     │
      │   descricao   │   qtd_devolvida  │
      │           │   │   data_item      │
      │     ^     │   └────┬─────────────┘
      │     │     │        │
      │ 1:N │         1:N  │
      │     │        │
      │     │    ┌───▼─────────┐
      └─────┼────┤ITEMNOTA     │
            │    │────────────┤
            │    │PK id       │
            │    │FK notafiscal
            │    │FK produto_id
            │    │   quantidade
            └────┤        
                 └─────────┘

┌─────────────────────────────────────┐
│   CONFIGURACAO_SISTEMA              │
├─────────────────────────────────────┤
│ PK id                               │
│    prazo_devolucao_dias (default:30)│
└─────────────────────────────────────┘

Legendas:
  PK = Primary Key (Chave Primária)
  FK = Foreign Key (Chave Estrangeira)
  *  = Unique (Valor único)
  ^  = Relacionamento
```

---

## 📊 Diagrama de Estados

### Estados de uma Devolução

```
┌─────────────────────────────────────────────────────────┐
│                CICLO DE DEVOLUÇÃO                       │
└─────────────────────────────────────────────────────────┘

    ┌──────────┐
    │ CRIAÇÃO  │
    └────┬─────┘
         │
         │ Usuario envia form
         │ DevolutionService.criar()
         ▼
    ┌──────────────────┐
    │    PENDENTE      │
    │  ⏳ Aguardando  │  ◄────┐
    │  processamento   │       │ (Pode retornar)
    └────┬─────────────┘       │
         │                     │
         │ Admin aprova        │
         │ ou nega             │
         ▼                     │
    ┌──────────────────┐       │
    │  EM PROCESSO     │       │
    │  🔄 Verificando │       │
    │  a devolução     │       │
    └────┬─────────────┘       │
         │                     │
    ┌────┴──────────────────┐  │
    │                       │  │
    │ Aprova   │   Rejeita  │  │
    │ Devolução│            │  │
    │          │ Envia email│──┘
    │          │ de rejeição│
    │          │            │
    ▼          ▼            │
    │  CONCLUÍDO      REJEITADO
    │  ✓ Devolvido   ✗ Não aceito
    │    com sucesso

Status no BD:
  • 'pendente'     → Aguardando aprovação
  • 'em_processo'  → Sob análise
  • 'concluido'    → Finalizado com sucesso
  • 'rejeitado'    → Não foi aceito (OPCIONAL)

Transições:
  pendente → em_processo (Revisão iniciada)
  em_processo → concluido (Aprovado e processado)
  em_processo → pendente (Retorna para revisão)
  pendente → rejeitado (Não qualifica)
```

---

## ⚙️ Stack Técnico

### Componentes & Versões

```
Frontend:
  ├─ HTML5
  ├─ CSS3 (Style.css customizado + Admin CSS)
  ├─ JavaScript Vanilla (sem framework)
  └─ jQuery (OPCIONAL, se necessário AJAX)

Backend:
  ├─ Django 4.2.0
  │  ├─ Auth (Usuario customizado)
  │  ├─ ORM (Queries otimizadas)
  │  ├─ Admin (Painel)
  │  └─ Forms (Validação)
  │
  └─ Python 3.9+
     ├─ PyMySQL 1.1.0       (Driver de conexão)
     ├─ structlog 24.1.0     (Logging estruturado)
     ├─ pdfplumber 0.11.9    (Leitura de PDF)
     ├─ Pillow 11.0.0        (Imagem/Foto)
     ├─ python-dotenv 1.2.2  (Variáveis de env)
     └─ django-ratelimit 4.1.0 (Rate limiting)

Database:
  ├─ MySQL 5.7+
  ├─ InnoDB (transações ACID)
  ├─ Índices otimizados (5x queries)
  └─ Encoding: utf8mb4

Infrastructure:
  ├─ Servidor: Django dev (DEV) / Gunicorn (PROD)
  ├─ WSGI: ProjetoDevolucao/wsgi.py
  ├─ static: WhiteNoise
  ├─ Media: uploads/
  └─ Logs: logs/app.log (JSON rotativo)
```

---

## 🎯 Tempos de Desenvolvimento

### Cronograma de Implementação

```
┌──────────────────────────────────────────────────────────┐
│  FASE 1: Segurança & Infrastructure                     │
├──────────────────────────────────────────────────────────┤
│  ✓ Secrets Management (.env)           2-3 horas        │
│  ✓ Índices de BD                       1 hora           │
│  ✓ DEBUG=False & Página erro           30 minutos       │
│  ✓ Logging Estruturado                 3-4 horas        │
│  ─────────────────────────────────────────────────────   │
│  TOTAL FASE 1:                         ~9 horas        │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  FASE 2: Arquitetura & Performance                       │
├──────────────────────────────────────────────────────────┤
│  ✓ Service Layer                       2 horas          │
│  ✓ Rate Limiting                       1 hora           │
│  ✓ Paginação Otimizada                 1.5 horas        │
│  ─────────────────────────────────────────────────────   │
│  TOTAL FASE 2:                         ~4.5 horas       │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  FASE 3: Integrações (Opcional)                          │
├──────────────────────────────────────────────────────────┤
│  ◻ Sankhya ERP Adapter                 5-6 horas        │
│  ◻ Email Notifications                 2-3 horas        │
│  ◻ Webhooks & REST API                 4-5 horas        │
│  ─────────────────────────────────────────────────────   │
│  TOTAL FASE 3:                         ~11-14 horas     │
└──────────────────────────────────────────────────────────┘

TOTAL PROJETO: ~24-27 horas ✓
```

---

## 📚 Documentação de Referência

### Arquivos Importantes

| Arquivo | Propósito |
|---------|-----------|
| **GUIA_COMPLETO.md** (este) | Documentação completa + instalação |
| SERVICE_LAYER_GUIDE.md | Como usar DevolutionService, etc |
| LOGGING_SETUP.md | Auditoria & logging estruturado |
| RATE_LIMITING_INTEGRATION.md | Proteção contra DoS |
| PAGINATION_INTEGRATION.md | Paginação & performance |
| README_OTIMIZACOES.md | Resumo de melhorias |
| RESUMO_FINAL.md | Executive summary |
| .env.example | Template de variáveis |
| requirements.txt | Dependências Python |

---

## 🚀 Pronto para Começar?

### Checklist Rápido

- [ ] Python 3.9+ instalado
- [ ] MySQL rodando
- [ ] Git clonado/pasta aberta
- [ ] Venv criado e ativado
- [ ] requirements.txt instalado
- [ ] .env configurado
- [ ] Banco de dados criado
- [ ] Migrações aplicadas
- [ ] Servidor Django rodando

```bash
# Teste rápido
python manage.py check
# Esperado: System check identified no issues

# Se aparecer "System check identified no issues (0 silenced)"
# ✅ Você está pronto!
```

---

**Documento criado:** 05 de março de 2026  
**Versão:** 1.0  
**Status:** 🟢 Produção-Ready
