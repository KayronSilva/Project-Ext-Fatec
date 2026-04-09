# Rate Limiting - Guia de Integração

## ✅ O que foi Implementado

### Arquivo: `devolucao/rate_limiting.py`

Decorators pré-configurados para proteção contra abuso:

```python
@protect_buscar_cliente      # 60/hora
@protect_buscar_notas        # 120/hora
@protect_buscar_itens        # 120/hora
@protect_perfil_get          # 30/hora
@protect_perfil_save         # 10/hora
```

---

## 📋 Integração em 3 Passos

### PASSO 1: Importar decorators

No topo de `devolucao/views.py`:

```python
from devolucao.rate_limiting import (
    protect_buscar_cliente,
    protect_buscar_notas,
    protect_buscar_itens,
    protect_perfil_get,
    protect_perfil_save,
)
```

---

### PASSO 2: Adicionar aos endpoints AJAX

#### Exemplo 1: Proteger `buscar_cliente()`

**ANTES:**
```python
@login_required
def buscar_cliente(request):
    documento = request.GET.get('documento', '')
    # ... resto do código
```

**DEPOIS:**
```python
@protect_buscar_cliente
@login_required
def buscar_cliente(request):
    documento = request.GET.get('documento', '')
    # ... resto do código
```

#### Exemplo 2: Proteger `buscar_notas_cliente()`

```python
@protect_buscar_notas
@login_required
def buscar_notas_cliente(request):
    # ... resto do código
```

#### Exemplo 3: Proteger atualização de perfil

```python
@protect_perfil_save
@login_required
def perfil_salvar(request):
    # ... validação e salvamento
```

---

## 🧪 Teste Rate Limiting

### Manual (em desenvolvimento)

```bash
# Terminal 1: Iniciar servidor
python manage.py runserver

# Terminal 2: Fazer requisições
for i in {1..65}; do
    curl "http://localhost:8000/ajax/buscar-cliente/?documento=12345678901"
done

# A 61ª requisição retornará: "429 Too Many Requests"
```

---

## 📊 Padrão de Resposta

### Request dentro do limite (200)

```json
{
    "encontrado": true,
    "tipo": "PF",
    "nome": "João Silva"
}
```

### Request excedendo limite (429)

```json
{
    "detail": "Request was throttled. Expected available in 3600s."
}
```

---

## ⚙️ Configurações Recomendadas

| Endpoint | Limite | Razão |
|----------|--------|-------|
| buscar_cliente | 60/h | Evita enumeration de clientes |
| buscar_notas | 120/h | Menos crítico, mais tráfego |
| buscar_itens | 120/h | Idem |
| perfil_get | 30/h | Perfil é sensitivo |
| perfil_save | 10/h | Crítico: máx 10 updates/h |

---

## 🎯 Proteção Oferecida

### Cenário 1: DoS (Negação de Serviço)

**Sem Rate Limiting:**
```
Atacante: 10.000 req/s
→ Servidor congela
→ Usuários legítimos fora do ar
```

**Com Rate Limiting:**
```
Atacante: 10.000 req/s
→ Apenas 60 aceitas por hora
→ Resto retorna 429
→ Servidor responsivo
```

### Cenário 2: Enumeration de Clientes

**Sem Rate Limiting:**
```
Atacante descobre CPFs válidos:
GET /?documento=10000000001 → 404
GET /?documento=10000000002 → 200
... (infinitas tentativas)
```

**Com Rate Limiting:**
```
Apenas 60 buscas/hora
→ Impraticável enumerar milhões de documentos
```

### Cenário 3: Força Bruta

**Sem Rate Limiting:** 1000 updates/s possível  
**Com Rate Limiting:** 10 updates/h apenas

---

## 🔧 Customizar Limites

### Opção A: Em `rate_limiting.py`

```python
RATE_LIMITS = {
    'buscar_cliente': '30/h',      # Reduzido
    'buscar_notas_cliente': '60/h',
}
```

### Opção B: Decorator customizado

```python
from devolucao.rate_limiting import rate_limit_ajax

@rate_limit_ajax('100/h')  # Custom
@login_required
def meu_endpoint(request):
    ...
```

---

## 🔒 Boas Práticas

### ✅ DO (Faça)

```python
# Limitar leitura (GET)
@protect_buscar_cliente
@login_required
def buscar_cliente(request):
    ...

# Limitar escrita (POST) ainda mais
@rate_limit_write('5/h')
@login_required
def criar_algo(request):
    ...

# Logar exceções
try:
    resultado = operacao()
except Exception as e:
    log_error('operation.failed', error=e)
```

### ❌ DON'T (Não faça)

```python
# NÃO: Rate limiting muito frouxo
@rate_limit_ajax('10000/h')  # Inútil!
def buscar_cliente(request):
    ...

# NÃO: Sem proteção em endpoints críticos
def perfil_salvar(request):  # Sem @protect!
    ...
```

---

## ✅ Checklist de Implementação

- [ ] Lido `devolucao/rate_limiting.py`
- [ ] Importado decorators
- [ ] Adicionado `@protect_*` a endpoints AJAX
- [ ] Testado em desenvolvimento
- [ ] Verificado que 429 é retornado ao exceder
- [ ] Verificado que usuários legítimos não são afetados
- [ ] Commit das mudanças

---

**Status**: ✅ Ready to integrate  
**Tempo**: ~15-20 minutos  
**Complexidade**: Baixa  
**ROI**: Alto (segurança imediata)
