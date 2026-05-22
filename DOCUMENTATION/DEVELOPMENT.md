# DOCUMENTATION: GUIA DE DESENVOLVIMENTO

Veja este guia para entender como adicionar novas features ao projeto.

## Ciclo de Desenvolvimento

### Passo 1: Planejar

Antes de codificar:

```
☐ Objetivo: Adicionar nova feature? Bug fix? Refactoring?
  └─ Exemplo: "Permitir que admin marque devoluções como concluídas"

☐ Modelos afetados: Quais tabelas?
  └─ Exemplo: Devolucao (novo campo: data_conclusao)

☐ Views/Endpoints: Quais URLs?
  └─ Exemplo: POST /admin/devolucao/<id>/marcar-concluido/

☐ Testes: Como validar?
  └─ Exemplo: Testar transição de status pendente → concluído

☐ Documentação: Qual é o fluxo?
  └─ Exemplo: Adicionar docstring
```

### Passo 2: Criar Branch

```bash
git checkout -b feature/seu-recurso
# Exemplo: feature/marcar-devolucao-concluida
```

### Passo 3: Fazer Mudanças

#### A. Adicionar Model (se necessário)

```python
# devolucao/models.py
class Devolucao(models.Model):
    # ... campos existentes ...
    data_conclusao = models.DateTimeField(
        null=True, blank=True,
        db_column='dt_conclusao'
    )
```

#### B. Criar Migração

```bash
python manage.py makemigrations devolucao
python manage.py migrate
```

#### C. Adicionar Service

```python
# devolucao/services.py
class DevolutionService:
    @staticmethod
    def marcar_concluida(devolucao_id, usuario):
        """Marca uma devolução como concluída."""
        devolucao = Devolucao.objects.get(id=devolucao_id)
        
        if devolucao.status != 'em_processo':
            raise StatusInvalidoError(...)
        
        if not usuario.is_staff:
            raise PermissaoNegadaError(...)
        
        devolucao.status = 'concluido'
        devolucao.data_conclusao = timezone.now()
        devolucao.save()
        return devolucao
```

#### D. Adicionar View

```python
# devolucao/views.py
@require_POST
@staff_member_required
def marcar_devolucao_concluida(request, devolucao_id):
    """POST /admin/devolucao/<id>/marcar-concluido/"""
    try:
        devolucao = DevolutionService.marcar_concluida(
            devolucao_id=devolucao_id,
            usuario=request.user
        )
        log_event('devolucao.marcada_concluida', {
            'devolucao_id': devolucao.id,
            'usuario_id': request.user.id,
        })
        return JsonResponse({'success': True})
    except StatusInvalidoError as e:
        return JsonResponse({'error': str(e)}, status=400)
```

#### E. Adicionar URL

```python
# devolucao/urls.py
urlpatterns = [
    path('admin/devolucao/<int:devolucao_id>/marcar-concluido/',
         views.marcar_devolucao_concluida,
         name='marcar_devolucao_concluida'),
]
```

#### F. Adicionar Testes

```python
# devolucao/tests.py
class TestMarcarDevolucaoConcluida(TestCase):
    def test_marcar_com_sucesso(self):
        """Marcar como concluída com sucesso."""
        admin = Usuario.objects.create_superuser(...)
        devolucao = Devolucao.objects.create(status='em_processo', ...)
        
        self.client.login(...)
        response = self.client.post(f'/admin/devolucao/{devolucao.id}/...')
        
        self.assertEqual(response.status_code, 200)
        devolucao.refresh_from_db()
        self.assertEqual(devolucao.status, 'concluido')
```

### Passo 4: Testar

```bash
python manage.py test devolucao.tests.TestMarcarDevolucaoConcluida -v 2
```

### Passo 5: Commit

```bash
git add .
git commit -m "Feature: Permitir marcar devoluções como concluídas"
```

### Passo 6: Pull Request

```bash
git push origin feature/seu-recurso
# Abrir PR no GitHub/GitLab
```

---

## ✅ Checklist de Código

Antes de submeter PR, verifique:

### Código

- [ ] Segue padrões do projeto
- [ ] Usa Service Layer (sem lógica em view)
- [ ] Tem try/except apropriado
- [ ] Loga eventos importantes
- [ ] Formatado (4 espaços de indentação)

### Banco de Dados

- [ ] Nova migração criada
- [ ] Migração testada
- [ ] Índices adicionados (se necessário)

### Testes

- [ ] Testes unitários escritos
- [ ] Testes passando `python manage.py test`
- [ ] Coverage > 80%

### Documentação

- [ ] Docstrings adicionados
- [ ] README atualizado (se necessário)
- [ ] Commits com mensagens claras

### Segurança

- [ ] Validação de entrada (não confiar em request)
- [ ] CSRF token em forms
- [ ] @login_required / @staff_member_required (se necessário)
- [ ] Sem credenciais em código

### Performance

- [ ] Sem N+1 queries
- [ ] select_related() / prefetch_related() (se necessário)
- [ ] Paginação para listas grandes

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
```

---

## 📚 Referências Rápidas

### Imports Comuns

```python
from django.db import models, transaction
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from devolucao.logging_utils import log_event
```

### Comandos Úteis

```bash
# Verificar problemas syntax
python manage.py check

# Verificar migrações
python manage.py showmigrations

# Listar URLs
python manage.py show_urls
```

---

**Status:** 🟢 Pronto para contribuições  
**Última atualização:** 7 de Abril de 2026
