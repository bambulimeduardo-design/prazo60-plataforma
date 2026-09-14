# Prazo60 · Centro de Inteligência

> Diagnóstico não pode esperar. Tratamento também não.

Plataforma web do grupo **Dataholics** para acompanhar o cumprimento da **Lei nº 12.732/2012**
(início do tratamento oncológico em até 60 dias) em casos de câncer de mama (CID-10 C50),
população feminina, Estado de São Paulo.

A plataforma percorre a cadeia **dados → diagnóstico → gargalo → alternativa → simulação → decisão**
e identifica em toda tela o que é **dado real**, **estimativa**, **simulação**, **projeção** ou **demonstração**.

Projeto do **Enterprise Challenge Oracle x FIAP** (turma 1TSCPV), avaliado pela banca da Oracle.

| Recurso | Link |
|---|---|
| Plataforma web (produção) | https://prazo60.onrender.com |
| Painel Power BI | [Painel Câncer de Mama SP](https://app.powerbi.com/groups/me/reports/0a799b85-3b20-4162-81b6-d3a61ba73ff7/d1bb6caba29ffc924e85?experience=power-bi) |
| Entregas das Sprints 1 a 4 | [`entregas/`](entregas/) |

- Requisitos e rastreabilidade: [`docs/REQUISITOS.md`](docs/REQUISITOS.md)
- Colocar online (Render): [`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md)
- Power BI e Oracle Select AI: [`docs/INTEGRACOES.md`](docs/INTEGRACOES.md)
- Conferência dos números: [`etl/relatorio_validacao.md`](etl/relatorio_validacao.md)

## Acesso

| Usuário | Senha |
|---|---|
| `DATAHOLICS` | definida pelo grupo (armazenada somente como hash PBKDF2) |

O usuário não diferencia maiúsculas/minúsculas; a senha diferencia.

## Rodar localmente

```bash
pip install -r requirements.txt
uvicorn server.main:app --reload --port 8000
```

Abra http://localhost:8000 e entre com o usuário acima.

## Testes

```bash
pip install pytest
python -m pytest -q
```

33 testes cobrem autenticação, bloqueio por tentativas, CSRF, rotas protegidas, cabeçalhos de
segurança, conferência dos KPIs e alertas com os valores publicados, supressão de grupos pequenos,
localizador, os 5 cenários do simulador e a recusa da IA em inventar respostas.

## Arquitetura

```text
Navegador (HTML/CSS/JS modular, Chart.js local, SVG)
   │  HTTPS · cookie de sessão HttpOnly · CSP
   ▼
FastAPI (server/main.py)
   ├─ autenticação e proteção      server/auth.py, server/settings.py
   ├─ motor analítico agregado     server/analytics.py   ← server/data (base minimizada)
   ├─ simulador de encaminhamento  server/simulation.py
   └─ Select AI (opcional)         server/select_ai.py → server/oracle → Oracle ADB
```

```text
prazo60-plataforma/
├── server/            API, autenticação, análises, simulação, Oracle
│   └── data/          casos.csv.gz (minimizado) e referencia.json, gerados pelo ETL
├── web/
│   ├── public/        tela de login e logo (única parte acessível sem sessão)
│   └── app/           aplicação (servida só com sessão válida)
│       ├── css/       global.css, dashboard.css, responsive.css
│       └── js/        core.js, charts.js, map.js, app.js, views/*.js
├── etl/               build_data.py, fontes/, relatorio_validacao.md
├── scripts/           gerar_hash_senha.py
├── tests/             test_plataforma.py
├── docs/              requisitos, deploy, integrações
└── render.yaml        deploy no Render
```

## Páginas

| Menu | Pergunta que responde |
|---|---|
| Início | As pacientes iniciam o tratamento em 60 dias? |
| Visão Executiva | Qual a situação, a tendência e quem precisa de atenção? |
| Panorama dos 60 Dias | Como os casos se distribuem entre o diagnóstico e o tratamento? |
| Demanda & Oferta | Onde há mais casos por estabelecimento habilitado? |
| Mapa de Atendimento | Onde estão os problemas? |
| Onde estão os gargalos? | Quais regiões e municípios pioraram e que fatores se relacionam? |
| Para onde encaminhar? | Quais unidades compatíveis existem perto do município? |
| Simulação | O que acontece se redistribuirmos? |
| Power BI | Análise aprofundada (relatório incorporado) |
| Inteligência Artificial | Perguntas em linguagem natural (Oracle Select AI) |
| Dados & Metodologia | Fontes, pipeline, qualidade, indicadores, privacidade, limitações |
| Sobre o Prazo60 | Problema, lei, objetivo, impacto, equipe |

Filtros globais: ano, mês, DRS, município, estabelecimento, tipo de tratamento, situação do prazo,
residência ou local de tratamento. **Modo Apresentação** percorre 12 etapas com ← → e Esc.

## Dados

`python etl/build_data.py` lê os arquivos já existentes do projeto (`staging_casos.csv`, scripts
SQL de municípios e unidades, `js/data.js` do site anterior) e as coordenadas municipais, e gera:

- `server/data/casos.csv.gz`: somente ano/mês do diagnóstico, municípios, CNES, tipo de tratamento e dias.
  Código do caso, data de nascimento e datas exatas são descartados.
- `server/data/referencia.json`: DRS, oferta, municípios, unidades, mapa e textos metodológicos.
- `etl/relatorio_validacao.md`: KPI geral e 34 indicadores por DRS conferidos com o site anterior (0 divergências).

A API só devolve agregados. Grupos com menos de 10 casos têm percentual e mediana suprimidos.
Nenhum arquivo com dados individuais de pacientes (data de nascimento, datas exatas) é versionado.

## Entregas das Sprints (`entregas/`)

Este repositório unifica a plataforma e o repositório das Sprints 1 a 3
([AmandaBarral/Prazo60_Dataholics](https://github.com/AmandaBarral/Prazo60_Dataholics)), com os commits
originais preservados, e o relatório técnico da Sprint 4.

| Pasta | Conteúdo |
|---|---|
| `entregas/SPRINT_01` | Ideação do projeto |
| `entregas/SPRINT_02` | Arquitetura da solução |
| `entregas/SPRINT_03` | Entregas por disciplina: SQL (DDL/DML e `VW_FILA_PRAZO`), pipeline `pipeline_datasus.py`, notebook de ML, evidências de arquitetura e relatório de governança OES |
| `entregas/SPRINT_04` | Relatório técnico (Power BI, arquitetura Lambda, indicadores) |

Por LGPD, na unificação ficaram de fora os extratos com dados individuais (`POBR_SP_Mama_Tratado 1.csv`,
`POBR_SP_Mama_Tratado.xlsx`, `RAW_PAINEL_ONCOLOGIA_consolidado.xlsx`), as datas de nascimento do script DML
foram generalizadas para 01/01 do ano e a saída de `df_pobr.head()` do notebook foi limpa. Os microdados
podem ser obtidos no FTP público do DATASUS: `ftp://ftp.datasus.gov.br/dissemin/publicos/painel_oncologia/Dados/`.

## O que mudou em relação à versão anterior

**Preservado:** identidade visual (rosa institucional, Poppins/IBM Plex), logo, foto da equipe, todos os
indicadores e textos metodológicos, mapa dos 17 DRS, Sankey de migração, regras de alerta, evidências do
Select AI e a estrutura do backend Oracle.

**Corrigido:**
- a antiga “simulação de ocupação” derivava um percentual do número do DRS (`45 + seed % 50`), um dado inventado; foi substituída por um modelo sobre fluxos reais com premissas explícitas;
- o `index.html` de 855 KB com imagens em base64 virou arquivos otimizados (logo de 520 KB → 41 KB);
- filtros que não alteravam alguns gráficos agora recalculam todas as análises no servidor;
- o antigo `app.js` duplicado e não utilizado foi eliminado.

**Adicionado:** login com usuário e senha, publicação online com HTTPS, filtros globais reais, localizador
com distância estimada, simulador em 4 etapas com 5 cenários, recomendações com fundamento, municípios
críticos, fatores relacionados, qualidade de dados, central de indicadores, área Power BI configurável,
chat preparado para o Select AI, testes automatizados e documentação.

## Limitações

Dados públicos com defasagem; sem ocupação hospitalar em tempo real; localização não é vaga; simulações
são hipotéticas; recomendações não substituem a regulação oficial; base só com casos que já iniciaram
tratamento; distâncias em linha reta. Detalhes na aba *Limitações* da plataforma.
