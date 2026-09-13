# Prazo 60

Plataforma digital que monitora o cumprimento da Lei 12.732/2012 (prazo legal de 60 dias entre diagnóstico e início de tratamento oncológico no SUS), com foco em câncer de mama no estado de São Paulo.

Projeto desenvolvido para o Enterprise Challenge FIAP + Oracle (012026), turma 1TSCPV.

## O problema

O tratamento oncológico deve ser iniciado em até 60 dias após o diagnóstico, conforme a Lei nº 12.732/2012. Dados fragmentados, capacidade desigual entre unidades de saúde e ausência de monitoramento em tempo real geram risco de atraso, especialmente relevante por lidar com dados sensíveis de pacientes.

Análise de dados reais do DATASUS mostrou que 58,9% dos casos de câncer de mama em SP (entre os com informação de tratamento) ultrapassam esse prazo.

## O objetivo

Desenvolver uma solução que utilize dados públicos de saúde para identificar riscos de atraso no início do tratamento oncológico e apoiar a gestão na garantia do cumprimento da Lei nº 12.732/2012.

## A solução

Da informação à ação: integração de dados, monitoramento, análise preditiva e foco no paciente, entregando dashboards de acompanhamento por unidade de saúde e indicadores de risco de atraso.

## Arquitetura

1. **Fontes de dados**: SIH, SIA, CNES, SIM, IBGE (via DATASUS)
2. **ETL (tratamento)**: Python
3. **Base integrada**: SQL (Oracle Autonomous Database)
4. **Camada de análise**: SQL
5. **Dashboards**: Power BI

## Fontes de dados

- SIH (Sistema de Informações Hospitalares)
- SIA (Sistema de Informações Ambulatoriais)
- CNES (Cadastro Nacional de Estabelecimentos de Saúde)
- SIM (Sistema de Informações sobre Mortalidade)
- IBGE (Indicadores Demográficos)
- PAINEL-Oncologia (DATASUS/INCA), via TabNet e microdados brutos (FTP público)
- RHC/INCA (Registro Hospitalar de Câncer), como fonte complementar de validação

## Demonstração

Link do dashboard (Power BI): _[completar]_

Vídeo pitch (YouTube): _[completar]_

## Estrutura do repositório

```
sprint1_ideacao/        → Documento de ideação (Sprint 1)
sprint2_arquitetura/    → Diagramas de arquitetura e protótipos (Sprint 2)
sprint3_construcao/     → Entregas por disciplina (Sprint 3)
  ├── data_ethics_governance/
  ├── smart_sql/
  ├── data_driven_apps/
  ├── data_architecture_nosql/
  ├── modern_data_architecture/
  └── statistical_methods/
sprint4_solucao_final/  → Apresentação final, vídeo pitch, evidências
dados/exemplos/         → Bases tratadas usadas no projeto
```

## Time Dataholics

- Amanda Barral (RM569662)
- Eduardo Bambulim (RM573228)
- Gabriela Fernandes (RM568972)
- Júlia Furiate (RM570547)
- Lívia Santos (RM573963)
