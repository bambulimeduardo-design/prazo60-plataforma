// Prazo60 - Inicio: evidencia central com dados de todo o estado (ignora filtros globais).

(function (P60) {
  const u = P60.u;

  P60.views.inicio = {
    titulo: 'Início',
    async ativar() {
      const alvo = u.$('#inicio-evidencia');
      const pergunta = alvo.querySelector('.cartao-pergunta').outerHTML;
      try {
        const p = await P60.dados.painel({ ano: '', mes: '', drs: '', municipio: '', cnes: '', tipo: '', situacao: '', dimensao: 'residencia' });
        const k = p.kpis;
        const periodo = `${P60.dados.opcoes.anos[0]}–${P60.dados.opcoes.anos.at(-1)}`;
        alvo.innerHTML = `${pergunta}
          <p class="evidencia-numero">${u.pct(k.pct_fora_60)}</p>
          <p class="evidencia-texto">das pacientes com câncer de mama iniciaram o tratamento <strong>após o prazo legal de 60 dias</strong> (${u.num(k.n)} casos, ${periodo}).</p>
          <div class="evidencia-barra" aria-hidden="true"><span style="width:${k.pct_dentro_60}%"></span><span style="width:${k.pct_fora_60}%"></span></div>
          <div class="evidencia-legenda"><span>Até 60 dias: ${u.pct(k.pct_dentro_60)}</span><span>Acima de 60 dias: ${u.pct(k.pct_fora_60)}</span></div>
          <div class="evidencia-mini">
            <div><b>${u.dias(k.mediana_dias)}</b><span>dias de mediana</span></div>
            <div><b>${u.num(k.municipios)}</b><span>municípios de SP</span></div>
            <div><b>${u.num(k.estabelecimentos)}</b><span>estabelecimentos</span></div>
          </div>`;
      } catch (erro) {
        alvo.innerHTML = pergunta + P60.ui.estado('erro', erro.message);
      }
    },
  };
})(window.P60);
