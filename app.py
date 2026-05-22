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

def processar_custos(df_voos_filtrado, origem, valor_milheiro):
    if df_voos_filtrado.empty: return df_voos_filtrado
    df_temp = df_voos_filtrado.copy()
    taxa_embarque_base = TAXAS_AEROPORTO.get(origem, TAXA_PADRAO)
    data_atual = datetime.now().date()
    
    def calcular_taxa_total(data_voo):
        if pd.notna(data_voo):
            if (data_voo.date() - data_atual).days < 90:
                return taxa_embarque_base + 49.90
        return taxa_embarque_base

    df_temp['Taxa'] = df_temp['Data partida_dt'].apply(calcular_taxa_total)
    df_temp['Custo Real Clube'] = ((df_temp['Preco clube'] / 1000) * valor_milheiro) + df_temp['Taxa']
    df_temp['Custo Real Normal'] = ((df_temp['Preco normal'] / 1000) * valor_milheiro) + df_temp['Taxa']
    return df_temp

def gerar_html_calendario(df_mes, ano, mes, coluna_valor, titulo, taxa_base, is_pontos, val_min, val_max):
    meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
                7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    
    html = f"<div style='text-align: center; color: #1f2937; font-size: 15px; font-weight: bold;'>{titulo}</div>"
    html += f"<div style='text-align: center; color: #4b5563; font-size: 11px; margin-bottom: 3px;'>Taxa de Embarque: R$ {taxa_base:.2f}</div>"
    html += f"<div style='text-align: center; color: #1e293b; font-size: 14px; margin-bottom: 8px; font-weight: 600;'>{meses_pt[mes]} {ano}</div>"
    
    html += "<table style='width:100%; border-collapse: separate; border-spacing: 3px; text-align:center; font-family: sans-serif;'>"
    html += "<tr style='background-color:#1e293b; color:white; font-size: 11px; font-weight:bold;'>"
    for d in ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']:
        html += f"<td style='padding:4px; border-radius: 3px;'>{d}</td>"
    html += "</tr>"

    df_dia = df_mes.groupby(df_mes['Data partida_dt'].dt.day)[coluna_valor].min().to_dict() if not df_mes.empty else {}
    df_voos_minimos = df_mes.sort_values(coluna_valor).groupby(df_mes['Data partida_dt'].dt.day).first() if not df_mes.empty else pd.DataFrame()
    
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
                        r, g, b = int(187 + (68 * (peso * 2))), 247, int(208 - (100 * (peso * 2)))
                    else:
                        r, g, b = 255, int(247 - (45 * ((peso - 0.5) * 2))), int(108 + (94 * ((peso - 0.5) * 2)))
                    
                    text_val = f"{val/1000:.1f}k" if is_pontos else f"R${val:.0f}"
                    
                    if day in df_voos_minimos.index:
                        voo = df_voos_minimos.loc[day]
                        tooltip = f"Saída: {voo['Hora partida']} | Chegada: {voo['Hora chegada']} | Número de voos: {voo['Numero voos']} | Duração: {voo['Duracao']}"
                    else:
                        tooltip = ""
                        
                    html += f"<td title='{tooltip}' style='background-color:rgb({r},{g},{b}); padding:8px 2px; border-radius:5px; box-shadow: 1px 1px 2px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; cursor: help;'>"
                    html += f"<div style='font-size:14px; font-weight:bold; color:#0f172a;'>{day}</div>"
                    html += f"<div style='font-size:11px; font-weight:800; color:#1e293b;'>{text_val}</div>"
                    html += "</td>"
                else:
                    html += f"<td style='background-color:#f8fafc; padding:8px 2px; border-radius:5px; border: 1px dashed #cbd5e1;'>"
                    html += f"<div style='font-size:14px; color:#94a3b8;'>{day}</div>"
                    html += f"<div style='font-size:11px; color:#cbd5e1;'>-</div>"
                    html += "</td>"
        html += "</tr>"
    html += "</table>"
    return html

# --- INÍCIO DA INTERFACE ---

# Configurações do Cabeçalho Customizado
TEXTO_EXIBIDO = "@Casaldaspassagens" 
LINK_INSTAGRAM = "https://www.instagram.com/casaldaspassagens_?igsh=MThxZTl2NHVwbTl2ZQ%3D%3D"
URL_FOTO_PERFIL = "https://drive.google.com/uc?export=download&id=1a_NhrKaI4PLBedx1T6gxHzq4eF57n2ke"

@dt.cache_data
def obter_imagem_base64_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        img_bytes = BytesIO(response.content)
        encoded_string = base64.b64encode(img_bytes.read()).decode()
        return encoded_string
    except Exception:
        return None

img_base64 = obter_imagem_base64_url(URL_FOTO_PERFIL)

if img_base64:
    html_titulo = f"""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 25px;">
        <img src="data:image/jpeg;base64,{img_base64}" 
             style="border-radius: 50%; width: 50px; height: 50px; object-fit: cover;">
        <a href="{LINK_INSTAGRAM}" target="_blank" 
           style="text-decoration: none; color: inherit; font-size: 2.3em; font-weight: bold; font-family: sans-serif;">
           {TEXTO_EXIBIDO}
        </a>
    </div>
    """
    dt.markdown(html_titulo, unsafe_allow_html=True)
else:
    dt.markdown(f"#[{TEXTO_EXIBIDO}]({LINK_INSTAGRAM})", unsafe_allow_html=True)

df_voos = carregar_dados()

if df_voos.empty:
    dt.warning("⚠️ Planilha vazia ou erro de conexão.")
else:
    dt.sidebar.header("🔍 Configurações")
    
    df_voos['Rota_Ida'] = df_voos['Origem'] + " -> " + df_voos['Destino']
    rotas = sorted(list(df_voos['Rota_Ida'].dropna().unique()))
    rota_sel = dt.sidebar.selectbox("Selecione a Rota:", rotas)
    orig_ida, dest_ida = rota_sel.split(" -> ")
    orig_volta, dest_volta = dest_ida, orig_ida
    
    modo = dt.sidebar.radio("Mostrar valores em:", ["Pontos", "Reais (Clube)", "Reais (Normal)"])
    milheiro = dt.sidebar.number_input("Valor do Milheiro (R$):", value=17.00, step=0.50, format="%.2f")

    # Bases totais para Sliders
    df_i_total = df_voos[(df_voos['Origem'] == orig_ida) & (df_voos['Destino'] == dest_ida)]
    df_v_total = df_voos[(df_voos['Origem'] == orig_volta) & (df_voos['Destino'] == dest_volta)]

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
    t_min_v, t_max_v = round(df_v_total['Duracao_Minutos'].min()/60, 1) if not df_v_total.empty else 0.0, round(df_v_total['Duracao_Minutos'].max()/60, 1) if not df_v_total.empty else 0.0
    slide_t_v = dt.sidebar.slider("Volta: Tempo (h)", t_min_v, t_max_v, (t_min_v, t_max_v), step=0.5)

    dt.sidebar.markdown("---")
    dt.sidebar.info("💡 **Regra 90 dias:** Voos em < 90 dias somam **R$ 49,90** de taxa Azul automaticamente.")

    # Processamento
    df_i_proc = processar_custos(df_i_total, origem=orig_ida, valor_milheiro=milheiro)
    df_v_proc = processar_custos(df_v_total, origem=orig_volta, valor_milheiro=milheiro)

    # Filtragem
    df_i_proc = df_i_proc[(df_i_proc['Numero voos'].between(slide_v_i[0], slide_v_i[1])) & (df_i_proc['Duracao_Minutos'].between(slide_t_i[0]*60, slide_t_i[1]*60))]
    df_v_proc = df_v_proc[(df_v_proc['Numero voos'].between(slide_v_v[0], slide_v_v[1])) & (df_v_proc['Duracao_Minutos'].between(slide_t_v[0]*60, slide_t_v[1]*60))]

    meses = sorted(pd.concat([df_i_proc['Mês/Ano'], df_v_proc['Mês/Ano']]).dropna().unique(), key=lambda x: datetime.strptime(x, "%m/%Y"))
    is_pts = modo == "Pontos"

    # Escala Global
    glob = pd.concat([df_i_proc[col_val], df_v_proc[col_val]]).dropna()
    g_min, g_max = (glob.min(), glob.max()) if not glob.empty else (0, 1)

    t_base_i, t_base_v = TAXAS_AEROPORTO.get(orig_ida, TAXA_PADRAO), TAXAS_AEROPORTO.get(orig_volta, TAXA_PADRAO)

    # Renderização
    for m in meses:
        m_int, a_int = map(int, m.split("/"))
        c1, c2 = dt.columns(2)
        with c1: dt.markdown(gerar_html_calendario(df_i_proc[df_i_proc['Mês/Ano']==m], a_int, m_int, col_val, f"IDA: {orig_ida}➔{dest_ida}", t_base_i, is_pts, g_min, g_max), unsafe_allow_html=True)
        with c2: dt.markdown(gerar_html_calendario(df_v_proc[df_v_proc['Mês/Ano']==m], a_int, m_int, col_val, f"VOLTA: {orig_volta}➔{dest_volta}", t_base_v, is_pts, g_min, g_max), unsafe_allow_html=True)
        dt.markdown("<hr style='margin:10px 0; border:0.5px solid #eee;'>", unsafe_allow_html=True)
