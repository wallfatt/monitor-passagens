import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
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
        df['Origem'], df['Destino'] = df['Origem'].str.upper(), df['Destino'].str.upper()
        df['Data partida_dt'] = pd.to_datetime(df['Data partida'], format='%d/%m/%Y')
        df['Duracao_Minutos'] = df['Duracao'].apply(conv_minutos)
        return df
    except: return pd.DataFrame()

# INTERFACE
df = carregar()
if df.empty:
    dt.error("Erro ao carregar dados.")
else:
    dt.sidebar.header("Filtros")
    rota = dt.sidebar.selectbox("Rota:", sorted(list((df['Origem']+" -> "+df['Destino']).unique())))
    orig, dest = rota.split(" -> ")
    modo = dt.sidebar.radio("Valores em:", ["Pontos", "Reais (Clube)", "Reais (Normal)"])
    milheiro = dt.sidebar.number_input("Milheiro (R$):", value=17.0)

    # Filtragem
    df_i = df[(df['Origem']==orig) & (df['Destino']==dest)].copy()
    df_v = df[(df['Origem']==dest) & (df['Destino']==orig)].copy()
    
    # Cálculo
    for d in [df_i, df_v]:
        taxa = TAXAS.get(d['Origem'].iloc[0] if not d.empty else "", 50.0)
        d['Custo'] = ((d['Preco clube']/1000)*milheiro) + taxa + (49.9 if (d['Data partida_dt']-datetime.now()).dt.days < 90 else 0)
        d['Valor_Exibir'] = d['Preco clube'] if modo=="Pontos" else d['Custo']

    # Render
    c1, c2 = dt.columns(2)
    for col, data, tit in [(c1, df_i, f"IDA: {orig}->{dest}"), (c2, df_v, f"VOLTA: {dest}->{orig}")]:
        with col:
            dt.subheader(tit)
            meses = sorted(data['Data partida_dt'].dt.to_period('M').unique())
            for m in meses:
                dt.write(f"### {m}")
                df_m = data[data['Data partida_dt'].dt.to_period('M') == m]
                dias = sorted(df_m['Data partida_dt'].dt.day.unique())
                
                # Grade de dias
                cols_grid = dt.columns(7)
                for i, d in enumerate(dias):
                    voos = df_m[df_m['Data partida_dt'].dt.day == d].sort_values('Valor_Exibir')
                    with cols_grid[i % 7].popover(str(d)):
                        for _, v in voos.iterrows():
                            dt.markdown(f"- {v['Valor_Exibir']:,.0f} | {v['Hora partida']}")
