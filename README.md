# Supply Chain Intelligence - MME

Dashboard de inteligência de supply chain para monitoramento de contratos e risco de fornecedores do Ministério de Minas e Energia (MME).

## Sobre o projeto

Este projeto coleta dados públicos de contratos governamentais via API do PNCP, cruza com o cadastro de sancionados (CEIS/CNEP) e gera um painel analítico com alertas de risco, anomalias de preço e concentração de mercado.

## Funcionalidades

- KPIs de contratos: valor total, quantidade, fornecedores ativos e em risco
- Análise de gasto por categoria e evolução mensal
- Detecção de anomalias de preço por Z-Score
- Índice de Concentração HHI por categoria
- Calendário de vencimentos com alertas
- Monitor de fornecedores com sanções ativas
- Exportação de dados em CSV

## Arquitetura de dados

```
data/
  bronze/   <- dados brutos das APIs (CSV)
  silver/   <- dados limpos e tipados (Parquet) [gerado pelo notebook 02]
  gold/     <- views analíticas prontas para consumo (DuckDB) [gerado pelo notebook 02]
```

## Fontes de dados

| Fonte | Conteudo | Endpoint |
|---|---|---|
| PNCP | Contratacoes e contratos do MME | https://pncp.gov.br/api/consulta/v1/ |
| CEIS/CNEP | Empresas sancionadas | Portal da Transparencia |
| BCB | Indices economicos IPCA e IGPM | python-bcb |

## Estrutura do repositorio

```
supply_chain/
  assets/               <- imagens e recursos estaticos
  data/
    bronze/             <- dados brutos (versionados)
    silver/             <- dados processados (ignorado pelo git)
    gold/               <- banco DuckDB final (ignorado pelo git)
  notebooks/
    01_ingest.ipynb     <- coleta de dados das APIs
    02_transform.ipynb  <- transformacao e carga no DuckDB
  app.py                <- dashboard Streamlit
  requirements.txt      <- dependencias Python
```

## Instalacao

```bash
# Clone o repositorio
git clone https://github.com/lucasborgs/supply_chain.git
cd supply_chain

# Crie e ative um ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instale as dependencias
pip install -r requirements.txt
```

## Como executar

1. Execute o notebook de ingestao para buscar os dados da API:
   ```
   notebooks/01_ingest.ipynb
   ```

2. Execute o notebook de transformacao para gerar o banco DuckDB:
   ```
   notebooks/02_transform.ipynb
   ```

3. Inicie o dashboard:
   ```bash
   streamlit run app.py
   ```

## Tecnologias

- Python 3.11+
- Streamlit 1.40
- DuckDB 1.4
- Pandas 2.2
- Plotly 5.24
- python-bcb 0.3.3

## Dados de entrada

O CNPJ do orgao monitorado esta configurado no notebook `01_ingest.ipynb`. Para monitorar outro orgao, altere a variavel `CNPJ_MME`.

## Licenca

Dados publicos do governo federal brasileiro - uso livre conforme Lei de Acesso a Informacao (Lei 12.527/2011).
