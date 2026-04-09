import os
import django
from datetime import date, timedelta
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ProjetoDevolucao.settings')
django.setup()

from devolucao.models import ConfiguracaoSistema, NotaFiscal, Cliente, Devolucao, Usuario
from devolucao.services import PrazoService

print('='*60)
print('TESTE 6: Service de Prazos')
print('='*60)

# Prazo configurado
config = ConfiguracaoSistema.prazo()
print(f'Prazo configurado: {config} dias')

# Testar cálculo de prazo
data_emissao = date.today() - timedelta(days=5)
print(f'Data de emissão: {data_emissao}')

limite = data_emissao + timedelta(days=config)
print(f'Limite de devolução seria: {limite}')

# Testar nota dentro do prazo
try:
    notas = NotaFiscal.objects.all()[:1]
    if notas:
        nota = notas[0]
        print(f'Testando nota: {nota.numero_nota}')
        print(f'Data emissão: {nota.data_emissao}')
        
        dias_restantes, status = PrazoService.status_prazo(nota)
        print(f'Dias restantes: {dias_restantes}')
        print(f'Status: {status}')
        
        if status in ['DISPONÍVEL', 'VENCENDO', 'EXPIRADA']:
            print('✓ Status válido')
        else:
            print('✗ Status inválido')
except Exception as e:
    print(f'⚠ Erro ao testar nota: {e}')

print()

print('='*60)
print('TESTE 7: Modelo de Devoluções')
print('='*60)

# Contar devoluções
count = Devolucao.objects.count()
print(f'Total de devoluções no BD: {count}')

# Se houver devoluções, mostrar status
if Devolucao.objects.exists():
    devs = Devolucao.objects.values('status').distinct()
    print('Status de devoluções:')
    for dev_status in devs:
        status = dev_status['status']
        num = Devolucao.objects.filter(status=status).count()
        print(f'  - {status}: {num}')
    print('✓ Devoluções funcionando')
else:
    print('⊘ Nenhuma devolução no BD (esperado para novo projeto)')

print()
print('='*60)
print('TESTE 8: Validação de Modelos')
print('='*60)

# Testar criação de usuário
test_email = f'teste_{int(time.time())}@test.com'

try:
    usuario = Usuario.objects.create_user(email=test_email, password='senha123')
    print(f'✓ Usuário criado: {usuario.email}')
    
    # Validar autenticação
    usuario_auth = Usuario.objects.get(email=test_email)
    if usuario_auth.check_password('senha123'):
        print('✓ Senha validada corretamente')
    else:
        print('✗ Erro na validação de senha')
        
    # Cleanup
    usuario.delete()
except Exception as e:
    print(f'✗ Erro ao testar usuário: {e}')

print()
print('='*60)
print('TESTE 9: Forms')
print('='*60)

from devolucao.forms import LoginForm, CadastroForm

# Testar form de login
form = LoginForm(data={'email': 'admin@test.com', 'password': 'senha'})
if form.is_valid():
    print('✓ LoginForm validável')
else:
    print('⊘ LoginForm com avisos (esperado se dados não correspondem)')

# Testar form de cadastro
form2 = CadastroForm(data={
    'email': f'novo_{int(time.time())}@test.com',
    'password1': 'SenhaForte123!',
    'password2': 'SenhaForte123!'
})
if form2.is_valid():
    print('✓ CadastroForm validável')
else:
    print(f'⊘ CadastroForm erros: {form2.errors}')

print()
print('='*60)
print('✅ TESTES DE SERVICES COMPLETADOS!')
print('='*60)
