import streamlit as dt
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
import calendar
import re

dt.set_page_config(page_title="Radar de Voos", layout="wide", page_icon="✈️")

# LINK DO GOOGLE DRIVE
ID_PLANILHA = "1kW2FY4lAxRcp2ZSmBVfeuUWgqGZprLE4"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"

TAXAS_AEROPORTO = {"STM": 36.67, "NAT": 48.26, "BEL": 54.45, "VCP": 31.94, "GRU": 33.64, "BSB": 32.87}
TAXA_PADRAO = 50.00

def converter_duracao_para_minutos(dur_str):
    if pd.isna(dur_str) or not isinstance(dur_str, str): return 0
    dur_str = dur_str.lower()
    dias = horas = minutos = 0
    if match := re.search(r'(\d+)\s*d', dur_str): dias = int(match.group(1))
    if match := re.search(r'(\d+)\s*h', dur_str): horas = int(match.group(1))
    if match := re.search(r'(\d+)\s*m', dur_str): minutos = int(match.group(1))
    return (dias * 1440) + (horas * 60) + minutos

@dt.cache_data(ttl=120)
def carregar_dados():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(URL_DRIVE_CSV, headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.content.decode('utf-8', errors='ignore')))
            df = df.dropna(subset=['Origem', 'Destino', 'Data partida'])
            df['Preco normal'] = pd.to_numeric(df['Preco normal'], errors='coerce')
            df['Preco clube'] = pd.to_numeric(df['Preco clube'], errors='coerce')
            df['Numero voos'] = pd.to_numeric(df['Numero voos'], errors='coerce').fillna(1).astype(int)
            df['Duracao_Minutos'] = df['Duracao'].apply(converter_duracao_para_minutos)
            df['Data partida_dt'] = pd.to_datetime(df['Data partida'], format='%d/%m/%Y', errors='coerce')
            df['Mês/Ano'] = df['Data partida_dt'].dt.strftime('%m/%Y')
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

def processar_custos(df, origem, milheiro):
    if df.empty: return df
    df = df.copy()
    taxa_base = TAXAS_AEROPORTO.get(origem, TAXA_PADRAO)
    data_atual = datetime.now().date()
    df['Taxa'] = df['Data partida_dt'].apply(lambda x: taxa_base + 49.90 if (x.date() - data_atual).days < 90 else taxa_base)
    df['Custo Real Clube'] = ((df['Preco clube'] / 1000) * milheiro) + df['Taxa']
    df['Custo Real Normal'] = ((df['Preco normal'] / 1000) * milheiro) + df['Taxa']
    return df

# --- INTERFACE ---
dt.title("✈️ Radar de Voos Azul")
df_voos = carregar_dados()

if df_voos.empty:
    dt.warning("⚠️ Planilha vazia ou indisponível.")
else:
    dt.sidebar.header("⚙️ Filtros")
    df_voos['Rota_Ida'] = df_voos['Origem'] + " -> " + df_voos['Destino']
    rotas = sorted(list(df_voos['Rota_Ida'].dropna().unique()))
    rota_sel = dt.sidebar.selectbox("Rota:", rotas)
    orig_i, dest_i = rota_sel.split(" -> ")
    orig_v, dest_v = dest_i, orig_i
    
    modo = dt.sidebar.radio("Valores em:", ["Pontos", "Reais (Clube)", "Reais (Normal)"])
    milheiro = dt.sidebar.number_input("Valor Milheiro (R$):", value=17.00, step=0.50)

    # Configuração Sliders
    df_i_tot = df_voos[(df_voos['Origem'] == orig_i) & (df_voos['Destino'] == dest_i)]
    df_v_tot = df_voos[(df_voos['Origem'] == orig_v) & (df_voos['Destino'] == dest_v)]

    dt.sidebar.subheader("✈️ Filtros Ida")
    v_i = dt.sidebar.slider("Ida: Conexões", int(df_i_tot['Numero voos'].min()), int(df_i_tot['Numero voos'].max()), (1, int(df_i_tot['Numero voos'].max())))
    t_i = dt.sidebar.slider("Ida: Tempo (h)", 0.0, 25.0, (0.0, 25.0), step=0.5)

    dt.sidebar.subheader("🔄 Filtros Volta")
    v_v = dt.sidebar.slider("Volta: Conexões", int(df_v_tot['Numero voos'].min()), int(df_v_tot['Numero voos'].max()), (1, int(df_v_tot['Numero voos'].max())))
    t_v = dt.sidebar.slider("Volta: Tempo (h)", 0.0, 25.0, (0.0, 25.0), step=0.5)

    # Processamento
    df_i = processar_custos(df_i_tot, orig_i, milheiro)
    df_v = processar_custos(df_v_tot, orig_v, milheiro)
    
    df_i = df_i[(df_i['Numero voos'].between(*v_i)) & (df_i['Duracao_Minutos'].between(t_i[0]*60, t_i[1]*60))]
    df_v = df_v[(df_v['Numero voos'].between(*v_v)) & (df_v['Duracao_Minutos'].between(t_v[0]*60, t_v[1]*60))]

    col_v, is_pts = ('Preco clube', True) if modo=="Pontos" else ('Custo Real Clube', False) if modo=="Reais (Clube)" else ('Custo Real Normal', False)
    
    glob = pd.concat([df_i[col_v], df_v[col_v]]).dropna()
    g_min, g_max = (glob.min(), glob.max()) if not glob.empty else (0, 1)

    for mes in sorted(pd.concat([df_i['Mês/Ano'], df_v['Mês/Ano']]).unique(), key=lambda x: datetime.strptime(x, "%m/%Y")):
        m_int, a_int = map(int, mes.split("/"))
        c1, c2 = dt.columns(2)
        
        def render_cal(df_mes, col_v, tit, taxa, is_pts):
            dt.subheader(tit)
            cal = calendar.Calendar(firstweekday=0)
            for semana in cal.monthdayscalendar(a_int, m_int):
                cols = dt.columns(7)
                for i, dia in enumerate(semana):
                    if dia != 0:
                        voos = df_mes[df_mes['Data partida_dt'].dt.day == dia].sort_values(col_v)
                        if not voos.empty:
                            min_val = voos[col_v].min()
                            peso = (min_val - g_min) / (g_max - g_min) if g_max != g_min else 0
                            r = int(187 + (68 * (peso * 2))) if peso < 0.5 else 255
                            g = 247 if peso < 0.5 else int(247 - (45 * ((peso - 0.5) * 2)))
                            b = int(208 - (100 * (peso * 2))) if peso < 0.5 else int(108 + (94 * ((peso - 0.5) * 2)))
                            
                            with cols[i].popover(f"{dia}\n{min_val/1000 if is_pts else min_val:.0f}"):
                                dt.write(f"Opções {dia}/{m_int}:")
                                for _, v in voos.iterrows():
                                    dt.markdown(f"- **{v[col_v]:,.0f}** | {v['Hora partida']} | {'Dir' if v['Numero voos']==1 else 'Conexão'}")
                        else: cols[i].button(str(dia), disabled=True)

        with c1: render_cal(df_i[df_i['Mês/Ano']==mes], col_v, f"IDA: {orig_i}➔{dest_i}", TAXAS_AEROPORTO.get(orig_i), is_pts)
        with c2: render_cal(df_v[df_v['Mês/Ano']==mes], col_v, f"VOLTA: {orig_v}➔{dest_v}", TAXAS_AEROPORTO.get(orig_v), is_pts)
