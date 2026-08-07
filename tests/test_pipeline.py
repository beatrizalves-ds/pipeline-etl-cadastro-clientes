"""
Testes automatizados do pipeline de ETL.

Rodar tudo do zero (gera os dados brutos, roda o pipeline, valida o
resultado) e confirma que os números batem exatamente com o que está
documentado no README. Se esses testes passam, o pipeline funciona
de ponta a ponta, não é só um script que "parece" funcionar.
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module", autouse=True)
def rodar_pipeline_do_zero():
    """Gera os dados brutos e roda o pipeline completo antes de qualquer teste,
    exatamente como uma pessoa faria ao clonar o repositório pela primeira vez."""
    subprocess.run(
        [sys.executable, "scripts/gerar_dados_brutos.py"],
        cwd=RAIZ, check=True, capture_output=True, text=True,
    )
    subprocess.run(
        [sys.executable, "scripts/pipeline_etl.py"],
        cwd=RAIZ, check=True, capture_output=True, text=True,
    )
    yield


def test_base_limpa_foi_gerada():
    caminho = RAIZ / "dados_limpos" / "clientes_consolidado.csv"
    assert caminho.exists(), "A base limpa não foi gerada pelo pipeline"


def test_log_qualidade_foi_gerado():
    caminho = RAIZ / "dados_limpos" / "log_qualidade.csv"
    assert caminho.exists(), "O log de qualidade não foi gerado pelo pipeline"


def test_quantidade_de_linhas_aprovadas():
    df = pd.read_csv(RAIZ / "dados_limpos" / "clientes_consolidado.csv")
    assert len(df) == 410, f"Esperado 410 linhas aprovadas, veio {len(df)}"


def test_quantidade_de_rejeicoes():
    df_log = pd.read_csv(RAIZ / "dados_limpos" / "log_qualidade.csv")
    assert len(df_log) == 8, f"Esperado 8 rejeições, veio {len(df_log)}"


def test_motivos_de_rejeicao_batem_com_o_documentado():
    df_log = pd.read_csv(RAIZ / "dados_limpos" / "log_qualidade.csv")
    contagem = df_log["motivo_rejeicao"].value_counts().to_dict()
    esperado = {
        "CNPJ ausente ou em formato inválido": 3,
        "Data de cadastro ausente ou ilegível": 2,
        "Linha totalmente vazia": 1,
        "Linha duplicada (exata)": 1,
        "CNPJ duplicado entre regionais, mantido o cadastro mais recente": 1,
    }
    assert contagem == esperado, f"Motivos de rejeição não batem: {contagem}"


def test_todo_cnpj_na_base_final_tem_14_digitos():
    """Guarda contra o bug de zero à esquerda: se o pandas voltar a inferir
    a coluna de CNPJ como número, este teste quebra imediatamente."""
    df = pd.read_csv(RAIZ / "dados_limpos" / "clientes_consolidado.csv", dtype={"cnpj": str})
    tamanhos = df["cnpj"].str.len().unique()
    assert list(tamanhos) == [14], f"Existem CNPJs com tamanho diferente de 14: {tamanhos}"


def test_nenhum_cnpj_duplicado_na_base_final():
    df = pd.read_csv(RAIZ / "dados_limpos" / "clientes_consolidado.csv", dtype={"cnpj": str})
    assert df["cnpj"].is_unique, "Existe CNPJ duplicado na base final, a deduplicação falhou"


def test_todas_as_4_regionais_estao_presentes():
    df = pd.read_csv(RAIZ / "dados_limpos" / "clientes_consolidado.csv")
    regionais_esperadas = {"Sudeste", "Sul", "Nordeste", "Centro-Oeste"}
    assert set(df["regional"].unique()) == regionais_esperadas
