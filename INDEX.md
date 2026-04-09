# 📚 ÍNDICE GERAL DO PROJETO

## Bem-vindo ao Sistema de Gerenciamento de Devoluções! 👋

Este documento centraliza toda a estrutura do projeto. Use o índice abaixo para encontrar exatamente o que você precisa.

---

## ⚡ GUIA RÁPIDO - Comece Aqui!

### 🚀 Quero Rodar o Projeto AGORA (5 min)
📄 [QUICK_START.md](QUICK_START.md)
```bash
.\venv\Scripts\Activate.ps1
python manage.py runserver
# → http://localhost:8000
```

### 📊 Quero Ver Diagramas e Fluxos (20 min)
📄 [DOCUMENTATION/VISUAL_GUIDE.md](DOCUMENTATION/VISUAL_GUIDE.md)
- User journey completo
- Arquitetura em camadas
- Diagrama de dados
- Estados de devolução

### 📖 Quero Entender a Arquitetura (30-60 min)
Leia em ordem:
1. **Resumo Visual (5 min):** [DOCUMENTATION/VISUAL_GUIDE.md](DOCUMENTATION/VISUAL_GUIDE.md)
2. **Arquitetura Completa (30 min):** [DOCUMENTATION/ARCHITECTURE.md](DOCUMENTATION/ARCHITECTURE.md)
3. **Fluxo de Dados (15 min):** [DOCUMENTATION/ARCHITECTURE.md#fluxo-de-dados](DOCUMENTATION/ARCHITECTURE.md)

### 🛠️ Vou Adicionar uma Nova Feature (1-2 h)
📄 [DOCUMENTATION/DEVELOPMENT.md](DOCUMENTATION/DEVELOPMENT.md)
- Padrões de código
- Workflow de features
- Exemplos práticos
- Checklist de PR

---

## 📁 ESTRUTURA DE PASTAS

### 📄 RAIZ - Arquivos Essenciais
```
README.md              ← Visão geral do projeto
QUICK_START.md         ← Setup em 5 minutos
INDEX.md               ← Você está aqui! 📍
requirements.txt       ← Dependências Python
manage.py              ← CLI Django
.env / .env.example    ← Configuração de ambiente
```

### 📚 DOCUMENTATION/ - Guias Principais
```
ARCHITECTURE.md        ← Arquitetura completa, MVC, Service Layer
DEVELOPMENT.md         ← Como adicionar features, padrões, workflow
VISUAL_GUIDE.md        ← Diagramas, fluxos, diagrama E/R, stack técnico
```

| Arquivo | Tempo | Noção | Quando Ler |
|---------|-------|-------|-----------|
| ARCHITECTURE.md | 30 min | Entender tudo | Primeira semana |
| DEVELOPMENT.md | 1-2 h | Projeto completo | Antes de codificar |
| VISUAL_GUIDE.md | 20 min | Visão rápida | Prefere diagramas |

### 🔧 GUIDES/ - Guias Técnicos de Integração
```
SERVICES.md            ← Como usar ClienteService, NotaService, etc
LOGGING.md             ← Logging estruturado com structlog
PAGINATION.md          ← Paginação server-side (otimização #7)
RATE_LIMITING.md       ← Rate limiting decorators (otimização #6)
```

| Guia | Descrição | Tipo |
|------|-----------|------|
| SERVICES.md | Exemplos de como usar serviços de negócio | Integração |
| LOGGING.md | Configurar logging estruturado | Infraestrutura |
| PAGINATION.md | Implementar paginação eficiente | Performance |
| RATE_LIMITING.md | Proteger endpoints com rate limit | Segurança |

### 🗂️ ARCHIVE/ - Documentação Histórica
```
OPTIMIZATIONS_PHASE1.md       ← Log de otimizações fase 1-2
OPTIMIZATIONS_SUMMARY.md      ← Resumo final de otimizações
TEST_RESULTS_2026_04_07.md    ← Resultados de testes detalhados
TEST_SUMMARY_2026_04_07.md    ← Sumário executivo de testes
```

**Use ARCHIVE/ para:**
- Entender histórico de otimizações
- Consultar resultados de testes passados
- Referência de decisões anteriores

---

## 🧪 TESTES - Pasta `tests/`

| Arquivo | Cobertura | Status | Executar |
|---------|-----------|--------|----------|
| `test_business_flow.py` | Fluxo completo de negócio | ✅ 100% | `python tests/test_business_flow.py` |
| `test_services.py` | Service layer isolado | ✅ 87.5% | `python tests/test_services.py` |
| `test_views.py` | Views/Auth/AJAX | ✅ 100% | `python tests/test_views.py` |
| `test_integration.py` | Full return flow com NF | ✅ 100% | `python tests/test_integration.py` |
| `test_models.py` | Model schemas/validação | ✅ Active | `python tests/test_models.py` |

**Executar todos os testes:**
```bash
cd tests/
python test_business_flow.py
python test_services.py
python test_views.py
python test_integration.py
```

---

## 🐍 CÓDIGO-FONTE - Estrutura Django

### Aplicação Principal: `devolucao/`
```
devolucao/
├── models.py              ← 12 modelos de dados
├── services.py            ← 5 service classes (lógica de negócio)
├── views.py               ← 45+ endpoints/views
├── forms.py               ← Formulários Django
├── urls.py                ← Roteamento de URLs
├── decorators.py          ← Decorators customizados
│
├── INFRAESTRUTURA:
├── logging_utils.py       ← Structlog integration
├── pagination_service.py  ← Server-side pagination
├── rate_limiting.py       ← Rate limit decorators
├── sankhya_api.py         ← ERP integration
├── importacao_service.py  ← XML/ERP import
│
├── migrations/            ← Schema migrations (5 versões)
├── static/css/            ← Estilos (dark mode, materialize)
└── templates/             ← 12 templates HTML
```

### Configuração: `ProjetoDevolucao/`
```
ProjetoDevolucao/
├── settings.py            ← Django settings (logging, apps, BD)
├── urls.py                ← Root URL routing
├── asgi.py                ← ASGI server
└── wsgi.py                ← WSGI server
```

### Pastas Adicionais
```
logs/                      ← Structured logging output (JSON)
uploads/                   ← User files (fotos, PDFs)
temp/                      ← Temporary processing
.git/                      ← Version control
venv/                      ← Python virtual environment
```

---

## 🎯 DECISÃO RÁPIDA - Qual Guia Para Mim?

### Você é novo no projeto?
```
Novo em Django?
├─ SIM: Leia QUICK_START.md → DOCUMENTATION/VISUAL_GUIDE.md
└─ NÃO: Leia QUICK_START.md → DOCUMENTATION/ARCHITECTURE.md
```

### Você vai codificar uma feature?
```
Qual tipo de feature?
├─ Novo endpoint: DOCUMENTATION/DEVELOPMENT.md + GUIDES/SERVICES.md
├─ Novo modelo: DOCUMENTATION/DEVELOPMENT.md + DOCUMENTATION/ARCHITECTURE.md
├─ Performance: GUIDES/PAGINATION.md ou GUIDES/RATE_LIMITING.md
└─ Logging: GUIDES/LOGGING.md
```

### Você quer entender "como funciona"?
```
Prefere aprender como?
├─ Visualmente (diagramas): DOCUMENTATION/VISUAL_GUIDE.md
├─ Detalhadamente (texto): DOCUMENTATION/ARCHITECTURE.md
├─ Escrevendo código: DOCUMENTATION/DEVELOPMENT.md
└─ Vendo exemplos: GUIDES/* (cada guia tem exemplos)
```

### Você precisa debugar algo?
```
Tipo de problema?
├─ Teste falhando: ARCHIVE/TEST_* para referência histórica
├─ Logging não funciona: GUIDES/LOGGING.md
├─ Performance lenta: GUIDES/PAGINATION.md + GUIDES/RATE_LIMITING.md
└─ Erro nos modelos: DOCUMENTATION/ARCHITECTURE.md (sessão dados)
```

---

## 📊 STATUS DO PROJETO

| Componente | Status | Última Atualização |
|-----------|--------|-------------------|
| Modelos de Dados | ✅ Completo | 2026-04-07 |
| Services | ✅ Operacional | 2026-04-07 |
| Views | ✅ 100% | 2026-04-07 |
| Autenticação | ✅ Funcional | 2026-04-07 |
| Testes | ✅ 87.5%+ | 2026-04-07 |
| Documentação | ✅ Completa | 2026-04-07 |
| Produção | 🟢 PRONTO | 2026-04-07 |

---

## 🔗 REFERÊNCIA RÁPIDA

### Configuração Inicial
```bash
# 1. Ativar ambiente
.\venv\Scripts\Activate.ps1

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar .env
cp .env.example .env
# Editar .env com suas credenciais

# 4. Rodarmigrations
python manage.py migrate

# 5. Criar superuser
python manage.py createsuperuser

# 6. Rodar servidor
python manage.py runserver
```

### Comandos Comuns
```bash
# Testes
python tests/test_business_flow.py

# Desenvolvimento
python manage.py runserver --settings=ProjetoDevolucao.settings

# Admin
# → http://localhost:8000/admin/

# Logs
tail -f logs/app.log
```

---

## 📞 SUPORTE

| Dúvida | Onde Procurar |
|--------|---------------|
| "Como faço X?" | DOCUMENTATION/DEVELOPMENT.md e GUIDES/* |
| "Como a arquitetura funciona?" | DOCUMENTATION/ARCHITECTURE.md |
| "Qual é a estrutura?" | Aqui no INDEX.md! |
| "Histórico de testes" | ARCHIVE/TEST_*/* |
| "Como usar service X?" | GUIDES/SERVICES.md |
| "Como logar?" | GUIDES/LOGGING.md |

---

## 🎓 ROTEIROS RECOMENDADOS

### Para Novo Dev (Semana 1)
1. **Dia 1:** QUICK_START.md → Rodar e explorar
2. **Dia 2:** DOCUMENTATION/VISUAL_GUIDE.md → Entender fluxos
3. **Dia 3:** DOCUMENTATION/ARCHITECTURE.md → Detalhes técnicos
4. **Dia 4:** DOCUMENTATION/DEVELOPMENT.md → Padrões de código
5. **Dia 5:** Implementar primeira feature pequena

### Para Feature Complexa
1. Ler DOCUMENTATION/ARCHITECTURE.md (sessão relevante)
2. Ler DOCUMENTATION/DEVELOPMENT.md
3. Consultar GUIDES/ conforme necessário
4. Executar testes relacionados em `tests/`
5. Verificar histórico em ARCHIVE/TEST_* se similar

### Para Manutenção/Debugging
1. Procurar em GUIDES/ pela infraestrutura em questão
2. Consultar ARCHIVE/TEST_* para cenários históricos
3. Validar com testes em `tests/`
4. Atualizar documentação se necessário

---

## ✨ ÚLTIMAS MUDANÇAS (2026-04-07)

- ✅ Reorganização completa de estrutura
- ✅ Consolidação de documentação
- ✅ Testes organizados em pasta centralizada
- ✅ Remoção de arquivos obsoletos
- ✅ Criação deste INDEX.md centralizador

---

**Última Atualização:** 7 de Abril de 2026  
**Status:** 🟢 Sistema Operacional - Pronto para Produção
