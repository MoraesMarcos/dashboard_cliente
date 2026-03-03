import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import date

# Configurações de Conexão (Segura com st.secrets)
def conectar_banco():
    return psycopg2.connect(
        host="mp.serveblog.net",
        port="5432",
        database="unico",
        user="leitura",
        password=st.secrets["DB_PASSWORD"] 
    )

@st.cache_data
def carregar_dados_bi():
    conn = conectar_banco()
    # CPF removido da query para garantir a privacidade dos dados
    query = """
    SELECT 
        e.nome AS cliente,
        e.nascimento,
        e.celular AS telefone,
        o.id AS id_operacao,
        o.data AS data_venda,
        i.nomeproduto AS produto,
        i.quantidade,
        i.precounitario, 
        i.precobruto,
        i.precoliquido AS total_pago,
        (i.precobruto - i.precoliquido) AS economia,
        CASE 
            WHEN i.promocao LIKE '%CLUBE MP%' OR i.descontopromocao > 0 THEN 'CLUBE MP'
            ELSE 'NORMAL'
        END AS modalidade
    FROM entidade e
    INNER JOIN operacao o ON o.cliente = e.codigo::varchar
    INNER JOIN item i ON o.id = i.idoperacao
    WHERE e.cliente = 1 
      AND CAST(e.codigo AS INTEGER) >= 2246 
      AND o.cancelado = 0 
      AND i.cancelado = 0;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    # Tratamento de Datas
    df['data_venda'] = pd.to_datetime(df['data_venda'])
    df['nascimento'] = pd.to_datetime(df['nascimento'])
    hoje = pd.to_datetime(date.today())
    
    return df, hoje

# --- Interface ---
st.set_page_config(page_title="Dashboard Melhor Preço", layout="wide")
st.title("🚀 BI - Melhor Preço")

try:
    df_raw, hoje = carregar_dados_bi()

    # --- Sidebar: Filtros ---
    st.sidebar.header("⚙️ Configurações")
    
    # Seleção de Período
    data_min = df_raw['data_venda'].min().date()
    data_max = df_raw['data_venda'].max().date()
    data_range = st.sidebar.date_input("Período de Vendas", [data_min, data_max])
    
    st.sidebar.markdown("---")

    # Filtragem principal dos dados pelo período de datas
    if len(data_range) == 2:
        df = df_raw[(df_raw['data_venda'].dt.date >= data_range[0]) & (df_raw['data_venda'].dt.date <= data_range[1])]
    else:
        df = df_raw

    # --- Ranking ---
    st.subheader("🏆 Ranking de Clientes (Maiores Compradores)")
    
    df_ranking = df.groupby('cliente').agg(
        Total_Gasto=('total_pago', 'sum'),
        Qtd_Itens=('quantidade', 'sum'),
        Economia_no_Clube=('economia', 'sum')
    ).reset_index().sort_values(by='Total_Gasto', ascending=False)
    
    df_ranking.index = range(1, len(df_ranking) + 1)
    st.dataframe(df_ranking.style.format({
        'Total_Gasto': 'R$ {:.2f}', 
        'Economia_no_Clube': 'R$ {:.2f}', 
        'Qtd_Itens': '{:.0f}'
    }), use_container_width=True)

    st.markdown("---")
    
    # --- Quadrante de Fidelidade ---
    st.subheader("🎯 Quadrante de Fidelidade")
    rfm_data = df.groupby('cliente').agg({
        'data_venda': lambda x: (hoje - x.max()).days,
        'id_operacao': 'nunique',
        'total_pago': 'sum'
    }).rename(columns={'data_venda': 'Recência (dias)', 'id_operacao': 'Frequência', 'total_pago': 'Valor Total'}).reset_index()

    fig_rfm = px.scatter(rfm_data, x="Frequência", y="Valor Total", size="Valor Total", color="Recência (dias)",
                         hover_name="cliente", color_continuous_scale="Viridis")
    st.plotly_chart(fig_rfm, use_container_width=True)

    st.markdown("---")

    # --- Status de Participação dos Clientes ---
    st.subheader("👥 Status de Fidelidade dos Clientes")
    
    # Agrupa por cliente para saber se ele tem pelo menos uma compra no "CLUBE MP"
    df_status_clientes = df.groupby(['cliente', 'telefone', 'nascimento']).agg(
        Status_Clube=('modalidade', lambda x: 'Participa' if 'CLUBE MP' in x.values else 'Não Participa')
    ).reset_index()
    
    # Formata a data de nascimento
    df_status_clientes['nascimento'] = df_status_clientes['nascimento'].dt.strftime('%d/%m/%Y')
    
    # Exibe a tabela interativa (agora sem a coluna CPF)
    st.dataframe(df_status_clientes.sort_values(by='cliente'), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro no processamento: {e}")