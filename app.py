import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import calendar
import re

dt.set_page_config(page_title="Radar de Voos", layout="wide", page_icon="✈️")

# CONFIGURAÇÕES
ID_PLANILHA = "1kW2FY4lAxRcp2ZSmBVfeuUWgqGZprLE4"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"
TAXAS = {"STM": 36.67, "NAT": 48.26, "BEL": 54.45, "VCP": 31.94, "GRU": 33.64, "BSB": 32.87}

def conv_minutos(dur):
    if not isinstance(dur, str): return 0
    d = re.search(r'(\d+)\s*d', dur.lower())
    h = re.search(r'(\d+)\s*h', dur.lower())
    m = re.search(r'(\d+)\s*m', dur.lower())
    return (int(d.group(1))*1440 if d else 0) + (int(h.group(1))*60 if h else 0) + (int(m.group(1)) if m else 0)

@dt.cache_data(ttl=60)
def carregar():
    try:
        r = requests.get(URL_DRIVE_CSV, headers={"User-Agent": "Mozilla/5.0"})
        df = pd.read_csv(StringIO(r.content.decode('utf-8', errors='ignore')))
        df = df.dropna(subset=['Origem', 'Destino', 'Data partida'])
        df['Origem'] = df['Origem'].astype(str).str.strip().str.upper()
        df['Destino'] = df['Destino'].astype(str).str.strip().str.upper()
        df['Data partida_dt'] = pd.to_datetime(df['Data partida'], format='%d/%m/%Y', errors='coerce')
        df['Duracao_Minutos'] = df['Duracao'].apply(conv_minutos)
        df['Numero voos'] = pd.to_numeric(df['Numero voos'], errors='coerce').fillna(1)
        return df
    except: return pd.DataFrame()

def render_cal(df_mes, col_v, tit, taxa, is_pts, g_min, g_max):
    dt.markdown(f"<div style='text-align:center; font-weight:bold;'>{tit}</div>", unsafe_allow_html=True)
    dt.markdown(f"<div style='text-align:center; font-size:11px;'>Taxa: R${taxa:.2f}</div>", unsafe_allow_html=True)
    
    cal = calendar.Calendar(firstweekday=0)
    mes, ano = df_mes['Data partida_dt'].iloc[0].month, df_mes['Data partida_dt'].iloc[0].year
    
    # Criamos um dicionário para busca rápida: dia -> melhor voo
    df_min = df_mes.sort_values(col_v).groupby(df_mes['Data partida_dt'].dt.day).first()
    
    for semana in cal.monthdayscalendar(ano, mes):
        cols = dt.columns(7)
        for i, day in enumerate(semana):
            if day != 0 and day in df_min.index:
                voo = df_min.loc[day]
                val = voo[col_v]
                # Tooltip detalhado no title=""
                tooltip = f"Saída: {voo['Hora partida']} | Chegada: {voo['Hora chegada']} | Voo: {'Direto' if voo['Numero voos']==1 else 'Conexão'}"
                
                peso = (val - g_min) / (g_max - g_min) if g_max != g_min else 0
                r, g, b = (255, int(247-(45*(peso*2))), int(108+(94*(peso*2)))) if peso > 0.5 else (int(187+(68*(peso*2))), 247, int(208-(100*(peso*2))))
                
                label = f"{val/1000:.1f}k" if is_pts else f"R${val:.0f}"
                cols[i].markdown(f"""<div title='{tooltip}' style='background-color:rgb({r},{g},{b}); padding:5px; border-radius:5px; text-align:center; font-size:11px; cursor: help;'>
                                 <b>{day}</b><br>{label}</div>""", unsafe_allow_html=True)
            elif day != 0: 
                cols[i].markdown(f"<div style='text-align:center; font-size:11px; color:#ccc;'>{day}</div>", unsafe_allow_html=True)

# INTERFACE
df = carregar()
if not df.empty:
    # [Mantido o mesmo layout de filtros anterior]
    dt.sidebar.header("🔍 Filtros")
    rota = dt.sidebar.selectbox("Rota:", sorted(list((df['Origem']+" -> "+df['Destino']).unique())))
    orig, dest = rota.split(" -> ")
    modo = dt.sidebar.radio("Valores:", ["Pontos", "Reais (Clube)", "Reais (Normal)"])
    milheiro = dt.sidebar.number_input("Milheiro (R$):", value=17.0)
    
    # Cálculo
    data_hj = pd.Timestamp(datetime.now().date())
    df['Taxa_Embarque'] = df['Origem'].map(TAXAS).fillna(50.0)
    df['Taxa_Azul'] = ((df['Data partida_dt'] - data_hj).dt.days < 90).apply(lambda x: 49.9 if x else 0)
    df['Custo'] = ((df['Preco clube']/1000)*milheiro) + df['Taxa_Embarque'] + df['Taxa_Azul']
    df['Valor'] = df['Preco clube'] if modo=="Pontos" else (df['Custo'] if modo=="Reais (Clube)" else ((df['Preco normal']/1000)*milheiro)+df['Taxa_Embarque']+df['Taxa_Azul'])

    # Render
    c1, c2 = dt.columns(2)
    meses = sorted(pd.concat([df['Data partida_dt']]).dt.to_period('M').unique())
    g_min, g_max = df['Valor'].min(), df['Valor'].max()
    
    for m in meses:
        df_i = df[(df['Origem']==orig) & (df['Destino']==dest) & (df['Data partida_dt'].dt.to_period('M')==m)]
        df_v = df[(df['Origem']==dest) & (df['Destino']==orig) & (df['Data partida_dt'].dt.to_period('M')==m)]
        with c1: render_cal(df_i, 'Valor', f"IDA: {orig}->{dest}", 36.67, modo=="Pontos", g_min, g_max)
        with c2: render_cal(df_v, 'Valor', f"VOLTA: {dest}->{orig}", 48.26, modo=="Pontos", g_min, g_max)
