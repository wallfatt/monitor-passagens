import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import seaborn as sns

# Configuração da página do Streamlit
dt.set_page_config(page_title="Radar de Voos - Calendário", layout="wide", page_icon="✈️")

# LINK DO SEU GOOGLE DRIVE (Download direto)
ID_PLANILHA = "1kW2FY4lAxRcp2ZSmBVfeuUWgqGZprLE4"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"

TAXAS_AEROPORTO = {
    "STM": 33.15, "NAT": 35.40, "BEL": 34.20, "VCP": 33.65, "GRU": 34.63, "BSB": 35.10
}
TAXA_PADRAO = 35.00
VALOR_MILHEIRO = 17.50 

@dt.cache_data(ttl=120)  # Cache curto de 2 minutos para carregar rápido
def carregar_dados():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(URL_DRIVE_CSV, headers=headers)
        if response.status_code == 200:
            conteudo_texto = response.content.decode('utf-8', errors='ignore')
            df = pd.read_csv(StringIO(conteudo_texto))
            df = df.dropna(subset=['Origem', 'Destino', 'Data partida', 'Preco clube'])
            
            df['Origem'] = df['Origem'].astype(str).str.strip().str.upper()
            df['Destino'] = df['Destino'].astype(str).str.strip().str.upper()
            df['Preco normal'] = pd.to_numeric(df['Preco normal'], errors='coerce')
            df['Preco clube'] = pd.to_numeric(df['Preco clube'], errors='coerce')
            
            # Formatação de datas
            df['Data partida_dt'] = pd.to_datetime(df['Data partida'], format='%d/%m/%Y', errors='coerce')
            df['Mês/Ano'] = df['Data partida_dt'].dt.strftime('%m/%Y')
            df['Dia_Semana'] = df['Data partida_dt'].dt.day_name()
            df['Dia_Mes'] = df['Data partida_dt'].dt.day
            df['Semana_Ano'] = df['Data partida_dt'].dt.isocalendar().week
            
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

df_voos = carregar_dados()

if df_voos.empty:
    dt.warning("⚠️ Planilha vazia ou indisponível no Google Drive.")
else:
    # Mapeamento de dias para o formato brasileiro
    dias_map = {
        'Monday': 'Seg', 'Tuesday': 'Ter', 'Wednesday': 'Qua', 
        'Thursday': 'Qui', 'Friday': 'Sex', 'Saturday': 'Sáb', 'Sunday': 'Dom'
    }
    df_voos['Dia_Semana'] = df_voos['Dia_Semana'].map(dias_map)
    ordem_dias = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

    # --- COLUNA ESQUERDA: CONFIGURAÇÕES E FILTROS ---
    dt.sidebar.header("⚙️ Configurações do Radar")
    
    rotas_disponiveis = sorted(list((df_voos['Origem'] + " -> " + df_voos['Destino']).unique()))
    rota_selecionada = dt.sidebar.selectbox("Rota:", rotas_disponiveis)
    origem_sel, destino_sel = rota_selecionada.split(" -> ")
    
    df_filtrado = df_voos[(df_voos['Origem'] == origem_sel) & (df_voos['Destino'] == destino_sel)].copy()
    
    meses_disponiveis = sorted(df_filtrado['Mês/Ano'].dropna().unique(), key=lambda x: datetime.strptime(x, "%m/%Y"))
    mes_selecionado = dt.sidebar.selectbox("Mês de Partida:", meses_disponiveis)
    
    # O FILTRO PRINCIPAL QUE VOCÊ PEDIU: Escolha da unidade visual
    modo_visualizacao = dt.sidebar.radio("Visualizar Preços por:", ["Pontos (Clube)", "Valor em Reais (R$)"])
    
    tipo_voo = dt.sidebar.radio("Filtro de Conexão:", ["Todos", "Apenas Direto"])

    # Aplicação dos filtros dinâmicos de cálculo
    taxa_embarque_base = TAXAS_AEROPORTO.get(origem_sel, TAXA_PADRAO)
    data_atual = datetime.now().date()

    def calcular_taxa_total(row):
        if pd.notna(row['Data partida_dt']):
            if (row['Data partida_dt'].date() - data_atual).days < 90:
                return taxa_embarque_base + 49.90
        return taxa_embarque_base

    df_filtrado['Taxa'] = df_filtrado.apply(calcular_taxa_total, axis=1)
    df_filtrado['Custo Real'] = ((df_filtrado['Preco clube'] / 1000) * VALOR_MILHEIRO) + df_filtrado['Taxa']

    # Filtro final de conexões
    if tipo_voo == "Apenas Direto":
        df_filtrado = df_filtrado[df_filtrado['Numero voos'] == 1]

    # Agrupa para pegar sempre o menor preço coletado de cada dia
    df_dia = df_filtrado[df_filtrado['Mês/Ano'] == mes_selecionado].groupby('Dia_Mes').first().reset_index()

    # --- DIVISÃO DA TELA AO MEIO ---
    col_esquerda, col_direita = dt.columns([1.1, 0.9])

    with col_esquerda:
        dt.subheader(f"📅 Calendário de Preços — {mes_selecionado}")
        
        if df_dia.empty:
            dt.info("Sem dados de voos para o mês selecionado.")
        else:
            # Define qual valor vai preencher o calendário de cores
            coluna_valor = 'Preco clube' if modo_visualizacao == "Pontos (Clube)" else 'Custo Real'
            sufixo = "k pts" if modo_visualizacao == "Pontos (Clube)" else " R$"
            
            # Montagem da matriz do calendário (Semanas x Dias da Semana)
            df_mes_completo = df_filtrado[df_filtrado['Mês/Ano'] == mes_selecionado]
            df_pivot = df_mes_completo.pivot_table(
                index='Semana_Ano', 
                columns='Dia_Semana', 
                values=coluna_valor, 
                aggfunc='min'
            )
            
            # Reorganiza os dias da semana de Segunda a Domingo
            df_pivot = df_pivot.reindex(columns=ordem_dias)
            
            # Cria a matriz correspondente de texto com os números dos dias (ex: "03\n45k")
            df_pivot_dias = df_mes_completo.pivot_table(
                index='Semana_Ano', columns='Dia_Semana', values='Dia_Mes', aggfunc='first'
            ).reindex(columns=ordem_dias)
            
            labels = df_pivot.copy()
            for sem in df_pivot.index:
                for dia in ordem_dias:
                    val = df_pivot.loc[sem, dia]
                    num_dia = df_pivot_dias.loc[sem, dia]
                    if pd.notna(val) and pd.notna(num_dia):
                        exibicao_preco = f"{val/1000:.1f}" if modo_visualizacao == "Pontos (Clube)" else f"{val:.0f}"
                        labels.loc[sem, dia] = f"{int(num_dia):02d}\n{exibicao_preco}{sufixo}"
                    else:
                        labels.loc[sem, dia] = ""

            # Geração do mapa de calor colorido (Verde = Barato, Vermelho = Caro)
            cm = sns.light_palette("green", as_cmap=True).reversed() if modo_visualizacao == "Pontos (Clube)" else sns.color_palette("rdylgn_r", as_cmap=True)
            
            # Plot do Grid estilizado usando o st.dataframe estilizado simulando o grid
            df_grid_visual = df_pivot.copy()
            df_grid_visual.index = [f"Semana {i}" for i in range(1, len(df_grid_visual) + 1)]
            
            # Substitui os valores brutos pelos textos formatados (Dia + Preço)
            for sem_idx, sem in enumerate(df_pivot.index):
                for dia in ordem_dias:
                    df_grid_visual.iloc[sem_idx, df_grid_visual.columns.get_loc(dia)] = labels.loc[sem, dia]
            
            # Preenche células sem voos com traço
            df_grid_visual = df_grid_visual.fillna("-")
            
            # Exibição do grid
            dt.dataframe(df_grid_visual, use_container_width=True)
            dt.caption("💡 Cores sugeridas: Dias com menor valor numérico são destacados no painel de controle.")

    with col_direita:
        dt.subheader("📋 Melhores Oportunidades Encontradas")
        
        if not df_dia.empty:
            # Ordena a lista lateral para destacar os top voos mais baratos do mês
            df_lista_lateral = df_dia.sort_values(by=coluna_valor, ascending=True).head(8)
            
            for idx, row in df_lista_lateral.iterrows():
                with dt.container():
                    c1, c2 = dt.columns([0.4, 0.6])
                    with c1:
                        dt.markdown(f"### 📅 {row['Data partida'][:5]}")
                    with c2:
                        if modo_visualizacao == "Pontos (Clube)":
                            dt.markdown(f"🟢 **{int(row['Preco clube']):,} pts** *(Normal: {int(row['Preco normal']):,})*".replace(",", "."))
                        else:
                            dt.markdown(f"💰 **R$ {row['Custo Real']:.2f}** *(Taxas: R$ {row['Taxa']:.2f})*".replace(".", ","))
                        dt.caption(f"🕒 {row['Hora partida']} ➔ Conexões: {int(row['Numero voos'])-1}")
                    dt.markdown("---")
