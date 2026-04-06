# Service Layer - Guia de Integração

## ✅ Estrutura Implementada

### Serviços Disponíveis

#### 1. **PrazoService**
Cálculos de prazo de devolução

```python
from devolucao.services import PrazoService

# Calcular se prazo expirou
expirado, dias_restantes = PrazoService.calcular_expirado_e_dias(nota)
if expirado:
    print(f'Prazo expirou! Restavam {dias_restantes} dias')

# Validar (levanta ValidationError se expirado)
try:
    PrazoService.validar_prazo(nota)
except ValidationError as e:
    messages.error(request, str(e))
```

---

#### 2. **ClienteService**
Operações com clientes

```python
from devolucao.services import ClienteService

# Buscar por documento (CPF ou CNPJ)
cliente = ClienteService.buscar_por_documento('123.456.789-01')

# Verificar propriedade (segurança)
try:
    ClienteService.verificar_propriedade(request.user, cliente)
except ValidationError:
    return JsonResponse({'erro': 'Acesso negado'}, status=403)
```

---

#### 3. **NotaService**
Operações com notas fiscais

```python
from devolucao.services import NotaService

# Buscar notas válidas do cliente
notas = NotaService.buscar_notas_cliente(cliente, filtrar_expiradas=True)

# Calcular saldo disponível para devolução
saldo = NotaService.calcular_saldo_produto(nota, produto)
disponivel = saldo['disponivel']
```

---

#### 4. **DevolutionService**
Criação e validação de devoluções

```python
from devolucao.services import DevolutionService
from django.core.exceptions import ValidationError

try:
    # Validar antes de criar
    DevolutionService.validar_produtos(nota, produtos_data)
    DevolutionService.validar_motivos(produtos_data)

    # Criar devolução (com transação atômica)
    devolucao = DevolutionService.criar_devolucao(
        nota=nota,
        produtos_data=produtos_data,
        usuario_id=request.user.id,
        request_files=request.FILES
    )

    messages.success(request, f'Devolução #{devolucao.pk} criada!')

except (ValidationError, ValueError) as e:
    messages.error(request, str(e))
```

---

## 📋 Próximos Passos de Integração

1. **Refatorar `buscar_cliente()`**
   - Usar `ClienteService.buscar_por_documento()`
   - Usar `ClienteService.verificar_propriedade()`

2. **Refatorar `buscar_notas_cliente()`**
   - Usar `NotaService.buscar_notas_cliente()`
   - Usar `PrazoService.calcular_expirado_e_dias()` para cada nota

3. **Refatorar `_handle_enviar()`**
   - Usar `DevolutionService.criar_devolucao()`
   - Remover duplicação de validação

4. **Adicionar testes**
   - Rodar: `python manage.py test devolucao.tests`
   - Ver exemplos em `tests.py`

---

## 🧪 Exemplo: Refatorar uma view

### ANTES:
```python
def buscar_cliente(request):
    documento = request.GET.get('documento', '')

    try:
        if len(documento) == 11:
            cliente = Cliente.objects.get(cpf=documento)
        else:
            cliente = Cliente.objects.get(cnpj=documento)
    except Cliente.DoesNotExist:
        return JsonResponse({'encontrado': False})

    # ... resto do código
```

### DEPOIS:
```python
from devolucao.services import ClienteService
from devolucao.logging_utils import log_action

def buscar_cliente(request):
    documento = request.GET.get('documento', '')

    cliente = ClienteService.buscar_por_documento(documento)
    if not cliente:
        return JsonResponse({'encontrado': False})

    log_action('cliente.buscado',
        documento=documento[:4] + '***',
        usuario_id=request.user.id
    )

    # ... resto do código
```

---

## ✅ Benefícios Alcançados

| Benefício | Antes | Depois |
|-----------|-------|--------|
| **Testabilidade** | Precisa HttpRequest | Testa direto |
| **Reutilização** | Lógica em views | Classes reutilizáveis |
| **Manutenção** | 725 linhas em views | Separado em services |
| **Documentação** | Implícita | Docstrings claras |
| **Logging** | Nenhum | Integrado via logging_utils |

---

## 🧪 Rodando Testes

```bash
# Ver quais testes existem
python manage.py test devolucao.tests -v 2

# Rodar todos
python manage.py test devolucao.tests

# Rodar um teste específico
python manage.py test devolucao.tests.PrazoServiceTestCase.test_validar_prazo_expirado_sobe_erro
```

---

## 🎯 Checklist para Próxima Sessão

- [ ] Integrar ClienteService em `buscar_cliente()`
- [ ] Integrar NotaService em `buscar_notas_cliente()`
- [ ] Integrar DevolutionService em `_handle_enviar()`
- [ ] Adicionar logging em pontos críticos
- [ ] Executar testes: `python manage.py test devolucao`
- [ ] Reduzir views.py de 725 → ~400 linhas

---

## 📚 Referências

- Services: `devolucao/services.py`
- Testes: `devolucao/tests.py`
- Logging: `devolucao/logging_utils.py`
- Guia Logging: `LOGGING_SETUP.md`
