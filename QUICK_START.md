# ⚡ QUICK START - 5 MINUTOS

## 🎯 Resumo de 30 Segundos

Sistema Django para gerenciar devoluções de produtos. Clientes fazem solicitações, admin aprova.

**Stack:** Django 4.2 + MySQL + Python 3.9+ + structlog

**Status:** ✅ Pronto para produção

---

## 🚀 Rodar em 5 Passos



```bash
# 1. Clonar ou abrir pasta
cd C:\Users\seu_usuario\Desktop\FATEC---PROJETO-EXT-MAIN

# 2. Ativar virtual environment
.\venv\Scripts\Activate.ps1

# 3. Instalar dependências (se primeira vez)
pip install -r requirements.txt

# 4. Configurar banco (se primeira vez)
# Edite .env com credenciais MySQL
# Depois: python manage.py migrate

# 5. RODAR SERVIDOR
python manage.py runserver

# Acesse: http://localhost:8000
```

---

## 📋 Checklist Primeiro Setup

#INSTALE O PYTHON, CRIE O AMBIENTE VIRTUAL, INSTALE O DJANGO
#INSTALE O MYSQL, CRIE UM BANCO CHAMADO devolucao, DEPOIS CONFIGURE O BANCO NO SETTINGS

- [ ] Python 3.9+ instalado (`python --version`)
- [ ] MySQL rodando (`mysql -u root -p`)
- [ ] `.\venv\Scripts\Activate.ps1` (venv ativado)
- [ ] `pip install -r requirements.txt` (dependências)
- [ ] `.env` criado com senhas reais
- [ ] Banco `devolucao` criado (`CREATE DATABASE devolucao`)
- [ ] `python manage.py migrate` (tabelas criadas)
- [ ] `python manage.py runserver` (servidor rodando)
- [ ] Login em http://localhost:8000 (funcionando ✓)

---

## 🔑 Acessos Iniciais

### Criar Admin (uma vez)
```bash
python manage.py createsuperuser
# Email: admin@example.com
# Senha: senhaSegura123
```

### Acessar Admin
```
http://localhost:8000/admin/
Email: admin@example.com
Senha: senhaSegura123
```

### Criar Cliente de Teste
1. Ir para `/cadastro` 
2. Email: `teste@example.com`
3. Senha: `senhaSegura123`
4. Pronto! Pode usar app

---

## 📂 Arquivos Principais

| Arquivo | O quê |
|---------|-------|
| `devolucao/models.py` | Base de dados (tabelas) |
| `devolucao/views.py` | Páginas e endpoints |
| `devolucao/services.py` | Lógica de negócio |
| `devolucao/urls.py` | Rotas |
| `ProjetoDevolucao/settings.py` | Configurações |
| `.env` | Senhas (secreto!) |

---

## ⚙️ Variáveis de Ambiente (`.env`)

```bash
# Copie de .env.example
copy .env.example .env

# Edite:
SECRET_KEY=sua-chave-secreta-64-caracteres
DEBUG=True  # False em produção
DATABASE_PASSWORD=sua_senha_mysql_real
```

---

## 🗄️ Banco de Dados

### Criar BD (primeira vez)
```bash
mysql -u root -p
mysql> CREATE DATABASE devolucao CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
mysql> EXIT;
```

### Aplicar mudanças
```bash
python manage.py migrate
```

### Resetar BD (cuidado!)
```bash
python manage.py migrate zero
python manage.py migrate
```

---

## 🧪 Testes

```bash
# Rodar todos
python manage.py test devolucao

# Teste específico
python manage.py test devolucao.tests.TestMarcarDevolucaoConcluida

# Com cobertura
pip install coverage
coverage run --source='.' manage.py test devolucao
coverage report
```

---

## 🐛 Problemas Comuns

### "Módulo não encontrado"
```bash
# Ativar venv
.\venv\Scripts\Activate.ps1

# Instalar deps
pip install -r requirements.txt
```

### "Connection refused" MySQL
```bash
# Verificar senha no .env
# Ou rodar MySQL:
# Windows: Services → MySQL → Iniciar
```

### "Port 8000 já em uso"
```bash
python manage.py runserver 8001
```

### "Tabela não existe"
```bash
python manage.py migrate
```

---

## 📚 Documentação Completa

| Documento | Leia se... |
|-----------|-----------|
| **GUIA_COMPLETO.md** | Quer entender tudo (longo) |
| **GUIA_VISUAL_RESUMO.md** | Quer ver diagramas e arquitetura |
| **GUIA_DESENVOLVIMENTO.md** | Vai adicionar features |
| **QUICK_START.md** | Quer rodar em 5 minutos (este arquivo) |
| SERVICE_LAYER_GUIDE.md | Quer entender services |
| LOGGING_SETUP.md | Quer configurar logs |
| RATE_LIMITING_INTEGRATION.md | Quer proteger endpoints |
| PAGINATION_INTEGRATION.md | Quer otimizar queries |

---

## 🚀 Próximos Passos

1. **Rodar aplicação** → `python manage.py runserver`
2. **Criar conta** → Ir para `/cadastro`
3. **Testar feature** → Criar devolução em `/devolucao`
4. **Ver admin** → Acessar `/admin`
5. **Adicionar feature** → Leia `GUIA_DESENVOLVIMENTO.md`

---

## ✅ Verificar Setup

```bash
# Sistema OK?
python manage.py check
# Esperado: "System check identified no issues"

# BD OK?
python manage.py migrate --plan
# Esperado: lista de migrações

# Rodar testes
python manage.py test --no-migrations
# Esperado: OK (X tests in Y.XXXs)
```

---

## 🔗 URLs Importantes

```
http://localhost:8000/             → Dashboard
http://localhost:8000/login        → Login
http://localhost:8000/cadastro     → Registrar
http://localhost:8000/devolucao    → Criar devolução
http://localhost:8000/admin        → Painel admin
```

---

## 📞 Ajuda Rápida

**Erro de migração:**
```bash
python manage.py showmigrations
python manage.py migrate --fake-initial
python manage.py migrate
```

**Resetar senha admin:**
```bash
python manage.py changepassword admin@example.com
```

**Ver SQL que vai rodar:**
```bash
python manage.py sqlmigrate devolucao 0001
```

**Listar todas URLs:**
```bash
python manage.py show_urls
```

---

## 💡 Dica Profissional

Mantenha 2 terminais abertos:

**Terminal 1 - Servidor:**
```bash
python manage.py runserver
```

**Terminal 2 - Testes/Migrations:**
```bash
python manage.py test devolucao
python manage.py migrate
```

---

## 🎉 Pronto!

Se você conseguiu rodar `python manage.py runserver` e acessou `http://localhost:8000` sem erros, **parabéns!** 🎉

O projeto está funcionando em sua máquina. Agora:

- Leia `GUIA_COMPLETO.md` para entender a arquitetura
- Leia `GUIA_DESENVOLVIMENTO.md` para adicionar features
- Abra PRs com código novo!

---

**Última atualização:** 05 de março de 2026  
**Versão:** 1.0
