# Integrações: Power BI e Oracle Select AI

## 1. Power BI

A página **Power BI** lê o endereço do relatório de uma única configuração no servidor. Não há
iframe de exemplo: sem configuração, a página mostra que o relatório ainda não foi incorporado.

### Onde inserir o embed

| Variável (Render > Environment ou `.env`) | Exemplo |
|---|---|
| `POWERBI_EMBED_URL` | `https://app.powerbi.com/view?r=eyJrIjoi...` ou `https://app.powerbi.com/reportEmbed?reportId=...&autoAuth=true&ctid=...` |
| `POWERBI_TITULO` | `Relatório Prazo60` |

Também é aceito o link copiado da barra do navegador (`https://app.powerbi.com/groups/me/reports/<id>/<página>`):
o servidor o converte para `reportEmbed?reportId=<id>&autoAuth=true&pageName=<página>`, porque a página
normal do Power BI não pode ser exibida dentro de outro site. O relatório atual do projeto já está
configurado assim no `render.yaml`.

O servidor só aceita endereços de `app.powerbi.com` ou `app.fabric.microsoft.com`, e a política de
segurança (CSP `frame-src`) autoriza apenas esses domínios.

### Como atualizar

- **Conteúdo do relatório:** publique a nova versão no Power BI Service; o site mostra automaticamente.
- **Trocar de relatório:** altere `POWERBI_EMBED_URL` e salve (o Render reinicia o serviço). Nenhum código muda.

### Opções de incorporação

| Modo | Como obter o link | Quem consegue ver | Permissões necessárias |
|---|---|---|---|
| Publicar na Web | Arquivo > Inserir relatório > Publicar na Web | **Qualquer pessoa com o link**, mesmo sem login no Prazo60 | Administrador do tenant precisa habilitar |
| Site ou portal seguro | Arquivo > Inserir relatório > Site ou portal | Somente quem entra com conta Microsoft com acesso ao relatório | Licença Pro ou PPU para cada visualizador |
| Power BI Embedded (app owns data) | API REST do Power BI + token gerado no backend | Usuários do Prazo60, sem conta Microsoft | Capacidade A/EM/F, service principal no Azure AD |

### Limitações e riscos do “Publicar na Web”

- O link é **público**: o login desta plataforma não protege o relatório, porque o link pode ser copiado
  do código da página e aberto diretamente.
- Não suporta segurança em nível de linha (RLS).
- O relatório pode ser indexado ou compartilhado sem controle.
- **Use somente com dados agregados**, como os do Prazo60. Nunca com dados individuais.

### Alternativas para ambiente privado

1. **Portal seguro**: troque o link e mantenha o relatório compartilhado só com as contas do grupo.
2. **Power BI Embedded**: crie um endpoint `/api/powerbi/token` no FastAPI usando a biblioteca `msal`
   com service principal (variáveis `PBI_TENANT_ID`, `PBI_CLIENT_ID`, `PBI_CLIENT_SECRET`,
   `PBI_WORKSPACE_ID`, `PBI_REPORT_ID`) e renderize com `powerbi-client` no frontend. O token expira em
   cerca de 1 hora e nunca expõe o segredo ao navegador.

## 2. Oracle Select AI

### Arquitetura

```text
Frontend (página Inteligência Artificial)
   │  POST /api/ia/perguntar  (sessão + cabeçalho anti-CSRF + limite de 20 perguntas/hora)
   ▼
API FastAPI (server/select_ai.py)
   │  python-oracledb, modo thin, mTLS com wallet
   ▼
Oracle Autonomous Database · Prazo60DB (OCI São Paulo)
   │  DBMS_CLOUD_AI.GENERATE(prompt, profile_name => 'PRAZO60_AI', action => 'showsql' | 'narrate')
   ▼
Resposta em texto + SQL gerado (exibido para auditoria)
```

O navegador nunca acessa o banco e nunca recebe usuário, senha, wallet ou connection string.

### Estado atual

- Protótipo validado no SQL Developer com 200 casos (evidências exibidas na plataforma).
- Base completa (45.416 casos) carregável com os scripts de `Prazo60_Carga_Oracle`.
- Endpoint e interface prontos; **desligados** até a configuração abaixo. Sem ela, a API responde
  `503 nao_configurado` e a interface diz claramente que nenhuma resposta foi gerada.

### Como ativar

1. Rodar a carga completa no Prazo60DB (README de `Prazo60_Carga_Oracle`).
2. Criar ou atualizar o perfil de IA com as tabelas do projeto:

   ```sql
   BEGIN
     DBMS_CLOUD_AI.CREATE_PROFILE(
       profile_name => 'PRAZO60_AI',
       attributes   => '{"provider": "oci",
                         "credential_name": "OCI_CRED",
                         "object_list": [
                           {"owner": "ADMIN", "name": "TB_CASO_PACIENTE"},
                           {"owner": "ADMIN", "name": "TB_TRATAMENTO"},
                           {"owner": "ADMIN", "name": "TB_UNIDADE_SAUDE"},
                           {"owner": "ADMIN", "name": "TB_MUNICIPIO"},
                           {"owner": "ADMIN", "name": "TB_DRS"},
                           {"owner": "ADMIN", "name": "TB_STATUS_PRAZO"},
                           {"owner": "ADMIN", "name": "TB_TIPO_TRATAMENTO"}]}');
   END;
   /
   ```

3. **Criar um usuário de banco somente leitura** para a API (não usar ADMIN em produção), com `SELECT`
   nessas tabelas e `EXECUTE` em `DBMS_CLOUD_AI`.
4. Baixar o wallet do Autonomous Database. No Render, envie os arquivos como **Secret Files**
   (ficam em `/etc/secrets/`).
5. Definir no servidor:

   | Variável | Valor |
   |---|---|
   | `SELECT_AI_HABILITADO` | `true` |
   | `SELECT_AI_PERFIL` | `PRAZO60_AI` |
   | `ORACLE_USER` / `ORACLE_PASSWORD` | usuário somente leitura |
   | `ORACLE_DSN` | `prazo60db_medium` |
   | `ORACLE_WALLET_DIR` | `/etc/secrets` |
   | `ORACLE_WALLET_PASSWORD` | senha do wallet, se houver |

6. Reiniciar o serviço. O selo da página muda para **Integração ativa**.

### Cuidados

- A pergunta é enviada como *bind variable*, nunca concatenada em SQL.
- Respostas de LLM podem errar: a interface mostra o SQL gerado para conferência.
- O perfil deve listar apenas tabelas sem identificação pessoal.

## 3. Trocar a fonte de dados para o Oracle (roadmap)

O frontend consome apenas o contrato JSON de `/api/painel`, `/api/localizador` e `/api/simulacao`.
Para ler do Prazo60DB em vez da base local, basta implementar um provedor com os mesmos métodos de
`BaseLocal` (`painel`, `localizador`, `opcoes`) usando `server/oracle/queries.py` como ponto de partida.
Nenhuma tela precisa mudar.
