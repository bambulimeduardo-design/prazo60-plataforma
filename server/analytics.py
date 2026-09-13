"""
Motor analitico local do Prazo60.

Le a base minimizada (server/data/casos.csv.gz) e devolve SOMENTE agregados.
Nenhum endpoint devolve linha individual. Grupos com menos de MIN_CASOS_EXIBICAO
casos tem percentuais e medianas suprimidos (protecao contra reidentificacao).

O contrato de saida (dicionarios) e o mesmo que um provedor Oracle devera
respeitar no futuro: o frontend nao sabe de onde o numero veio.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock

LIMITE_LEGAL = 60
LIMIAR_PROXIMO = 45
MIN_CASOS_EXIBICAO = 10
MIN_CASOS_RANKING = 30

FAIXAS = (("0-30", 0, 30), ("31-45", 31, 45), ("46-60", 46, 60), ("61-90", 61, 90), ("91-120", 91, 120), ("121+", 121, None))
SITUACOES = {"dentro": (0, LIMIAR_PROXIMO), "limite": (LIMIAR_PROXIMO + 1, LIMITE_LEGAL), "acima": (LIMITE_LEGAL + 1, None)}
FORA_SP = "Fora do Estado de SP"


@dataclass(frozen=True, slots=True)
class Caso:
    ano: int
    mes: int
    mun_res: str
    mun_trat: str
    cnes: str
    tipo: str
    dias: int
    drs_res: int  # 0 = fora de SP
    drs_trat: int


@dataclass(frozen=True)
class Filtros:
    ano: int | None = None
    mes: int | None = None
    drs: int | None = None
    municipio: str | None = None
    cnes: str | None = None
    tipo: str | None = None
    situacao: str | None = None
    dimensao: str = "residencia"


class DadosInsuficientes(ValueError):
    """Recorte com poucos casos para calcular algo com seguranca estatistica e de privacidade."""


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def resumir(dias: list[int], minimo: int = MIN_CASOS_EXIBICAO) -> dict:
    n = len(dias)
    vazio = {"pct_dentro_60": None, "pct_fora_60": None, "mediana_dias": None, "media_dias": None, "maior_tempo_dias": None}
    if n == 0:
        return {"n": 0, "suprimido": False, **vazio}
    if n < minimo:
        return {"n": None, "suprimido": True, **vazio}
    fora = sum(1 for d in dias if d > LIMITE_LEGAL)
    return {
        "n": n,
        "suprimido": False,
        "pct_dentro_60": round(100 * (n - fora) / n, 1),
        "pct_fora_60": round(100 * fora / n, 1),
        "mediana_dias": float(statistics.median(dias)),
        "media_dias": round(statistics.fmean(dias), 1),
        "maior_tempo_dias": max(dias),
    }


def classificar_alerta(pct_recente: float, variacao_pp: float) -> str:
    """Mesmas regras ja documentadas no site anterior e no backend Oracle (queries.py)."""
    if pct_recente >= 70 and variacao_pp > 0:
        return "CRITICO"
    if variacao_pp > 5:
        return "ATENCAO"
    if pct_recente < 55 and variacao_pp <= 0:
        return "OPORTUNIDADE"
    return "MONITORAR"


def mediana_ponderada(pares: list[tuple[float, float]]) -> float | None:
    pares = sorted(p for p in pares if p[1] > 0)
    total = sum(p[1] for p in pares)
    if total == 0:
        return None
    acumulado = 0.0
    for valor, peso in pares:
        acumulado += peso
        if acumulado >= total / 2:
            return valor
    return pares[-1][0]


def br(valor: float | None, casas: int = 1) -> str:
    """Numero no formato brasileiro (1.234,5) para textos gerados pelo servidor."""
    if valor is None:
        return "—"
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def br_sinal(valor: float | None, casas: int = 1) -> str:
    if valor is None:
        return "—"
    return ("+" if valor > 0 else "") + br(valor, casas)


class BaseLocal:
    def __init__(self, casos: list[Caso], referencia: dict):
        self.casos = casos
        self.ref = referencia
        self.municipios: dict[str, dict] = referencia["municipios"]
        self.unidades: dict[str, dict] = referencia["unidades"]
        self.drs: dict[int, dict] = {int(k): v for k, v in referencia["drs"].items()}
        self.tipos = sorted({c.tipo for c in casos})

        meses_por_ano: dict[int, set[int]] = defaultdict(set)
        for c in casos:
            meses_por_ano[c.ano].add(c.mes)
        self.anos = sorted(meses_por_ano)
        self.anos_parciais = [a for a in self.anos if len(meses_por_ano[a]) < 12]
        self.ano_fechado = max(a for a in self.anos if a not in self.anos_parciais)
        self.periodo_base = (self.ano_fechado - 1, self.ano_fechado)

        pontos = defaultdict(list)
        for m in self.municipios.values():
            if m["lat"] is not None:
                pontos[m["drs"]].append((m["lat"], m["lon"]))
        self.centroide_drs = {d: (statistics.fmean(p[0] for p in v), statistics.fmean(p[1] for p in v)) for d, v in pontos.items()}

        self.dias_por_unidade: dict[str, list[int]] = defaultdict(list)
        self.dias_recentes_por_unidade: dict[str, list[int]] = defaultdict(list)
        for c in casos:
            self.dias_por_unidade[c.cnes].append(c.dias)
            if c.ano in self.periodo_base:
                self.dias_recentes_por_unidade[c.cnes].append(c.dias)

        self.unidades_tratantes_por_municipio = Counter(
            u["municipio_ibge"] for cnes, u in self.unidades.items() if not u["fora_sp"] and self.dias_por_unidade.get(cnes)
        )

        self._cache: dict[Filtros, dict] = {}
        self._lock = Lock()

    # ------------------------------------------------------------ carga

    @classmethod
    def carregar(cls, pasta: Path) -> "BaseLocal":
        referencia = json.loads((pasta / "referencia.json").read_text(encoding="utf-8"))
        municipios = referencia["municipios"]
        casos = []
        with gzip.open(pasta / "casos.csv.gz", "rt", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                mr, mt = municipios.get(r["mun_res"]), municipios.get(r["mun_trat"])
                casos.append(Caso(int(r["ano"]), int(r["mes"]), r["mun_res"], r["mun_trat"], r["cnes"], r["tipo"], int(r["dias"]),
                                  mr["drs"] if mr else 0, mt["drs"] if mt else 0))
        return cls(casos, referencia)

    # ------------------------------------------------------------ utilitarios

    def nome_drs(self, numero: int) -> str:
        return self.drs[numero]["nome"] if numero in self.drs else FORA_SP

    def nome_unidade(self, cnes: str) -> str:
        u = self.unidades.get(cnes)
        return u["nome"] if u and u["nome"] else f"Unidade CNES {cnes}"

    def coordenada_unidade(self, cnes: str) -> tuple[float, float] | None:
        u = self.unidades.get(cnes)
        if not u or u["fora_sp"]:
            return None
        m = self.municipios.get(u["municipio_ibge"])
        return (m["lat"], m["lon"]) if m and m["lat"] is not None else None

    def distancia_km(self, municipio: str, cnes: str) -> float | None:
        origem = self.municipios.get(municipio)
        destino = self.coordenada_unidade(cnes)
        if not origem or origem["lat"] is None or not destino:
            return None
        return haversine_km(origem["lat"], origem["lon"], *destino)

    def compatibilidade(self, cnes: str) -> str:
        u = self.unidades.get(cnes, {})
        if u.get("habilitacao"):
            return "confirmada"
        if len(self.dias_por_unidade.get(cnes, ())) >= MIN_CASOS_RANKING:
            return "observada"
        return "limitada"

    def filtrar(self, f: Filtros) -> list[Caso]:
        residencia = f.dimensao == "residencia"
        faixa = SITUACOES.get(f.situacao) if f.situacao else None
        saida = []
        for c in self.casos:
            if f.ano is not None and c.ano != f.ano:
                continue
            if f.mes is not None and c.mes != f.mes:
                continue
            if f.tipo is not None and c.tipo != f.tipo:
                continue
            if f.cnes is not None and c.cnes != f.cnes:
                continue
            if f.drs is not None and (c.drs_res if residencia else c.drs_trat) != f.drs:
                continue
            if f.municipio is not None and (c.mun_res if residencia else c.mun_trat) != f.municipio:
                continue
            if faixa and (c.dias < faixa[0] or (faixa[1] is not None and c.dias > faixa[1])):
                continue
            saida.append(c)
        return saida

    # ------------------------------------------------------------ opcoes de filtro

    def opcoes(self) -> dict:
        casos_por_municipio = Counter(c.mun_res for c in self.casos)
        recentes_por_municipio = Counter(c.mun_res for c in self.casos if c.ano in self.periodo_base)
        return {
            "anos": self.anos,
            "anos_parciais": self.anos_parciais,
            "ano_fechado": self.ano_fechado,
            "periodo_base_simulacao": list(self.periodo_base),
            "tipos_tratamento": self.tipos,
            "drs": [{"numero": n, "nome": d["nome"]} for n, d in sorted(self.drs.items())],
            "municipios": [
                {"ibge": ibge, "nome": m["nome"], "drs": m["drs"], "casos": casos_por_municipio.get(ibge, 0),
                 "simulavel": recentes_por_municipio.get(ibge, 0) >= 20}
                for ibge, m in sorted(self.municipios.items(), key=lambda kv: kv[1]["nome"])
            ],
            "unidades": sorted(
                ({"cnes": cnes, "nome": self.nome_unidade(cnes), "municipio": self.municipios.get(u["municipio_ibge"], {}).get("nome")}
                 for cnes, u in self.unidades.items() if not u["fora_sp"] and len(self.dias_por_unidade.get(cnes, ())) >= MIN_CASOS_RANKING),
                key=lambda u: u["nome"],
            ),
            "limites": {"legal": LIMITE_LEGAL, "proximo": LIMIAR_PROXIMO, "min_exibicao": MIN_CASOS_EXIBICAO, "min_ranking": MIN_CASOS_RANKING},
        }

    # ------------------------------------------------------------ painel principal

    def painel(self, f: Filtros) -> dict:
        with self._lock:
            if f in self._cache:
                return self._cache[f]
        resultado = self._calcular_painel(f)
        with self._lock:
            if len(self._cache) > 256:
                self._cache.clear()
            self._cache[f] = resultado
        return resultado

    def _calcular_painel(self, f: Filtros) -> dict:
        residencia = f.dimensao == "residencia"
        casos = self.filtrar(f)
        sem_periodo = replace(f, ano=None, mes=None)
        casos_serie = self.filtrar(sem_periodo)
        regional = replace(f, drs=None, municipio=None)
        casos_regionais = self.filtrar(regional)
        casos_regionais_serie = self.filtrar(replace(regional, ano=None, mes=None))

        kpis = resumir([c.dias for c in casos])
        kpis["municipios"] = len({c.mun_res for c in casos if c.mun_res in self.municipios})
        kpis["estabelecimentos"] = len({c.cnes for c in casos})

        return {
            "filtros": f.__dict__,
            "kpis": kpis,
            "comparacao": self._comparacao(f),
            "serie_mensal": self._serie(casos_serie, lambda c: (c.ano, c.mes)),
            "serie_anual": self._serie(casos_serie, lambda c: (c.ano,)),
            "faixas": self._faixas(casos),
            "situacao": self._situacao(casos),
            "faixas_por_ano": [{"ano": ano, "parcial": ano in self.anos_parciais, "faixas": self._faixas([c for c in casos_serie if c.ano == ano])} for ano in self.anos],
            "tipos_tratamento": [{"tipo": t, **resumir([c.dias for c in casos if c.tipo == t])} for t in self.tipos],
            "por_drs": self._por_drs(f, casos_regionais, casos_regionais_serie),
            "por_municipio": self._por_municipio(f, self.filtrar(replace(f, municipio=None))),
            "por_unidade": self._por_unidade(self.filtrar(replace(f, cnes=None))),
            "fluxos": self._fluxos(casos),
            "alertas": self._alertas_drs(casos_regionais_serie, residencia),
            "alertas_municipios": self._alertas_municipios(self.filtrar(replace(sem_periodo, municipio=None)), residencia),
            "referencias": {"ano_fechado": self.ano_fechado, "anos_parciais": self.anos_parciais, "min_exibicao": MIN_CASOS_EXIBICAO, "min_ranking": MIN_CASOS_RANKING},
        }

    def _comparacao(self, f: Filtros) -> dict:
        ano_ref = f.ano if f.ano is not None else self.ano_fechado
        anterior = ano_ref - 1 if (ano_ref - 1) in self.anos else None
        atual = resumir([c.dias for c in self.filtrar(replace(f, ano=ano_ref))])
        prev = resumir([c.dias for c in self.filtrar(replace(f, ano=anterior))]) if anterior else None
        variacao = None
        if prev and atual["n"] and prev["n"]:
            variacao = {
                "pct_fora_pp": round(atual["pct_fora_60"] - prev["pct_fora_60"], 1),
                "mediana_dias": atual["mediana_dias"] - prev["mediana_dias"],
                "casos_pct": round(100 * (atual["n"] - prev["n"]) / prev["n"], 1),
            }
        return {"ano_referencia": ano_ref, "ano_anterior": anterior, "parcial": ano_ref in self.anos_parciais, "atual": atual, "anterior": prev, "variacao": variacao}

    def _serie(self, casos: list[Caso], chave) -> list[dict]:
        grupos = defaultdict(list)
        for c in casos:
            grupos[chave(c)].append(c.dias)
        saida = []
        for k in sorted(grupos):
            item = {"ano": k[0], "parcial": k[0] in self.anos_parciais, **resumir(grupos[k])}
            if len(k) == 2:
                item["mes"] = k[1]
                item["rotulo"] = f"{k[1]:02d}/{k[0]}"
            else:
                item["rotulo"] = str(k[0])
            saida.append(item)
        return saida

    def _faixas(self, casos: list[Caso]) -> list[dict]:
        total = len(casos)
        saida = []
        for nome, ini, fim in FAIXAS:
            qtd = sum(1 for c in casos if c.dias >= ini and (fim is None or c.dias <= fim))
            saida.append({"faixa": nome, "quantidade": qtd, "percentual": round(100 * qtd / total, 1) if total else None})
        return saida

    def _situacao(self, casos: list[Caso]) -> dict:
        total = len(casos)
        saida = {}
        for nome, (ini, fim) in SITUACOES.items():
            qtd = sum(1 for c in casos if c.dias >= ini and (fim is None or c.dias <= fim))
            saida[nome] = {"quantidade": qtd, "percentual": round(100 * qtd / total, 1) if total else None}
        return saida

    def _por_drs(self, f: Filtros, casos: list[Caso], casos_serie: list[Caso]) -> list[dict]:
        residencia = f.dimensao == "residencia"
        ano_oferta = f.ano if f.ano is not None else self.ano_fechado
        grupos, grupos_ano_ref = defaultdict(list), defaultdict(int)
        fora_da_regiao = Counter()
        for c in casos:
            d = c.drs_res if residencia else c.drs_trat
            grupos[d].append(c)
            if c.drs_res and c.drs_trat != c.drs_res:
                fora_da_regiao[c.drs_res] += 1
        for c in casos_serie:
            if c.ano == ano_oferta:
                grupos_ano_ref[c.drs_res if residencia else c.drs_trat] += 1

        saida = []
        for numero, info in sorted(self.drs.items()):
            lista = grupos.get(numero, [])
            dias = [c.dias for c in lista]
            oferta = info["oferta_por_ano"].get(str(ano_oferta)) or info["oferta_2025"]
            estab = oferta["estabelecimentos_cacon_unacon"]
            casos_ref = grupos_ano_ref.get(numero, 0)
            resumo = resumir(dias)
            saida.append({
                "drs": numero,
                "nome": info["nome"],
                **resumo,
                "pct_121_mais": round(100 * sum(1 for d in dias if d > 120) / len(dias), 1) if len(dias) >= MIN_CASOS_EXIBICAO else None,
                "pct_tratado_fora_da_regiao": round(100 * fora_da_regiao[numero] / len(lista), 1) if residencia and len(lista) >= MIN_CASOS_EXIBICAO else None,
                "ano_oferta": ano_oferta,
                "estabelecimentos_cacon_unacon": estab,
                "mamografias_rastreio": oferta["mamografias_rastreio"],
                "casos_ano_oferta": casos_ref,
                "pressao_casos_por_estabelecimento": round(casos_ref / estab, 1) if estab else None,
            })
        return saida

    def _por_municipio(self, f: Filtros, casos: list[Caso]) -> list[dict]:
        residencia = f.dimensao == "residencia"
        grupos = defaultdict(list)
        for c in casos:
            ibge = c.mun_res if residencia else c.mun_trat
            if ibge in self.municipios:
                grupos[ibge].append(c)
        saida = []
        for ibge, lista in grupos.items():
            m = self.municipios[ibge]
            resumo = resumir([c.dias for c in lista])
            fora_do_municipio = sum(1 for c in lista if c.mun_trat != c.mun_res)
            saida.append({
                "ibge": ibge, "nome": m["nome"], "drs": m["drs"], "x": m["x"], "y": m["y"],
                **resumo,
                "casos_faixa": "<10" if resumo["suprimido"] else None,
                "pct_tratado_fora_do_municipio": round(100 * fora_do_municipio / len(lista), 1) if residencia and not resumo["suprimido"] else None,
                "unidades_tratantes_no_municipio": self.unidades_tratantes_por_municipio.get(ibge, 0),
            })
        saida.sort(key=lambda r: (r["n"] or 0), reverse=True)
        return saida

    def _por_unidade(self, casos: list[Caso]) -> list[dict]:
        grupos = defaultdict(list)
        for c in casos:
            grupos[c.cnes].append(c.dias)
        saida = []
        for cnes, dias in grupos.items():
            u = self.unidades.get(cnes, {})
            m = self.municipios.get(u.get("municipio_ibge"), {})
            saida.append({
                "cnes": cnes, "nome": self.nome_unidade(cnes), "nome_confirmado": bool(u.get("nome_confirmado")),
                "municipio": m.get("nome") or FORA_SP, "municipio_ibge": u.get("municipio_ibge") if m else None,
                "drs": m.get("drs"), "habilitacao": u.get("habilitacao"),
                "compatibilidade": self.compatibilidade(cnes), **resumir(dias),
            })
        saida.sort(key=lambda r: (r["n"] or 0), reverse=True)
        return saida

    def _fluxos(self, casos: list[Caso]) -> dict:
        contagem = Counter()
        for c in casos:
            origem = self.nome_drs(c.drs_res) if c.drs_res else FORA_SP
            destino = self.nome_drs(c.drs_trat) if c.drs_trat else FORA_SP
            if origem != destino:
                contagem[(origem, destino)] += 1
        total = sum(contagem.values())
        top = [{"origem": o, "destino": d, "valor": v} for (o, d), v in contagem.most_common(15) if v >= MIN_CASOS_EXIBICAO]
        return {"links": top, "total_fora_da_regiao": total, "soma_exibida": sum(l["valor"] for l in top), "total_casos": len(casos)}

    def _alertas_drs(self, casos_serie: list[Caso], residencia: bool) -> list[dict]:
        recente, anterior = self.ano_fechado, self.ano_fechado - 1
        grupos = defaultdict(lambda: defaultdict(list))
        for c in casos_serie:
            d = c.drs_res if residencia else c.drs_trat
            if d:
                grupos[d][c.ano].append(c.dias)
        saida = []
        for numero, info in sorted(self.drs.items()):
            r, a = resumir(grupos[numero][recente], MIN_CASOS_RANKING), resumir(grupos[numero][anterior], MIN_CASOS_RANKING)
            item = {"drs": numero, "nome": info["nome"], "ano_recente": recente, "ano_anterior": anterior,
                    "pct_fora_recente": r["pct_fora_60"], "pct_fora_anterior": a["pct_fora_60"], "casos_ano_recente": r["n"],
                    "mediana_recente": r["mediana_dias"]}
            if r["n"] and a["n"]:
                item["variacao_pp"] = round(r["pct_fora_60"] - a["pct_fora_60"], 1)
                item["classificacao"] = classificar_alerta(r["pct_fora_60"], item["variacao_pp"])
            else:
                item["variacao_pp"] = None
                item["classificacao"] = "DADOS_INSUFICIENTES"
            saida.append(item)
        return saida

    def _alertas_municipios(self, casos_serie: list[Caso], residencia: bool) -> list[dict]:
        recente, anterior = self.ano_fechado, self.ano_fechado - 1
        grupos = defaultdict(lambda: defaultdict(list))
        for c in casos_serie:
            ibge = c.mun_res if residencia else c.mun_trat
            if ibge in self.municipios and c.ano in (recente, anterior):
                grupos[ibge][c.ano].append(c.dias)
        saida = []
        for ibge, anos in grupos.items():
            r, a = resumir(anos[recente], MIN_CASOS_RANKING), resumir(anos[anterior], MIN_CASOS_RANKING)
            if not (r["n"] and a["n"]):
                continue
            variacao = round(r["pct_fora_60"] - a["pct_fora_60"], 1)
            m = self.municipios[ibge]
            saida.append({"ibge": ibge, "nome": m["nome"], "drs": m["drs"], "drs_nome": self.nome_drs(m["drs"]),
                          "pct_fora_recente": r["pct_fora_60"], "pct_fora_anterior": a["pct_fora_60"], "variacao_pp": variacao,
                          "casos_ano_recente": r["n"], "mediana_recente": r["mediana_dias"], "classificacao": classificar_alerta(r["pct_fora_60"], variacao)})
        ordem = {"CRITICO": 0, "ATENCAO": 1, "MONITORAR": 2, "OPORTUNIDADE": 3}
        saida.sort(key=lambda x: (ordem[x["classificacao"]], -x["pct_fora_recente"]))
        return saida

    # ------------------------------------------------------------ apoio a decisao

    def recomendacoes(self, painel: dict) -> list[dict]:
        """Cartoes ATENCAO / RISCO / OPORTUNIDADE / ACAO SUGERIDA a partir de regras explicitas."""
        alertas = [a for a in painel["alertas"] if a["classificacao"] != "DADOS_INSUFICIENTES"]
        por_drs = {d["drs"]: d for d in painel["por_drs"]}
        if not alertas:
            return []
        ano, ant = self.ano_fechado, self.ano_fechado - 1
        cards = []

        pior = max(alertas, key=lambda a: a["pct_fora_recente"])
        cards.append({
            "tipo": "ATENCAO", "drs": pior["drs"], "titulo": f"{pior['nome']}",
            "texto": f"{br(pior['pct_fora_recente'])}% das pacientes iniciaram o tratamento após 60 dias em {ano} ({br(pior['casos_ano_recente'], 0)} casos). É o maior percentual entre as regiões com dados suficientes.",
            "fundamento": "Maior percentual acima de 60 dias no último ano fechado, entre regiões com pelo menos 30 casos no ano.",
            "destino": "gargalos",
        })

        pioras = [a for a in alertas if a["variacao_pp"] > 0]
        if pioras:
            risco = max(pioras, key=lambda a: a["variacao_pp"])
            cards.append({
                "tipo": "RISCO", "drs": risco["drs"], "titulo": risco["nome"],
                "texto": f"Piora de {br_sinal(risco['variacao_pp'])} p.p. no percentual acima de 60 dias ({br(risco['pct_fora_anterior'])}% em {ant} para {br(risco['pct_fora_recente'])}% em {ano}).",
                "fundamento": "Maior variação positiva (piora) entre os dois últimos anos fechados. A demanda absoluta não é usada como sinal de risco porque os anos recentes ainda recebem registros com atraso.",
                "destino": "gargalos",
            })

        candidatas = [a for a in alertas if a["variacao_pp"] <= 0 and (a["casos_ano_recente"] or 0) >= 100]
        if candidatas:
            melhor = min(candidatas, key=lambda a: a["pct_fora_recente"])
            cards.append({
                "tipo": "OPORTUNIDADE", "drs": melhor["drs"], "titulo": melhor["nome"],
                "texto": f"Menor percentual acima de 60 dias com tendência estável ou de melhora: {br(melhor['pct_fora_recente'])}% em {ano} ({br_sinal(melhor['variacao_pp'])} p.p.). Pode servir de referência de processo ou apoiar pactuação regional.",
                "fundamento": "Região com pelo menos 100 casos no ano, variação menor ou igual a zero e menor percentual acima de 60 dias. Não indica existência de vaga.",
                "destino": "demanda-oferta",
            })

        if pior["drs"] in self.centroide_drs:
            lat, lon = self.centroide_drs[pior["drs"]]
            vizinhas = []
            for a in alertas:
                if a["drs"] == pior["drs"] or (a["casos_ano_recente"] or 0) < 100 or a["pct_fora_recente"] > pior["pct_fora_recente"] - 10:
                    continue
                dist = haversine_km(lat, lon, *self.centroide_drs[a["drs"]])
                vizinhas.append((dist, a))
            if vizinhas:
                dist, alvo = min(vizinhas, key=lambda x: x[0])
                pressao_pior = por_drs[pior["drs"]]["pressao_casos_por_estabelecimento"]
                pressao_alvo = por_drs[alvo["drs"]]["pressao_casos_por_estabelecimento"]
                cards.append({
                    "tipo": "ACAO_SUGERIDA", "drs": pior["drs"], "titulo": f"Avaliar fluxo complementar: {pior['nome']} → {alvo['nome']}",
                    "texto": (f"{alvo['nome']} registrou {br(alvo['pct_fora_recente'])}% acima de 60 dias em {ano}, contra {br(pior['pct_fora_recente'])}% em {pior['nome']}. "
                              f"Distância aproximada entre os centros das regiões: {br(dist, 0)} km. Pressão assistencial: {br(pressao_pior)} vs {br(pressao_alvo)} casos por estabelecimento habilitado. "
                              "Testar o impacto no Simulador e confirmar capacidade real com a regulação antes de qualquer encaminhamento."),
                    "fundamento": "Região mais próxima (centroide das sedes municipais) com pelo menos 10 p.p. a menos acima de 60 dias e pelo menos 100 casos no ano.",
                    "destino": "simulacao",
                })
        return cards

    # ------------------------------------------------------------ localizador

    def localizador(self, municipio: str, limite: int = 12) -> dict:
        origem = self.municipios.get(municipio)
        if not origem:
            raise DadosInsuficientes("Município não encontrado entre os 645 municípios de SP.")
        residentes = [c for c in self.casos if c.mun_res == municipio]
        resumo_origem = resumir([c.dias for c in residentes])
        uso = Counter(c.cnes for c in residentes)

        onde_tratam = []
        for cnes, qtd in uso.most_common(6):
            if qtd < MIN_CASOS_EXIBICAO:
                continue
            dist = self.distancia_km(municipio, cnes)
            onde_tratam.append({"cnes": cnes, "nome": self.nome_unidade(cnes), "casos": qtd, "percentual": round(100 * qtd / len(residentes), 1),
                                "distancia_km": round(dist, 1) if dist is not None else None,
                                **{k: v for k, v in resumir([c.dias for c in residentes if c.cnes == cnes]).items() if k in ("pct_fora_60", "mediana_dias")}})

        faixas_km = (10, 25, 50, 100, 200)
        ordem_compat = {"confirmada": 0, "observada": 1, "limitada": 2}
        candidatas, limitadas = [], 0
        for cnes, u in self.unidades.items():
            dist = self.distancia_km(municipio, cnes)
            if dist is None:
                continue
            compat = self.compatibilidade(cnes)
            if compat == "limitada":
                limitadas += 1
                continue
            m = self.municipios[u["municipio_ibge"]]
            todos = self.dias_por_unidade.get(cnes, [])
            recentes = self.dias_recentes_por_unidade.get(cnes, [])
            resumo_u = resumir(todos)
            informacoes = sum([bool(u["nome_confirmado"]), bool(u["habilitacao"]), not resumo_u["suprimido"] and resumo_u["n"] > 0])
            faixa = next((i for i, lim in enumerate(faixas_km) if dist <= lim), len(faixas_km))
            atendidos = uso.get(cnes, 0)
            candidatas.append({
                "cnes": cnes, "nome": self.nome_unidade(cnes), "nome_confirmado": u["nome_confirmado"],
                "municipio": m["nome"], "municipio_ibge": u["municipio_ibge"], "drs": m["drs"], "drs_nome": self.nome_drs(m["drs"]),
                "mesmo_municipio": u["municipio_ibge"] == municipio, "mesma_regiao": m["drs"] == origem["drs"],
                "distancia_km": round(dist, 1), "faixa_distancia": ["até 10 km", "10–25 km", "25–50 km", "50–100 km", "100–200 km", "mais de 200 km"][faixa],
                "compatibilidade": compat, "habilitacao": u["habilitacao"], "gestao": u["gestao"], "fonte_habilitacao": u["fonte_habilitacao"],
                "casos_c50_base": resumo_u["n"], "casos_c50_periodo_recente": len(recentes) if len(recentes) >= MIN_CASOS_EXIBICAO else None,
                "pct_fora_60": resumo_u["pct_fora_60"], "mediana_dias": resumo_u["mediana_dias"],
                "residentes_origem_atendidos": atendidos if atendidos >= MIN_CASOS_EXIBICAO else ("<10" if atendidos else 0),
                "informacoes_disponiveis": informacoes,
                "_ordem": (faixa, ordem_compat[compat], -informacoes, dist),
            })
        candidatas.sort(key=lambda x: x["_ordem"])
        for c in candidatas:
            c.pop("_ordem")

        return {
            "origem": {"ibge": municipio, "nome": origem["nome"], "drs": origem["drs"], "drs_nome": self.nome_drs(origem["drs"]),
                       "lat": origem["lat"], "lon": origem["lon"], **resumo_origem,
                       "pct_tratado_fora_do_municipio": round(100 * sum(1 for c in residentes if c.mun_trat != municipio) / len(residentes), 1) if len(residentes) >= MIN_CASOS_EXIBICAO else None},
            "onde_tratam_hoje": onde_tratam,
            "unidades": candidatas[:limite],
            "total_compativeis": len(candidatas),
            "unidades_com_poucos_casos_omitidas": limitadas,
            "ordenacao": ["faixa de distância estimada (linha reta entre sedes municipais)", "compatibilidade: habilitação confirmada (CIB-SP) antes de unidade observada tratando ≥ 30 casos C50 na base", "quantidade de informações assistenciais disponíveis"],
            "aviso_disponibilidade": "A plataforma não possui acesso à ocupação hospitalar em tempo real. A lista mostra onde existe serviço e não confirma vaga.",
        }
