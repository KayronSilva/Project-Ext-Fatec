import json, re, os
from datetime import date
import pdfplumber
import logging
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction
from django.db.models import Sum, Count, F

from .importacao_service import (
    XMLNFeImporter, NotaFiscalImporter, NotaImportada,
    ItemImportado, get_integration, ERP_REGISTRY,
)

logger = logging.getLogger(__name__)


def _is_ajax_request(request):
    """Verifica se é uma requisição AJAX pelo header X-Requested-With"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


from .models import (
    Cliente, NotaFiscal, Produto, ItemNotaFiscal,
    Devolucao, ItemDevolucao, ConfiguracaoSistema, MOTIVOS_DEVOLUCAO,
)
from .forms import ClienteForm, NotaForm, DevolucaoForm, CadastroForm, LoginForm, AdminCriarForm
from .decorators import (
    admin_required, cliente_required, permission_required_custom,
    cliente_pode_deletar_devolucao,
)

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


# ════════════════════════════════════════════════════════
# Autenticação — Login separado por tipo de usuário
# ════════════════════════════════════════════════════════

def login_view(request):
    """Login de cliente — alias para compatibilidade com links existentes."""
    return login_cliente_view(request)


def login_cliente_view(request):
    """Login exclusivo para clientes (is_staff=False)."""
    if request.user.is_authenticated:
        return redirect('painel_admin' if request.user.is_staff else 'acompanhar_devolucoes')

    form  = LoginForm(request.POST or None, request=request)
    error = None

    if request.method == 'POST':
        if form.is_valid():
            if form.usuario.is_staff:
                error = 'Esta área é exclusiva para clientes. Use o login de administrador.'
            else:
                auth.login(request, form.usuario)
                return redirect(request.GET.get('next', 'acompanhar_devolucoes'))
        else:
            error = form.errors.get('__all__', ['E-mail ou senha incorretos.'])[0]

    return render(request, 'login_cliente.html', {'form': form, 'error': error})


def login_admin_view(request):
    """Login exclusivo para administradores (is_staff=True)."""
    if request.user.is_authenticated:
        return redirect('painel_admin' if request.user.is_staff else 'acompanhar_devolucoes')

    form  = LoginForm(request.POST or None, request=request)
    error = None

    if request.method == 'POST':
        if form.is_valid():
            if not form.usuario.is_staff:
                error = 'Esta área é exclusiva para administradores.'
            else:
                auth.login(request, form.usuario)
                return redirect(request.GET.get('next', 'painel_admin'))
        else:
            error = form.errors.get('__all__', ['E-mail ou senha incorretos.'])[0]

    return render(request, 'login_admin.html', {'form': form, 'error': error})


def cadastro_view(request):
    if request.user.is_authenticated:
        return redirect('acompanhar_devolucoes')

    form = CadastroForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        auth.login(request, usuario)
        messages.success(request, 'Cadastro realizado com sucesso! Bem-vindo(a).')
        return redirect('acompanhar_devolucoes')

    return render(request, 'cadastro.html', {'form': form})


def logout_view(request):
    was_staff = request.user.is_staff
    auth.logout(request)
    return redirect('login_admin' if was_staff else 'login')


# ════════════════════════════════════════════════════════
# Helpers internos
# ════════════════════════════════════════════════════════

def _get_cliente_logado(request):
    """Retorna o Cliente vinculado ao usuário ou None."""
    try:
        return request.user.cliente
    except Exception:
        return None


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


# ════════════════════════════════════════════════════════
# AJAX: busca cliente por CPF ou CNPJ
# ════════════════════════════════════════════════════════

@cliente_required
@require_GET
def buscar_cliente(request):
    documento = re.sub(r'\D', '', request.GET.get('documento', '').strip())

    if not documento:
        return JsonResponse({'encontrado': False, 'nome_exibicao': '', 'tipo': ''})

    cliente_logado = _get_cliente_logado(request)
    if not cliente_logado or cliente_logado.documento != documento:
        return JsonResponse({'encontrado': False, 'nome_exibicao': '', 'tipo': ''}, status=403)

    return JsonResponse({
        'encontrado':    True,
        'tipo':          cliente_logado.tipo,
        'nome_exibicao': cliente_logado.nome_exibicao,
        'razao_social':  cliente_logado.razao_social or cliente_logado.nome or '',
    })


# ════════════════════════════════════════════════════════
# AJAX: busca notas do cliente
# ════════════════════════════════════════════════════════

@cliente_required
@require_GET
def buscar_notas_cliente(request):
    documento = re.sub(r'\D', '', request.GET.get('documento', '').strip())

    cliente = _get_cliente_logado(request)
    if not cliente:
        return JsonResponse({'encontrado': False, 'notas': []}, status=403)
    if cliente.documento != documento:
        return JsonResponse({'encontrado': False, 'notas': []}, status=403)

    notas_qs = (
        NotaFiscal.objects
        .filter(cliente=cliente, itens__isnull=False)
        .distinct()
    )

    if not notas_qs.exists():
        return JsonResponse({
            'encontrado': True,
            'notas': [],
            'aviso': 'Nenhuma nota com itens encontrada para este cliente.',
        })

    notas_ids = list(notas_qs.values_list('id', flat=True))

    orig_map = {
        r['nota_fiscal_id']: r['total']
        for r in ItemNotaFiscal.objects
            .filter(nota_fiscal_id__in=notas_ids)
            .values('nota_fiscal_id')
            .annotate(total=Sum('quantidade'))
    }

    dev_map = {
        r['nf_id']: r['total']
        for r in ItemDevolucao.objects
            .filter(devolucao__nota_fiscal_id__in=notas_ids)
            .values(nf_id=F('devolucao__nota_fiscal_id'))
            .annotate(total=Sum('quantidade_devolvida'))
    }

    notas_objs = {n.pk: n for n in notas_qs}

    notas_list = []
    for nota in notas_objs.values():
        original   = orig_map.get(nota.pk, 0)
        devolvido  = dev_map.get(nota.pk, 0)
        disponivel = max(0, original - devolvido)
        expirado, dias_restantes = _checar_prazo(nota)

        notas_list.append({
            'id':                   nota.pk,
            'numero_nota':          nota.numero_nota,
            'totalmente_devolvida': disponivel == 0,
            'prazo_expirado':       bool(expirado),
            'dias_restantes':       dias_restantes,
            'data_emissao':         nota.data_emissao.strftime('%d/%m/%Y') if nota.data_emissao else None,
        })

    return JsonResponse({'encontrado': True, 'notas': notas_list})


# ════════════════════════════════════════════════════════
# AJAX: busca itens de uma nota
# ════════════════════════════════════════════════════════

@cliente_required
@require_GET
def buscar_itens_nota(request):
    nota_id   = request.GET.get('nota_id', '').strip()
    documento = re.sub(r'\D', '', request.GET.get('documento', '').strip())

    cliente = _get_cliente_logado(request)
    if not cliente:
        return JsonResponse({'encontrado': False, 'itens': [], 'aviso': 'Acesso negado.'}, status=403)
    if cliente.documento != documento:
        return JsonResponse({'encontrado': False, 'itens': [], 'aviso': 'Acesso negado.'}, status=403)

    try:
        nota = NotaFiscal.objects.get(id=nota_id, cliente=cliente)
    except NotaFiscal.DoesNotExist:
        return JsonResponse({'encontrado': False, 'itens': [], 'aviso': 'Nota não encontrada para este cliente.'})

    expirado, dias_restantes = _checar_prazo(nota)
    if expirado:
        prazo = ConfiguracaoSistema.prazo()
        return JsonResponse({
            'encontrado':     False,
            'itens':          [],
            'prazo_expirado': True,
            'aviso': (
                f'O prazo de devolução desta nota expirou. '
                f'O limite é de {prazo} dias após a emissão '
                f'({nota.data_emissao.strftime("%d/%m/%Y")}).'
            ),
        })

    itens = nota.itens.select_related('produto').all()
    if not itens.exists():
        return JsonResponse({'encontrado': False, 'itens': [], 'aviso': 'Nota sem itens cadastrados.'})

    dados = []
    for item in itens:
        ja_devolvido = (
            ItemDevolucao.objects
            .filter(devolucao__nota_fiscal=nota, produto=item.produto)
            .aggregate(total=Sum('quantidade_devolvida'))['total']
        ) or 0

        disponivel = max(0, item.quantidade - ja_devolvido)
        if disponivel == 0:
            continue

        dados.append({
            'id':                    item.produto.id,
            'codigo':                item.produto.codigo,
            'descricao':             item.produto.descricao,
            'quantidade_original':   item.quantidade,
            'quantidade_devolvida':  ja_devolvido,
            'quantidade_disponivel': disponivel,
        })

    if not dados:
        return JsonResponse({
            'encontrado': False, 'itens': [],
            'totalmente_devolvida': True,
            'aviso': 'Todos os itens desta nota já atingiram o limite de devolução.',
        })

    prazo = ConfiguracaoSistema.prazo()
    return JsonResponse({
        'encontrado':     True,
        'itens':          dados,
        'nota_id':        nota.id,
        'dias_restantes': dias_restantes,
        'prazo_dias':     prazo,
        'data_emissao':   nota.data_emissao.strftime('%d/%m/%Y') if nota.data_emissao else None,
    })


# ════════════════════════════════════════════════════════
# Tela de devolução
# ════════════════════════════════════════════════════════

@cliente_required
def tela_devolucao(request):
    # Verifica permissão de criar antes de exibir o formulário
    cliente = _get_cliente_logado(request)
    if cliente and not cliente.tem_permissao('criar'):
        messages.error(request, '⛔ Você não tem permissão para criar devoluções.')
        return redirect('acompanhar_devolucoes')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'enviar':
            cliente_form = ClienteForm(request.POST)
            nota_form    = NotaForm(request.POST, request.FILES)
            return _handle_enviar(request, cliente_form, nota_form)

        if action == 'carregar_pdf':
            return _handle_carregar_pdf(request)

    return render(request, 'devolucao.html', {
        'cliente_form': ClienteForm(),
        'nota_form':    NotaForm(),
        'dev_form':     DevolucaoForm(),
        'produtos':     [],
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
                return render(request, 'devolucao.html', {
                    'cliente_form': cliente_form,
                    'nota_form':    nota_form,
                    'dev_form':     DevolucaoForm(),
                    'produtos':     produtos,
                })

        documento   = re.sub(r'\D', '', cliente_form.cleaned_data['documento'])
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
                return render(request, 'devolucao.html', {
                    'cliente_form': cliente_form,
                    'nota_form':    nota_form,
                    'dev_form':     DevolucaoForm(),
                    'produtos':     produtos,
                })

        erros_foto = []
        for prod in produtos:
            foto_file = request.FILES.get(f'foto_produto_{prod["produto_id"]}')
            if foto_file and foto_file.size > FOTO_MAX_BYTES:
                erros_foto.append(
                    f'Foto de "{prod.get("descricao", prod["produto_id"])}" excede 2 MB.'
                )
        if erros_foto:
            if _is_ajax_request(request):
                return JsonResponse({'success': False, 'errors': erros_foto})
            else:
                for msg in erros_foto:
                    messages.error(request, msg)
                return render(request, 'devolucao.html', {
                    'cliente_form': cliente_form,
                    'nota_form':    nota_form,
                    'dev_form':     DevolucaoForm(),
                    'produtos':     produtos,
                })

        with transaction.atomic():
            erros = []

            ids_produtos = [p['produto_id'] for p in produtos]
            produtos_map = {
                str(obj.pk): obj
                for obj in Produto.objects.select_for_update().filter(id__in=ids_produtos)
            }

            for prod in produtos:
                produto_obj = produtos_map.get(str(prod['produto_id']))
                if not produto_obj:
                    erros.append(f'Produto ID {prod["produto_id"]} não encontrado.')
                    continue

                item_nota = ItemNotaFiscal.objects.filter(
                    nota_fiscal=nota, produto=produto_obj
                ).first()
                if not item_nota:
                    erros.append(
                        f'O produto "{produto_obj.descricao}" não pertence à nota {numero_nota}.'
                    )
                    continue

                ja_devolvido = (
                    ItemDevolucao.objects
                    .filter(devolucao__nota_fiscal=nota, produto=produto_obj)
                    .aggregate(total=Sum('quantidade_devolvida'))['total']
                ) or 0

                disponivel = item_nota.quantidade - ja_devolvido
                if prod['quantidade'] > disponivel:
                    erros.append(
                        f'"{produto_obj.descricao}": solicitado {prod["quantidade"]} un., '
                        f'saldo disponível: {disponivel} un.'
                    )

            if erros:
                raise ValueError('\n'.join(erros))

            devolucao = Devolucao.objects.create(
                nota_fiscal=nota,
                usuario_criador=request.user
            )

            for prod in produtos:
                produto_obj = produtos_map.get(str(prod['produto_id']))

                motivo = prod.get('motivo', '')
                if motivo and motivo not in MOTIVOS_VALIDOS:
                    motivo = ''

                foto_file = request.FILES.get(f'foto_produto_{prod["produto_id"]}')
                logger.info(f"Foto received for product {prod['produto_id']}: {foto_file}")
                ItemDevolucao.objects.create(
                    devolucao=devolucao,
                    produto=produto_obj,
                    quantidade_devolvida=prod['quantidade'],
                    motivo=motivo,
                    observacao=prod.get('observacao', ''),
                    foto=foto_file,
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
            return render(request, 'devolucao.html', {
                'cliente_form': cliente_form,
                'nota_form':    nota_form,
                'dev_form':     DevolucaoForm(),
                'produtos':     produtos if 'produtos' in locals() else [],
            })

    logger.info(f"Devolução #{devolucao.pk} criada com sucesso por {request.user.email}")
    messages.success(request, f'Devolução #{devolucao.pk} registrada com sucesso!')

    if _is_ajax_request(request):
        return JsonResponse({'success': True, 'redirect_url': reverse('acompanhar_devolucoes')})
    else:
        return redirect('tela_devolucao')


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

    cliente_form = ClienteForm(data={
        'documento':     dados['cnpj_cliente'],
        'nome_exibicao': dados['razao_social_cliente'],
    })
    nota_form = NotaForm(data={'numero_nota': dados['numero_nota']})

    messages.success(request, 'PDF carregado com sucesso.')
    return render(request, 'devolucao.html', {
        'cliente_form': cliente_form,
        'nota_form':    nota_form,
        'dev_form':     DevolucaoForm(),
        'produtos':     dados['produtos'],
    })


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


# ════════════════════════════════════════════════════════
# AJAX: excluir devolução (cliente — apenas pendentes)
# ════════════════════════════════════════════════════════

@require_POST
@cliente_required
@cliente_pode_deletar_devolucao
def excluir_devolucao_cliente(request, devolucao_id):
    """
    POST /devolucao/<id>/excluir/
    Permite que o cliente cancele uma devolução PENDENTE.
    O decorador @cliente_pode_deletar_devolucao já valida:
      - status == 'pendente'
      - cliente é o criador
      - cliente tem permissão 'deletar'
    """
    devolucao = get_object_or_404(Devolucao, pk=devolucao_id)
    num = devolucao.pk
    devolucao.delete()
    logger.info(f"Devolução #{num} cancelada pelo cliente {request.user.email}")
    return JsonResponse({'success': True})


# ════════════════════════════════════════════════════════
# AJAX: perfil do usuário logado
# ════════════════════════════════════════════════════════

@cliente_required
@require_GET
def perfil_dados(request):
    usuario = request.user
    cliente = _get_cliente_logado(request)

    dados = {
        'email':        usuario.email,
        'tipo':         cliente.tipo          if cliente else '',
        'nome':         cliente.nome          if cliente else '',
        'razao_social': cliente.razao_social  if cliente else '',
        'telefone':     cliente.telefone      if cliente else '',
        'celular':      cliente.celular       if cliente else '',
        'logradouro':   cliente.logradouro    if cliente else '',
        'numero':       cliente.numero        if cliente else '',
        'complemento':  cliente.complemento   if cliente else '',
        'bairro':       cliente.bairro        if cliente else '',
        'cidade':       cliente.cidade        if cliente else '',
        'estado':       cliente.estado        if cliente else '',
        'cep':          cliente.cep           if cliente else '',
        'documento':    cliente.documento     if cliente else '',
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

    with transaction.atomic():
        if novo_email and novo_email != usuario.email:
            usuario.email = novo_email
            cliente.email = novo_email

        if nova_senha:
            usuario.set_password(nova_senha)

        usuario.save()

        cliente.telefone    = body.get('telefone',    '').strip()
        cliente.celular     = body.get('celular',     '').strip()
        cliente.logradouro  = body.get('logradouro',  '').strip()
        cliente.numero      = body.get('numero',      '').strip()
        cliente.complemento = body.get('complemento', '').strip()
        cliente.bairro      = body.get('bairro',      '').strip()
        cliente.cidade      = body.get('cidade',      '').strip()
        cliente.estado      = body.get('estado',      '').strip()
        cliente.cep         = body.get('cep',         '').strip()
        cliente.save(skip_validation=True)

    if nova_senha:
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, usuario)

    return JsonResponse({'ok': True, 'email': usuario.email})


# ════════════════════════════════════════════════════════
# Acompanhar Devoluções (área do cliente)
# ════════════════════════════════════════════════════════

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
        Devolucao.objects
        .filter(cliente=cliente)
        .select_related('nota_fiscal', 'cliente')
        .prefetch_related('itens__produto')
        .order_by('-data_criacao')
    )

    raw = devolucoes.order_by().values('status').annotate(total=Count('id'))
    por_status = {r['status']: r['total'] for r in raw}
    contagens = {
        'todos':       sum(por_status.values()),
        'pendente':    por_status.get('pendente',    0),
        'em_processo': por_status.get('em_processo', 0),
        'concluido':   por_status.get('concluido',   0),
        'recusada':    por_status.get('recusada',    0),
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
                'pk':           dev.pk,
                'status':       dev.status,
                'numero_nota':  dev.nota_fiscal.numero_nota or '',
                'nome_cliente': dev.cliente.nome_exibicao if dev.cliente else '',
                'documento':    dev.cliente.documento     if dev.cliente else '',
                'tipo_cliente': dev.cliente.tipo          if dev.cliente else '',
                'data_criacao': dev.data_criacao.strftime('%d/%m/%Y'),
                'obs_geral':    dev.observacao_geral or '',
                # Permissões por devolução: só pode editar/deletar se pendente E cliente tem permissão
                'pode_editar':  dev.cliente_pode_editar() and cliente.tem_permissao('editar'),
                'pode_deletar': dev.cliente_pode_editar() and cliente.tem_permissao('deletar'),
                'itens': [
                    {
                        'descricao':      item.produto.descricao or '',
                        'codigo':         item.produto.codigo or '',
                        'quantidade':     item.quantidade_devolvida,
                        'motivo':         item.motivo or '',
                        'motivo_display': item.get_motivo_display() or '',
                        'observacao':     item.observacao or '',
                        'foto_url':       item.foto.url if item.foto else '',
                    }
                    for item in dev.itens.all()
                ],
            }
            for dev in devolucoes_para_json
        ],
        cls=DjangoJSONEncoder,
    )

    return render(request, 'acompanhar_devolucoes.html', {
        'devolucoes':        devolucoes,
        'contagens':         contagens,
        'devolucoes_json':   devolucoes_json,
        'iniciais_usuario':  iniciais_usuario,
        'primeiro_nome':     primeiro_nome,
        'cliente_permissoes': {
            'pode_criar':      cliente.tem_permissao('criar'),
            'pode_visualizar': cliente.tem_permissao('visualizar'),
            'pode_editar':     cliente.tem_permissao('editar'),
            'pode_deletar':    cliente.tem_permissao('deletar'),
        },
    })


# ════════════════════════════════════════════════════════
# Painel Administrativo
# ════════════════════════════════════════════════════════

@admin_required
def painel_admin(request):
    """Dashboard administrativo — exibe e gerencia todas as devoluções."""
    devolucoes = (
        Devolucao.objects
        .select_related('nota_fiscal', 'cliente')
        .prefetch_related('itens__produto')
        .order_by('-data_criacao')
    )

    raw = devolucoes.order_by().values('status').annotate(total=Count('id'))
    por_status = {r['status']: r['total'] for r in raw}
    contagens = {
        'todos':       sum(por_status.values()),
        'pendente':    por_status.get('pendente',    0),
        'em_processo': por_status.get('em_processo', 0),
        'concluido':   por_status.get('concluido',   0),
        'recusada':    por_status.get('recusada',    0),
    }

    devolucoes_json = json.dumps(
        [
            {
                'pk':             dev.pk,
                'status':         dev.status,
                'status_display': dev.get_status_display(),
                'numero_nota':    dev.nota_fiscal.numero_nota or '',
                'nome_cliente':   dev.cliente.nome_exibicao if dev.cliente else '',
                'documento':      dev.cliente.documento     if dev.cliente else '',
                'tipo_cliente':   dev.cliente.tipo          if dev.cliente else '',
                'data_criacao':   dev.data_criacao.strftime('%d/%m/%Y'),
                'obs_geral':      dev.observacao_geral or '',
                'itens': [
                    {
                        'descricao':      item.produto.descricao or '',
                        'codigo':         item.produto.codigo or '',
                        'quantidade':     item.quantidade_devolvida,
                        'motivo':         item.motivo or '',
                        'motivo_display': item.get_motivo_display() or '',
                        'observacao':     item.observacao or '',
                        'foto_url':       item.foto.url if item.foto else '',
                    }
                    for item in dev.itens.all()
                ],
            }
            for dev in devolucoes[:500]
        ],
        cls=DjangoJSONEncoder,
    )

    return render(request, 'Painel_admin.html', {
        'devolucoes':            devolucoes,
        'contagens':             contagens,
        'devolucoes_json':       devolucoes_json,
        'pode_gerenciar_admins': request.user.is_superuser or request.user.has_perm('devolucao.pode_gerenciar_usuarios'),
    })


@require_POST
@admin_required
def atualizar_status_devolucao(request, devolucao_id):
    """AJAX — atualiza o status de uma devolução. Restrito a staff."""
    try:
        body        = json.loads(request.body)
        novo_status = body.get('status', '').strip()
    except (json.JSONDecodeError, TypeError):
        novo_status = request.POST.get('status', '').strip()

    STATUSES_VALIDOS = {'pendente', 'em_processo', 'concluido', 'recusada'}
    if novo_status not in STATUSES_VALIDOS:
        return JsonResponse({'success': False, 'error': 'Status inválido.'}, status=400)

    try:
        devolucao        = Devolucao.objects.get(pk=devolucao_id)
        status_anterior  = devolucao.status
        devolucao.status = novo_status
        devolucao.save(update_fields=['status'])
        logger.info(
            f"Devolução #{devolucao_id}: '{status_anterior}' → '{novo_status}' "
            f"por {request.user.email}"
        )
        return JsonResponse({
            'success':        True,
            'status':         devolucao.status,
            'status_display': devolucao.get_status_display(),
        })
    except Devolucao.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Devolução não encontrada.'}, status=404)


# ════════════════════════════════════════════════════════
# Gestão de Usuários (Clientes + Administradores)
# ════════════════════════════════════════════════════════

ESTADOS_BR = [
    'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS',
    'MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC',
    'SP','SE','TO',
]


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
    # Garante ao menos 'visualizar' para não travar o acesso completamente
    return ','.join(perms_selecionadas) if perms_selecionadas else 'visualizar'


@permission_required_custom('devolucao.pode_gerenciar_usuarios')
def gestao_usuarios(request):
    """Lista clientes e administradores em abas separadas."""
    from .models import Usuario

    admins_qs = Usuario.objects.filter(is_staff=True).order_by('email')
    admins = [
        {
            'usuario':      a,
            'is_superuser': a.is_superuser,
            'permissoes': [
                {'code': c, 'label': l, 'tem': a.is_superuser or a.has_perm(c)}
                for c, l in TODAS_PERMISSOES
            ],
        }
        for a in admins_qs
    ]

    clientes_qs = (
        Usuario.objects
        .filter(is_staff=False)
        .select_related('cliente')
        .order_by('email')
    )
    clientes = []
    for u in clientes_qs:
        try:
            cliente_obj = u.cliente
        except Exception:
            cliente_obj = None
        clientes.append({
            'usuario': u,
            'cliente': cliente_obj,
        })

    return render(request, 'gestao_usuarios.html', {
        'admins':           admins,
        'clientes':         clientes,
        'todas_permissoes': TODAS_PERMISSOES,
    })


@permission_required_custom('devolucao.pode_gerenciar_usuarios')
def usuario_criar(request):
    """Cria um novo usuário — cliente ou administrador."""
    tipo_usuario = request.GET.get('tipo', 'cliente')
    if request.method == 'POST':
        tipo_usuario = request.POST.get('tipo_usuario', 'cliente')

    if request.method == 'POST':
        return _handle_usuario_criar(request, tipo_usuario)

    return render(request, 'gestao_usuarios_form.html', {
        'acao':             'criar',
        'tipo_usuario':     tipo_usuario,
        'todas_permissoes': TODAS_PERMISSOES,
        'estados':          ESTADOS_BR,
        'cliente_data':     {},
    })


def _handle_usuario_criar(request, tipo_usuario):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    email           = request.POST.get('email', '').strip().lower()
    senha           = request.POST.get('senha', '').strip()
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
        cliente_data['tipo']        = tipo_pessoa
        cliente_data['tipo_pessoa'] = tipo_pessoa
        cliente_data['telefone']    = request.POST.get('telefone',    '').strip()
        cliente_data['celular']     = request.POST.get('celular',     '').strip()
        cliente_data['logradouro']  = request.POST.get('logradouro',  '').strip()
        cliente_data['numero']      = request.POST.get('numero',      '').strip()
        cliente_data['complemento'] = request.POST.get('complemento', '').strip()
        cliente_data['bairro']      = request.POST.get('bairro',      '').strip()
        cliente_data['cidade']      = request.POST.get('cidade',      '').strip()
        cliente_data['estado']      = request.POST.get('estado',      '').strip()
        cliente_data['cep']         = request.POST.get('cep',         '').strip()

        if tipo_pessoa == 'PF':
            nome = request.POST.get('nome', '').strip()
            cpf  = re.sub(r'\D', '', request.POST.get('cpf', ''))
            if not nome: erros['nome'] = 'Nome é obrigatório.'
            if not cpf or len(cpf) != 11:
                erros['cpf'] = 'CPF inválido.'
            elif Cliente.objects.filter(cpf=cpf).exists():
                erros['cpf'] = 'CPF já cadastrado.'
            cliente_data['nome'] = nome
            cliente_data['cpf']  = cpf
        else:
            razao_social = request.POST.get('razao_social', '').strip()
            cnpj         = re.sub(r'\D', '', request.POST.get('cnpj', ''))
            if not razao_social: erros['razao_social'] = 'Razão social é obrigatória.'
            if not cnpj or len(cnpj) != 14:
                erros['cnpj'] = 'CNPJ inválido.'
            elif Cliente.objects.filter(cnpj=cnpj).exists():
                erros['cnpj'] = 'CNPJ já cadastrado.'
            cliente_data['razao_social'] = razao_social
            cliente_data['cnpj']         = cnpj

    if erros:
        messages.error(request, 'Corrija os erros abaixo antes de continuar.')
        return render(request, 'gestao_usuarios_form.html', {
            'acao':             'criar',
            'tipo_usuario':     tipo_usuario,
            'todas_permissoes': TODAS_PERMISSOES,
            'estados':          ESTADOS_BR,
            'cliente_data':     cliente_data,
            'erros':            erros,
        })

    with transaction.atomic():
        is_staff = (tipo_usuario == 'admin')
        is_super = is_staff and request.POST.get('is_superuser') == 'on'

        if is_super and not request.user.is_superuser:
            messages.error(
                request,
                '⚠️ Apenas Super Administradores podem criar novos Super Administradores.'
            )
            return render(request, 'gestao_usuarios_form.html', {
                'acao':             'criar',
                'tipo_usuario':     tipo_usuario,
                'todas_permissoes': TODAS_PERMISSOES,
                'estados':          ESTADOS_BR,
                'cliente_data':     cliente_data,
            })

        usuario = User.objects.create_user(
            username=email,
            email=email,
            password=senha,
            is_staff=is_staff,
            is_superuser=is_super,
        )

        if tipo_usuario == 'cliente':
            tipo_pessoa = cliente_data.get('tipo', 'PF')

            # ── Permissões do cliente vindas dos checkboxes ──────────
            permissoes_str = _perms_cliente_from_post(request)

            cliente_kwargs = dict(
                usuario              = usuario,
                email                = email,
                tipo                 = tipo_pessoa,
                telefone             = cliente_data.get('telefone',    ''),
                celular              = cliente_data.get('celular',     ''),
                logradouro           = cliente_data.get('logradouro',  ''),
                numero               = cliente_data.get('numero',      ''),
                complemento          = cliente_data.get('complemento', ''),
                bairro               = cliente_data.get('bairro',      ''),
                cidade               = cliente_data.get('cidade',      ''),
                estado               = cliente_data.get('estado',      ''),
                cep                  = cliente_data.get('cep',         ''),
                permissoes_devolucao = permissoes_str,
            )
            if tipo_pessoa == 'PF':
                cliente_kwargs['nome'] = cliente_data.get('nome', '')
                cliente_kwargs['cpf']  = cliente_data.get('cpf',  '')
            else:
                cliente_kwargs['razao_social'] = cliente_data.get('razao_social', '')
                cliente_kwargs['cnpj']         = cliente_data.get('cnpj', '')

            Cliente.objects.create(**cliente_kwargs)

        elif not is_super:
            perms_sel = request.POST.getlist('permissoes')
            _aplicar_permissoes(usuario, perms_sel)

    logger.info(f"Usuário criado: {email} (tipo={tipo_usuario}) por {request.user.email}")
    messages.success(request, f'Usuário {email} criado com sucesso.')
    return redirect('gestao_usuarios')


@permission_required_custom('devolucao.pode_gerenciar_usuarios')
def usuario_editar(request, usuario_id):
    """Edita um usuário existente — cliente ou administrador."""
    from .models import Usuario
    usuario_editado = get_object_or_404(Usuario, pk=usuario_id)

    # Validação de hierarquia: Super Admin só pode ser editado por Super Admin
    if usuario_editado.is_superuser and not request.user.is_superuser:
        messages.error(
            request,
            '⚠️ Apenas Super Administradores podem editar outros Super Administradores.'
        )
        return redirect('gestao_usuarios')

    if usuario_editado.pk == request.user.pk and not request.user.is_superuser:
        messages.warning(request, 'Para editar seu próprio perfil, use a página de perfil.')
        return redirect('gestao_usuarios')

    tipo_usuario = 'admin' if usuario_editado.is_staff else 'cliente'

    # Tenta carregar dados do cliente vinculado
    try:
        cliente_obj = usuario_editado.cliente
        cliente_data = {
            'nome':                  cliente_obj.nome          or '',
            'razao_social':          cliente_obj.razao_social  or '',
            'cpf':                   cliente_obj.cpf           or '',
            'cnpj':                  cliente_obj.cnpj          or '',
            'tipo':                  cliente_obj.tipo          or 'PF',
            'tipo_pessoa':           cliente_obj.tipo          or 'PF',
            'telefone':              cliente_obj.telefone      or '',
            'celular':               cliente_obj.celular       or '',
            'logradouro':            cliente_obj.logradouro    or '',
            'numero':                cliente_obj.numero        or '',
            'complemento':           cliente_obj.complemento   or '',
            'bairro':                cliente_obj.bairro        or '',
            'cidade':                cliente_obj.cidade        or '',
            'estado':                cliente_obj.estado        or '',
            'cep':                   cliente_obj.cep           or '',
            # ── Permissões do cliente passadas ao template ──────────
            'permissoes_devolucao':  cliente_obj.permissoes_devolucao or 'criar,visualizar,editar,deletar',
        }
    except Exception:
        cliente_obj  = None
        cliente_data = {}

    perms_atuais = [
        {'code': c, 'label': l, 'tem': usuario_editado.is_superuser or usuario_editado.has_perm(c)}
        for c, l in TODAS_PERMISSOES
    ]

    if request.method == 'POST':
        return _handle_usuario_editar(
            request, usuario_editado, tipo_usuario, cliente_obj, perms_atuais, cliente_data
        )

    return render(request, 'gestao_usuarios_form.html', {
        'acao':             'editar',
        'tipo_usuario':     tipo_usuario,
        'usuario_editado':  usuario_editado,
        'cliente_data':     cliente_data,
        'perms_atuais':     perms_atuais,
        'todas_permissoes': TODAS_PERMISSOES,
        'estados':          ESTADOS_BR,
    })


def _handle_usuario_editar(request, usuario_editado, tipo_usuario, cliente_obj, perms_atuais, cliente_data_orig):
    erros = {}

    nova_senha  = request.POST.get('nova_senha',      '').strip()
    confirmar   = request.POST.get('confirmar_senha', '').strip()
    if nova_senha:
        if len(nova_senha) < 8:
            erros['nova_senha'] = 'A senha deve ter no mínimo 8 caracteres.'
        elif nova_senha != confirmar:
            erros['confirmar_senha'] = 'As senhas não coincidem.'

    cliente_data = dict(cliente_data_orig)
    if tipo_usuario == 'cliente' and cliente_obj:
        cliente_data['telefone']    = request.POST.get('telefone',    '').strip()
        cliente_data['celular']     = request.POST.get('celular',     '').strip()
        cliente_data['logradouro']  = request.POST.get('logradouro',  '').strip()
        cliente_data['numero']      = request.POST.get('numero',      '').strip()
        cliente_data['complemento'] = request.POST.get('complemento', '').strip()
        cliente_data['bairro']      = request.POST.get('bairro',      '').strip()
        cliente_data['cidade']      = request.POST.get('cidade',      '').strip()
        cliente_data['estado']      = request.POST.get('estado',      '').strip()
        cliente_data['cep']         = request.POST.get('cep',         '').strip()

        if cliente_obj.tipo == 'PF':
            nome = request.POST.get('nome', '').strip()
            if not nome:
                erros['nome'] = 'Nome é obrigatório.'
            cliente_data['nome'] = nome
        else:
            razao_social = request.POST.get('razao_social', '').strip()
            if not razao_social:
                erros['razao_social'] = 'Razão social é obrigatória.'
            cliente_data['razao_social'] = razao_social

    if erros:
        messages.error(request, 'Corrija os erros abaixo.')
        return render(request, 'gestao_usuarios_form.html', {
            'acao':             'editar',
            'tipo_usuario':     tipo_usuario,
            'usuario_editado':  usuario_editado,
            'cliente_data':     cliente_data,
            'perms_atuais':     perms_atuais,
            'todas_permissoes': TODAS_PERMISSOES,
            'estados':          ESTADOS_BR,
            'erros':            erros,
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
            cliente_obj.telefone    = cliente_data.get('telefone',    '')
            cliente_obj.celular     = cliente_data.get('celular',     '')
            cliente_obj.logradouro  = cliente_data.get('logradouro',  '')
            cliente_obj.numero      = cliente_data.get('numero',      '')
            cliente_obj.complemento = cliente_data.get('complemento', '')
            cliente_obj.bairro      = cliente_data.get('bairro',      '')
            cliente_obj.cidade      = cliente_data.get('cidade',      '')
            cliente_obj.estado      = cliente_data.get('estado',      '')
            cliente_obj.cep         = cliente_data.get('cep',         '')
            if cliente_obj.tipo == 'PF':
                cliente_obj.nome = cliente_data.get('nome', '')
            else:
                cliente_obj.razao_social = cliente_data.get('razao_social', '')

            # ── Salva permissões do cliente vindas dos checkboxes ────
            cliente_obj.permissoes_devolucao = _perms_cliente_from_post(request)

            cliente_obj.save(skip_validation=True)

    logger.info(f"Usuário editado: {usuario_editado.email} por {request.user.email}")
    messages.success(request, f'Usuário {usuario_editado.email} atualizado com sucesso.')
    return redirect('gestao_usuarios')


@require_POST
@permission_required_custom('devolucao.pode_gerenciar_usuarios')
def usuario_excluir(request, usuario_id):
    """Exclui qualquer usuário via AJAX com validação de hierarquia."""
    from .models import Usuario
    usuario_alvo = get_object_or_404(Usuario, pk=usuario_id)

    # Validação 1: não permitir auto-exclusão
    if usuario_alvo.pk == request.user.pk:
        return JsonResponse(
            {'success': False, 'error': 'Você não pode excluir a si mesmo.'},
            status=400
        )

    # Validação 2: Super Admin só pode ser excluído por Super Admin
    if usuario_alvo.is_superuser and not request.user.is_superuser:
        return JsonResponse(
            {'success': False, 'error': 'Apenas Super Administradores podem excluir outros Super Administradores.'},
            status=403
        )

    # Validação 3: não permitir exclusão do último Super Admin
    if usuario_alvo.is_superuser:
        super_admin_count = Usuario.objects.filter(is_superuser=True).count()
        if super_admin_count <= 1:
            return JsonResponse(
                {'success': False, 'error': 'Não é possível excluir o único Super Administrador do sistema.'},
                status=400
            )

    nome  = usuario_alvo.email
    tipo  = 'admin' if usuario_alvo.is_staff else 'cliente'
    usuario_alvo.delete()
    logger.info(f"Usuário excluído: {nome} (tipo={tipo}) por {request.user.email}")
    return JsonResponse({'success': True, 'nome': nome})


# ════════════════════════════════════════════════════════
# Importação de Notas Fiscais
# ════════════════════════════════════════════════════════

@admin_required
def importar_notas(request):
    """Página principal de importação de notas fiscais."""
    notas_recentes = (
        NotaFiscal.objects
        .select_related('cliente')
        .prefetch_related('itens')
        .order_by('-id')[:20]
    )

    historico = [
        {
            'numero_nota':  nota.numero_nota,
            'data_emissao': nota.data_emissao,
            'cliente':      nota.cliente,
            'total_itens':  nota.itens.count(),
            'origem_icon':  '📄',
        }
        for nota in notas_recentes
    ]

    erp_nome = list(ERP_REGISTRY.keys())[0].title() if ERP_REGISTRY else 'ERP'

    return render(request, 'importar_notas.html', {
        'historico': historico,
        'erp_nome':  erp_nome,
    })


@require_POST
@admin_required
def preview_xml(request):
    """
    AJAX — lê o XML enviado e retorna os dados extraídos sem salvar no banco.
    Permite que o admin visualize antes de confirmar a importação.
    """
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
                'numero_nota':       nota.numero_nota,
                'data_emissao':      nota.data_emissao,
                'documento_cliente': nota.documento_cliente,
                'nome_cliente':      nota.nome_cliente,
                'itens': [
                    {
                        'codigo_produto': i.codigo_produto,
                        'descricao':      i.descricao,
                        'quantidade':     i.quantidade,
                    }
                    for i in nota.itens
                ],
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
    """AJAX — recebe os dados do preview e salva no banco."""
    try:
        body = json.loads(request.body)
        nota_data = body.get('nota', {})
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    if not nota_data:
        return JsonResponse({'success': False, 'error': 'Nenhum dado de nota enviado.'}, status=400)

    try:
        nota = NotaImportada(
            numero_nota       = nota_data.get('numero_nota', ''),
            data_emissao      = nota_data.get('data_emissao', ''),
            documento_cliente = nota_data.get('documento_cliente', ''),
            nome_cliente      = nota_data.get('nome_cliente', ''),
            origem            = 'xml',
            itens=[
                ItemImportado(
                    codigo_produto = i.get('codigo_produto', ''),
                    descricao      = i.get('descricao', ''),
                    quantidade     = int(i.get('quantidade', 0)),
                )
                for i in nota_data.get('itens', [])
            ],
        )

        resultado = NotaFiscalImporter().salvar(nota)
        logger.info(
            f"NF importada (XML): {resultado['nota_fiscal'].numero_nota} "
            f"por {request.user.email}"
        )
        return JsonResponse({
            'success':       True,
            'numero_nota':   resultado['nota_fiscal'].numero_nota,
            'cliente':       resultado['cliente'].nome_exibicao,
            'itens_criados': resultado['itens_criados'],
            'criada':        resultado['criada'],
        })
    except Exception as e:
        logger.error(f'Erro ao importar XML: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@admin_required
def testar_conexao_erp(request):
    """AJAX — testa se a integração ERP está acessível."""
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
    """AJAX — busca uma nota no ERP pelo número."""
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
                'numero_nota':       nota.numero_nota,
                'data_emissao':      nota.data_emissao,
                'documento_cliente': nota.documento_cliente,
                'nome_cliente':      nota.nome_cliente,
                'itens': [
                    {'codigo_produto': i.codigo_produto, 'descricao': i.descricao, 'quantidade': i.quantidade}
                    for i in nota.itens
                ],
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
    """AJAX — importa a nota retornada pelo ERP e salva no banco."""
    try:
        body = json.loads(request.body)
        nota_data = body.get('nota', {})
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    if not nota_data:
        return JsonResponse({'success': False, 'error': 'Nenhum dado de nota enviado.'}, status=400)

    try:
        nota = NotaImportada(
            numero_nota       = nota_data.get('numero_nota', ''),
            data_emissao      = nota_data.get('data_emissao', ''),
            documento_cliente = nota_data.get('documento_cliente', ''),
            nome_cliente      = nota_data.get('nome_cliente', ''),
            origem            = nota_data.get('origem', 'erp'),
            itens=[
                ItemImportado(
                    codigo_produto = i.get('codigo_produto', ''),
                    descricao      = i.get('descricao', ''),
                    quantidade     = int(i.get('quantidade', 0)),
                )
                for i in nota_data.get('itens', [])
            ],
        )

        resultado = NotaFiscalImporter().salvar(nota)
        logger.info(
            f"NF importada (ERP): {resultado['nota_fiscal'].numero_nota} "
            f"por {request.user.email}"
        )
        return JsonResponse({
            'success':       True,
            'numero_nota':   resultado['nota_fiscal'].numero_nota,
            'cliente':       resultado['cliente'].nome_exibicao,
            'itens_criados': resultado['itens_criados'],
            'criada':        resultado['criada'],
        })
    except Exception as e:
        logger.error(f'Erro ao importar nota do ERP: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)