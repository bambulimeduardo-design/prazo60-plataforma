# Relatorio de validacao do ETL

## KPI geral
- total_casos: recalculado=45416 | site anterior=45416 | OK
- pct_dentro_60: recalculado=38.7 | site anterior=38.7 | OK
- pct_fora_60: recalculado=61.3 | site anterior=61.3 | OK
- mediana_dias: recalculado=79.0 | site anterior=79.0 | OK
- media_dias: recalculado=112.1 | site anterior=112.1 | OK
- maior_tempo_dias: recalculado=1443 | site anterior=1443

## Por DRS (residencia)
- DRS 1: casos 16568 vs 16568, % fora 60.2 vs 60.2 -> OK
- DRS 2: casos 993 vs 993, % fora 75.3 vs 75.3 -> OK
- DRS 3: casos 924 vs 924, % fora 49.9 vs 49.9 -> OK
- DRS 4: casos 1808 vs 1808, % fora 57.6 vs 57.6 -> OK
- DRS 5: casos 857 vs 857, % fora 76.9 vs 76.9 -> OK
- DRS 6: casos 1999 vs 1999, % fora 51.3 vs 51.3 -> OK
- DRS 7: casos 4598 vs 4598, % fora 64.1 vs 64.1 -> OK
- DRS 8: casos 797 vs 797, % fora 66.8 vs 66.8 -> OK
- DRS 9: casos 1635 vs 1635, % fora 44.6 vs 44.6 -> OK
- DRS 10: casos 1617 vs 1617, % fora 56.5 vs 56.5 -> OK
- DRS 11: casos 999 vs 999, % fora 69.8 vs 69.8 -> OK
- DRS 12: casos 367 vs 367, % fora 64.6 vs 64.6 -> OK
- DRS 13: casos 1796 vs 1796, % fora 53.5 vs 53.5 -> OK
- DRS 14: casos 971 vs 971, % fora 84.3 vs 84.3 -> OK
- DRS 15: casos 2309 vs 2309, % fora 64.7 vs 64.7 -> OK
- DRS 16: casos 2460 vs 2460, % fora 69.3 vs 69.3 -> OK
- DRS 17: casos 2940 vs 2940, % fora 55.6 vs 55.6 -> OK

## Por DRS (tratamento)
- DRS 1: casos 17052 vs 17052, % fora 60.0 vs 60.0 -> OK
- DRS 2: casos 441 vs 441, % fora 65.5 vs 65.5 -> OK
- DRS 3: casos 710 vs 710, % fora 45.6 vs 45.6 -> OK
- DRS 4: casos 1629 vs 1629, % fora 57.3 vs 57.3 -> OK
- DRS 5: casos 3148 vs 3148, % fora 72.8 vs 72.8 -> OK
- DRS 6: casos 2960 vs 2960, % fora 54.4 vs 54.4 -> OK
- DRS 7: casos 4378 vs 4378, % fora 64.4 vs 64.4 -> OK
- DRS 8: casos 654 vs 654, % fora 65.1 vs 65.1 -> OK
- DRS 9: casos 1427 vs 1427, % fora 44.2 vs 44.2 -> OK
- DRS 10: casos 1553 vs 1553, % fora 56.5 vs 56.5 -> OK
- DRS 11: casos 901 vs 901, % fora 68.8 vs 68.8 -> OK
- DRS 12: casos 342 vs 342, % fora 65.5 vs 65.5 -> OK
- DRS 13: casos 1752 vs 1752, % fora 52.5 vs 52.5 -> OK
- DRS 14: casos 871 vs 871, % fora 85.6 vs 85.6 -> OK
- DRS 15: casos 2883 vs 2883, % fora 69.1 vs 69.1 -> OK
- DRS 16: casos 1806 vs 1806, % fora 70.4 vs 70.4 -> OK
- DRS 17: casos 2909 vs 2909, % fora 55.6 vs 55.6 -> OK

## Projecao do mapa
- metodo escolhido: equiretangular
- sedes municipais dentro do poligono do proprio DRS: 91.6%
- hipoteses testadas: {'bbox': 83.7, 'equiretangular': 91.6}

## Cobertura
- municipios SP: 645 (sem coordenada: 0 [])
- unidades (CNES tratantes + referencia CIB): 114, com nome confirmado: 20
- casos minimizados gravados: 45416
