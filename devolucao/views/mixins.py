import json, re, os
from datetime import date
import pdfplumber
import logging
from django.db.models import Sum
from django.core.serializers.json import DjangoJSONEncoder

from ..models import (
    NotaFiscal, ItemNotaFiscal, Devolucao, ItemDevolucao, 
    ConfiguracaoSistema, MOTIVOS_DEVOLUCAO, ClienteVinculado,
)

logger = logging.getLogger(__name__)

# ── Constantes globais ────────────────────────────────
MOTIVOS_VALIDOS = {m[0] for m in MOTIVOS_DEVOLUCAO}
FOTO_MAX_BYTES  = 2 * 1024 * 1024   # 2 MB por foto
PDF_MAX_BYTES   = 5 * 1024 * 1024   # 5 MB por PDF

TODAS_PERMISSOES = [
    ('devolucao.pode_criar_devolucao',      'Criar devoluções'),
    ('devolucao.pode_editar_devolucao',     'Editar devoluções'),
    ('devolucao.pode_excluir_devolucao',    'Excluir devoluções'),
    ('devolucao.pode_ver_todas_devolucoes', 'Ver todas as devoluções'),
    ('devolucao.pode_gerenciar_usuarios',   'Gerenciar usuários/admins'),
]

ESTADOS_BR = [
    'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS',
    'MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC',
    'SP','SE','TO',
]


# ════════════════════════════════════════════════════════
# Helpers internos
# ════════════════════════════════════════════════════════

def _is_ajax_request(request):
    """Verifica se é uma requisição AJAX pelo header X-Requested-With"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _get_cliente_logado(request):
    """Retorna o Cliente vinculado ao usuário ou None."""
    try:
        return request.user.cliente
    except Exception:
        return None


def _get_clientes_vinculados_do_usuario(usuario):
    """Retorna lista de ClienteVinculado ativos para um usuário."""
    clientes_queryset = (
        usuario.clientes_vinculados
        .filter(ativo=True)
        .select_related('cliente')
    )
    return sorted(clientes_queryset, key=lambda cv: cv.cliente.nome_exibicao)


def _quantidade_disponivel(nota_id: int, produto_id: int) -> int:
    original = (
        ItemNotaFiscal.objects
        .filter(nota_fiscal_id=nota_id, produto_id=produto_id)
        .values_list('quantidade', flat=True)
        .first()
    ) or 0

    ja_devolvido = (
        ItemDevolucao.objects
        .filter(devolucao__nota_fiscal_id=nota_id, produto_id=produto_id)
        .aggregate(total=Sum('quantidade_devolvida'))['total']
    ) or 0

    return max(0, original - ja_devolvido)


def _checar_prazo(nota):
    if not nota.data_emissao:
        return None, None
    prazo = ConfiguracaoSistema.prazo()
    delta = (date.today() - nota.data_emissao).days
    dias_restantes = prazo - delta
    expirado = delta > prazo
    return expirado, dias_restantes


def _extrair_dados_pdf(caminho_pdf):
    dados = {'numero_nota': '', 'cnpj_cliente': '', 'razao_social_cliente': '', 'produtos': []}
    with pdfplumber.open(caminho_pdf) as pdf:
        texto = ' '.join(page.extract_text() or '' for page in pdf.pages)

    m = re.search(r'NF-e\s+Nº\.\s*(\d{3}\.\d{3}\.\d{3})', texto)
    if m:
        dados['numero_nota'] = m.group(1).replace('.', '')

    m = re.search(r'CNPJ\s*/\s*CPF\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', texto)
    if m:
        dados['cnpj_cliente'] = re.sub(r'\D', '', m.group(1))

    m = re.search(r'NOME\s*/\s*RAZÃO SOCIAL\s*(.*?)\s*CNPJ', texto)
    if m:
        dados['razao_social_cliente'] = m.group(1).strip()

    for match in re.findall(
        r'(\d{6})\s+([A-Z0-9\-\. ]+?)\s+\d{8}\s+\d{4}\s+\d{4}\s+UN\s+(\d{1,3},\d{4})', texto
    ):
        dados['produtos'].append({
            'codigo':     int(match[0]),
            'descricao':  match[1].strip(),
            'quantidade': int(float(match[2].replace(',', '.'))),
            'motivo':     '',
            'observacao': '',
        })

    return dados


def _serializar_nota(nota, ids_clientes=None):
    """Serializa NotaFiscal para dict compatível com o frontend."""
    itens_originais = list(nota.itens.all())
    total_original  = sum(i.quantidade for i in itens_originais)

    devolvidos_map = {}
    for dev in nota.devolucoes.all():
        for item_dev in dev.itens.all():
            pid = item_dev.produto_id
            devolvidos_map[pid] = devolvidos_map.get(pid, 0) + item_dev.quantidade_devolvida

    total_devolvido = sum(devolvidos_map.values())
    disponivel      = max(0, total_original - total_devolvido)

    expirado = None
    dias_restantes = None
    if nota.data_emissao:
        prazo = ConfiguracaoSistema.prazo()
        delta = (date.today() - nota.data_emissao).days
        dias_restantes = prazo - delta
        expirado = delta > prazo

    itens_json = []
    for item in itens_originais:
        devolvido_item = devolvidos_map.get(item.produto_id, 0)
        itens_json.append({
            'produto_id':            item.produto_id,
            'codigo':                item.produto.codigo    if item.produto else '',
            'descricao':             item.produto.descricao if item.produto else '',
            'quantidade_original':   item.quantidade,
            'quantidade_devolvida':  devolvido_item,
            'quantidade_disponivel': max(0, item.quantidade - devolvido_item),
        })

    if disponivel == 0 and total_original > 0:
        status_calc = 'devolvida'
    elif nota.status in ('cancelada',):
        status_calc = 'cancelada'
    else:
        status_calc = 'ativa'

    devolucoes_json = []
    for dev in nota.devolucoes.all():
        devolucoes_json.append({
            'pk':     dev.pk,
            'status': dev.status,
            'status_display': dev.get_status_display(),
            'data':   dev.data_criacao.strftime('%d/%m/%Y'),
        })

    return {
        'id':              nota.pk,
        'numero_nota':     nota.numero_nota or '',
        'data_emissao':    nota.data_emissao.strftime('%d/%m/%Y') if nota.data_emissao else '—',
        'status':          nota.status,
        'status_calc':     status_calc,
        'valor_total':     float(nota.valor_total) if nota.valor_total else None,
        'cliente_id':      nota.cliente_id,
        'cliente_nome':    nota.cliente.nome_exibicao if nota.cliente else '—',
        'cliente_doc':     nota.cliente.documento     if nota.cliente else '—',
        'total_itens':     total_original,
        'total_devolvido': total_devolvido,
        'disponivel':      disponivel,
        'expirado':        expirado,
        'dias_restantes':  dias_restantes,
        'itens':           itens_json,
        'devolucoes':      devolucoes_json,
        'pode_devolver':   (not expirado) and disponivel > 0 and nota.status != 'cancelada',
    }


def _aplicar_permissoes(usuario, perms_codigos):
    """Aplica exatamente as permissões marcadas, removendo as desmarcadas."""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    ct             = ContentType.objects.get_for_model(Devolucao)
    codigos_limpos = [p.split('.')[-1] for p in perms_codigos]
    perms_qs       = Permission.objects.filter(content_type=ct, codename__in=codigos_limpos)
    usuario.user_permissions.set(perms_qs)


def _perms_cliente_from_post(request):
    """Lê os checkboxes de permissão do cliente e retorna string separada por vírgula."""
    perms_selecionadas = []
    for perm in ['criar', 'visualizar', 'editar', 'deletar']:
        if request.POST.get(f'perm_{perm}'):
            perms_selecionadas.append(perm)
    return ','.join(perms_selecionadas) if perms_selecionadas else 'visualizar'