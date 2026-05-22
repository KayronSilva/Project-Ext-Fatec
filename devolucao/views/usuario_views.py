import re
import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.core.serializers.json import DjangoJSONEncoder

from ..models import Usuario, Cliente, Devolucao, ConfiguracaoSistema
from ..decorators import admin_required, permission_required_custom
from .mixins import (
    TODAS_PERMISSOES, ESTADOS_BR, _aplicar_permissoes, _perms_cliente_from_post,
)

logger = logging.getLogger(__name__)


@admin_required
def painel_admin(request):
    devolucoes = Devolucao.objects.select_related('nota_fiscal', 'cliente').prefetch_related('itens__produto').order_by('-data_criacao')
    raw = devolucoes.order_by().values('status').annotate(total=Count('id'))
    por_status = {r['status']: r['total'] for r in raw}
    contagens = { 
        'todos': sum(por_status.values()), 'pendente': por_status.get('pendente', 0),
        'em_processo': por_status.get('em_processo', 0), 'concluido': por_status.get('concluido', 0),
        'recusada': por_status.get('recusada', 0),
    }

    devolucoes_json = json.dumps(
        [
            {
                'pk': dev.pk, 'status': dev.status, 'status_display': dev.get_status_display(),
                'numero_nota': dev.nota_fiscal.numero_nota or '', 'nome_cliente': dev.cliente.nome_exibicao if dev.cliente else '',
                'documento': dev.cliente.documento if dev.cliente else '', 'tipo_cliente': dev.cliente.tipo if dev.cliente else '',
                'data_criacao': dev.data_criacao.strftime('%d/%m/%Y'), 'obs_geral': dev.observacao_geral or '',
                'obs_interna': dev.observacao_interna or '',
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
            for dev in devolucoes[:500]
        ],
        cls=DjangoJSONEncoder,
    )

    try:
        config = ConfiguracaoSistema.objects.first()
    except Exception:
        config = None

    return render(request, 'admin/Painel_admin.html', {
        'devolucoes': devolucoes, 'contagens': contagens, 'devolucoes_json': devolucoes_json,
        'pode_gerenciar_admins': request.user.is_superuser or request.user.has_perm('devolucao.pode_gerenciar_usuarios'),
        'configuracao': config,
    })


@permission_required_custom('devolucao.pode_gerenciar_usuarios')
def gestao_usuarios(request):
    admins_qs = Usuario.objects.filter(is_staff=True).order_by('email')
    admins = [
        {
            'usuario': a, 'is_superuser': a.is_superuser,
            'permissoes': [{'code': c, 'label': l, 'tem': a.is_superuser or a.has_perm(c)} for c, l in TODAS_PERMISSOES],
        }
        for a in admins_qs
    ]

    clientes_qs = Usuario.objects.filter(is_staff=False).select_related('cliente').order_by('email')
    clientes = []
    for u in clientes_qs:
        try:
            cliente_obj = u.cliente
        except Exception:
            cliente_obj = None
        clientes.append({'usuario': u, 'cliente': cliente_obj})

    return render(request, 'admin/gestao_usuarios.html', {
        'admins': admins, 'clientes': clientes, 'todas_permissoes': TODAS_PERMISSOES,
    })


@permission_required_custom('devolucao.pode_gerenciar_usuarios')
def usuario_criar(request):
    tipo_usuario = request.GET.get('tipo', 'cliente')
    if request.method == 'POST':
        tipo_usuario = request.POST.get('tipo_usuario', 'cliente')
        return _handle_usuario_criar(request, tipo_usuario)

    return render(request, 'admin/gestao_usuarios_form.html', {
        'acao': 'criar', 'tipo_usuario': tipo_usuario,
        'todas_permissoes': TODAS_PERMISSOES, 'estados': ESTADOS_BR, 'cliente_data': {},
    })


def _handle_usuario_criar(request, tipo_usuario):
    User = get_user_model()

    email = request.POST.get('email', '').strip().lower()
    senha = request.POST.get('senha', '').strip()
    confirmar_senha = request.POST.get('confirmar_senha', '').strip()

    erros = {}
    if not email:
        erros['email'] = 'E-mail é obrigatório.'
    elif User.objects.filter(email=email).exists():
        erros['email'] = 'Este e-mail já está cadastrado.'
    if not senha:
        erros['senha'] = 'Senha é obrigatória.'
    elif len(senha) < 8:
        erros['senha'] = 'A senha deve ter no mínimo 8 caracteres.'
    elif senha != confirmar_senha:
        erros['confirmar_senha'] = 'As senhas não coincidem.'

    cliente_data = {}
    if tipo_usuario == 'cliente':
        tipo_pessoa = request.POST.get('tipo_pessoa', 'PF')
        cliente_data['tipo'] = tipo_pessoa
        cliente_data['tipo_pessoa'] = tipo_pessoa
        for field in ['telefone', 'celular', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep']:
            cliente_data[field] = request.POST.get(field, '').strip()

        if tipo_pessoa == 'PF':
            nome = request.POST.get('nome', '').strip()
            cpf = re.sub(r'\D', '', request.POST.get('cpf', ''))
            if not nome: erros['nome'] = 'Nome é obrigatório.'
            if not cpf or len(cpf) != 11: erros['cpf'] = 'CPF inválido.'
            elif Cliente.objects.filter(cpf=cpf).exists(): erros['cpf'] = 'CPF já cadastrado.'
            cliente_data['nome'] = nome
            cliente_data['cpf'] = cpf
        else:
            razao_social = request.POST.get('razao_social', '').strip()
            cnpj = re.sub(r'\D', '', request.POST.get('cnpj', ''))
            if not razao_social: erros['razao_social'] = 'Razão social é obrigatória.'
            if not cnpj or len(cnpj) != 14: erros['cnpj'] = 'CNPJ inválido.'
            elif Cliente.objects.filter(cnpj=cnpj).exists(): erros['cnpj'] = 'CNPJ já cadastrado.'
            cliente_data['razao_social'] = razao_social
            cliente_data['cnpj'] = cnpj

    if erros:
        messages.error(request, 'Corrija os erros abaixo antes de continuar.')
        return render(request, 'admin/gestao_usuarios_form.html', {
            'acao': 'criar', 'tipo_usuario': tipo_usuario,
            'todas_permissoes': TODAS_PERMISSOES, 'estados': ESTADOS_BR,
            'cliente_data': cliente_data, 'erros': erros,
        })

    with transaction.atomic():
        is_staff = (tipo_usuario == 'admin')
        is_super = is_staff and request.POST.get('is_superuser') == 'on'

        if is_super and not request.user.is_superuser:
            messages.error(request, '⚠️ Apenas Super Administradores podem criar novos Super Administradores.')
            return render(request, 'admin/gestao_usuarios_form.html', {
                'acao': 'criar', 'tipo_usuario': tipo_usuario,
                'todas_permissoes': TODAS_PERMISSOES, 'estados': ESTADOS_BR, 'cliente_data': cliente_data,
            })

        usuario = User.objects.create_user(username=email, email=email, password=senha, is_staff=is_staff, is_superuser=is_super)

        if tipo_usuario == 'cliente':
            tipo_pessoa = cliente_data.get('tipo', 'PF')
            permissoes_str = _perms_cliente_from_post(request)
            cliente_kwargs = dict(
                usuario=usuario, email=email, tipo=tipo_pessoa,
                telefone=cliente_data.get('telefone', ''), celular=cliente_data.get('celular', ''),
                logradouro=cliente_data.get('logradouro', ''), numero=cliente_data.get('numero', ''),
                complemento=cliente_data.get('complemento', ''), bairro=cliente_data.get('bairro', ''),
                cidade=cliente_data.get('cidade', ''), estado=cliente_data.get('estado', ''),
                cep=cliente_data.get('cep', ''), permissoes_devolucao=permissoes_str,
            )
            if tipo_pessoa == 'PF':
                cliente_kwargs['nome'] = cliente_data.get('nome', '')
                cliente_kwargs['cpf'] = cliente_data.get('cpf', '')
            else:
                cliente_kwargs['razao_social'] = cliente_data.get('razao_social', '')
                cliente_kwargs['cnpj'] = cliente_data.get('cnpj', '')
            Cliente.objects.create(**cliente_kwargs)

        elif not is_super:
            perms_sel = request.POST.getlist('permissoes')
            _aplicar_permissoes(usuario, perms_sel)

    logger.info(f"Usuário criado: {email} (tipo={tipo_usuario}) por {request.user.email}")
    messages.success(request, f'Usuário {email} criado com sucesso.')
    return redirect('gestao_usuarios')


@permission_required_custom('devolucao.pode_gerenciar_usuarios')
def usuario_editar(request, usuario_id):
    usuario_editado = get_object_or_404(Usuario, pk=usuario_id)

    if usuario_editado.is_superuser and not request.user.is_superuser:
        messages.error(request, '⚠️ Apenas Super Administradores podem editar outros Super Administradores.')
        return redirect('gestao_usuarios')

    if usuario_editado.pk == request.user.pk and not request.user.is_superuser:
        messages.warning(request, 'Para editar seu próprio perfil, use a página de perfil.')
        return redirect('gestao_usuarios')

    tipo_usuario = 'admin' if usuario_editado.is_staff else 'cliente'

    try:
        cliente_obj = usuario_editado.cliente
        cliente_data = {
            'nome': cliente_obj.nome or '', 'razao_social': cliente_obj.razao_social or '',
            'cpf': cliente_obj.cpf or '', 'cnpj': cliente_obj.cnpj or '',
            'tipo': cliente_obj.tipo or 'PF', 'tipo_pessoa': cliente_obj.tipo or 'PF',
            'telefone': cliente_obj.telefone or '', 'celular': cliente_obj.celular or '',
            'logradouro': cliente_obj.logradouro or '', 'numero': cliente_obj.numero or '',
            'complemento': cliente_obj.complemento or '', 'bairro': cliente_obj.bairro or '',
            'cidade': cliente_obj.cidade or '', 'estado': cliente_obj.estado or '',
            'cep': cliente_obj.cep or '', 'permissoes_devolucao': cliente_obj.permissoes_devolucao or 'criar,visualizar,editar,deletar',
        }
    except Exception:
        cliente_obj  = None
        cliente_data = {}

    perms_atuais = [
        {'code': c, 'label': l, 'tem': usuario_editado.is_superuser or usuario_editado.has_perm(c)}
        for c, l in TODAS_PERMISSOES
    ]

    if request.method == 'POST':
        return _handle_usuario_editar(request, usuario_editado, tipo_usuario, cliente_obj, perms_atuais, cliente_data)

    return render(request, 'admin/gestao_usuarios_form.html', {
        'acao': 'editar', 'tipo_usuario': tipo_usuario, 'usuario_editado': usuario_editado,
        'cliente_data': cliente_data, 'perms_atuais': perms_atuais,
        'todas_permissoes': TODAS_PERMISSOES, 'estados': ESTADOS_BR,
    })


def _handle_usuario_editar(request, usuario_editado, tipo_usuario, cliente_obj, perms_atuais, cliente_data_orig):
    erros = {}

    nova_senha  = request.POST.get('nova_senha', '').strip()
    confirmar   = request.POST.get('confirmar_senha', '').strip()
    if nova_senha:
        if len(nova_senha) < 8:
            erros['nova_senha'] = 'A senha deve ter no mínimo 8 caracteres.'
        elif nova_senha != confirmar:
            erros['confirmar_senha'] = 'As senhas não coincidem.'

    cliente_data = dict(cliente_data_orig)
    if tipo_usuario == 'cliente' and cliente_obj:
        for field in ['telefone', 'celular', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep']:
            cliente_data[field] = request.POST.get(field, '').strip()

        if cliente_obj.tipo == 'PF':
            nome = request.POST.get('nome', '').strip()
            if not nome: erros['nome'] = 'Nome é obrigatório.'
            cliente_data['nome'] = nome
        else:
            razao_social = request.POST.get('razao_social', '').strip()
            if not razao_social: erros['razao_social'] = 'Razão social é obrigatória.'
            cliente_data['razao_social'] = razao_social

    if erros:
        messages.error(request, 'Corrija os erros abaixo.')
        return render(request, 'admin/gestao_usuarios_form.html', {
            'acao': 'editar', 'tipo_usuario': tipo_usuario, 'usuario_editado': usuario_editado,
            'cliente_data': cliente_data, 'perms_atuais': perms_atuais,
            'todas_permissoes': TODAS_PERMISSOES, 'estados': ESTADOS_BR, 'erros': erros,
        })

    with transaction.atomic():
        if nova_senha:
            usuario_editado.set_password(nova_senha)

        if tipo_usuario == 'admin':
            is_super = request.POST.get('is_superuser') == 'on'
            usuario_editado.is_superuser = is_super
            usuario_editado.save(update_fields=['password', 'is_superuser'] if nova_senha else ['is_superuser'])
            if is_super:
                usuario_editado.user_permissions.clear()
            else:
                perms_sel = request.POST.getlist('permissoes')
                _aplicar_permissoes(usuario_editado, perms_sel)
        else:
            usuario_editado.save(update_fields=['password'] if nova_senha else [])

        if tipo_usuario == 'cliente' and cliente_obj:
            for field in ['telefone', 'celular', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep']:
                setattr(cliente_obj, field, cliente_data.get(field, ''))
            if cliente_obj.tipo == 'PF':
                cliente_obj.nome = cliente_data.get('nome', '')
            else:
                cliente_obj.razao_social = cliente_data.get('razao_social', '')

            cliente_obj.permissoes_devolucao = _perms_cliente_from_post(request)
            cliente_obj.save(skip_validation=True)

    logger.info(f"Usuário editado: {usuario_editado.email} por {request.user.email}")
    messages.success(request, f'Usuário {usuario_editado.email} atualizado com sucesso.')
    return redirect('gestao_usuarios')