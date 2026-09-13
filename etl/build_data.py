"""
Prazo60 - ETL de preparacao dos dados da plataforma.

Entradas (todas ja existentes no projeto):
  - Prazo60_Carga_Oracle/.../staging_casos.csv   (45.416 casos C50, nivel caso)
  - Prazo60_Carga_Oracle/.../02a_popular_municipios.sql (645 municipios SP -> DRS)
  - Prazo60_Carga_Oracle/.../02b_popular_unidades.sql  (CNES -> municipio, nomes confirmados)
  - js/data.js do site anterior (oferta CACON/UNACON, mapa DRS, qualidade, textos, Select AI)
  - etl/fontes/municipios_coordenadas.csv (lat/long das sedes municipais, derivado do IBGE)

Saidas (server/data, NUNCA servidas como arquivo estatico):
  - casos.csv.gz      minimizado: sem cod_caso, sem data de nascimento, sem datas exatas
  - referencia.json   dimensoes e textos de apoio
  - etl/relatorio_validacao.md  conferencia contra os numeros ja publicados no site anterior

Rodar a partir da raiz do repositorio:
    python etl/build_data.py
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PROJETOS = RAIZ.parent
CARGA = PROJETOS / "Prazo60_Carga_Oracle" / "Prazo60_Carga_Oracle" / "Prazo60_Carga_Oracle"
SAIDA = RAIZ / "server" / "data"
FONTES = RAIZ / "etl" / "fontes"

LIMITE_LEGAL = 60


def ler_data_js() -> dict:
    src = (PROJETOS / "js" / "data.js").read_text(encoding="utf-8")
    corpo = src[src.index("{"): src.rstrip().rstrip(";").rindex("}") + 1]
    return json.loads(corpo)


def ler_municipios_sql() -> dict[str, dict]:
    texto = (CARGA / "02a_popular_municipios.sql").read_text(encoding="utf-8")
    rx = re.compile(
        r"SELECT '((?:[^']|'')*)' AS NOME_MUNICIPIO, '(\d+)' AS COD_IBGE, ID_DRS FROM TB_DRS WHERE COD_DRS = 'DRS-(\d+)'"
    )
    return {
        ibge: {"nome": nome.replace("''", "'"), "drs": int(drs)}
        for nome, ibge, drs in rx.findall(texto)
    }


def ler_unidades_sql() -> dict[str, dict]:
    texto = (CARGA / "02b_popular_unidades.sql").read_text(encoding="utf-8")
    rx = re.compile(
        r"SELECT '(\d+)' AS COD_CNES, '((?:[^']|'')*)' AS NOME_UNIDADE, ID_MUNICIPIO FROM TB_MUNICIPIO WHERE NOME_MUNICIPIO = '((?:[^']|'')*)'"
    )
    unidades = {}
    for cnes, nome, municipio in rx.findall(texto):
        confirmado = "a confirmar" not in nome
        unidades[cnes] = {
            "nome": nome.replace("''", "'") if confirmado else None,
            "municipio_nome_sql": municipio.replace("''", "'"),
        }
    return unidades


def ler_coordenadas() -> dict[str, tuple[float, float]]:
    """codigo IBGE de 7 digitos no arquivo -> 6 digitos (sem verificador), como na base de casos."""
    coords = {}
    with (FONTES / "municipios_coordenadas.csv").open(encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            if linha["codigo_uf"] == "35":
                coords[linha["codigo_ibge"][:6]] = (float(linha["latitude"]), float(linha["longitude"]))
    return coords


def ler_casos() -> list[dict]:
    with (CARGA / "staging_casos.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


# ---------------------------------------------------------------- geometria

def parse_path(d: str) -> list[list[tuple[float, float]]]:
    aneis, atual = [], []
    for cmd, x, y in re.findall(r"([MLZ]?)\s*(-?[\d.]+),(-?[\d.]+)", d):
        if cmd == "M" and atual:
            aneis.append(atual)
            atual = []
        atual.append((float(x), float(y)))
    if atual:
        aneis.append(atual)
    return aneis


def ponto_no_poligono(x: float, y: float, aneis) -> bool:
    dentro = False
    for anel in aneis:
        n = len(anel)
        j = n - 1
        for i in range(n):
            xi, yi = anel[i]
            xj, yj = anel[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                dentro = not dentro
            j = i
    return dentro


def ajustar_projecao(mapa: dict, municipios: dict, coords: dict) -> dict:
    """
    O SVG dos DRS foi gerado a partir da malha do IBGE, mas a projecao usada nao foi
    documentada. Testamos duas hipoteses de transformacao linear (bbox a bbox, e
    equiretangular com aspecto preservado) e escolhemos a que coloca mais sedes
    municipais dentro do poligono do proprio DRS. A taxa de acerto vai para o relatorio.
    """
    poligonos = {int(k): parse_path(v) for k, v in mapa["paths"].items()}
    xs = [p[0] for aneis in poligonos.values() for anel in aneis for p in anel]
    ys = [p[1] for aneis in poligonos.values() for anel in aneis for p in anel]
    pontos = [(ibge, coords[ibge]) for ibge in municipios if ibge in coords]
    lats = [c[0] for _, c in pontos]
    lons = [c[1] for _, c in pontos]

    def taxa(fx, fy):
        ok = sum(
            ponto_no_poligono(fx(lon), fy(lat), poligonos[municipios[ibge]["drs"]])
            for ibge, (lat, lon) in pontos
        )
        return ok / len(pontos)

    candidatos = {}

    ax = (max(xs) - min(xs)) / (max(lons) - min(lons))
    ay = (max(ys) - min(ys)) / (max(lats) - min(lats))
    candidatos["bbox"] = (
        {"x_escala": ax, "x_desloc": min(xs) - ax * min(lons), "y_escala": -ay, "y_desloc": max(ys) + ay * min(lats)}
    )

    cos_lat = math.cos(math.radians((max(lats) + min(lats)) / 2))
    escala = min((max(xs) - min(xs)) / ((max(lons) - min(lons)) * cos_lat), (max(ys) - min(ys)) / (max(lats) - min(lats)))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    clon, clat = (max(lons) + min(lons)) / 2, (max(lats) + min(lats)) / 2
    candidatos["equiretangular"] = {
        "x_escala": escala * cos_lat, "x_desloc": cx - escala * cos_lat * clon,
        "y_escala": -escala, "y_desloc": cy + escala * clat,
    }

    resultados = {}
    for nome, p in candidatos.items():
        resultados[nome] = taxa(lambda lon, p=p: p["x_escala"] * lon + p["x_desloc"],
                                lambda lat, p=p: p["y_escala"] * lat + p["y_desloc"])
    melhor = max(resultados, key=resultados.get)
    return {"metodo": melhor, "parametros": candidatos[melhor], "taxa_acerto": round(resultados[melhor] * 100, 1), "testados": {k: round(v * 100, 1) for k, v in resultados.items()}}


# ---------------------------------------------------------------- agregados de conferencia

def resumo(dias: list[int]) -> dict:
    n = len(dias)
    fora = sum(d > LIMITE_LEGAL for d in dias)
    return {
        "total_casos": n,
        "pct_dentro_60": round((n - fora) / n * 100, 1),
        "pct_fora_60": round(fora / n * 100, 1),
        "mediana_dias": statistics.median(dias),
        "media_dias": round(statistics.mean(dias), 1),
    }


# ---------------------------------------------------------------- textos herdados sem acento

# Os textos metodologicos do site anterior foram escritos sem acentos. Corrigimos apenas palavras
# sem ambiguidade (ex.: "nao" -> "não"); nomes proprios, codigos (CRITICO, VENCIDO) e SQL ficam intactos.
ACENTOS = {
    "anonimizacao": "anonimização", "assistencia": "assistência", "atualizacao": "atualização", "apos": "após", "ate": "até",
    "classificacao": "classificação", "coincidencias": "coincidências", "combinacao": "combinação", "comecou": "começou",
    "comparacao": "comparação", "concentracao": "concentração", "concluidos": "concluídos", "confirmacao": "confirmação",
    "correlacao": "correlação", "corrigivel": "corrigível", "desejavel": "desejável", "deteccao": "detecção",
    "diagnostico": "diagnóstico", "distancia": "distância", "distribuicao": "distribuição", "distribuida": "distribuída",
    "especifica": "específica", "especifico": "específico", "estao": "estão", "estatico": "estático", "estatistica": "estatística",
    "estavel": "estável", "exercicio": "exercício", "exfiltracao": "exfiltração", "formula": "fórmula", "gestao": "gestão",
    "governanca": "governança", "identificacao": "identificação", "inconsistencia": "inconsistência", "inconsistencias": "inconsistências",
    "inicio": "início", "legitimas": "legítimas", "limitacao": "limitação", "limitacoes": "limitações", "maximo": "máximo",
    "media": "média", "migracao": "migração", "minimizacao": "minimização", "municipio": "município", "municipios": "municípios",
    "nao": "não", "numero": "número", "oncologico": "oncológico", "oncologicos": "oncológicos", "periodo": "período",
    "proporcao": "proporção", "prototipo": "protótipo", "publica": "pública", "referencia": "referência", "regiao": "região",
    "regioes": "regiões", "relacao": "relação", "relatorio": "relatório", "remocao": "remoção", "residencia": "residência",
    "sao": "são", "saude": "saúde", "secao": "seção", "seguranca": "segurança", "series": "séries", "sistemica": "sistêmica",
    "tipico": "típico", "transparencia": "transparência", "ultimo": "último", "unica": "única", "validas": "válidas",
    "validos": "válidos", "variacao": "variação", "ja": "já", "metodologica": "metodológica", "analise": "análise",
}
FRASES = {" e esperado e desejavel": " é esperado e desejável", "Isto e ": "Isto é ", " nao e ": " não é "}
CAMPOS_SEM_CORRECAO = {"sql_gerado", "tecnologia", "nome_tecnico"}


def acentuar(texto: str) -> str:
    for de, para in FRASES.items():
        texto = texto.replace(de, para)

    def trocar(m: re.Match) -> str:
        palavra = m.group(0)
        novo = ACENTOS.get(palavra.lower())
        if not novo:
            return palavra
        return novo.capitalize() if palavra[0].isupper() else novo

    return re.sub(r"\b[A-Za-z]+\b", trocar, texto)


def acentuar_campos(valor, chave: str | None = None):
    if chave in CAMPOS_SEM_CORRECAO:
        return valor
    if isinstance(valor, str):
        return acentuar(valor)
    if isinstance(valor, list):
        return [acentuar_campos(v) for v in valor]
    if isinstance(valor, dict):
        return {k: acentuar_campos(v, k) for k, v in valor.items()}
    return valor


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    antigo = ler_data_js()
    municipios_sql = ler_municipios_sql()
    unidades_sql = ler_unidades_sql()
    coords = ler_coordenadas()
    casos = ler_casos()

    # ---- municipios (SP) com DRS e coordenadas
    projecao = ajustar_projecao(antigo["mapa_drs"], municipios_sql, coords)
    p = projecao["parametros"]
    municipios = {}
    for ibge, m in sorted(municipios_sql.items(), key=lambda kv: kv[1]["nome"]):
        lat, lon = coords.get(ibge, (None, None))
        municipios[ibge] = {
            "nome": m["nome"],
            "drs": m["drs"],
            "lat": lat,
            "lon": lon,
            "x": round(p["x_escala"] * lon + p["x_desloc"], 2) if lon is not None else None,
            "y": round(p["y_escala"] * lat + p["y_desloc"], 2) if lat is not None else None,
        }

    # ---- unidades tratantes: municipio mais frequente de tratamento para cada CNES
    mun_por_cnes = defaultdict(Counter)
    for c in casos:
        mun_por_cnes[c["cnes_tratamento"]][c["mun_tratamento_ibge"]] += 1

    referencia_cib = {h["cnes"]: h for h in antigo["hospitais_referencia"]}
    nome_por_ibge = {ibge: m["nome"] for ibge, m in municipios.items()}
    ibge_por_nome = {m["nome"]: ibge for ibge, m in municipios.items()}

    unidades = {}
    todos_cnes = set(mun_por_cnes) | set(referencia_cib)
    for cnes in sorted(todos_cnes):
        ref = referencia_cib.get(cnes)
        sql = unidades_sql.get(cnes, {})
        if cnes in mun_por_cnes:
            mun_ibge = mun_por_cnes[cnes].most_common(1)[0][0]
        else:
            mun_ibge = ibge_por_nome.get(sql.get("municipio_nome_sql", ""))
        nome = (ref or {}).get("nome") or sql.get("nome")
        unidades[cnes] = {
            "cnes": cnes,
            "nome": nome,
            "nome_confirmado": nome is not None,
            "municipio_ibge": mun_ibge,
            "fora_sp": mun_ibge is None or not str(mun_ibge).startswith("35"),
            "habilitacao": (ref or {}).get("tipo"),
            "gestao": (ref or {}).get("gestao"),
            "fonte_habilitacao": "Deliberacoes CIB-SP (validado pelo grupo)" if ref else None,
        }

    # ---- casos minimizados
    linhas_min = []
    for c in casos:
        dd, mm, aaaa = c["data_diagnostico"].split("/")
        linhas_min.append({
            "ano": aaaa,
            "mes": mm,
            "mun_res": c["mun_residencia_ibge"],
            "mun_trat": c["mun_tratamento_ibge"],
            "cnes": c["cnes_tratamento"],
            "tipo": c["nome_tipo_tratamento"],
            "dias": c["dias_espera"],
        })
    with gzip.open(SAIDA / "casos.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas_min[0].keys()))
        w.writeheader()
        w.writerows(linhas_min)

    # ---- DRS
    drs = {}
    oferta_ano = defaultdict(dict)
    for o in antigo["oferta_por_drs_ano"]:
        oferta_ano[o["drs"]][str(o["ano"])] = {"mamografias_rastreio": o["ccmec50a69"], "estabelecimentos_cacon_unacon": o["ccmhhcac"]}
    for o in antigo["oferta_por_drs"]:
        drs[o["drs"]] = {
            "numero": o["drs"],
            "nome": antigo["drs_nomes"][str(o["drs"])],
            "oferta_2025": {"mamografias_rastreio": o["ccmec50a69"], "estabelecimentos_cacon_unacon": o["ccmhhcac"]},
            "oferta_por_ano": oferta_ano[o["drs"]],
        }

    referencia = {
        "meta": {
            **antigo["meta"],
            "gerado_por": "etl/build_data.py",
            "fonte_coordenadas": "kelvins/municipios-brasileiros (sede municipal, derivado do IBGE)",
            "projecao_mapa": projecao,
            "supressao_minima_casos": 10,
        },
        "drs": drs,
        "municipios": municipios,
        "unidades": unidades,
        "mapa": antigo["mapa_drs"],
        "qualidade_dados": antigo["qualidade_dados"],
        "select_ai_evidencia": antigo["select_ai_evidencia"],
        "indicadores_info": antigo["indicadores_info"],
        "privacidade_etica": antigo["privacidade_etica"],
        "pipeline_dados": antigo["pipeline_dados"],
        "arquitetura_tecnologica": antigo["arquitetura_tecnologica"],
        "apis_futuras": antigo["apis_futuras"],
        "alertas_metodologia": antigo["drs_alertas_metodologia"],
        "hospitais_referencia_fonte": antigo["hospitais_referencia_fonte"],
    }
    for chave in ("qualidade_dados", "select_ai_evidencia", "indicadores_info", "privacidade_etica", "pipeline_dados",
                  "arquitetura_tecnologica", "apis_futuras", "alertas_metodologia", "hospitais_referencia_fonte"):
        referencia[chave] = acentuar_campos(referencia[chave])
    (SAIDA / "referencia.json").write_text(json.dumps(referencia, ensure_ascii=False), encoding="utf-8")

    # ---- conferencia contra o site anterior
    rel = ["# Relatorio de validacao do ETL", ""]
    dias_todos = [int(c["dias_espera"]) for c in casos]
    geral = resumo(dias_todos)
    rel.append("## KPI geral")
    for k, v in geral.items():
        ant = antigo["kpi_geral"].get(k)
        rel.append(f"- {k}: recalculado={v} | site anterior={ant} | {'OK' if float(v) == float(ant) else 'DIVERGE'}")
    rel.append(f"- maior_tempo_dias: recalculado={max(dias_todos)} | site anterior={antigo['kpi_geral']['maior_tempo_dias']}")

    divergencias = 0
    for dim, campo, chave_antiga in (("residencia", "mun_residencia_ibge", "por_drs_residencia"), ("tratamento", "mun_tratamento_ibge", "por_drs_tratamento")):
        grupos = defaultdict(list)
        for c in casos:
            m = municipios.get(c[campo])
            if m:
                grupos[m["drs"]].append(int(c["dias_espera"]))
        rel += ["", f"## Por DRS ({dim})"]
        for a in antigo[chave_antiga]:
            r = resumo(grupos[a["drs"]])
            ok = r["total_casos"] == a["total_casos"] and r["pct_fora_60"] == a["pct_fora_60"]
            divergencias += not ok
            rel.append(f"- DRS {a['drs']}: casos {r['total_casos']} vs {a['total_casos']}, % fora {r['pct_fora_60']} vs {a['pct_fora_60']} -> {'OK' if ok else 'DIVERGE'}")

    rel += ["", "## Projecao do mapa", f"- metodo escolhido: {projecao['metodo']}", f"- sedes municipais dentro do poligono do proprio DRS: {projecao['taxa_acerto']}%", f"- hipoteses testadas: {projecao['testados']}"]
    sem_coord = [m["nome"] for m in municipios.values() if m["lat"] is None]
    rel += ["", "## Cobertura", f"- municipios SP: {len(municipios)} (sem coordenada: {len(sem_coord)} {sem_coord[:5]})",
            f"- unidades (CNES tratantes + referencia CIB): {len(unidades)}, com nome confirmado: {sum(u['nome_confirmado'] for u in unidades.values())}",
            f"- casos minimizados gravados: {len(linhas_min)}"]
    (RAIZ / "etl" / "relatorio_validacao.md").write_text("\n".join(rel) + "\n", encoding="utf-8")
    print("\n".join(rel))
    print(f"\nDivergencias por DRS: {divergencias}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
