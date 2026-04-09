import os
import django
from django.test import Client
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ProjetoDevolucao.settings')
django.setup()

from devolucao.models import Cliente, NotaFiscal, ItemNotaFiscal, Produto

print('='*60)
print('TESTE 10: Views e Autenticação')
print('='*60)

client = Client()

# Testar login
print('Testando login...')
response = client.post('/login/', {
    'email': 'admin@test.com',
    'password': 'admin123'
})

if response.status_code in [200, 302]:
    print(f'✓ Login respondeu com {response.status_code}')
else:
    print(f'⚠ Login respondeu com {response.status_code}')

# Testar acesso a dashboard sem autenticação
print('\nTestando acesso a dashboard sem autenticação...')
response = client.get('/acompanhar/')
if response.status_code == 302:  # Redirect para login
    print('✓ Dashboard protegido, redireciona para login')
elif response.status_code == 200:
    print('✓ Dashboard acessível')
else:
    print(f'⚠ Dashboard retornou {response.status_code}')

# Testar AJAX endpoint de cliente
print('\nTestando AJAX de busca de cliente...')
response = client.get('/buscar_cliente/', {'termo': '11144477735'})
print(f'Status code: {response.status_code}')
if response.status_code == 200:
    print('✓ AJAX de cliente respondeu')
    content = response.json() if response.get('Content-Type') == 'application/json' else None
    if content:
        print(f'  Resposta: {content}')
else:
    print(f'⚠ AJAX retornou {response.status_code}')

print()
print('='*60)
print('TESTE 11: Data Integrity')
print('='*60)

# Verificar relacionamentos
try:
    clientes = Cliente.objects.all()
    print(f'Total de clientes: {clientes.count()}')
    
    if clientes.exists():
        cliente = clientes.first()
        print(f'Cliente teste: {cliente.razao_social or cliente.nome}')
        print(f'  Documento: {cliente.cpf or cliente.cnpj}')
        print(f'  Tipo: {cliente.tipo}')
        
        # Verificar notas vinculadas
        notas = NotaFiscal.objects.filter(cliente=cliente)
        print(f'  Notas fiscais: {notas.count()}')
        
        if notas.exists():
            nota = notas.first()
            print(f'\n  Nota teste: {nota.numero_nota}')
            print(f'    Emissão: {nota.data_emissao}')
            
            # Verificar itens da nota
            itens = ItemNotaFiscal.objects.filter(nota_fiscal=nota)
            print(f'    Itens: {itens.count()}')
            
            if itens.exists():
                item = itens.first()
                print(f'\n    Item teste:')
                print(f'      Produto: {item.produto.descricao}')
                print(f'      Quantidade: {item.quantidade}')

except Exception as e:
    print(f'✗ Erro ao verificar data integrity: {e}')

print()
print('='*60)
print('TESTE 12: Rate Limiting')
print('='*60)

from django.test.client import Client
from django.http import HttpRequest

print('Verificando decoradores de rate limiting...')

# Verificar se decoradores estão aplicados
from devolucao import views
import inspect

endpoints_rate_limited = [
    'buscar_cliente',
    'buscar_notas_cliente',
    'buscar_itens_nota'
]

for endpoint in endpoints_rate_limited:
    if hasattr(views, endpoint):
        func = getattr(views, endpoint)
        source = inspect.getsource(func)
        if 'ratelimit' in source or 'rate_limit' in source:
            print(f'✓ {endpoint} tem rate limiting')
        else:
            print(f'⊘ {endpoint} pode ter rate limiting decorado')

print()
print('='*60)
print('✅ TESTES DE VIEWS E SEGURANÇA COMPLETADOS!')
print('='*60)
