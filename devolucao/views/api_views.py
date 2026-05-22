import json
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Sum, Q, Prefetch

from ..models import (
    Cliente, NotaFiscal, ItemNotaFiscal, Devolucao, ItemDevolucao, 
    ConfiguracaoSistema, Usuario, ClienteVinculado,
)
from ..decorators import admin_required, cliente_required, permission_required_custom, cliente_pode_deletar_devolucao
from ..forms import BuscaAvancadaForm
from ..importacao_service import XMLNFeImporter, NotaFiscalImporter, NotaImportada, ItemImportado, get_integration, ERP_REGISTRY
from .mixins import (
    _get_cliente_logado, _get_clientes_vinculados_do_usuario, _serializar_nota,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
# AJAX: Devolução e Perfil do Cliente
# ════════════════════════════════════════════════════════
@require_POST
@cliente_required
@cliente_pode_deletar_devolucao
def excluir_devolucao_cliente(request, devolucao_id):
    devolucao = get_object_or_404(Devolucao, pk=devolucao_id)
    num = devolucao.pk
    devolucao.delete()
    logger.info(f"Devolução #{num} cancelada pelo cliente {request.user.email}")
    return JsonResponse({'success': True})


@cliente_required
@require_GET
def perfil_dados(request):
    usuario = request.user
    cliente = _get_cliente_logado(request)
    dados = {
        'email': usuario.email, 'tipo': cliente.tipo if cliente else '',
        'nome': cliente.nome if cliente else '', 'razao_social': cliente.razao_social if cliente else '',
        'telefone': cliente.telefone if cliente else '', 'celular': cliente.celular if cliente else '',
        'logradouro': cliente.logradouro if cliente else '', 'numero': cliente.numero if cliente else '',
        'complemento': cliente.complemento if cliente else '', 'bairro': cliente.bairro if cliente else '',
        'cidade': cliente.cidade if cliente else '', 'estado': cliente.estado if cliente else '',
        'cep': cliente.cep if cliente else '', 'documento': cliente.documento if cliente else '',
    }
    return JsonResponse(dados)


@cliente_required
@require_POST
def perfil_salvar(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)

    usuario = request.user
    cliente = _get_cliente_logado(request)
    if not cliente:
        return JsonResponse({'ok': False, 'erro': 'Perfil de cliente não encontrado.'}, status=400)

    erros = {}
    novo_email = body.get('email', '').strip().lower()
    if not novo_email:
        erros['email'] = 'E-mail é obrigatório.'
    elif novo_email != usuario.email:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(email=novo_email).exclude(pk=usuario.pk).exists():
            erros['email'] = 'Este e-mail já está em uso.'

    nova_senha = body.get('nova_senha', '').strip()
    confirmar  = body.get('confirmar_senha', '').strip()
    if nova_senha:
        if len(nova_senha) < 8:
            erros['nova_senha'] = 'A senha deve ter no mínimo 8 caracteres.'
        elif nova_senha != confirmar:
            erros['confirmar_senha'] = 'As senhas não coincidem.'

    if not body.get('telefone', '').strip():
        erros['telefone'] = 'Telefone é obrigatório.'

    if erros:
        return JsonResponse({'ok': False, 'erros': erros}, status=422)

    from django.db import transaction
    with transaction.atomic():
        if novo_email and novo_email != usuario.email:
            usuario.email = novo_email
            cliente.email = novo_email
        if nova_senha:
            usuario.set_password(nova_senha)
        usuario.save()

        cliente.telefone    = body.get('telefone', '').strip()
        cliente.celular     = body.get('celular', '').strip()
        cliente.logradouro  = body.get('logradouro', '').strip()
        cliente.numero      = body.get('numero', '').strip()
        cliente.complemento = body.get('complemento', '').strip()
        cliente.bairro      = body.get('bairro', '').strip()
        cliente.cidade      = body.get('cidade', '').strip()
        cliente.estado      = body.get('estado', '').strip()
        cliente.cep         = body.get('cep', '').strip()
        cliente.save(skip_validation=True)

    if nova_senha:
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, usuario)

    return JsonResponse({'ok': True, 'email': usuario.email})


# ════════════════════════════════════════════════════════
# AJAX: Ações do Painel Admin
# ════════════════════════════════════════════════════════
@require_POST
@admin_required
def atualizar_status_devolucao(request, devolucao_id):
    try:
        body = json.loads(request.body)
        novo_status = body.get('status', '').strip()
    except (json.JSONDecodeError, TypeError):
        novo_status = request.POST.get('status', '').strip()

    STATUSES_VALIDOS = {'pendente', 'em_processo', 'concluido', 'recusada'}
    if novo_status not in STATUSES_VALIDOS:
        return JsonResponse({'success': False, 'error': 'Status inválido.'}, status=400)

    try:
        devolucao = Devolucao.objects.get(pk=devolucao_id)
        status_anterior = devolucao.status
        devolucao.status = novo_status
        devolucao.save(update_fields=['status'])
        logger.info(f"Devolução #{devolucao_id}: '{status_anterior}' → '{novo_status}' por {request.user.email}")
        return JsonResponse({'success': True, 'status': devolucao.status, 'status_display': devolucao.get_status_display()})
    except Devolucao.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Devolução não encontrada.'}, status=404)


@require_POST
@admin_required
def salvar_observacao_interna(request, devolucao_id):
    try:
        body = json.loads(request.body)
        obs  = body.get('observacao_interna', '').strip()
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    try:
        devolucao = Devolucao.objects.get(pk=devolucao_id)
        devolucao.observacao_interna = obs
        devolucao.save(update_fields=['observacao_interna'])
        logger.info(f"Obs. interna da devolução #{devolucao_id} atualizada por {request.user.email}")
        return JsonResponse({'success': True, 'observacao_interna': obs})
    except Devolucao.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Devolução não encontrada.'}, status=404)


@require_POST
@admin_required
def salvar_configuracoes(request):
    try:
        whatsapp_numero = request.POST.get('whatsapp_numero', '').strip()
        if whatsapp_numero and not any(c.isdigit() for c in whatsapp_numero):
            return JsonResponse({'success': False, 'error': 'Número de WhatsApp inválido.'}, status=400)

        config, _ = ConfiguracaoSistema.objects.get_or_create(pk=1)
        config.whatsapp_numero = whatsapp_numero if whatsapp_numero else ''
        config.save()

        logger.info(f"Configuração de WhatsApp atualizada: {whatsapp_numero} por {request.user.email}")
        return JsonResponse({'success': True, 'message': 'Configurações salvas com sucesso!', 'whatsapp_numero': config.whatsapp_numero or ''})
    except Exception as e:
        logger.error(f"Erro ao salvar configurações: {str(e)}")
        return JsonResponse({'success': False, 'error': f'Erro ao salvar: {str(e)}'}, status=500)


@require_POST
@permission_required_custom('devolucao.pode_gerenciar_usuarios')
def usuario_excluir(request, usuario_id):
    usuario_alvo = get_object_or_404(Usuario, pk=usuario_id)
    if usuario_alvo.pk == request.user.pk:
        return JsonResponse({'success': False, 'error': 'Você não pode excluir a si mesmo.'}, status=400)
    if usuario_alvo.is_superuser and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Apenas Super Administradores podem excluir outros Super Administradores.'}, status=403)
    if usuario_alvo.is_superuser:
        super_admin_count = Usuario.objects.filter(is_superuser=True).count()
        if super_admin_count <= 1:
            return JsonResponse({'success': False, 'error': 'Não é possível excluir o único Super Administrador do sistema.'}, status=400)

    nome = usuario_alvo.email
    tipo = 'admin' if usuario_alvo.is_staff else 'cliente'
    usuario_alvo.delete()
    logger.info(f"Usuário excluído: {nome} (tipo={tipo}) por {request.user.email}")
    return JsonResponse({'success': True, 'nome': nome})


# ════════════════════════════════════════════════════════
# AJAX: Gerenciar Clientes Vinculados
# ════════════════════════════════════════════════════════
@admin_required
@require_GET
def ajax_listar_clientes_vinculados(request, usuario_id):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    clientes_vinculados = usuario.clientes_vinculados.select_related('cliente').all()
    dados = [{
        'cliente_vinculado_id': cv.id, 'cliente_id': c.id, 'nome_exibicao': c.nome_exibicao,
        'documento': c.documento, 'tipo': c.tipo, 'ativo': cv.ativo,
        'data_vinculacao': cv.data_vinculacao.strftime('%d/%m/%Y %H:%M') if cv.data_vinculacao else '',
    } for cv in clientes_vinculados for c in [cv.cliente]]
    
    return JsonResponse({'success': True, 'clientes': dados})


@admin_required
@require_GET
def ajax_listar_clientes_disponiveis(request, usuario_id):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    termo = request.GET.get('termo', '').strip()
    ja_vinculados = usuario.clientes_vinculados.values_list('cliente_id', flat=True)
    
    clientes_disponiveis = Cliente.objects.exclude(id__in=ja_vinculados)
    if termo:
        clientes_disponiveis = clientes_disponiveis.filter(Q(nome__icontains=termo) | Q(razao_social__icontains=termo) | Q(cpf__icontains=termo) | Q(cnpj__icontains=termo))
    
    dados = [{'cliente_id': c.id, 'nome_exibicao': c.nome_exibicao, 'documento': c.documento, 'tipo': c.tipo} for c in clientes_disponiveis[:20]]
    return JsonResponse({'success': True, 'clientes': dados})


@admin_required
@require_POST
def ajax_vincular_cliente(request, usuario_id):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    try:
        data = json.loads(request.body)
        cliente_id = data.get('cliente_id')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    if not cliente_id:
        return JsonResponse({'success': False, 'error': 'cliente_id é obrigatório'}, status=400)
    
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    if usuario.clientes_vinculados.filter(cliente=cliente).exists():
        return JsonResponse({'success': False, 'error': 'Este cliente já está vinculado'}, status=400)
    
    cv = ClienteVinculado.objects.create(usuario=usuario, cliente=cliente, ativo=True)
    return JsonResponse({
        'success': True,
        'cliente_vinculado': {
            'cliente_vinculado_id': cv.id, 'cliente_id': cliente.id, 'nome_exibicao': cliente.nome_exibicao,
            'documento': cliente.documento, 'tipo': cliente.tipo, 'ativo': cv.ativo,
            'data_vinculacao': cv.data_vinculacao.strftime('%d/%m/%Y %H:%M'),
        }
    })


@admin_required
@require_POST
def ajax_desvinculador_cliente(request, usuario_id, cliente_vinculado_id):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    cv = get_object_or_404(ClienteVinculado, pk=cliente_vinculado_id, usuario=usuario)
    cliente_nome = cv.cliente.nome_exibicao
    cv.delete()
    return JsonResponse({'success': True, 'mensagem': f'Cliente "{cliente_nome}" removido'})


@admin_required
@require_POST
def ajax_toggle_cliente_ativo(request, usuario_id, cliente_vinculado_id):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Acesso negado'}, status=403)
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    cv = get_object_or_404(ClienteVinculado, pk=cliente_vinculado_id, usuario=usuario)
    cv.ativo = not cv.ativo
    cv.save()
    estado = 'ativado' if cv.ativo else 'desativado'
    return JsonResponse({'success': True, 'ativo': cv.ativo, 'mensagem': f'Cliente {estado}'})


# ════════════════════════════════════════════════════════
# AJAX: Importação XML / ERP
# ════════════════════════════════════════════════════════
@require_POST
@admin_required
def preview_xml(request):
    xml_file = request.FILES.get('xml_content')
    if not xml_file:
        return JsonResponse({'success': False, 'error': 'Nenhum arquivo enviado.'}, status=400)
    if xml_file.size > 5 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'Arquivo muito grande (máx 5 MB).'}, status=400)

    try:
        conteudo = xml_file.read()
        nota = XMLNFeImporter().parse(conteudo)
        return JsonResponse({
            'success': True,
            'nota': {
                'numero_nota': nota.numero_nota, 'data_emissao': nota.data_emissao,
                'documento_cliente': nota.documento_cliente, 'nome_cliente': nota.nome_cliente,
                'itens': [{'codigo_produto': i.codigo_produto, 'descricao': i.descricao, 'quantidade': i.quantidade} for i in nota.itens],
                'origem': nota.origem,
            },
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=422)
    except Exception as e:
        logger.error(f'Erro ao fazer preview do XML: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Erro interno ao processar XML.'}, status=500)


@require_POST
@admin_required
def importar_xml(request):
    try:
        body = json.loads(request.body)
        nota_data = body.get('nota', {})
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)
    if not nota_data:
        return JsonResponse({'success': False, 'error': 'Nenhum dado de nota enviado.'}, status=400)

    try:
        nota = NotaImportada(
            numero_nota=nota_data.get('numero_nota', ''), data_emissao=nota_data.get('data_emissao', ''),
            documento_cliente=nota_data.get('documento_cliente', ''), nome_cliente=nota_data.get('nome_cliente', ''),
            origem='xml', itens=[ItemImportado(codigo_produto=i.get('codigo_produto', ''), descricao=i.get('descricao', ''), quantidade=int(i.get('quantidade', 0))) for i in nota_data.get('itens', [])],
        )
        resultado = NotaFiscalImporter().salvar(nota)
        return JsonResponse({'success': True, 'numero_nota': resultado['nota_fiscal'].numero_nota, 'cliente': resultado['cliente'].nome_exibicao, 'itens_criados': resultado['itens_criados'], 'criada': resultado['criada']})
    except Exception as e:
        logger.error(f'Erro ao importar XML: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@admin_required
def testar_conexao_erp(request):
    if not ERP_REGISTRY:
        return JsonResponse({'ok': False, 'mensagem': 'Nenhuma integração configurada.'})
    nome_erp = list(ERP_REGISTRY.keys())[0]
    try:
        integracao = get_integration(nome_erp)
        ok, mensagem = integracao.testar_conexao()
        return JsonResponse({'ok': ok, 'mensagem': mensagem, 'erp': integracao.nome})
    except Exception as e:
        return JsonResponse({'ok': False, 'mensagem': str(e)})


@require_POST
@admin_required
def buscar_nota_erp(request):
    try:
        body = json.loads(request.body)
        numero_nota = body.get('numero_nota', '').strip()
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)
    if not numero_nota:
        return JsonResponse({'success': False, 'error': 'Informe o número da nota.'}, status=400)
    if not ERP_REGISTRY:
        return JsonResponse({'success': False, 'error': 'Nenhuma integração ERP configurada.'})

    nome_erp = list(ERP_REGISTRY.keys())[0]
    try:
        integracao = get_integration(nome_erp)
        nota = integracao.buscar_nota_por_numero(numero_nota)
        if nota is None:
            return JsonResponse({'success': False, 'error': f'Nota "{numero_nota}" não encontrada no ERP.'})
        return JsonResponse({
            'success': True,
            'nota': {
                'numero_nota': nota.numero_nota, 'data_emissao': nota.data_emissao,
                'documento_cliente': nota.documento_cliente, 'nome_cliente': nota.nome_cliente,
                'itens': [{'codigo_produto': i.codigo_produto, 'descricao': i.descricao, 'quantidade': i.quantidade} for i in nota.itens],
                'origem': nota.origem,
            },
        })
    except NotImplementedError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        logger.error(f'Erro ao buscar nota no ERP: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@admin_required
def importar_erp(request):
    try:
        body = json.loads(request.body)
        nota_data = body.get('nota', {})
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)
    if not nota_data:
        return JsonResponse({'success': False, 'error': 'Nenhum dado de nota enviado.'}, status=400)

    try:
        nota = NotaImportada(
            numero_nota=nota_data.get('numero_nota', ''), data_emissao=nota_data.get('data_emissao', ''),
            documento_cliente=nota_data.get('documento_cliente', ''), nome_cliente=nota_data.get('nome_cliente', ''),
            origem=nota_data.get('origem', 'erp'), itens=[ItemImportado(codigo_produto=i.get('codigo_produto', ''), descricao=i.get('descricao', ''), quantidade=int(i.get('quantidade', 0))) for i in nota_data.get('itens', [])],
        )
        resultado = NotaFiscalImporter().salvar(nota)
        return JsonResponse({'success': True, 'numero_nota': resultado['nota_fiscal'].numero_nota, 'cliente': resultado['cliente'].nome_exibicao, 'itens_criados': resultado['itens_criados'], 'criada': resultado['criada']})
    except Exception as e:
        logger.error(f'Erro ao importar nota do ERP: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ════════════════════════════════════════════════════════
# AJAX: Outras buscas
# ════════════════════════════════════════════════════════
@require_GET
@login_required
def ajax_detalhes_nota(request, nota_id):
    nota = get_object_or_404(
        NotaFiscal.objects.select_related('cliente').prefetch_related(
            Prefetch('itens', queryset=ItemNotaFiscal.objects.select_related('produto')),
            Prefetch('devolucoes', queryset=Devolucao.objects.prefetch_related(Prefetch('itens', queryset=ItemDevolucao.objects.select_related('produto')))),
        ), pk=nota_id
    )

    if not request.user.is_staff:
        clientes_vinculados = _get_clientes_vinculados_do_usuario(request.user)
        ids_clientes = {cv.cliente.id for cv in clientes_vinculados}
        if nota.cliente_id not in ids_clientes:
            return JsonResponse({'encontrado': False, 'erro': 'Acesso negado.'}, status=403)

    return JsonResponse({'encontrado': True, 'nota': _serializar_nota(nota)})


@require_POST
@admin_required
def busca_avancada_ajax(request):
    try:
        form = BuscaAvancadaForm(json.loads(request.body))
        if form.is_valid():
            qs = Devolucao.objects.select_related('nota_fiscal', 'cliente').order_by('-data_criacao')
            if form.cleaned_data.get('numero_nota'):
                qs = qs.filter(nota_fiscal__numero_nota__icontains=form.cleaned_data['numero_nota'])
            if form.cleaned_data.get('status'):
                qs = qs.filter(status=form.cleaned_data['status'])
            resultados = [{'id': dev.pk, 'numero_nota': dev.nota_fiscal.numero_nota or '', 'cliente': dev.cliente.nome_exibicao if dev.cliente else '', 'status': dev.get_status_display(), 'data': dev.data_criacao.strftime('%d/%m/%Y')} for dev in qs[:50]]
            return JsonResponse({'success': True, 'resultados': resultados})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    except Exception as e:
        logger.error(f'Erro em busca_avancada_ajax: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)