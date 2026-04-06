# 🛠️ GUIA DE DESENVOLVIMENTO - ADICIONAR NOVAS FEATURES

## Índice
1. [Estrutura de Arquivo](#estrutura-de-arquivo)
2. [Ciclo de Desenvolvimento](#ciclo-de-desenvolvimento)
3. [Como Adicionar um Novo Endpoint](#como-adicionar-um-novo-endpoint)
4. [Como Adicionar um Novo Modelo](#como-adicionar-um-novo-modelo)
5. [Padrões de Código](#padrões-de-código)
6. [Checklist de Pull Request](#checklist-de-pull-request)

---

## 📁 Estrutura de Arquivo

Quando criar um novo recurso, mantenha a estrutura:

```
devolucao/
├─ models.py             ← Novos modelos aqui
├─ views.py              ← Novos endpoints aqui
├─ urls.py               ← Rotas aqui
├─ forms.py              ← Novos formulários aqui
├─ services.py           ← Lógica de negócio (NEW!)
├─ templates/            ← HTML dos endpoints
│  └─ novo_recurso.html
├─ static/
│  └─ js/novo_recurso.js
└─ migrations/           ← Mudanças de BD
   └─ 0005_novo_modelo.py
```

**Princípio:** Cada mudança deve seguir a arquitetura MVC + Service Layer.

---

## 🔄 Ciclo de Desenvolvimento

### Passo 1: Planejar

Antes de codificar, defina:

```
☐ Objetivo: O que você está implementando?
  ├─ Nova feature? Bug fix? Refactoring?
  └─ Exemplo: "Permitir que admin marque devoluções como concluídas"

☐ Modelos afetados: Quais tabelas?
  └─ Exemplo: Devolucao (novo campo: data_conclusao)

☐ Views/Endpoints: Quais URLs?
  └─ Exemplo: POST /admin/devolucao/<id>/marcar-concluido/

☐ Testes: Como validar?
  └─ Exemplo: Testar transição de status pendente → concluído

☐ Documentação: Qual é o fluxo?
  └─ Exemplo: Adicionar descrição no docstring
```

### Passo 2: Criar Branch

```bash
git checkout -b feature/seu-recurso
# Exemplo: feature/marcar-devolucao-concluida
```

### Passo 3: Fazer Mudanças

Veja exemplos abaixo.

### Passo 4: Testar Localmente

```bash
python manage.py test devolucao.tests.TestNovoRecurso
```

### Passo 5: Commit com Mensagem Clara

```bash
git add .
git commit -m "Feature: Permitir marcar devoluções como concluídas"
# Formato: [Feature/Fix/Refactor]: Descrição breve
```

### Passo 6: Push & Pull Request

```bash
git push origin feature/seu-recurso
# Abra PR no GitHub/GitLab
```

---

## 📝 Como Adicionar um Novo Endpoint

### Exemplo: Marcar Devolução como Concluída

#### PASSO 1: Adicionar Model (se necessário)

**Arquivo:** `devolucao/models.py`

```python
class Devolucao(models.Model):
    # ... campos existentes ...
    
    # NOVO CAMPO
    data_conclusao = models.DateTimeField(
        null=True, blank=True,
        db_column='dt_conclusao',
        help_text='Data quando foi concluída a devolução'
    )
```

#### PASSO 2: Criar Migração

```bash
python manage.py makemigrations devolucao
# Isso cria: devolucao/migrations/0005_devolucao_data_conclusao.py

python manage.py migrate
# Aplica a mudança no BD
```

#### PASSO 3: Adicionar Service (Lógica)

**Arquivo:** `devolucao/services.py`

```python
class DevolutionService:
    # ... métodos existentes ...
    
    @staticmethod
    def marcar_concluida(devolucao_id, usuario):
        """
        Marca uma devolução como concluída.
        
        Validações:
          - Status é 'em_processo'?
          - Usuário tem permissão?
        
        Retorna:
          - Devolucao atualizada
        
        Levanta:
          - StatusInvalidoError
          - PermissaoNegadaError
        """
        devolucao = Devolucao.objects.get(id=devolucao_id)
        
        # Validação 1: Status correto?
        if devolucao.status != 'em_processo':
            raise StatusInvalidoError(
                f"Não pode marcar como concluída. "
                f"Status atual: {devolucao.status}"
            )
        
        # Validação 2: Permissão?
        if not usuario.is_staff:
            raise PermissaoNegadaError("Apenas admin pode marcar como concluída")
        
        # Atualizar
        devolucao.status = 'concluido'
        devolucao.data_conclusao = timezone.now()
        devolucao.save()
        
        return devolucao
```

#### PASSO 4: Adicionar View (Endpoint)

**Arquivo:** `devolucao/views.py`

```python
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from devolucao.services import DevolutionService

@require_POST
@staff_member_required  # Apenas admin pode acessar
def marcar_devolucao_concluida(request, devolucao_id):
    """
    POST /admin/devolucao/<id>/marcar-concluido/
    
    Marca devolução como concluída.
    Apenas para admins.
    """
    try:
        devolucao = DevolutionService.marcar_concluida(
            devolucao_id=devolucao_id,
            usuario=request.user
        )
        
        # Logging
        log_event('devolucao.marcada_concluida', {
            'devolucao_id': devolucao.id,
            'usuario_id': request.user.id,
            'timestamp': timezone.now().isoformat()
        })
        
        return JsonResponse({
            'success': True,
            'devolucao_id': devolucao.id,
            'status': devolucao.status,
            'data_conclusao': devolucao.data_conclusao.isoformat()
        })
    
    except StatusInvalidoError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
    except PermissaoNegadaError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=403)
```

#### PASSO 5: Adicionar URL

**Arquivo:** `devolucao/urls.py`

```python
urlpatterns = [
    # ... rotas existentes ...
    
    # NOVO
    path('admin/devolucao/<int:devolucao_id>/marcar-concluido/',
         views.marcar_devolucao_concluida,
         name='marcar_devolucao_concluida'),
]
```

#### PASSO 6: Adicionar Template (se necessário)

**Arquivo:** `devolucao/templates/acompanhar_devolucoes.html`

Adicionar botão no template:

```html
<!-- Dentro da tabela de devoluções, na coluna de ações -->
<td>
    {% if devolucao.status == 'em_processo' and user.is_staff %}
        <button class="btn btn-success" 
                onclick="marcarConcluida({{ devolucao.id }})">
            ✓ Marcar Concluída
        </button>
    {% endif %}
</td>
```

Adicionar JavaScript:

```javascript
// Em devolucao/static/js/admin.js

function marcarConcluida(devolucaoId) {
    fetch(`/admin/devolucao/${devolucaoId}/marcar-concluido/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('✓ Devolução marcada como concluída!');
            location.reload();  // Recarregar página
        } else {
            alert('✗ Erro: ' + data.error);
        }
    })
    .catch(error => console.error('Erro:', error));
}
```

#### PASSO 7: Adicionar Testes

**Arquivo:** `devolucao/tests.py`

```python
class TestMarcarDevolucaoConcluida(TestCase):
    """Testes para marcar devolução como concluída."""
    
    def setUp(self):
        """Preparar dados de teste."""
        self.admin = Usuario.objects.create_superuser(
            email='admin@test.com',
            password='senha123'
        )
        
        self.cliente = Cliente.objects.create(
            tipo='PF',
            cpf='11111111111',
            nome='Teste User'
        )
        
        self.nota = NotaFiscal.objects.create(
            cliente=self.cliente,
            numero_nota='NF-001',
            data_emissao=date.today()
        )
        
        self.devolucao = Devolucao.objects.create(
            cliente=self.cliente,
            nota_fiscal=self.nota,
            usuario=self.admin,
            motivo='Danificado',
            status='em_processo'
        )
    
    def test_marcar_concluida_com_sucesso(self):
        """Teste: Marcar devolução como concluída."""
        self.client.login(email='admin@test.com', password='senha123')
        
        response = self.client.post(
            f'/admin/devolucao/{self.devolucao.id}/marcar-concluido/'
        )
        
        self.assertEqual(response.status_code, 200)
        self.devolucao.refresh_from_db()
        self.assertEqual(self.devolucao.status, 'concluido')
        self.assertIsNotNone(self.devolucao.data_conclusao)
    
    def test_marcar_concluida_usuario_nao_admin(self):
        """Teste: Usuário comum não pode marcar como concluída."""
        usuario_comum = Usuario.objects.create_user(
            email='user@test.com',
            password='senha123'
        )
        self.client.login(email='user@test.com', password='senha123')
        
        response = self.client.post(
            f'/admin/devolucao/{self.devolucao.id}/marcar-concluido/'
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        self.devolucao.refresh_from_db()
        self.assertEqual(self.devolucao.status, 'em_processo')  # Não mudou
    
    def test_marcar_concluida_status_invalido(self):
        """Teste: Não pode marcar como concluída se status ≠ em_processo."""
        self.devolucao.status = 'pendente'
        self.devolucao.save()
        
        self.client.login(email='admin@test.com', password='senha123')
        
        response = self.client.post(
            f'/admin/devolucao/{self.devolucao.id}/marcar-concluido/'
        )
        
        self.assertEqual(response.status_code, 400)  # Bad Request
        self.devolucao.refresh_from_db()
        self.assertEqual(self.devolucao.status, 'pendente')  # Não mudou
```

#### PASSO 8: Rodar Testes

```bash
python manage.py test devolucao.tests.TestMarcarDevolucaoConcluida -v 2

# Esperado:
# test_marcar_concluida_com_sucesso ... ok
# test_marcar_concluida_usuario_nao_admin ... ok
# test_marcar_concluida_status_invalido ... ok
#
# Ran 3 tests in 0.235s
# OK
```

---

## 📊 Como Adicionar um Novo Modelo

### Exemplo: Adicionar modelo de "Comentário" em Devoluções

#### PASSO 1: Definir Modelo

**Arquivo:** `devolucao/models.py`

```python
class ComentarioDevolucao(models.Model):
    """Comentários de admin em uma devolução."""
    
    devolucao = models.ForeignKey(
        Devolucao,
        on_delete=models.CASCADE,
        related_name='comentarios',
        db_column='id_devolucao'
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        db_column='id_usuario'
    )
    texto = models.TextField(
        db_column='texto_comentario',
        help_text='Comentário do admin sobre a devolução'
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        db_column='dt_criacao'
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        db_column='dt_atualizacao'
    )
    
    def __str__(self):
        return f'Comentário #{self.id} em Devolução #{self.devolucao.id}'
    
    class Meta:
        db_table = 'tb_comentario_devolucao'
        verbose_name = 'Comentário de Devolução'
        verbose_name_plural = 'Comentários de Devolução'
        ordering = ['-data_criacao']
        
        # Índice para performance
        indexes = [
            models.Index(fields=['devolucao', '-data_criacao']),
        ]
```

#### PASSO 2: Criar Migração

```bash
python manage.py makemigrations devolucao
# Cria: devolucao/migrations/0006_comentariodevolucao.py

python manage.py migrate
```

#### PASSO 3: Registrar no Admin (opcional)

**Arquivo:** `devolucao/admin.py`

```python
from django.contrib import admin
from .models import ComentarioDevolucao

class ComentarioDevolucaoInline(admin.TabularInline):
    """Exibir comentários inline na página de devolução."""
    model = ComentarioDevolucao
    extra = 1  # Um campo vazio para adicionar novo
    fields = ('usuario', 'texto', 'data_criacao', 'data_atualizacao')
    readonly_fields = ('data_criacao', 'data_atualizacao')

class DevolutionAdmin(admin.ModelAdmin):
    inlines = [ComentarioDevolucaoInline]
    list_display = ('id', 'cliente', 'status', 'data_criacao')

admin.site.register(Devolucao, DevolutionAdmin)
admin.site.register(ComentarioDevolucao)
```

---

## 📋 Padrões de Código

### ✅ DO: Usar Service Layer

```python
# ✓ CORRETO: Lógica em service, view delega
# views.py
@login_required
def criar_devolucao(request):
    resultado = DevolutionService.criar(
        cliente_id=request.POST.get('cliente_id'),
        ...
    )
    return JsonResponse(resultado)
```

### ❌ DON'T: Colocar lógica em View

```python
# ✗ ERRADO: Lógica espalhada na view
@login_required
def criar_devolucao(request):
    cliente = Cliente.objects.get(id=...)
    
    # Validação de prazo (isso deveria estar em service!!)
    nota = NotaFiscal.objects.get(...)
    prazo = nota.data_emissao + timedelta(days=30)
    if date.today() > prazo:
        raise Exception("Prazo expirado")
    
    # Criação (isso deveria estar em service!!)
    devolucao = Devolucao.objects.create(...)
    ...
```

### ✅ DO: Usar Transações

```python
# ✓ CORRETO: Tudo ou nada
@transaction.atomic
def criar_devolucao(...):
    devolucao = Devolucao.objects.create(...)
    for item in itens:
        ItemDevolucao.objects.create(...)
    # Se erro aqui, tudo é revertido
```

### ✅ DO: Logar Eventos Importantes

```python
# ✓ CORRETO: Auditoria completa
log_event('devolucao.criada', {
    'usuario_id': user.id,
    'devolucao_id': dev.id,
    'itens': len(items),
    'timestamp': timezone.now().isoformat()
})
```

### ✅ DO: Validar Entrada

```python
# ✓ CORRETO: Validação clara
if motivo not in MOTIVOS_VALIDOS:
    raise ValueError(f"Motivo '{motivo}' não é válido")
```

### ✅ DO: Usar Docstrings

```python
# ✓ CORRETO: Documentação clara
def marcar_concluida(devolucao_id):
    """
    Marca devolução como concluída.
    
    Args:
        devolucao_id: ID da devolução
    
    Returns:
        Devolucao atualizada
    
    Raises:
        StatusInvalidoError: Se status não é 'em_processo'
    """
    ...
```

### ✅ DO: Usar Type Hints

```python
# ✓ CORRETO: Types explícitos (Python 3.9+)
def buscar_cliente(documento: str) -> Optional[Cliente]:
    """Busca cliente por CPF ou CNPJ."""
    ...
```

### ✅ DO: Tratamento de Erro Específico

```python
# ✓ CORRETO: Erros específicos
try:
    devolucao = DevolutionService.criar(...)
except PrazoExpiradoError as e:
    return JsonResponse({'error': str(e)}, status=400)
except PermissaoNegadaError as e:
    return JsonResponse({'error': str(e)}, status=403)
except Exception as e:
    log_event('erro_nao_esperado', {'error': str(e)})
    return JsonResponse({'error': 'Erro interno'}, status=500)
```

---

## ✅ Checklist de Pull Request

Antes de submeter PR, verifique:

- [ ] **Código**
  - [ ] Segue padrões do projeto
  - [ ] Usa Service Layer (sem lógica em view)
  - [ ] Tem try/except apropriado
  - [ ] Loga eventos importantes
  - [ ] Código formatado (indentação 4 espaços)

- [ ] **Banco de Dados**
  - [ ] Nova migração criada (`makemigrations`)
  - [ ] Migração foi testada (`migrate`)
  - [ ] Índices adicionados (se necessário)
  - [ ] Sem operações bloqueantes

- [ ] **Testes**
  - [ ] Testes unitários escritos
  - [ ] Testes passando (`python manage.py test`)
  - [ ] Coverage > 80% (se possível)

- [ ] **Documentação**
  - [ ] Docstrings adicionados
  - [ ] README atualizado (se necessário)
  - [ ] Commits com mensagens claras

- [ ] **Segurança**
  - [ ] Validação de entrada (não confiar em request)
  - [ ] CSRF token em forms
  - [ ] @login_required / @staff_member_required (se necessário)
  - [ ] Sem credenciais em código

- [ ] **Performance**
  - [ ] Sem N+1 queries
  - [ ] select_related() / prefetch_related() (se necessário)
  - [ ] Paginação para listas grandes
  - [ ] Índices adicionados (if applicable)

**Exemplo de mensagem de commit:**

```
Feature: Marcar devoluções como concluídas

- Adiciona campo data_conclusao em Devolucao
- Adiciona service DevolutionService.marcar_concluida()
- Adiciona endpoint POST /admin/devolucao/<id>/marcar-concluido/
- Adiciona testes unitários (3/3 passando)
- Adiciona logging em JSON para auditoria

Fixes: #42 (número do issue, se existir)
```

---

## 🧪 Executar Testes

```bash
# Testes específicos
python manage.py test devolucao.tests.TestMarcarDevolucaoConcluida

# Todos os testes
python manage.py test devolucao

# Com cobertura
pip install coverage
coverage run --source='.' manage.py test devolucao
coverage report
coverage html  # Gera relatório HTML em htmlcov/
```

---

## 🔍 Verificar Qualidade

```bash
# Verificar problemas syntax
python manage.py check

# Verificar migrações
python manage.py showmigrations

# Listar URLs
python manage.py show_urls
```

---

## 📚 Referências Rápidas

### Imports Comuns

```python
# Models & ORM
from django.db import models, transaction
from django.db.models import Q, Sum, Count, F, Case, When, Value

# Views & Auth
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET

# Forms
from django import forms
from django.core.exceptions import ValidationError

# Utils
from django.utils import timezone
from django.conf import settings
from datetime import date, timedelta
import json

# Logging
from devolucao.logging_utils import log_event
```

### Validação Padrão

```python
# Email
from django.core.validators import EmailValidator

# CPF/CNPJ
from devolucao.models import validar_cpf, validar_cnpj

# Arquivo
from django.core.validators import FileExtensionValidator
```

---

**Última atualização:** 05 de março de 2026  
**Versão:** 1.0  
**Status:** 🟢 Pronto para contribuições
