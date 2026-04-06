# 📘 GUIA COMPLETO - PROJETO DEVOLUÇÃO

## 📑 Índice
1. [Visão Geral](#visão-geral)
2. [Arquitetura do Projeto](#arquitetura-do-projeto)
3. [Fluxo de Funcionamento](#fluxo-de-funcionamento)
4. [Estrutura de Diretórios](#estrutura-de-diretórios)
5. [Componentes Principais](#componentes-principais)
6. [Instalação Passo a Passo](#instalação-passo-a-passo)
7. [Executar o Projeto](#executar-o-projeto)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

### O que é?

**Projeto Devolução** é uma aplicação Django de gerenciamento de devoluções de produtos. Permite que clientes (pessoas físicas ou jurídicas) façam solicitações de devolução de itens em notas fiscais, com prazos controláveis e auditoria completa.

### Características Principais

✅ **Autenticação via Email** — Sistema de login/cadastro customizado
✅ **Suporte Duplo** — Pessoas Físicas (CPF) e Jurídicas (CNPJ)
✅ **Validação Rigorosa** — Algoritmos certificados de CPF e CNPJ
✅ **Notas Fiscais** — Integração com NDFe, cálculo de prazos
✅ **Logging Estruturado** — Auditoria em JSON, rastreamento completo
✅ **Rate Limiting** — Proteção contra abuso de AJAX
✅ **Paginação** — Queries otimizadas para grandes volumes
✅ **Admin Django** — Gerenciar dados via painel administrativo

### Tecnologias

| Componente | Tecnologia | Versão |
|-----------|-----------|--------|
| Framework | Django | 4.2.0 |
| Banco de Dados | MySQL | 5.7+ |
| Autenticação | SHA256 (Django native) | - |
| Logging | structlog | 24.1.0 |
| PDFs | pdfplumber | 0.11.9 |
| Imagens | Pillow | 11.0.0 |
| Interface | HTML5 + CSS3 + JavaScript | Vanilla |

---

## 🏗️ Arquitetura do Projeto

### Padrão MVC + Service Layer

```
┌─────────────────────────────────────────────────────────┐
│                    CAMADA DE VISUALIZAÇÃO               │
│                  (Templates + JavaScript)                │
│  (acompanhar_devolucoes.html, devolucao.html, etc)      │
└────────────────────────┬────────────────────────────────┘
                         │ (Requisições/Respostas HTTP)
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 CAMADA DE CONTROLE (Views)              │
│     (devolucao/views.py - views.py dentro de devolucao) │
│  - login_view(), cadastro_view()                        │
│  - acompanhar_devolucoes(), tela_devolucao()            │
│  - buscar_cliente(), buscar_notas_cliente()             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              CAMADA DE NEGÓCIO (Services)               │
│             (devolucao/services.py - OPCIONAL)          │
│  - DevolutionService (criar devolução com validação)    │
│  - ClienteService (buscar por documento)                │
│  - PrazoService (calcular expiração)                    │
│  - NotaService (validar notas e itens)                  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│         CAMADA DE PERSISTÊNCIA (Modelos)                │
│              (devolucao/models.py)                      │
│  - Usuario, Cliente, NotaFiscal                         │
│  - Produto, ItemNotaFiscal                              │
│  - Devolucao, ItemDevolucao                             │
│  - ConfiguracaoSistema                                  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│           BANCO DE DADOS (MySQL)                        │
│         (db.sqlite3 ou MySQL remoto)                    │
│  - Tabelas: tb_usuario, tb_cliente, tb_notafiscal, etc  │
└─────────────────────────────────────────────────────────┘
```

### Fluxo de Dados

```
USUÁRIO
  │
  ├─► Acessa http://localhost:8000/login
  │         │
  │         ▼
  │    login_view() (views.py)
  │         │
  │         ├─► Valida credenciais com LoginForm
  │         ├─► auth.login(request, usuario)
  │         └─► Redireciona para acompanhar_devolucoes
  │
  ├─► Clica em "Nova Devolução"
  │         │
  │         ▼
  │    tela_devolucao() (views.py)
  │         │
  │         └─► Renderiza form interativo
  │
  ├─► Preenche CPF/CNPJ e clica buscar (AJAX)
  │         │
  │         ▼
  │    buscar_cliente() (AJAX endpoint)
  │         │
  │         ├─► ClienteService.buscar_por_documento()
  │         ├─► Valida CPF/CNPJ
  │         ├─► Retorna dados em JSON
  │         └─► JavaScript renderiza na página
  │
  ├─► Seleciona Nota Fiscal (AJAX)
  │         │
  │         ▼
  │    buscar_notas_cliente() (AJAX endpoint)
  │         │
  │         ├─► NotaService.obter_notas()
  │         ├─► Calcula prazo com PrazoService
  │         └─► Retorna lista de notas
  │
  ├─► Seleciona Nota e clica buscar itens (AJAX)
  │         │
  │         ▼
  │    buscar_itens_nota() (AJAX endpoint)
  │         │
  │         ├─► Calcula quantidade disponível
  │         ├─► Retorna itens com saldos
  │         └─► JavaScript atualiza tabela
  │
  └─► Preenche motivo e clica enviar (POST)
            │
            ▼
       criar_devolucao() (POST endpoint)
            │
            ├─► @transaction.atomic (transação segura)
            ├─► DevolutionService.criar()
            │    ├─► Valida prazos
            │    ├─► Valida quantidades
            │    ├─► Cria Devolucao (status='pendente')
            │    └─► Cria ItemDevolucao
            │
            ├─► Registra log estruturado
            │    └─► logging_utils.log_event()
            │         └─► JSON em logs/app.log
            │
            ├─► Rate limiting (3 req/min)
            │    └─► rate_limiting.ratelimit
            │         └─► Bloqueia se exceder
            │
            └─► Retorna JSON com sucesso
```

---

## 🔄 Fluxo de Funcionamento

### 1️⃣ FASE: Autenticação

```
┌─────────────────────────────────────────────────────────┐
│                   NOVO USUÁRIO?                         │
└────────────────────┬────────────────────────────────────┘
         NÃO         │          SIM
  ┌──────────────────┼──────────────────┐
  │                  │                  │
  ▼                  ▼                  ▼
[HOME]          [LOGIN]            [CADASTRO]
  │               │                    │
  │        Email + Senha          Email + Nova Senha
  │               │                    │
  │        Busca Usuario           Cria Usuario
  │               │        ┌──────────┘
  │        Hash + Valida  │
  │               │       │
  │               └───┬───┘
  │                   │
  └───────┬───────────┘
          │
          ▼
      [AUTH OK]
          │
          ├─► session_key criada
          ├─► Usuário vinculado com Cliente (opcional)
          └─► Redireciona para dashboard
```

**Arquivos Envolvidos:**
- `devolucao/models.py` → `Usuario`, `Cliente`
- `devolucao/forms.py` → `LoginForm`, `CadastroForm`
- `devolucao/views.py` → `login_view()`, `cadastro_view()`

---

### 2️⃣ FASE: Buscar Dados do Cliente

```
┌────────────────────────────────────────────────────────┐
│    Usuário preenche CPF/CNPJ ("11111111111")          │
└──────────────────┬─────────────────────────────────────┘
                   │
         ▼ JavaScript envia AJAX
         https://localhost:8000/ajax/buscar-cliente/
                   │
                   ▼
         buscar_cliente() (VIEW)
                   │
          ├─► Valida se é AJAX
          ├─► Extrai CPF/CNPJ do request
          ├─► Apenas dígitos: 11111111111
          │
          ├─► ClienteService.buscar_por_documento()
          │    │
          │    ├─► Query: Cliente.objects.filter(cpf="11111111111")
          │    ├─► Se encontrou:
          │    │    └─► Retorna {nome, cpf, email, telefone}
          │    │
          │    └─► Se não encontrou:
          │         └─► Retorna {error: "Cliente não encontrado"}
          │
          └─► JsonResponse(dados)
                   │
                   ▼
          ◄ JSON: {"nome": "João Silva", "cpf": "111..."}
          
          JavaScript renderiza na página
```

### 3️⃣ FASE: Buscar Notas Fiscais

```
┌────────────────────────────────────────────────────────┐
│    Usuário seleciona Cliente e clica "Buscar Notas"   │
└──────────────────┬─────────────────────────────────────┘
                   │
         ▼ AJAX POST
         /ajax/buscar-notas-cliente/
                   │
                   ▼
         buscar_notas_cliente() (VIEW)
                   │
          ├─► Extrai cliente_id do request
          │
          ├─► NotaService.obter_notas(cliente_id)
          │    │
          │    ├─► Query: NotaFiscal.objects
          │    │          .filter(cliente_id=1)
          │    │          .order_by('-data_emissao')
          │    │
          │    ├─► Para cada nota:
          │    │    │
          │    │    ├─► data_emissao = "2025-12-01"
          │    │    │
          │    │    ├─► PrazoService.calcular_prazo(data_emissao)
          │    │    │    │
          │    │    │    ├─► Config.prazo = 30 dias
          │    │    │    ├─► Calcula: 2025-12-01 + 30 = 2025-12-31
          │    │    │    │
          │    │    │    └─► Status:
          │    │    │         • Passou prazo? → "EXPIRADA"
          │    │    │         • Dentro do prazo? → "DISPONÍVEL"
          │    │    │
          │    │    └─► Retorna {numero_nota, data, dias_restantes}
          │    │
          │    └─► Retorna lista paginada
          │
          └─► JsonResponse(notas_list)
                   │
                   ▼
          ◄ JSON: [
               {
                 "id": 1,
                 "numero_nota": "NF-001-2025",
                 "data_emissao": "2025-12-01",
                 "dias_restantes": 15,
                 "status": "DISPONÍVEL"
               },
               ...
            ]
          
          JavaScript renderiza tabela de notas
```

### 4️⃣ FASE: Buscar Itens da Nota

```
┌────────────────────────────────────────────────────────┐
│    Usuário clica em uma nota ("NF-001" e busca itens) │
└──────────────────┬─────────────────────────────────────┘
                   │
         ▼ AJAX POST
         /ajax/buscar-itens-nota/
         Body: {nota_id: 1}
                   │
                   ▼
         buscar_itens_nota() (VIEW)
                   │
          ├─► Extrai nota_id do request
          │
          ├─► Query: ItemNotaFiscal.objects
          │          .filter(nota_fiscal_id=1)
          │
          ├─► Para cada item:
          │    │
          │    ├─► produto.descricao = "Camiseta"
          │    ├─► quantidade_original = 100
          │    │
          │    ├─► quantidade_ja_devolvida = 
          │    │    ItemDevolucao.objects
          │    │    .filter(
          │    │       produto_id=1,
          │    │       devolucao__nota_fiscal_id=1
          │    │    )
          │    │    .aggregate(Sum('quantidade_devolvida'))
          │    │    = 20
          │    │
          │    ├─► disponivel = 100 - 20 = 80
          │    │
          │    └─► Retorna {produto_id, descricao, qtd_original, qtd_disponível}
          │
          └─► JsonResponse(itens_list)
                   │
                   ▼
          ◄ JSON: [
               {
                 "produto_id": 1,
                 "descricao": "Camiseta",
                 "quantidade_original": 100,
                 "quantidade_disponivel": 80
               },
               ...
            ]
          
          JavaScript renderiza tabela com inputs de quantidade
```

### 5️⃣ FASE: Criar Devolução

```
┌────────────────────────────────────────────────────────┐
│   Usuário preenche quantidades e envia formulário      │
└──────────────────┬─────────────────────────────────────┘
                   │
         ▼ POST /devolucao/
         Form: {
           cliente_id: 1,
           nota_fiscal_id: 1,
           motivo: "Produto danificado",
           itens: [
             {produto_id: 1, quantidade: 5},
             {produto_id: 2, quantidade: 3}
           ],
           fotos: [File, File],
           pdf: File
         }
                   │
                   ▼
         criar_devolucao() (POST VIEW)
                   │
          ├─► @transaction.atomic (transação)
          │    ├─► Garante: SER TUDO OU NADA
          │    └─► Se erro: rollback automático
          │
          ├─► rate_limit(max_requests=3, window=60)
          │    └─► Se >3 requisições/min: 429
          │
          ├─► DevolutionService.criar()
          │    │
          │    ├─► Validação #1: Prazo expirado?
          │    │    └─► data_emissao + prazo < hoje
          │    │         └─► Se SIM: raise PrazoExpiradoError
          │    │
          │    ├─► Validação #2: Quantidade > saldo?
          │    │    └─► Para cada item:
          │    │         quantidade_solicitada > quantidade_disponivel
          │    │         └─► Se SIM: raise QuantidadeIndisponível
          │    │
          │    ├─► Validação #3: Motivo válido?
          │    │    └─► motivo in MOTIVOS_DEVOLUCAO
          │    │         └─► Se NÃO: raise MotivoInválido
          │    │
          │    ├─► Processamento de arquivos:
          │    │    ├─► Fotos (JPEG/PNG, max 2MB cada)
          │    │    │   └─► Renomeia: devolucao_1_foto1.jpg
          │    │    │   └─► Salva em: uploads/fotos_devolucao/
          │    │    │
          │    │    └─► PDF (max 5MB)
          │    │        └─► Extrai texto com pdfplumber
          │    │        └─► Salva em: uploads/pdfs/
          │    │
          │    ├─► Criação no banco (INSERT):
          │    │    │
          │    │    ├─► INSERT Devolucao
          │    │    │    {
          │    │    │      cliente_id: 1,
          │    │    │      nota_fiscal_id: 1,
          │    │    │      motivo: "Produto danificado",
          │    │    │      status: "pendente",
          │    │    │      data_criacao: NOW(),
          │    │    │      id_usuario: request.user.id
          │    │    │    }
          │    │    │
          │    │    ├─► Para cada item solicitado:
          │    │    │    INSERT ItemDevolucao
          │    │    │    {
          │    │    │      devolucao_id: 1,
          │    │    │      produto_id: 1,
          │    │    │      quantidade_devolvida: 5,
          │    │    │      data_item: NOW()
          │    │    │    }
          │    │    │
          │    │    └─► COMMIT (confirma todas INSERTs)
          │    │
          │    └─► Retorna devolucao_id
          │
          ├─► Logging (auditoria)
          │    └─► logging_utils.log_event('devolucao.criada', {
          │         usuario_id: request.user.id,
          │         devolucao_id: 1,
          │         itens: 2,
          │         motivo: "Danificado",
          │         timestamp: "2026-03-05T10:30:45Z"
          │        })
          │        └─► Salva em logs/app.log
          │
          └─► JsonResponse({success: true, devolucao_id: 1})
                   │
                   ▼
          ◄ JavaScript redireciona para acompanhamento
```

### 6️⃣ FASE: Acompanhar Devoluções

```
┌────────────────────────────────────────────────────────┐
│    Usuário acessa /acompanhar-devolucoes               │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
         acompanhar_devolucoes() (GET VIEW)
                   │
          ├─► @login_required (valida sessão)
          │
          ├─► PaginationService.paginar()
          │    │
          │    ├─► Query: Devolucao.objects
          │    │          .filter(usuario_id=request.user.id)
          │    │          .select_related('cliente', 'nota_fiscal')
          │    │          .prefetch_related('itens__produto')
          │    │          .order_by('-data_criacao')
          │    │
          │    ├─► Aplica paginação:
          │    │    page_size = 20
          │    │    pagina = request.GET.get('page', 1)
          │    │    limit = 20, offset = 0 (pag 1)
          │    │           = 20, offset = 20 (pag 2)
          │    │
          │    └─► Retorna {devolucoes, total_count, num_pages}
          │
          └─► render('acompanhar_devolucoes.html', {
               devolucoes: [...],
               paginator: {...}
              })
                   │
                   ▼
          ◄ Renderiza template com Devolucao lista
             Cada devolucao mostra:
             • Status badge (pendente/em_processo/concluído)
             • Data criação
             • Nota fiscal associada
             • Motivo
             • Itens devolvidos
             • Foto/PDF se houver
```

---

## 📂 Estrutura de Diretórios

```
OldProject2/                          # Raiz do projeto
│
├── manage.py                         # Comando Django CLI
├── requirements.txt                  # Dependências Python
├── db.sqlite3                        # Banco de dados (desenvolvimento)
├── .env                              # Variáveis de ambiente (secreto)
├── .env.example                      # Template .env (git-tracked)
├── .gitignore                        # Arquivos ignorados pelo Git
│
├── ProjetoDevolucao/                 # Configuração Django
│   ├── __init__.py
│   ├── settings.py                   # Configurações (BD, apps, logging)
│   ├── urls.py                       # Rotas principais
│   ├── wsgi.py                       # WSGI para produção
│   └── asgi.py                       # ASGI para async
│
├── devolucao/                        # App principal (lógica)
│   ├── __init__.py
│   ├── models.py                     # Modelos BD:
│   │                                  #   - Usuario
│   │                                  #   - Cliente
│   │                                  #   - NotaFiscal
│   │                                  #   - Produto
│   │                                  #   - ItemNotaFiscal
│   │                                  #   - Devolucao
│   │                                  #   - ItemDevolucao
│   │                                  #   - ConfiguracaoSistema
│   │
│   ├── views.py                      # Views (Controllers):
│   │                                  #   - login_view()
│   │                                  #   - cadastro_view()
│   │                                  #   - acompanhar_devolucoes()
│   │                                  #   - tela_devolucao()
│   │                                  #   - buscar_cliente() [AJAX]
│   │                                  #   - buscar_notas_cliente() [AJAX]
│   │                                  #   - buscar_itens_nota() [AJAX]
│   │
│   ├── forms.py                      # Formulários:
│   │                                  #   - LoginForm
│   │                                  #   - CadastroForm
│   │                                  #   - ClienteForm
│   │                                  #   - NotaForm
│   │                                  #   - DevolucaoForm
│   │
│   ├── urls.py                       # Rotas do app
│   │
│   ├── admin.py                      # Admin Django (painel)
│   ├── apps.py                       # Config do app
│   ├── tests.py                      # Testes unitários
│   │
│   ├── services.py                   # Lógica de negócio (NOVO)
│   │                                  #   - DevolutionService
│   │                                  #   - ClienteService
│   │                                  #   - NotaService
│   │                                  #   - PrazoService
│   │
│   ├── logging_utils.py              # Utilities de logging (NOVO)
│   │                                  #   - log_event()
│   │                                  #   - mask_sensitive()
│   │
│   ├── pagination_service.py         # Paginação otimizada (NOVO)
│   │                                  #   - PaginationService
│   │
│   ├── rate_limiting.py              # Rate limiting (NOVO)
│   │                                  #   - @ratelimit decorator
│   │
│   ├── sankhya_api.py                # Integração ERP (OPCIONAL)
│   │
│   ├── migrations/                   # Histórico de mudanças BD
│   │   ├── 0001_initial.py
│   │   ├── 0002_..._add_fields.py
│   │   ├── 0003_..._more.py
│   │   ├── 0004_add_critical_indexes.py  # Índices BD (NOVO)
│   │   └── __init__.py
│   │
│   ├── static/                       # Arquivos estáticos (CSS, JS, IMG)
│   │   ├── css/
│   │   │   └── style.css             # CSS customizado
│   │   ├── js/                       # JavaScript (AJAX)
│   │   └── img/
│   │
│   ├── templates/                    # Templates HTML
│   │   ├── login.html                # Tela de login
│   │   ├── cadastro.html             # Tela de cadastro
│   │   ├── acompanhar_devolucoes.html # Dashboard (devoluções)
│   │   ├── devolucao.html            # Formulário de devolução
│   │   ├── 500.html                  # Página de erro customizada
│   │   └── base.html                 # Template base (OPCIONAL)
│   │
│   └── __pycache__/                  # Cache Python (ignorar)
│
├── staticfiles/                      # Arquivos estáticos coletados (PROD)
│   └── admin/
│
├── uploads/                          # Arquivos enviados
│   ├── fotos_devolucao/              # Fotos de devoluções
│   ├── pdfs/                         # PDFs guardados
│   └── uploads/                      # Espelhamento (DEPRECATED)
│
├── temp/                             # Arquivos temporários
│
├── logs/                             # Log files (estruturados)
│   ├── app.log                       # Logs gerais
│   └── errors.log                    # Logs de erro
│
└── Documentação:
    ├── README_OTIMIZACOES.md         # Resumo de otimizações
    ├── SERVICE_LAYER_GUIDE.md        # Como usar services
    ├── LOGGING_SETUP.md              # Como configura logging
    ├── RATE_LIMITING_INTEGRATION.md  # Como usar rate limit
    ├── PAGINATION_INTEGRATION.md     # Como usar paginação
    ├── RESUMO_FINAL.md               # Resumo executivo
    └── GUIA_COMPLETO.md              # Este arquivo!
```

---

## 🧩 Componentes Principais

### 1. Modelos (BD)

#### `Usuario`
Autenticação do sistema. Login via **email** (não username).

```python
class Usuario(AbstractBaseUser, PermissionsMixin):
    email          # Campo único, username
    is_active      # Se está ativo
    is_staff       # Se é administrador
    date_joined    # Data de criação
```

**Vinculação:**
```
Usuario 1-to-1 Cliente (opcional)
```

#### `Cliente`
Pessoa física ou jurídica.

```python
class Cliente:
    usuario       # FK → Usuario (1-to-1)
    tipo          # 'PF' (CPF) ou 'PJ' (CNPJ)
    
    # Se PF:
    cpf           # 11 dígitos
    nome          # Nome completo
    
    # Se PJ:
    cnpj          # 14 dígitos
    razao_social  # Razão social
    
    # Contato:
    email, telefone, celular
    
    # Endereço:
    logradouro, numero, complemento, bairro, cidade, estado, cep
```

**Validação:**
- CPF: Algoritmo de 2 dígitos verificadores
- CNPJ: Algoritmo de 2 dígitos verificadores
- Um documento por cliente (unique)

#### `NotaFiscal`
Documento fiscal de venda.

```python
class NotaFiscal:
    cliente          # FK → Cliente
    numero_nota      # "NF-001-2025" (único)
    data_emissao     # Data de emissão (usada para prazos)
    arquivo_pdf      # FileField (PDF da NF)
```

#### `Produto`
Itens da nota fiscal.

```python
class Produto:
    codigo       # ID do produto (ERP)
    descricao    # "Camiseta", "Calça", etc
```

#### `ItemNotaFiscal`
Linha de item em uma NF.

```python
class ItemNotaFiscal:
    nota_fiscal  # FK → NotaFiscal
    produto      # FK → Produto
    quantidade   # Qtd vendida (ex: 100)
```

#### `ConfiguracaoSistema`
Parametrizações globais.

```python
class ConfiguracaoSistema:
    prazo_devolucao_dias  # Padrão: 30 dias
```

#### `Devolucao`
Solicitação de devolução.

```python
class Devolucao:
    cliente          # FK → Cliente
    nota_fiscal      # FK → NotaFiscal
    usuario          # FK → Usuario (quem criou)
    motivo           # "Produto danificado", "Defeito", etc
    status           # 'pendente', 'em_processo', 'concluído'
    data_criacao     # Quando foi criada
    foto             # FileField (fotos do produto)
    arquivo_pdf      # FileField (documentação)
```

#### `ItemDevolucao`
Itens específicos sendo devolvidos.

```python
class ItemDevolucao:
    devolucao              # FK → Devolucao
    produto                # FK → Produto
    quantidade_devolvida   # Qtd que o cliente quer devolver
    data_item              # Quando adicionado
```

---

### 2. Views (Controllers)

#### `login_view(request)`
Tela e processamento de login.

```python
def login_view(request):
    if request.user.is_authenticated:
        return redirect('acompanhar_devolucoes')  # Já logado
    
    form = LoginForm(request.POST or None, request=request)
    
    if request.method == 'POST' and form.is_valid():
        auth.login(request, form.usuario)
        return redirect('acompanhar_devolucoes')
    
    return render(request, 'login.html', {'form': form})
```

**Fluxo:**
1. GET /login → Mostra formulário
2. POST /login (email + senha) → Valida credenciais
3. Se OK → Cria session → Redireciona dashboard
4. Se erro → Mostra mensagem de erro

---

#### `cadastro_view(request)`
Registra novo usuário + cliente.

```python
def cadastro_view(request):
    if request.user.is_authenticated:
        return redirect('acompanhar_devolucoes')
    
    form = CadastroForm(request.POST or None)
    
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        auth.login(request, usuario)
        messages.success(request, 'Cadastro realizado!')
        return redirect('acompanhar_devolucoes')
    
    return render(request, 'cadastro.html', {'form': form})
```

**O que `CadastroForm.save()` faz:**
1. Cria Usuario (email único)
2. Cria Cliente automático
3. Retorna Usuario criado

---

#### `acompanhar_devolucoes(request)`
Dashboard com histórico de devoluções.

```python
@login_required
def acompanhar_devolucoes(request):
    cliente = _get_cliente_logado(request)
    
    devolucoes = (Devolucao.objects
                  .filter(cliente=cliente)
                  .select_related('nota_fiscal', 'usuario')
                  .prefetch_related('itens')
                  .order_by('-data_criacao'))
    
    # Paginação
    page = request.GET.get('page', 1)
    devolucoes = pagina_list(devolucoes, page_size=20, page=page)
    
    return render(request, 'acompanhar_devolucoes.html', {
        'devolucoes': devolucoes
    })
```

**Exibe:**
- Lista de devoluções do cliente logado
- Paginada (20 por página)
- Cada devolução com:
  - Status badge
  - Data
  - Nota fiscal
  - Motivo
  - Itens devolvidos
  - Fotos/PDF

---

#### `tela_devolucao(request)` - Formulário
Tela com formulário interativo de devolução.

```python
@login_required
def tela_devolucao(request):
    cliente = _get_cliente_logado(request)
    
    return render(request, 'devolucao.html', {
        'cliente': cliente,
        'motivos': MOTIVOS_DEVOLUCAO
    })
```

**Renderiza:**
- Inputs para preencher CPF/CNPJ
- Botões AJAX para buscar dados
- Tabela dinâmica de notas
- Tabela dinâmica de itens
- Inputs para quantidade devolver
- Upload de fotos/PDF

---

#### AJAX Endpoints

##### `buscar_cliente(request)` - AJAX
Busca Cliente por CPF/CNPJ.

```python
def buscar_cliente(request):
    documento = request.POST.get('documento', '')
    
    # ClienteService
    cliente = ClienteService.buscar_por_documento(documento)
    
    if cliente:
        return JsonResponse({
            'id': cliente.id,
            'nome': cliente.nome_exibicao,
            'documento': cliente.documento,
            'email': cliente.email,
            'telefone': cliente.telefone
        })
    else:
        return JsonResponse({'error': 'Não encontrado'}, status=404)
```

**Requisição:**
```bash
POST /ajax/buscar-cliente/
Content-Type: application/x-www-form-urlencoded

documento=11111111111
```

**Resposta (sucesso):**
```json
{
  "id": 1,
  "nome": "João Silva",
  "documento": "111.111.111-11",
  "email": "joao@example.com",
  "telefone": "11999999999"
}
```

---

##### `buscar_notas_cliente(request)` - AJAX
Lista notas fiscais de um cliente.

```python
def buscar_notas_cliente(request):
    cliente_id = request.POST.get('cliente_id')
    
    notas = NotaService.obter_notas(cliente_id)
    
    notas_data = []
    for nota in notas:
        dias_restantes, status = PrazoService.status_prazo(nota)
        
        notas_data.append({
            'id': nota.id,
            'numero': nota.numero_nota,
            'data_emissao': nota.data_emissao.isoformat(),
            'dias_restantes': dias_restantes,
            'status': status
        })
    
    return JsonResponse({'notas': notas_data})
```

**Resposta:**
```json
{
  "notas": [
    {
      "id": 1,
      "numero": "NF-001-2025",
      "data_emissao": "2025-12-01",
      "dias_restantes": 15,
      "status": "DISPONÍVEL"
    },
    {
      "id": 2,
      "numero": "NF-002-2025",
      "data_emissao": "2025-10-01",
      "dias_restantes": -30,
      "status": "EXPIRADA"
    }
  ]
}
```

---

##### `buscar_itens_nota(request)` - AJAX
Lista itens de uma nota com saldo disponível.

```python
def buscar_itens_nota(request):
    nota_id = request.POST.get('nota_id')
    
    itens = ItemNotaFiscal.objects.filter(nota_fiscal_id=nota_id)
    
    itens_data = []
    for item in itens:
        disponivel = _quantidade_disponivel(nota_id, item.produto_id)
        
        itens_data.append({
            'produto_id': item.produto_id,
            'descricao': item.produto.descricao,
            'quantidade_original': item.quantidade,
            'quantidade_disponivel': disponivel
        })
    
    return JsonResponse({'itens': itens_data})
```

---

### 3. Services (Lógica de Negócio)

#### `DevolutionService`
Orquestra criação de devolução.

```python
class DevolutionService:
    @staticmethod
    def criar(cliente_id, nota_id, motivo, itens_list, usuario):
        """
        Cria devolução com validações.
        
        Validações:
          - Prazo expirado?
          - Quantidades > saldo?
          - Motivo válido?
        
        Transação: SER TUDO OU NADA
        """
        # 1. Validar prazos
        nota = NotaFiscal.objects.get(id=nota_id)
        if PrazoService.esta_expirado(nota):
            raise PrazoExpiradoError("Prazo de devolução expirado")
        
        # 2. Validar quantidades
        for item in itens_list:
            disponivel = _quantidade_disponivel(nota_id, item['produto_id'])
            if item['quantidade'] > disponivel:
                raise QuantidadeIndisponível(
                    f"Produto {item['produto_id']} sem saldo"
                )
        
        # 3. Validar motivo
        if motivo not in MOTIVOS_VALIDOS:
            raise MotivoInválido(f"Motivo '{motivo}' inválido")
        
        # 4. Criar em BD (transação)
        with transaction.atomic():
            devolucao = Devolucao.objects.create(
                cliente_id=cliente_id,
                nota_fiscal_id=nota_id,
                usuario=usuario,
                motivo=motivo,
                status='pendente'
            )
            
            for item in itens_list:
                ItemDevolucao.objects.create(
                    devolucao=devolucao,
                    produto_id=item['produto_id'],
                    quantidade_devolvida=item['quantidade']
                )
        
        return devolucao
```

---

#### `ClienteService`
Busca e validação de clientes.

```python
class ClienteService:
    @staticmethod
    def buscar_por_documento(documento):
        """Busca Cliente por CPF ou CNPJ."""
        apenas_digitos = re.sub(r'\D', '', documento)
        
        if len(apenas_digitos) == 11:
            # É CPF
            return Cliente.objects.filter(cpf=apenas_digitos).first()
        elif len(apenas_digitos) == 14:
            # É CNPJ
            return Cliente.objects.filter(cnpj=apenas_digitos).first()
        
        return None
```

---

#### `PrazoService`
Cálculo de prazos de devolução.

```python
class PrazoService:
    @staticmethod
    def calcular_prazo(data_emissao):
        """Calcula data limite de devolução."""
        prazo_dias = ConfiguracaoSistema.prazo()
        return data_emissao + timedelta(days=prazo_dias)
    
    @staticmethod
    def esta_expirado(nota):
        """Verifica se a nota está vencida."""
        limite = PrazoService.calcular_prazo(nota.data_emissao)
        return date.today() > limite
    
    @staticmethod
    def status_prazo(nota):
        """Retorna (dias_restantes, status)."""
        limite = PrazoService.calcular_prazo(nota.data_emissao)
        dias = (limite - date.today()).days
        
        if dias < 0:
            return dias, "EXPIRADA"
        elif dias <= 7:
            return dias, "VENCENDO"
        else:
            return dias, "DISPONÍVEL"
```

---

#### `NotaService`
Operações com notas fiscais.

```python
class NotaService:
    @staticmethod
    def obter_notas(cliente_id, ordenar_por='-data_emissao'):
        """Retorna notas do cliente (paginadas)."""
        return (NotaFiscal.objects
                .filter(cliente_id=cliente_id)
                .select_related('cliente')
                .prefetch_related('itens__produto')
                .order_by(ordenar_por))
```

---

### 4. Logging Estruturado

Usa `structlog` para registrar eventos em JSON.

```python
from devolucao.logging_utils import log_event

# Registrar criação de devolução
log_event('devolucao.criada', {
    'usuario_id': request.user.id,
    'devolucao_id': devolucao.id,
    'itens': len(itens_list),
    'motivo': motivo
})

# Saída em logs/app.log:
{
  "event": "devolucao.criada",
  "usuario_id": 5,
  "devolucao_id": 42,
  "itens": 2,
  "motivo": "Produto danificado",
  "timestamp": "2026-03-05T10:30:45.123456Z"
}
```

---

### 5. Rate Limiting

Proteção contra abuso de AJAX.

```python
from devolucao.rate_limiting import ratelimit

@ratelimit(max_requests=3, window=60)  # 3 req/min
def buscar_cliente(request):
    """Se >3 requisições em 60s → 429 Too Many Requests"""
    ...
```

---

### 6. Paginação

Queries otimizadas para grandes volumes.

```python
from devolucao.pagination_service import paginar

devolucoes = Devolucao.objects.filter(cliente=cliente)

# Retorna: QuerySet com .paginator, .page_obj
paginado = paginar(devolucoes, page_size=20, page=request.GET.get('page', 1))

# Template:
{% for dev in paginado %}
  <div>{{ dev.motivo }}</div>
{% endfor %}

<div class="pagination">
  {% if paginado.has_previous %}
    <a href="?page=1">Primeira</a>
  {% endif %}
  <!-- Números de páginas -->
  {% if paginado.has_next %}
    <a href="?page={{ paginado.next_page_number }}">Próxima</a>
  {% endif %}
</div>
```

---

## 🚀 Instalação Passo a Passo

### Pré-requisitos

Antes de começar, certifique-se de ter:

- ✅ **Python 3.9+** instalado
- ✅ **MySQL 5.7+** rodando localmente
- ✅ **Git** instalado
- ✅ **pip** (gerenciador de pacotes Python)
- ✅ **Visual Studio Code** (recomendado)

### Verificar instalações

```powershell
# Verificar Python
python --version
# Esperado: Python 3.x.x

# Verificar pip
pip --version
# Esperado: pip 21.0+

# Verificar MySQL (se instalado)
mysql --version
# Esperado: mysql Ver 8.0+
```

---

### PASSO 1: Clonar o Repositório

```bash
# Vá para a pasta onde quer o projeto
cd C:\Users\seu_usuario\Desktop

# Clone o repositório (caso esteja no Git)
git clone https://github.com/seu_usuario/OldProject2.git
cd OldProject2

# OU se já tem a pasta, apenas abra:
cd C:\Users\kayron.eduardo\Desktop\OldProject2
```

---

### PASSO 2: Criar Virtual Environment

Um virtual environment isola as dependências do projeto.

```powershell
# Criar venv
python -m venv venv

# Ativar venv (Windows)
.\venv\Scripts\Activate.ps1

# Você deve ver "(venv)" no prompt:
# (venv) C:\Users\kayron.eduardo\Desktop\OldProject2>

# Se houver erro de permissão, rode PowerShell como admin ou:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Para próximas sessões:**
```powershell
# Ativar (Windows)
.\venv\Scripts\Activate.ps1

# Desativar (quando terminar)
deactivate
```

---

### PASSO 3: Instalar Dependências

```powershell
# Certifique-se de estar na pasta do projeto COM venv ativado
cd C:\Users\kayron.eduardo\Desktop\OldProject2

# Instalar todas as dependências
pip install -r requirements.txt

# Esperado:
# Successfully installed Django==4.2.0 PyMySQL==1.1.0 ... (todos)
```

**O que será instalado:**
```
Django==4.2.0              # Framework web
PyMySQL==1.1.0             # Driver MySQL
python-dotenv==1.2.2       # Variáveis de ambiente
structlog==24.1.0          # Logging estruturado
django-ratelimit==4.1.0    # Rate limiting
Pillow==11.0.0             # Processamento de imagens
pdfplumber==0.11.9         # Leitura de PDFs
```

---

### PASSO 4: Configurar Variáveis de Ambiente

#### 4a) Cópia o arquivo `.env.example` para `.env`

```powershell
# Copiar (Windows)
Copy-Item .env.example .env

# Ou copiar manualmente:
# Abra .env.example no VS Code
# Copie todo conteúdo
# Crie arquivo .env
# Cole conteúdo
```

#### 4b) Editar `.env` com suas credenciais

**Arquivo `.env`:**
```bash
# ─── SEGREDOS ─────────────────────────────
SECRET_KEY=seu-chave-segura-aqui-64-caracteres
DEBUG=True  # False em produção

# ─── BANCO DE DADOS ────────────────────────
DATABASE_ENGINE=django.db.backends.mysql
DATABASE_NAME=devolucao
DATABASE_USER=root
DATABASE_PASSWORD=sua_senha_mysql  # ⚠️ MUDE ISTO
DATABASE_HOST=localhost
DATABASE_PORT=3306

# ─── HOSTS ────────────────────────────────
ALLOWED_HOSTS=localhost,127.0.0.1

# ─── LOGGING ────────────────────────────────
LOG_LEVEL=INFO
```

**Procedimento:**
1. Abra `.env` no VS Code
2. Mude `DATABASE_PASSWORD` para sua senha MySQL
3. Salve (Ctrl+S)

---

### PASSO 5: Criar Banco de Dados MySQL

**Se você NÃO tem banco de dados `devolucao` ainda:**

```powershell
# Conectar ao MySQL
mysql -u root -p

# Digite sua senha MySQL (digitará invisível)

# Dentro do prompt MySQL:
mysql> CREATE DATABASE devolucao CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# Verificar criação
mysql> SHOW DATABASES;
# Deve listar "devolucao"

# Sair
mysql> EXIT;
```

**Se já tem o banco:**
```powershell
mysql -u root -p -e "SHOW DATABASES;" | findstr devolucao

# Se aparecer "devolucao", está OK
```

---

### PASSO 6: Aplicar Migrações (Criar Tabelas)

```powershell
# Certifique-se de estar na pasta raiz COM venv ativado
cd C:\Users\kayron.eduardo\Desktop\OldProject2

# Ver migrações não aplicadas
python manage.py showmigrations

# Aplicar todas
python manage.py migrate

# Esperado:
# Running migrations:
#   Applying devolucao.0001_initial... OK
#   Applying devolucao.0002_...         OK
#   Applying devolucao.0003_...         OK
#   Applying devolucao.0004_...         OK
```

**O que cria:**
- Tabelas de usuário, cliente, nota fiscal
- Tabelas de devolução, itens
- Índices otimizados no banco

---

### PASSO 7: Criar Superusuário (Admin)

```powershell
python manage.py createsuperuser

# Promptará:
# Email: seu@email.com
# Password: sua_senha
# Password (again): sua_senha

# Se OK:
# Superuser created successfully.
```

---

### PASSO 8: Coletar Arquivos Estáticos (Opcional)

Necessário apenas em **produção**. Em desenvolvimento, o Django serve automaticamente.

```powershell
# Coletar CSS, JS, IMG estáticos
python manage.py collectstatic --noinput

# Cria pasta staticfiles/
```

---

### PASSO 9: Rodar o Servidor de Desenvolvimento

```powershell
python manage.py runserver

# Esperado:
# Starting development server at http://127.0.0.1:8000/
# Quit the server with CTRL-BREAK.
```

---

## 🎮 Executar o Projeto

### Fluxo Completo de Execução

#### 1️⃣ Abrir Terminal PowerShell

```powershell
# Navegue até a pasta do projeto
cd C:\Users\kayron.eduardo\Desktop\OldProject2

# Ativar virtual environment
.\venv\Scripts\Activate.ps1

# Prompt deve mostrar (venv)
```

#### 2️⃣ Iniciar servidor Django

```powershell
python manage.py runserver

# Saída:
# Watching for file changes with StatReloader
# Quit the server with CTRL-BREAK.
# Starting development server at http://127.0.0.1:8000/
# Django version 4.2.0, using settings 'ProjetoDevolucao.settings'
```

#### 3️⃣ Acessar no navegador

Abra seu navegador e vá para:

```
http://localhost:8000/
```

**Você será redirecionado para `/login`**

#### 4️⃣ Primeira vez: Criar conta

```
Clique em "Cadastro"
    ↓
Email: novo@email.com
Senha: senha_forte_123
Confirmar senha: senha_forte_123
    ↓
Enviar
    ↓
Login automático + Redirecionado para Dashboard
```

#### 5️⃣ Após login: Usar a aplicação

**Dashboard:**
```
URL: http://localhost:8000/
Mostra: Histórico de suas devoluções
```

**Nova Devolução:**
```
URL: http://localhost:8000/devolucao/
Mostra: Formulário interativo
  1. Preencha CPF/CNPJ
  2. Clique "Buscar Cliente"
  3. Clique "Buscar Notas"
  4. Selecione nota
  5. Clique "Buscar Itens"
  6. Preencha quantidades
  7. Selecione motivo
  8. Enviar
```

**Painel Admin:**
```
URL: http://localhost:8000/admin/
Login: seu@email.com + sua_senha
Mostra: Gerenciamento completo do BD
```

---

### Arquivo de Configuração Pós-Instalação

Crie um arquivo `SETUP_LOCAL.md` no seu projeto para documentar sua configuração:

```markdown
# Setup Local - Seus Dados

## Ambiente
- Python: 3.x.x
- DB: MySQL em localhost:3306
- Email: seu@email.com (superuser)

## Ports
- Django Dev: http://localhost:8000
- MySQL: localhost:3306

## Credenciais
- Admin: seu@email.com / [sua_senha]
- DB: root / [sua_senha_mysql]

## Como rodar
1. .\venv\Scripts\Activate.ps1
2. python manage.py runserver
3. Abra http://localhost:8000
```

---

## 🆘 Troubleshooting

### ❌ Erro: "ModuleNotFoundError: No module named 'django'"

**Causa:** Virtual environment não ativado ou dependências não instaladas

**Solução:**
```powershell
# Ativar venv
.\venv\Scripts\Activate.ps1

# Verificar instalação
pip list | findstr django

# Se não aparecer, instalar:
pip install -r requirements.txt
```

---

### ❌ Erro: "Access denied for user 'root'@'localhost'"

**Causa:** Senha do MySQL incorreta no `.env`

**Solução:**
```powershell
# 1. Verificar senha MySQL (tente conectar)
mysql -u root -p

# 2. Se conectou, está OK - mude no .env
# Se não conectou, force reset:
```

**Reset senha MySQL (Windows):**
```powershell
# Atalho: Tecla Windows + R
services.msc

# Procure "MySQL"
# Botão direito → Iniciar (se parado)

# Tente reconectar
mysql -u root -p
```

---

### ❌ Erro: "No module named 'django.core.management'"

**Causa:** Não está na pasta correta

**Solução:**
```powershell
# Certifique-se
cd C:\Users\kayron.eduardo\Desktop\OldProject2
ls manage.py  # Deve aparecer

# Depois tente novamente
python manage.py runserver
```

---

### ❌ Erro: "FileNotFoundError: [Errno 2] No such file or directory: '.env'"

**Causa:** `.env` não existe

**Solução:**
```powershell
# Criar .env a partir de .env.example
Copy-Item .env.example .env

# Editar credenciais
notepad .env

# Salvar (Ctrl+S)
```

---

### ❌ Erro: "CSRF token missing or incorrect"

**Causa:** Sessão expirou ou formulário sem token

**Solução:**
1. Limpe cookies do navegador (Ctrl+Shift+Del)
2. Faça logout e login novamente
3. Verifique que tem `{% csrf_token %}` no form HTML

---

### ❌ Erro: "database table does not exist"

**Causa:** Migrações não foram aplicadas

**Solução:**
```powershell
# Aplicar todas as migrações
python manage.py migrate

# Criar tabelas novamente se necessário
python manage.py migrate zero  # Reseta
python manage.py migrate       # Reaplica
```

---

### ❌ Erro: "Port 8000 already in use"

**Causa:** Outro processo usando porta 8000

**Solução:**
```powershell
# Opção 1: Usar outra porta
python manage.py runserver 8001

# Opção 2: Matar processo na porta
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process

# Depois tentar novamente
python manage.py runserver
```

---

### ✅ Tudo pronto?

Se você conseguiu:
1. ✅ Instalar dependências
2. ✅ Criar/conectar ao banco MySQL
3. ✅ Aplicar migrações
4. ✅ Rodar servidor Django
5. ✅ Acessar http://localhost:8000

**Parabéns! O projeto está rodando em sua máquina! 🎉**

---

## 📚 Próximos Passos

### Para Desenvolvedores Adicionando Recursos

1. **Criar branch de trabalho:**
   ```bash
   git checkout -b feature/meu-recurso
   git add .
   git commit -m "Adição de meu recurso"
   git push origin feature/meu-recurso
   ```

2. **Entender Service Layer:**
   - Leia [SERVICE_LAYER_GUIDE.md](SERVICE_LAYER_GUIDE.md)
   - Use classes do `devolucao/services.py`

3. **Logging correto:**
   - Leia [LOGGING_SETUP.md](LOGGING_SETUP.md)
   - Use `log_event()` para auditoria

4. **Paginação:**
   - Leia [PAGINATION_INTEGRATION.md](PAGINATION_INTEGRATION.md)

5. **Rate Limiting:**
   - Leia [RATE_LIMITING_INTEGRATION.md](RATE_LIMITING_INTEGRATION.md)

---

## 📞 Suporte

Se encontrar problemas:

1. **Verifique erros:**
   ```bash
   # Ver logs estruturados
   tail logs/app.log
   tail logs/errors.log
   ```

2. **Teste a aplicação:**
   ```bash
   python manage.py test devolucao
   ```

3. **Restaure BD limpo:**
   ```bash
   python manage.py migrate zero
   python manage.py migrate
   ```

---

## ✨ Resumo

| Item | Status |
|------|--------|
| Documentação | ✅ Completa |
| Código | ✅ Produção-ready |
| BD | ✅ Indexado |
| Logging | ✅ Estruturado |
| Segurança | ✅ `.env` configurado |
| Performance | ✅ Service Layer + Paginação |
| Rate Limiting | ✅ Protegido |

**Você está pronto para contribuir!** 🚀

---

**Última atualização:** 05 de março de 2026  
**Versão:** 1.0  
**Mantido por:** Sua Equipe
