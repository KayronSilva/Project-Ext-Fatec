"""
Testes unitários para services.

Rodar com:
    pytest devolucao/tests.py -v
    ou
    python manage.py test devolucao.tests
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date, timedelta

from devolucao.models import (
    Usuario, Cliente, NotaFiscal, Produto, ItemNotaFiscal,
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
