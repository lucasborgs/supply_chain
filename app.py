import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
from datetime import datetime

# ============================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================
st.set_page_config(
    page_title="Supply Chain Intelligence - MME",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .block-container {padding-top: 1rem;}
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
    }
    .risk-high {color: #ff4b4b; font-weight: bold;}
    .risk-low {color: #21c354; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

# ============================================
# CONEXÃO COM O BANCO
# ============================================
@st.cache_resource
def get_connection():
    return duckdb.connect("data/gold/supply_chain.duckdb", read_only=True)

try:
    con = get_connection()
except Exception as e:
    st.error(f"Erro ao conectar ao banco de dados: {e}")
    st.info("Execute o notebook transform.ipynb para criar o banco de dados.")
    st.stop()

# ============================================
# FUNÇÕES AUXILIARES
# ============================================
@st.cache_data(ttl=300)
def load_data(query):
    return con.execute(query).df()

def format_currency(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_number(value):
    return f"{value:,}".replace(",", ".")

def format_human_br(num):
    if num is None:
        return "R$ 0,00"
        
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    
    sufixos = ['', ' Mil', ' MM', ' Bi', ' Tri']
    
    # Formata com 1 casa decimal e troca ponto por vírgula
    return 'R$ {:.1f}{}'.format(num, sufixos[magnitude]).replace('.', ',')

# ============================================
# SIDEBAR - FILTROS
# ============================================
st.sidebar.image("assets/govbr.webp", width=200)
st.sidebar.title("Filtros")

# Filtro de Categoria
categorias = load_data("SELECT DISTINCT categoria_spend FROM vw_contratos ORDER BY 1")
filtro_cat = st.sidebar.multiselect(
    "Categoria de Gasto",
    options=categorias['categoria_spend'].tolist(),
    default=[]
)

# Filtro de Tipo de Contrato
tipos = load_data("SELECT DISTINCT tipoContrato FROM vw_contratos WHERE tipoContrato IS NOT NULL ORDER BY 1")
filtro_tipo = st.sidebar.multiselect(
    "Tipo de Contrato",
    options=tipos['tipoContrato'].tolist(),
    default=[]
)

# Filtro de Risco
filtro_risco = st.sidebar.radio(
    "Filtrar por Risco",
    options=["Todos", "Com Sanção", "Sem Sanção"],
    index=0
)

# Filtro de Período
st.sidebar.subheader("Período")
col_ini, col_fim = st.sidebar.columns(2)
data_min = load_data("SELECT MIN(dataAssinatura) as dt FROM vw_contratos")['dt'][0]
data_max = datetime.now().date()

if pd.notna(data_min) and pd.notna(data_max):
    data_inicio = col_ini.date_input("Início", value=pd.to_datetime(data_min))
    data_fim = col_fim.date_input("Fim", value=pd.to_datetime(data_max))
else:
    data_inicio = col_ini.date_input("Início")
    data_fim = col_fim.date_input("Fim")

# Construir cláusula WHERE
conditions = []
if filtro_cat:
    lista = "', '".join(filtro_cat)
    conditions.append(f"categoria_spend IN ('{lista}')")
if filtro_tipo:
    lista = "', '".join(filtro_tipo)
    conditions.append(f"tipoContrato IN ('{lista}')")
if filtro_risco == "Com Sanção":
    conditions.append("tem_sancao = true")
elif filtro_risco == "Sem Sanção":
    conditions.append("tem_sancao = false")
if data_inicio and data_fim:
    conditions.append(f"dataAssinatura >= '{data_inicio}' AND dataAssinatura <= '{data_fim}'")

where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

# ============================================
# HEADER
# ============================================
st.title("⚡ Supply Chain Intelligence - MME")
st.caption("Monitoramento de Contratos e Análise de Risco de Fornecedores - Ministério de Minas e Energia")

# ============================================
# KPIs PRINCIPAIS
# ============================================

df_kpis = load_data("SELECT * FROM vw_kpis")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="💰 Total Contratado",
        value=format_human_br(df_kpis['valor_total_contratos'][0])
    )

with col2:
    st.metric(
        label="📄 Contratos",
        value=format_number(df_kpis['total_contratos'][0])
    )

with col3:
    st.metric(
        label="🏢 Fornecedores",
        value=format_number(df_kpis['total_fornecedores'][0])
    )

with col4:
    fornecedores_risco = df_kpis['fornecedores_com_sancao'][0]
    st.metric(
        label="⚠️ Fornecedores em Risco",
        value=format_number(fornecedores_risco)
    )

st.divider()

# ============================================
# GRÁFICOS - LINHA 1
# ============================================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 Spend por Categoria")

    query_cat = f"""
        SELECT categoria_spend,
               SUM(valorGlobal) as valor_total,
               COUNT(*) as qtd
        FROM vw_contratos_risco
        {where_clause}
        GROUP BY categoria_spend
        ORDER BY valor_total DESC
        LIMIT 10
    """
    df_cat = load_data(query_cat)

    if not df_cat.empty:
        # Ordenar do maior para menor (para gráfico horizontal, menor valor fica no topo)
        df_cat = df_cat.sort_values('valor_total', ascending=True)
        fig_cat = px.bar(
            df_cat,
            x='valor_total',
            y='categoria_spend',
            orientation='h',
            text=df_cat['valor_total'].apply(lambda x: f'R$ {x/1000:.0f}K'),
            color='valor_total',
            color_continuous_scale='Blues'
        )
        fig_cat.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            yaxis_title="",
            xaxis_title="Valor Total (R$)",
            height=400
        )
        fig_cat.update_traces(textposition='outside')
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado para os filtros selecionados.")

with col_right:
    st.subheader("📈 Evolução Mensal")

    query_mes = f"""
        SELECT DATE_TRUNC('month', dataAssinatura) as mes,
               SUM(valorGlobal) as valor_total,
               COUNT(*) as qtd_contratos
        FROM vw_contratos_risco
        {where_clause}
        GROUP BY DATE_TRUNC('month', dataAssinatura)
        ORDER BY mes
    """
    df_mes = load_data(query_mes)

    if not df_mes.empty:
        fig_line = px.area(
            df_mes,
            x='mes',
            y='valor_total',
            markers=True,
            line_shape='spline'
        )
        fig_line.update_layout(
            xaxis_title="Mês",
            yaxis_title="Valor Total (R$)",
            height=400
        )
        fig_line.update_traces(
            fill='tozeroy',
            fillcolor='rgba(0, 123, 255, 0.2)',
            line_color='#007bff'
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado para os filtros selecionados.")

# ============================================
# GRÁFICOS - LINHA 2
# ============================================
col_left2, col_right2 = st.columns(2)

with col_left2:
    st.subheader("🏢 Distribuição por Unidade")

    query_unidade = f"""
        SELECT unidadeOrgao as unidade,
               SUM(valorGlobal) as valor_total,
               COUNT(*) as qtd
        FROM vw_contratos_risco
        {where_clause}
        GROUP BY unidadeOrgao
        ORDER BY valor_total DESC
    """
    df_unidade = load_data(query_unidade)

    if not df_unidade.empty:
        fig_pie = px.pie(
            df_unidade,
            values='valor_total',
            names='unidade',
            hole=0.4
        )
        fig_pie.update_layout(height=350)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado.")

with col_right2:
    st.subheader("📋 Por Tipo de Contrato")

    query_tipo = f"""
        SELECT tipoContrato as tipo,
               SUM(valorGlobal) as valor_total,
               COUNT(*) as qtd
        FROM vw_contratos_risco
        {where_clause}
        GROUP BY tipoContrato
        ORDER BY valor_total DESC
    """
    df_tipo = load_data(query_tipo)

    if not df_tipo.empty:
        fig_tipo = px.bar(
            df_tipo,
            x='tipo',
            y='valor_total',
            text=df_tipo['qtd'].apply(lambda x: f'{x} contratos'),
            color='tipo'
        )
        fig_tipo.update_layout(
            showlegend=False,
            xaxis_title="",
            yaxis_title="Valor Total (R$)",
            height=350
        )
        st.plotly_chart(fig_tipo, use_container_width=True)
    else:
        st.info("Nenhum dado encontrado.")

st.divider()

with st.expander("🔎 Análise de Dispersão de Valores (Boxplot)"):
    st.caption("Identifique variações anormais nos valores de contrato para uma mesma categoria.")

    # Boxplot exige os dados brutos, não agregados. Usamos a view base filtrada.
    query_box = f"""
        SELECT categoria_spend, valorGlobal, razao_social
        FROM vw_contratos_risco
        {where_clause}
        -- Filtramos outliers extremos para o gráfico não ficar ilegível (opcional)
        AND valorGlobal > 0
    """
    df_box = load_data(query_box)

    if not df_box.empty:
        fig_box = px.box(
            df_box,
            x="categoria_spend",
            y="valorGlobal",
            points="all", # Mostra cada contrato como um ponto
            hover_data=["razao_social"],
            color="categoria_spend"
        )
        fig_box.update_layout(
            showlegend=False,
            xaxis_title="",
            yaxis_title="Valor do Contrato (R$)",
            height=500
        )
        st.plotly_chart(fig_box, use_container_width=True)
    else:
        st.info("Sem dados suficientes para análise de dispersão.")

# ============================================
# ANÁLISE DE CONCENTRAÇÃO HHI 
# ============================================
with st.expander("📊 Análise de Concentração de Mercado (Índice HHI)"):
    st.caption("""
    O Índice Herfindahl-Hirschman (HHI) mede a concentração de mercado por categoria de gasto.
    **Interpretação:** HHI < 1500 = Competitivo | 1500-2500 = Moderado | > 2500 = Altamente Concentrado (Monopólio)
    """)

    query_hhi = f"""
        WITH dados_filtrados AS (
            SELECT * FROM vw_contratos_risco
            {where_clause}
        ),
        total_categoria AS (
            SELECT categoria_spend, SUM(valorGlobal) AS total_cat
            FROM dados_filtrados
            GROUP BY categoria_spend
        ),
        share_fornecedor AS (
            SELECT
                c.categoria_spend,
                c.razao_social,
                SUM(c.valorGlobal) AS total_fornecedor,
                (SUM(c.valorGlobal) / tc.total_cat) * 100 AS market_share
            FROM dados_filtrados c
            JOIN total_categoria tc ON c.categoria_spend = tc.categoria_spend
            GROUP BY c.categoria_spend, c.razao_social, tc.total_cat
        )
        SELECT
            categoria_spend,
            ROUND(SUM(market_share * market_share), 2) AS hhi_index,
            COUNT(DISTINCT razao_social) AS qtd_fornecedores,
            CASE
                WHEN SUM(market_share * market_share) > 2500 THEN 'Crítica (Monopólio)'
                WHEN SUM(market_share * market_share) > 1500 THEN 'Moderada'
                ELSE 'Baixa (Competitiva)'
            END AS classificacao_risco
        FROM share_fornecedor
        GROUP BY categoria_spend
        ORDER BY hhi_index DESC
    """
    df_hhi = load_data(query_hhi)

    if not df_hhi.empty:
        # Métricas de concentração
        col_hhi1, col_hhi2, col_hhi3 = st.columns(3)

        categorias_criticas = len(df_hhi[df_hhi['classificacao_risco'] == 'Crítica (Monopólio)'])
        categorias_moderadas = len(df_hhi[df_hhi['classificacao_risco'] == 'Moderada'])
        categorias_competitivas = len(df_hhi[df_hhi['classificacao_risco'] == 'Baixa (Competitiva)'])

        col_hhi1.metric("🔴 Categorias Críticas", categorias_criticas)
        col_hhi2.metric("🟡 Categorias Moderadas", categorias_moderadas)
        col_hhi3.metric("🟢 Categorias Competitivas", categorias_competitivas)

        # Gráfico de barras horizontal com cores por classificação
        color_map = {
            'Crítica (Monopólio)': '#ff4b4b',
            'Moderada': '#ffa500',
            'Baixa (Competitiva)': '#21c354'
        }

        df_hhi_sorted = df_hhi.sort_values('hhi_index', ascending=True)

        fig_hhi = px.bar(
            df_hhi_sorted,
            x='hhi_index',
            y='categoria_spend',
            orientation='h',
            color='classificacao_risco',
            color_discrete_map=color_map,
            text='hhi_index',
            hover_data=['qtd_fornecedores']
        )

        # Adicionar linhas de referência
        # fig_hhi.add_vline(x=1500, line_dash="dash", line_color="blue", annotation_text="Limite Moderado (1500)", annotation_position="bottom")
        fig_hhi.add_vline(x=2500, line_dash="dash", line_color="black", annotation_text="Limite Crítico (2500)", annotation_position="top")

        fig_hhi.update_layout(
            xaxis_title="Índice HHI",
            yaxis_title="",
            legend_title="Classificação",
            height=450,
            showlegend=True
        )
        fig_hhi.update_traces(textposition='outside')

        st.plotly_chart(fig_hhi, use_container_width=True)

        # Tabela detalhada
        st.subheader("Detalhamento por Categoria")
        st.dataframe(
            df_hhi,
            use_container_width=True,
            hide_index=True,
            column_config={
                "categoria_spend": st.column_config.TextColumn("Categoria"),
                "hhi_index": st.column_config.NumberColumn("Índice HHI", format="%.2f"),
                "qtd_fornecedores": st.column_config.NumberColumn("Nº Fornecedores"),
                "classificacao_risco": st.column_config.TextColumn("Classificação"),
            }
        )
    else:
        st.info("Dados de concentração não disponíveis. Execute o notebook de transformação.")

# ============================================
# DETECÇÃO DE ANOMALIAS DE PREÇO 
# ============================================
with st.expander("🔍 Detecção de Anomalias de Preço (Z-Score)"):
    st.caption("""
    Identifica contratos com valores significativamente diferentes da média da categoria usando o método Z-Score.
    **Interpretação:** Z > 2 = Alto Valor (Anômalo) | Z < -1.5 = Suspeita de Subpreço
    """)

    query_anomalias = f"""
        WITH dados_filtrados AS (
            SELECT * FROM vw_contratos_risco
            {where_clause}
        ),
        estatisticas AS (
            SELECT
                categoria_spend,
                AVG(valorGlobal) AS media_cat,
                STDDEV(valorGlobal) AS desvio_cat,
                COUNT(*) AS qtd_cat
            FROM dados_filtrados
            GROUP BY categoria_spend
        )
        SELECT
            c.cnpj,
            c.razao_social,
            c.objetoContrato,
            c.valorGlobal,
            c.categoria_spend,
            c.dataAssinatura,
            ROUND(e.media_cat, 2) AS media_categoria,
            ROUND(e.desvio_cat, 2) AS desvio_categoria,
            CASE
                WHEN e.qtd_cat = 1 THEN NULL
                ELSE ROUND((c.valorGlobal - e.media_cat) / NULLIF(e.desvio_cat, 0), 2)
            END AS z_score,
            CASE
                WHEN e.qtd_cat = 1 THEN 'Categoria com único valor'
                WHEN e.desvio_cat IS NULL OR e.desvio_cat = 0 THEN 'Categoria com único valor'
                WHEN (c.valorGlobal - e.media_cat) > (2 * e.desvio_cat) THEN 'Alto Valor (Anômalo)'
                WHEN (c.valorGlobal - e.media_cat) < (-1.5 * e.desvio_cat) THEN 'Suspeita Subpreço'
                ELSE 'Dentro da Normalidade'
            END AS status_preco
        FROM dados_filtrados c
        JOIN estatisticas e ON c.categoria_spend = e.categoria_spend
        ORDER BY z_score DESC NULLS LAST
    """
    df_anomalias = load_data(query_anomalias)

    if not df_anomalias.empty:
        # Métricas de anomalias
        col_an1, col_an2, col_an3, col_an4 = st.columns(4)

        anomalos_alto = len(df_anomalias[df_anomalias['status_preco'] == 'Alto Valor (Anômalo)'])
        anomalos_baixo = len(df_anomalias[df_anomalias['status_preco'] == 'Suspeita Subpreço'])
        normais = len(df_anomalias[df_anomalias['status_preco'] == 'Dentro da Normalidade'])
        valor_anomalo = df_anomalias[df_anomalias['status_preco'] == 'Alto Valor (Anômalo)']['valorGlobal'].sum()

        col_an1.metric("🔴 Alto Valor", anomalos_alto)
        col_an2.metric("🟡 Subpreço", anomalos_baixo)
        col_an3.metric("🟢 Normais", normais)
        col_an4.metric("💰 Valor Anômalo Total", format_human_br(valor_anomalo))

        # Filtro para mostrar apenas anomalias ou todos
        filtro_anomalia = st.radio(
            "Exibir:",
            options=["Apenas Anomalias", "Todos os Contratos"],
            horizontal=True
        )

        if filtro_anomalia == "Apenas Anomalias":
            df_display = df_anomalias[df_anomalias['status_preco'] != 'Dentro da Normalidade']
        else:
            df_display = df_anomalias

        # Gráfico de dispersão Z-Score por categoria
        if not df_display.empty:
            color_map_anomalia = {
                'Alto Valor (Anômalo)': '#ff4b4b',
                'Suspeita Subpreço': '#ffa500',
                'Dentro da Normalidade': '#21c354',
                'Categoria com único valor': '#808080'
            }

            fig_anomalia = px.scatter(
                df_display,
                x='categoria_spend',
                y='z_score',
                size='valorGlobal',
                color='status_preco',
                color_discrete_map=color_map_anomalia,
                hover_data=['razao_social', 'valorGlobal', 'media_categoria'],
                title="Distribuição de Z-Score por Categoria"
            )

            # Linhas de referência
            fig_anomalia.add_hline(y=2, line_dash="dash", line_color="red", annotation_text="Limite Alto (Z=2)")
            fig_anomalia.add_hline(y=-1.5, line_dash="dash", line_color="orange", annotation_text="Limite Baixo (Z=-1.5)")
            fig_anomalia.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.5)

            fig_anomalia.update_layout(
                xaxis_title="",
                yaxis_title="Z-Score",
                height=450,
                showlegend=True,
                legend_title="Status"
            )
            fig_anomalia.update_xaxes(tickangle=45)

            st.plotly_chart(fig_anomalia, use_container_width=True)

        # Tabela detalhada de anomalias
        st.subheader("Contratos com Valores Anômalos")
        df_anomalos_table = df_anomalias[df_anomalias['status_preco'].isin(['Alto Valor (Anômalo)', 'Suspeita Subpreço'])].copy()

        if not df_anomalos_table.empty:
            st.dataframe(
                df_anomalos_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "cnpj": st.column_config.TextColumn("CNPJ"),
                    "razao_social": st.column_config.TextColumn("Fornecedor"),
                    "objetoContrato": st.column_config.TextColumn("Objeto", width="large"),
                    "valorGlobal": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                    "categoria_spend": st.column_config.TextColumn("Categoria"),
                    "dataAssinatura": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "media_categoria": st.column_config.NumberColumn("Média Cat.", format="R$ %.2f"),
                    "desvio_categoria": st.column_config.NumberColumn("Desvio", format="R$ %.2f"),
                    "z_score": st.column_config.NumberColumn("Z-Score", format="%.2f"),
                    "status_preco": st.column_config.TextColumn("Status"),
                }
            )
        else:
            st.success("Nenhum contrato com valor anômalo identificado!")
    else:
        st.info("Dados de anomalias não disponíveis. Execute o notebook de transformação.")

# ============================================
# RADAR DE VENCIMENTOS
# ============================================
st.subheader("📅 Radar de Vencimentos de Contratos")
st.caption("Acompanhe contratos próximos do vencimento para planejar renovações ou novas licitações com antecedência.")

venc_where = where_clause + " AND dataVigenciaFim IS NOT NULL" if where_clause else "WHERE dataVigenciaFim IS NOT NULL"
query_vencimentos = f"""
    SELECT
        razao_social,
        cnpj,
        categoria_spend,
        objetoContrato,
        tipoContrato,
        dataVigenciaFim,
        valorGlobal,
        DATE_DIFF('day', CURRENT_DATE, dataVigenciaFim) AS dias_para_vencimento,
        CASE
            WHEN DATE_DIFF('day', CURRENT_DATE, dataVigenciaFim) < 0 THEN 'VENCIDO'
            WHEN DATE_DIFF('day', CURRENT_DATE, dataVigenciaFim) <= 30 THEN 'CRÍTICO (0-30 dias)'
            WHEN DATE_DIFF('day', CURRENT_DATE, dataVigenciaFim) <= 90 THEN 'ATENÇÃO (30-90 dias)'
            WHEN DATE_DIFF('day', CURRENT_DATE, dataVigenciaFim) <= 180 THEN 'PLANEJAMENTO (90-180 dias)'
            ELSE 'REGULAR'
        END AS status_prazo
    FROM vw_contratos_risco
    {venc_where}
    ORDER BY dias_para_vencimento ASC
"""
df_vencimentos = load_data(query_vencimentos)

if not df_vencimentos.empty:
    # Métricas de vencimento
    col_v1, col_v2, col_v3, col_v4, col_v5 = st.columns(5)

    vencidos = df_vencimentos[df_vencimentos['status_prazo'] == 'VENCIDO']
    criticos = df_vencimentos[df_vencimentos['status_prazo'] == 'CRÍTICO (0-30 dias)']
    atencao = df_vencimentos[df_vencimentos['status_prazo'] == 'ATENÇÃO (30-90 dias)']
    planejamento = df_vencimentos[df_vencimentos['status_prazo'] == 'PLANEJAMENTO (90-180 dias)']
    regulares = df_vencimentos[df_vencimentos['status_prazo'] == 'REGULAR']

    col_v1.metric("⚫ Vencidos", len(vencidos), format_human_br(vencidos['valorGlobal'].sum()) if len(vencidos) > 0 else "R$ 0")
    col_v2.metric("🔴 Críticos (0-30d)", len(criticos), format_human_br(criticos['valorGlobal'].sum()) if len(criticos) > 0 else "R$ 0")
    col_v3.metric("🟠 Atenção (30-90d)", len(atencao), format_human_br(atencao['valorGlobal'].sum()) if len(atencao) > 0 else "R$ 0")
    col_v4.metric("🟡 Planej. (90-180d)", len(planejamento), format_human_br(planejamento['valorGlobal'].sum()) if len(planejamento) > 0 else "R$ 0")
    col_v5.metric("🟢 Regulares", len(regulares), format_human_br(regulares['valorGlobal'].sum()) if len(regulares) > 0 else "R$ 0")

    # Filtro de status
    filtro_status_venc = st.multiselect(
        "Filtrar por Status:",
        options=['VENCIDO', 'CRÍTICO (0-30 dias)', 'ATENÇÃO (30-90 dias)', 'PLANEJAMENTO (90-180 dias)', 'REGULAR'],
        default=['VENCIDO', 'CRÍTICO (0-30 dias)', 'ATENÇÃO (30-90 dias)']
    )

    df_venc_filtrado = df_vencimentos[df_vencimentos['status_prazo'].isin(filtro_status_venc)] if filtro_status_venc else df_vencimentos

    # Gráfico de timeline
    if not df_venc_filtrado.empty:
        color_map_venc = {
            'VENCIDO': '#000000',
            'CRÍTICO (0-30 dias)': '#ff4b4b',
            'ATENÇÃO (30-90 dias)': '#ffa500',
            'PLANEJAMENTO (90-180 dias)': '#ffd700',
            'REGULAR': '#21c354'
        }

        fig_venc = px.bar(
            df_venc_filtrado.head(30),
            x='dias_para_vencimento',
            y='razao_social',
            orientation='h',
            color='status_prazo',
            color_discrete_map=color_map_venc,
            hover_data=['valorGlobal', 'categoria_spend', 'dataVigenciaFim'],
            title="Contratos por Dias até o Vencimento (Top 30)"
        )

        # Linha de referência no dia 0
        fig_venc.add_vline(x=0, line_dash="solid", line_color="red", line_width=2)
        fig_venc.add_vline(x=30, line_dash="dash", line_color="orange", opacity=0.5)
        fig_venc.add_vline(x=90, line_dash="dash", line_color="gold", opacity=0.5)

        fig_venc.update_layout(
            xaxis_title="Dias para Vencimento",
            yaxis_title="",
            height=500,
            showlegend=True,
            legend_title="Status"
        )

        st.plotly_chart(fig_venc, use_container_width=True)

    # Tabela detalhada
    with st.expander("📋 Ver detalhes dos contratos"):
        st.dataframe(
            df_venc_filtrado,
            use_container_width=True,
            hide_index=True,
            column_config={
                "razao_social": st.column_config.TextColumn("Fornecedor"),
                "cnpj": st.column_config.TextColumn("CNPJ"),
                "categoria_spend": st.column_config.TextColumn("Categoria"),
                "objetoContrato": st.column_config.TextColumn("Objeto", width="large"),
                "tipoContrato": st.column_config.TextColumn("Tipo"),
                "dataVigenciaFim": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                "valorGlobal": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "dias_para_vencimento": st.column_config.NumberColumn("Dias p/ Venc."),
                "status_prazo": st.column_config.TextColumn("Status"),
            }
        )

        # Download
        csv_venc = df_venc_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar Radar de Vencimentos",
            data=csv_venc,
            file_name=f"radar_vencimentos_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
else:
    st.info("Dados de vencimentos não disponíveis. Execute o notebook de transformação.")

st.divider()

# ============================================
# MONITOR DE RISCO
# ============================================
st.subheader("🚨 Monitor de Risco - Contratos com Fornecedores Sancionados")

risco_where = where_clause + " AND tem_sancao = true" if where_clause else "WHERE tem_sancao = true"
query_risco = f"""
    SELECT
        razao_social as "Fornecedor",
        cnpj as "CNPJ",
        valorGlobal as "Valor (R$)",
        categoria_spend as "Categoria",
        tipoContrato as "Tipo",
        dataAssinatura as "Data Assinatura",
        lista_sancoes as "Sanções",
        lista_orgaos as "Órgãos Sancionadores"
    FROM vw_contratos_risco
    {risco_where}
    ORDER BY valorGlobal DESC
"""
df_risco = load_data(query_risco)

if not df_risco.empty:
    # Métricas de risco
    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Contratos em Risco", len(df_risco))
    col_r2.metric("Valor Total em Risco", format_currency(df_risco['Valor (R$)'].sum()))
    col_r3.metric("Fornecedores Únicos", df_risco['CNPJ'].nunique())

    # Tabela
    st.dataframe(
        df_risco,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Data Assinatura": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "CNPJ": st.column_config.TextColumn(width="medium"),
            "Sanções": st.column_config.TextColumn(width="large"),
        }
    )

    # Download
    csv = df_risco.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Exportar para CSV",
        data=csv,
        file_name=f"contratos_risco_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
else:
    st.success("✅ Nenhum contrato com fornecedor sancionado encontrado!")

st.divider()

# ============================================
# TABELA COMPLETA DE CONTRATOS
# ============================================
with st.expander("📋 Ver todos os contratos"):
    query_todos = f"""
        SELECT
            razao_social as "Fornecedor",
            cnpj as "CNPJ",
            valorGlobal as "Valor (R$)",
            categoria_spend as "Categoria",
            tipoContrato as "Tipo",
            unidadeOrgao as "Unidade",
            dataAssinatura as "Data Assinatura",
            dataVigenciaFim as "Vigência Fim",
            tem_sancao as "Em Risco"
        FROM vw_contratos_risco
        {where_clause}
        ORDER BY valorGlobal DESC
    """
    df_todos = load_data(query_todos)

    st.dataframe(
        df_todos,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Data Assinatura": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Vigência Fim": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Em Risco": st.column_config.CheckboxColumn(),
        }
    )

# ============================================
# FOOTER
# ============================================
st.divider()
st.caption("Supply Chain Intelligence | Dados: PNCP + CEIS/CNEP | Atualizado em: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
