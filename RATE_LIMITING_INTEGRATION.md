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

No topo de `devolucao/views.py`, adicione:

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
    echo ""
done

# A 61ª requisição retornará: "429 Too Many Requests"
```

### Com Python

```python
import requests
from time import sleep

# Fazer 61 requisições
for i in range(61):
    resp = requests.get(
        'http://localhost:8000/ajax/buscar-cliente/',
        params={'documento': '12345678901'},
        headers={'Authorization': 'Bearer seu_token'}
    )

    if resp.status_code == 429:
        print(f'Rate limit atingido na requisição {i+1}!')
        print(resp.json())
        break
    elif i % 10 == 0:
        print(f'Requisição {i+1}: OK')
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

### Headers de Resposta

```
X-RateLimit-Limit: 60        # Limite total
X-RateLimit-Remaining: 45    # Requisições restantes
X-RateLimit-Reset: 1646409600 # Timestamp quando reseta
```

---

## ⚙️ Configurações Recomendadas

| Endpoint | Limite | Razão |
|----------|--------|-------|
| buscar_cliente | 60/h | Evita enumeration de clientes |
| buscar_notas | 120/h | Menos crítico, mais tráfego esperado |
| buscar_itens | 120/h | Idem |
| perfil_get | 30/h | Perfil é sensitivo |
| perfil_save | 10/h | Crítico: máx 10 updates/hora |

---

## 🎯 Proteção Oferecida

### Cenário 1: DoS (Negação de Serviço)

**Sem Rate Limiting:**
```
Atacante faz 10.000 req/s
→ Servidor congela
→ Usuários legítimos não conseguem usar
```

**Com Rate Limiting:**
```
Atacante faz 10.000 req/s
→ Apenas 60 são aceitas por hora
→ Resto retorna 429
→ Servidor permanece responsivo
```

### Cenário 2: Enumeration de Clientes

**Sem Rate Limiting:**
```
Atacante pode descobrir todos os CPFs válidos:
GET /ajax/buscar-cliente/?documento=10000000001 → 404
GET /ajax/buscar-cliente/?documento=10000000002 → 200
... (infinitas tentativas)
```

**Com Rate Limiting:**
```
Atacante limitado a 60 buscas/hora
→ Impraticável enumerar milhões de documentos
```

### Cenário 3: Força Bruta em Perfil

**Sem Rate Limiting:**
```
Atacante tenta 1000 updates/s ao perfil
→ Spam massivo
```

**Com Rate Limiting:**
```
Apenas 10 updates/hora aceitos
→ Impossível fazer spam em escala
```

---

## 🔧 Customizar Limites

### Opção A: Modificar em `rate_limiting.py`

```python
RATE_LIMITS = {
    'buscar_cliente': '30/h',      # Reduzido para 30
    'buscar_notas_cliente': '60/h', # Reduzido para 60
}
```

### Opção B: Usar decorator customizado

```python
from devolucao.rate_limiting import rate_limit_ajax

@rate_limit_ajax('100/h')  # Custom: 100 por hora
@login_required
def meu_endpoint(request):
    ...
```

### Opção C: Rate limiting por IP (em vez de usuário)

```python
from devolucao.rate_limiting import rate_limit_ajax

@rate_limit_ajax('1000/h', key='ip')  # Por IP, não por usuário
@login_required
def publico_endpoint(request):
    ...
```

---

## 🚨 Comportamento em Desenvolvimento

### DEBUG=True (Desenvolvimento)

Rate limiting funciona normalmente, mas útil para testar.

### DEBUG=False (Produção)

Rate limiting SEMPRE ativo. **Recomendado**: aumentar limites se houver tráfego legítimo alto.

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
@rate_limit_write('5/h')  # Apenas 5 por hora
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
def perfil_salvar(request):  # Sem @protect_perfil_save!
    ...

# NÃO: Limites iguais para leitura e escrita
# Escrita deveria ter limite muito menor
@protect_buscar_cliente  # 60/h é OK
@protect_perfil_save     # 10/h é muito baixo para escrita frequente
```

---

## 📚 Próximas Melhorias

Após integrar Rate Limiting:

1. **Monitorar Rate Limiting**
   - Adicionar métricas em logs
   - Alertar se muitos usuários chegam ao limite
   - Aumentar limites se tráfego for legítimo mas alto

2. **Cache em Rate Limiting**
   - Django-ratelimit usa cache por padrão
   - Configurar Redis para rate limiting distribuído (em múltiplos servidores)

3. **Customizar Mensagem de Erro**
   - Retornar mensagem amigável em português
   - Link para documentação de API

---

## ✅ Checklist de Implementação

- [ ] Lido `devolucao/rate_limiting.py`
- [ ] Importado decorators em `views.py`
- [ ] Adicionado `@protect_*` a todos endpoints AJAX
- [ ] Testado em desenvolvimento (curl ou Python requests)
- [ ] Verificado que 429 é retornado ao exceder limite
- [ ] Verificado que usuários legítimos não são afetados
- [ ] Commit das mudanças

---

## 🆘 Troubleshooting

### Problema: "Sempre recebo 429 mesmo primeira requisição"

**Solução**: Verificar cache (Redis/Memcached)
```bash
# Limpar cache
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

### Problema: "Rate limiting não está funcionando"

**Solução**: Verificar que decorator está **acima** de @login_required
```python
# CERTO: rate limit ACIMA
@protect_buscar_cliente
@login_required
def buscar_cliente(request):
    ...

# ERRADO: rate limit ABAIXO
@login_required
@protect_buscar_cliente
def buscar_cliente(request):
    ...
```

### Problema: "Usuários reclamam que limite é muito baixo"

**Solução**: Aumentar em RATE_LIMITS
```python
RATE_LIMITS = {
    'buscar_cliente': '120/h',  # Aumentado de 60
}
```

---

## 📈 Impacto Esperado

| Métrica | Sem Rate Limit | Com Rate Limit |
|---------|---|---|
| **Requisições DoS máx/s** | 10.000+ | ~20 (60/h) |
| **Enumeration CPFs/dia** | Infinito | ~1.440 |
| **CPU durante ataque** | 100% | <5% |
| **Usuários legítimos afetados** | Sim | Não |

---

**Status**: ✅ Ready to integrate
**Tempo de integração**: ~15-20 minutos
**Complexidade**: Baixa
**ROI**: Alto (segurança imediata)
