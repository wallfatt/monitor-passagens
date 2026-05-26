import streamlit as dt
import pandas as pd
import requests
from io import StringIO, BytesIO
import base64
from datetime import datetime
import calendar
import re

dt.set_page_config(page_title="Radar de Voos - Calendários Compactos", layout="wide", page_icon="✈️")

# Mapeamento de Localidades
LOCALIDADES = {
    "SAO": ["GRU", "VCP", "CGH"],
    "RIO": ["GIG", "SDU", "RRJ"]
}

# Inverte o mapeamento para facilitar a busca (ex: GRU -> SAO)
MAPA_INVERSO = {aero: loc for loc, aeroportos in LOCALIDADES.items() for aero in aeroportos}

ID_PLANILHA = "16zImsvHaEvcWJg4eCIrNy4o-NZJ0fZ7L"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"

# ... (Funções converter_duracao_para_minutos, carregar_dados, processar_custos, gerar_html_calendario iguais às anteriores) ...

def carregar_dados():
    try:
        response = requests.get(URL_DRIVE_CSV, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.content.decode('utf-8', errors='ignore')))
            df['ORIGEM'] = df['ORIGEM'].astype(str).str.strip().str.upper()
            df['DESTINO'] = df['DESTINO'].astype(str).str.strip().str.upper()
            # Substitui aeroportos pela localidade pai, se existir
            df['ORIGEM_LOC'] = df['ORIGEM'].apply(lambda x: MAPA_INVERSO.get(x, x))
            df['DESTINO_LOC'] = df['DESTINO'].apply(lambda x: MAPA_INVERSO.get(x, x))
            
            df['PRECO NORMAL'] = pd.to_numeric(df['PRECO NORMAL'], errors='coerce')
            df['PRECO CLUBE'] = pd.to_numeric(df['PRECO CLUBE'], errors='coerce')
            df['SUBVOO'] = df['SUBVOO'].astype(str).str.strip()
            df['Duracao_Minutos'] = df['DURACAO'].apply(converter_duracao_para_minutos)
            df['Data partida_dt'] = pd.to_datetime(df['DATA PARTIDA'], format='%d/%m/%Y', errors='coerce')
            df['Mês/Ano'] = df['Data partida_dt'].dt.strftime('%m/%Y')
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- INTERFACE ---
df_voos = carregar_dados()

if df_voos.empty: dt.warning("⚠️ Planilha vazia.")
else:
    dt.sidebar.header("🔍 Configurações")
    
    # Rota baseada nas Localidades
    df_voos['Rota_Ida'] = df_voos['ORIGEM_LOC'] + " -> " + df_voos['DESTINO_LOC']
    rotas = sorted(list(df_voos['Rota_Ida'].dropna().unique()))
    rota_sel = dt.sidebar.selectbox("Selecione a Rota:", rotas)
    orig_ida, dest_ida = rota_sel.split(" -> ")
    
    # Filtro Dinâmico de Aeroportos
    if orig_ida in LOCALIDADES:
        aeros = dt.sidebar.multiselect(f"Aeroportos em {orig_ida}:", LOCALIDADES[orig_ida], default=LOCALIDADES[orig_ida])
    else: aeros = [orig_ida]
    
    usar_skiplagging = dt.sidebar.checkbox("Ativar Skiplagging", value=False)
    
    # Filtragem aplicada
    df_i_total = df_voos[(df_voos['ORIGEM_LOC'] == orig_ida) & (df_voos['DESTINO_LOC'] == dest_ida)]
    if orig_ida in LOCALIDADES: df_i_total = df_i_total[df_i_total['ORIGEM'].isin(aeros)]
    
    if not usar_skiplagging:
        df_i_total = df_i_total[df_i_total['SUBVOO'] == 'Nao']
        
    # ... (Restante da renderização igual ao anterior) ...
