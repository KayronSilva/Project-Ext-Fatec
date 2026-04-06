from django.urls import path
from . import views

urlpatterns = [
    # ── Autenticação ──────────────────────────────────────
    path('login/',       views.login_cliente_view, name='login'),
    path('admin-login/', views.login_admin_view,   name='login_admin'),
    path('cadastro/',    views.cadastro_view,       name='cadastro'),
    path('logout/',      views.logout_view,         name='logout'),

    # ── App principal (cliente) ───────────────────────────
    path('',           views.acompanhar_devolucoes, name='acompanhar_devolucoes'),
    path('devolucao/', views.tela_devolucao,        name='tela_devolucao'),
    path('devolucao/<int:devolucao_id>/excluir/', views.excluir_devolucao_cliente, name='excluir_devolucao_cliente'),

    # ── AJAX ──────────────────────────────────────────────
    path('ajax/perfil/',               views.perfil_dados,         name='perfil_dados'),
    path('ajax/perfil/salvar/',        views.perfil_salvar,        name='perfil_salvar'),
    path('ajax/buscar-cliente/',       views.buscar_cliente,       name='buscar_cliente'),
    path('ajax/buscar-notas-cliente/', views.buscar_notas_cliente, name='buscar_notas_cliente'),
    path('ajax/buscar-itens-nota/',    views.buscar_itens_nota,    name='buscar_itens_nota'),

    # ── Painel Administrativo ─────────────────────────────
    path('painel/',                                      views.painel_admin,               name='painel_admin'),
    path('painel/devolucao/<int:devolucao_id>/status/', views.atualizar_status_devolucao, name='atualizar_status_devolucao'),

    # ── Gestão de Usuários ────────────────────────────────
    path('painel/usuarios/',                          views.gestao_usuarios, name='gestao_usuarios'),
    path('painel/usuarios/criar/',                    views.usuario_criar,   name='usuario_criar'),
    path('painel/usuarios/<int:usuario_id>/editar/',  views.usuario_editar,  name='usuario_editar'),
    path('painel/usuarios/<int:usuario_id>/excluir/', views.usuario_excluir, name='usuario_excluir'),

    # ── Importação de Notas Fiscais ───────────────────────
    path('painel/importar/',              views.importar_notas,     name='importar_notas'),
    path('painel/importar/preview-xml/',  views.preview_xml,        name='preview_xml'),
    path('painel/importar/xml/',          views.importar_xml,       name='importar_xml'),
    path('painel/importar/erp/testar/',   views.testar_conexao_erp, name='testar_conexao_erp'),
    path('painel/importar/erp/buscar/',   views.buscar_nota_erp,    name='buscar_nota_erp'),
    path('painel/importar/erp/importar/', views.importar_erp,       name='importar_erp'),
]