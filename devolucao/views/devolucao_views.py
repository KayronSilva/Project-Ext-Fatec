import json
import logging
import os
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Sum, Count

from ..models import (
    ClienteVinculado, Produto, NotaFiscal, ItemNotaFiscal, Devolucao, ItemDevolucao, 
    ConfiguracaoSistema, Cliente,
)
from ..forms import ClienteForm, NotaForm, DevolucaoForm, DevolucaoClienteForm
from ..decorators import cliente_required
from .mixins import (
    _is_ajax_request, _get_clientes_vinculados_do_usuario, _get_cliente_logado,
    _checar_prazo, _extrair_dados_pdf, MOTIVOS_VALIDOS, FOTO_MAX_BYTES, PDF_MAX_BYTES,
)

logger = logging.getLogger(__name__)


@cliente_required
def tela_devolucao(request):
    cliente_vinculados = _get_clientes_vinculados_do_usuario(request.user)

    if not cliente_vinculados:
        messages.error(request, '⛔ Nenhuma empresa ou pessoa vinculada à sua conta. Contate o administrador.')
        return redirect('acompanhar_devolucoes')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'enviar':
            dev_form = DevolucaoClienteForm(data=request.POST, files=request.FILES, usuario=request.user)
            return _handle_enviar_novo(request, dev_form)

        if action == 'carregar_pdf':
            return _handle_carregar_pdf(request)

    try:
        config = ConfiguracaoSistema.objects.first()
        whatsapp_numero = config.whatsapp_numero if config else None
    except Exception:
        whatsapp_numero = None

    return render(request, 'cliente/devolucao.html', {
        'devolucao_form': DevolucaoClienteForm(usuario=request.user),
        'dev_form':       DevolucaoForm(),
        'produtos':       [],
        'whatsapp_numero': whatsapp_numero,
    })


def _handle_enviar(request, cliente_form, nota_form):
    try:
        logger.info("Iniciando processamento de envio de devolução")
        produtos_json = request.POST.get('produtos_json', '[]')
        produtos = json.loads(produtos_json)

        if not produtos:
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': ['Adicione pelo menos um produto antes de enviar.']})
            else:
                messages.error(request, 'Adicione pelo menos um produto antes de enviar.')
                return redirect('tela_devolucao')

        if not (cliente_form.is_valid() and nota_form.is_valid()):
            if _is_ajax_request(request):
                errors = []
                for form in [cliente_form, nota_form]:
                    for field, field_errors in form.errors.items():
                        errors.extend(field_errors)
                return JsonResponse({'success': False, 'errors': errors})
            else:
                messages.error(request, 'Verifique os campos do formulário.')
                try:
                    config = ConfiguracaoSistema.objects.first()
                    whatsapp_numero = config.whatsapp_numero if config else None
                except Exception:
                    whatsapp_numero = None
                return render(request, 'cliente/devolucao.html', {
                    'cliente_form': cliente_form, 'nota_form': nota_form,
                    'dev_form': DevolucaoForm(), 'produtos': produtos, 'whatsapp_numero': whatsapp_numero,
                })

        documento   = __import__('re').sub(r'\D', '', cliente_form.cleaned_data['documento'])
        numero_nota = nota_form.cleaned_data['numero_nota']

        if len(documento) == 11:
            cliente = Cliente.objects.get(cpf=documento)
        else:
            cliente = Cliente.objects.get(cnpj=documento)

        nota = NotaFiscal.objects.get(numero_nota=numero_nota, cliente=cliente)

        pdf_file = nota_form.cleaned_data.get('arquivo_pdf')
        if pdf_file:
            nota.arquivo_pdf = pdf_file
            nota.save(update_fields=['arquivo_pdf'])

        expirado, _ = _checar_prazo(nota)
        if expirado:
            prazo = ConfiguracaoSistema.prazo()
            error_msg = f'O prazo de devolução da nota {numero_nota} expirou ({prazo} dias após emissão).'
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': [error_msg]})
            else:
                messages.error(request, error_msg)
                try:
                    config = ConfiguracaoSistema.objects.first()
                    whatsapp_numero = config.whatsapp_numero if config else None
                except Exception:
                    whatsapp_numero = None
                return render(request, 'cliente/devolucao.html', {
                    'cliente_form': cliente_form, 'nota_form': nota_form,
                    'dev_form': DevolucaoForm(), 'produtos': produtos, 'whatsapp_numero': whatsapp_numero,
                })

        erros_foto = []
        for prod in produtos:
            foto_file = request.FILES.get(f'foto_produto_{prod["produto_id"]}')
            if foto_file and foto_file.size > FOTO_MAX_BYTES:
                erros_foto.append(f'Foto de "{prod.get("descricao", prod["produto_id"])}" excede 2 MB.')
        if erros_foto:
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': erros_foto})
            else:
                for msg in erros_foto:
                    messages.error(request, msg)
                try:
                    config = ConfiguracaoSistema.objects.first()
                    whatsapp_numero = config.whatsapp_numero if config else None
                except Exception:
                    whatsapp_numero = None
                return render(request, 'cliente/devolucao.html', {
                    'cliente_form': cliente_form, 'nota_form': nota_form,
                    'dev_form': DevolucaoForm(), 'produtos': produtos, 'whatsapp_numero': whatsapp_numero,
                })

        with transaction.atomic():
            erros = []
            ids_produtos = [p['produto_id'] for p in produtos]
            produtos_map = {str(obj.pk): obj for obj in Produto.objects.select_for_update().filter(id__in=ids_produtos)}

            for prod in produtos:
                produto_obj = produtos_map.get(str(prod['produto_id']))
                if not produto_obj:
                    erros.append(f'Produto ID {prod["produto_id"]} não encontrado.')
                    continue

                item_nota = ItemNotaFiscal.objects.filter(nota_fiscal=nota, produto=produto_obj).first()
                if not item_nota:
                    erros.append(f'O produto "{produto_obj.descricao}" não pertence à nota {numero_nota}.')
                    continue

                ja_devolvido = (ItemDevolucao.objects.filter(devolucao__nota_fiscal=nota, produto=produto_obj).aggregate(total=Sum('quantidade_devolvida'))['total']) or 0
                disponivel = item_nota.quantidade - ja_devolvido
                if prod['quantidade'] > disponivel:
                    erros.append(f'"{produto_obj.descricao}": solicitado {prod["quantidade"]} un., saldo disponível: {disponivel} un.')

            if erros:
                raise ValueError('\n'.join(erros))

            devolucao = Devolucao.objects.create(nota_fiscal=nota, usuario_criador=request.user)

            for prod in produtos:
                produto_obj = produtos_map.get(str(prod['produto_id']))
                motivo = prod.get('motivo', '')
                if motivo and motivo not in MOTIVOS_VALIDOS:
                    motivo = ''
                foto_file = request.FILES.get(f'foto_produto_{prod["produto_id"]}')
                logger.info(f"Foto received for product {prod['produto_id']}: {foto_file}")
                ItemDevolucao.objects.create(
                    devolucao=devolucao, produto=produto_obj, quantidade_devolvida=prod['quantidade'],
                    motivo=motivo, observacao=prod.get('observacao', ''), foto=foto_file,
                )
                logger.info(f"ItemDevolucao created for product {prod['produto_id']}")

            if erros:
                raise ValueError('\n'.join(erros))

    except Exception as exc:
        logger.error(f"Erro geral em _handle_enviar: {exc}", exc_info=True)
        if _is_ajax_request(request):
            return JsonResponse({'success': False, 'errors': [str(exc)]})
        else:
            messages.error(request, str(exc))
            try:
                config = ConfiguracaoSistema.objects.first()
                whatsapp_numero = config.whatsapp_numero if config else None
            except Exception:
                whatsapp_numero = None
            return render(request, 'cliente/devolucao.html', {
                'cliente_form': cliente_form, 'nota_form': nota_form,
                'dev_form': DevolucaoForm(), 'produtos': produtos if 'produtos' in locals() else [],
                'whatsapp_numero': whatsapp_numero,
            })

    logger.info(f"Devolução #{devolucao.pk} criada com sucesso por {request.user.email}")
    messages.success(request, f'Devolução #{devolucao.pk} registrada com sucesso!')

    if _is_ajax_request(request):
        return JsonResponse({'success': True, 'redirect_url': reverse('acompanhar_devolucoes')})
    else:
        return redirect('tela_devolucao')


def _handle_enviar_novo(request, dev_form):
    """Handler nova para enviar devolução usando DevolucaoClienteForm."""
    try:
        logger.info("Iniciando _handle_enviar_novo (nova API)")
        produtos_json = request.POST.get('produtos_json', '[]')
        produtos = json.loads(produtos_json)

        if not produtos:
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': ['Adicione pelo menos um produto antes de enviar.']})
            else:
                messages.error(request, 'Adicione pelo menos um produto antes de enviar.')
                return redirect('tela_devolucao')

        if not dev_form.is_valid():
            errors = []
            for field, field_errors in dev_form.errors.items():
                errors.extend(field_errors)
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': errors})
            else:
                for err in errors:
                    messages.error(request, err)
                return redirect('tela_devolucao')

        cliente_vinculado_id = dev_form.cleaned_data['cliente_vinculado'].id
        numero_nota = dev_form.cleaned_data['numero_nota']

        try:
            cliente_vinculado = ClienteVinculado.objects.get(id=cliente_vinculado_id, usuario=request.user, ativo=True)
        except ClienteVinculado.DoesNotExist:
            error_msg = 'Empresa ou pessoa selecionada não é válida para esta conta.'
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': [error_msg]}, status=403)
            else:
                messages.error(request, error_msg)
                return redirect('tela_devolucao')

        cliente = cliente_vinculado.cliente

        if not cliente.tem_permissao('criar'):
            error_msg = '⛔ Você não tem permissão para criar devoluções.'
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': [error_msg]}, status=403)
            else:
                messages.error(request, error_msg)
                return redirect('acompanhar_devolucoes')

        try:
            nota = NotaFiscal.objects.get(numero_nota=numero_nota, cliente=cliente)
        except NotaFiscal.DoesNotExist:
            error_msg = f'Nota fiscal {numero_nota} não encontrada para esta empresa/pessoa.'
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': [error_msg]})
            else:
                messages.error(request, error_msg)
                return redirect('tela_devolucao')

        pdf_file = dev_form.cleaned_data.get('arquivo_pdf')
        if pdf_file:
            nota.arquivo_pdf = pdf_file
            nota.save(update_fields=['arquivo_pdf'])

        expirado, _ = _checar_prazo(nota)
        if expirado:
            prazo = ConfiguracaoSistema.prazo()
            error_msg = f'O prazo de devolução da nota {numero_nota} expirou ({prazo} dias após emissão).'
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': [error_msg]})
            else:
                messages.error(request, error_msg)
                return redirect('tela_devolucao')

        erros_foto = []
        for prod in produtos:
            foto_file = request.FILES.get(f'foto_produto_{prod["produto_id"]}')
            if foto_file and foto_file.size > FOTO_MAX_BYTES:
                erros_foto.append(f'Foto de "{prod.get("descricao", prod["produto_id"])}" excede 2 MB.')
        if erros_foto:
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': erros_foto})
            else:
                for msg in erros_foto:
                    messages.error(request, msg)
                return redirect('tela_devolucao')

        with transaction.atomic():
            erros = []
            ids_produtos = [p['produto_id'] for p in produtos]
            produtos_map = {str(obj.pk): obj for obj in Produto.objects.select_for_update().filter(id__in=ids_produtos)}

            for prod in produtos:
                produto_obj = produtos_map.get(str(prod['produto_id']))
                if not produto_obj:
                    erros.append(f'Produto ID {prod["produto_id"]} não encontrado.')
                    continue
                item_nota = ItemNotaFiscal.objects.filter(nota_fiscal=nota, produto=produto_obj).first()
                if not item_nota:
                    erros.append(f'O produto "{produto_obj.descricao}" não pertence à nota {numero_nota}.')
                    continue
                ja_devolvido = (ItemDevolucao.objects.filter(devolucao__nota_fiscal=nota, produto=produto_obj).aggregate(total=Sum('quantidade_devolvida'))['total']) or 0
                disponivel = item_nota.quantidade - ja_devolvido
                if prod['quantidade'] > disponivel:
                    erros.append(f'"{produto_obj.descricao}": solicitado {prod["quantidade"]} un., saldo disponível: {disponivel} un.')

            if erros:
                raise ValueError('\n'.join(erros))

            devolucao = Devolucao.objects.create(nota_fiscal=nota, cliente=cliente, usuario_criador=request.user)

            for prod in produtos:
                produto_obj = produtos_map.get(str(prod['produto_id']))
                motivo = prod.get('motivo', '')
                if motivo and motivo not in MOTIVOS_VALIDOS:
                    motivo = ''
                foto_file = request.FILES.get(f'foto_produto_{prod["produto_id"]}')
                ItemDevolucao.objects.create(
                    devolucao=devolucao, produto=produto_obj, quantidade_devolvida=prod['quantidade'],
                    motivo=motivo, observacao=prod.get('observacao', ''), foto=foto_file,
                )

    except Exception as exc:
        logger.error(f"Erro em _handle_enviar_novo: {exc}", exc_info=True)
        error_msg = str(exc)
        if _is_ajax_request(request):
            return JsonResponse({'success': False, 'errors': [error_msg]})
        else:
            messages.error(request, error_msg)
            return redirect('tela_devolucao')

    logger.info(f"Devolução #{devolucao.pk} criada com sucesso por {request.user.email} usando nova API")
    messages.success(request, f'Devolução #{devolucao.pk} registrada com sucesso!')

    if _is_ajax_request(request):
        return JsonResponse({'success': True, 'redirect_url': reverse('acompanhar_devolucoes')})
    else:
        return redirect('acompanhar_devolucoes')


def _handle_carregar_pdf(request):
    if 'arquivo_pdf' not in request.FILES:
        messages.error(request, 'Nenhum PDF enviado.')
        return redirect('tela_devolucao')

    pdf_file = request.FILES['arquivo_pdf']

    if pdf_file.size > PDF_MAX_BYTES:
        messages.error(request, 'PDF não pode exceder 5 MB.')
        return redirect('tela_devolucao')

    path      = default_storage.save('temp/' + pdf_file.name, pdf_file)
    full_path = os.path.join(default_storage.location, path)

    dados = _extrair_dados_pdf(full_path)

    cliente_form = ClienteForm(data={'documento': dados['cnpj_cliente'], 'nome_exibicao': dados['razao_social_cliente']})
    nota_form = NotaForm(data={'numero_nota': dados['numero_nota']})

    try:
        config = ConfiguracaoSistema.objects.first()
        whatsapp_numero = config.whatsapp_numero if config else None
    except Exception:
        whatsapp_numero = None

    messages.success(request, 'PDF carregado com sucesso.')
    return render(request, 'cliente/devolucao.html', {
        'cliente_form': cliente_form, 'nota_form': nota_form,
        'dev_form': DevolucaoForm(), 'produtos': dados['produtos'], 'whatsapp_numero': whatsapp_numero,
    })


@cliente_required
def acompanhar_devolucoes(request):
    """Área do cliente para acompanhar suas devoluções."""
    cliente = _get_cliente_logado(request)
    if not cliente:
        return redirect('login')

    if not cliente.tem_permissao('visualizar'):
        messages.error(request, '⛔ Você não tem permissão para visualizar devoluções.')
        return redirect('acompanhar_devolucoes')

    devolucoes = (
        Devolucao.objects.filter(cliente=cliente)
        .select_related('nota_fiscal', 'cliente')
        .prefetch_related('itens__produto')
        .order_by('-data_criacao')
    )

    raw = devolucoes.order_by().values('status').annotate(total=Count('id'))
    por_status = {r['status']: r['total'] for r in raw}
    contagens = {
        'todos': sum(por_status.values()),
        'pendente': por_status.get('pendente', 0),
        'em_processo': por_status.get('em_processo', 0),
        'concluido': por_status.get('concluido', 0),
        'recusada': por_status.get('recusada', 0),
    }

    try:
        nome_completo = cliente.nome_exibicao or request.user.email
    except Exception:
        nome_completo = request.user.email

    palavras         = nome_completo.strip().split()
    iniciais_usuario = ''.join(w[0].upper() for w in palavras[:2])
    primeiro_nome    = palavras[0] if palavras else 'Perfil'

    devolucoes_para_json = devolucoes[:200]

    devolucoes_json = json.dumps(
        [
            {
                'pk': dev.pk, 'status': dev.status,
                'numero_nota': dev.nota_fiscal.numero_nota or '',
                'nome_cliente': dev.cliente.nome_exibicao if dev.cliente else '',
                'documento': dev.cliente.documento if dev.cliente else '',
                'tipo_cliente': dev.cliente.tipo if dev.cliente else '',
                'data_criacao': dev.data_criacao.strftime('%d/%m/%Y'),
                'obs_geral': dev.observacao_geral or '',
                'pode_editar': dev.cliente_pode_editar() and cliente.tem_permissao('editar'),
                'pode_deletar': dev.cliente_pode_editar() and cliente.tem_permissao('deletar'),
                'itens': [
                    {
                        'descricao': item.produto.descricao or '', 'codigo': item.produto.codigo or '',
                        'quantidade': item.quantidade_devolvida, 'motivo': item.motivo or '',
                        'motivo_display': item.get_motivo_display() or '', 'observacao': item.observacao or '',
                        'foto_url': item.foto.url if item.foto else '',
                    }
                    for item in dev.itens.all()
                ],
            }
            for dev in devolucoes_para_json
        ],
        cls=DjangoJSONEncoder,
    )

    context = {
        'devolucoes': devolucoes, 'contagens': contagens, 'devolucoes_json': devolucoes_json,
        'iniciais_usuario': iniciais_usuario, 'primeiro_nome': primeiro_nome,
        'cliente_permissoes': {
            'pode_criar': cliente.tem_permissao('criar'), 'pode_visualizar': cliente.tem_permissao('visualizar'),
            'pode_editar': cliente.tem_permissao('editar'), 'pode_deletar': cliente.tem_permissao('deletar'),
        },
    }

    try:
        config = ConfiguracaoSistema.objects.first()
        if config and config.whatsapp_numero:
            context['whatsapp_numero'] = config.whatsapp_numero
    except Exception:
        pass

    return render(request, 'cliente/acompanhar_devolucoes.html', context)