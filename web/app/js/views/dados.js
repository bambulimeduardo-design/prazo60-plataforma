// Prazo60 - Dados & Metodologia: fontes, pipeline, qualidade, indicadores, privacidade, limitacoes.

(function (P60) {
  const u = P60.u;

  function diasDesde(dataBr) {
    const [d, m, a] = String(dataBr).split('/').map(Number);
    if (!a) return null;
    return Math.floor((Date.now() - new Date(a, m - 1, d).getTime()) / 86400000);
  }

  function qualidade() {
    const q = P60.dados.referencia.qualidade_dados;
    const cob = P60.dados.referencia.cobertura;
    const proj = P60.dados.referencia.meta.projecao_mapa;
    u.html(u.$('#dados-qualidade-kpis'), [
      P60.ui.kpi({ rotulo: 'Registros analisados', valor: u.num(q.registros_validos), rodape: `de ${u.num(q.total_bruto)} brutos · ${u.pct(q.pct_validos, 2)} válidos` }),
      P60.ui.kpi({ rotulo: 'Completude', valor: u.pct(Math.min(q.completude_idade, q.completude_estadiamento), 0), classe: 'sucesso', rodape: 'idade e estadiamento preenchidos' }),
      P60.ui.kpi({ rotulo: 'Atualidade', valor: u.num(diasDesde(q.diagnostico_mais_recente)), unidade: 'dias', rodape: `desde o diagnóstico mais recente (${u.esc(q.diagnostico_mais_recente)})` }),
      P60.ui.kpi({ rotulo: 'Cobertura territorial', valor: `${cob.municipios_com_coordenada}/${cob.municipios_sp}`, rodape: 'municípios de SP mapeados para DRS e coordenadas' }),
    ].join(''));
    const linhas = [
      ['Período', `Diagnósticos de ${cob.anos[0]} a ${cob.anos.at(-1)} (${cob.anos_parciais.join(', ')} parcial)`],
      ['Diagnóstico / tratamento mais recente', `${q.diagnostico_mais_recente} / ${q.tratamento_mais_recente}`],
      ['Consistência', `${u.num(q.descartados_data_invalida)} registros descartados: ${q.motivo_descarte}`],
      ['Duplicidade', `${u.num(q.possiveis_duplicados)} possíveis duplicados mantidos. ${q.nota_duplicados}`],
      ['Identificação (CNS)', `${u.pct(q.cns_preenchido_pct, 0)} preenchido. ${q.nota_cns}`],
      ['Cobertura de oferta', q.cobertura_drs_oferta],
      ['Unidades tratantes', `${cob.unidades} CNES; ${cob.unidades_nome_confirmado} com nome e ${cob.unidades_habilitacao_confirmada} com habilitação confirmados (CIB-SP). Demais exibidas pelo código CNES.`],
      ['Confiabilidade do ETL', 'Recálculo automático conferido com os 34 indicadores por DRS publicados anteriormente (residência e tratamento): 0 divergências.'],
      ['Precisão do mapa', `${proj.taxa_acerto}% das sedes municipais caem dentro do polígono da própria DRS na malha simplificada (projeção ${proj.metodo}).`],
      ['Proteção estatística', 'Grupos com menos de 10 casos têm percentuais e medianas suprimidos; rankings e alertas exigem 30 casos.'],
    ];
    u.html(u.$('#dados-qualidade-linhas'), linhas.map(([k, v]) => `<div class="qualidade-linha"><span><strong>${u.esc(k)}</strong></span><span>${u.esc(v)}</span></div>`).join(''));
  }

  function indicadores() {
    const campos = [['definicao', 'Definição'], ['formula', 'Fórmula'], ['fonte', 'Fonte'], ['periodo', 'Periodicidade / período'], ['limitacoes', 'Limitações'], ['interpretacao', 'Interpretação']];
    u.html(u.$('#dados-indicadores'), Object.values(P60.indicadores.todos()).map((i) => `<article class="cartao indicador">
      <h3>${u.esc(i.nome)}</h3>
      <dl class="definicao">${campos.filter(([k]) => i[k]).map(([k, r]) => `<dt>${r}</dt><dd>${u.esc(i[k])}</dd>`).join('')}</dl>
    </article>`).join(''));
  }

  function mostrarAba(aba) {
    u.$$('#dados-abas button').forEach((b) => { b.classList.toggle('ativo', b.dataset.aba === aba); b.setAttribute('aria-selected', b.dataset.aba === aba); });
    u.$$('.aba-painel').forEach((p) => { p.hidden = p.dataset.aba !== aba; });
  }

  P60.views.dados = {
    titulo: 'Dados & Metodologia',
    iniciar() {
      qualidade();
      indicadores();
      u.$('#dados-abas').addEventListener('click', (e) => { const b = e.target.closest('[data-aba]'); if (b) mostrarAba(b.dataset.aba); });
    },
    mostrarAba,
  };
})(window.P60);
