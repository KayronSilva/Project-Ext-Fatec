import re
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils import timezone


# ════════════════════════════════════════════════════════
# Validadores de CPF e CNPJ
# ════════════════════════════════════════════════════════

def _only_digits(value: str) -> str:
    return re.sub(r'\D', '', value or '')


def validar_cpf(cpf: str):
    """Valida CPF usando o algoritmo dos dois dígitos verificadores."""
    cpf = _only_digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValidationError('CPF inválido.')

    for i, peso_inicio in enumerate([10, 11]):
        soma = sum(int(cpf[j]) * (peso_inicio - j) for j in range(peso_inicio - 1))
        resto = (soma * 10) % 11
        if resto in (10, 11):
            resto = 0
        if resto != int(cpf[peso_inicio - 1]):
            raise ValidationError('CPF inválido.')


def validar_cnpj(cnpj: str):
    """Valida CNPJ usando o algoritmo dos dois dígitos verificadores."""
    cnpj = _only_digits(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        raise ValidationError('CNPJ inválido.')

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    for pesos in (pesos1, pesos2):
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(len(pesos)))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(cnpj[len(pesos)]):
            raise ValidationError('CNPJ inválido.')


# ════════════════════════════════════════════════════════
# Manager de usuário customizado
# ════════════════════════════════════════════════════════

class UsuarioManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O e-mail é obrigatório.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


# ════════════════════════════════════════════════════════
# Modelo de Usuário (autenticação via e-mail)
# ════════════════════════════════════════════════════════

class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Usuário do sistema. Login via e-mail.
    Vinculado 1-para-1 com Cliente após o cadastro.
    
    Hierarquia de admins:
    - is_superuser=True  → Super Administrador (controle total)
    - is_staff=True      → Administrador comum (gerencia clientes)
    - is_staff=False     → Cliente (envia devoluções)
    """
    email      = models.EmailField(unique=True, db_column='email')
    is_active  = models.BooleanField(default=True,  db_column='ativo')
    is_staff   = models.BooleanField(default=False, db_column='staff')
    date_joined = models.DateTimeField(default=timezone.now, db_column='dt_cadastro')

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    def __str__(self):
        return self.email

    class Meta:
        db_table     = 'tb_usuario'
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'


# ════════════════════════════════════════════════════════
# Modelo Cliente (estendido — suporta CPF e CNPJ + Permissões)
# ════════════════════════════════════════════════════════

TIPO_CLIENTE = [
    ('PF', 'Pessoa Física'),
    ('PJ', 'Pessoa Jurídica'),
]

# ── Permissões padrão para clientes ──────────────────────
PERMISSOES_CLIENTE_PADRAO = [
    ('pode_criar_devolucao', 'Criar devoluções'),
    ('pode_visualizar_devolucao', 'Visualizar devoluções'),
    ('pode_editar_devolucao', 'Editar devoluções não-enviadas'),
    ('pode_deletar_devolucao', 'Deletar devoluções não-enviadas'),
]

PERMISSOES_CLIENTE_CHOICES = [
    ('criar', 'Criar devoluções'),
    ('visualizar', 'Visualizar devoluções'),
    ('editar', 'Editar devoluções não-enviadas'),
    ('deletar', 'Deletar devoluções não-enviadas'),
]


class Cliente(models.Model):
    """
    Representa tanto pessoa física (CPF) quanto jurídica (CNPJ).
    Apenas um dos dois campos de documento deve ser preenchido.
    
    Novo campo: permissoes_devolucao (JSON string ou separado por vírgula)
    Exemplo: 'criar,visualizar,editar' ou 'visualizar' (apenas leitura)
    """
    usuario      = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='cliente',
        db_column='id_usuario',
    )
    tipo         = models.CharField(max_length=2, choices=TIPO_CLIENTE, db_column='tipo')

    # Pessoa Física
    cpf          = models.CharField(max_length=11, unique=True, null=True, blank=True, db_column='cpf')
    nome         = models.CharField(max_length=100, null=True, blank=True, db_column='nome')

    # Pessoa Jurídica (campos originais mantidos)
    cnpj         = models.CharField(max_length=14, unique=True, null=True, blank=True, db_column='cnpj')
    razao_social = models.CharField(max_length=100, null=True, blank=True, db_column='razao_soc')

    # Campos de contato
    email        = models.EmailField(null=True, blank=True, db_column='email')
    telefone     = models.CharField(max_length=20, null=True, blank=True, db_column='telefone')
    celular      = models.CharField(max_length=20, null=True, blank=True, db_column='celular')

    # Endereço estruturado
    logradouro   = models.CharField(max_length=100, null=True, blank=True, db_column='logradouro')
    numero       = models.CharField(max_length=10,  null=True, blank=True, db_column='numero')
    complemento  = models.CharField(max_length=50,  null=True, blank=True, db_column='complemento')
    bairro       = models.CharField(max_length=50,  null=True, blank=True, db_column='bairro')
    cidade       = models.CharField(max_length=50,  null=True, blank=True, db_column='cidade')
    estado       = models.CharField(max_length=2,   null=True, blank=True, db_column='estado')
    cep          = models.CharField(max_length=9,   null=True, blank=True, db_column='cep')

    # Campo legado — mantido para dados antigos
    endereco     = models.CharField(max_length=200, null=True, blank=True, db_column='endereco')

    # ── NEW: Permissões de devoluções (separadas por vírgula) ──────────────
    permissoes_devolucao = models.CharField(
        max_length=100,
        default='criar,visualizar,editar,deletar',
        null=True, blank=True,
        db_column='perms_devolucao',
        help_text='Permissões separadas por vírgula: criar, visualizar, editar, deletar'
    )

    @property
    def documento(self) -> str:
        return self.cpf if self.tipo == 'PF' else self.cnpj

    @property
    def nome_exibicao(self) -> str:
        if self.tipo == 'PF':
            return self.nome or ''
        return f'Empresa: {self.razao_social}' if self.razao_social else ''

    def tem_permissao(self, perm: str) -> bool:
        """
        Verifica se o cliente tem uma permissão específica.
        
        Args:
            perm: Uma das permissões: 'criar', 'visualizar', 'editar', 'deletar'
        
        Returns:
            True se tem permissão, False caso contrário
        """
        if not self.permissoes_devolucao:
            return False
        perms = [p.strip() for p in self.permissoes_devolucao.split(',')]
        return perm.strip().lower() in perms

    def clean(self):
        errors = {}

        if self.tipo == 'PF':
            if not self.cpf:
                errors['cpf'] = 'CPF é obrigatório para Pessoa Física.'
            else:
                try:
                    validar_cpf(self.cpf)
                except ValidationError as e:
                    errors['cpf'] = e.message
            if not self.nome:
                errors['nome'] = 'Nome é obrigatório para Pessoa Física.'
            self.cnpj = None
            self.razao_social = None

        elif self.tipo == 'PJ':
            if not self.cnpj:
                errors['cnpj'] = 'CNPJ é obrigatório para Pessoa Jurídica.'
            else:
                try:
                    validar_cnpj(self.cnpj)
                except ValidationError as e:
                    errors['cnpj'] = e.message
            if not self.razao_social:
                errors['razao_social'] = 'Razão Social é obrigatória para Pessoa Jurídica.'
            self.cpf = None
            self.nome = None

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        skip_validation = kwargs.pop('skip_validation', False)
        if not skip_validation:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.nome_exibicao} ({self.documento})'

    class Meta:
        db_table     = 'tb_cliente'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'


# ════════════════════════════════════════════════════════
# Modelos existentes — sem alteração
# ════════════════════════════════════════════════════════

class NotaFiscal(models.Model):
    cliente      = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, null=True, blank=True, db_column='id_cliente'
    )
    numero_nota  = models.CharField(max_length=50, null=True, blank=True, db_column='nunota', unique=True)
    data_emissao = models.DateField(
        null=True, blank=True, db_column='dt_emissao',
        help_text='Data de emissao da nota. Usada para calcular prazo de devolucao.'
    )
    arquivo_pdf  = models.FileField(
        upload_to='uploads/pdfs/',
        null=True, blank=True,
        db_column='pdf',
        validators=[FileExtensionValidator(['pdf'])],
    )

    def __str__(self):
        return f'Nota {self.numero_nota or "(sem número)"}'

    class Meta:
        db_table     = 'tb_notafiscal'
        verbose_name = 'Nota Fiscal'
        verbose_name_plural = 'Notas Fiscais'


class Produto(models.Model):
    codigo    = models.IntegerField(null=True, blank=True, db_column='codprod')
    descricao = models.CharField(max_length=100, null=True, blank=True, db_column='descricao')

    def __str__(self):
        return f'{self.codigo or "?"} - {self.descricao or "Sem descrição"}'

    class Meta:
        db_table     = 'tb_produto'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'


class ItemNotaFiscal(models.Model):
    nota_fiscal = models.ForeignKey(
        NotaFiscal, on_delete=models.CASCADE, related_name='itens', db_column='id_notafiscal'
    )
    produto     = models.ForeignKey(Produto, on_delete=models.PROTECT, db_column='id_produto')
    quantidade  = models.PositiveIntegerField(db_column='qtd')

    def __str__(self):
        return f'{self.produto.descricao} - NF {self.nota_fiscal.numero_nota}'

    class Meta:
        db_table     = 'tb_itens_nota'
        verbose_name = 'Item da Nota'
        verbose_name_plural = 'Itens da Nota'


# ════════════════════════════════════════════════════════
# Configuracao do sistema (tabela de parametros)
# ════════════════════════════════════════════════════════

class ConfiguracaoSistema(models.Model):
    prazo_devolucao_dias = models.PositiveIntegerField(
        default=30,
        db_column='prazo_dev_dias',
    )

    @classmethod
    def prazo(cls):
        obj = cls.objects.first()
        return obj.prazo_devolucao_dias if obj else 30

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Configuracao — prazo de devolucao: {self.prazo_devolucao_dias} dias'

    class Meta:
        db_table     = 'tb_configuracao'
        verbose_name = 'Configuracao do Sistema'
        verbose_name_plural = 'Configuracoes do Sistema'


STATUS_DEVOLUCAO = [
    ('pendente',    'Pendente'),
    ('em_processo', 'Em Processo'),
    ('concluido',   'Concluído'),
    ('recusada',    'Recusada'),
]

MOTIVOS_DEVOLUCAO = [
    ('produto_danificado', 'Produto danificado'),
    ('erro_pedido',        'Erro no pedido'),
    ('prazo_vencido',      'Prazo de validade vencido'),
    ('outro',              'Outro'),
]


class Devolucao(models.Model):
    """
    Modelo de devolução com rastreamento de criador.
    
    Novo campo: usuario_criador (quem criou)
    - Permite auditar quem criou a devolução
    - Permite bloquear edição pós-envio
    - Permite apenas admin editar após envio
    """
    nota_fiscal      = models.ForeignKey(
        NotaFiscal, on_delete=models.CASCADE, related_name='devolucoes', db_column='id_notafiscal'
    )
    cliente          = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, null=True, blank=True,
        db_column='id_cliente', editable=False,
    )
    
    # ── NEW: Rastreamento de quem criou ──────────────────
    usuario_criador = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='id_usuario_criador',
        related_name='devolucoes_criadas',
        help_text='Usuário que criou a devolução'
    )
    
    status           = models.CharField(
        max_length=20, choices=STATUS_DEVOLUCAO, default='pendente', db_column='status'
    )
    data_criacao     = models.DateTimeField(auto_now_add=True, db_column='dt_criacao')
    observacao_geral = models.CharField(max_length=200, blank=True, null=True, db_column='obs_geral')

    def save(self, *args, **kwargs):
        if self.nota_fiscal_id and not self.cliente_id:
            self.cliente = self.nota_fiscal.cliente
        super().save(*args, **kwargs)

    @property
    def pode_ser_editada(self) -> bool:
        """
        Verifica se a devolução pode ser editada.
        
        Regras:
        - Se status é 'pendente' → pode ser editada por qualquer um
        - Se status mudou → apenas admin pode editar
        
        Returns:
            True se pode ser editada, False caso contrário
        """
        return self.status == 'pendente'

    def cliente_pode_editar(self) -> bool:
        """
        Verifica se o cliente CRIADOR pode editar.
        
        Regra: Cliente só pode editar se devolução está 'pendente'
        """
        return self.status == 'pendente'

    def __str__(self):
        return f'Devolução #{self.pk} — NF {self.nota_fiscal.numero_nota or "?"} ({self.get_status_display()})'

    class Meta:
        db_table     = 'tb_devolucao'
        verbose_name = 'Devolução'
        verbose_name_plural = 'Devoluções'
        ordering     = ['-data_criacao']
        # ── Permissões customizadas ────────────────────────
        # Após adicionar, rode: python manage.py migrate
        permissions = [
            ('pode_criar_devolucao',      'Pode criar devoluções'),
            ('pode_editar_devolucao',     'Pode editar devoluções'),
            ('pode_excluir_devolucao',    'Pode excluir devoluções'),
            ('pode_ver_todas_devolucoes', 'Pode ver todas as devoluções'),
            ('pode_gerenciar_usuarios',   'Pode gerenciar usuários/admins'),
        ]


class ItemDevolucao(models.Model):
    devolucao            = models.ForeignKey(
        Devolucao, on_delete=models.CASCADE, related_name='itens', db_column='id_devolucao'
    )
    produto              = models.ForeignKey(Produto, on_delete=models.PROTECT, db_column='id_produto')
    quantidade_devolvida = models.PositiveIntegerField(db_column='qtd_devolvida')
    motivo               = models.CharField(
        max_length=50, choices=MOTIVOS_DEVOLUCAO, blank=True, null=True, db_column='motivo'
    )
    observacao           = models.CharField(max_length=100, blank=True, null=True, db_column='obs')
    foto                 = models.ImageField(
        upload_to='uploads/fotos_devolucao/',
        null=True, blank=True,
        db_column='foto',
    )

    def __str__(self):
        return f'{self.produto} × {self.quantidade_devolvida} (Dev #{self.devolucao_id})'

    class Meta:
        db_table     = 'tb_itens_devolucao'
        verbose_name = 'Item da Devolução'
        verbose_name_plural = 'Itens da Devolução'