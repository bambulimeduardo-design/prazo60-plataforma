"""
Consultas SQL que replicam, contra o Oracle real, os mesmos indicadores que
hoje vem prontos no data.js estatico do site.

Nao cobre ainda: oferta_por_drs (mamografias, CACON/UNACON), mapa (poligonos
de DRS) e sankey (fluxo de migracao). Esses tres dependem de fontes que ainda
nao foram carregadas neste banco (a planilha prazo60_analitico.xlsx tem esse
dado, mas ele vive fora do Oracle ate hoje). Ver README para o plano.
"""

from .database import query_all, query_one

CAMPO_MUNICIPIO_POR_DIMENSAO = {
    "residencia": "c.ID_MUNICIPIO_RESIDENCIA",
    "tratamento": "ut.ID_MUNICIPIO",
}


def get_kpi_geral() -> dict:
    sql = """
        SELECT
            COUNT(*) AS total_casos,
            ROUND(SUM(CASE WHEN t.DIAS_ESPERA <= 60 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS pct_dentro_60,
            ROUND(SUM(CASE WHEN t.DIAS_ESPERA > 60 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS pct_fora_60,
            MEDIAN(t.DIAS_ESPERA) AS mediana_dias,
            ROUND(AVG(t.DIAS_ESPERA), 1) AS media_dias,
            MAX(t.DIAS_ESPERA) AS maior_tempo_dias
        FROM TB_TRATAMENTO t
    """
    return query_one(sql)


def get_por_drs(dimensao: str, ano: int | None) -> list[dict]:
    """dimensao: 'residencia' ou 'tratamento'."""
    campo_municipio = CAMPO_MUNICIPIO_POR_DIMENSAO[dimensao]
    filtro_ano = "AND EXTRACT(YEAR FROM c.DATA_DIAGNOSTICO) = :ano" if ano else ""

    sql = f"""
        SELECT
            d.COD_DRS AS drs,
            d.NOME_DRS AS drs_nome,
            COUNT(*) AS total_casos,
            ROUND(SUM(CASE WHEN t.DIAS_ESPERA <= 60 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS pct_dentro_60,
            ROUND(SUM(CASE WHEN t.DIAS_ESPERA > 60 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS pct_fora_60,
            MEDIAN(t.DIAS_ESPERA) AS mediana_dias
        FROM TB_CASO_PACIENTE c
        JOIN TB_TRATAMENTO t ON t.ID_CASO = c.ID_CASO
        JOIN TB_UNIDADE_SAUDE ut ON ut.ID_UNIDADE = t.ID_UNIDADE_TRATAMENTO
        JOIN TB_MUNICIPIO m ON m.ID_MUNICIPIO = {campo_municipio}
        JOIN TB_DRS d ON d.ID_DRS = m.ID_DRS
        WHERE 1=1 {filtro_ano}
        GROUP BY d.COD_DRS, d.NOME_DRS
        ORDER BY d.COD_DRS
    """
    return query_all(sql, {"ano": ano} if ano else None)


def get_temporal_ano(dimensao: str = "tratamento") -> list[dict]:
    campo_municipio = CAMPO_MUNICIPIO_POR_DIMENSAO[dimensao]
    sql = f"""
        SELECT
            EXTRACT(YEAR FROM c.DATA_DIAGNOSTICO) AS ano,
            COUNT(*) AS total_casos,
            ROUND(SUM(CASE WHEN t.DIAS_ESPERA <= 60 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS pct_dentro_60,
            ROUND(SUM(CASE WHEN t.DIAS_ESPERA > 60 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS pct_fora_60,
            MEDIAN(t.DIAS_ESPERA) AS mediana_dias,
            MAX(t.DIAS_ESPERA) AS maior_tempo_dias
        FROM TB_CASO_PACIENTE c
        JOIN TB_TRATAMENTO t ON t.ID_CASO = c.ID_CASO
        JOIN TB_UNIDADE_SAUDE ut ON ut.ID_UNIDADE = t.ID_UNIDADE_TRATAMENTO
        GROUP BY EXTRACT(YEAR FROM c.DATA_DIAGNOSTICO)
        ORDER BY ano
    """
    return query_all(sql)


def get_drs_alertas(dimensao: str = "residencia") -> list[dict]:
    """
    Classificacao CRITICO/ATENCAO/MONITORAR/OPORTUNIDADE por DRS, comparando
    o ultimo ano fechado contra o anterior. A agregacao roda em SQL; a regra
    de classificacao roda aqui em Python, para ficar legivel e facil de ajustar
    sem reescrever a query (mesma logica ja documentada na secao Alertas do site).
    """
    campo_municipio = CAMPO_MUNICIPIO_POR_DIMENSAO[dimensao]
    sql = f"""
        SELECT
            d.COD_DRS AS drs,
            d.NOME_DRS AS drs_nome,
            EXTRACT(YEAR FROM c.DATA_DIAGNOSTICO) AS ano,
            COUNT(*) AS total_casos,
            ROUND(SUM(CASE WHEN t.DIAS_ESPERA > 60 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS pct_fora_60
        FROM TB_CASO_PACIENTE c
        JOIN TB_TRATAMENTO t ON t.ID_CASO = c.ID_CASO
        JOIN TB_UNIDADE_SAUDE ut ON ut.ID_UNIDADE = t.ID_UNIDADE_TRATAMENTO
        JOIN TB_MUNICIPIO m ON m.ID_MUNICIPIO = {campo_municipio}
        JOIN TB_DRS d ON d.ID_DRS = m.ID_DRS
        GROUP BY d.COD_DRS, d.NOME_DRS, EXTRACT(YEAR FROM c.DATA_DIAGNOSTICO)
        ORDER BY d.COD_DRS, ano
    """
    linhas = query_all(sql)

    por_drs = {}
    for linha in linhas:
        por_drs.setdefault(linha["drs"], []).append(linha)

    resultado = []
    for drs, anos in por_drs.items():
        anos_ordenados = sorted(anos, key=lambda x: x["ano"])
        if len(anos_ordenados) < 2:
            continue
        recente, anterior = anos_ordenados[-1], anos_ordenados[-2]
        variacao = round(recente["pct_fora_60"] - anterior["pct_fora_60"], 1)

        if recente["pct_fora_60"] >= 70 and variacao > 0:
            classificacao = "CRITICO"
        elif variacao > 5:
            classificacao = "ATENCAO"
        elif recente["pct_fora_60"] < 55 and variacao <= 0:
            classificacao = "OPORTUNIDADE"
        else:
            classificacao = "MONITORAR"

        resultado.append({
            "drs": drs,
            "drs_nome": recente["drs_nome"],
            "ano_recente": recente["ano"],
            "ano_anterior": anterior["ano"],
            "pct_fora_recente": recente["pct_fora_60"],
            "pct_fora_anterior": anterior["pct_fora_60"],
            "variacao_pp": variacao,
            "casos_ano_recente": recente["total_casos"],
            "classificacao": classificacao,
        })
    return resultado


def get_qualidade_dados() -> dict:
    sql = """
        SELECT
            COUNT(*) AS total_casos,
            MAX(c.DATA_DIAGNOSTICO) AS diagnostico_mais_recente,
            MAX(t.DATA_INICIO_TRATAMENTO) AS tratamento_mais_recente,
            SUM(CASE WHEN u.NOME_UNIDADE LIKE '%nome a confirmar%' THEN 0 ELSE 1 END) AS unidades_com_nome_confirmado,
            COUNT(DISTINCT t.ID_UNIDADE_TRATAMENTO) AS unidades_distintas
        FROM TB_CASO_PACIENTE c
        JOIN TB_TRATAMENTO t ON t.ID_CASO = c.ID_CASO
        JOIN TB_UNIDADE_SAUDE u ON u.ID_UNIDADE = t.ID_UNIDADE_TRATAMENTO
    """
    return query_one(sql)


def get_unidades_saude() -> list[dict]:
    sql = """
        SELECT
            u.COD_CNES AS cnes,
            u.NOME_UNIDADE AS nome,
            m.NOME_MUNICIPIO AS municipio,
            d.COD_DRS AS drs,
            d.NOME_DRS AS drs_nome,
            CASE WHEN u.NOME_UNIDADE LIKE '%nome a confirmar%' THEN 0 ELSE 1 END AS nome_confirmado
        FROM TB_UNIDADE_SAUDE u
        JOIN TB_MUNICIPIO m ON m.ID_MUNICIPIO = u.ID_MUNICIPIO
        JOIN TB_DRS d ON d.ID_DRS = m.ID_DRS
        ORDER BY d.COD_DRS, u.NOME_UNIDADE
    """
    return query_all(sql)
