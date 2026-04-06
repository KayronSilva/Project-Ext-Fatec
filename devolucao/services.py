"""
Service Layer - Lógica de negócio isolada de views.

Este módulo contém classes que encapsulam a lógica de domínio do sistema.
Benefícios:
  - Testável sem HttpRequest
  - Reutilizável (views, APIs, tasks)
  - Documentação clara de fluxos de negócio
"""

import structlog
from datetime import date
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum

from devolucao.logging_utils import log_action, log_error
from devolucao.models import (
    Cliente, NotaFiscal, Produto, ItemNotaFiscal, ItemDevolucao,
    Devolucao, ConfiguracaoSistema
)

logger = structlog.get_logger()


class PrazoService:
    """Serviço para cálculos de prazo de devolução."""

    @staticmethod
    def calcular_expirado_e_dias(nota):
        """
        Calcula se prazo de devolução expirou e dias restantes.

        Args:
            nota (NotaFiscal): Nota fiscal

        Returns:
            tuple: (expirado: bool, dias_restantes: int)
        """
        if not nota.data_emissao:
            return None, None

        prazo_config = ConfiguracaoSistema.prazo()
        delta_dias = (date.today() - nota.data_emissao).days
        dias_restantes = prazo_config - delta_dias
        expirado = delta_dias > prazo_config

        return expirado, dias_restantes

    @staticmethod
    def validar_prazo(nota):
        """Valida se prazo não expirou. Sobe ValidationError se expirado."""
        expirado, dias_restantes = PrazoService.calcular_expirado_e_dias(nota)

        if expirado:
            prazo = ConfiguracaoSistema.prazo()
            raise ValidationError(
                f'Prazo de {prazo} dias para devolução já expirou. '
                f'Nota emitida em {nota.data_emissao}'
            )


class ClienteService:
    """Serviço para operações com clientes."""

    @staticmethod
    def buscar_por_documento(documento: str):
        """
        Busca cliente por CPF ou CNPJ.

        Args:
            documento (str): CPF (11 dígitos) ou CNPJ (14 dígitos)

        Returns:
            Cliente ou None
        """
        documento_limpo = documento.replace('.', '').replace('/', '').replace('-', '')

        try:
            if len(documento_limpo) == 11:
                return Cliente.objects.get(cpf=documento_limpo)
            elif len(documento_limpo) == 14:
                return Cliente.objects.get(cnpj=documento_limpo)
        except Cliente.DoesNotExist:
            return None

        return None

    @staticmethod
    def verificar_propriedade(usuario, cliente):
        """
        Verifica se cliente pertence ao usuário autenticado.

        Raises:
            ValidationError: Se cliente não pertence ao usuário
        """
        try:
            cliente_logado = usuario.cliente
        except Exception:
            raise ValidationError("Usuário não possui cliente associado")

        if cliente_logado.id != cliente.id:
            raise ValidationError("Acesso negado: cliente não pertence a este usuário")


class NotaService:
    """Serviço para operações com notas fiscais."""

    @staticmethod
    def buscar_notas_cliente(cliente, filtrar_expiradas=True):
        """
        Busca notas de um cliente com cálculo de saldo disponível.

        Args:
            cliente (Cliente): Cliente
            filtrar_expiradas (bool): Se True, exclui notas com prazo expirado

        Returns:
            QuerySet de NotaFiscal
        """
        notas = NotaFiscal.objects.filter(cliente=cliente).select_related('cliente')

        if filtrar_expiradas:
            # Filtrar no Python (pragmático para pequenos datasets)
            notas_validas = []
            for nota in notas:
                expirado, _ = PrazoService.calcular_expirado_e_dias(nota)
                if not expirado:
                    notas_validas.append(nota)
            return notas_validas

        return list(notas)

    @staticmethod
    def calcular_saldo_produto(nota, produto):
        """
        Calcula quantidade disponível para devolução de um produto.

        Returns:
            dict: {'original': int, 'devolvido': int, 'disponivel': int}
        """
        try:
            item_nota = ItemNotaFiscal.objects.get(
                nota_fiscal=nota,
                produto=produto
            )
        except ItemNotaFiscal.DoesNotExist:
            return {'original': 0, 'devolvido': 0, 'disponivel': 0}

        devolvido = (
            ItemDevolucao.objects
            .filter(devolucao__nota_fiscal=nota, produto=produto)
            .aggregate(total=Sum('quantidade_devolvida'))['total']
        ) or 0

        disponivel = item_nota.quantidade - devolvido

        return {
            'original': item_nota.quantidade,
            'devolvido': devolvido,
            'disponivel': disponivel
        }


class DevolutionService:
    """Serviço para criação e validação de devoluções."""

    @staticmethod
    def validar_produtos(nota, produtos_data):
        """
        Valida se produtos podem ser devolvidos.

        Args:
            nota (NotaFiscal): Nota fiscal
            produtos_data (list): Lista de dicts com 'produto_id' e 'quantidade'

        Raises:
            ValueError: Se há problemas com produtos
        """
        erros = []

        # Validar que produtos existem
        ids_produtos = [p['produto_id'] for p in produtos_data]
        produtos_map = {
            str(obj.pk): obj
            for obj in Produto.objects.filter(id__in=ids_produtos)
        }

        for prod_data in produtos_data:
            produto_id = str(prod_data['produto_id'])
            quantidade = prod_data.get('quantidade', 0)

            # Produto existe?
            produto = produtos_map.get(produto_id)
            if not produto:
                erros.append(f'Produto {produto_id} não encontrado')
                continue

            # Produto está nesta nota?
            try:
                item_nota = ItemNotaFiscal.objects.get(
                    nota_fiscal=nota,
                    produto=produto
                )
            except ItemNotaFiscal.DoesNotExist:
                erros.append(f'Produto "{produto.descricao}" não está nesta nota')
                continue

            # Há saldo disponível?
            saldo = NotaService.calcular_saldo_produto(nota, produto)
            if quantidade > saldo['disponivel']:
                erros.append(
                    f'"{produto.descricao}": '
                    f'solicitado {quantidade}, disponível {saldo["disponivel"]}'
                )

        if erros:
            raise ValueError('\n'.join(erros))

    @staticmethod
    def validar_motivos(produtos_data):
        """Valida que motivos estão preenchidos adequadamente."""
        motivos_validos = {
            'produto_danificado', 'erro_pedido', 'prazo_vencido', 'outro', ''
        }

        for prod_data in produtos_data:
            motivo = prod_data.get('motivo', '')
            if motivo not in motivos_validos:
                raise ValueError(
                    f'Motivo inválido: {motivo}. '
                    f'Use: {", ".join(motivos_validos)}'
                )

    @staticmethod
    @transaction.atomic
    def criar_devolucao(nota, produtos_data, usuario_id, request_files=None):
        """
        Cria devolução com validação completa.

        Args:
            nota (NotaFiscal): Nota fiscal
            produtos_data (list): Lista de {produto_id, quantidade, motivo, observacao}
            usuario_id (int): ID do usuário autenticado
            request_files (dict): request.FILES do Django

        Returns:
            Devolucao: Devolução criada

        Raises:
            ValidationError, ValueError: Se validações falharem
        """
        # Validações
        PrazoService.validar_prazo(nota)
        DevolutionService.validar_produtos(nota, produtos_data)
        DevolutionService.validar_motivos(produtos_data)

        log_action('devolucao.validacao_passou',
            usuario_id=usuario_id,
            nota_id=nota.pk,
            quantidade_produtos=len(produtos_data)
        )

        # Criar devolução
        devolucao = Devolucao.objects.create(
            nota_fiscal=nota,
            cliente=nota.cliente
        )

        # Criar items
        produtos_map = {
            str(obj.pk): obj
            for obj in Produto.objects.filter(
                id__in=[p['produto_id'] for p in produtos_data]
            )
        }

        for prod_data in produtos_data:
            produto = produtos_map[str(prod_data['produto_id'])]

            # Pegar foto se existe
            foto_key = f'foto_produto_{prod_data["produto_id"]}'
            foto = request_files.get(foto_key) if request_files else None

            ItemDevolucao.objects.create(
                devolucao=devolucao,
                produto=produto,
                quantidade_devolvida=prod_data['quantidade'],
                motivo=prod_data.get('motivo', ''),
                observacao=prod_data.get('observacao', ''),
                foto=foto
            )

        # Log de sucesso
        log_action('devolucao.criada',
            devolucao_id=devolucao.pk,
            usuario_id=usuario_id,
            nota_id=nota.pk,
            quantidade_itens=len(produtos_data)
        )

        return devolucao


class PerfilService:
    """Serviço para atualização de perfil de usuário."""

    @staticmethod
    def atualizar_cliente(cliente, dados):
        """
        Atualiza dados do cliente com validação.

        Args:
            cliente (Cliente): Cliente
            dados (dict): Dicionário com campos a atualizar
        """
        campos_permitidos = {
            'telefone', 'celular', 'email', 'cep', 'logradouro',
            'numero', 'complemento', 'bairro', 'cidade', 'estado'
        }

        for campo, valor in dados.items():
            if campo not in campos_permitidos:
                continue

            if valor:  # Só atualiza se não vazio
                setattr(cliente, campo, valor)

        cliente.save()

        log_action('cliente.atualizado',
            cliente_id=cliente.id,
            campos=list(dados.keys())
        )
