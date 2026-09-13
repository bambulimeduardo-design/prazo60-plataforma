# Documento de Requisitos · Plataforma Prazo60 v2

| Item | Valor |
|---|---|
| Produto | Prazo60 · Centro de Inteligência |
| Responsável | Grupo Dataholics |
| Base legal | Lei nº 12.732/2012 (primeiro tratamento oncológico em até 60 dias) |
| Recorte | Câncer de mama (CID-10 C50), sexo feminino, Estado de São Paulo, diagnósticos 2022–2026 |
| Status dos itens | **Atendido** (implementado e testado) · **Preparado** (código pronto, depende de configuração externa) · **Roadmap** (fora desta versão) |

## 1. Objetivo

Responder, com dados públicos, a três perguntas de gestão:

1. **O que está acontecendo?** As pacientes iniciam o tratamento em até 60 dias?
2. **Onde está acontecendo?** Em que regiões, municípios e unidades?
3. **O que podemos fazer?** Quais alternativas existem nos dados e qual seria o impacto estimado?

Tudo isso sem inventar dados e identificando o que é real, estimado, simulado, projetado ou demonstrativo.

## 2. Perfis de uso

| Perfil | Necessidade | Páginas principais |
|---|---|---|
| Gestor de saúde | Entender a situação em segundos e priorizar regiões | Visão Executiva, Gargalos, Mapa |
| Regulação / planejamento | Avaliar alternativas e impacto de redistribuições | Para onde encaminhar?, Simulação |
| Banca acadêmica / especialistas | Verificar método, fontes e limitações | Dados & Metodologia, Sobre |
| Analista de dados | Aprofundar e auditar | Power BI, Prazo60 AI, API |

Nesta versão existe **um único usuário** (`DATAHOLICS`) compartilhado pelo grupo.

## 3. Requisitos funcionais

### 3.1 Acesso e navegação

| ID | Requisito | Status | Onde |
|---|---|---|---|
| RF-01 | Site online com URL própria e HTTPS | Preparado (deploy pelo grupo) | `render.yaml`, `docs/DEPLOY_RENDER.md` |
| RF-02 | Tela de login com usuário e senha; único usuário `DATAHOLICS` | Atendido | `web/public/login.html`, `server/main.py` |
| RF-03 | Sair (logout) e expiração automática da sessão (8 h) | Atendido | Topo da aplicação |
| RF-04 | Menu consistente com 12 itens agrupados em Entender, Localizar, Agir e Aprofundar | Atendido | `web/app/index.html` |
| RF-05 | Trilha de navegação (breadcrumb), estados de carregamento, vazio e erro | Atendido | `app.js`, `core.js` |
| RF-06 | Botão “Como calculamos?” com definição, fórmula, fonte, período, premissas, limitações e interpretação | Atendido | Modal de indicadores |
| RF-07 | Modo Apresentação em 12 etapas, com navegação por setas e tela cheia | Atendido | `app.js` |

### 3.2 Diagnóstico

| ID | Requisito | Status | Onde |
|---|---|---|---|
| RF-10 | Página inicial com hero, slogan, texto institucional e os CTAs “Explorar os dados” e “Conhecer o projeto” | Atendido | Início |
| RF-11 | KPIs: pacientes, % dentro, % acima de 60 dias, média, mediana, maior tempo, municípios e estabelecimentos | Atendido | Visão Executiva |
| RF-12 | Tendência mensal, comparação anual, variação entre anos e sparklines | Atendido | Visão Executiva |
| RF-13 | Distância até a meta legal (gauge de % dentro do prazo vs 100%) | Atendido | Visão Executiva |
| RF-14 | Régua temporal Dia 0 → 30 → 45 → 60 → acima de 60 | Atendido | Panorama |
| RF-15 | Classificação dentro / próximo do limite / acima do prazo | Atendido | Panorama |
| RF-16 | Distribuição em 0–30, 31–45, 46–60, 61–90, 91–120 e 121+ dias, também por ano | Atendido | Panorama |

### 3.3 Localização e gargalos

| ID | Requisito | Status | Onde |
|---|---|---|---|
| RF-20 | KPIs de demanda, oferta (CACON/UNACON) e pressão assistencial | Atendido | Demanda & Oferta |
| RF-21 | Rankings: maior demanda, menor oferta relativa, maior pressão, maior % acima de 60 dias | Atendido | Demanda & Oferta |
| RF-22 | Aviso explícito de que demanda/oferta não equivale à existência de vaga | Atendido | Demanda & Oferta |
| RF-23 | Fluxos de pacientes entre regiões (Sankey) | Atendido | Demanda & Oferta |
| RF-24 | Mapa interativo de SP por DRS, com métrica selecionável, municípios e unidades | Atendido | Mapa |
| RF-25 | Clique na região mostra demanda, oferta, % acima de 60, tempo, unidades e filtra a plataforma | Atendido | Mapa |
| RF-26 | Alertas CRÍTICO, ATENÇÃO, MONITORAR e OPORTUNIDADE baseados em regras | Atendido | Gargalos |
| RF-27 | Municípios críticos e fatores relacionados por região | Atendido | Gargalos |
| RF-28 | Cartões ATENÇÃO, RISCO, OPORTUNIDADE e AÇÃO SUGERIDA, com fundamento visível | Atendido | Visão Executiva, Gargalos |

### 3.4 Apoio à decisão

| ID | Requisito | Status | Onde |
|---|---|---|---|
| RF-30 | Localizador por município de origem ou DRS | Atendido | Para onde encaminhar? |
| RF-31 | Exibir nome, município, CNES, tipo de habilitação, distância estimada e informações assistenciais | Atendido (endereço: indisponível nas bases carregadas, link para a ficha CNES) | Para onde encaminhar? |
| RF-32 | Ordenar por proximidade → compatibilidade → informações disponíveis | Atendido | `analytics.py::localizador` |
| RF-33 | Nunca afirmar vaga; aviso de que não há ocupação em tempo real | Atendido | Para onde encaminhar? |
| RF-34 | Exemplo demonstrativo de São Bernardo do Campo | Atendido | Botão “Exemplo” |
| RF-35 | Simulador em 4 etapas identificado como AMBIENTE DE SIMULAÇÃO | Atendido | Simulação |
| RF-36 | Cenários: capacidade normal, demanda elevada, unidade indisponível, aumento de demanda, redistribuição regional | Atendido | Simulação |
| RF-37 | Resultado com cenário atual, simulado, alternativa, impacto, variação do tempo, deslocamento e distribuição da demanda | Atendido | Simulação |
| RF-38 | Premissas ajustáveis, limitações e dados necessários para tornar a recomendação operacional | Atendido | Simulação |

### 3.5 Aprofundamento e transparência

| ID | Requisito | Status | Onde |
|---|---|---|---|
| RF-40 | Área de incorporação do Power BI com configuração centralizada, carregamento e mensagem de indisponível | Preparado (falta o link do relatório) | Power BI, `POWERBI_EMBED_URL` |
| RF-41 | Documentar embed, atualização, permissões, riscos do “Publicar na Web” e alternativas privadas | Atendido | `docs/INTEGRACOES.md`, página Power BI |
| RF-42 | Interface “Pergunte aos dados” e chat preparados para o Oracle Select AI, sem IA simulada | Preparado (faltam credenciais Oracle) | Inteligência Artificial, `/api/ia/perguntar` |
| RF-43 | Fontes, período, tratamento, limpeza, transformação e limitações | Atendido | Dados & Metodologia |
| RF-44 | Pipeline visual e arquitetura tecnológica | Atendido | Dados & Metodologia |
| RF-45 | Qualidade dos dados: completude, consistência, atualidade, duplicidade, cobertura, confiabilidade | Atendido | Dados & Metodologia |
| RF-46 | Central de indicadores | Atendido | Dados & Metodologia |
| RF-47 | Privacidade e ética; lista de limitações | Atendido | Dados & Metodologia |
| RF-48 | Página institucional com equipe Dataholics | Atendido | Sobre |

### 3.6 Filtros globais

| ID | Requisito | Status |
|---|---|---|
| RF-50 | Filtros: ano, mês, DRS, município, estabelecimento, tipo de tratamento, situação do prazo | Atendido |
| RF-51 | Alternância residência da paciente ou local de tratamento | Atendido |
| RF-52 | Chips de filtros ativos, remoção individual e “Limpar filtros” | Atendido |
| RF-53 | Filtros persistem na sessão do navegador e recalculam todas as análises no servidor | Atendido |
| RF-54 | CID fixo em C50 (único CID da base), exibido como contexto | Atendido |

## 4. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | Dias até o tratamento = data de início do tratamento − data do diagnóstico. |
| RN-02 | Fora do prazo: mais de 60 dias. Dentro do prazo: até 60 dias. |
| RN-03 | Situação: dentro 0–45 · próximo do limite 46–60 · acima > 60. |
| RN-04 | Registros com tratamento anterior ao diagnóstico são descartados (765 de 46.181). |
| RN-05 | Município → DRS pela malha oficial dos 645 municípios; residência fora de SP é agrupada como “Fora do Estado de SP”. |
| RN-06 | Alertas comparam os dois últimos anos fechados: CRÍTICO ≥ 70% e variação > 0; ATENÇÃO variação > +5 p.p.; OPORTUNIDADE < 55% e variação ≤ 0; MONITORAR demais. Mínimo de 30 casos por ano. |
| RN-07 | Grupos com menos de 10 casos: percentuais e medianas suprimidos (“<10”). Rankings exigem 30 casos. |
| RN-08 | Pressão assistencial = casos no ano ÷ estabelecimentos CACON/UNACON do mesmo ano e DRS. |
| RN-09 | Compatibilidade da unidade: “confirmada” com habilitação documentada na CIB-SP; “observada” com ≥ 30 casos C50 tratados na base; demais omitidas. |
| RN-10 | Distância estimada: Haversine entre sedes municipais (IBGE). |
| RN-11 | Simulação: período base = dois últimos anos fechados; município precisa de ≥ 20 casos; alternativas com ≥ 50 casos no período. |
| RN-12 | Modelo de congestionamento: fator = (1 − q) + q · g(ρ₀·L)/g(ρ₀), g(ρ) = ρ/(1 − ρ), ρ limitado a 0,97; ρ₀ (utilização de base) e q (parte sensível à fila) são premissas do usuário. |
| RN-13 | Recomendações seguem regras explícitas (seção “Fundamento” de cada cartão) e nunca constituem decisão clínica. |

## 5. Requisitos de dados

| ID | Requisito | Status |
|---|---|---|
| RD-01 | Nunca inventar dados, hospitais, leitos, capacidade ou indicadores | Atendido (a ocupação fictícia da versão anterior foi removida) |
| RD-02 | Selos DADO REAL, ESTIMATIVA, SIMULAÇÃO, PROJEÇÃO, DEMONSTRAÇÃO e PREMISSA | Atendido |
| RD-03 | ETL reprodutível e validado contra números publicados | Atendido (`etl/relatorio_validacao.md`: 0 divergências) |
| RD-04 | Camada de abstração para trocar a base local pelo Oracle sem alterar a interface | Preparado (`BaseLocal` + `server/oracle`) |
| RD-05 | Não carregar dados gigantes no navegador | Atendido (API agregada; base de 45 mil casos fica no servidor) |

## 6. Requisitos não funcionais

### 6.1 Segurança

| ID | Requisito | Implementação |
|---|---|---|
| RS-01 | Senha nunca em texto puro | Hash PBKDF2-SHA256, 600.000 iterações, comparação em tempo constante |
| RS-02 | Sessão segura | Cookie assinado, HttpOnly, SameSite=Lax, Secure em produção, validade de 8 h |
| RS-03 | Proteção contra força bruta | 5 tentativas erradas por IP bloqueiam por 15 min (HTTP 429) |
| RS-04 | Proteção CSRF | Cabeçalho `X-Requested-With` obrigatório em POST e verificação de `Origin` |
| RS-05 | Aplicação e API acessíveis só com sessão | `/app/*` redireciona para `/login`; `/api/*` responde 401 |
| RS-06 | Cabeçalhos de segurança | CSP restritiva (sem scripts externos), HSTS, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy |
| RS-07 | Nenhum segredo no frontend | Credenciais Oracle, wallet e segredos só em variáveis de ambiente do servidor |
| RS-08 | Validação de entradas | Pydantic e regex para todos os parâmetros; `bind variables` no SQL |
| RS-09 | Não indexação | `X-Robots-Tag: noindex` e `robots.txt` |
| RS-10 | Documentação da API oculta em produção | `docs_url` e `openapi_url` desativados |

### 6.2 Privacidade (LGPD)

| ID | Requisito | Implementação |
|---|---|---|
| RP-01 | Não exibir nome, CPF, CNS, endereço residencial, telefone ou identificadores | Nenhum desses campos existe em qualquer camada |
| RP-02 | Minimização | ETL descarta código do caso, data de nascimento e datas exatas |
| RP-03 | Agregação | API devolve apenas agregados, com supressão abaixo de 10 casos |
| RP-04 | Finalidade | Monitoramento da lei e gestão pública; aviso de não uso clínico |
| RP-05 | Repositório | Deve ser privado (documentado) |

### 6.3 Qualidade de uso

| ID | Requisito | Evidência |
|---|---|---|
| RNF-01 | Desempenho | Base carrega em ~0,3 s; painel sem filtros em ~0,2 s; com filtros ~0,07 s; respostas em cache |
| RNF-02 | Responsividade | Desktop prioritário; breakpoints 1280/1100/960/640 px; menu lateral recolhível; tabelas com rolagem |
| RNF-03 | Acessibilidade | Link “Pular para o conteúdo”, foco visível, `aria-*` em navegação, modal e alertas, respeito a `prefers-reduced-motion` |
| RNF-04 | Manutenibilidade | Frontend modular por página; servidor em módulos; nenhuma dependência de build |
| RNF-05 | Testabilidade | 33 testes automatizados (`tests/test_plataforma.py`) |
| RNF-06 | Disponibilidade | Plano gratuito do Render hiberna após 15 min sem uso; plano Starter elimina a espera |

## 7. Critérios de aceite

| Critério | Verificação |
|---|---|
| Identidade Prazo60 preservada, layout profissional e responsivo | Revisão visual; logo e paleta originais |
| Navegação, filtros, gráficos, mapa, localizador e simulador funcionando | Teste manual de todas as páginas no navegador, sem erros de console da aplicação |
| Power BI e Select AI preparados | Estados “aguardando configuração” e “roadmap técnico”; endpoints prontos |
| Fontes identificadas, dados reais separados de simulados, fórmulas e limitações documentadas | Selos em todas as seções; central de indicadores; aba Limitações |
| Frontend organizado, dados separados, APIs preparadas, segurança respeitada | Estrutura de pastas; testes de segurança |
| Demonstrar problema → evidência → localização → alternativa → simulação → solução | Modo Apresentação e “Caso de uso completo” na página inicial |
| Números corretos | KPIs e alertas conferidos por teste com os valores publicados anteriormente |

## 8. Dependências externas (ações do grupo)

| Dependência | Para quê | Quem |
|---|---|---|
| Conta no GitHub (repositório privado) e no Render | Colocar o site online | Grupo |
| Link de incorporação do relatório Power BI | Exibir o relatório na página Power BI | Grupo |
| Usuário somente leitura, wallet e perfil `PRAZO60_AI` no Prazo60DB | Ativar o Prazo60 AI | Grupo |
| Consulta à API CNES/DATASUS | Nome e endereço das 94 unidades sem nome confirmado | Roadmap |
| Integração com regulação (ex.: CROSS-SP) | Disponibilidade real de vagas | Roadmap, depende de convênio |

## 9. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Interpretar simulação como realidade | Faixa e selos de simulação, premissas visíveis, limitações e dados necessários em todo resultado |
| Interpretar localização como vaga | Aviso fixo no localizador e na página de Demanda & Oferta |
| Reidentificação em municípios pequenos | Supressão < 10 casos; nenhum dado individual na API |
| Viés dos anos recentes (casos ainda sem tratamento) | Nota nas séries e na aba Limitações |
| Link público do Power BI | Documentação dos riscos e alternativas privadas |
| Senha compartilhada vazar | Troca por variável `APP_PASSWORD_HASH` sem alterar código; bloqueio por tentativas |
| Hibernação do plano gratuito na apresentação | Abrir o site minutos antes ou usar plano Starter |

## 10. Mapa de navegação

```text
/login ──(DATAHOLICS + senha)──► /app/#/inicio
                                   │
   Entender   ├─ #/inicio · #/executiva · #/panorama
   Localizar  ├─ #/demanda-oferta · #/mapa · #/gargalos
   Agir       ├─ #/encaminhar ──► #/simulacao
   Aprofundar └─ #/powerbi · #/ia · #/dados · #/sobre

Modo Apresentação: Problema → Impacto → Dados → Diagnóstico → Demanda & Oferta → Gargalos →
Localizador → Simulação → Power BI → IA → Solução → Impacto esperado
```
