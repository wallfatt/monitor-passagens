import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import calendar
import re

# Configuração da página do Streamlit
dt.set_page_config(page_title="Radar de Voos - Calendários Compactos", layout="wide", page_icon="✈️")

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
    dias, horas, minutos = 0, 0, 0
    
    # Busca por dias (d), horas (h) e minutos (m)
    match_d = re.search(r'(\d+)\s*d', dur_str)
    match_h = re.search(r'(\d+)\s*h', dur_str)
    match_m = re.search(r'(\d+)\s*m', dur_str)
    
    if match_d: dias = int(match_d.group(1))
    if match_h: horas = int(match_h.group(1))
    if match_m: minutos = int(match_m.group(1))
    
    # Caso o dado seja apenas um número sem letras, assume minutos
    if not any([match_d, match_h, match_m]):
        match_puro = re.search(r'(\d+)', dur_str)
        if match_puro: minutos = int(match_puro.group(1))
            
    return (dias * 24 * 60) + (horas * 60) + minutos

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
            
            # Conversão de tempo total com suporte a DIAS
            df['Duracao_Minutos'] = df['Duracao'].apply(converter_duracao_para_minutos)
            df['Data partida_dt'] = pd.to_datetime(df['Data partida'], format='%d/%m/%Y', errors='coerce')
            df['Mês/Ano'] = df['Data partida_dt'].dt.strftime('%m/%Y')
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def render_cal(df_mes, col_v, tit, taxa, is_pts, g_min, g_max):
    dt.markdown(f"<div style='text-align:center; font-weight:bold;'>{tit}</div>", unsafe_allow_html=True)
    dt.markdown(f"<div style='text-align:center; font-size:11px;'>Taxa: R${taxa:.2f}</div>", unsafe_allow_html=True)
    
    cal = calendar.Calendar(firstweekday=0)
    mes, ano = df_mes['Data partida_dt'].iloc[0].month, df_mes['Data partida_dt'].iloc[0].year
    
    # Busca o voo mais barato de cada dia para montar o tooltip
    df_min = df_mes.sort_values(col_v).groupby(df_mes['Data partida_dt'].dt.day).first()
    
    for semana in cal.monthdayscalendar(ano, mes):
        cols = dt.columns(7)
        for i, day in enumerate(semana):
            if day != 0 and day in df_min.index:
                voo = df_min.loc[day]
                val = voo[col_v]
                peso = (val - g_min) / (g_max - g_min) if g_max != g_min else 0
                r, g, b = (255, int(247-(45*(peso*2))), int(108+(94*(peso*2)))) if peso > 0.5 else (int(187+(68*(peso*2))), 247, int(208-(100*(peso*2))))
                
                # Formatando o valor corretamente (correção do bug visual)
                label_valor = f"{val/1000:.1f}k" if is_pts else f"R${val:.0f}"
                
                # Montando o Tooltip (Dica ao passar o mouse)
                tipo_voo = 'Direto' if voo['Numero voos'] == 1 else 'Conexão'
                tooltip_texto = f"Saída: {voo['Hora partida']} | Chegada: {voo['Hora chegada']} | {tipo_voo} | Duração: {voo['Duracao']}"
                
                # Adicionado title= e cursor:help
                cols[i].markdown(f"""<div title='{tooltip_texto}' style='background-color:rgb({r},{g},{b}); padding:5px; border-radius:5px; text-align:center; font-size:11px; cursor:help;'>
                                 <b>{day}</b><br>{label_valor}</div>""", unsafe_allow_html=True)
            elif day != 0: 
                cols[i].markdown(f"<div style='text-align:center; font-size:11px; color:#ccc;'>{day}</div>", unsafe_allow_html=True)

# INTERFACE
df = carregar_dados()
if not df.empty:
    dt.sidebar.header("🔍 Filtros")
    
    df['Rota_Ida'] = df['Origem'] + " -> " + df['Destino']
    rotas = sorted(list(df['Rota_Ida'].dropna().unique()))
    rota_sel = dt.sidebar.selectbox("Selecione a Rota:", rotas)
    orig_ida, dest_ida = rota_sel.split(" -> ")
    orig_volta, dest_volta = dest_ida, orig_ida
    
    modo = dt.sidebar.radio("Mostrar valores em:", ["Pontos", "Reais (Clube)", "Reais (Normal)"])
    milheiro = dt.sidebar.number_input("Valor do Milheiro (R$):", value=17.00, step=0.50, format="%.2f")

    # Bases totais para Sliders
    df_i_total = df[(df['Origem'] == orig_ida) & (df['Destino'] == dest_ida)]
    df_v_total = df[(df['Origem'] == orig_volta) & (df['Destino'] == dest_volta)]

    # Sliders Ida
    dt.sidebar.markdown("---")
    dt.sidebar.subheader("✈️ Filtros Ida")
    v_min_i, v_max_i = int(df_i_total['Numero voos'].min() or 1), int(df_i_total['Numero voos'].max() or 1)
    slide_v_i = dt.sidebar.slider("Ida: Conexões", v_min_i, v_max_i, (v_min_i, v_max_i)) if v_min_i != v_max_i else (v_min_i, v_max_i)
    t_min_i, t_max_i = round(df_i_total['Duracao_Minutos'].min()/60, 1) if not df_i_total.empty else 0.0, round(df_i_total['Duracao_Minutos'].max()/60, 1) if not df_i_total.empty else 0.0
    slide_t_i = dt.sidebar.slider("Ida: Tempo (h)", t_min_i, t_max_i, (t_min_i, t_max_i), step=0.5)

    # Sliders Volta
    dt.sidebar.markdown("---")
    dt.sidebar.subheader("🔄 Filtros Volta")
    v_min_v, v_max_v = int(df_v_total['Numero voos'].min() or 1), int(df_v_total['Numero voos'].max() or 1)
    slide_v_v = dt.sidebar.slider("Volta: Conexões", v_min_v, v_max_v, (v_min_v, v_max_v)) if v_min_v != v_max_v else (v_min_v, v_max_v)
    t_min_v, t_max_v = round(df_v_total['Duracao_Minutos'].min()/60,
