import streamlit as dt
import pandas as pd
import requests
from io import StringIO, BytesIO
import base64
from datetime import datetime
import calendar
import re

# Configuração da página do Streamlit
dt.set_page_config(page_title="Radar de Voos - Calendários Compactos", layout="wide", page_icon="✈️")

# LINK DO GOOGLE DRIVE
ID_PLANILHA = "16zImsvHaEvcWJg4eCIrNy4o-NZJ0fZ7L"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"

# TAXAS FIXAS POR AEROPORTO ATUALIZADAS
TAXAS_AEROPORTO = {
    "STM": 36.67, "NAT": 48.26, "BEL": 54.45, "VCP": 31.94, "GRU": 33.64, "BSB": 32.87
}
TAXA_PADRAO = 50.00

def converter_duracao_para_minutos(dur_str):
    if pd.isna(dur_str) or not isinstance(dur_str, str): return 0
    dur_str = dur_str.lower()
    dias, horas, minutos = 0, 0, 0
    match_d = re.search(r'(\d+)\s*d', dur_str)
    match_h = re.search(r'(\d+)\s*h', dur_str)
    match_m = re.search(r'(\d+)\s*m', dur_str)
    if match_d: dias = int(match_d.group(1))
    if match_h: horas = int(match_h.group(1))
    if match_m: minutos = int(match_m.group(1))
    if not any([match_d, match_h, match_m]):
        match_puro = re.search(r'(\d+)', dur_str)
        if match_puro: minutos = int(match_puro.group(1))
    return (dias * 24 * 60) + (horas * 60) + minutos

@dt.cache_data(ttl=120)
def carregar_dados():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(URL_DRIVE_CSV, headers=headers)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.content.decode('utf-8', errors='ignore')))
            df = df.dropna(subset=['ORIGEM', 'DESTINO', 'DATA PARTIDA'])
            df['ORIGEM'] = df['ORIGEM'].astype(str).str.strip().str.upper()
            df['DESTINO'] = df['DESTINO'].astype(str).str.strip().str.upper()
            df['PRECO NORMAL'] = pd.to_numeric(df['PRECO NORMAL'], errors='coerce')
            df['PRECO CLUBE'] = pd.to_numeric(df['PRECO CLUBE'], errors='coerce')
            df['NUMERO VOOS'] = pd.to_numeric(df['NUMERO VOOS'], errors='coerce').fillna(1).astype(int)
            df['SUBVOO'] = df['SUBVOO'].astype(str).str.strip()
            df['Duracao_Minutos'] = df['DURACAO'].apply(converter_duracao_para_minutos)
            df['Data partida_dt'] = pd.to_datetime(df['DATA PARTIDA'], format='%d/%m/%Y', errors='coerce')
            df['Mês/Ano'] = df['Data partida_dt'].dt.strftime('%m/%Y')
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

def processar_custos(df_voos_filtrado, origem, valor_milheiro):
    if df_voos_filtrado.empty: return df_voos_filtrado
    df_temp = df_voos_filtrado.copy()
    taxa_embarque_base = TAXAS_AEROPORTO.get(origem, TAXA_PADRAO)
    data_atual = datetime.now().date()
    df_temp['Taxa'] = df_temp['Data partida_dt'].apply(lambda d: taxa_embarque_base + 49.90 if (d.date() - data_atual).days < 90 else taxa_embarque_base)
    df_temp['Custo Real Clube'] = ((df_temp['PRECO CLUBE'] / 1000) * valor_milheiro) + df_temp['Taxa']
    df_temp['Custo Real Normal'] = ((df_temp['PRECO NORMAL'] / 1000) * valor_milheiro) + df_temp['Taxa']
    return df_temp

def gerar_html_calendario(df_mes, ano, mes, coluna_valor, titulo, taxa_base, is_pontos, val_min, val_max):
    meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    html = f"<div style='text-align: center; color: #1f2937; font-size: 15px; font-weight: bold;'>{titulo}</div>"
    html += f"<div style='text-align: center; color: #4b5563; font-size: 11px; margin-bottom: 3px;'>Taxa de Embarque: R$ {taxa_base:.2f}</div>"
    html += f"<div style='text-align: center; color: #1e293b; font-size: 14px; margin-bottom: 8px; font-weight: 600;'>{meses_pt[mes]} {ano}</div>"
    html += "<table style='width:100%; border-collapse: separate; border-spacing: 3px; text-align:center; font-family: sans-serif;'>"
    html += "<tr style='background-color:#1e293b; color:white; font-size: 11px; font-weight:bold;'>"
    for d in ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']: html += f"<td style='padding:4px; border-radius: 3px;'>{d}</td>"
    html += "</tr>"
    df_dia = df_mes.groupby(df_mes['Data partida_dt'].dt.day)[coluna_valor].min().to_dict()
    df_voos_minimos = df_mes.sort_values(coluna_valor).groupby(df_mes['Data partida_dt'].dt.day).first()
    val_range = val_max - val_min if val_max != val_min else 1
    cal = calendar.Calendar(firstweekday=0)
    for week in cal.monthdayscalendar(ano, mes):
        html += "<tr>"
        for day in week:
            if day == 0: html += "<td style='background-color:transparent;'></td>"
            elif day in df_dia:
                val = df_dia[day]
                peso = (val - val_min) / val_range
                r, g, b = (int(187 + (68 * (peso * 2))), 247, int(208 - (100 * (peso * 2)))) if peso < 0.5 else (255, int(247 - (45 * ((peso - 0.5) * 2))), int(108 + (94 * ((peso - 0.5) * 2))))
                text_val = f"{val/1000:.1f}k" if is_pontos else f"R${val:.0f}"
                voo = df_voos_minimos.loc[day]
                tooltip = f"Saída: {voo['HORA PARTIDA']} | Chegada: {voo['HORA CHEGADA']}"
                if str(voo.get('SUBVOO', 'Nao')).lower().startswith('sim'): tooltip += f" | ⚠️ SKIPIAG: {voo['SUBVOO']}"
                tooltip += f" | Duração: {voo['DURACAO']}"
                html += f"<td title='{tooltip}' style='background-color:rgb({r},{g},{b}); padding:8px 2px; border-radius:5px; border: 1px solid #e2e8f0; cursor: help;'><div style='font-size:14px; font-weight:bold; color:#0f172a;'>{day}</div><div style='font-size:11px; font-weight:800; color:#1e293b;'>{text_val}</div></td>"
            else: html += f"<td style='background-color:#f8fafc; padding:8px 2px; border-radius:5px; border: 1px dashed #cbd5e1;'><div style='font-size:14px; color:#94a3b8;'>{day}</div><div style='font-size:11px; color:#cbd5e1;'>-</div></td>"
        html += "</tr>"
    return html + "</table>"

# --- INTERFACE ---
TEXTO_EXIBIDO = "@Casaldaspassagens"
df_voos = carregar_dados()

if df_voos.empty: dt.warning("⚠️ Planilha vazia ou erro de conexão.")
else:
    dt.sidebar.header("🔍 Configurações")
    df_voos['Rota_Ida'] = df_voos['ORIGEM'] + " -> " + df_voos['DESTINO']
    rota_sel = dt.sidebar.selectbox("Selecione a Rota:", sorted(list(df_voos['Rota_Ida'].dropna().unique())))
    orig_ida, dest_ida = rota_sel.split(" -> ")
    orig_volta, dest_volta = dest_ida, orig_ida
    modo = dt.sidebar.radio("Mostrar valores em:", ["Pontos", "Reais (Clube)", "Reais (Normal)"])
    milheiro = dt.sidebar.number_input("Valor do Milheiro (R$):", value=17.00, step=0.50, format="%.2f")
    usar_skiplagging = dt.sidebar.checkbox("Ativar Skiplagging (Buscar Subtrechos)", value=False)
    
    df_i_total = df_voos[(df_voos['ORIGEM'] == orig_ida) & (df_voos['DESTINO'] == dest_ida)]
    df_v_total = df_voos[(df_voos['ORIGEM'] == orig_volta) & (df_voos['DESTINO'] == dest_volta)]
    
    df_i_proc = processar_custos(df_i_total, orig_ida, milheiro)
    df_v_proc = processar_custos(df_v_total, orig_volta, milheiro)
    
    if not usar_skiplagging:
        df_i_proc = df_i_proc[df_i_proc['SUBVOO'] == 'Nao']
        df_v_proc = df_v_proc[df_v_proc['SUBVOO'] == 'Nao']

    col_val = 'PRECO CLUBE' if modo == "Pontos" else ('Custo Real Clube' if modo == "Reais (Clube)" else 'Custo Real Normal')
    is_pts = (modo == "Pontos")
    
    meses = sorted(pd.concat([df_i_proc['Mês/Ano'], df_v_proc['Mês/Ano']]).dropna().unique(), key=lambda x: datetime.strptime(x, "%m/%Y"))
    g_min, g_max = (pd.concat([df_i_proc[col_val], df_v_proc[col_val]]).min(), pd.concat([df_i_proc[col_val], df_v_proc[col_val]]).max())

    for m in meses:
        m_int, a_int = map(int, m.split("/"))
        c1, c2 = dt.columns(2)
        with c1: dt.markdown(gerar_html_calendario(df_i_proc[df_i_proc['Mês/Ano']==m], a_int, m_int, col_val, f"IDA: {orig_ida}➔{dest_ida}", TAXAS_AEROPORTO.get(orig_ida, TAXA_PADRAO), is_pts, g_min, g_max), unsafe_allow_html=True)
        with c2: dt.markdown(gerar_html_calendario(df_v_proc[df_v_proc['Mês/Ano']==m], a_int, m_int, col_val, f"VOLTA: {orig_volta}➔{dest_volta}", TAXAS_AEROPORTO.get(orig_volta, TAXA_PADRAO), is_pts, g_min, g_max), unsafe_allow_html=True)
        dt.markdown("<hr>", unsafe_allow_html=True)
