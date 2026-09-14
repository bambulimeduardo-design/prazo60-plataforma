-- ============================================================================
-- ENTERPRISE CHALLENGE ORACLE x FIAP 2026 | Projeto: PRAZO60
-- Disciplina: SMART SQL & RELATIONAL DATABASES | Sprint 3 - Entrega 03
-- Equipe: Dataholics | Turma: 1TSCPV
--
-- Integrantes (ordem alfabetica):
--   Amanda   - RM569662
--   Eduardo  - RM573228
--   Gabriela - RM568972
--   Julia    - RM570547
--   Livia    - RM573963
--
-- Dataset de origem: TabNet PAINEL-Oncologia (DATASUS), recortado para
-- CID-10 C50 (cancer de mama), sexo feminino, Estado de Sao Paulo,
-- complementado com a divisao territorial dos Departamentos Regionais
-- de Saude (DRS/SP) para calculo do prazo da Lei 12.732/2012.
--
-- Regra de modelagem:
--   DRS > MUNICIPIO > UNIDADE_SAUDE
--   UNIDADE_DIAGNOSTICO -> CASO_PACIENTE -> TRATAMENTO -> UNIDADE_TRATAMENTO
--
-- A entidade CASO_PACIENTE representa o caso oncologico observado na fonte
-- (nao ha CNS/identificador de paciente disponivel na base), permitindo
-- diferenciar a unidade de diagnostico da unidade de tratamento e suportar
-- casos ainda aguardando inicio de tratamento (fila viva).
-- ============================================================================

-- ============================================================================
-- DROP TABLES (ordem inversa das dependencias de FK)
-- Executar somente quando for necessario recriar o schema.
-- ============================================================================
-- DROP VIEW VW_FILA_PRAZO;
-- DROP TABLE TB_TRATAMENTO PURGE;
-- DROP TABLE TB_STATUS_PRAZO PURGE;
-- DROP TABLE TB_TIPO_TRATAMENTO PURGE;
-- DROP TABLE TB_CASO_PACIENTE PURGE;
-- DROP TABLE TB_UNIDADE_SAUDE PURGE;
-- DROP TABLE TB_MUNICIPIO PURGE;
-- DROP TABLE TB_DRS PURGE;

-- ============================================================================
-- TABELA 1: TB_DRS
-- ============================================================================
CREATE TABLE TB_DRS (
    ID_DRS      NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    COD_DRS     VARCHAR2(10)    NOT NULL,
    NOME_DRS    VARCHAR2(100)   NOT NULL,
    CONSTRAINT UQ_DRS_COD UNIQUE (COD_DRS)
);

-- ============================================================================
-- TABELA 2: TB_MUNICIPIO
-- ============================================================================
CREATE TABLE TB_MUNICIPIO (
    ID_MUNICIPIO     NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    NOME_MUNICIPIO   VARCHAR2(100)   NOT NULL,
    COD_IBGE         VARCHAR2(7),
    ID_DRS           NUMBER          NOT NULL,
    CONSTRAINT UQ_MUNICIPIO_NOME UNIQUE (NOME_MUNICIPIO),
    CONSTRAINT FK_MUNICIPIO_DRS FOREIGN KEY (ID_DRS)
        REFERENCES TB_DRS (ID_DRS)
);

-- ============================================================================
-- TABELA 3: TB_UNIDADE_SAUDE
-- Unidade de diagnostico/tratamento referenciada pelo CNES.
-- ============================================================================
CREATE TABLE TB_UNIDADE_SAUDE (
    ID_UNIDADE      NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    COD_CNES        VARCHAR2(15)    NOT NULL,
    NOME_UNIDADE    VARCHAR2(150)   NOT NULL,
    ENDERECO        VARCHAR2(200),
    ID_MUNICIPIO    NUMBER          NOT NULL,
    CONSTRAINT UQ_UNIDADE_CNES UNIQUE (COD_CNES),
    CONSTRAINT FK_UNIDADE_MUNICIPIO FOREIGN KEY (ID_MUNICIPIO)
        REFERENCES TB_MUNICIPIO (ID_MUNICIPIO)
);

-- ============================================================================
-- TABELA 4: TB_CASO_PACIENTE
--
-- A entidade representa o CASO ONCOLOGICO observado na fonte, e nao uma
-- identidade persistente de paciente.
--
-- Nao armazenamos nome, CPF ou CNS. COD_CASO e apenas uma chave interna para
-- relacionar o caso aos seus registros de tratamento.
-- ============================================================================
CREATE TABLE TB_CASO_PACIENTE (
    ID_CASO                NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    COD_CASO               VARCHAR2(20)    NOT NULL,
    DATA_NASCIMENTO        DATE            NOT NULL,
    ESTAGIO_TUMOR          VARCHAR2(2),
    DATA_DIAGNOSTICO       DATE            NOT NULL,
    ID_UNIDADE_DIAGNOSTICO NUMBER          NOT NULL,
    CONSTRAINT UQ_CASO_COD UNIQUE (COD_CASO),
    -- Codigo de estadiamento do TabNet (campo ESTADIAM), de 0 a 5.
    -- NULL permitido: uma parte dos registros da base nao traz estadiamento.
    CONSTRAINT CK_CASO_ESTAGIO CHECK (
        ESTAGIO_TUMOR IN ('0','1','2','3','4','5') OR ESTAGIO_TUMOR IS NULL
    ),
    CONSTRAINT FK_CASO_UNIDADE_DIAG FOREIGN KEY (ID_UNIDADE_DIAGNOSTICO)
        REFERENCES TB_UNIDADE_SAUDE (ID_UNIDADE)
);

-- ============================================================================
-- TABELA 5: TB_TIPO_TRATAMENTO
-- ============================================================================
CREATE TABLE TB_TIPO_TRATAMENTO (
    ID_TIPO_TRATAMENTO      NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    NOME_TIPO_TRATAMENTO    VARCHAR2(30)    NOT NULL,
    CONSTRAINT UQ_TIPO_TRATAMENTO_NOME UNIQUE (NOME_TIPO_TRATAMENTO)
);

-- ============================================================================
-- TABELA 6: TB_STATUS_PRAZO
-- ============================================================================
CREATE TABLE TB_STATUS_PRAZO (
    ID_STATUS_PRAZO    NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    COD_STATUS         VARCHAR2(20)    NOT NULL,
    DESCRICAO          VARCHAR2(200)   NOT NULL,
    COR_HEX             VARCHAR2(7),
    ORDEM_EXIBICAO      NUMBER,
    CONSTRAINT UQ_STATUS_PRAZO_COD UNIQUE (COD_STATUS)
);

-- ============================================================================
-- TABELA 7: TB_TRATAMENTO
--
-- ID_UNIDADE_TRATAMENTO resolve a diferenca entre:
--   - unidade onde o diagnostico ocorreu;
--   - unidade onde o tratamento ocorreu.
--
-- Para AGUARDANDO, DATA_INICIO_TRATAMENTO, DIAS_ESPERA e
-- ID_UNIDADE_TRATAMENTO podem ser NULL.
-- ============================================================================
CREATE TABLE TB_TRATAMENTO (
    ID_TRATAMENTO          NUMBER          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ID_CASO                NUMBER          NOT NULL,
    ID_TIPO_TRATAMENTO     NUMBER          NOT NULL,
    ID_UNIDADE_TRATAMENTO  NUMBER,
    DATA_INICIO_TRATAMENTO DATE,
    DIAS_ESPERA            NUMBER,
    ID_STATUS_PRAZO        NUMBER          NOT NULL,

    CONSTRAINT CK_TRATAMENTO_DIAS CHECK (
        DIAS_ESPERA IS NULL OR DIAS_ESPERA >= 0
    ),

    CONSTRAINT CK_TRATAMENTO_INICIO_COERENTE CHECK (
        DATA_INICIO_TRATAMENTO IS NULL OR DIAS_ESPERA IS NOT NULL
    ),

    CONSTRAINT CK_TRATAMENTO_UNIDADE_COERENTE CHECK (
        DATA_INICIO_TRATAMENTO IS NULL OR ID_UNIDADE_TRATAMENTO IS NOT NULL
    ),

    CONSTRAINT FK_TRATAMENTO_CASO FOREIGN KEY (ID_CASO)
        REFERENCES TB_CASO_PACIENTE (ID_CASO),

    CONSTRAINT FK_TRATAMENTO_TIPO FOREIGN KEY (ID_TIPO_TRATAMENTO)
        REFERENCES TB_TIPO_TRATAMENTO (ID_TIPO_TRATAMENTO),

    CONSTRAINT FK_TRATAMENTO_UNIDADE FOREIGN KEY (ID_UNIDADE_TRATAMENTO)
        REFERENCES TB_UNIDADE_SAUDE (ID_UNIDADE),

    CONSTRAINT FK_TRATAMENTO_STATUS FOREIGN KEY (ID_STATUS_PRAZO)
        REFERENCES TB_STATUS_PRAZO (ID_STATUS_PRAZO)
);

-- ============================================================================
-- INDICES
-- ============================================================================
CREATE INDEX IX_MUNICIPIO_DRS       ON TB_MUNICIPIO (ID_DRS);
CREATE INDEX IX_UNIDADE_MUNICIPIO   ON TB_UNIDADE_SAUDE (ID_MUNICIPIO);
CREATE INDEX IX_CASO_UNIDADE_DIAG   ON TB_CASO_PACIENTE (ID_UNIDADE_DIAGNOSTICO);
CREATE INDEX IX_CASO_DATA_DIAG      ON TB_CASO_PACIENTE (DATA_DIAGNOSTICO);
CREATE INDEX IX_TRATAMENTO_CASO     ON TB_TRATAMENTO (ID_CASO);
CREATE INDEX IX_TRATAMENTO_TIPO     ON TB_TRATAMENTO (ID_TIPO_TRATAMENTO);
CREATE INDEX IX_TRATAMENTO_UNIDADE  ON TB_TRATAMENTO (ID_UNIDADE_TRATAMENTO);
CREATE INDEX IX_TRATAMENTO_STATUS   ON TB_TRATAMENTO (ID_STATUS_PRAZO);

-- ============================================================================
-- VIEW: VW_FILA_PRAZO
--
-- Para casos AGUARDANDO, a contagem e dinamica:
--   dias desde o diagnostico ate SYSDATE.
--
-- Assim um caso sem tratamento iniciado pode ser identificado como
-- AGUARDANDO_DENTRO_PRAZO ou AGUARDANDO_VENCIDO sem alterar o status historico.
-- ============================================================================
CREATE OR REPLACE VIEW VW_FILA_PRAZO AS
SELECT
    c.ID_CASO,
    c.COD_CASO,
    c.DATA_NASCIMENTO,
    c.ESTAGIO_TUMOR,
    c.DATA_DIAGNOSTICO,
    u.COD_CNES AS CNES_DIAGNOSTICO,
    u.NOME_UNIDADE AS UNIDADE_DIAGNOSTICO,
    t.ID_TRATAMENTO,
    tt.NOME_TIPO_TRATAMENTO,
    ut.COD_CNES AS CNES_TRATAMENTO,
    ut.NOME_UNIDADE AS UNIDADE_TRATAMENTO,
    t.DATA_INICIO_TRATAMENTO,
    t.DIAS_ESPERA AS DIAS_ESPERA_REGISTRADOS,
    sp.COD_STATUS AS STATUS_BASE,
    CASE
        WHEN t.DATA_INICIO_TRATAMENTO IS NULL
        THEN TRUNC(SYSDATE - c.DATA_DIAGNOSTICO)
        ELSE t.DIAS_ESPERA
    END AS DIAS_ESPERA_ATUAL,
    CASE
        WHEN t.DATA_INICIO_TRATAMENTO IS NULL
             AND TRUNC(SYSDATE - c.DATA_DIAGNOSTICO) > 60
            THEN 'AGUARDANDO_VENCIDO'
        WHEN t.DATA_INICIO_TRATAMENTO IS NULL
            THEN 'AGUARDANDO_DENTRO_PRAZO'
        ELSE sp.COD_STATUS
    END AS CLASSIFICACAO_PRAZO,
    c.DATA_DIAGNOSTICO + 60 AS DATA_LIMITE_LEGAL
FROM TB_CASO_PACIENTE c
JOIN TB_UNIDADE_SAUDE u
    ON u.ID_UNIDADE = c.ID_UNIDADE_DIAGNOSTICO
JOIN TB_TRATAMENTO t
    ON t.ID_CASO = c.ID_CASO
JOIN TB_TIPO_TRATAMENTO tt
    ON tt.ID_TIPO_TRATAMENTO = t.ID_TIPO_TRATAMENTO
JOIN TB_STATUS_PRAZO sp
    ON sp.ID_STATUS_PRAZO = t.ID_STATUS_PRAZO
LEFT JOIN TB_UNIDADE_SAUDE ut
    ON ut.ID_UNIDADE = t.ID_UNIDADE_TRATAMENTO;

COMMIT;
