# DOCUMENTATION: GUIA VISUAL

Diagramas e fluxos visuais do sistema.

## 🔄 Fluxo de Usuário Completo

```
┌─────────────────────────────────┐
│    NOVO ACESSO                  │
└──┬──────────────────────────────┘
   │
   ├─ [LOGIN]    [CADASTRO]    [HOME]
   │      │          │            │
   └──────┴──────────┴────────────┘
              │
      ▼ [Autenticado]
   
┌─────────────────────────────────┐
│ DASHBOARD                       │
│ ┌─────────────────────────────┐ │
│ │ Minhas Devoluções           │ │
│ │ ──────────────────────────  │ │
│ │ Status │ Data │ NF │ Ações │ │
│ │ ✓      │ 05/3 │ 1  │ [Ver] │ │
│ │ ⏳     │ 04/3 │ 2  │ [Ver] │ │
│ │ ◉      │ 03/3 │ 3  │ [Ver] │ │
│ └─────────────────────────────┘ │
│                                 │
│  [+ NOVA DEVOLUÇÃO]             │
└────┬────────────────────────────┘
     │
     ▼ [Clica botão]

┌─────────────────────────────────┐
│ FORMULÁRIO DE DEVOLUÇÃO         │
│                                 │
│ 1. CPF/CNPJ: [__________] [🔍] │
│    ✓ João Silva                 │
│                                 │
│ 2. [BUSCAR NOTAS] 🔍            │
│    ◉ NF-001 ✓ DISPONÍVEL       │
│    ○ NF-002 ✗ EXPIRADA        │
│                                 │
│ 3. Produto  │ Qtd │ [Input]    │
│    Camiseta │ 100 │ [___5____] │
│    Calça    │ 50  │ [___3____] │
│                                 │
│ 4. Motivo: [Danificado ▼]       │
│    Fotos: [📸]  PDF: [📄]       │
│                                 │
│    [CANCELAR] [ENVIAR] ✓        │
└────┬────────────────────────────┘
     │ POST /devolucao/
     ▼
   ✓ Validações ✓ Criado ✓ Logs
     │
     ▼ [Sucesso]
   [CONFIRMAÇÃO]
```

---

## 📊 Arquitetura em Camadas

```
┌──────────────────────────────────────┐
│ 🌐 FRONTEND (HTML+JS+CSS)            │
└────┬─────────────────────────────────┘
     │ HTTP
     ▼
┌──────────────────────────────────────┐
│ 🔧 VIEWS (Django)                    │
│ • login_view()                       │
│ • tela_devolucao()                   │
│ • buscar_cliente() [AJAX]            │
│ • buscar_notas_cliente() [AJAX]      │
│ • criar_devolucao() [POST]           │
└────┬─────────────────────────────────┘
     │ Calls
     ▼
┌──────────────────────────────────────┐
│ 📦 SERVICES (Lógica)                 │
│ • DevolutionService                  │
│ • ClienteService                     │
│ • NotaService                        │
│ • PrazoService                       │
│ • PaginationService                  │
└────┬─────────────────────────────────┘
     │ ORM
     ▼
┌──────────────────────────────────────┐
│ 🗄️ MODELS (Dados)                    │
│ • Usuario, Cliente                   │
│ • NotaFiscal, ItemNotaFiscal         │
│ • Devolucao, ItemDevolucao           │
└────┬─────────────────────────────────┘
     │ SQL
     ▼
┌──────────────────────────────────────┐
│ 💾 MYSQL (Banco)                     │
└──────────────────────────────────────┘
```

---

## 🔒 Fluxo de Autenticação

```
Novo?
├─ SIM → [CADASTRO]
│         Email + CPF/CNPJ + Senha
│         └→ Criar Usuario + Cliente
│
└─ NÃO → [LOGIN]
         Email + Senha
         └→ Buscar Usuario
            ├─ Senha OK? → [Session]
            └─ Senha errada? → [401]
```

---

## 📈 Fluxo de Dados

### Buscar Cliente

```
Frontend: CPF → POST /ajax/buscar-cliente/
    ↓
ClienteService.buscar_por_documento()
    ├─ Apenas dígitos
    ├─ Query: Cliente.objects.filter(cpf=)
    └─ Valida CPF
    ↓
JSON: {nome, email, telefone, ...}
    ↓
Frontend: Renderiza
```

### Criar Devolução

```
Frontend: Form → POST /devolucao/
    ↓
Valida CSRF + Auth + Rate limit
    ↓
@transaction.atomic()
    ├─ Valida Prazo
    ├─ Valida Quantidades
    ├─ Processa Arquivos
    ├─ INSERT Devolucao
    ├─ INSERT ItemDevolucao (foreach)
    └─ COMMIT ou ROLLBACK
    ↓
log_event('devolucao.criada', {...})
    ↓
JSON: {success: true, devolucao_id: 42}
```

---

## 🗄️ Modelo de Dados

### Relacionamentos

```
USUARIO        1:1
  │──────┐
  │      │
  ▼      ▼
CLIENTE ←── 1:N ──→ NOTAFISCAL ←── 1:N ──→ ITEMNOTAFISCAL
  │
  ├──── 1:N ──→ DEVOLUCAO
  │              │
  │              └──── 1:N ──→ ITEMDEVOLUCAO
  │                              ↑
  │                              │
  └──── 1:N ──→ PRODUTO ◄────────┘
```

### Tabelas Principais

```
tb_usuario         → Autenticação
tb_cliente         → PF (CPF) ou PJ (CNPJ)
tb_notafiscal      → Documentos fiscais (NF)
tb_produto         → Itens vendáveis
tb_itens_nota      → Linha de NF
tb_devolucao       → Solicitação de devolução
tb_item_devolucao  → Itens sendo devolvidos
tb_configuracao    → Parametrizações globais
```

---

## ⚙️ Stack Técnico

```
Frontend:          Backend:           Database:
├─ HTML5           ├─ Django 4.2       └─ MySQL 5.7+
├─ CSS3            ├─ Python 3.9+      
├─ JavaScript      └─ PyMySQL, structlog,
└─ Vanilla            pdfplumber, Pillow
```

---

## 🎯 Estados de Devolução

```
[CRIAÇÃO]
    ↓
[PENDENTE] ⏳ Aguardando revisão
    ├──→ [EM_PROCESSO] 🔄 Em análise
    │       ├──→ [CONCLUÍDO] ✓ Finalizado
    │       └──→ [PENDENTE] (retorna)
    └──→ [REJEITADO] ✗ Não aceito
```

---

## 🔐 Segurança

```
[Entrada de Usuário]
    ├─ CSRF Token ✓
    ├─ Rate Limiting ✓
    └─ Input Validation ✓
         ↓
    [Query Segura]
    ├─ ORM (protegida de SQL injection)
    ├─ Parametrized queries
    └─ select_related (otimizado)
         ↓
    [Banco Seguro]
    ├─ Transação @atomic
    ├─ Índices otimizados
    └─ InnoDB (ACID)
```

---

## 📊 Performance

### Sem Otimização

```
Query: SELECT * FROM tb_devolucao
Tempo: 45 segundos
Memória: 450MB
Resultado: Timeout do servidor
```

### Com Otimização (Paginação)

```
Query: SELECT * FROM tb_devolucao LIMIT 50 OFFSET 0
Tempo: 300 ms
Memória: 5MB
Resultado: Responsivo e rápido
```

---

## 🧪 Adicionando Feature

```
PLANEJAR
    ↓
CRIAR BRANCH (feature/*)
    ↓
IMPLEMENTAR
    ├─ Model (se necessário)
    ├─ Migração
    ├─ Service
    ├─ View
    ├─ URL
    └─ Teste
    ↓
TESTAR (python manage.py test)
    ↓
COMMIT (mensagem clara)
    ↓
PULL REQUEST
```

---

**Status:** 🟢 Referência Visual Completa  
**Última atualização:** 7 de Abril de 2026
