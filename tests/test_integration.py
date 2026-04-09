"""
Teste de integração para o fluxo de devolução com nota fiscal.

Testa o cenário onde:
1. Usuário seleciona um cliente_vinculado
2. Sistema busca notas disponíveis
3. Sistema retorna notas ou mensagem apropriada
4. Usuário seleciona nota e vê itens disponíveis
"""
import os
import django
from django.test import TestCase, Client
from django.contrib.auth.models import AnonymousUser
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ProjetoDevolucao.settings')
django.setup()

from devolucao.models import (
    Usuario, Cliente, ClienteVinculado, NotaFiscal, ItemNotaFiscal,
    Produto, ConfiguracaoSistema, Devolucao, ItemDevolucao
)


class DevolutionFlowIntegrationTest(TestCase):
    """Testa fluxo completo de devolução com nota fiscal"""

    def setUp(self):
        """Cria dados de teste"""
        # Cria usuário cliente
        self.usuario = Usuario.objects.create_user(
            email='cliente@test.com',
            password='senha123',
            is_staff=False
        )

        # Cria cliente (PJ)
        self.cliente = Cliente.objects.create(
            usuario=self.usuario,
            tipo='PJ',
            razao_social='Empresa Teste LTDA',
            cnpj='11222233000181',
            email='empresa@test.com',
            telefone='1133334444',
            endereco='Rua Teste, 123'
        )

        # Cria cliente vinculado
        self.cliente_vinculado = ClienteVinculado.objects.create(
            usuario=self.usuario,
            cliente=self.cliente,
            ativo=True
        )

        # Cria configuração sistema (prazo padrão)
        ConfiguracaoSistema.objects.all().delete()
        ConfiguracaoSistema.objects.create(prazo_devolucao_dias=30)

        # Cria produto
        self.produto = Produto.objects.create(
            codigo='P001',
            descricao='Produto Teste',
            categoria='Eletrônicos'
        )

        # Cria nota fiscal (dentro do prazo)
        hoje = date.today()
        self.nota_fiscal = NotaFiscal.objects.create(
            cliente=self.cliente,
            numero_nota='NF-001',
            data_emissao=hoje - timedelta(days=10),  # 10 dias atrás
            valor_total=1000.00,
            status='importada'
        )

        # Cria itens da nota fiscal
        ItemNotaFiscal.objects.create(
            nota_fiscal=self.nota_fiscal,
            produto=self.produto,
            quantidade=5,
            valor_unitario=200.00
        )

        self.client = Client()

    def test_usuario_nao_autenticado_bloqueado(self):
        """Testa que usuário não autenticado não pode acessar AJAX"""
        response = self.client.get(
            f'/ajax/buscar-notas-cliente-vinculado/?cliente_vinculado_id={self.cliente_vinculado.id}',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        # Deve redirecionar para login
        self.assertEqual(response.status_code, 302)

    def test_buscar_notas_cliente_vinculado_sucesso(self):
        """Testa busca de notas para cliente vinculado válido"""
        self.client.login(email='cliente@test.com', password='senha123')

        response = self.client.get(
            f'/ajax/buscar-notas-cliente-vinculado/?cliente_vinculado_id={self.cliente_vinculado.id}',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Validações
        self.assertTrue(data['encontrado'])
        self.assertGreater(len(data['notas']), 0)
        self.assertEqual(data['notas'][0]['numero_nota'], 'NF-001')
        self.assertTrue(data['notas'][0]['totalmente_devolvida'] == False)

    def test_buscar_notas_cliente_vinculado_invalido(self):
        """Testa busca com cliente_vinculado inválido"""
        self.client.login(email='cliente@test.com', password='senha123')

        response = self.client.get(
            '/ajax/buscar-notas-cliente-vinculado/?cliente_vinculado_id=999',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        # Deve retornar 403 (acesso negado)
        self.assertEqual(response.status_code, 403)

    def test_buscar_itens_nota_sucesso(self):
        """Testa busca de itens de uma nota"""
        self.client.login(email='cliente@test.com', password='senha123')

        response = self.client.get(
            f'/ajax/buscar-itens-nota-cliente-vinculado/?cliente_vinculado_id={self.cliente_vinculado.id}&nota_id={self.nota_fiscal.id}',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data['encontrado'])
        self.assertGreater(len(data['itens']), 0)
        self.assertEqual(data['itens'][0]['codigo'], 'P001')
        self.assertEqual(data['itens'][0]['quantidade_disponivel'], 5)

    def test_nota_totalmente_devolvida(self):
        """Testa comportamento quando nota é totalmente devolvida"""
        # Cria devolução de todos os itens
        devolucao = Devolucao.objects.create(
            usuario=self.usuario,
            nota_fiscal=self.nota_fiscal,
            status='finalizada'
        )

        ItemDevolucao.objects.create(
            devolucao=devolucao,
            produto=self.produto,
            quantidade_devolvida=5,
            motivo='Defeito'
        )

        self.client.login(email='cliente@test.com', password='senha123')

        response = self.client.get(
            f'/ajax/buscar-notas-cliente-vinculado/?cliente_vinculado_id={self.cliente_vinculado.id}',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        data = response.json()
        # Nota deve aparecer como totalmente devolvida
        self.assertTrue(data['notas'][0]['totalmente_devolvida'])

    def test_nota_expirada(self):
        """Testa comportamento quando nota está expirada"""
        # Cria nota muito antiga (fora do prazo)
        nota_expirada = NotaFiscal.objects.create(
            cliente=self.cliente,
            numero_nota='NF-002',
            data_emissao=date.today() - timedelta(days=45),  # 45 dias atrás
            valor_total=1000.00,
            status='importada'
        )

        ItemNotaFiscal.objects.create(
            nota_fiscal=nota_expirada,
            produto=self.produto,
            quantidade=5,
            valor_unitario=200.00
        )

        self.client.login(email='cliente@test.com', password='senha123')

        response = self.client.get(
            f'/ajax/buscar-notas-cliente-vinculado/?cliente_vinculado_id={self.cliente_vinculado.id}',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        data = response.json()
        # Nota expirada não deve aparecer na lista
        notas_disponiveis = [n for n in data['notas'] if n['numero_nota'] == 'NF-002']
        self.assertEqual(len(notas_disponiveis), 0)

    def test_parametros_faltando(self):
        """Testa validação de parâmetros obrigatórios"""
        self.client.login(email='cliente@test.com', password='senha123')

        # Sem cliente_vinculado_id
        response = self.client.get(
            '/ajax/buscar-notas-cliente-vinculado/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)

        # Sem nota_id
        response = self.client.get(
            f'/ajax/buscar-itens-nota-cliente-vinculado/?cliente_vinculado_id={self.cliente_vinculado.id}',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    import unittest
    unittest.main()
