import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import calendar

# Configuração da página do Streamlit
dt.set_page_config(page_title="Radar de Voos - Calendários", layout="wide", page_icon="✈️")

# LINK DO GOOGLE DRIVE
ID_PLANILHA = "1kW2FY4lAxRcp2ZSmBVfeuUWgqGZprLE4"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"

# TAXAS FIXAS POR AEROPORTO
TAXAS_AEROPORTO = {
    "STM": 33.15, "NAT": 35.40, "BEL": 34.20, "VCP": 33.65, "GRU": 34.63, "BSB": 35.10
}
TAXA_PADRAO = 35.00

@dt.cache_data(ttl=120)
def carregar_dados():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(URL_DRIVE_CSV, headers=headers)
        if response.status_code == 200:
            conteudo_texto = response.content.decode('utf-8', errors='ignore')
            df = pd.read_csv(StringIO(conteudo_texto))
            
            df = df.dropna(subset=['Origem', 'Destino', 'Data partida'])
            df['Origem'] = df['Origem'].astype(str).str.strip().str.upper()
            df['Destino'] = df['Destino'].astype(str).str.strip().str.upper()
            
            df['Preco normal'] = pd.to_numeric(df['Preco normal'], errors='coerce')
            df['Preco clube'] = pd.to_numeric(df['Preco clube'], errors='coerce')
            
            df['Data partida_dt'] = pd.to_datetime(df['Data partida'], format='%d/%m/%Y', errors='coerce')
            df['Mês/Ano'] = df['Data partida_dt'].dt.strftime('%m/%Y')
            
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def processar_custos(df_voos_filtrado, origem, valor_milheiro):
    if df_voos_filtrado.empty:
        return df_voos_filtrado
        
    df_temp = df_voos_filtrado.copy()
    taxa_embarque_base = TAXAS_AEROPORTO.get(origem, TAXA_PADRAO)
    data_atual = datetime.now().date()
    
    def calcular_taxa_total(data_voo):
        if pd.notna(data_voo):
            diferenca_dias = (data_voo.date() - data_atual).days
            if diferenca_dias < 90:
                return taxa_embarque_base + 49.90
        return taxa_embarque_base

    df_temp['Taxa'] = df_temp['Data partida_dt'].apply(calcular_taxa_total)
    df_temp['Custo Real Clube'] = ((df_temp['Preco clube'] / 1000) * valor_milheiro) + df_temp['Taxa']
    df_temp['Custo Real Normal'] = ((df_temp['Preco normal'] / 1000) * valor_milheiro) + df_temp['Taxa']
    
    return df_temp

def gerar_html_calendario(df_mes, ano, mes, coluna_valor, titulo, is_pontos):
    meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
                7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    
    html = f"<h3 style='text-align: center; color: #1f2937;'>{titulo} - {meses_pt[mes]} {ano}</h3>"
    html += "<table style='width:100%; border-collapse: separate; border-spacing: 4px; text-align:center; font-family: sans-serif;'>"
    html += "<tr style='background-color:#1e293b; color:white; font-weight:bold;'>"
    for d in ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']:
        html += f"<td style='padding:8px; border-radius: 4px;'>{d}</td>"
    html += "</tr>"

    if df_mes.empty:
        val_min, val_max, val_range = 0, 1, 1
        df_dia = {}
    else:
        df_dia = df_mes.groupby(df_mes['Data partida_dt'].dt.day)[coluna_valor].min().to_dict()
        val_min = min(df_dia.values()) if df_dia else 0
        val_max = max(df_dia.values()) if df_dia else 1
        val_range = val_max - val_min if val_max != val_min else 1

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(ano, mes)

    for week in month_days:
        html += "<tr>"
        for day in week:
            if day == 0:
                html += "<td style='background-color:transparent;'></td>"
            else:
                if day in df_dia:
                    val = df_dia[day]
                    peso = (val - val_min) / val_range
                    
                    if peso < 0.5:
                        r = int(187 + (68 * (peso * 2)))
                        g = 247
                        b = int(208 - (100 * (peso * 2)))
                    else:
                        r = 255
                        g = int(247 - (45 * ((peso - 0.5) * 2)))
                        b = int(108 + (94 * ((peso - 0.5) * 2)))
                    
                    bg_color = f"rgb({r},{g},{b})"
                    
                    if is_pontos:
                        text_val = f"{val/1000:.1f}k"
                    else:
                        text_val = f"R${val:.0f}"
                        
                    html += f"<td style='background-color:{bg_color}; padding:15px 5px; border-radius:6px; box-shadow: 1px 1px 3px rgba(0,0,0,0.1); border: 1px solid #e2e8f0;'>"
                    html += f"<div style='font-size:18px; font-weight:bold; color:#0f172a; margin-bottom: 2px;'>{day}</div>"
                    html += f"<div style='font-size:13px; font-weight:800; color:#1e293b;'>{text_val}</div>"
                    html += "</td>"
                else:
                    html += f"<td style='background-color:#f1f5f9; padding:15px 5px; border-radius:6px; border: 1px dashed #cbd5e1;'>"
                    html += f"<div style='font-size:18px; color:#94a3b8;'>{day}</div>"
                    html += f"<div style='font-size:13px; color:#cbd5e1;'>-</div>"
                    html += "</td>"
        html += "</tr>"
    html += "</table>"
    return html


# --- INÍCIO DA INTERFACE ---
dt.title("✈️ Dashboard - Painel de Passagens")

df_voos = carregar_dados()

if df_voos.empty:
    dt.warning("⚠️ Os dados ainda não foram processados ou a planilha está vazia.")
else:
    # --- MENU LATERAL (FILTROS) ---
    dt.sidebar.header("🔍 Configurações de Busca")
    
    df_voos['Rota_Ida'] = df_voos['Origem'] + " -> " + df_voos['Destino']
    rotas_disponiveis = sorted(list(df_voos['Rota_Ida'].dropna().unique()))
    
    rota_selecionada = dt.sidebar.selectbox("Selecione a Rota (Ida):", rotas_disponiveis)
    origem_ida, destino_ida = rota_selecionada.split(" -> ")
    
    # Deriva a volta automaticamente
    origem_volta, destino_volta = destino_ida, origem_ida
    
    # Filtro de Métricas
    modo_visualizacao = dt.sidebar.selectbox(
        "Mostrar valores em:", 
        ["Pontos", "Reais (Clube)", "Reais (Normal)"]
    )
    
    # Valor do milheiro
    valor_milheiro = dt.sidebar.number_input(
        "Valor do Milheiro da Azul (R$):", 
        value=17.00, 
        step=0.50,
        format="%.2f"
    )
    
    # Mês de Pesquisa
    meses_disponiveis = sorted(df_voos['Mês/Ano'].dropna().unique(), key=lambda x: datetime.strptime(x, "%m/%Y"))
    mes_selecionado = dt.sidebar.selectbox("Selecione o Mês:", meses_disponiveis)
    mes_int, ano_int = map(int, mes_selecionado.split("/"))

    # --- PROCESSAMENTO DOS DADOS ---
    # Processa Ida
    df_ida = df_voos[(df_voos['Origem'] == origem_ida) & (df_voos['Destino'] == destino_ida)]
    df_ida_processado = processar_custos(df_ida, origem_ida, valor_milheiro)
    df_ida_mes = df_ida_processado[df_ida_processado['Mês/Ano'] == mes_selecionado]
    
    # Processa Volta
    df_volta = df_voos[(df_voos['Origem'] == origem_volta) & (df_voos['Destino'] == destino_volta)]
    df_volta_processado = processar_custos(df_volta, origem_volta, valor_milheiro)
    df_volta_mes = df_volta_processado[df_volta_processado['Mês/Ano'] == mes_selecionado]

    # Define qual coluna usar baseada na seleção
    if modo_visualizacao == "Pontos":
        coluna_valor = 'Preco clube'
        is_pontos = True
    elif modo_visualizacao == "Reais (Clube)":
        coluna_valor = 'Custo Real Clube'
        is_pontos = False
    else:
        coluna_valor = 'Custo Real Normal'
        is_pontos = False

    # --- RENDERIZAÇÃO DOS CALENDÁRIOS ---
    col1, col2 = dt.columns(2)
    
    with col1:
        dt.markdown(gerar_html_calendario(
            df_ida_mes, ano_int, mes_int, coluna_valor, 
            f"IDA: {origem_ida} ➔ {destino_ida}", is_pontos
        ), unsafe_allow_html=True)
        
    with col2:
        dt.markdown(gerar_html_calendario(
            df_volta_mes, ano_int, mes_int, coluna_valor, 
            f"VOLTA: {origem_volta} ➔ {destino_volta}", is_pontos
        ), unsafe_allow_html=True)

    dt.markdown(
        "<div style='display: flex; gap: 20px; font-size: 14px; margin-top: 25px; justify-content: center;'>"
        "<span>🟢 Menor Preço do Mês</span>"
        "<span>🟡 Preço Intermediário</span>"
        "<span>🔴 Maior Preço do Mês</span>"
        "</div>", unsafe_allow_html=True
    )
