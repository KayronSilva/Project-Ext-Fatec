# Importa o módulo principal de modelos do Django (necessário para criar tabelas no banco).
from django.db import models
# Importa exceção usada para validações personalizadas em modelos.
from django.core.exceptions import ValidationError
# Importa um validador útil (não usado neste código, mas pronto para validar 


# ======================================================
# MODELO CLIENTE
# ======================================================
class Cliente(models.Model):
    # Campo para armazenar o CNPJ do cliente (somente números, 14 dígitos).
    # 'blank=True' permite que o campo seja deixado em branco nos formulários.
    # 'db_column' define o nome da coluna correspondente no banco de dados.
    cnpj = models.CharField(max_length=14, blank=True, db_column='cnpj')

    # Campo para armazenar a razão social do cliente.
    # 'null=True' permite valor nulo no banco de dados.
    # 'blank=True' permite campo vazio nos formulários Django.
    razao_social = models.CharField(max_length=100, null=True, blank=True, db_column='razao_soc')

    # Método de validação customizada do modelo.
    # É chamado automaticamente quando 'full_clean()' é executado ou manualmente antes de salvar.
    def clean(self):
        # Se o CNPJ estiver preenchido, verifica se tem exatamente 14 caracteres numéricos.
        if self.cnpj and len(self.cnpj) != 14:
            # Se não tiver 14 dígitos, gera erro de validação.
            raise ValidationError('CNPJ deve conter 14 dígitos numéricos.')

    # Define como o objeto será exibido (por exemplo, no admin ou em logs).
    def __str__(self):
        # Retorna uma string com a razão social e o CNPJ.
        return f'{self.razao_social or "Sem razão social"} ({self.cnpj or "Sem CNPJ"})'

    # Configurações adicionais do modelo.
    class Meta:
        db_table = 'tb_cliente'  # Nome da tabela no banco de dados.
        verbose_name = 'Cliente'  # Nome singular exibido no admin.
        verbose_name_plural = 'Clientes'  # Nome plural exibido no admin.


# ======================================================
# MODELO NOTA FISCAL
# ======================================================
class NotaFiscal(models.Model):
    # Campo de chave estrangeira ligando a nota a um cliente.
    # Se o cliente for apagado, as notas associadas também são excluídas (on_delete=models.CASCADE).
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, null=True, blank=True, db_column='id_cliente'
    )

    # Número da nota fiscal (string para aceitar letras e números).
    numero_nota = models.CharField(max_length=50, null=True, blank=True, db_column='nunota')

    # Representação textual da nota fiscal.
    def __str__(self):
        # Retorna “Nota [número]” ou “(sem número)” caso não tenha valor.
        return f'Nota {self.numero_nota or "(sem número)"}'

    class Meta:
        db_table = 'tb_notafiscal'  # Nome da tabela no banco de dados.
        verbose_name = 'Nota Fiscal'
        verbose_name_plural = 'Notas Fiscais'


# ======================================================
# MODELO PRODUTO
# ======================================================
class Produto(models.Model):
    # Código numérico do produto.
    # 'unique=True' garante que não existam dois produtos com o mesmo código.
    codigo = models.IntegerField(unique=True, null=True, blank=True, db_column='codprod')

    # Descrição textual do produto.
    descricao = models.CharField(max_length=100, null=True, blank=True, db_column='descricao')

    def __str__(self):
        # Exibe o código e a descrição do produto ou valores padrão se estiverem vazios.
        return f'{self.codigo or "?"} - {self.descricao or "Sem descrição"}'

    class Meta:
        db_table = 'tb_produto'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'


# ======================================================
# MODELO ITEM DA NOTA FISCAL (relação entre nota e produto)
# ======================================================
class ItemNotaFiscal(models.Model):
    # Chave estrangeira para a nota fiscal à qual o item pertence.
    nota_fiscal = models.ForeignKey(
        NotaFiscal,
        on_delete=models.CASCADE,   # Se a nota for deletada, seus itens também são.
        related_name='itens',       # Permite acessar itens via nota.itens.all()
        db_column='id_notafiscal',  # Nome da coluna no banco.
    )

    # Chave estrangeira para o produto incluído na nota.
    produto = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT,   # Impede excluir produto se houver notas associadas.
        db_column='id_produto',
    )

    # Quantidade de produtos incluídos na nota.
    quantidade = models.PositiveIntegerField(db_column='qtd')

    class Meta:
        db_table = 'tb_itens_nota'
        verbose_name = 'Item da Nota'
        verbose_name_plural = 'Itens da Nota'

    def __str__(self):
        # Exibe uma representação amigável: nome do produto + número da nota.
        return f'{self.produto.descricao} - NF {self.nota_fiscal.numero_nota}'


# ======================================================
# MODELO DEVOLUÇÃO
# ======================================================
class Devolucao(models.Model):
    # Lista de opções fixas para o campo "motivo" (tuplas de valor e rótulo legível).
    MOTIVOS_OPCOES = [
        ('produto_danificado', 'Produto danificado'),
        ('erro_pedido', 'Erro no pedido'),
        ('prazo_vencido', 'Prazo de validade vencido'),
        ('outro', 'Outro'),
    ]

    # Referência à nota fiscal que originou a devolução.
    nota_fiscal = models.ForeignKey(
        NotaFiscal,
        on_delete=models.CASCADE,   # Se a nota for excluída, a devolução também será.
        related_name='devolucoes',  # Acesso reverso: nota.devolucoes.all()
        db_column='id_notafiscal',
    )

    # Produto devolvido (usa o código do produto como referência).
    produto = models.ForeignKey(
        Produto,
        to_field='codigo',          # Relaciona usando o campo 'codigo' em vez do ID padrão.
        on_delete=models.CASCADE,   # Se o produto for excluído, a devolução também será.
        blank=True,
        null=True,
        db_column='codprod',
    )

    # Cliente responsável pela devolução (pode ser nulo).
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='id_cliente',
    )

    # Quantidade de produtos devolvidos.
    quantidade_devolvida = models.PositiveIntegerField(
        blank=True, null=True, db_column='qtd_devolvida'
    )

    # Motivo da devolução (escolhido entre as opções definidas acima).
    motivo = models.CharField(
        max_length=200,
        choices=MOTIVOS_OPCOES,
        blank=True,
        null=True,
        db_column='motivo'
    )

    # Campo de texto opcional para observações adicionais.
    observacao = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_column='obs'
    )

    # Método sobrescrito de salvamento — executa antes de gravar no banco.
    def save(self, *args, **kwargs):
        # Se a devolução estiver associada a uma nota que tem cliente,
        # copia automaticamente o cliente da nota para o campo 'cliente' da devolução.
        if self.nota_fiscal and self.nota_fiscal.cliente:
            self.cliente = self.nota_fiscal.cliente
        # Chama o método original de salvamento para persistir o registro.
        super().save(*args, **kwargs)

    def __str__(self):
        # Retorna uma representação amigável do registro de devolução.
        return f'Devolução de {self.produto or "?"} - NF {self.nota_fiscal.numero_nota or "?"}'

    class Meta:
        db_table = 'tb_devolucao'  # Nome da tabela no banco.
        verbose_name = 'Devolução'
        verbose_name_plural = 'Devoluções'
