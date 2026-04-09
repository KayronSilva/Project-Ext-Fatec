# DOCUMENTAÇÃO: ARQUITETURA COMPLETA

Este arquivo foi consolidado a partir de `GUIA_COMPLETO.md` e `GUIA_DESENVOLVIMENTO.md`.

## Visão Geral

**Projeto Devolução** é uma aplicação Django de gerenciamento de devoluções de produtos. Permite que clientes (pessoas físicas ou jurídicas) façam solicitações de devolução de itens em notas fiscais, com prazos controláveis e auditoria completa.

### Características Principais

✅ **Autenticação via Email** — Sistema de login/cadastro customizado  
✅ **Suporte Duplo** — Pessoas Físicas (CPF) e Jurídicas (CNPJ)  
✅ **Validação Rigorosa** — Algoritmos certificados de CPF e CNPJ  
✅ **Notas Fiscais** — Integração com NF-e, cálculo de prazos  
✅ **Logging Estruturado** — Auditoria em JSON, rastreamento completo  
✅ **Rate Limiting** — Proteção contra abuso de AJAX  
✅ **Paginação** — Queries otimizadas para grandes volumes  
✅ **Admin Django** — Gerenciar dados via painel administrativo  

---

## 🏗️ Arquitetura do Projeto

### Padrão MVC + Service Layer

```
┌─────────────────────────────────────────────────────────┐
│          CAMADA DE VISUALIZAÇÃO (Templates)            │
│  (acompanhar_devolucoes.html, devolucao.html, etc)    │
└────────────────────┬────────────────────────────────────┘
                     │ (HTTP)
                     ▼
┌─────────────────────────────────────────────────────────┐
│      CAMADA DE CONTROLE (Views)                         │
│  (devolucao/views.py - login, cadastro, buscar, etc)   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│    CAMADA DE NEGÓCIO (Services)                         │
│  (ClienteService, NotaService, PrazoService, etc)       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│    CAMADA DE PERSISTÊNCIA (Modelos)                     │
│  (Usuario, Cliente, NotaFiscal, Devolucao, etc)         │
└────────────────────┬────────────────────────────────────┘
                     │ ORM
                     ▼
┌─────────────────────────────────────────────────────────┐
│        BANCO DE DADOS (MySQL)                           │
│  (tb_usuario, tb_cliente, tb_notafiscal, etc)          │
└─────────────────────────────────────────────────────────┘
```

### Estrutura de Diretórios

```
devolucao/
├─ models.py              ← 12 modelos de dados
├─ views.py               ← 45+ endpoints
├─ urls.py                ← Roteamento
├─ forms.py               ← Validação de formulários
├─ services.py            ← Lógica de negócio
├─ decorators.py          ← Decorators customizados
├─ logging_utils.py       ← Logging estruturado
├─ pagination_service.py  ← Paginação otimizada
├─ rate_limiting.py       ← Rate limiting
├─ sankhya_api.py         ← ERP integration
├─ importacao_service.py  ← XML/ERP import
├─ admin.py               ← Admin Django
│
├─ migrations/            ← Schema migrations
├─ static/                ← CSS, JS
└─ templates/             ← HTML templates
```

---

## 🔄 Fluxo de Dados

### 1. Criação de Devolução

```
Usuário Preenche Form
    ↓
Valida CSRF Token
    ↓
Verifica Autenticação @login_required
    ↓
Rate Limiting @ratelimit
    ↓
DevolucaoForm.is_valid() → Valida campos
    ↓
@transaction.atomic() → Transação segura
    ├─ Valida Prazo (não expirado)
    ├─ Valida Quantidades (saldo disponível)
    ├─ Valida Motivo (enumeration válida)
    ├─ Processa Arquivos (fotos, PDF)
    ├─ Cria Devolucao no BD (INSERT)
    ├─ Cria ItemDevolucao (FOREACH items)
    └─ COMMIT ou ROLLBACK
    ↓
Logging: logging_utils.log_event()
    ↓
JsonResponse( {success: true, devolucao_id: 42} )
    ↓
JavaScript Redireciona para Dashboard
```

### 2. Busca de Cliente (AJAX)

```
Frontend: CPF/CNPJ → POST /ajax/buscar-cliente/
    ↓
rate_limit_ajax (60/hora)
    ↓
ClienteService.buscar_por_documento()
    ├─ Extrai apenas dígitos
    ├─ Query: Cliente.objects.filter(cpf= ou cnpj=)
    └─ Valida CPF/CNPJ
    ↓
JSON Response: {nome, email, tipo, ...}
    ↓
Frontend: Renderiza dados na página
```

### 3. Busca de Notas (AJAX)

```
Frontend: POST /ajax/buscar-notas-cliente/
    ↓
NotaService.buscar_notas_cliente(cliente)
    ├─ Query: NotaFiscal.objects.filter(cliente=)
    └─ Para cada nota:
        ├─ PrazoService.calcular_prazo()
        │  ├─ data_emissão + 30 dias = data_limite
        │  └─ Hoje > data_limite? → "EXPIRADA"
        └─ Retorna status "DISPONÍVEL" ou "EXPIRADA"
    ↓
JSON Response: [{numero, data, dias_restantes, ...}]
    ↓
Frontend: Renderiza tabela de notas
```

---

## 📋 Padrões de Desenvolvimento

### ✅ Usar Service Layer

```python
# Lógica em service, view delega
@login_required
def criar_devolucao(request):
    resultado = DevolutionService.criar(
        cliente_id=request.POST['cliente_id'],
        nota_id=request.POST['nota_id'],
        ...
    )
    return JsonResponse(resultado)
```

### ✅ Usar Transações

```python
@transaction.atomic
def criar_devolucao(...):
    devolucao = Devolucao.objects.create(...)
    for item in itens:
        ItemDevolucao.objects.create(...)
    # Se erro, tudo é revertido
```

### ✅ Validar Entrada

```python
if motivo not in MOTIVOS_VALIDOS:
    raise ValueError(f"Motivo inválido: {motivo}")
```

### ✅ Logar Eventos

```python
log_event('devolucao.criada', {
    'usuario_id': user.id,
    'devolucao_id': dev.id,
    'itens': len(items),
})
```

### ✅ Usar Docstrings

```python
def criar_devolucao(cliente_id, nota_id):
    """
    Cria nova devolução com validações.
    
    Args:
        cliente_id: ID do cliente
        nota_id: ID da nota fiscal
    
    Returns:
        Devolucao criada
    
    Raises:
        PrazoExpiradoError: Se prazo venceu
        QuantidadeIndisponível: Se saldo insuficiente
    """
    ...
```

---

## 🧪 Adicionando Nova Feature

### PASSO 1: Planejar

```
☐ Objetivo: O que você está implementando?
☐ Modelos afetados: Quais tabelas?
☐ Views/Endpoints: Quais URLs?
☐ Testes: Como validar?
☐ Documentação: Qual é o fluxo?
```

### PASSO 2: Criar Branch

```bash
git checkout -b feature/seu-recurso
```

### PASSO 3: Implementar Model

```python
class MeuModelo(models.Model):
    campo = models.CharField(max_length=100, db_column='coluna_bd')
    
    class Meta:
        db_table = 'tb_meu_modelo'
        verbose_name = 'Meu Modelo'
```

### PASSO 4: Criar Migração

```bash
python manage.py makemigrations devolucao
python manage.py migrate
```

### PASSO 5: Adicionar Service

```python
class MeuService:
    @staticmethod
    def fazer_algo(param1, param2):
        """Descrição clara."""
        resultado = calcular(param1)
        return resultado
```

### PASSO 6: Adicionar View

```python
@login_required
def meu_endpoint(request):
    resultado = MeuService.fazer_algo(...)
    log_event('meu_evento', {'info': resultado})
    return JsonResponse({'success': True})
```

### PASSO 7: Adicionar URL

```python
urlpatterns = [
    path('meu-endpoint/', views.meu_endpoint, name='meu'),
]
```

### PASSO 8: Escrever Testes

```python
class TestMeuModelo(TestCase):
    def test_criar_com_sucesso(self):
        obj = MeuModelo.objects.create(campo='valor')
        self.assertEqual(obj.campo, 'valor')
```

### PASSO 9: Commit & PR

```bash
git add .
git commit -m "Feature: Descrição da feature"
git push origin feature/seu-recurso
# Abrir Pull Request
```

---

## ✅ Checklist de PR

- [ ] Segue padrões do projeto
- [ ] Usa Service Layer
- [ ] Tem try/except apropriado
- [ ] Loga eventos importantes
- [ ] Novos testes escritos e passando
- [ ] Docstrings adicionados
- [ ] Sem credenciais em código
- [ ] CSRF token em forms
- [ ] sem N+1 queries
- [ ] Suporte a paginação (se necessário)

---

## 📚 Referências

- Veja [GUIDES/SERVICES.md](../GUIDES/SERVICES.md) para usar services
- Veja [GUIDES/LOGGING.md](../GUIDES/LOGGING.md) para logging
- Veja [GUIDES/PAGINATION.md](../GUIDES/PAGINATION.md) para paginação
- Veja [GUIDES/RATE_LIMITING.md](../GUIDES/RATE_LIMITING.md) para rate limiting

---

**Status:** 🟢 Pronto para desenvolvimento  
**Última atualização:** 7 de Abril de 2026
