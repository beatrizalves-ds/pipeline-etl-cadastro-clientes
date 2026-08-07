# Pipeline de ETL: Cadastro de Clientes Multirregional

![Testes](https://github.com/beatrizalves-ds/pipeline-etl-cadastro-clientes/actions/workflows/tests.yml/badge.svg)

Pipeline em Python que consolida cadastros de clientes vindos de 4 sistemas
regionais diferentes, cada um exportando em formato, encoding e
nomenclatura próprios, em uma base única, limpa e auditável.

> Dados fictícios, gerados para fins de portfólio. Não representam nenhuma
> empresa real.

## O problema

Cada regional exporta seu cadastro de clientes com seu próprio "sotaque" de
dados:

| Regional | Formato | Encoding | Separador | Formato de data |
|---|---|---|---|---|
| Sudeste | CSV | UTF-8 | vírgula | `DD/MM/AAAA` |
| Sul | CSV | Latin-1 | ponto e vírgula | `AAAA-MM-DD` |
| Nordeste | Excel | N/A | N/A | texto `DD-Mon-AAAA` |
| Centro-Oeste | CSV | UTF-8 | tabulação | número de série do Excel |

Consolidar isso manualmente é lento e sujeito a erro silencioso. Este
pipeline automatiza extração, limpeza, validação e deduplicação.

## Estrutura

    dados_brutos/       4 exportações regionais originais (sujas, de propósito)
    scripts/
      gerar_dados_brutos.py   gera os 4 arquivos de origem sintéticos
      pipeline_etl.py         pipeline completo: extração, limpeza, validação, consolidação
    dados_limpos/
      clientes_consolidado.csv   base final, limpa e deduplicada
      log_qualidade.csv          toda rejeição, com motivo e identificador original
    case_study/
      Pipeline_ETL_Case_Study.pdf   resumo executivo do projeto
    tests/
      test_pipeline.py        testes automatizados de ponta a ponta

## Como rodar

    pip install pandas openpyxl
    python scripts/gerar_dados_brutos.py   # gera os 4 arquivos de origem
    python scripts/pipeline_etl.py         # roda o pipeline completo

## Como validar que funciona

O pipeline é determinístico (usa uma semente fixa na geração dos dados), então
rodar os dois comandos acima em qualquer computador produz exatamente os
mesmos números documentados abaixo. Além disso, o repositório tem uma suíte
de testes automatizados que roda o pipeline do zero e confere cada resultado:

    pip install pytest
    python -m pytest tests/ -v

O selo no topo deste README mostra o resultado da última execução automática
desses testes, disparada a cada alteração no código.

## Resultado

- **418** linhas recebidas das 4 fontes
- **410** aprovadas na base final (**98,1%**)
- **8** rejeitadas, cada uma com motivo registrado no log de qualidade

| Motivo da rejeição | Ocorrências |
|---|---|
| CNPJ ausente ou em formato inválido | 3 |
| Data de cadastro ausente ou ilegível | 2 |
| Linha totalmente vazia | 1 |
| Linha duplicada (exata) | 1 |
| CNPJ duplicado entre regionais | 1 |

## Decisões técnicas

- **CNPJ sempre lido como texto.** O pandas infere tipo numérico em colunas
  só com dígitos e descarta zeros à esquerda silenciosamente. Forçar
  `dtype=str` na leitura evitou corromper cerca de 34% da base, o primeiro
  bug real encontrado ao rodar o pipeline pela primeira vez.
- **Data interpretada pelo formato conhecido de cada origem**, nunca
  adivinhada por inferência genérica.
- **Toda rejeição é registrada com motivo**, nunca descartada em silêncio.
  O log é a peça central de auditoria do pipeline.

## Ferramentas

Python, pandas, regex, pytest, GitHub Actions.
