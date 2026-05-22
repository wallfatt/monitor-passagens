import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime

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

@dt.cache_data(ttl=120)  # Cache de 2 minutos para atualizar rápido
def carregar_dados():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(URL_DRIVE_CSV, headers=headers)
        if response.status_code == 200:
            conteudo_texto = response.content.decode('utf-8', errors='ignore')
            df = pd.read_csv(StringIO(conteudo_texto))
            df = df.dropna(subset=['Origem', 'Destino', 'Data partida', 'Preco clube'])
            
            df['Origem'] = df['Origem'].astype(str).str.strip().str.upper()
            df['Destino'] = df['Destino'].astype(str).str.strip().str.upper()
            df['Preco normal'] = pd.to_numeric(df['Preco normal'], errors='coerce')
            df['Preco clube'] = pd.to_numeric(df['Preco clube'], errors='coerce')
            
            # Formatação de datas e agrupamentos temporais
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

    # --- BARRA LATERAL: CONFIGURAÇÕES E FILTROS ---
    dt.sidebar.header("⚙️ Configurações do Radar")
    
    rotas_disponiveis = sorted(list((df_voos['Origem'] + " -> " + df_voos['Destino']).unique()))
    rota_selecionada = dt.sidebar.selectbox("Rota:", rotas_disponiveis)
    origem_sel, destino_sel = rota_selecionada.split(" -> ")
    
    # LINHA CORRIGIDA AQUI: Caractere intruso removido com sucesso!
    df_filtrado = df_voos[(df_voos['Origem'] == origem_sel) & (df_voos['Destino'] == destino_sel)].copy()
    
    meses_disponiveis = sorted(df_filtrado['Mês/Ano'].dropna().unique(), key=lambda x: datetime.strptime(x, "%m/%Y"))
    mes_selecionado = dt.sidebar.selectbox("Mês de Partida:", meses_disponiveis)
    
    # Alternador de exibição lateral
    modo_visualizacao = dt.sidebar.radio("Visualizar Preços por:", ["Pontos (Clube)", "Valor em Reais (R$)"])
    tipo_voo = dt.sidebar.radio("Filtro de Conexão:", ["Todos", "Apenas Direto"])

    # Cálculos das taxas com a regra dos 90 dias
    taxa_embarque_base = TAXAS_AEROPORTO.get(origem_sel, TAXA_PADRAO)
    data_atual = datetime.now().date()

    def calcular_taxa_total(row):
        if pd.notna(row['Data partida_dt']):
            if (row['Data partida_dt'].date() - data_atual).days < 90:
                return taxa_embarque_base + 49.90
        return taxa_embarque_base

    df_filtrado['Taxa'] = df_filtrado.apply(calcular_taxa_total, axis=1)
    df_filtrado['Custo Real'] = ((df_filtrado['Preco clube'] / 1000) * VALOR_MILHEIRO) + df_filtrado['Taxa']

    if tipo_voo == "Apenas Direto":
        df_filtrado = df_filtrado[df_filtrado['Numero voos'] == 1]

    # Consolida os dados do mês selecionado pegando o menor preço de cada dia
    df_mes = df_filtrado[df_filtrado['Mês/Ano'] == mes_selecionado]
    df_dia = df_mes.sort_values('Preco clube').groupby('Dia_Mes').first().reset_index()

    # --- DIVISÃO DA TELA AO MEIO ---
    col_esquerda, col_direita = dt.columns([1.2, 0.8])

    with col_esquerda:
        dt.subheader(f"📅 Calendário de Preços — {mes_selecionado}")
        
        if df_dia.empty:
            dt.info("Sem dados de voos para o mês selecionado.")
        else:
            coluna_valor = 'Preco clube' if modo_visualizacao == "Pontos (Clube)" else 'Custo Real'
            sufixo = "k" if modo_visualizacao == "Pontos (Clube)" else "R$"
            
            # Encontra o preço mínimo e máximo do mês para criar a escala de cor (Heatmap)
            val_min = df_dia[coluna_valor].min()
            val_max = df_dia[coluna_valor].max()
            val_range = (val_max - val_min) if (val_max - val_min) > 0 else 1
            
            # Criamos uma matriz de semanas vazia pronta para aceitar TEXTOS (object)
            semanas_do_mes = sorted(df_mes['Semana_Ano'].unique())
            df_grid = pd.DataFrame("", index=semanas_do_mes, columns=ordem_dias, dtype=object)
            
            # Dicionário auxiliar para guardar as cores de fundo de cada célula
            cores_celulas = {}
            
            # Preenche a matriz rodando dia por dia do mês recolhido
            for _, row in df_dia.iterrows():
                sem = row['Semana_Ano']
                dia_sem = row['Dia_Semana']
                val = row[coluna_valor]
                dia_num = int(row['Dia_Mes'])
                
                # Formata a exibição do texto
                exibicao_preco = f"{val/1000:.1f}" if modo_visualizacao == "Pontos (Clube)" else f"{val:.0f}"
                texto_celula = f"{dia_num:02d} ({exibicao_preco}{sufixo})"
                df_grid.at[sem, dia_sem] = texto_celula
                
                # Descobre quão barato é o dia (0.0 = Mais Barato, 1.0 = Mais Caro)
                peso_proporcao = (val - val_min) / val_range
                
                # Gera as cores dinamicamente: Verde para o mais barato, passando por Amarelo, até Vermelho
                if peso_proporcao < 0.5:
                    r = int(187 + (68 * (peso_proporcao * 2)))
                    g = int(247)
                    b = int(208 - (100 * (peso_proporcao * 2)))
                else:
                    r = int(255)
                    g = int(247 - (45 * ((peso_proporcao - 0.5) * 2)))
                    b = int(108 + (94 * ((peso_proporcao - 0.5) * 2)))
                    
                cores_celulas[texto_celula] = f"background-color: rgb({r},{g},{b}); color: #1e293b; font-weight: bold; text-align: center;"

            # Modifica os nomes das linhas para exibição na tela
            df_grid.index = [f"Semana {i}" for i in range(1, len(df_grid) + 1)]
            
            # Função de colorização nativa do Pandas que lê o nosso dicionário de pesos
            def aplicar_cores_heatmap(val):
                return cores_celulas.get(val, "background-color: #f8fafc; color: #cbd5e1; text-align: center;")

            # Renderiza o calendário colorido completo
            dt.dataframe(df_grid.style.map(aplicar_cores_heatmap), use_container_width=True)
            
            # Legenda de Cores
            dt.markdown(
                "<div style='display: flex; gap: 15px; font-size: 13px; margin-top: -10px;'>"
                "<span>🟢 Mais Barato do Mês</span>"
                "<span>🟡 Preço Médio</span>"
                "<span>🔴 Mais Caro do Mês</span>"
                "</div>", unsafe_allow_html=True
            )

    with col_direita:
        dt.subheader("📋 Melhores Oportunidades")
        
        if not df_dia.empty:
            # Ordena e lista as 8 melhores datas na coluna da direita
            df_lista_lateral = df_dia.sort_values(by=coluna_valor, ascending=True).head(8)
            
            for idx, row in df_lista_lateral.iterrows():
                with dt.container():
                    c1, c2 = dt.columns([0.35, 0.65])
                    with c1:
                        dt.markdown(f"### 📅 {row['Data partida'][:5]}")
                    with c2:
                        if modo_visualizacao == "Pontos (Clube)":
                            dt.markdown(f"🟢 **{int(row['Preco clube']):,} pts**\n*(Normal: {int(row['Preco normal']):,})*".replace(",", "."))
                        else:
                            dt.markdown(f"💰 **R$ {row['Custo Real']:.2f}**\n*(Taxas: R$ {row['Taxa']:.2f})*".replace(".", ","))
                        dt.caption(f"🕒 {row['Hora partida']} | Voo: {'Direto' if row['Numero voos'] == 1 else 'Conexão'}")
                    dt.markdown("---")
