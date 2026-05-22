import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime

# Configuração da página do Streamlit
dt.set_page_config(page_title="Radar de Voos - Azul Pontos", layout="wide", page_icon="✈️")

# LINK DO SEU GOOGLE DRIVE (Preparado para baixar o CSV gerado pela imagem)
ID_PLANILHA = "1kW2FY4lAxRcp2ZSmBVfeuUWgqGZprLE4"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"

@dt.cache_data(ttl=120)  # Atualiza o cache a cada 2 minutos
def carregar_dados():
    try:
        # Usa o User-Agent para o Google Drive não bloquear o download
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(URL_DRIVE_CSV, headers=headers)
        
        if response.status_code == 200:
            conteudo_texto = response.content.decode('utf-8', errors='ignore')
            dados_csv = StringIO(conteudo_texto)
            df = pd.read_csv(dados_csv)
            
            # Limpeza de segurança (remove linhas em branco geradas no arquivo)
            df = df.dropna(subset=['Origem', 'Destino', 'Data partida'])
            df['Origem'] = df['Origem'].astype(str).str.strip().str.upper()
            df['Destino'] = df['Destino'].astype(str).str.strip().str.upper()
            
            # Converte os preços para numérico de forma segura
            df['Preco normal'] = pd.to_numeric(df['Preco normal'], errors='coerce')
            df['Preco clube'] = pd.to_numeric(df['Preco clube'], errors='coerce')
            
            # Ajusta o formato das datas de partida para ordenação correta
            df['Data partida_dt'] = pd.to_datetime(df['Data partida'], format='%d/%m/%Y', errors='coerce')
            
            return df
        else:
            dt.error(f"Erro do Google Drive: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        dt.error(f"Falha na conexão com o Drive: {e}")
        return pd.DataFrame()

# Título do Dashboard
dt.title("✈️ Dashboard - Monitoramento de Voos Azul Pontos")
dt.markdown("Consulte os melhores preços em milhas coletados pelo robô buscador.")

df_voos = carregar_dados()

if df_voos.empty:
    dt.warning("⚠️ A planilha não pôde ser carregada do Google Drive ou está vazia.")
else:
    # --- BARRA LATERAL: FILTROS ---
    dt.sidebar.header("🔍 Filtros de Busca")
    
    # Filtro de Rota unificado (com tratamento contra erros)
    df_voos['Rota'] = df_voos['Origem'] + " -> " + df_voos['Destino']
    rotas_disponiveis = sorted(list(df_voos['Rota'].dropna().unique()))
    
    if not rotas_disponiveis:
        dt.info("Aguardando o preenchimento de rotas na planilha...")
    else:
        rota_selecionada = dt.sidebar.selectbox("Escolha a Rota:", rotas_disponiveis)
        origem_sel, destino_sel = rota_selecionada.split(" -> ")
        
        # Filtrando datas com base na rota
        df_filtrado_rota = df_voos[(df_voos['Origem'] == origem_sel) & (df_voos['Destino'] == destino_sel)]
        
        # Filtro de Data de Partida
        datas_disponiveis = sorted(df_filtrado_rota['Data partida_dt'].dropna().unique())
        datas_formatadas = [pd.to_datetime(d).strftime('%d/%m/%Y') for d in datas_disponiveis]
        
        data_selecionada_str = dt.sidebar.selectbox("Data de Partida:", datas_formatadas)
        
        # Filtro de Tipo de Voo (Direto ou Conexões)
        conexoes_max = int(df_filtrado_rota['Numero voos'].max()) if not df_filtrado_rota.empty else 1
        opcoes_voo = ["Todos", "Apenas Direto"]
        if conexoes_max > 1:
            opcoes_voo.append("Com Conexão")
        tipo_voo = dt.sidebar.radio("Tipo de Voo:", opcoes_voo)

        # Aplicação final dos filtros no DataFrame
        df_final = df_filtrado_rota[df_filtrado_rota['Data partida'] == data_selecionada_str].copy()
        
        if tipo_voo == "Apenas Direto":
            df_final = df_final[df_final['Numero voos'] == 1]
        elif tipo_voo == "Com Conexão":
            df_final = df_final[df_final['Numero voos'] > 1]
            
        # Ordenar por menor preço do clube
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
                media_clube = df_final['Preco clube'].mean()
                dt.metric(
                    label="📊 Média do Dia (Clube)", 
                    value=f"{int(media_clube):,} pts".replace(",", ".")
                )
            with col3:
                dt.metric(
                    label="🕒 Horário de Partida", 
                    value=f"{melhor_voo['Hora partida']} -> {melhor_voo['Hora chegada']}"
                )
            with col4:
                texto_conexao = "Direto" if melhor_voo['Numero voos'] == 1 else f"{int(melhor_voo['Numero voos'])-1} conexão(ões)"
                dt.metric(label="✈️ Conexões (Melhor Voo)", value=texto_conexao)
                
            dt.markdown("---")
            
            # --- TABELA DE RESULTADOS ---
            dt.subheader(f"📋 Voos Disponíveis para {rota_selecionada} em {data_selecionada_str}")
            
            # Formatando a tabela para exibição visual
            df_exibicao = df_final[[
                "Hora partida", "Hora chegada", "Duracao", "Numero voos", "Preco normal", "Preco clube", "Hora pesquisa"
            ]].copy()
            
            df_exibicao.columns = [
                "Saída", "Chegada", "Duração", "Total de Voos", "Preço Normal (Pts)", "Preço Clube (Pts)", "Última Atualização"
            ]
            
            # Exibe a tabela destacando o preço mais baixo da coluna
            dt.dataframe(
                df_exibicao.style.format({
                    "Preço Normal (Pts)": "{:,.0f}".format,
                    "Preço Clube (Pts)": "{:,.0f}".format
                }).highlight_min(subset=["Preço Clube (Pts)"], color="#bbf7d0"),
                use_container_width=True
            )
            
            # Histórico de Coletas (Gráfico de linha de variação)
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
                dt.info("💡 À medida que o robô rodar mais vezes, um gráfico de evolução de preços aparecerá aqui automaticamente.")
                
        else:
            dt.info("❌ Nenhum voo encontrado com os filtros selecionados.")
