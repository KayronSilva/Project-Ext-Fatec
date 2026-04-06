from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Devolucao, ItemDevolucao, Cliente, NotaFiscal,
    Produto, ItemNotaFiscal, ConfiguracaoSistema,
)


# ════════════════════════════════════════════════════════
# ConfiguracaoSistema
# ════════════════════════════════════════════════════════

@admin.register(ConfiguracaoSistema)
class ConfiguracaoSistemaAdmin(admin.ModelAdmin):
    list_display = ('prazo_devolucao_dias',)


# ════════════════════════════════════════════════════════
# Devolucao
# ════════════════════════════════════════════════════════

class ItemDevolucaoInline(admin.TabularInline):
    model         = ItemDevolucao
    extra         = 0
    can_delete    = False
    # Apenas campos que existem no model ItemDevolucao
    readonly_fields = ('produto', 'quantidade_devolvida', 'motivo', 'observacao', 'foto_thumb')
    fields          = ('produto', 'quantidade_devolvida', 'motivo', 'observacao', 'foto_thumb')

    def foto_thumb(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="height:48px;border-radius:4px;object-fit:cover;">',
                obj.foto.url,
            )
        return '—'
    foto_thumb.short_description = 'Foto'


@admin.register(Devolucao)
class DevolucaoAdmin(admin.ModelAdmin):
    # ── Campos exibidos na lista ──────────────────────────
    list_display  = ('id', 'get_cliente', 'nota_fiscal', 'status_badge', 'get_itens_count', 'usuario_criador', 'data_criacao')
    list_filter   = ('status', 'data_criacao')
    search_fields = ('cliente__nome', 'cliente__cpf', 'cliente__cnpj', 'nota_fiscal__numero_nota', 'usuario_criador__email')
    
    # ── Campos readonly (não podem ser editados) ──────────
    readonly_fields = ('data_criacao', 'cliente', 'nota_fiscal', 'usuario_criador', 'pode_ser_editada_display')
    
    # ── Campos exibidos no formulário ────────────────────
    fieldsets = (
        ('Informações da Devolução', {
            'fields': ('nota_fiscal', 'cliente', 'usuario_criador', 'data_criacao')
        }),
        ('Status e Observações', {
            'fields': ('status', 'observacao_geral', 'pode_ser_editada_display')
        }),
    )
    
    list_per_page   = 30
    inlines         = [ItemDevolucaoInline]
    actions         = ['aprovar_devolucoes', 'concluir_devolucoes', 'recusar_devolucoes']

    # ── Campos calculados ────────────────────────────────

    def get_cliente(self, obj):
        return obj.cliente.nome_exibicao if obj.cliente else '—'
    get_cliente.short_description = 'Cliente'
    get_cliente.admin_order_field = 'cliente__nome'

    def get_itens_count(self, obj):
        return obj.itens.count()
    get_itens_count.short_description = 'Itens'

    def pode_ser_editada_display(self, obj):
        """Exibe se a devolução pode ser editada."""
        pode = obj.pode_ser_editada
        cor = '#28a745' if pode else '#dc3545'
        texto = 'Sim, pode ser editada' if pode else 'Não, foi enviada'
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            cor, texto
        )
    pode_ser_editada_display.short_description = 'Pode ser editada?'

    def status_badge(self, obj):
        # Status corretos conforme STATUS_DEVOLUCAO em models.py
        cores = {
            'pendente':    '#e07b00',
            'em_processo': '#1a6aff',
            'concluido':   '#1a7a4a',
            'recusada':    '#c0392b',
        }
        cor = cores.get(obj.status, '#888')
        return format_html(
            '<span style="color:#fff;background:{};padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600">{}</span>',
            cor,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    # ── Ações em massa ───────────────────────────────────

    @admin.action(description='▶ Mover selecionadas para Em Processo')
    def aprovar_devolucoes(self, request, queryset):
        updated = queryset.filter(status='pendente').update(status='em_processo')
        self.message_user(request, f'{updated} devolução(ões) movidas para Em Processo.')

    @admin.action(description='✓ Marcar selecionadas como Concluídas')
    def concluir_devolucoes(self, request, queryset):
        updated = queryset.filter(status='em_processo').update(status='concluido')
        self.message_user(request, f'{updated} devolução(ões) marcadas como Concluídas.')

    @admin.action(description='✗ Recusar selecionadas')
    def recusar_devolucoes(self, request, queryset):
        # Status correto é 'recusada'
        updated = queryset.filter(status__in=['pendente', 'em_processo']).update(status='recusada')
        self.message_user(request, f'{updated} devolução(ões) recusadas.')


# ════════════════════════════════════════════════════════
# Cliente (ATUALIZADO - com permissões)
# ════════════════════════════════════════════════════════

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display    = ('id', 'nome_exibicao', 'tipo', 'documento_display', 'email', 'cidade', 'estado', 'permissoes_display')
    list_filter     = ('tipo', 'estado')
    search_fields   = ('nome', 'razao_social', 'cpf', 'cnpj', 'email')
    readonly_fields = ('documento_display',)
    
    # ── Fieldsets para melhor organização ──────────────
    fieldsets = (
        ('Identificação', {
            'fields': ('usuario', 'tipo', 'documento_display')
        }),
        ('Dados Pessoais', {
            'fields': ('nome', 'cpf') if True else ('razao_social', 'cnpj'),
        }),
        ('Contato', {
            'fields': ('email', 'telefone', 'celular'),
        }),
        ('Endereço', {
            'fields': (
                ('logradouro', 'numero'),
                ('complemento', 'bairro'),
                ('cidade', 'estado', 'cep'),
                'endereco',  # Campo legado
            ),
            'classes': ('collapse',),  # Collapsível
        }),
        ('Permissões de Devolução', {
            'fields': ('permissoes_devolucao',),
            'description': 'Quais ações o cliente pode fazer? Separe por vírgula: criar, visualizar, editar, deletar',
        }),
    )

    def documento_display(self, obj):
        return obj.documento or '—'
    documento_display.short_description = 'CPF / CNPJ'

    def permissoes_display(self, obj):
        """Exibe as permissões de forma visual."""
        if not obj.permissoes_devolucao:
            return format_html('<span style="color:#999">Nenhuma</span>')
        
        perms = obj.permissoes_devolucao.split(',')
        cores = {
            'criar': '#007bff',
            'visualizar': '#28a745',
            'editar': '#ffc107',
            'deletar': '#dc3545',
        }
        
        html = ''
        for perm in perms:
            perm = perm.strip()
            cor = cores.get(perm, '#6c757d')
            html += format_html(
                '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;margin-right:4px;font-size:11px;font-weight:bold">{}</span>',
                cor, perm.upper()
            )
        return format_html(html)
    permissoes_display.short_description = 'Permissões'


# ════════════════════════════════════════════════════════
# NotaFiscal
# ════════════════════════════════════════════════════════

@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display  = ('id', 'numero_nota', 'cliente', 'data_emissao', 'total_itens')
    list_filter   = ('data_emissao',)
    search_fields = ('numero_nota', 'cliente__nome', 'cliente__cnpj', 'cliente__cpf')
    raw_id_fields = ('cliente',)
    
    def total_itens(self, obj):
        return obj.itens.count()
    total_itens.short_description = 'Itens'


# ════════════════════════════════════════════════════════
# Produto
# ════════════════════════════════════════════════════════

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display  = ('id', 'codigo', 'descricao')
    search_fields = ('codigo', 'descricao')