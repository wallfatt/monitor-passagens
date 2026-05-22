import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import calendar
import re

# Configuração da página do Streamlit
dt.set_page_config(page_title="Radar de Voos - Filtros Avançados", layout="wide", page_icon="✈️")

# LINK DO GOOGLE DRIVE
ID_PLANILHA = "1kW2FY4lAxRcp2ZSmBVfeuUWgqGZprLE4"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"

# TAXAS FIXAS POR AEROPORTO ATUALIZADAS
TAXAS_AEROPORTO = {
    "STM": 36.67, 
    "NAT": 48.26, 
    "BEL": 54.45, 
    "VCP": 31.94, 
    "GRU": 33.64, 
    "BSB": 32.87
}
TAXA_PADRAO = 50.00

def converter_duracao_para_minutos(dur_str):
    if pd.isna(dur_str) or not isinstance(dur_str, str):
        return 0
    dur_str = dur_str.lower()
    horas = 0
    minutos = 0
    match_h = re.search(r'(\d+)\s*h', dur_str)
    match_m = re.search(r'(\d+)\s*m', dur_str)
    if match_h:
        horas = int(match_h.group(1))
    if match_m:
        minutos = int(match_m.group(1))
    if not match_h and not match_m:
        match_puro = re.search(r'(\d+)', dur_str)
        if match_puro:
            minutos = int(match_puro.group(1))
    return (horas * 60) + minutos

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
            df['Numero voos'] = pd.to_numeric(df['Numero voos'], errors='coerce').fillna(1).astype(int)
            
            df['Duracao_Minutos'] = df['Duracao'].apply(converter_duracao_para_minutos)
            
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

def gerar_html_calendario(df_mes, ano, mes, coluna_valor, titulo, taxa_base, is_pontos, val_min, val_max):
    meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
                7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    
    html = f"<div style='text-align: center; color: #1f2937; font-size: 18px; font-weight: bold;'>{titulo}</div>"
    html += f"<div style='text-align: center; color: #4b5563; font-size: 13px; margin-bottom: 5px;'>Taxa de Embarque local: R$ {taxa_base:.2f}</div>"
    html += f"<div style='text-align: center; color: #1e293b; font-size: 16px; margin-bottom: 10px; font-weight: 600;'>{meses_pt[mes]} {ano}</div>"
    
    html += "<table style='width:100%; border-collapse: separate; border-spacing: 4px; text-align:center; font-family: sans-serif;'>"
    html += "<tr style='background-color:#1e293b; color:white; font-weight:bold;'>"
    for d in ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']:
        html += f"<td style='padding:8px; border-radius: 4px;'>{d}</td>"
    html += "</tr>"

    df_dia = {}
    if not df_mes.empty:
        df_dia = df_mes.groupby(df_mes['Data partida_dt'].dt.day)[coluna_valor].min().to_dict()

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
    origem_volta, destino_volta = destino_ida, origem_ida
    
    modo_visualizacao = dt.sidebar.radio(
        "Mostrar valores em:", 
        ["Pontos", "Reais (Clube)", "Reais (Normal)"]
    )
    
    valor_milheiro = dt.sidebar.number_input(
        "Valor do Milheiro da Azul (R$):", 
        value=17.00, 
        step=0.50,
        format="%.2f"
    )

    df_ida_total = df_voos[(df_voos['Origem'] == origem_ida) & (df_voos['Destino'] == destino_ida)]
    df_volta_total = df_voos[(df_voos['Origem'] == origem_volta) & (df_voos['Destino'] == destino_volta)]

    # --- CONFIGURAÇÃO DOS SLIDERS DINÂMICOS (IDA) ---
    dt.sidebar.markdown("---")
    dt.sidebar.subheader("✈️ Filtros da Ida")
    
    min_v_ida = int(df_ida_total['Numero voos'].min()) if not df_ida_total.empty else 1
    max_v_ida = int(df_ida_total['Numero voos'].max()) if not df_ida_total.empty else 1
    if min_v_ida == max_v_ida:
        dt.sidebar.text(f"Número de voos (Ida): Fixo em {min_v_ida}")
        slider_voos_ida = (min_v_ida, max_v_ida)
    else:
        slider_voos_ida = dt.sidebar.slider("Ida: Número de voos (Conexões)", min_v_ida, max_v_ida, (min_v_ida, max_v_ida))

    min_t_ida = round(float(df_ida_total['Duracao_Minutos'].min() / 60), 1) if not df_ida_total.empty else 0.0
    max_t_ida = round(float(df_ida_total['Duracao_Minutos'].max() / 60), 1) if not df_ida_total.empty else 24.0
    if min_t_ida == max_t_ida:
        dt.sidebar.text(f"Tempo total (Ida): Fixo em {min_t_ida}h")
        slider_tempo_ida = (min_t_ida, max_t_ida)
    else:
        slider_tempo_ida = dt.sidebar.slider("Ida: Tempo total voo (Horas)", min_t_ida, max_t_ida, (min_t_ida, max_t_ida), step=0.5, format="%.1fh")

    # --- CONFIGURAÇÃO DOS SLIDERS DINÂMICOS (VOLTA) ---
    dt.sidebar.markdown("---")
    dt.sidebar.subheader("🔄 Filtros da Volta")
    
    min_v_volta = int(df_volta_total['Numero voos'].min()) if not df_volta_total.empty else 1
    max_v_volta = int(df_volta_total['Numero voos'].max()) if not df_volta_total.empty else 1
    if min_v_volta == max_v_volta:
        dt.sidebar.text(f"Número de voos (Volta): Fixo em {min_v_volta}")
        slider_voos_volta = (min_v_volta, max_v_volta)
    else:
        slider_voos_volta = dt.sidebar.slider("Volta: Número de voos (Conexões)", min_v_volta, max_v_volta, (min_v_volta, max_v_volta))

    min_t_volta = round(float(df_volta_total['Duracao_Minutos'].min() / 60), 1) if not df_volta_total.empty else 0.0
    max_t_volta = round(float(df_volta_total['Duracao_Minutos'].max() / 60), 1) if not df_volta_total.empty else 24.0
    if min_t_volta == max_t_volta:
        dt.sidebar.text(f"Tempo total (Volta): Fixo em {min_t_volta}h")
        slider_tempo_volta = (min_t_volta, max_t_volta)
    else:
        slider_tempo_volta = dt.sidebar.slider("Volta: Tempo total voo (Horas)", min_t_volta, max_t_volta, (min_t_volta, max_t_volta), step=0.5, format="%.1fh")

    dt.sidebar.markdown("---")
    dt.sidebar.info("💡 **Atenção (Regra Azul):**\nVoos com menos de 90 dias da data atual pagam uma taxa extra de emissão no valor de **R$ 49,90**. Esse valor já é somado automaticamente no cálculo em Reais.")

    # --- PROCESSAMENTO E FILTRAGEM DINÂMICA ---
    # Linha corrigida aqui:
    df_ida_processado = processar_custos(df_ida_total, origem=origem_ida, valor_milheiro=valor_milheiro)
    df_volta_processado = processar_custos(df_volta_total, origem=origem_volta, valor_milheiro=valor_milheiro)

    df_ida_processado = df_ida_processado[
        (df_ida_processado['Numero voos'] >= slider_voos_ida[0]) & (df_ida_processado['Numero voos'] <= slider_voos_ida[1]) &
        (df_ida_processado['Duracao_Minutos'] >= slider_tempo_ida[0] * 60) & (df_ida_processado['Duracao_Minutos'] <= slider_tempo_ida[1] * 60)
    ]
    
    df_volta_processado = df_volta_processado[
        (df_volta_processado['Numero voos'] >= slider_voos_volta[0]) & (df_volta_processado['Numero voos'] <= slider_voos_volta[1]) &
        (df_volta_processado['Duracao_Minutos'] >= slider_tempo_volta[0] * 60) & (df_volta_processado['Duracao_Minutos'] <= slider_tempo_volta[1] * 60)
    ]

    meses_disponiveis = sorted(
        pd.concat([df_ida_processado['Mês/Ano'], df_volta_processado['Mês/Ano']]).dropna().unique(),
        key=lambda x: datetime.strptime(x, "%m/%Y")
    )

    if modo_visualizacao == "Pontos":
        coluna_valor = 'Preco clube'
        is_pontos = True
    elif modo_visualizacao == "Reais (Clube)":
        coluna_valor = 'Custo Real Clube'
        is_pontos = False
    else:
        coluna_valor = 'Custo Real Normal'
        is_pontos = False

    # --- ESCALA GLOBAL DE CORES ---
    valores_globais = pd.concat([df_ida_processado[coluna_valor], df_volta_processado[coluna_valor]]).dropna()
    global_min = valores_globais.min() if not valores_globais.empty else 0
    global_max = valores_globais.max() if not valores_globais.empty else 1

    taxa_base_ida = TAXAS_AEROPORTO.get(origem_ida, TAXA_PADRAO)
    taxa_base_volta = TAXAS_AEROPORTO.get(origem_volta, TAXA_PADRAO)

    # --- RENDERIZAÇÃO DOS CALENDÁRIOS EM CASCATA ---
    for mes_ano in meses_disponiveis:
        mes_int, ano_int = map(int, mes_ano.split("/"))
        
        df_ida_mes = df_ida_processado[df_ida_processado['Mês/Ano'] == mes_ano]
        df_volta_mes = df_volta_processado[df_volta_processado['Mês/Ano'] == mes_ano]

        col1, col2 = dt.columns(2)
        
        with col1:
            dt.markdown(gerar_html_calendario(
                df_ida_mes, ano_int, mes_int, coluna_valor, 
                f"IDA: {origem_ida} ➔ {destino_ida}", taxa_base_ida, is_pontos, global_min, global_max
            ), unsafe_allow_html=True)
            
        with col2:
            dt.markdown(gerar_html_calendario(
                df_volta_mes, ano_int, mes_int, coluna_valor, 
                f"VOLTA: {origem_volta} ➔ {destino_volta}", taxa_base_volta, is_pontos, global_min, global_max
            ), unsafe_allow_html=True)
            
        dt.markdown("<br><hr style='border:1px solid #e2e8f0;'><br>", unsafe_allow_html=True)
