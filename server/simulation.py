"""
Simulador de Encaminhamento (AMBIENTE DE SIMULACAO).

O que e dado real aqui:
  - fluxo atual das residentes do municipio de origem para cada unidade (2 ultimos anos fechados);
  - volume anual e distribuicao de dias de espera de cada unidade no mesmo periodo;
  - distancia estimada (linha reta entre sedes municipais).

O que e premissa (ajustavel na tela e sempre exibido):
  - utilizacao_base: quao perto da capacidade cada unidade ja opera hoje (nao existe na fonte publica);
  - fracao_fila: parte da espera que depende de fila (o restante e o percurso clinico: exames, estadiamento).

Modelo de congestionamento (inspirado em fila M/M/1): o tempo em fila cresce com rho/(1-rho).
Se a carga relativa de uma unidade e L, rho_sim = rho_base * L, e o fator aplicado aos dias
de espera e: (1 - q) + q * g(rho_sim) / g(rho_base), com g(rho) = rho / (1 - rho).
E um modelo didatico para comparar cenarios, nao uma previsao operacional.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from .analytics import LIMITE_LEGAL, MIN_CASOS_EXIBICAO, BaseLocal, DadosInsuficientes, br, br_sinal, mediana_ponderada

CENARIOS = {
    "capacidade_normal": {"nome": "Capacidade normal", "descricao": "Linha de base do modelo: nenhuma mudança de demanda ou de fluxo."},
    "demanda_elevada": {"nome": "Demanda elevada no município", "descricao": "Aumento pontual de casos entre residentes do município de origem, distribuídos como hoje."},
    "unidade_indisponivel": {"nome": "Unidade indisponível", "descricao": "A unidade escolhida deixa de receber residentes do município; o fluxo vai para as alternativas mais próximas."},
    "aumento_demanda": {"nome": "Aumento de demanda na região", "descricao": "Aumento de casos em todas as residentes do DRS de origem, pressionando todas as unidades que as atendem."},
    "redistribuicao_regional": {"nome": "Redistribuição regional", "descricao": "Parte das residentes hoje atendidas na unidade principal passa a ser encaminhada para uma unidade alternativa."},
}

PREMISSAS_PADRAO = {"utilizacao_base": 0.70, "fracao_fila": 0.50}
MIN_CASOS_ALTERNATIVA = 50  # no periodo base; unidades muito pequenas saturariam com qualquer redistribuicao
RHO_MAXIMO = 0.97
RHO_SATURACAO = 0.95

LIMITACOES = [
    "Não há dado público de ocupação, agenda ou capacidade por serviço; a utilização de base é uma premissa informada pelo usuário.",
    "Somente o fluxo das residentes do município (ou do DRS, no cenário regional) é alterado; pacientes de outras origens seguem iguais.",
    "Distância em linha reta entre sedes municipais; não representa rota, tempo de viagem nem transporte sanitário.",
    "A base contém apenas casos com tratamento iniciado; filas em aberto não aparecem.",
    "O resultado serve para comparar cenários e orientar perguntas à regulação, nunca para decidir encaminhamento individual.",
]

DADOS_NECESSARIOS = [
    "Ocupação e agenda reais por unidade e por modalidade (quimioterapia, radioterapia, cirurgia), por exemplo via CROSS-SP.",
    "Capacidade instalada efetiva (salas, aceleradores lineares, cadeiras de quimioterapia, equipe).",
    "Fila atual de casos diagnosticados ainda sem tratamento.",
    "Tempo real de deslocamento e oferta de transporte sanitário.",
    "Regras de regulação e pactuações intermunicipais vigentes.",
]


def _g(rho: float) -> float:
    return rho / (1 - rho)


def _fator(carga_relativa: float, rho_base: float, fracao_fila: float) -> tuple[float, bool]:
    rho = min(rho_base * carga_relativa, RHO_MAXIMO)
    fator = (1 - fracao_fila) + fracao_fila * _g(rho) / _g(rho_base)
    return fator, rho_base * carga_relativa >= RHO_SATURACAO


def _pct_fora(pares: list[tuple[float, float]]) -> float | None:
    total = sum(p for _, p in pares)
    if not total:
        return None
    return round(100 * sum(p for v, p in pares if v > LIMITE_LEGAL) / total, 1)


def _mediana(pares: list[tuple[float, float]]) -> float | None:
    m = mediana_ponderada(pares)
    return round(m, 1) if m is not None else None


def contexto(base: BaseLocal, municipio: str) -> dict:
    """Dados reais para montar as etapas 1 e 2 do simulador."""
    origem = base.municipios.get(municipio)
    if not origem:
        raise DadosInsuficientes("Município não encontrado entre os 645 municípios de SP.")
    anos = base.periodo_base
    residentes = [c for c in base.casos if c.mun_res == municipio and c.ano in anos]
    if len(residentes) < 20:
        raise DadosInsuficientes(f"{origem['nome']} tem menos de 20 casos em {anos[0]}–{anos[1]}. Escolha um município com mais casos para uma simulação estável.")

    fluxo = Counter(c.cnes for c in residentes)
    em_sp = [(cnes, q) for cnes, q in fluxo.most_common() if base.coordenada_unidade(cnes)]
    if not em_sp:
        raise DadosInsuficientes("As residentes deste município são atendidas apenas fora de SP na base.")
    principal = em_sp[0][0]

    alternativas = []
    for cnes in base.unidades:
        if cnes == principal or base.compatibilidade(cnes) == "limitada":
            continue
        dist = base.distancia_km(municipio, cnes)
        recentes = base.dias_recentes_por_unidade.get(cnes, [])
        if dist is None or len(recentes) < MIN_CASOS_ALTERNATIVA:
            continue
        alternativas.append({"cnes": cnes, "nome": base.nome_unidade(cnes), "distancia_km": round(dist, 1), "compatibilidade": base.compatibilidade(cnes),
                             "municipio": base.municipios[base.unidades[cnes]["municipio_ibge"]]["nome"],
                             "volume_anual": round(len(recentes) / len(anos), 1)})
    alternativas.sort(key=lambda a: a["distancia_km"])
    alternativas = alternativas[:6]
    # Destino sugerido: entre as 3 mais proximas, a de maior volume (absorve melhor a carga extra).
    sugerida = max(alternativas[:3], key=lambda a: a["volume_anual"])["cnes"] if alternativas else None
    for a in alternativas:
        a["sugerida"] = a["cnes"] == sugerida

    def descrever(cnes: str, qtd: int) -> dict:
        dist = base.distancia_km(municipio, cnes)
        return {"cnes": cnes, "nome": base.nome_unidade(cnes), "casos_periodo": qtd if qtd >= MIN_CASOS_EXIBICAO else None,
                "percentual": round(100 * qtd / len(residentes), 1), "distancia_km": round(dist, 1) if dist is not None else None}

    return {
        "origem": {"ibge": municipio, "nome": origem["nome"], "drs": origem["drs"], "drs_nome": base.nome_drs(origem["drs"]), "casos_periodo": len(residentes)},
        "periodo_base": list(anos),
        "unidade_principal": descrever(principal, fluxo[principal]),
        "unidades_atuais": [descrever(c, q) for c, q in em_sp[:5]],
        "alternativas": alternativas,
        "destino_sugerido": sugerida,
        "cenarios": [{"id": k, **v} for k, v in CENARIOS.items()],
        "premissas_padrao": PREMISSAS_PADRAO,
    }


def simular(base: BaseLocal, municipio: str, cenario: str, parametros: dict) -> dict:
    if cenario not in CENARIOS:
        raise DadosInsuficientes("Cenário desconhecido.")
    ctx = contexto(base, municipio)
    anos = base.periodo_base
    n_anos = len(anos)
    rho_base = float(parametros.get("utilizacao_base", PREMISSAS_PADRAO["utilizacao_base"]))
    fracao_fila = float(parametros.get("fracao_fila", PREMISSAS_PADRAO["fracao_fila"]))
    origem = base.municipios[municipio]

    recentes = [c for c in base.casos if c.ano in anos]
    fluxo_base = Counter(c.cnes for c in recentes if c.mun_res == municipio)
    volume_base = Counter(c.cnes for c in recentes)
    principal = ctx["unidade_principal"]["cnes"]
    ids_alternativas = [a["cnes"] for a in ctx["alternativas"]]

    fluxo_sim = Counter({k: float(v) for k, v in fluxo_base.items()})
    delta: dict[str, float] = defaultdict(float)
    indisponivel = None
    redistribuidos = 0.0
    parametros_usados: dict = {"utilizacao_base": rho_base, "fracao_fila": fracao_fila}

    if cenario == "demanda_elevada":
        aumento = float(parametros.get("aumento_pct", 20)) / 100
        parametros_usados["aumento_pct"] = aumento * 100
        for cnes, q in fluxo_base.items():
            fluxo_sim[cnes] = q * (1 + aumento)
            delta[cnes] += q * aumento

    elif cenario == "aumento_demanda":
        aumento = float(parametros.get("aumento_pct", 15)) / 100
        parametros_usados["aumento_pct"] = aumento * 100
        for cnes, q in Counter(c.cnes for c in recentes if c.drs_res == origem["drs"]).items():
            delta[cnes] += q * aumento
        for cnes, q in fluxo_base.items():
            fluxo_sim[cnes] = q * (1 + aumento)

    elif cenario == "unidade_indisponivel":
        indisponivel = parametros.get("cnes") or principal
        if indisponivel not in fluxo_base:
            raise DadosInsuficientes("A unidade escolhida não atende residentes deste município no período base.")
        destinos = [a for a in ctx["alternativas"] if a["cnes"] != indisponivel][:3]
        if not destinos:
            raise DadosInsuficientes("Não há alternativas compatíveis com volume suficiente para redistribuir.")
        movidos = fluxo_base[indisponivel]
        # Cada alternativa recebe proporcionalmente ao seu porte e inversamente a distancia.
        pesos = [a["volume_anual"] / max(a["distancia_km"], 5) for a in destinos]
        for a, p in zip(destinos, pesos):
            parte = movidos * p / sum(pesos)
            fluxo_sim[a["cnes"]] += parte
            delta[a["cnes"]] += parte
        fluxo_sim[indisponivel] = 0
        delta[indisponivel] -= movidos
        redistribuidos = movidos
        parametros_usados["cnes"] = indisponivel
        parametros_usados["destinos"] = [a["cnes"] for a in destinos]

    elif cenario == "redistribuicao_regional":
        percentual = float(parametros.get("percentual", 30)) / 100
        destino = parametros.get("destino") or ctx["destino_sugerido"]
        if destino not in ids_alternativas:
            raise DadosInsuficientes("Escolha uma unidade alternativa da lista.")
        movidos = fluxo_base[principal] * percentual
        fluxo_sim[principal] -= movidos
        fluxo_sim[destino] += movidos
        delta[principal] -= movidos
        delta[destino] += movidos
        redistribuidos = movidos
        parametros_usados.update({"percentual": percentual * 100, "destino": destino})

    envolvidas = list(dict.fromkeys([c["cnes"] for c in ctx["unidades_atuais"]] + [k for k, v in delta.items() if v] + ids_alternativas[:2]))

    fatores: dict[str, float] = {}
    linhas_unidades = []
    for cnes in envolvidas:
        vol = volume_base.get(cnes, 0)
        if not vol:
            continue
        carga = (vol + delta.get(cnes, 0)) / vol
        fator, saturada = _fator(carga, rho_base, fracao_fila)
        fatores[cnes] = fator
        mediana_base = _mediana([(d, 1) for d in base.dias_recentes_por_unidade[cnes]])
        dist = base.distancia_km(municipio, cnes)
        linhas_unidades.append({
            "cnes": cnes, "nome": base.nome_unidade(cnes), "distancia_km": round(dist, 1) if dist is not None else None,
            "volume_anual_base": round(vol / n_anos, 1), "volume_anual_simulado": round((vol + delta.get(cnes, 0)) / n_anos, 1),
            "carga_relativa": round(carga, 3), "utilizacao_base": round(rho_base * 100, 1),
            "utilizacao_simulada": None if cnes == indisponivel else round(min(rho_base * carga, RHO_MAXIMO) * 100, 1),
            "saturada": saturada and cnes != indisponivel, "indisponivel": cnes == indisponivel,
            "mediana_base_dias": mediana_base, "mediana_simulada_dias": None if cnes == indisponivel else round(mediana_base * fator, 1),
            "residentes_ano_base": round(fluxo_base.get(cnes, 0) / n_anos, 1), "residentes_ano_simulado": round(fluxo_sim.get(cnes, 0) / n_anos, 1),
        })

    def mistura(fluxo: Counter, usar_fatores: bool) -> list[tuple[float, float]]:
        pares = []
        for cnes, q in fluxo.items():
            dias = base.dias_recentes_por_unidade.get(cnes)
            if not q or not dias:
                continue
            f = fatores.get(cnes, 1.0) if usar_fatores else 1.0
            peso = q / len(dias)
            pares.extend((d * f, peso) for d in dias)
        return pares

    def deslocamento(fluxo: Counter) -> float | None:
        soma = peso = 0.0
        for cnes, q in fluxo.items():
            dist = base.distancia_km(municipio, cnes)
            if dist is not None and q:
                soma += dist * q
                peso += q
        return round(soma / peso, 1) if peso else None

    base_modelo, sim_modelo = mistura(fluxo_base, False), mistura(fluxo_sim, True)
    real = [c.dias for c in recentes if c.mun_res == municipio]
    resultado_origem = {
        "real_observado": {"n": len(real), "mediana_dias": _mediana([(d, 1) for d in real]), "pct_fora_60": _pct_fora([(d, 1) for d in real])},
        "modelo_base": {"mediana_dias": _mediana(base_modelo), "pct_fora_60": _pct_fora(base_modelo)},
        "modelo_simulado": {"mediana_dias": _mediana(sim_modelo), "pct_fora_60": _pct_fora(sim_modelo)},
        "pacientes_redistribuidos_ano": round(redistribuidos / n_anos, 1),
        "deslocamento_medio_base_km": deslocamento(fluxo_base),
        "deslocamento_medio_simulado_km": deslocamento(fluxo_sim),
    }
    mb, ms = resultado_origem["modelo_base"], resultado_origem["modelo_simulado"]
    resultado_origem["variacao_mediana_dias"] = round(ms["mediana_dias"] - mb["mediana_dias"], 1) if None not in (mb["mediana_dias"], ms["mediana_dias"]) else None
    resultado_origem["variacao_pct_fora_pp"] = round(ms["pct_fora_60"] - mb["pct_fora_60"], 1) if None not in (mb["pct_fora_60"], ms["pct_fora_60"]) else None

    total_base, total_sim = sum(fluxo_base.values()), sum(fluxo_sim.values())
    distribuicao = [{"cnes": l["cnes"], "nome": l["nome"],
                     "antes_pct": round(100 * fluxo_base.get(l["cnes"], 0) / total_base, 1),
                     "depois_pct": round(100 * fluxo_sim.get(l["cnes"], 0) / total_sim, 1) if total_sim else 0}
                    for l in linhas_unidades]
    outros_antes = round(100 - sum(d["antes_pct"] for d in distribuicao), 1)
    outros_depois = round(100 - sum(d["depois_pct"] for d in distribuicao), 1)
    if outros_antes > 0.5 or outros_depois > 0.5:
        distribuicao.append({"cnes": None, "nome": "Demais unidades", "antes_pct": max(outros_antes, 0), "depois_pct": max(outros_depois, 0)})

    return {
        "tipo_resultado": "SIMULACAO",
        "origem": ctx["origem"],
        "periodo_base": list(anos),
        "cenario": {"id": cenario, **CENARIOS[cenario], "parametros": parametros_usados},
        "premissas": [
            {"nome": "Utilização de base das unidades", "valor": f"{rho_base * 100:.0f}%", "tipo": "PREMISSA", "explicacao": "Não existe na fonte pública. Valores altos tornam o sistema mais sensível a qualquer aumento de carga."},
            {"nome": "Parte da espera sensível à fila", "valor": f"{fracao_fila * 100:.0f}%", "tipo": "PREMISSA", "explicacao": "O restante representa o percurso clínico (exames, estadiamento, consultas), que não muda com a carga."},
            {"nome": "Período de referência", "valor": f"{anos[0]}–{anos[1]}", "tipo": "DADO REAL", "explicacao": "Volumes e distribuições de dias de espera observados na base Painel-Oncologia."},
        ],
        "unidades": linhas_unidades,
        "resultado_origem": resultado_origem,
        "distribuicao": distribuicao,
        "leitura": _leitura(ctx, cenario, resultado_origem, linhas_unidades),
        "limitacoes": LIMITACOES,
        "dados_necessarios": DADOS_NECESSARIOS,
    }


def _leitura(ctx: dict, cenario: str, r: dict, unidades: list[dict]) -> list[str]:
    nome = ctx["origem"]["nome"]
    frases = []
    mb, ms = r["modelo_base"], r["modelo_simulado"]
    if cenario == "capacidade_normal":
        frases.append(f"Linha de base: no modelo, as residentes de {nome} teriam mediana de {br(mb['mediana_dias'])} dias e {br(mb['pct_fora_60'])}% acima de 60 dias. Os valores reais observados aparecem ao lado para comparação.")
    else:
        variacao = r["variacao_mediana_dias"] or 0
        sentido = "diminuiria" if variacao < 0 else "aumentaria" if variacao > 0 else "ficaria estável"
        frases.append(f"No cenário simulado, a mediana estimada de espera das residentes de {nome} {sentido}: de {br(mb['mediana_dias'])} para {br(ms['mediana_dias'])} dias ({br_sinal(variacao)}).")
        frases.append(f"Percentual estimado acima de 60 dias: {br(mb['pct_fora_60'])}% → {br(ms['pct_fora_60'])}% ({br_sinal(r['variacao_pct_fora_pp'])} p.p.).")
    if r["pacientes_redistribuidos_ano"]:
        frases.append(f"Cerca de {br(r['pacientes_redistribuidos_ano'])} pacientes por ano mudariam de unidade. Deslocamento médio estimado: {br(r['deslocamento_medio_base_km'])} km → {br(r['deslocamento_medio_simulado_km'])} km.")
    for u in unidades:
        if u["saturada"]:
            frases.append(f"Atenção: {u['nome']} passaria de {br(u['utilizacao_base'], 0)}% para {br(u['utilizacao_simulada'], 0)}% de utilização estimada. O gargalo pode apenas mudar de lugar.")
    return frases
