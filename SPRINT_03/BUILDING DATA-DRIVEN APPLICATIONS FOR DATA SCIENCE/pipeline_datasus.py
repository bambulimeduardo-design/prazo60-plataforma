import os
import pandas as pd


def executar_etl(caminho_entrada, caminho_saida):
    # 1. Leitura: Carrega o arquivo bruto CSV no Pandas[cite: 1, 2]
    print("1. Lendo base de dados bruta...")

    # sep=';' define o separador de colunas usado pelo DATASUS[cite: 1, 2]
    # low_memory=False evita avisos de tipos de dados em arquivos grandes[cite: 2]
    df = pd.read_csv(caminho_entrada, sep=';', low_memory=False)

    print("2. Fazendo tratamentos necessários...")

    # Regra dos 60 Dias (Lei nº 12.732/2012):
    # Converte TEMPO_TRAT para numérico limpo e atribui 'Sim' (<= 60 dias) ou 'Não' (> 60 dias)[cite: 2].
    tempo_limpo = pd.to_numeric(
        df['TEMPO_TRAT'].astype(str).str.replace('+', ''), errors='coerce'
    )
    df['DS_CUMPRE_LEI_60_DIAS'] = (tempo_limpo <= 60).map(
        {True: 'Sim', False: 'Não'}
    )

    # 2. Flag de Deslocamento: Compara o município onde o paciente mora (MUN_RESID)
    # com o município onde faz o tratamento (MUN_TRATAM)[cite: 2].
    # Se forem diferentes (!=), gera 'Sim', indicando que o paciente precisou viajar[cite: 2].
    df['DS_DESLOCAMENTO_MUNICIPAL'] = (
        df['MUN_RESID'] != df['MUN_TRATAM']
    ).map({True: 'Sim', False: 'Não'})

    # 3. Decodificação de Tratamento: Traduz os códigos numéricos originais (1, 2, 3...)
    # em nomes claros para o dashboard[cite: 2].
    mapa_tratamento = {
        1: 'Cirurgia',
        2: 'Quimioterapia',
        3: 'Radioterapia',
        4: 'Outros',
    }
    df['DS_TRATAMENTO'] = (
        df['TRATAMENTO'].map(mapa_tratamento).fillna('Não Informado')
    )

    # 4. Decodificação de Estadiamento: Traduz o estágio do câncer (0 a 5) em texto descritivo[cite: 2].
    mapa_estadiamento = {
        0: 'Estágio 0',
        1: 'Estágio I',
        2: 'Estágio II',
        3: 'Estágio III',
        4: 'Estágio IV',
        5: 'Não se Aplica',
    }
    df['DS_ESTADIAMENTO'] = (
        df['ESTADIAM'].map(mapa_estadiamento).fillna('Não Classificado')
    )

    # 5. Categorização por Faixa Etária: Usa a lista 'bins' e os nomes 'labels'
    # para transformar a coluna IDADE em grupos etários[cite: 2].
    bins = [0, 39, 49, 69, 120]
    labels = ['< 40 anos', '40 a 49 anos', '50 a 69 anos', '70+ anos']
    df['FAIXA_ETARIA'] = pd.cut(df['IDADE'], bins=bins, labels=labels)

    # 6. Exportação: Salva o dataframe transformado em um novo arquivo CSV[cite: 2].
    # index=False impede a criação de uma coluna extra de números de linha[cite: 2].
    # encoding='utf-8-sig' garante que o Power BI acentue as palavras corretamente[cite: 2].
    # df.to_csv(caminho_saida, sep=';', index=False, encoding='utf-8-sig')
    print("3. Exportando dataset tratado em Excel...")
    df.to_excel(caminho_saida, index=False, sheet_name="Base")


if __name__ == '__main__':
    # Define os caminhos dinamicamente a partir da pasta onde o script está salvo
    # para evitar o erro FileNotFoundError em outros computadores[cite: 2].
    PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))

    ARQUIVO_ENTRADA = os.path.join(
        PASTA_ATUAL, 'POBR_2022_2026_SP_mama_feminino.csv'
    )
    ARQUIVO_SAIDA = os.path.join(PASTA_ATUAL, 'POBR_SP_Mama_Tratado_TESTES.xlsx')

    executar_etl(ARQUIVO_ENTRADA, ARQUIVO_SAIDA)