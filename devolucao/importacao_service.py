"""
Serviço de importação de Notas Fiscais.

Estrutura genérica que permite conectar qualquer ERP com mínima alteração.

Para integrar um novo ERP:
    1. Crie uma classe que herda de ERPIntegrationBase
    2. Implemente os métodos abstratos
    3. Registre em ERP_REGISTRY abaixo

Exemplo:
    class MinhaIntegracao(ERPIntegrationBase):
        def buscar_notas_por_cliente(self, documento): ...
        def buscar_itens_nota(self, nota_id_erp): ...
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import xml.etree.ElementTree as ET
import re
import logging

logger = logging.getLogger(__name__)

_NS = 'http://www.portalfiscal.inf.br/nfe'  # namespace padrão NF-e


# ════════════════════════════════════════════════════════
# Data classes de transferência (independentes do Django)
# ════════════════════════════════════════════════════════

@dataclass
class ItemImportado:
    codigo_produto: str
    descricao:      str
    quantidade:     int


@dataclass
class NotaImportada:
    numero_nota:   str
    data_emissao:  str          # formato ISO: YYYY-MM-DD
    documento_cliente: str      # CPF (11 dígitos) ou CNPJ (14 dígitos)
    nome_cliente:  str
    itens:         list[ItemImportado] = field(default_factory=list)
    origem:        str = 'manual'   # 'xml', 'sankhya', 'api_generica', etc.
    raw_data:      Optional[dict] = None  # dados brutos para debug


# ════════════════════════════════════════════════════════
# Base abstrata para integrações de ERP
# ════════════════════════════════════════════════════════

class ERPIntegrationBase(ABC):
    """
    Contrato que qualquer integração ERP deve implementar.

    Para conectar um novo sistema (ex: TOTVS, SAP, Bling):
        - Herde desta classe
        - Implemente os 3 métodos abstratos
        - Registre em ERP_REGISTRY
    """

    @property
    @abstractmethod
    def nome(self) -> str:
        """Nome legível do ERP (ex: 'Sankhya', 'TOTVS')."""

    @abstractmethod
    def testar_conexao(self) -> tuple[bool, str]:
        """
        Testa se a integração está acessível.

        Returns:
            (True, 'OK') se conectado
            (False, 'mensagem de erro') se falhou
        """

    @abstractmethod
    def buscar_notas_por_documento(self, documento: str) -> list[NotaImportada]:
        """
        Busca notas fiscais de um cliente pelo CPF/CNPJ.

        Args:
            documento: CPF (11 dígitos) ou CNPJ (14 dígitos), apenas números

        Returns:
            Lista de NotaImportada
        """

    @abstractmethod
    def buscar_nota_por_numero(self, numero_nota: str) -> Optional[NotaImportada]:
        """
        Busca uma nota específica pelo número.

        Args:
            numero_nota: Número da nota fiscal

        Returns:
            NotaImportada ou None se não encontrada
        """


# ════════════════════════════════════════════════════════
# Implementação Sankhya (stub — pronto para conectar)
# ════════════════════════════════════════════════════════

class SankhyaIntegration(ERPIntegrationBase):
    """
    Integração com Sankhya W.

    Para ativar:
        1. Configure SANKHYA_URL, SANKHYA_USER, SANKHYA_PASSWORD no .env
        2. Substitua os métodos stub pela lógica real do sankhya_api.py
    """

    @property
    def nome(self) -> str:
        return 'Sankhya W'

    def __init__(self):
        from django.conf import settings
        self.base_url = getattr(settings, 'SANKHYA_URL', '')
        self.usuario  = getattr(settings, 'SANKHYA_USER', '')
        self.senha    = getattr(settings, 'SANKHYA_PASSWORD', '')

    def testar_conexao(self) -> tuple[bool, str]:
        if not self.base_url:
            return False, 'SANKHYA_URL não configurada no .env'
        # TODO: implementar chamada real à API Sankhya
        # try:
        #     from .sankhya_api import SankhyaAPI
        #     api = SankhyaAPI(self.base_url, self.usuario, self.senha)
        #     return api.ping()
        # except Exception as e:
        #     return False, str(e)
        return False, 'Integração Sankhya ainda não configurada. Configure SANKHYA_URL no .env.'

    def buscar_notas_por_documento(self, documento: str) -> list[NotaImportada]:
        # TODO: implementar via sankhya_api.py
        # Exemplo de estrutura esperada:
        # notas_raw = SankhyaAPI(...).get_notas_cliente(documento)
        # return [self._converter(n) for n in notas_raw]
        raise NotImplementedError(
            'Integração Sankhya não implementada. '
            'Complete o método buscar_notas_por_documento em SankhyaIntegration.'
        )

    def buscar_nota_por_numero(self, numero_nota: str) -> Optional[NotaImportada]:
        # TODO: implementar via sankhya_api.py
        raise NotImplementedError(
            'Integração Sankhya não implementada. '
            'Complete o método buscar_nota_por_numero em SankhyaIntegration.'
        )

    def _converter(self, nota_raw: dict) -> NotaImportada:
        """
        Converte resposta da API Sankhya para NotaImportada.
        Ajuste os campos conforme o retorno real da sua API.
        """
        return NotaImportada(
            numero_nota        = str(nota_raw.get('NUNOTA', '')),
            data_emissao       = nota_raw.get('DTNEG', '')[:10],  # YYYY-MM-DD
            documento_cliente  = re.sub(r'\D', '', nota_raw.get('CGC_CPF', '')),
            nome_cliente       = nota_raw.get('NOMEPARC', ''),
            itens=[
                ItemImportado(
                    codigo_produto = str(i.get('CODPROD', '')),
                    descricao      = i.get('DESCRPROD', ''),
                    quantidade     = int(float(i.get('QTDNEG', 0))),
                )
                for i in nota_raw.get('itens', [])
            ],
            origem   = 'sankhya',
            raw_data = nota_raw,
        )


# ════════════════════════════════════════════════════════
# Registro de integrações disponíveis
# ════════════════════════════════════════════════════════

ERP_REGISTRY: dict[str, type[ERPIntegrationBase]] = {
    'sankhya': SankhyaIntegration,
    # 'totvs':  TOTVSIntegration,   # adicione aqui novos ERPs
    # 'bling':  BlingIntegration,
}

def get_integration(nome: str) -> ERPIntegrationBase:
    """Retorna instância da integração pelo nome registrado."""
    cls = ERP_REGISTRY.get(nome)
    if not cls:
        raise ValueError(f"Integração '{nome}' não encontrada. Disponíveis: {list(ERP_REGISTRY.keys())}")
    return cls()


# ════════════════════════════════════════════════════════
# Parser de XML NF-e (padrão SEFAZ)
# ════════════════════════════════════════════════════════

def _tag(nome: str) -> str:
    return f'{{{_NS}}}{nome}'


def _find(elem, *caminhos: str) -> Optional[ET.Element]:
    """Busca elemento com ou sem namespace."""
    for caminho in caminhos:
        # tenta com namespace
        partes_ns = '/'.join(_tag(p) for p in caminho.split('/'))
        result = elem.find(partes_ns)
        if result is not None:
            return result
        # tenta sem namespace (XMLs sem declaração de namespace)
        result = elem.find(caminho)
        if result is not None:
            return result
    return None


def _text(elem, *caminhos: str, default: str = '') -> str:
    node = _find(elem, *caminhos)
    return (node.text or '').strip() if node is not None else default


def _only_digits(value: str) -> str:
    return re.sub(r'\D', '', value or '')


class XMLNFeImporter:
    """
    Lê XML de NF-e (padrão SEFAZ) e extrai dados estruturados.

    Suporta:
        - NF-e com namespace  (http://www.portalfiscal.inf.br/nfe)
        - NF-e sem namespace  (alguns emissores antigos)
        - Arquivo .xml direto ou .xml dentro de nfeProc
    """

    def parse(self, xml_content: bytes) -> NotaImportada:
        """
        Analisa o conteúdo XML e retorna NotaImportada.

        Args:
            xml_content: bytes do arquivo XML

        Raises:
            ValueError: se o XML não for uma NF-e válida
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise ValueError(f'XML inválido: {e}')

        # Localiza o elemento infNFe (pode estar dentro de nfeProc)
        infNFe = (
            _find(root, 'NFe/infNFe')
            or _find(root, 'infNFe')
        )
        if infNFe is None:
            raise ValueError('Estrutura XML não reconhecida como NF-e. Elemento <infNFe> não encontrado.')

        numero_nota  = self._extrair_numero(infNFe)
        data_emissao = self._extrair_data(infNFe)
        doc_cliente, nome_cliente = self._extrair_destinatario(infNFe)
        itens = self._extrair_itens(infNFe)

        if not numero_nota:
            raise ValueError('Número da nota não encontrado no XML.')
        if not doc_cliente:
            raise ValueError('CPF/CNPJ do destinatário não encontrado no XML.')
        if not itens:
            raise ValueError('Nenhum item (produto) encontrado no XML.')

        return NotaImportada(
            numero_nota        = numero_nota,
            data_emissao       = data_emissao,
            documento_cliente  = doc_cliente,
            nome_cliente       = nome_cliente,
            itens              = itens,
            origem             = 'xml',
        )

    def _extrair_numero(self, infNFe: ET.Element) -> str:
        ide = _find(infNFe, 'ide')
        if ide is None:
            return ''
        nnf  = _text(ide, 'nNF')
        serie = _text(ide, 'serie')
        return f'{serie}-{nnf}' if serie and nnf else nnf

    def _extrair_data(self, infNFe: ET.Element) -> str:
        ide = _find(infNFe, 'ide')
        if ide is None:
            return ''
        raw = _text(ide, 'dhEmi') or _text(ide, 'dEmi')
        # dhEmi pode ser '2024-01-15T10:30:00-03:00' — pega só a data
        return raw[:10] if raw else ''

    def _extrair_destinatario(self, infNFe: ET.Element) -> tuple[str, str]:
        dest = _find(infNFe, 'dest')
        if dest is None:
            return '', ''

        cnpj = _only_digits(_text(dest, 'CNPJ'))
        cpf  = _only_digits(_text(dest, 'CPF'))
        doc  = cnpj if cnpj else cpf

        nome = (
            _text(dest, 'xNome')
            or _text(dest, 'xFant')
            or ''
        )
        return doc, nome

    def _extrair_itens(self, infNFe: ET.Element) -> list[ItemImportado]:
        itens = []
        # Itens ficam em <det nItem="1"><prod>...</prod></det>
        ns_det = _tag('det')
        det_list = infNFe.findall(f'.//{ns_det}')

        # fallback sem namespace
        if not det_list:
            det_list = infNFe.findall('.//det')

        for det in det_list:
            prod = _find(det, 'prod')
            if prod is None:
                continue

            codigo = _text(prod, 'cProd')
            descricao = _text(prod, 'xProd')
            qtd_raw = _text(prod, 'qCom') or _text(prod, 'qTrib') or '0'

            try:
                quantidade = int(float(qtd_raw.replace(',', '.')))
            except ValueError:
                quantidade = 0

            if quantidade <= 0:
                continue

            itens.append(ItemImportado(
                codigo_produto = codigo,
                descricao      = descricao,
                quantidade     = quantidade,
            ))

        return itens


# ════════════════════════════════════════════════════════
# Orquestrador: salva NotaImportada no banco Django
# ════════════════════════════════════════════════════════

class NotaFiscalImporter:
    """
    Recebe um NotaImportada e persiste no banco.

    Comportamento:
        - Cliente: busca por CPF/CNPJ. Se não existir, cria automaticamente.
        - Nota: se já existir o número, atualiza itens (idempotente).
        - Produto: busca por código. Se não existir, cria.
        - ItemNotaFiscal: recria todos os itens da nota (substitui).

    Uso:
        importer = NotaFiscalImporter()
        resultado = importer.salvar(nota_importada)
    """

    def salvar(self, nota: NotaImportada) -> dict:
        """
        Salva a nota no banco de forma idempotente.

        Returns:
            dict com 'nota_fiscal', 'cliente', 'itens_criados', 'criado' (bool)
        """
        from django.db import transaction
        from .models import Cliente, NotaFiscal, Produto, ItemNotaFiscal

        with transaction.atomic():
            cliente = self._get_ou_criar_cliente(nota, Cliente)
            nota_fiscal, criada = self._get_ou_atualizar_nota(nota, cliente, NotaFiscal)
            itens_criados = self._salvar_itens(nota, nota_fiscal, Produto, ItemNotaFiscal)

        logger.info(
            'nota_fiscal.importada',
            extra={
                'numero_nota':   nota_fiscal.numero_nota,
                'cliente':       cliente.nome_exibicao,
                'itens':         itens_criados,
                'criada':        criada,
                'origem':        nota.origem,
            }
        )

        return {
            'nota_fiscal':   nota_fiscal,
            'cliente':       cliente,
            'itens_criados': itens_criados,
            'criada':        criada,
        }

    def _get_ou_criar_cliente(self, nota: NotaImportada, Cliente):
        doc = _only_digits(nota.documento_cliente)
        tipo = 'PF' if len(doc) == 11 else 'PJ'

        if tipo == 'PF':
            cliente = Cliente.objects.filter(cpf=doc).first()
            if not cliente:
                cliente = Cliente(tipo='PF', cpf=doc, nome=nota.nome_cliente or f'Cliente {doc}')
                cliente.save(skip_validation=True)
        else:
            cliente = Cliente.objects.filter(cnpj=doc).first()
            if not cliente:
                cliente = Cliente(tipo='PJ', cnpj=doc, razao_social=nota.nome_cliente or f'Empresa {doc}')
                cliente.save(skip_validation=True)

        return cliente

    def _get_ou_atualizar_nota(self, nota: NotaImportada, cliente, NotaFiscal):
        from datetime import date
        data = None
        if nota.data_emissao:
            try:
                data = date.fromisoformat(nota.data_emissao)
            except ValueError:
                pass

        nota_fiscal, criada = NotaFiscal.objects.get_or_create(
            numero_nota=nota.numero_nota,
            defaults={'cliente': cliente, 'data_emissao': data},
        )

        # Se já existia, atualiza cliente e data
        if not criada:
            nota_fiscal.cliente = cliente
            if data:
                nota_fiscal.data_emissao = data
            nota_fiscal.save(update_fields=['cliente', 'data_emissao'])

        return nota_fiscal, criada

    def _salvar_itens(self, nota: NotaImportada, nota_fiscal, Produto, ItemNotaFiscal) -> int:
        # Remove itens antigos e recria (garante consistência)
        ItemNotaFiscal.objects.filter(nota_fiscal=nota_fiscal).delete()

        criados = 0
        for item in nota.itens:
            try:
                codigo_int = int(item.codigo_produto)
            except (ValueError, TypeError):
                codigo_int = None

            produto, _ = Produto.objects.get_or_create(
                codigo=codigo_int,
                defaults={'descricao': item.descricao},
            )
            # Atualiza descrição se mudou
            if produto.descricao != item.descricao:
                produto.descricao = item.descricao
                produto.save(update_fields=['descricao'])

            ItemNotaFiscal.objects.create(
                nota_fiscal=nota_fiscal,
                produto=produto,
                quantidade=item.quantidade,
            )
            criados += 1

        return criados