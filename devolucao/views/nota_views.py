import json
import logging
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Sum, F, Q, Prefetch
from django.core.serializers.json import DjangoJSONEncoder

from ..models import (
    NotaFiscal, ItemNotaFiscal, ItemDevolucao, Devolucao, 
    ConfiguracaoSistema, ClienteVinculado,
)
from ..forms import BuscaAvancadaForm
from ..decorators import cliente_required, admin_required
from ..importacao_service import XMLNFeImporter, NotaFiscalImporter, NotaImportada, ItemImportado, get_integration, ERP_REGISTRY
from .mixins import (
    _get_clientes_vinculados_do_usuario, _checar_prazo, _serializar_nota,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
# AJAX: busca info do cliente vinculado (nova API)
# ════════════════════════════════════════════════════════
@cliente_required
@require_GET
def buscar_cliente_vinculado(request):
    cliente_vinculado_id = request.GET.get('cliente_vinculado_id', '').strip()
    if not cliente_vinculado_id:
        return JsonResponse({'encontrado': False}, status=400)

    try:
        cliente_vinculado = ClienteVinculado.objects.get(id=cliente_vinculado_id, usuario=request.user, ativo=True)
        cliente = cliente_vinculado.cliente
    except ClienteVinculado.DoesNotExist:
        return JsonResponse({'encontrado': False}, status=403)

    return JsonResponse({
        'encontrado': True, 'tipo': cliente.tipo, 'nome_exibicao': cliente.nome_exibicao,
        'documento': cliente.documento, 'razao_social_ou_nome': cliente.razao_social or cliente.nome or '',
    })


@cliente_required
@require_GET
def buscar_notas_cliente_vinculado(request):
    cliente_vinculado_id = request.GET.get('cliente_vinculado_id', '').strip()
    logger.info(f"buscar_notas_cliente_vinculado: usuario={request.user.id}, cliente_vinculado_id={cliente_vinculado_id}")

    if not cliente_vinculado_id:
        return JsonResponse({'encontrado': False, 'notas': []}, status=400)

    try:
        cliente_vinculado = ClienteVinculado.objects.get(id=cliente_vinculado_id, usuario=request.user, ativo=True)
    except ClienteVinculado.DoesNotExist:
        return JsonResponse({'encontrado': False, 'notas': []}, status=403)

    cliente = cliente_vinculado.cliente
    notas_qs = NotaFiscal.objects.filter(cliente=cliente, itens__isnull=False).distinct()
    
    if not notas_qs.exists():
        return JsonResponse({'encontrado': True, 'notas': [], 'aviso': 'Nenhuma nota com itens encontrada para este cliente.'})

    notas_ids = list(notas_qs.values_list('id', flat=True))
    orig_map = {r['nota_fiscal_id']: r['total'] for r in ItemNotaFiscal.objects.filter(nota_fiscal_id__in=notas_ids).values('nota_fiscal_id').annotate(total=Sum('quantidade'))}
    dev_map = {r['nf_id']: r['total'] for r in ItemDevolucao.objects.filter(devolucao__nota_fiscal_id__in=notas_ids).values(nf_id=F('devolucao__nota_fiscal_id')).annotate(total=Sum('quantidade_devolvida'))}

    notas_objs = {n.pk: n for n in notas_qs}
    notas_list = []
    expired_count = 0

    for nota in notas_objs.values():
        expirado, dias_restantes = _checar_prazo(nota)
        if expirado:
            expired_count += 1
            continue
        original   = orig_map.get(nota.pk, 0)
        devolvido  = dev_map.get(nota.pk, 0)
        disponivel = max(0, original - devolvido)
        notas_list.append({
            'id': nota.pk, 'numero_nota': nota.numero_nota, 'totalmente_devolvida': disponivel == 0,
            'prazo_expirado': False, 'dias_restantes': dias_restantes,
            'data_emissao': nota.data_emissao.strftime('%d/%m/%Y') if nota.data_emissao else None,
        })

    if not notas_list:
        msg = 'Nenhuma nota disponível para este cliente.'
        if expired_count > 0:
            prazo = ConfiguracaoSistema.prazo()
            msg = f'Nenhuma nota disponível dentro do prazo de {prazo} dias. Todas as {expired_count} nota(s) encontradas estão expiradas.'
        return JsonResponse({'encontrado': True, 'notas': [], 'aviso': msg})

    return JsonResponse({'encontrado': True, 'notas': notas_list})


@cliente_required
@require_GET
def buscar_itens_nota_cliente_vinculado(request):
    cliente_vinculado_id = request.GET.get('cliente_vinculado_id', '').strip()
    nota_id = request.GET.get('nota_id', '').strip()

    if not cliente_vinculado_id or not nota_id:
        return JsonResponse({'encontrado': False, 'itens': []}, status=400)

    try:
        cliente_vinculado = ClienteVinculado.objects.get(id=cliente_vinculado_id, usuario=request.user, ativo=True)
    except ClienteVinculado.DoesNotExist:
        return JsonResponse({'encontrado': False, 'itens': [], 'aviso': 'Acesso negado.'}, status=403)

    cliente = cliente_vinculado.cliente
    try:
        nota = NotaFiscal.objects.get(id=nota_id, cliente=cliente)
    except NotaFiscal.DoesNotExist:
        return JsonResponse({'encontrado': False, 'itens': [], 'aviso': 'Nota não encontrada para este cliente.'})

    expirado, dias_restantes = _checar_prazo(nota)
    if expirado:
        prazo = ConfiguracaoSistema.prazo()
        return JsonResponse({
            'encontrado': False, 'itens': [], 'prazo_expirado': True,
            'aviso': f'O prazo de devolução desta nota expirou. O limite é de {prazo} dias após a emissão ({nota.data_emissao.strftime("%d/%m/%Y")}).',
        })

    itens = nota.itens.select_related('produto').all()
    if not itens.exists():
        return JsonResponse({'encontrado': False, 'itens': [], 'aviso': 'Nota sem itens cadastrados.'})

    dados = []
    for item in itens:
        ja_devolvido = (ItemDevolucao.objects.filter(devolucao__nota_fiscal=nota, produto=item.produto).aggregate(total=Sum('quantidade_devolvida'))['total']) or 0
        disponivel = max(0, item.quantidade - ja_devolvido)
        if disponivel == 0:
            continue
        dados.append({
            'id': item.produto.id, 'codigo': item.produto.codigo, 'descricao': item.produto.descricao,
            'quantidade_original': item.quantidade, 'quantidade_devolvida': ja_devolvido, 'quantidade_disponivel': disponivel,
        })

    if not dados:
        return JsonResponse({'encontrado': False, 'itens': [], 'totalmente_devolvida': True, 'aviso': 'Todos os itens desta nota já atingiram o limite de devolução.'})

    prazo = ConfiguracaoSistema.prazo()
    return JsonResponse({
        'encontrado': True, 'itens': dados, 'nota_id': nota.id,
        'dias_restantes': dias_restantes, 'prazo_dias': prazo,
        'data_emissao': nota.data_emissao.strftime('%d/%m/%Y') if nota.data_emissao else None,
    })


@cliente_required
@require_GET
def buscar_notas_por_filtro_cliente_vinculado(request):
    cliente_vinculado_id = request.GET.get('cliente_vinculado_id', '').strip()
    tipo_busca = request.GET.get('tipo_busca', '').strip().lower()
    termo_busca = request.GET.get('termo_busca', '').strip()

    if not cliente_vinculado_id or tipo_busca not in ['nota', 'produto']:
        return JsonResponse({'encontrado': False, 'notas': [], 'mensagem': 'Parâmetros inválidos.'}, status=400)
    if len(termo_busca) < 2:
        return JsonResponse({'encontrado': False, 'notas': [], 'mensagem': 'Digite pelo menos 2 caracteres.'}, status=400)

    try:
        cliente_vinculado = ClienteVinculado.objects.get(id=cliente_vinculado_id, usuario=request.user, ativo=True)
    except ClienteVinculado.DoesNotExist:
        return JsonResponse({'encontrado': False, 'notas': [], 'mensagem': 'Acesso negado.'}, status=403)
    
    cliente = cliente_vinculado.cliente
    
    if tipo_busca == 'nota':
        notas_qs = NotaFiscal.objects.filter(cliente=cliente, itens__isnull=False).filter(Q(id__icontains=termo_busca) | Q(numero_nota__icontains=termo_busca)).distinct()
    elif tipo_busca == 'produto':
        notas_qs = (NotaFiscal.objects.filter(cliente=cliente, itens__produto__codigo__icontains=termo_busca, itens__isnull=False).distinct() | 
                    NotaFiscal.objects.filter(cliente=cliente, itens__produto__descricao__icontains=termo_busca, itens__isnull=False).distinct())

    if not notas_qs.exists():
        return JsonResponse({'encontrado': False, 'notas': [], 'mensagem': f'Nenhuma nota encontrada para: {termo_busca}', 'tipo_busca': tipo_busca, 'termo_busca': termo_busca})
    
    notas_ids = list(notas_qs.values_list('id', flat=True))
    orig_map = {r['nota_fiscal_id']: r['total'] for r in ItemNotaFiscal.objects.filter(nota_fiscal_id__in=notas_ids).values('nota_fiscal_id').annotate(total=Sum('quantidade'))}
    dev_map = {r['nf_id']: r['total'] for r in ItemDevolucao.objects.filter(devolucao__nota_fiscal_id__in=notas_ids).values(nf_id=F('devolucao__nota_fiscal_id')).annotate(total=Sum('quantidade_devolvida'))}
    
    notas_list = []
    for nota in notas_qs.select_related('cliente').prefetch_related('itens__produto'):
        expirado, dias_restantes = _checar_prazo(nota)
        if expirado:
            continue
        itens = []
        for item in nota.itens.all():
            ja_devolvido = (ItemDevolucao.objects.filter(devolucao__nota_fiscal=nota, produto=item.produto).aggregate(total=Sum('quantidade_devolvida'))['total']) or 0
            disponivel = max(0, item.quantidade - ja_devolvido)
            if tipo_busca == 'produto':
                if not (termo_busca.lower() in item.produto.codigo.lower() or termo_busca.lower() in item.produto.descricao.lower()):
                    continue
            itens.append({'id': item.produto.id, 'codigo': item.produto.codigo, 'descricao': item.produto.descricao, 'quantidade_original': item.quantidade, 'quantidade_devolvida': ja_devolvido, 'quantidade_disponivel': disponivel})
        
        if itens:
            notas_list.append({'id': nota.id, 'numero_nota': nota.numero_nota, 'data_emissao': nota.data_emissao.strftime('%d/%m/%Y') if nota.data_emissao else None, 'dias_restantes': dias_restantes, 'itens': itens})
    
    if not notas_list:
        return JsonResponse({'encontrado': False, 'notas': [], 'mensagem': f'Nenhuma nota com itens disponíveis para: {termo_busca}', 'tipo_busca': tipo_busca, 'termo_busca': termo_busca})
    
    return JsonResponse({'encontrado': True, 'notas': notas_list, 'tipo_busca': tipo_busca, 'termo_busca': termo_busca, 'total': len(notas_list)})


# DEPRECATED
@cliente_required
@require_GET
def buscar_cliente(request):
    return JsonResponse({'encontrado': False, 'nome_exibicao': '', 'tipo': ''}, status=400)

@cliente_required
@require_GET
def buscar_notas_cliente(request):
    return JsonResponse({'encontrado': False, 'notas': []}, status=400)

@cliente_required
@require_GET
def buscar_itens_nota(request):
    return JsonResponse({'encontrado': False, 'itens': []}, status=400)


# ════════════════════════════════════════════════════════
# Templates e Portais baseados em Notas
# ════════════════════════════════════════════════════════
@cliente_required
def minhas_compras(request):
    clientes_vinculados = _get_clientes_vinculados_do_usuario(request.user)
    if not clientes_vinculados:
        from django.contrib import messages
        messages.error(request, '⛔ Nenhuma empresa ou pessoa vinculada à sua conta. Contate o administrador.')
        return redirect('acompanhar_devolucoes')

    ids_clientes = [cv.cliente.id for cv in clientes_vinculados]
    notas_qs = (
        NotaFiscal.objects.filter(cliente_id__in=ids_clientes)
        .select_related('cliente')
        .prefetch_related(
            Prefetch('itens', queryset=ItemNotaFiscal.objects.select_related('produto')),
            Prefetch('devolucoes', queryset=Devolucao.objects.prefetch_related(Prefetch('itens', queryset=ItemDevolucao.objects.select_related('produto')))),
        ).order_by('-data_emissao', '-id')
    )

    notas_list = [_serializar_nota(n) for n in notas_qs[:300]]
    contagens = {
        'todas': len(notas_list), 'ativa': sum(1 for n in notas_list if n['status_calc'] == 'ativa'),
        'devolvida': sum(1 for n in notas_list if n['status_calc'] == 'devolvida'),
        'cancelada': sum(1 for n in notas_list if n['status_calc'] == 'cancelada'),
        'pode_devolver': sum(1 for n in notas_list if n['pode_devolver']),
    }
    notas_json = json.dumps(notas_list, cls=DjangoJSONEncoder)

    try:
        cliente = request.user.cliente
        nome_completo = cliente.nome_exibicao or request.user.email
    except Exception:
        nome_completo = request.user.email

    palavras         = nome_completo.strip().split()
    iniciais_usuario = ''.join(w[0].upper() for w in palavras[:2])
    primeiro_nome    = palavras[0] if palavras else 'Perfil'

    context = {'notas_json': notas_json, 'contagens': contagens, 'iniciais_usuario': iniciais_usuario, 'primeiro_nome': primeiro_nome}
    try:
        config = ConfiguracaoSistema.objects.first()
        if config and config.whatsapp_numero:
            context['whatsapp_numero'] = config.whatsapp_numero
    except Exception:
        pass

    return render(request, 'cliente/minhas_compras.html', context)


@admin_required
def portal_vendas(request):
    notas_qs = (
        NotaFiscal.objects.select_related('cliente')
        .prefetch_related(
            Prefetch('itens', queryset=ItemNotaFiscal.objects.select_related('produto')),
            Prefetch('devolucoes', queryset=Devolucao.objects.prefetch_related(Prefetch('itens', queryset=ItemDevolucao.objects.select_related('produto')))),
        ).order_by('-data_emissao', '-id')
    )

    notas_list = [_serializar_nota(n) for n in notas_qs[:500]]
    contagens = {
        'todas': len(notas_list), 'ativa': sum(1 for n in notas_list if n['status_calc'] == 'ativa'),
        'devolvida': sum(1 for n in notas_list if n['status_calc'] == 'devolvida'),
        'cancelada': sum(1 for n in notas_list if n['status_calc'] == 'cancelada'),
    }
    notas_json = json.dumps(notas_list, cls=DjangoJSONEncoder)
    total_itens_dev = sum(n['total_devolvido'] for n in notas_list)

    return render(request, 'admin/portal_vendas.html', {
        'notas_json': notas_json, 'contagens': contagens, 'total_itens_dev': total_itens_dev,
        'pode_gerenciar_admins': request.user.is_superuser or request.user.has_perm('devolucao.pode_gerenciar_usuarios'),
    })


@admin_required
def importar_notas(request):
    notas_recentes = NotaFiscal.objects.select_related('cliente').prefetch_related('itens').order_by('-id')[:20]
    historico = [{'numero_nota': nota.numero_nota, 'data_emissao': nota.data_emissao, 'cliente': nota.cliente, 'total_itens': nota.itens.count(), 'origem_icon': '📄'} for nota in notas_recentes]
    erp_nome = list(ERP_REGISTRY.keys())[0].title() if ERP_REGISTRY else 'ERP'
    return render(request, 'admin/importar_notas.html', {'historico': historico, 'erp_nome': erp_nome})


@admin_required
def busca_avancada(request):
    form = BuscaAvancadaForm(request.GET or None)
    devolucoes = None

    if form.is_valid() and any(form.cleaned_data.values()):
        qs = Devolucao.objects.select_related('nota_fiscal', 'cliente').prefetch_related('itens__produto').order_by('-data_criacao')
        if form.cleaned_data.get('numero_nota'):
            qs = qs.filter(nota_fiscal__numero_nota__icontains=form.cleaned_data['numero_nota'])
        if form.cleaned_data.get('numero_devolucao'):
            qs = qs.filter(pk=form.cleaned_data['numero_devolucao'])
        if form.cleaned_data.get('email_cliente'):
            qs = qs.filter(cliente__usuario__email__icontains=form.cleaned_data['email_cliente'])
        if form.cleaned_data.get('status'):
            qs = qs.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('motivo'):
            qs = qs.filter(itens__motivo=form.cleaned_data['motivo']).distinct()
        if form.cleaned_data.get('data_inicio'):
            qs = qs.filter(data_criacao__date__gte=form.cleaned_data['data_inicio'])
        if form.cleaned_data.get('data_fim'):
            qs = qs.filter(data_criacao__date__lte=form.cleaned_data['data_fim'])
        devolucoes = qs[:100]

    return render(request, 'busca_avancada.html', {
        'form': form, 'devolucoes': devolucoes,
        'total_resultados': len(devolucoes) if devolucoes else 0,
    })