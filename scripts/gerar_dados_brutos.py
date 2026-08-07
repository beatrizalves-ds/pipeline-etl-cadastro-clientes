"""
Gera 4 arquivos de origem "sujos", simulando exportações de 4 sistemas
regionais diferentes de cadastro de clientes — cada um com seu próprio
formato de coluna, separador, encoding e formato de data, como acontece
de verdade quando cada regional opera com uma ferramenta distinta.
"""
import pandas as pd
import numpy as np
import random
from datetime import date, timedelta

rng = random.Random(42)
np_rng = np.random.default_rng(42)

CIDADES = {
    "Sudeste": [("São Paulo", "SP"), ("Campinas", "SP"), ("Belo Horizonte", "MG"), ("Rio de Janeiro", "RJ"), ("Uberlândia", "MG")],
    "Sul": [("Porto Alegre", "RS"), ("Curitiba", "PR"), ("Florianópolis", "SC"), ("Caxias do Sul", "RS"), ("Londrina", "PR")],
    "Nordeste": [("Recife", "PE"), ("Salvador", "BA"), ("Fortaleza", "CE"), ("Natal", "RN"), ("Maceió", "AL")],
    "Centro-Oeste": [("Goiânia", "GO"), ("Cuiabá", "MT"), ("Campo Grande", "MS"), ("Brasília", "DF"), ("Rondonópolis", "MT")],
}

SEGMENTOS = ["Varejo", "Indústria", "Serviços", "Agronegócio", "Distribuição"]
PREFIXOS = ["Comercial", "Indústria", "Grupo", "Distribuidora", "Atacado", "Rede"]
NOMES = ["Vitória", "Norte", "Aliança", "Central", "União", "Progresso", "Horizonte", "Planalto", "Litoral", "Serra",
         "Bom Sucesso", "Nova Era", "Primavera", "Estrela", "Cordilheira", "Meridional", "Atlântico", "Cerrado"]
SUFIXOS = ["Ltda", "S.A.", "EIRELI", "ME"]

VENDEDORES = ["Carlos Souza", "Ana Ribeiro", "Marcos Lima", "Juliana Alves", "Pedro Santos",
              "Fernanda Costa", "Ricardo Melo", "Camila Rocha", "Bruno Teixeira", "Larissa Pinto"]

def gerar_cnpj(valido=True):
    base = "".join(str(rng.randint(0, 9)) for _ in range(8))
    filial = "0001"
    if valido:
        # gera 2 dígitos verificadores plausíveis (não é o cálculo oficial completo, só formato)
        dv = f"{rng.randint(10,99)}"
    else:
        dv = f"{rng.randint(0,9)}"  # só 1 dígito -> formato inválido de propósito
    return base, filial, dv

def nome_empresa():
    return f"{rng.choice(PREFIXOS)} {rng.choice(NOMES)} {rng.choice(SUFIXOS)}"

def data_aleatoria():
    inicio = date(2023, 1, 1)
    fim = date(2026, 6, 30)
    dias = (fim - inicio).days
    return inicio + timedelta(days=rng.randint(0, dias))

def gerar_linhas(regional, n):
    linhas = []
    cnpjs_usados = []
    for i in range(n):
        base, filial, dv = gerar_cnpj(valido=True)
        cnpj_valido = f"{base}{filial}{dv}"
        cnpjs_usados.append(cnpj_valido)
        cidade, uf = rng.choice(CIDADES[regional])
        linhas.append({
            "cnpj": cnpj_valido,
            "nome": nome_empresa(),
            "vendedor": rng.choice(VENDEDORES),
            "data": data_aleatoria(),
            "cidade": cidade,
            "uf": uf,
            "segmento": rng.choice(SEGMENTOS),
        })
    return linhas, cnpjs_usados

# =================================================================
# SUDESTE — CSV, UTF-8, vírgula, formato "limpo" de referência
# =================================================================
linhas, cnpjs_se = gerar_linhas("Sudeste", 140)

# injeta problemas: CNPJ faltante, CNPJ mal formatado, linha duplicada
linhas[3]["cnpj"] = ""                                   # CNPJ vazio
linhas[7]["cnpj"] = linhas[7]["cnpj"][:9]                 # CNPJ curto demais
linhas.append(dict(linhas[15]))                          # linha duplicada exata

df_se = pd.DataFrame(linhas)
df_se["data"] = pd.to_datetime(df_se["data"]).dt.strftime("%d/%m/%Y")
df_se = df_se.rename(columns={
    "cnpj": "CNPJ", "nome": "Razao_Social", "vendedor": "Vendedor",
    "data": "Data_Cadastro", "cidade": "Cidade", "uf": "UF", "segmento": "Segmento",
})
df_se.to_csv("/home/claude/etl_project/dados_brutos/sudeste_clientes.csv", index=False, encoding="utf-8")

# =================================================================
# SUL — CSV, Latin-1, ponto e vírgula, nomes de coluna em minúsculo,
# data em ISO, alguns dias inválidos (erro de digitação)
# =================================================================
linhas, cnpjs_sul = gerar_linhas("Sul", 110)
linhas[5]["data"] = None  # data faltante

df_sul = pd.DataFrame(linhas)

def formata_data_sul(d, idx):
    if d is None:
        return ""
    if idx == 20:
        return "2024-02-31"  # dia inválido, digitação errada
    return d.strftime("%Y-%m-%d")

df_sul["data"] = [formata_data_sul(d, i) for i, d in enumerate(df_sul["data"])]
df_sul = df_sul.rename(columns={
    "cnpj": "cnpj_cliente", "nome": "nome_cliente", "vendedor": "representante",
    "data": "dt_cadastro", "cidade": "municipio", "uf": "estado", "segmento": "segmento_mercado",
})
df_sul.to_csv(
    "/home/claude/etl_project/dados_brutos/sul_clientes.csv",
    index=False, sep=";", encoding="latin-1",
)

# =================================================================
# NORDESTE — Excel, cabeçalhos em maiúsculo, cidade/UF combinados,
# datas em texto "DD-Mon-AAAA", linha totalmente vazia
# =================================================================
linhas, cnpjs_ne = gerar_linhas("Nordeste", 95)
df_ne = pd.DataFrame(linhas)

meses_abv = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}
df_ne["data"] = df_ne["data"].apply(lambda d: f"{d.day:02d}-{meses_abv[d.month]}-{d.year}")
df_ne["cidade_uf"] = df_ne["cidade"] + "/" + df_ne["uf"]
df_ne["cnpj"] = df_ne["cnpj"].apply(lambda c: f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}")  # com pontuação

df_ne = df_ne[["cnpj", "nome", "vendedor", "data", "cidade_uf", "segmento"]]
df_ne = df_ne.rename(columns={
    "cnpj": "CNPJ CLIENTE", "nome": "NOME FANTASIA", "vendedor": "VENDEDOR RESPONSAVEL",
    "data": "DATA CADASTRO", "cidade_uf": "CIDADE/UF", "segmento": "SEGMENTO",
})
# insere uma linha totalmente vazia no meio do arquivo (comum em export manual)
df_ne = pd.concat([df_ne.iloc[:40], pd.DataFrame([{c: None for c in df_ne.columns}]), df_ne.iloc[40:]], ignore_index=True)

df_ne.to_excel("/home/claude/etl_project/dados_brutos/nordeste_clientes.xlsx", index=False)

# =================================================================
# CENTRO-OESTE — CSV, tabulação, CNPJ com letra por erro de digitação,
# data em formato numérico serial do Excel, cabeçalhos capitalizados distintos
# =================================================================
linhas, cnpjs_co = gerar_linhas("Centro-Oeste", 70)
df_co = pd.DataFrame(linhas)

# um CNPJ com caractere inválido (erro de digitação real, comum em campo texto livre)
cnpj_lista = df_co["cnpj"].tolist()
c = list(cnpj_lista[10])
c[5] = "O"  # letra "O" no lugar de zero
cnpj_lista[10] = "".join(c)
df_co["cnpj"] = cnpj_lista

# data como número de série do Excel (dias desde 1899-12-30)
epoch = date(1899, 12, 30)
df_co["data_serial"] = df_co["data"].apply(lambda d: (d - epoch).days)

df_co = df_co[["cnpj", "nome", "vendedor", "data_serial", "cidade", "uf", "segmento"]]
df_co = df_co.rename(columns={
    "cnpj": "Cnpj", "nome": "Cliente", "vendedor": "Vendedor",
    "data_serial": "Cadastro", "cidade": "Cidade", "uf": "Uf", "segmento": "Segmento",
})
df_co.to_csv(
    "/home/claude/etl_project/dados_brutos/centro_oeste_clientes.csv",
    index=False, sep="\t", encoding="utf-8",
)

# =================================================================
# Duplicidade cruzada proposital: um CNPJ do Sudeste é recadastrado
# também no Sul (cliente que aparece em duas regionais ao mesmo tempo)
# =================================================================
cnpj_cruzado = cnpjs_se[50]
with open("/home/claude/etl_project/dados_brutos/sul_clientes.csv", "a", encoding="latin-1") as f:
    f.write(f"{cnpj_cruzado};Cliente Cadastrado em Duas Regionais Ltda;Ana Ribeiro;2025-03-10;Porto Alegre;RS;Varejo\n")

print("Arquivos de origem gerados:")
print(" - sudeste_clientes.csv   (", len(df_se), "linhas )")
print(" - sul_clientes.csv       (", len(df_sul) + 1, "linhas, +1 duplicidade cruzada )")
print(" - nordeste_clientes.xlsx (", len(df_ne), "linhas, com 1 linha vazia )")
print(" - centro_oeste_clientes.csv (", len(df_co), "linhas )")
