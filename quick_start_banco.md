-- ═══════════════════════════════════════════════════════════════════════
--  PROJETO DEVOLUÇÃO — Inserção de Dados de Teste
--  Execute APÓS: makemigrations + migrate
--  Banco: devolucao
-- ═══════════════════════════════════════════════════════════════════════
create database devolucao;

USE devolucao;

SET SQL_SAFE_UPDATES  = 0;
SET FOREIGN_KEY_CHECKS = 0;

-- Limpa qualquer dado residual (seguro rodar várias vezes)
DELETE FROM tb_itens_devolucao;
DELETE FROM tb_devolucao;
DELETE FROM tb_itens_nota;
DELETE FROM tb_notafiscal;
DELETE FROM tb_produto;
DELETE FROM tb_cliente;
DELETE FROM tb_usuario_user_permissions;
DELETE FROM tb_usuario;
DELETE FROM tb_configuracao;

SET FOREIGN_KEY_CHECKS = 1;
SET SQL_SAFE_UPDATES  = 1;


-- ═══════════════════════════════════════════════════════════════════════
-- 1. CONFIGURAÇÃO DO SISTEMA (prazo de 30 dias)
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO tb_configuracao (id, prazo_dev_dias) VALUES (1, 30);


-- ═══════════════════════════════════════════════════════════════════════
-- 2. USUÁRIOS
--  Senha: definida via manage.py shell após este script
--
--  Hierarquia:
--    super_admin@teste.com      → superuser
--    admin@teste.com            → staff (todas as permissões)
--    admin_restrito@teste.com   → staff (só ver + gerenciar)
--    cliente_pf@teste.com       → cliente PF (permissões completas)
--    cliente_pj@teste.com       → cliente PJ (permissões completas)
--    cliente_leitura@teste.com  → cliente (só visualizar)
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO tb_usuario (password, last_login, is_superuser, email, ativo, staff, dt_cadastro) VALUES
  ('!unusable', NULL, 1, 'super_admin@teste.com',        1, 1, NOW()),
  ('!unusable', NULL, 0, 'admin@teste.com',               1, 1, NOW()),
  ('!unusable', NULL, 0, 'admin_restrito@teste.com',      1, 1, NOW()),
  ('!unusable', NULL, 0, 'cliente_pf@teste.com',          1, 0, NOW()),
  ('!unusable', NULL, 0, 'cliente_pj@teste.com',          1, 0, NOW()),
  ('!unusable', NULL, 0, 'cliente_leitura@teste.com',     1, 0, NOW());

SET @u_super    = (SELECT id FROM tb_usuario WHERE email = 'super_admin@teste.com');
SET @u_admin    = (SELECT id FROM tb_usuario WHERE email = 'admin@teste.com');
SET @u_restrito = (SELECT id FROM tb_usuario WHERE email = 'admin_restrito@teste.com');
SET @u_pf       = (SELECT id FROM tb_usuario WHERE email = 'cliente_pf@teste.com');
SET @u_pj       = (SELECT id FROM tb_usuario WHERE email = 'cliente_pj@teste.com');
SET @u_leitura  = (SELECT id FROM tb_usuario WHERE email = 'cliente_leitura@teste.com');


-- ═══════════════════════════════════════════════════════════════════════
-- 3. PERMISSÕES DOS ADMINS
--    O Django já criou as permissões via migrate — só vinculamos aqui
-- ═══════════════════════════════════════════════════════════════════════

SET @perm_criar_dev   = (SELECT id FROM auth_permission WHERE codename = 'pode_criar_devolucao');
SET @perm_editar_dev  = (SELECT id FROM auth_permission WHERE codename = 'pode_editar_devolucao');
SET @perm_excluir_dev = (SELECT id FROM auth_permission WHERE codename = 'pode_excluir_devolucao');
SET @perm_ver_todas   = (SELECT id FROM auth_permission WHERE codename = 'pode_ver_todas_devolucoes');
SET @perm_gerenciar   = (SELECT id FROM auth_permission WHERE codename = 'pode_gerenciar_usuarios');

-- Admin comum: todas as permissões customizadas
INSERT INTO tb_usuario_user_permissions (usuario_id, permission_id) VALUES
  (@u_admin, @perm_criar_dev),
  (@u_admin, @perm_editar_dev),
  (@u_admin, @perm_excluir_dev),
  (@u_admin, @perm_ver_todas),
  (@u_admin, @perm_gerenciar);

-- Admin restrito: só ver e gerenciar
INSERT INTO tb_usuario_user_permissions (usuario_id, permission_id) VALUES
  (@u_restrito, @perm_ver_todas),
  (@u_restrito, @perm_gerenciar);


-- ═══════════════════════════════════════════════════════════════════════
-- 4. CLIENTES
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO tb_cliente (id_usuario, tipo, cpf, nome, cnpj, razao_soc, email, telefone, celular, logradouro, numero, complemento, bairro, cidade, estado, cep, perms_devolucao) VALUES
  (@u_pf,      'PF', '12345678909', 'Joao Silva',      NULL,            NULL,                 'cliente_pf@teste.com',      '(65) 3621-1000', '(65) 99999-1111', 'Rua das Flores',  '123', 'Apto 4', 'Centro',              'Rondonopolis', 'MT', '78700-000', 'criar,visualizar,editar,deletar'),
  (@u_pj,      'PJ', NULL,          NULL,               '11222333000181','Empresa Teste LTDA', 'cliente_pj@teste.com',      '(65) 3621-2000', '(65) 99999-2222', 'Av. Industrial',  '500', 'Sala 10','Distrito Industrial', 'Rondonopolis', 'MT', '78705-000', 'criar,visualizar,editar,deletar'),
  (@u_leitura, 'PF', '98765432100', 'Maria Oliveira',  NULL,            NULL,                 'cliente_leitura@teste.com', '(65) 3621-3000', '(65) 99999-3333', 'Rua do Comercio', '77',  NULL,     'Jardim Primavera',    'Rondonopolis', 'MT', '78710-000', 'visualizar');

SET @c_pf      = (SELECT id FROM tb_cliente WHERE cpf  = '12345678909');
SET @c_pj      = (SELECT id FROM tb_cliente WHERE cnpj = '11222333000181');
SET @c_leitura = (SELECT id FROM tb_cliente WHERE cpf  = '98765432100');


-- ═══════════════════════════════════════════════════════════════════════
-- 5. PRODUTOS
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO tb_produto (codprod, descricao) VALUES
  (100101, 'Parafuso Sextavado M8 x 25mm'),
  (100102, 'Porca Travante M8'),
  (100103, 'Arruela Lisa M8'),
  (100104, 'Chave Allen 5mm'),
  (100105, 'Rolamento 6205 2RS'),
  (100106, 'Correia Dentada 5M-500'),
  (100107, 'Mangueira Hidraulica 1/2"'),
  (100108, 'Filtro de Oleo HF-101'),
  (100109, 'Retentores Kit (12 pcs)'),
  (100110, 'Lubrificante Industrial 1L'),
  (100111, 'Chave de Fenda 1/4" x 150mm'),
  (100112, 'Alicate Universal 8"'),
  (100113, 'Fita Isolante 19mm x 20m'),
  (100114, 'Cabo Eletrico 2.5mm (rolo 100m)'),
  (100115, 'Disjuntor Bipolar 20A');

SET @p1  = (SELECT id FROM tb_produto WHERE codprod = 100101);
SET @p2  = (SELECT id FROM tb_produto WHERE codprod = 100102);
SET @p3  = (SELECT id FROM tb_produto WHERE codprod = 100103);
SET @p4  = (SELECT id FROM tb_produto WHERE codprod = 100104);
SET @p5  = (SELECT id FROM tb_produto WHERE codprod = 100105);
SET @p6  = (SELECT id FROM tb_produto WHERE codprod = 100106);
SET @p7  = (SELECT id FROM tb_produto WHERE codprod = 100107);
SET @p8  = (SELECT id FROM tb_produto WHERE codprod = 100108);
SET @p9  = (SELECT id FROM tb_produto WHERE codprod = 100109);
SET @p10 = (SELECT id FROM tb_produto WHERE codprod = 100110);
SET @p11 = (SELECT id FROM tb_produto WHERE codprod = 100111);
SET @p12 = (SELECT id FROM tb_produto WHERE codprod = 100112);
SET @p13 = (SELECT id FROM tb_produto WHERE codprod = 100113);
SET @p14 = (SELECT id FROM tb_produto WHERE codprod = 100114);
SET @p15 = (SELECT id FROM tb_produto WHERE codprod = 100115);


-- ═══════════════════════════════════════════════════════════════════════
-- 6. NOTAS FISCAIS
--    NF-PF-001 → 10 dias atrás  (dentro do prazo, com devoluções)
--    NF-PF-002 → 20 dias atrás  (dentro do prazo, com devoluções)
--    NF-PF-003 → 35 dias atrás  (EXPIRADA — testa bloqueio de prazo)
--    NF-PF-004 → ontem          (recente, sem devolução)
--    NF-PJ-001 →  5 dias atrás  (dentro do prazo, com devoluções)
--    NF-PJ-002 → 15 dias atrás  (dentro do prazo, com devoluções)
--    NF-PJ-003 → ontem          (recente, sem devolução)
--    NF-LT-001 →  3 dias atrás  (cliente só leitura — sem devolução)
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO tb_notafiscal (id_cliente, nunota, dt_emissao) VALUES
--  (@c_pf,      'NF-PF-001', DATE_SUB(CURDATE(), INTERVAL 10 DAY)),
 -- (@c_pf,      'NF-PF-002', DATE_SUB(CURDATE(), INTERVAL 20 DAY)),
  (@c_pf,      'NF-PF-006', DATE_SUB(CURDATE(), INTERVAL 90 DAY));
 -- (@c_pf,      'NF-PF-004', DATE_SUB(CURDATE(), INTERVAL  1 DAY)),--
-- (@c_pj,      'NF-PJ-001', DATE_SUB(CURDATE(), INTERVAL  5 DAY)),
 -- (@c_pj,      'NF-PJ-002', DATE_SUB(CURDATE(), INTERVAL 15 DAY)),
--  (@c_pj,      'NF-PJ-003', DATE_SUB(CURDATE(), INTERVAL  1 DAY)),
 -- (@c_leitura, 'NF-LT-001', DATE_SUB(CURDATE(), INTERVAL  3 DAY));

SET @nf_pf1 = (SELECT id FROM tb_notafiscal WHERE nunota = 'NF-PF-001');
SET @nf_pf2 = (SELECT id FROM tb_notafiscal WHERE nunota = 'NF-PF-002');
SET @nf_pf3 = (SELECT id FROM tb_notafiscal WHERE nunota = 'NF-PF-003');
SET @nf_pf4 = (SELECT id FROM tb_notafiscal WHERE nunota = 'NF-PF-004');
SET @nf_pj1 = (SELECT id FROM tb_notafiscal WHERE nunota = 'NF-PJ-001');
SET @nf_pj2 = (SELECT id FROM tb_notafiscal WHERE nunota = 'NF-PJ-002');
SET @nf_pj3 = (SELECT id FROM tb_notafiscal WHERE nunota = 'NF-PJ-003');
SET @nf_lt1 = (SELECT id FROM tb_notafiscal WHERE nunota = 'NF-LT-001');


-- ═══════════════════════════════════════════════════════════════════════
-- 7. ITENS DAS NOTAS FISCAIS
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO tb_itens_nota (id_notafiscal, id_produto, qtd) VALUES
  (@nf_pf1, @p1,  50),
  (@nf_pf1, @p2,  50),
  (@nf_pf1, @p3, 100),
  (@nf_pf1, @p5,   5);

INSERT INTO tb_itens_nota (id_notafiscal, id_produto, qtd) VALUES
  (@nf_pf2, @p4,  10),
  (@nf_pf2, @p6,   8),
  (@nf_pf2, @p7,  15);

INSERT INTO tb_itens_nota (id_notafiscal, id_produto, qtd) VALUES
  (@nf_pf3, @p8,  20),
  (@nf_pf3, @p9,   6);

INSERT INTO tb_itens_nota (id_notafiscal, id_produto, qtd) VALUES
  (@nf_pf4, @p10,  4),
  (@nf_pf4, @p11, 12),
  (@nf_pf4, @p12,  6);

INSERT INTO tb_itens_nota (id_notafiscal, id_produto, qtd) VALUES
  (@nf_pj1, @p13, 50),
  (@nf_pj1, @p14,  5),
  (@nf_pj1, @p15, 10);

INSERT INTO tb_itens_nota (id_notafiscal, id_produto, qtd) VALUES
  (@nf_pj2, @p1, 200),
  (@nf_pj2, @p3, 300),
  (@nf_pj2, @p8,  30);

INSERT INTO tb_itens_nota (id_notafiscal, id_produto, qtd) VALUES
  (@nf_pj3, @p5,  20),
  (@nf_pj3, @p6,  15);

INSERT INTO tb_itens_nota (id_notafiscal, id_produto, qtd) VALUES
  (@nf_lt1, @p11, 10),
  (@nf_lt1, @p12,  5);


-- ═══════════════════════════════════════════════════════════════════════
-- 8. DEVOLUÇÕES
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO tb_devolucao (id_notafiscal, id_cliente, id_usuario_criador, status, dt_criacao, obs_geral) VALUES
  (@nf_pf1, @c_pf, @u_pf, 'pendente',    DATE_SUB(NOW(), INTERVAL  2 DAY), 'Parafusos chegaram com defeito visivelmente.'),
  (@nf_pf1, @c_pf, @u_pf, 'em_processo', DATE_SUB(NOW(), INTERVAL  8 DAY), 'Quantidade menor do que o pedido.'),
  (@nf_pf2, @c_pf, @u_pf, 'concluido',   DATE_SUB(NOW(), INTERVAL 15 DAY), 'Produto divergente — aceito e concluido.'),
  (@nf_pf2, @c_pf, @u_pf, 'recusada',    DATE_SUB(NOW(), INTERVAL 18 DAY), 'Uso incorreto pelo cliente conforme laudo.'),
  (@nf_pf1, @c_pf, @u_pf, 'pendente',    DATE_SUB(NOW(), INTERVAL  1 DAY), NULL),
  (@nf_pj1, @c_pj, @u_pj, 'pendente',    DATE_SUB(NOW(), INTERVAL  1 DAY), 'Fita isolante com lote com defeito de adesao.'),
  (@nf_pj2, @c_pj, @u_pj, 'em_processo', DATE_SUB(NOW(), INTERVAL 12 DAY), 'Parafusos com rosca danificada — lote inteiro.'),
  (@nf_pj2, @c_pj, @u_pj, 'concluido',   DATE_SUB(NOW(), INTERVAL 14 DAY), 'Retorno aceito e credito emitido.');

SET @dev1 = (SELECT id FROM tb_devolucao WHERE id_notafiscal = @nf_pf1 AND obs_geral = 'Parafusos chegaram com defeito visivelmente.');
SET @dev2 = (SELECT id FROM tb_devolucao WHERE id_notafiscal = @nf_pf1 AND obs_geral = 'Quantidade menor do que o pedido.');
SET @dev3 = (SELECT id FROM tb_devolucao WHERE id_notafiscal = @nf_pf2 AND obs_geral = 'Produto divergente — aceito e concluido.');
SET @dev4 = (SELECT id FROM tb_devolucao WHERE id_notafiscal = @nf_pf2 AND obs_geral = 'Uso incorreto pelo cliente conforme laudo.');
SET @dev5 = (SELECT id FROM tb_devolucao WHERE id_notafiscal = @nf_pf1 AND obs_geral IS NULL);
SET @dev6 = (SELECT id FROM tb_devolucao WHERE id_notafiscal = @nf_pj1);
SET @dev7 = (SELECT id FROM tb_devolucao WHERE id_notafiscal = @nf_pj2 AND obs_geral = 'Parafusos com rosca danificada — lote inteiro.');
SET @dev8 = (SELECT id FROM tb_devolucao WHERE id_notafiscal = @nf_pj2 AND obs_geral = 'Retorno aceito e credito emitido.');


-- ═══════════════════════════════════════════════════════════════════════
-- 9. ITENS DAS DEVOLUÇÕES
-- ═══════════════════════════════════════════════════════════════════════

INSERT INTO tb_itens_devolucao (id_devolucao, id_produto, qtd_devolvida, motivo, obs, foto) VALUES
  (@dev1, @p1, 10, 'produto_danificado', 'Parafusos vieram amassados na embalagem.', NULL),
  (@dev1, @p5,  2, 'erro_pedido',        'Rolamento errado: pedido 6205, recebeu 6304.', NULL);

INSERT INTO tb_itens_devolucao (id_devolucao, id_produto, qtd_devolvida, motivo, obs, foto) VALUES
  (@dev2, @p3, 20, 'erro_pedido', 'Arruelas M10 ao inves de M8.', NULL);

INSERT INTO tb_itens_devolucao (id_devolucao, id_produto, qtd_devolvida, motivo, obs, foto) VALUES
  (@dev3, @p4,  4, 'produto_danificado', 'Ponta da chave danificada.', NULL),
  (@dev3, @p6,  3, 'outro',              'Especificacao diferente do catalogo.', NULL);

INSERT INTO tb_itens_devolucao (id_devolucao, id_produto, qtd_devolvida, motivo, obs, foto) VALUES
  (@dev4, @p7, 5, 'prazo_vencido', 'Tentativa fora do prazo contratual.', NULL);

-- DEV-5: 2ª devolução na NF-PF-001 — testa saldo parcial
-- NF-PF-001 tem 50 parafusos; DEV-1 devolveu 10 → saldo disponível = 40
INSERT INTO tb_itens_devolucao (id_devolucao, id_produto, qtd_devolvida, motivo, obs, foto) VALUES
  (@dev5, @p1, 15, 'produto_danificado', 'Novo lote com o mesmo defeito.', NULL),
  (@dev5, @p2,  2, 'erro_pedido',        'Porcas com rosca incompativel.', NULL);

INSERT INTO tb_itens_devolucao (id_devolucao, id_produto, qtd_devolvida, motivo, obs, foto) VALUES
  (@dev6, @p13, 10, 'produto_danificado', 'Fita isolante sem aderencia — lote inteiro ruim.', NULL);

INSERT INTO tb_itens_devolucao (id_devolucao, id_produto, qtd_devolvida, motivo, obs, foto) VALUES
  (@dev7, @p1,  50, 'produto_danificado', 'Rosca fora do padrao M8.', NULL),
  (@dev7, @p3, 100, 'produto_danificado', 'Arruelas deformadas.', NULL);

INSERT INTO tb_itens_devolucao (id_devolucao, id_produto, qtd_devolvida, motivo, obs, foto) VALUES
  (@dev8, @p8, 10, 'outro', 'Filtro com codigo diferente do especificado.', NULL);


-- ═══════════════════════════════════════════════════════════════════════
-- 10. VERIFICAÇÃO FINAL
-- ═══════════════════════════════════════════════════════════════════════

SELECT '══ USUARIOS ══' AS '';
SELECT id, email,
  IF(is_superuser=1, 'Super Admin', IF(staff=1, 'Admin', 'Cliente')) AS tipo
FROM tb_usuario ORDER BY id;

SELECT '══ CLIENTES ══' AS '';
SELECT c.id, u.email,
  IF(c.tipo='PF', c.nome, c.razao_soc) AS nome,
  c.tipo, c.perms_devolucao
FROM tb_cliente c JOIN tb_usuario u ON u.id = c.id_usuario;

SELECT '══ NOTAS FISCAIS ══' AS '';
SELECT nf.nunota,
  IF(c.tipo='PF', c.nome, c.razao_soc) AS cliente,
  nf.dt_emissao,
  DATEDIFF(CURDATE(), nf.dt_emissao)            AS dias_atras,
  IF(DATEDIFF(CURDATE(), nf.dt_emissao) > 30, 'EXPIRADA', 'OK') AS prazo,
  COUNT(i.id) AS qtd_itens
FROM tb_notafiscal nf
JOIN tb_cliente c ON c.id = nf.id_cliente
LEFT JOIN tb_itens_nota i ON i.id_notafiscal = nf.id
GROUP BY nf.id ORDER BY nf.id;

SELECT '══ DEVOLUCOES ══' AS '';
SELECT d.id, nf.nunota,
  IF(c.tipo='PF', c.nome, c.razao_soc) AS cliente,
  d.status, DATE(d.dt_criacao) AS data,
  COUNT(itd.id) AS itens, SUM(itd.qtd_devolvida) AS qtd
FROM tb_devolucao d
JOIN tb_notafiscal nf ON nf.id = d.id_notafiscal
JOIN tb_cliente c     ON c.id  = d.id_cliente
LEFT JOIN tb_itens_devolucao itd ON itd.id_devolucao = d.id
GROUP BY d.id ORDER BY d.id;

select * from tb_notafiscal;
select * from tb_cliente;
select * from tb_usuario;