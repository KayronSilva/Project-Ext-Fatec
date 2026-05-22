"""
Testes unitários para services.

Rodar com:
    pytest devolucao/tests.py -v
    ou
    python manage.py test devolucao.tests
"""

from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.urls import reverse
from datetime import date, timedelta

from devolucao.models import (
    Usuario, Cliente, ClienteVinculado, NotaFiscal, Produto, ItemNotaFiscal,
    Devolucao, ItemDevolucao, ConfiguracaoSistema
)
from devolucao.services import (
    PrazoService, ClienteService, NotaService, DevolutionService
)


class PrazoServiceTestCase(TestCase):
    """Testes de cálculo de prazo."""

    def setUp(self):
        self.cliente = Cliente.objects.create(
            tipo='PF',
            cpf='11144477735',  # CPF válido para testes
            nome='João Silva'
        )
        ConfiguracaoSistema.objects.get_or_create(pk=1, defaults={'prazo_devolucao_dias': 30})

    def test_calcular_nota_dentro_prazo(self):
        """Nota dentro do prazo não deve estar expirada."""
        data_nota = date.today() - timedelta(days=15)  # 15 dias atrás
        nota = NotaFiscal.objects.create(
            numero_nota='001',
            cliente=self.cliente,
            data_emissao=data_nota
        )

        expirado, dias_restantes = PrazoService.calcular_expirado_e_dias(nota)

        self.assertFalse(expirado)
        self.assertGreater(dias_restantes, 0)

    def test_validar_prazo_expirado_sobe_erro(self):
        """Validação deve levantar erro para prazo expirado."""
        data_nota = date.today() - timedelta(days=45)
        nota = NotaFiscal.objects.create(
            numero_nota='003',
            cliente=self.cliente,
            data_emissao=data_nota
        )

        with self.assertRaises(ValidationError):
            PrazoService.validar_prazo(nota)


class ClienteServiceTestCase(TestCase):
    """Testes de busca de cliente."""

    def setUp(self):
        self.cliente_pf = Cliente.objects.create(
            tipo='PF',
            cpf='11144477735',  # CPF válido para testes
            nome='João Silva'
        )

    def test_buscar_cliente_por_cpf(self):
        """Buscar cliente por CPF deve encontrar."""
        cliente = ClienteService.buscar_por_documento('11144477735')
        self.assertEqual(cliente.id, self.cliente_pf.id)

    def test_buscar_cliente_inexistente(self):
        """Buscar cliente inexistente deve retornar None."""
        cliente = ClienteService.buscar_por_documento('99999999999')
        self.assertIsNone(cliente)


class NotaServiceTestCase(TestCase):
    """Testes de operações com notas."""

    def setUp(self):
        self.cliente = Cliente.objects.create(
            tipo='PF',
            cpf='11144477735',  # CPF válido para testes
            nome='João'
        )
        self.produto = Produto.objects.create(
            codigo=1001,
            descricao='Produto A'
        )
        self.nota = NotaFiscal.objects.create(
            numero_nota='001',
            cliente=self.cliente,
            data_emissao=date.today() - timedelta(days=10)
        )
        ItemNotaFiscal.objects.create(
            nota_fiscal=self.nota,
            produto=self.produto,
            quantidade=10
        )
        ConfiguracaoSistema.objects.get_or_create(pk=1, defaults={'prazo_devolucao_dias': 30})

    def test_calcular_saldo_novo_produto(self):
        """Produto novo deve ter saldo igual a quantidade."""
        saldo = NotaService.calcular_saldo_produto(self.nota, self.produto)

        self.assertEqual(saldo['original'], 10)
        self.assertEqual(saldo['devolvido'], 0)
        self.assertEqual(saldo['disponivel'], 10)


class BuscarNotasClienteVinculadoViewTestCase(TestCase):
    """Testa a API AJAX de busca de notas para cliente vinculado."""

    def setUp(self):
        self.client = Client()
        self.usuario = Usuario.objects.create_user(email='cliente@test.com', password='senha123')
        self.cliente = Cliente.objects.create(
            usuario=self.usuario,
            tipo='PF',
            cpf='11144477735',
            nome='João Silva'
        )
        self.cliente_vinculado = ClienteVinculado.objects.create(
            usuario=self.usuario,
            cliente=self.cliente,
            ativo=True
        )
        ConfiguracaoSistema.objects.get_or_create(pk=1, defaults={'prazo_devolucao_dias': 30})
        self.client.login(email='cliente@test.com', password='senha123')

    def test_retorna_notas_dentro_do_prazo(self):
        nota_valida = NotaFiscal.objects.create(
            numero_nota='001',
            cliente=self.cliente,
            data_emissao=date.today() - timedelta(days=10)
        )
        Produto.objects.create(codigo=1001, descricao='Produto Teste')
        ItemNotaFiscal.objects.create(
            nota_fiscal=nota_valida,
            produto=Produto.objects.first(),
            quantidade=5
        )

        response = self.client.get(
            reverse('buscar_notas_cliente_vinculado'),
            {'cliente_vinculado_id': str(self.cliente_vinculado.id)}
        )
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['encontrado'])
        self.assertEqual(len(data['notas']), 1)
        self.assertEqual(data['notas'][0]['numero_nota'], '001')
        self.assertNotIn('aviso', data)

    def test_retorna_aviso_quando_todas_as_notas_expiradas(self):
        nota_expirada = NotaFiscal.objects.create(
            numero_nota='002',
            cliente=self.cliente,
            data_emissao=date.today() - timedelta(days=40)
        )
        ItemNotaFiscal.objects.create(
            nota_fiscal=nota_expirada,
            produto=Produto.objects.create(codigo=1002, descricao='Produto Expirado'),
            quantidade=5
        )

        response = self.client.get(
            reverse('buscar_notas_cliente_vinculado'),
            {'cliente_vinculado_id': str(self.cliente_vinculado.id)}
        )
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['encontrado'])
        self.assertEqual(data['notas'], [])
        self.assertIn('aviso', data)
        self.assertIn('prazo', data['aviso'])

    def test_retorna_aviso_quando_cliente_nao_tem_notas(self):
        """Cliente vinculado sem notas deve retornar aviso apropriado."""
        response = self.client.get(
            reverse('buscar_notas_cliente_vinculado'),
            {'cliente_vinculado_id': str(self.cliente_vinculado.id)}
        )
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['encontrado'])
        self.assertEqual(data['notas'], [])
        self.assertIn('aviso', data)
        self.assertIn('itens', data['aviso'].lower())

    def test_retorna_aviso_quando_notas_sem_itens(self):
        """Notas sem itens cadastrados devem ser ignoradas."""
        NotaFiscal.objects.create(
            numero_nota='003',
            cliente=self.cliente,
            data_emissao=date.today() - timedelta(days=5)
        )

        response = self.client.get(
            reverse('buscar_notas_cliente_vinculado'),
            {'cliente_vinculado_id': str(self.cliente_vinculado.id)}
        )
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['encontrado'])
        self.assertEqual(data['notas'], [])
        self.assertIn('aviso', data)
        self.assertIn('itens', data['aviso'].lower())

