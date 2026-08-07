"""
Pipeline de ETL: Consolidação de Cadastro de Clientes Multirregional
======================================================================
Recebe 4 exportações de sistemas regionais diferentes (formatos,
encodings, nomenclaturas e convenções de data distintos) e produz:

  1. Uma base única, limpa e validada (dados_limpos/clientes_consolidado.csv)
  2. Um log de qualidade de dados detalhando cada rejeição e seu motivo
     (dados_limpos/log_qualidade.csv)
  3. Um resumo impresso no console com as métricas do processamento

Cada etapa é isolada em sua própria função para ficar testável e legível.
"""
import pandas as pd
import numpy as np
import re
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BRUTOS = RAIZ / "dados_brutos"
LIMPOS = RAIZ / "dados_limpos"
LIMPOS.mkdir(exist_ok=True)

REGISTROS_REJEITADOS = []  # acumula {regional, cnpj_original, motivo} para o log de qualidade


def registrar_rejeicao(regional, identificador, motivo):
    REGISTROS_REJEITADOS.append({
        "regional": regional,
        "identificador_original": identificador,
        "motivo_rejeicao": motivo,
    })


# ---------------------------------------------------------------
# 1. EXTRAÇÃO: cada fonte tem sua própria rotina de leitura,
#    porque cada uma tem encoding/separador/formato próprios
# ---------------------------------------------------------------
def ler_sudeste():
    df = pd.read_csv(BRUTOS / "sudeste_clientes.csv", encoding="utf-8", dtype={"CNPJ": str})
    df = df.rename(columns={
        "CNPJ": "cnpj", "Razao_Social": "nome", "Vendedor": "vendedor",
        "Data_Cadastro": "data_cadastro_raw", "Cidade": "cidade", "UF": "uf", "Segmento": "segmento",
    })
    df["regional"] = "Sudeste"
    df["formato_data_origem"] = "DD/MM/AAAA"
    return df


def ler_sul():
    df = pd.read_csv(BRUTOS / "sul_clientes.csv", encoding="latin-1", sep=";", dtype={"cnpj_cliente": str})
    df = df.rename(columns={
        "cnpj_cliente": "cnpj", "nome_cliente": "nome", "representante": "vendedor",
        "dt_cadastro": "data_cadastro_raw", "municipio": "cidade", "estado": "uf",
        "segmento_mercado": "segmento",
    })
    df["regional"] = "Sul"
    df["formato_data_origem"] = "AAAA-MM-DD"
    return df


def ler_nordeste():
    df = pd.read_excel(BRUTOS / "nordeste_clientes.xlsx", dtype={"CNPJ CLIENTE": str})
    df = df.rename(columns={
        "CNPJ CLIENTE": "cnpj", "NOME FANTASIA": "nome", "VENDEDOR RESPONSAVEL": "vendedor",
        "DATA CADASTRO": "data_cadastro_raw", "CIDADE/UF": "cidade_uf", "SEGMENTO": "segmento",
    })
    # cidade/UF vêm combinados nessa origem, separa em duas colunas
    cid_uf = df["cidade_uf"].str.split("/", n=1, expand=True)
    df["cidade"] = cid_uf[0]
    df["uf"] = cid_uf[1]
    df = df.drop(columns=["cidade_uf"])
    df["regional"] = "Nordeste"
    df["formato_data_origem"] = "DD-Mon-AAAA"
    return df


def ler_centro_oeste():
    df = pd.read_csv(BRUTOS / "centro_oeste_clientes.csv", sep="\t", encoding="utf-8", dtype={"Cnpj": str})
    df = df.rename(columns={
        "Cnpj": "cnpj", "Cliente": "nome", "Vendedor": "vendedor",
        "Cadastro": "data_cadastro_raw", "Cidade": "cidade", "Uf": "uf", "Segmento": "segmento",
    })
    df["regional"] = "Centro-Oeste"
    df["formato_data_origem"] = "SERIAL_EXCEL"
    return df


# ---------------------------------------------------------------
# 2. LIMPEZA: normaliza CNPJ e datas para um padrão único,
#    registrando rejeição sempre que o dado não puder ser confiavelmente
#    interpretado (preferível a adivinhar e mascarar um erro)
# ---------------------------------------------------------------
def normalizar_cnpj(valor):
    """Remove pontuação e valida que sobrem exatamente 14 dígitos numéricos."""
    if pd.isna(valor) or str(valor).strip() == "":
        return None
    limpo = re.sub(r"[^0-9A-Za-z]", "", str(valor))
    if not limpo.isdigit():
        return None  # contém letra (erro de digitação), não tenta adivinhar
    if len(limpo) != 14:
        return None  # tamanho incompatível com CNPJ
    return limpo


def normalizar_data(valor, formato_origem):
    """Converte para date() de acordo com o formato conhecido da origem.
    Retorna None (em vez de arriscar) se o valor não bater com o formato esperado."""
    if pd.isna(valor) or str(valor).strip() == "":
        return None
    texto = str(valor).strip()
    try:
        if formato_origem == "DD/MM/AAAA":
            return pd.to_datetime(texto, format="%d/%m/%Y", errors="raise").date()
        if formato_origem == "AAAA-MM-DD":
            return pd.to_datetime(texto, format="%Y-%m-%d", errors="raise").date()
        if formato_origem == "DD-Mon-AAAA":
            meses = {"Jan":1,"Fev":2,"Mar":3,"Abr":4,"Mai":5,"Jun":6,
                     "Jul":7,"Ago":8,"Set":9,"Out":10,"Nov":11,"Dez":12}
            dia, mes_abv, ano = texto.split("-")
            return date(int(ano), meses[mes_abv], int(dia))
        if formato_origem == "SERIAL_EXCEL":
            epoch = date(1899, 12, 30)
            return epoch + timedelta(days=int(float(texto)))
    except (ValueError, KeyError, TypeError):
        return None
    return None


def limpar_regional(df):
    regional = df["regional"].iloc[0]
    linhas_limpas = []

    for _, linha in df.iterrows():
        # linha completamente vazia (export manual costuma deixar rastro assim)
        if linha.drop(labels=["regional", "formato_data_origem"]).isna().all():
            registrar_rejeicao(regional, "(linha em branco)", "Linha totalmente vazia")
            continue

        cnpj_limpo = normalizar_cnpj(linha.get("cnpj"))
        if cnpj_limpo is None:
            registrar_rejeicao(regional, linha.get("cnpj", "(vazio)"), "CNPJ ausente ou em formato inválido")
            continue

        data_limpa = normalizar_data(linha.get("data_cadastro_raw"), linha["formato_data_origem"])
        if data_limpa is None:
            registrar_rejeicao(regional, cnpj_limpo, "Data de cadastro ausente ou ilegível")
            continue

        nome = str(linha.get("nome", "")).strip()
        if not nome or nome.lower() == "nan":
            registrar_rejeicao(regional, cnpj_limpo, "Nome do cliente ausente")
            continue

        linhas_limpas.append({
            "cnpj": cnpj_limpo,
            "nome": nome,
            "vendedor": str(linha.get("vendedor", "")).strip(),
            "data_cadastro": data_limpa,
            "cidade": str(linha.get("cidade", "")).strip(),
            "uf": str(linha.get("uf", "")).strip(),
            "segmento": str(linha.get("segmento", "")).strip(),
            "regional": regional,
        })

    return pd.DataFrame(linhas_limpas)


# ---------------------------------------------------------------
# 3. VALIDAÇÃO CRUZADA: duplicidade DENTRO da mesma regional
#    e duplicidade ENTRE regionais (mesmo CNPJ cadastrado 2x)
# ---------------------------------------------------------------
def remover_duplicados(df_consolidado):
    antes = len(df_consolidado)

    # duplicidade exata (mesma linha inteira repetida)
    dup_exata = df_consolidado.duplicated(keep="first")
    for _, linha in df_consolidado[dup_exata].iterrows():
        registrar_rejeicao(linha["regional"], linha["cnpj"], "Linha duplicada (exata)")
    df_consolidado = df_consolidado[~dup_exata]

    # mesmo CNPJ cadastrado em mais de uma regional -> mantém o cadastro mais recente,
    # rejeita os demais com motivo explícito (não é erro de digitação, é conflito de negócio)
    df_consolidado = df_consolidado.sort_values("data_cadastro", ascending=False)
    dup_cnpj = df_consolidado.duplicated(subset="cnpj", keep="first")
    for _, linha in df_consolidado[dup_cnpj].iterrows():
        registrar_rejeicao(
            linha["regional"], linha["cnpj"],
            "CNPJ duplicado entre regionais, mantido o cadastro mais recente"
        )
    df_consolidado = df_consolidado[~dup_cnpj]

    depois = len(df_consolidado)
    return df_consolidado.sort_values(["regional", "nome"]).reset_index(drop=True), antes - depois


# ---------------------------------------------------------------
# EXECUÇÃO DO PIPELINE
# ---------------------------------------------------------------
def executar():
    fontes = {
        "Sudeste": ler_sudeste(),
        "Sul": ler_sul(),
        "Nordeste": ler_nordeste(),
        "Centro-Oeste": ler_centro_oeste(),
    }

    total_recebido = sum(len(df) for df in fontes.values())

    limpos = [limpar_regional(df) for df in fontes.values()]
    df_consolidado = pd.concat(limpos, ignore_index=True)

    df_final, duplicados_removidos = remover_duplicados(df_consolidado)

    # -------- exporta base limpa --------
    caminho_saida = LIMPOS / "clientes_consolidado.csv"
    df_final.to_csv(caminho_saida, index=False, encoding="utf-8")

    # -------- exporta log de qualidade --------
    df_log = pd.DataFrame(REGISTROS_REJEITADOS)
    caminho_log = LIMPOS / "log_qualidade.csv"
    df_log.to_csv(caminho_log, index=False, encoding="utf-8")

    # -------- resumo no console --------
    total_aprovado = len(df_final)
    total_rejeitado = len(df_log)

    print("=" * 60)
    print("RESUMO DO PROCESSAMENTO")
    print("=" * 60)
    print(f"Linhas recebidas (4 fontes):     {total_recebido}")
    print(f"Linhas aprovadas na base final:  {total_aprovado}")
    print(f"Linhas rejeitadas:                {total_rejeitado}")
    print()
    print("Rejeições por motivo:")
    if not df_log.empty:
        print(df_log["motivo_rejeicao"].value_counts().to_string())
    print()
    print("Base final por regional:")
    print(df_final["regional"].value_counts().to_string())
    print("=" * 60)
    print(f"Base limpa salva em:  {caminho_saida}")
    print(f"Log de qualidade em:  {caminho_log}")

    return df_final, df_log


if __name__ == "__main__":
    executar()
