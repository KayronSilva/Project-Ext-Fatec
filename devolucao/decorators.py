"""
Decorators de autorização para o sistema de devoluções.

Uso:
    @admin_required
    def minha_view(request): ...

    @cliente_required
    def outra_view(request): ...

    @permission_required_custom('devolucao.pode_gerenciar_usuarios')
    def view_restrita(request): ...
    
    @cliente_pode_editar_devolucao
    def editar_devolucao(request, devolucao_id): ...
"""
from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden, JsonResponse
from .models import Devolucao, Cliente


def admin_required(view_func):
    """
    Garante que apenas usuários com is_staff=True acessem a view.
    - Não autenticado       → redireciona para login de admin (ou JSON 401 se AJAX)
    - Autenticado sem staff → redireciona para área do cliente (ou JSON 403 se AJAX)
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if not request.user.is_authenticated:
            if is_ajax:
                return JsonResponse(
                    {'error': 'Sessão expirada', 'session_expired': True},
                    status=401
                )
            return redirect(f'/admin-login/?next={request.path}')
        
        if not request.user.is_staff:
            if is_ajax:
                return JsonResponse(
                    {'error': 'Acesso negado'},
                    status=403
                )
            return redirect('acompanhar_devolucoes')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def cliente_required(view_func):
    """
    Garante que apenas clientes (is_staff=False) acessem a view.
    - Não autenticado → redireciona para login de cliente (ou JSON 401 se AJAX)
    - Admin logado    → redireciona para painel admin (ou JSON 403 se AJAX)
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if not request.user.is_authenticated:
            if is_ajax:
                return JsonResponse(
                    {'error': 'Sessão expirada', 'session_expired': True},
                    status=401
                )
            return redirect(f'/login/?next={request.path}')
        
        if request.user.is_staff:
            if is_ajax:
                return JsonResponse(
                    {'error': 'Acesso negado'},
                    status=403
                )
            return redirect('painel_admin')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def permission_required_custom(perm):
    """
    Verifica se o admin autenticado possui uma permissão específica.
    Superusuários passam automaticamente.

    Uso: @permission_required_custom('devolucao.pode_gerenciar_usuarios')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f'/admin-login/?next={request.path}')
            if not request.user.is_staff:
                return redirect('acompanhar_devolucoes')
            if not (request.user.is_superuser or request.user.has_perm(perm)):
                return HttpResponseForbidden(
                    '<h2>Acesso negado</h2>'
                    '<p>Você não tem permissão para acessar esta página.</p>'
                    '<p><a href="/painel/">Voltar ao painel</a></p>'
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_pode_editar_usuario(view_func):
    """
    Valida hierarquia: Admin comum NÃO pode editar Super Admin.
    
    Uso: @admin_pode_editar_usuario
    def usuario_editar(request, usuario_id): ...
    """
    @wraps(view_func)
    def wrapper(request, usuario_id, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect('login')
        
        # Importar aqui para evitar circular imports
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            usuario_alvo = User.objects.get(pk=usuario_id)
        except User.DoesNotExist:
            return HttpResponseForbidden(
                '<h2>Usuário não encontrado</h2>'
                '<p><a href="/gestao-usuarios/">Voltar</a></p>'
            )
        
        # ── Validação de hierarquia ──────────────────────────
        # Super Admin só pode ser editado por outro Super Admin
        if usuario_alvo.is_superuser and not request.user.is_superuser:
            return HttpResponseForbidden(
                '<h2>Acesso negado</h2>'
                '<p>Apenas Super Administradores podem editar outros Super Administradores.</p>'
                '<p><a href="/gestao-usuarios/">Voltar</a></p>'
            )
        
        # Admin comum não pode ser editado por... bem, pode ser editado por super admin
        # mas admin comum não pode editar super admin (já validado acima)
        
        return view_func(request, usuario_id, *args, **kwargs)
    return wrapper


def admin_pode_excluir_usuario(view_func):
    """
    Valida hierarquia: Admin comum NÃO pode excluir Super Admin.
    Também impede exclusão do último Super Admin.
    
    Uso: @admin_pode_excluir_usuario
    @require_POST
    def usuario_excluir(request, usuario_id): ...
    """
    @wraps(view_func)
    def wrapper(request, usuario_id, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse(
                {'success': False, 'error': 'Acesso negado'},
                status=403
            )
        
        # Importar aqui para evitar circular imports
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            usuario_alvo = User.objects.get(pk=usuario_id)
        except User.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': 'Usuário não encontrado'},
                status=404
            )
        
        # ── Validação 1: Super Admin só pode ser excluído por Super Admin ──
        if usuario_alvo.is_superuser and not request.user.is_superuser:
            return JsonResponse(
                {'success': False, 'error': 'Apenas Super Administradores podem excluir outros Super Administradores'},
                status=403
            )
        
        # ── Validação 2: Não permitir exclusão do último Super Admin ──────
        if usuario_alvo.is_superuser:
            super_admin_count = User.objects.filter(is_superuser=True).count()
            if super_admin_count <= 1:
                return JsonResponse(
                    {'success': False, 'error': 'Não é possível excluir o único Super Administrador do sistema'},
                    status=400
                )
        
        # ── Validação 3: Não permitir auto-exclusão (exceto super admin) ──
        if usuario_alvo.pk == request.user.pk and not request.user.is_superuser:
            return JsonResponse(
                {'success': False, 'error': 'Você não pode excluir a si mesmo'},
                status=400
            )
        
        return view_func(request, usuario_id, *args, **kwargs)
    return wrapper


def cliente_pode_editar_devolucao(view_func):
    """
    Valida se cliente pode editar uma devolução.
    
    Regras:
    - Devolução deve estar em status 'pendente'
    - Cliente só pode editar devoluções que criou
    - Admin pode editar sempre
    
    Uso: @cliente_pode_editar_devolucao
    def editar_devolucao(request, devolucao_id): ...
    
    Passa devolucao_obj no request: request.devolucao_obj
    """
    @wraps(view_func)
    def wrapper(request, devolucao_id, *args, **kwargs):
        try:
            devolucao = Devolucao.objects.get(pk=devolucao_id)
        except Devolucao.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': 'Devolução não encontrada'},
                status=404
            )
        
        # ── Admin pode editar qualquer devolução ──────────────
        if request.user.is_staff:
            request.devolucao_obj = devolucao
            return view_func(request, devolucao_id, *args, **kwargs)
        
        # ── Cliente tem restrições ───────────────────────────
        if not request.user.is_authenticated:
            return redirect('login')
        
        try:
            cliente = request.user.cliente
        except Exception:
            return JsonResponse(
                {'success': False, 'error': 'Perfil de cliente não encontrado'},
                status=400
            )
        
        # Validação 1: Devolução deve estar em 'pendente'
        if not devolucao.cliente_pode_editar():
            return JsonResponse(
                {'success': False, 'error': 'Devoluções enviadas não podem ser editadas. Apenas administradores podem modificá-las.'},
                status=403
            )
        
        # Validação 2: Cliente só pode editar devoluções que criou
        if devolucao.usuario_criador_id != request.user.pk:
            return JsonResponse(
                {'success': False, 'error': 'Você não pode editar devoluções de outros clientes'},
                status=403
            )
        
        # Validação 3: Cliente precisa ter permissão 'editar'
        if not cliente.tem_permissao('editar'):
            return JsonResponse(
                {'success': False, 'error': 'Você não tem permissão para editar devoluções'},
                status=403
            )
        
        request.devolucao_obj = devolucao
        return view_func(request, devolucao_id, *args, **kwargs)
    return wrapper


def cliente_pode_deletar_devolucao(view_func):
    """
    Valida se cliente pode deletar uma devolução.
    
    Regras:
    - Devolução deve estar em status 'pendente'
    - Cliente só pode deletar devoluções que criou
    - Admin pode deletar sempre
    
    Uso: @cliente_pode_deletar_devolucao
    def deletar_devolucao(request, devolucao_id): ...
    """
    @wraps(view_func)
    def wrapper(request, devolucao_id, *args, **kwargs):
        try:
            devolucao = Devolucao.objects.get(pk=devolucao_id)
        except Devolucao.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': 'Devolução não encontrada'},
                status=404
            )
        
        # ── Admin pode deletar qualquer devolução ──────────────
        if request.user.is_staff:
            return view_func(request, devolucao_id, *args, **kwargs)
        
        # ── Cliente tem restrições ───────────────────────────
        if not request.user.is_authenticated:
            return redirect('login')
        
        try:
            cliente = request.user.cliente
        except Exception:
            return JsonResponse(
                {'success': False, 'error': 'Perfil de cliente não encontrado'},
                status=400
            )
        
        # Validação 1: Devolução deve estar em 'pendente'
        if not devolucao.cliente_pode_editar():
            return JsonResponse(
                {'success': False, 'error': 'Devoluções enviadas não podem ser deletadas.'},
                status=403
            )
        
        # Validação 2: Cliente só pode deletar devoluções que criou
        if devolucao.usuario_criador_id != request.user.pk:
            return JsonResponse(
                {'success': False, 'error': 'Você não pode deletar devoluções de outros clientes'},
                status=403
            )
        
        # Validação 3: Cliente precisa ter permissão 'deletar'
        if not cliente.tem_permissao('deletar'):
            return JsonResponse(
                {'success': False, 'error': 'Você não tem permissão para deletar devoluções'},
                status=403
            )
        
        return view_func(request, devolucao_id, *args, **kwargs)
    return wrapper


def cliente_pode_visualizar_devolucao(view_func):
    """
    Valida se cliente pode visualizar uma devolução.
    
    Regras:
    - Cliente só pode visualizar devoluções que criou
    - Admin pode visualizar qualquer uma
    - Cliente precisa ter permissão 'visualizar'
    
    Uso: @cliente_pode_visualizar_devolucao
    def detalhes_devolucao(request, devolucao_id): ...
    """
    @wraps(view_func)
    def wrapper(request, devolucao_id, *args, **kwargs):
        try:
            devolucao = Devolucao.objects.get(pk=devolucao_id)
        except Devolucao.DoesNotExist:
            return JsonResponse(
                {'success': False, 'error': 'Devolução não encontrada'},
                status=404
            )
        
        # ── Admin pode visualizar qualquer devolução ──────────────
        if request.user.is_staff:
            return view_func(request, devolucao_id, *args, **kwargs)
        
        # ── Cliente tem restrições ───────────────────────────
        if not request.user.is_authenticated:
            return redirect('login')
        
        try:
            cliente = request.user.cliente
        except Exception:
            return JsonResponse(
                {'success': False, 'error': 'Perfil de cliente não encontrado'},
                status=400
            )
        
        # Validação 1: Cliente só pode visualizar devoluções que criou
        if devolucao.usuario_criador_id != request.user.pk:
            return JsonResponse(
                {'success': False, 'error': 'Você não pode visualizar devoluções de outros clientes'},
                status=403
            )
        
        # Validação 2: Cliente precisa ter permissão 'visualizar'
        if not cliente.tem_permissao('visualizar'):
            return JsonResponse(
                {'success': False, 'error': 'Você não tem permissão para visualizar devoluções'},
                status=403
            )
        
        return view_func(request, devolucao_id, *args, **kwargs)
    return wrapper