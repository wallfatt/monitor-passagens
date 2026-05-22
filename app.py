import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime

# Configuração da página do Streamlit
dt.set_page_config(page_title="Radar de Voos - Azul", layout="wide", page_icon="✈️")

# LINK DO SEU GOOGLE DRIVE (Mapeado e pronto para leitura direta)
ID_PLANILHA = "1kW2FY4lAxRcp2ZSmBVfeuUWgqGZprLE4"
URL_DRIVE_CSV = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/export?format=csv"

# --- TABELA FIXA DE TAXAS DE EMBARQUE POR AEROPORTO ---
TAXAS_AEROPORTO = {
    "STM": 33.15,  # Santarém
    "NAT": 35.40,  # Natal
    "BEL": 34.20,  # Belém
    "VCP": 33.65,  # Campinas
    "GRU": 34.63,  # Guarulhos
    "BSB": 35.10,  # Brasília
}
TAXA_PADRAO = 35.00  # Caso o robô encontre um aeroporto fora da lista anterior

# VALOR DE REFERÊNCIA DO MILHEIRO (Ajuste para o valor que você adota na sua estratégia)
VALOR_MILHEIRO = 17.50 

@dt.cache_data(ttl=300)  # Atualiza o cache do painel a cada 5 minutos
def carregar_dados():
    try:
        response = requests.get(URL_DRIVE_CSV)
        if response.status_code == 200:
            dados_csv = StringIO(response.text)
            df = pd.read_csv(dados_csv, encoding='utf-8')
            
            # Limpeza básica e conversão de pontos para número
            df['Preco normal'] = pd.to_numeric(df['Preco normal'], errors='coerce')
            df['Preco clube'] = pd.to_numeric(df['Preco clube'], errors='coerce')
            
            # Ajusta o formato das datas de partida para ordenação
            df['Data partida_dt'] = pd.to_datetime(df['Data partida'], format='%d/%m/%Y', errors='coerce')
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Erro ao carregar dados do Drive: {e}")
        return pd.DataFrame()

# Título do Dashboard
dt.title("✈️ Dashboard - Monitoramento de Voos Azul")
dt.markdown("Consulte os melhores preços em pontos e o custo real estimado em reais (Pontos + Taxas de Embarque e Emissão).")

df_voos = carregar_dados()

if df_voos.empty:
    dt.warning("⚠️ Não foi possível ler os dados da planilha do Google Drive. Lembre-se de verificar se o arquivo está compartilhado como 'Qualquer pessoa com o link pode ler' no seu painel do Drive.")
else:
    # --- BARRA LATERAL: FILTROS ---
    dt.sidebar.header("🔍 Filtros de Busca")
    
    rotas_disponiveis = (df_voos['Origem'] + " -> " + df_voos['Destino']).unique()
    rota_selecionada = dt.sidebar.selectbox("Escolha a Rota:", sorted(rotas_disponiveis))
    
    origem_sel, destino_sel = rota_selecionada.split(" -> ")
    
    df_filtrado_rota = df_voos[(df_voos['Origem'] == origem_sel) & (df_voos['Destino'] == destino_sel)]
    
    datas_disponiveis = sorted(df_filtrado_rota['Data partida_dt'].dropna().unique())
    datas_formatadas = [pd.to_datetime(d).strftime('%d/%m/%Y') for d in datas_disponiveis]
    
    if not datas_formatadas:
        dt.info("Não há datas disponíveis para esta rota.")
    else:
        data_selecionada_str = dt.sidebar.selectbox("Data de Partida:", datas_formatadas)
        
        conexoes_max = int(df_filtrado_rota['Numero voos'].max()) if not df_filtrado_rota.empty else 1
        opcoes_voo = ["Todos", "Apenas Direto"]
        if conexoes_max > 1:
            opcoes_voo.append("Com Conexão")
        tipo_voo = dt.sidebar.radio("Tipo de Voo:", opcoes_voo)

        # Aplicação final dos filtros
        df_final = df_filtrado_rota[df_filtrado_rota['Data partida'] == data_selecionada_str].copy()
        
        if tipo_voo == "Apenas Direto":
            df_final = df_final[df_final['Numero voos'] == 1]
        elif tipo_voo == "Com Conexão":
            df_final = df_final[df_final['Numero voos'] > 1]
            
        # --- CÁLCULO DINÂMICO DAS TAXAS E REAIS COM REGRA DOS 90 DIAS ---
        taxa_embarque_base = TAXAS_AEROPORTO.get(origem_sel, TAXA_PADRAO)
        data_atual = datetime.now().date()
        
        def calcular_taxa_total(row):
            data_voo = pd.to_datetime(row['Data partida'], format='%d/%m/%Y', errors='coerce').date()
            if pd.notna(data_voo):
                diferenca_dias = (data_voo - data_atual).days
                # REGRA DA AZUL: Se a viagem for em menos de 90 dias, cobra a taxa de emissão de R$ 49,90
                if diferenca_dias < 90:
                    return taxa_embarque_base + 49.90
            return taxa_embarque_base

        # Cria as colunas calculadas com base nas datas e milhas
        df_final['Taxa Calculada'] = df_final.apply(calcular_taxa_total, axis=1)
        df_final['Custo Real Clube'] = ((df_final['Preco clube'] / 1000) * VALOR_MILHEIRO) + df_final['Taxa Calculada']
        df_final['Custo Real Normal'] = ((df_final['Preco normal'] / 1000) * VALOR_MILHEIRO) + df_final['Taxa Calculada']

        # Ordenar pelo menor preço do clube
        df_final = df_final.sort_values(by="Preco clube", ascending=True)

        # --- CARD PRINCIPAL: INDICADORES ---
        if not df_final.empty:
            melhor_voo = df_final.iloc[0]
            
            col1, col2, col3, col4 = dt.columns(4)
            
            with col1:
                dt.metric(
                    label="🏆 Melhor Preço Clube", 
                    value=f"{int(melhor_voo['Preco clube']):,} pts".replace(",", "."),
                    delta=f"Normal: {int(melhor_voo['Preco normal']):,} pts".replace(",", ".")
                )
            with col2:
                dt.metric(
                    label="💰 Custo Total Estimado (Clube)", 
                    value=f"R$ {melhor_voo['Custo Real Clube']:.2f}".replace(".", ",")
                )
            with col3:
                # Mostra o valor total de taxas aplicadas àquela linha
                dt.metric(
                    label="🎫 Taxas Totais Aplicadas", 
                    value=f"R$ {melhor_voo['Taxa Calculada']:.2f}".replace(".", ",")
                )
            with col4:
                dt.metric(
                    label="🕒 Horário (Melhor Voo)", 
                    value=f"{melhor_voo['Hora partida']} ➔ {melhor_voo['Hora chegada']}"
                )
                
            dt.markdown("---")
            
            # --- TABELA DE RESULTADOS ---
            dt.subheader(f"📋 Lista Completa de Voos para {rota_selecionada} em {data_selecionada_str}")
            
            # Mapeamento do formato de colunas do seu banco
            col_chegada = "Hora arrival" if "Hora arrival" in df_final.columns else "Hora chegada"
            
            df_exibicao = df_final[[
                "Hora partida", col_chegada, "Duracao", "Numero voos", 
                "Preco normal", "Preco clube", "Taxa Calculada", "Custo Real Clube", "Hora pesquisa"
            ]].copy()
            
            df_exibicao.columns = [
                "Saída", "Chegada", "Duração", "Conexões", 
                "Preço Normal (Pts)", "Preço Clube (Pts)", "Taxas Totais (R$)", "Total Estimado (R$)", "Última Atualização"
            ]
            
            # Formatação numérica para exibição visual limpa
            formatos = {
                "Preço Normal (Pts)": "{:,.0f}".format,
                "Preço Clube (Pts)": "{:,.0f}".format,
                "Taxas Totais (R$)": "R$ {:,.2f}".format,
                "Total Estimado (R$)": "R$ {:,.2f}".format
            }

            dt.dataframe(
                df_exibicao.style.format(formatos).highlight_min(subset=["Preço Clube (Pts)"], color="#bbf7d0"),
                use_container_width=True
            )
            
            # Histórico de Coletas
            dt.markdown("---")
            dt.subheader("📈 Histórico de Variação de Preço (Evolução das Coletas)")
            
            df_historico = df_filtrado_rota[
                (df_filtrado_rota['Data partida'] == data_selecionada_str) & 
                (df_filtrado_rota['Hora partida'] == melhor_voo['Hora partida'])
            ].sort_values(by="Data pesquisa")
            
            if len(df_historico) > 1:
                df_grafico = df_historico.set_index("Data pesquisa")[["Preco normal", "Preco clube"]]
                dt.line_chart(df_grafico)
            else:
                dt.info("💡 À medida que o robô rodar mais vezes em horários diferentes, o histórico de variação de preços aparecerá aqui.")
                
        else:
            dt.info("❌ Nenhum voo encontrado com os filtros selecionados.")
