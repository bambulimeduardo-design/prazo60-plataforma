-- ============================================================
-- Prazo60 · preparar o Select AI para ser usado pelo site
-- Rodar no Database Actions > SQL (botao "Run Script", F5)
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A · como ADMIN
-- ------------------------------------------------------------

-- A1. A base completa esta carregada? Esperado: cerca de 45.416 (ou 45.616 com os 200 da Sprint 3).
SELECT COUNT(*) AS casos FROM TB_TRATAMENTO;

-- A2. Atributos do perfil que ja funciona. COPIE o resultado: vai ser reutilizado na parte B.
SELECT attribute_name, attribute_value
FROM   user_cloud_ai_profile_attributes
WHERE  profile_name = 'PRAZO60_AI';

-- A3. Usuario proprio do site, somente leitura (o site nao deve usar ADMIN).
--     Senha do ADB: 12 a 30 caracteres, com maiuscula, minuscula e numero; sem aspas duplas.
CREATE USER PRAZO60_APP IDENTIFIED BY "TROQUE_Esta_Senha_2026";
GRANT CREATE SESSION        TO PRAZO60_APP;
GRANT EXECUTE ON DBMS_CLOUD    TO PRAZO60_APP;
GRANT EXECUTE ON DBMS_CLOUD_AI TO PRAZO60_APP;

GRANT SELECT ON ADMIN.TB_CASO_PACIENTE   TO PRAZO60_APP;
GRANT SELECT ON ADMIN.TB_TRATAMENTO      TO PRAZO60_APP;
GRANT SELECT ON ADMIN.TB_UNIDADE_SAUDE   TO PRAZO60_APP;
GRANT SELECT ON ADMIN.TB_MUNICIPIO       TO PRAZO60_APP;
GRANT SELECT ON ADMIN.TB_DRS             TO PRAZO60_APP;
GRANT SELECT ON ADMIN.TB_STATUS_PRAZO    TO PRAZO60_APP;
GRANT SELECT ON ADMIN.TB_TIPO_TRATAMENTO TO PRAZO60_APP;
-- Se alguma das 7 tabelas tiver outro nome no seu banco, ajuste aqui e na parte B.

-- A4. Para entrar no SQL como PRAZO60_APP: Database Actions > Database Users >
--     PRAZO60_APP > Edit > ligar "Web Access" (REST Enable). Depois saia e entre com esse usuario.


-- ------------------------------------------------------------
-- PARTE B · logado como PRAZO60_APP
-- Credencial e perfil pertencem ao usuario que os cria; o PRAZO60_AI do ADMIN
-- nao fica visivel para outro usuario, por isso criamos os dele.
-- ------------------------------------------------------------

-- B1. Mesma API Signing Key usada na OCI_CRED do ADMIN.
BEGIN
  DBMS_CLOUD.CREATE_CREDENTIAL(
    credential_name => 'OCI_CRED',
    user_ocid       => 'ocid1.user.oc1..COLE_AQUI',
    tenancy_ocid    => 'ocid1.tenancy.oc1..COLE_AQUI',
    private_key     => 'COLE_AQUI_O_CONTEUDO_DA_CHAVE_PRIVADA_SEM_AS_LINHAS_BEGIN_E_END',
    fingerprint     => 'aa:bb:cc:...'
  );
END;
/

-- B2. Perfil com os MESMOS atributos obtidos em A2 (provider, region, model,
--     oci_compartment_id etc.). O importante: "owner" das tabelas = ADMIN.
BEGIN
  DBMS_CLOUD_AI.CREATE_PROFILE(
    profile_name => 'PRAZO60_AI',
    attributes   => '{
      "provider": "oci",
      "credential_name": "OCI_CRED",
      "region": "sa-saopaulo-1",
      "object_list": [
        {"owner": "ADMIN", "name": "TB_CASO_PACIENTE"},
        {"owner": "ADMIN", "name": "TB_TRATAMENTO"},
        {"owner": "ADMIN", "name": "TB_UNIDADE_SAUDE"},
        {"owner": "ADMIN", "name": "TB_MUNICIPIO"},
        {"owner": "ADMIN", "name": "TB_DRS"},
        {"owner": "ADMIN", "name": "TB_STATUS_PRAZO"},
        {"owner": "ADMIN", "name": "TB_TIPO_TRATAMENTO"}
      ]
    }'
  );
END;
/

-- B3. Os dois modos que o site usa (showsql para auditoria, narrate para a resposta em texto).
SELECT DBMS_CLOUD_AI.GENERATE(
         prompt       => 'Quantos casos ultrapassaram o prazo de 60 dias?',
         profile_name => 'PRAZO60_AI',
         action       => 'showsql') AS sql_gerado
FROM dual;

SELECT DBMS_CLOUD_AI.GENERATE(
         prompt       => 'Quantos casos ultrapassaram o prazo de 60 dias?',
         profile_name => 'PRAZO60_AI',
         action       => 'narrate') AS resposta
FROM dual;
