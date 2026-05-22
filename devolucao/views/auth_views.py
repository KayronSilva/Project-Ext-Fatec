import logging
from django.shortcuts import redirect, render
from django.contrib import messages, auth

from ..models import ConfiguracaoSistema
from ..forms import LoginForm, CadastroForm

logger = logging.getLogger(__name__)


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

    context = {'form': form, 'error': error}
    try:
        config = ConfiguracaoSistema.objects.first()
        if config and config.whatsapp_numero:
            context['whatsapp_numero'] = config.whatsapp_numero
    except Exception:
        pass

    return render(request, 'auth/login_cliente.html', context)


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

    return render(request, 'auth/login_admin.html', {'form': form, 'error': error})


def cadastro_view(request):
    if request.user.is_authenticated:
        return redirect('acompanhar_devolucoes')

    form = CadastroForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        auth.login(request, usuario)
        messages.success(request, 'Cadastro realizado com sucesso! Bem-vindo(a).')
        return redirect('acompanhar_devolucoes')

    context = {'form': form}
    try:
        config = ConfiguracaoSistema.objects.first()
        if config and config.whatsapp_numero:
            context['whatsapp_numero'] = config.whatsapp_numero
    except Exception:
        pass

    return render(request, 'auth/cadastro.html', context)


def logout_view(request):
    was_staff = request.user.is_staff
    auth.logout(request)
    return redirect('login_admin' if was_staff else 'login')