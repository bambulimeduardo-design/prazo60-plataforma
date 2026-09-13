// Prazo60 - nucleo do frontend: utilitarios, acesso a API, estado de filtros e componentes de UI.
// Nenhum dado e embutido no navegador: tudo vem da API autenticada, sempre agregado.

window.P60 = window.P60 || { views: {} };

(function (P60) {
  // ------------------------------------------------------------------ utilitarios
  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

  const u = {
    esc: (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ESC[c]),
    num(v, casas = 0) {
      if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
      return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
    },
    pct: (v, casas = 1) => (v === null || v === undefined ? '—' : u.num(v, casas) + '%'),
    dias: (v) => (v === null || v === undefined ? '—' : u.num(v, Number.isInteger(Number(v)) ? 0 : 1)),
    km: (v) => (v === null || v === undefined ? '—' : u.num(v, v < 10 ? 1 : 0) + ' km'),
    pp: (v) => (v === null || v === undefined ? '—' : (v > 0 ? '+' : '') + u.num(v, 1) + ' p.p.'),
    casos: (item) => (item && item.suprimido ? '<10' : u.num(item ? item.n : null)),
    mes: (m) => MESES[m - 1],
    semDrs: (nome) => String(nome || '').replace(/^DRS [IVXL]+ - /, ''),
    $: (sel, raiz = document) => raiz.querySelector(sel),
    $$: (sel, raiz = document) => [...raiz.querySelectorAll(sel)],
    html(el, conteudo) { if (el) el.innerHTML = conteudo; },
    debounce(fn, ms = 250) {
      let t;
      return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
    },
    mediana(valores) {
      const v = valores.filter((x) => x !== null && x !== undefined).sort((a, b) => a - b);
      if (!v.length) return null;
      const m = Math.floor(v.length / 2);
      return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
    },
  };
  P60.u = u;

  // ------------------------------------------------------------------ API
  class ErroApi extends Error {
    constructor(mensagem, status, corpo) { super(mensagem); this.status = status; this.corpo = corpo; }
  }

  async function tratar(resposta) {
    if (resposta.status === 401) {
      window.location.replace('/login');
      throw new ErroApi('Sessão expirada.', 401);
    }
    const corpo = await resposta.json().catch(() => ({}));
    if (!resposta.ok) {
      const detalhe = Array.isArray(corpo.detail) ? 'Parâmetros inválidos.' : corpo.detail;
      throw new ErroApi(detalhe || 'Falha ao consultar os dados.', resposta.status, corpo);
    }
    return corpo;
  }

  P60.api = {
    ErroApi,
    async get(caminho, params = {}) {
      const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined));
      const url = '/api/' + caminho + (qs.toString() ? '?' + qs : '');
      return tratar(await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } }));
    },
    async post(caminho, corpo) {
      return tratar(await fetch('/api/' + caminho, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'prazo60' },
        body: JSON.stringify(corpo || {}),
      }));
    },
  };

  // ------------------------------------------------------------------ estado de filtros
  const PADRAO = { ano: '', mes: '', drs: '', municipio: '', cnes: '', tipo: '', situacao: '', dimensao: 'residencia' };
  const CHAVE = 'p60-filtros';
  let filtros = { ...PADRAO };
  try { filtros = { ...PADRAO, ...JSON.parse(sessionStorage.getItem(CHAVE) || '{}') }; } catch (e) { /* armazenamento indisponivel */ }
  const ouvintes = new Set();

  P60.estado = {
    get filtros() { return { ...filtros }; },
    definir(parcial) {
      const novo = { ...filtros, ...parcial };
      if (JSON.stringify(novo) === JSON.stringify(filtros)) return;
      filtros = novo;
      try { sessionStorage.setItem(CHAVE, JSON.stringify(filtros)); } catch (e) { /* ok */ }
      ouvintes.forEach((fn) => fn(P60.estado.filtros));
    },
    limpar() { P60.estado.definir({ ...PADRAO, dimensao: filtros.dimensao }); },
    ouvir(fn) { ouvintes.add(fn); },
    ativos() { return Object.entries(filtros).filter(([k, v]) => v !== '' && k !== 'dimensao'); },
  };

  // ------------------------------------------------------------------ dados compartilhados
  const cachePainel = new Map();
  P60.dados = {
    referencia: null,
    opcoes: null,
    config: null,
    async carregarBase() {
      const [referencia, opcoes, config] = await Promise.all([P60.api.get('referencia'), P60.api.get('opcoes'), P60.api.get('config')]);
      Object.assign(P60.dados, { referencia, opcoes, config });
    },
    painel(parcial = {}) {
      const params = { ...P60.estado.filtros, ...parcial };
      const chave = JSON.stringify(params);
      if (!cachePainel.has(chave)) {
        const promessa = P60.api.get('painel', params).catch((erro) => { cachePainel.delete(chave); throw erro; });
        cachePainel.set(chave, promessa);
        if (cachePainel.size > 40) cachePainel.delete(cachePainel.keys().next().value);
      }
      return cachePainel.get(chave);
    },
    municipio: (ibge) => (P60.dados.opcoes.municipios.find((m) => m.ibge === ibge) || null),
    nomeDrs: (n) => (P60.dados.referencia.drs[n] || {}).nome || 'Fora do Estado de SP',
  };

  // ------------------------------------------------------------------ componentes
  const SELOS = { real: ['selo-real', 'Dado real'], simulacao: ['selo-simulacao', 'Simulação'], estimativa: ['selo-estimativa', 'Estimativa'], projecao: ['selo-projecao', 'Projeção'], demonstracao: ['selo-demonstracao', 'Demonstração'], premissa: ['selo-premissa', 'Premissa'] };

  P60.ui = {
    selo(tipo, texto) {
      const [classe, rotulo] = SELOS[tipo];
      return `<span class="selo ${classe}">${u.esc(texto || rotulo)}</span>`;
    },
    estado(tipo, texto) {
      const padrao = { carregando: 'Carregando…', vazio: 'Nenhum dado para os filtros selecionados.', erro: 'Não foi possível carregar os dados.' };
      return `<div class="estado estado-${tipo}" role="${tipo === 'erro' ? 'alert' : 'status'}">${u.esc(texto || padrao[tipo])}</div>`;
    },
    // inverter: aumento e bom (ex.: % dentro do prazo). neutro: sem juizo de valor (ex.: volume de casos).
    variacao(valor, { sufixo = ' p.p.', inverter = false, neutro = false, casas = 1 } = {}) {
      if (valor === null || valor === undefined) return '';
      const piora = inverter ? valor < 0 : valor > 0;
      const classe = neutro || valor === 0 ? 'neutra' : piora ? 'piora' : 'melhora';
      return `<span class="variacao ${classe}">${valor > 0 ? '+' : ''}${u.num(valor, casas)}${sufixo}</span>`;
    },
    kpi({ rotulo, valor, unidade = '', classe = '', rodape = '', indicador = '', spark = '' }) {
      return `<article class="kpi">
        <div class="kpi-topo"><p class="kpi-rotulo">${u.esc(rotulo)}</p>${indicador ? `<button class="botao-info" data-indicador="${indicador}" aria-label="Como calculamos ${u.esc(rotulo)}">?</button>` : ''}</div>
        <p class="kpi-valor ${classe}">${valor}${unidade ? `<small>${u.esc(unidade)}</small>` : ''}</p>
        ${spark ? `<div class="kpi-spark"><canvas id="${spark}"></canvas></div>` : ''}
        <div class="kpi-rodape">${rodape}</div>
      </article>`;
    },
    abrirModal(titulo, html) {
      u.$('#modal-titulo').textContent = titulo;
      u.$('#modal-corpo').innerHTML = html;
      const modal = u.$('#modal');
      modal.hidden = false;
      P60.ui._foco = document.activeElement;
      u.$('#modal-fechar').focus();
    },
    fecharModal() {
      u.$('#modal').hidden = true;
      if (P60.ui._foco) P60.ui._foco.focus();
    },
    toast(texto) {
      const el = u.$('#toast');
      el.textContent = texto;
      el.hidden = false;
      clearTimeout(P60.ui._toast);
      P60.ui._toast = setTimeout(() => { el.hidden = true; }, 3200);
    },
    mostrarIndicador(chave) {
      const info = P60.indicadores.obter(chave);
      if (!info) return;
      const campos = [['definicao', 'Definição'], ['formula', 'Fórmula'], ['fonte', 'Fonte'], ['periodo', 'Período'], ['premissas', 'Premissas'], ['limitacoes', 'Limitações'], ['interpretacao', 'Como interpretar']];
      const corpo = campos.filter(([k]) => info[k]).map(([k, r]) => `<dt>${r}</dt><dd>${u.esc(info[k])}</dd>`).join('');
      P60.ui.abrirModal(info.nome, `<dl class="definicao">${corpo}</dl>`);
    },
  };

  // ------------------------------------------------------------------ central de indicadores
  const FONTE = 'Painel-Oncologia (INCA/DATASUS), casos C50 femininos, SP, diagnóstico 2022–2026';
  const EXTRAS = {
    media_dias: { nome: 'Tempo médio até o tratamento', definicao: 'Média aritmética dos dias entre diagnóstico e início do primeiro tratamento.', formula: 'Soma dos dias / número de casos', fonte: FONTE, periodo: 'Conforme filtros aplicados', limitacoes: 'Sensível a valores extremos (há esperas acima de 1.000 dias); leia junto com a mediana.', interpretacao: 'Média muito acima da mediana indica cauda longa de esperas excessivas.' },
    municipios: { nome: 'Municípios analisados', definicao: 'Municípios de SP com ao menos um caso de residente no recorte.', formula: 'Contagem distinta do município de residência (IBGE)', fonte: FONTE, periodo: 'Conforme filtros aplicados', interpretacao: 'Cobertura territorial do recorte.' },
    estabelecimentos: { nome: 'Estabelecimentos analisados', definicao: 'Unidades (CNES) que iniciaram tratamento de ao menos um caso do recorte.', formula: 'Contagem distinta do CNES tratante', fonte: FONTE, periodo: 'Conforme filtros aplicados', limitacoes: 'Não equivale a estabelecimentos habilitados; inclui unidades fora de SP que trataram residentes de SP.', interpretacao: 'Dispersão do atendimento entre unidades.' },
    meta_60: { nome: 'Distância até a meta legal', definicao: 'A Lei 12.732/2012 garante o início do tratamento em até 60 dias para toda paciente: a meta é 100% dentro do prazo.', formula: 'Distância = 100% − percentual dentro do prazo (≤ 60 dias)', fonte: FONTE, periodo: 'Conforme filtros aplicados', interpretacao: 'Cada ponto percentual representa pacientes cujo direito legal não foi cumprido. Nenhuma meta intermediária é inventada pela plataforma.' },
    pressao: { nome: 'Pressão assistencial', definicao: 'Casos C50 do ano de referência por estabelecimento habilitado em oncologia (CACON/UNACON) na mesma região.', formula: 'Casos no ano / estabelecimentos CACON-UNACON no ano (por DRS)', fonte: 'Casos: ' + FONTE + '. Oferta: Painel-Oncologia, indicadores territoriais.', periodo: 'Ano filtrado ou último ano fechado', premissas: 'Casos contados pela dimensão selecionada (residência ou local de tratamento).', limitacoes: 'Não mede leitos, agenda, equipes nem ocupação. Não considera outros tipos de câncer atendidos pelas mesmas unidades.', interpretacao: 'Valores altos sugerem concentração de demanda sobre poucos serviços; demanda/oferta não equivale à existência de vaga.' },
    regras_alerta: { nome: 'Classificação de alertas', definicao: 'Cada região (ou município com ≥ 30 casos no ano) é classificada comparando os dois últimos anos fechados.', formula: 'Variação = % acima de 60 dias no último ano fechado − % no ano anterior. CRÍTICO: ≥ 70% e variação > 0. ATENÇÃO: variação > +5 p.p. OPORTUNIDADE: < 55% e variação ≤ 0. MONITORAR: demais.', fonte: FONTE, periodo: 'Último ano fechado vs anterior', limitacoes: 'Anos recentes ainda recebem registros; esperas longas em curso não aparecem (viés de casos fechados).', interpretacao: 'Ordem de prioridade para investigação, não ranking de qualidade das unidades.' },
    situacao: { nome: 'Situação do prazo', definicao: 'Classificação de cada caso pelo tempo até o tratamento.', formula: 'Dentro: 0–45 dias · Próximo do limite: 46–60 · Acima do prazo: > 60', fonte: FONTE, periodo: 'Conforme filtros aplicados', interpretacao: '“Dentro do prazo” no KPI geral inclui os casos próximos do limite (≤ 60 dias).' },
    distancia: { nome: 'Distância estimada', definicao: 'Distância em linha reta entre a sede do município de origem e a sede do município da unidade.', formula: 'Fórmula de Haversine sobre coordenadas das sedes municipais (IBGE)', fonte: 'kelvins/municipios-brasileiros (derivado do IBGE)', limitacoes: 'Não é rota, tempo de viagem nem considera transporte sanitário. Unidades no mesmo município aparecem a 0 km.', interpretacao: 'Use para ordenar alternativas próximas, não para planejar deslocamento.' },
    compatibilidade: { nome: 'Compatibilidade da unidade', definicao: 'Evidência disponível de que a unidade atende câncer de mama.', formula: 'Confirmada: habilitação CACON/UNACON documentada em deliberação CIB-SP. Observada: tratou ≥ 30 casos C50 na base. Unidades com menos casos são omitidas.', fonte: 'CIB-SP e CNES tratante da base Painel-Oncologia', limitacoes: 'Não confirma habilitação atual, modalidades disponíveis nem vaga.' },
  };
  P60.indicadores = {
    obter(chave) {
      const ref = (P60.dados.referencia && P60.dados.referencia.indicadores_info) || {};
      return ref[chave] || EXTRAS[chave] || null;
    },
    todos() {
      const ref = (P60.dados.referencia && P60.dados.referencia.indicadores_info) || {};
      return { ...ref, ...EXTRAS };
    },
  };

  document.addEventListener('click', (e) => {
    const alvo = e.target.closest('[data-indicador]');
    if (alvo) { e.preventDefault(); P60.ui.mostrarIndicador(alvo.dataset.indicador); }
  });
})(window.P60);
