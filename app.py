import streamlit as dt
import pandas as pd
import requests
from io import StringIO, BytesIO
import base64
from datetime import datetime
import calendar
import re
import math

# ==========================================
# CONFIGURAÇÕES INICIAIS
# ==========================================
dt.set_page_config(page_title="Radar de Voos - Calendários Compactos", layout="wide", page_icon="✈️")

# LINK DO GOOGLE DRIVE
ID_PLANILHA = "16zImsvHaEvcWJg4eCIrNy4o-NZJ0fZ7L"
URL_DRIVE_CSV = f"https://docs.google.com/uc?export=download&id={ID_PLANILHA}"

# Mapeamento de Localidades (Agrupamento de aeroportos)
LOCALIDADES = {
    "SAO": ["GRU", "VCP", "CGH"],
    "RIO": ["GIG", "SDU", "RRJ"]
}
MAPA_INVERSO = {aero: loc for loc, aeroportos in LOCALIDADES.items() for aero in aeroportos}

# TAXAS FIXAS POR AEROPORTO ATUALIZADAS CONFORME ÚLTIMOS DADOS
TAXAS_AEROPORTO = {
    "STM": 36.67, "NAT": 48.26, "BEL": 54.45, "VCP": 31.94, "GRU": 33.64, "BSB": 32.87,
    "CGH": 62.14, "GIG": 34.11, "SDU": 62.62, "RRJ": 37.83, "CNF": 33.56, "REC": 60.54
}
TAXA_PADRAO = 50.00

# ==========================================
# CSS PARA O EFEITO PISCANTE TURBINADO
# ==========================================
dt.markdown("""
<style>
@keyframes piscar-promocao {
    0% { box-shadow: inset 0 0 0px #22c55e, 0 0 5px rgba(34, 197, 94, 0.2); }
    100% { box-shadow: inset 0 0 20px rgba(34, 197, 94, 0.5), 0 0 25px rgba(34, 197, 94, 0.9); background-color: #dcfce7 !important; }
}
.pisca-efeito {
    animation: piscar-promocao 0.65s infinite alternate ease-in-out !important;
    border: 2px solid #16a34a !important;
    position: relative;
    z-index: 10;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# FUNÇÕES DE PROCESSAMENTO
# ==========================================
def converter_duracao_para_minutos(dur_str):
    if pd.isna(dur_str) or not isinstance(dur_str, str): return 0
    dur_str = dur_str.strip().lower()
    if ':' in dur_str:
        partes = dur_str.split(':')
        if len(partes) >= 2:
            try: return (int(partes[0]) * 60) + int(partes[1])
            except: pass
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
        if response.status_code != 200:
            dt.error(f"Erro ao conectar ao Drive. Status HTTP: {response.status_code}")
            return pd.DataFrame()
            
        conteudo_str = response.content.decode('utf-8', errors='ignore')
        try:
            df = pd.read_csv(StringIO(conteudo_str))
            if 'ORIGEM' not in [c.strip().upper() for c in df.columns]:
                df = pd.read_csv(StringIO(conteudo_str), sep='\t')
        except:
            df = pd.read_csv(StringIO(conteudo_str), sep='\t')
            
        if df.empty: return pd.DataFrame()
        df.columns = df.columns.str.strip().str.upper()
        
        colunas_essenciais = ['ORIGEM', 'DESTINO', 'DATA PARTIDA']
        for col in colunas_essenciais:
            if col not in df.columns: return pd.DataFrame()

        df = df.dropna(subset=colunas_essenciais)
        df['ORIGEM'] = df['ORIGEM'].astype(str).str.strip().str.upper()
        df['DESTINO'] = df['DESTINO'].astype(str).str.strip().str.upper()
        df['ORIGEM_LOC'] = df['ORIGEM'].apply(lambda x: MAPA_INVERSO.get(x, x))
        df['DESTINO_LOC'] = df['DESTINO'].apply(lambda x: MAPA_INVERSO.get(x, x))
        df['PRECO NORMAL'] = pd.to_numeric(df['PRECO NORMAL'], errors='coerce')
        df['PRECO CLUBE'] = pd.to_numeric(df['PRECO CLUBE'], errors='coerce')
        df['NUMERO VOOS'] = pd.to_numeric(df['NUMERO VOOS'], errors='coerce').fillna(1).astype(int)
        df['SUBVOO'] = df.get('SUBVOO', pd.Series(['Nao']*len(df))).astype(str).str.strip()
        df['Duracao_Minutos'] = df['DURACAO'].apply(converter_duracao_para_minutos)
        df['Data partida_dt'] = pd.to_datetime(df['DATA PARTIDA'], dayfirst=True, errors='coerce')
        df['Mês/Ano'] = df['Data partida_dt'].dt.strftime('%m/%Y')
        
        df['Datetime Partida'] = pd.to_datetime(df['DATA PARTIDA'] + ' ' + df['HORA PARTIDA'], dayfirst=True, errors='coerce')
        df['Datetime Chegada'] = pd.to_datetime(df['DATA CHEGADA'] + ' ' + df['HORA CHEGADA'], dayfirst=True, errors='coerce')
        return df
    except Exception as e: 
        dt.error(f"Erro inesperado no processamento da planilha: {e}")
        return pd.DataFrame()

def gerar_multitrechos(df, aeros_origem, aeros_dest, max_con_hours):
    df_leg1 = df[df['ORIGEM'].isin(aeros_origem)].copy()
    df_leg2 = df[df['DESTINO'].isin(aeros_dest)].copy()
    merged = pd.merge(df_leg1, df_leg2, left_on='DESTINO', right_on='ORIGEM', suffixes=('_1', '_2'))
    if merged.empty: return pd.DataFrame()
    
    layover = merged['Datetime Partida_2'] - merged['Datetime Chegada_1']
    merged['Layover_Mins'] = layover.dt.total_seconds() / 60
    valid = merged[(merged['Layover_Mins'] >= 20) & (merged['Layover_Mins'] <= max_con_hours * 60)].copy()
    if valid.empty: return pd.DataFrame()
    
    synth = pd.DataFrame()
    synth['ORIGEM'] = valid['ORIGEM_1']
    synth['DESTINO'] = valid['DESTINO_2']
    synth['ORIGEM_LOC'] = valid['ORIGEM_LOC_1']
    synth['DESTINO_LOC'] = valid['DESTINO_LOC_2']
    synth['DATA PARTIDA'] = valid['DATA PARTIDA_1']
    synth['HORA PARTIDA'] = valid['HORA PARTIDA_1']
    synth['DATA CHEGADA'] = valid['DATA CHEGADA_2']
    synth['HORA CHEGADA'] = valid['HORA CHEGADA_2']
    synth['Data partida_dt'] = valid['Data partida_dt_1']
    synth['Mês/Ano'] = valid['Mês/Ano_1']
    synth['PRECO NORMAL'] = valid['PRECO NORMAL_1'] + valid['PRECO NORMAL_2']
    synth['PRECO CLUBE'] = valid['PRECO CLUBE_1'] + valid['PRECO CLUBE_2']
    synth['NUMERO VOOS'] = valid['NUMERO VOOS_1'] + valid['NUMERO VOOS_2']
    
    dur_total = valid['Datetime Chegada_2'] - valid['Datetime Partida_1']
    synth['Duracao_Minutos'] = dur_total.dt.total_seconds() / 60
    
    def formata_duracao(mins):
        if pd.isna(mins): return ""
        return f"{int(mins // 60)}h {int(mins % 60)}m"
        
    synth['DURACAO'] = synth['Duracao_Minutos'].apply(formata_duracao)
    synth['SUBVOO'] = 'Multitrecho via ' + valid['DESTINO_1']
    synth['DATA PESQUISA'] = valid['DATA PESQUISA_1']
    synth['HORA PESQUISA'] = valid['HORA PESQUISA_1']
    
    data_atual = datetime.now().date()
    def calc_multi_tax(row):
        t1 = TAXAS_AEROPORTO.get(row['ORIGEM_1'], TAXA_PADRAO)
        t2 = TAXAS_AEROPORTO.get(row['ORIGEM_2'], TAXA_PADRAO)
        d1, d2 = row['Datetime Partida_1'], row['Datetime Partida_2']
        if pd.notna(d1) and (d1.date() - data_atual).days < 90: t1 += 49.90
        if pd.notna(d2) and (d2.date() - data_atual).days < 90: t2 += 49.90
        return t1 + t2
        
    synth['MULTITRECHO_TAXA'] = valid.apply(calc_multi_tax, axis=1)
    return synth

def processar_custos(df_voos_filtrado, valor_milheiro):
    df_temp = df_voos_filtrado.copy()
    if df_temp.empty:
        df_temp['Taxa'] = pd.Series(dtype=float)
        df_temp['Custo Real Clube'] = pd.Series(dtype=float)
        df_temp['Custo Real Normal'] = pd.Series(dtype=float)
        return df_temp

    data_atual = datetime.now().date()
    def calcular_taxa(row):
        if 'MULTITRECHO_TAXA' in row and pd.notna(row['MULTITRECHO_TAXA']):
            return row['MULTITRECHO_TAXA']
        base = TAXAS_AEROPORTO.get(row['ORIGEM'], TAXA_PADRAO)
        d = row['Data partida_dt']
        if pd.notna(d) and (d.date() - data_atual).days < 90: return base + 49.90
        return base
        
    df_temp['Taxa'] = df_temp.apply(calcular_taxa, axis=1)
    df_temp['Custo Real Clube'] = ((df_temp['PRECO CLUBE'] / 1000) * valor_milheiro) + df_temp['Taxa']
    df_temp['Custo Real Normal'] = ((df_temp['PRECO NORMAL'] / 1000) * valor_milheiro) + df_temp['Taxa']
    return df_temp

def gerar_html_calendario(df_mes, ano, mes, coluna_valor, titulo, is_pontos, val_min, val_max, threshold_top3):
    meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    
    if not df_mes.empty:
        aeros_unicos = sorted(df_mes['ORIGEM'].unique())
        taxas_str_list = [f"{aero} (R$ {TAXAS_AEROPORTO.get(aero, TAXA_PADRAO):.2f})" for aero in aeros_unicos]
        taxa_str = " | ".join(taxas_str_list)
    else: taxa_str = "R$ --"
    
    html = f"<div style='text-align: center; color: #1f2937; font-size: 15px; font-weight: bold;'>{titulo}</div>"
    html += f"<div style='text-align: center; color: #4b5563; font-size: 11px; margin-bottom: 3px;'>Taxas de Embarque: {taxa_str}</div>"
    html += f"<div style='text-align: center; color: #1e293b; font-size: 14px; margin-bottom: 8px; font-weight: 600;'>{meses_pt[mes]} {ano}</div>"
    
    html += "<table style='width:100%; border-collapse: separate; border-spacing: 3px; text-align:center; font-family: sans-serif;'>"
    html += "<tr style='background-color:#1e293b; color:white; font-size: 11px; font-weight:bold;'>"
    for d in ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']: html += f"<td style='padding:4px; border-radius: 3px;'>{d}</td>"
    html += "</tr>"
    
    df_dia = df_mes.groupby(df_mes['Data partida_dt'].dt.day)[coluna_valor].min().to_dict() if not df_mes.empty else {}
    df_voos_minimos = df_mes.sort_values(coluna_valor).groupby(df_mes['Data partida_dt'].dt.day).first() if not df_mes.empty else pd.DataFrame()
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
                orig, dest = str(voo.get('ORIGEM', '')), str(voo.get('DESTINO', ''))
                p_clube = f"{voo['PRECO CLUBE']:,.0f}".replace(",", ".") if pd.notna(voo['PRECO CLUBE']) else "-"
                p_normal = f"{voo['PRECO NORMAL']:,.0f}".replace(",", ".") if pd.notna(voo['PRECO NORMAL']) else "-"
                tx = f"R${voo['Taxa']:.2f}".replace(".", ",")
                
                subvoo = str(voo.get('SUBVOO', 'Nao')).strip()
                is_multi = subvoo.startswith('Multitrecho')
                
                # --- LÓGICA DO PISCAR E CORES ---
                is_top3 = val <= threshold_top3 and threshold_top3 > 0
                cor_texto = "red" if is_multi else "#1e293b"
                classe_css = "pisca-efeito" if is_top3 else ""
                borda_style = "border: 1px solid #e2e8f0;"
                
                dt_pesquisa = str(voo.get('DATA PESQUISA', '-'))
                hr_pesquisa = str(voo.get('HORA PESQUISA', '-'))
                
                if is_multi:
                    tooltip = f"⚠️ {subvoo} | Saída: {voo['HORA PARTIDA']} ({orig}) | Chegada: {voo['HORA CHEGADA']} ({dest}) | Duração: {voo['DURACAO']} | Preço clube: {p_clube} | Preço normal: {p_normal} | Tx embarque dupla: {tx} | Pesquisa: {dt_pesquisa} {hr_pesquisa}"
                else:
                    skip_str = "Não" if subvoo.lower() in ['nao', 'não', 'nan', ''] else subvoo
                    tooltip = f"Saída: {voo['HORA PARTIDA']} ({orig}) | Chegada: {voo['HORA CHEGADA']} ({dest}) | Duração: {voo['DURACAO']} | Preço clube: {p_clube} | Preço normal: {p_normal} | Tx embarque: {tx} | Skiplagging: {skip_str} | Pesquisa: {dt_pesquisa} {hr_pesquisa}"
                
                html += f"<td title='{tooltip}' class='{classe_css}' style='background-color:rgb({r},{g},{b}); padding:8px 2px; border-radius:5px; {borda_style} cursor: help;'><div style='font-size:14px; font-weight:bold; color:#0f172a;'>{day}</div><div style='font-size:11px; font-weight:800; color:{cor_texto};'>{text_val}</div></td>"
            else: html += f"<td style='background-color:#f8fafc; padding:8px 2px; border-radius:5px; border: 1px dashed #cbd5e1;'><div style='font-size:14px; color:#94a3b8;'>{day}</div><div style='font-size:11px; color:#cbd5e1;'>-</div></td>"
        html += "</tr>"
    return html + "</table>"

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
TEXTO_EXIBIDO = "@Casaldaspassagens"
LINK_INSTAGRAM = "https://www.instagram.com/casaldaspassagens_?igsh=MThxZTl2NHVwbTl2ZQ%3D%3D"
URL_FOTO_PERFIL = "https://drive.google.com/uc?export=download&id=1a_NhrKaI4PLBedx1T6gxHzq4eF57n2ke"

@dt.cache_data
def obter_imagem_base64_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return base64.b64encode(BytesIO(response.content).read()).decode()
    except: return None

img_base64 = obter_imagem_base64_url(URL_FOTO_PERFIL)
if img_base64:
    dt.markdown(f'<div style="display: flex; align-items: center; gap: 15px; margin-bottom: 25px;"><img src="data:image/jpeg;base64,{img_base64}" style="border-radius: 50%; width: 50px; height: 50px; object-fit: cover;"><a href="{LINK_INSTAGRAM}" target="_blank" style="text-decoration: none; color: inherit; font-size: 2.3em; font-weight: bold; font-family: sans-serif;">{TEXTO_EXIBIDO}</a></div>', unsafe_allow_html=True)
else: dt.markdown(f"#[{TEXTO_EXIBIDO}]({LINK_INSTAGRAM})", unsafe_allow_html=True)

df_voos = carregar_dados()

if df_voos.empty: 
    dt.warning("⚠️ Planilha vazia ou com formato inválido. Verifique os erros acima.")
else:
    dt.sidebar.header("🔍 Configurações")
    
    # ---------------- NOVO FLUXO DE ORIGEM E DESTINO DINÂMICOS ----------------
    origens_disp = sorted(list(df_voos['ORIGEM_LOC'].dropna().unique()))
    orig_ida = dt.sidebar.selectbox("📍 Origem (Digite ou selecione):", origens_disp)
    
    # Filtra os destinos possíveis com base na origem selecionada
    destinos_disp = sorted(list(df_voos[df_voos['ORIGEM_LOC'] == orig_ida]['DESTINO_LOC'].dropna().unique()))
    dest_ida = dt.sidebar.selectbox("🎯 Destino:", destinos_disp, disabled=(len(destinos_disp) == 0))
    
    orig_volta, dest_volta = dest_ida, orig_ida
    
    dt.sidebar.markdown("---")
    if orig_ida in LOCALIDADES: aeros_ida = dt.sidebar.multiselect(f"Aeros IDA em {orig_ida}:", LOCALIDADES[orig_ida], default=LOCALIDADES[orig_ida])
    else: aeros_ida = [orig_ida]
    
    if orig_volta in LOCALIDADES: aeros_volta = dt.sidebar.multiselect(f"Aeros VOLTA em {orig_volta}:", LOCALIDADES[orig_volta], default=LOCALIDADES[orig_volta])
    else: aeros_volta = [orig_volta]

    dt.sidebar.markdown("---")
    modo = dt.sidebar.radio("Mostrar valores em:", ["Pontos", "Reais (Clube)", "Reais (Normal)"])
    milheiro = dt.sidebar.number_input("Valor do Milheiro (R$):", value=17.00, step=0.50, format="%.2f")
    
    usar_skiplagging = dt.sidebar.checkbox("Ativar Skiplagging (Buscar Subtrechos)", value=True)
    usar_multitrecho = dt.sidebar.checkbox("Ativar Multitrecho (Busca Combinada)", value=True)
    if usar_multitrecho: max_con_hours = dt.sidebar.number_input("Máximo conexão Multitrecho (hrs)", min_value=1, max_value=20, value=3)
    else: max_con_hours = 0
    
    # ---------------- LÓGICA DE GERAÇÃO E FILTRO ----------------
    df_base = df_voos.copy()
    if not usar_skiplagging: df_base = df_base[~df_base['SUBVOO'].str.lower().str.startswith('sim')]
    
    # Somente renderiza se o destino foi selecionado e for válido
    if dest_ida:
        df_i_normal = df_base[(df_base['ORIGEM_LOC'] == orig_ida) & (df_base['DESTINO_LOC'] == dest_ida)]
        if orig_ida in LOCALIDADES: df_i_normal = df_i_normal[df_i_normal['ORIGEM'].isin(aeros_ida)]
        
        if usar_multitrecho:
            df_i_multi = gerar_multitrechos(df_base, aeros_ida, LOCALIDADES.get(dest_ida, [dest_ida]), max_con_hours)
            df_i_total = pd.concat([df_i_normal, df_i_multi], ignore_index=True) if not df_i_multi.empty else df_i_normal
        else: df_i_total = df_i_normal

        df_v_normal = df_base[(df_base['ORIGEM_LOC'] == orig_volta) & (df_base['DESTINO_LOC'] == dest_volta)]
        if orig_volta in LOCALIDADES: df_v_normal = df_v_normal[df_v_normal['ORIGEM'].isin(aeros_volta)]
        
        if usar_multitrecho:
            df_v_multi = gerar_multitrechos(df_base, aeros_volta, LOCALIDADES.get(dest_volta, [dest_volta]), max_con_hours)
            df_v_total = pd.concat([df_v_normal, df_v_multi], ignore_index=True) if not df_v_multi.empty else df_v_normal
        else: df_v_total = df_v_normal
        
        df_i_proc = processar_custos(df_i_total, milheiro)
        df_v_proc = processar_custos(df_v_total, milheiro)

        # ---------------- SLIDERS DE TEMPO ----------------
        dt.sidebar.markdown("---")
        dt.sidebar.subheader("✈️ Filtros de Tempo/Conexões")
        
        if not df_i_proc.empty:
            v_min_i, v_max_i = int(df_i_proc['NUMERO VOOS'].min()), int(df_i_proc['NUMERO VOOS'].max())
            t_min_i = float(math.floor(df_i_proc['Duracao_Minutos'].min() / 60))
            t_max_i = float(math.ceil(df_i_proc['Duracao_Minutos'].max() / 60))
            if t_min_i == t_max_i: t_max_i += 1.0
        else: v_min_i, v_max_i, t_min_i, t_max_i = 1, 1, 0.0, 1.0

        slide_v_i = dt.sidebar.slider("Ida: Conexões", v_min_i, v_max_i, (v_min_i, v_max_i)) if v_min_i < v_max_i else (v_min_i, v_max_i)
        slide_t_i = dt.sidebar.slider("Ida: Tempo (h)", t_min_i, t_max_i, (t_min_i, t_max_i), step=0.5) if t_min_i < t_max_i else (t_min_i, t_max_i)
        
        if not df_v_proc.empty:
            v_min_v, v_max_v = int(df_v_proc['NUMERO VOOS'].min()), int(df_v_proc['NUMERO VOOS'].max())
            t_min_v = float(math.floor(df_v_proc['Duracao_Minutos'].min() / 60))
            t_max_v = float(math.ceil(df_v_proc['Duracao_Minutos'].max() / 60))
            if t_min_v == t_max_v: t_max_v += 1.0
        else: v_min_v, v_max_v, t_min_v, t_max_v = 1, 1, 0.0, 1.0

        slide_v_v = dt.sidebar.slider("Volta: Conexões", v_min_v, v_max_v, (v_min_v, v_max_v)) if v_min_v < v_max_v else (v_min_v, v_max_v)
        slide_t_v = dt.sidebar.slider("Volta: Tempo (h)", t_min_v, t_max_v, (t_min_v, t_max_v), step=0.5) if t_min_v < t_max_v else (t_min_v, t_max_v)

        if not df_i_proc.empty: df_i_proc = df_i_proc[(df_i_proc['NUMERO VOOS'].between(slide_v_i[0], slide_v_i[1])) & (df_i_proc['Duracao_Minutos'].between(slide_t_i[0]*60, slide_t_i[1]*60))]
        if not df_v_proc.empty: df_v_proc = df_v_proc[(df_v_proc['NUMERO VOOS'].between(slide_v_v[0], slide_v_v[1])) & (df_v_proc['Duracao_Minutos'].between(slide_t_v[0]*60, slide_t_v[1]*60))]

        # ---------------- RENDERIZAÇÃO FINAL ----------------
        col_val = 'PRECO CLUBE' if modo == "Pontos" else ('Custo Real Clube' if modo == "Reais (Clube)" else 'Custo Real Normal')
        is_pts = (modo == "Pontos")
        
        mes_i = df_i_proc['Mês/Ano'] if not df_i_proc.empty and 'Mês/Ano' in df_i_proc.columns else pd.Series(dtype=str)
        mes_v = df_v_proc['Mês/Ano'] if not df_v_proc.empty and 'Mês/Ano' in df_v_proc.columns else pd.Series(dtype=str)
        meses = sorted(pd.concat([mes_i, mes_v]).dropna().unique(), key=lambda x: datetime.strptime(x, "%m/%Y"))
        
        val_ida = df_i_proc[col_val] if not df_i_proc.empty and col_val in df_i_proc.columns else pd.Series(dtype=float)
        val_volta = df_v_proc[col_val] if not df_v_proc.empty and col_val in df_v_proc.columns else pd.Series(dtype=float)
        glob = pd.concat([val_ida, val_volta]).dropna()
        g_min, g_max = (glob.min(), glob.max()) if not glob.empty else (0, 1)

        if not df_i_proc.empty and col_val in df_i_proc.columns:
            menores_i = df_i_proc.groupby(df_i_proc['Data partida_dt'].dt.date)[col_val].min().nsmallest(3)
            threshold_i = menores_i.max() if not menores_i.empty else -1
        else: threshold_i = -1
            
        if not df_v_proc.empty and col_val in df_v_proc.columns:
            menores_v = df_v_proc.groupby(df_v_proc['Data partida_dt'].dt.date)[col_val].min().nsmallest(3)
            threshold_v = menores_v.max() if not menores_v.empty else -1
        else: threshold_v = -1

        for m in meses:
            m_int, a_int = map(int, m.split("/"))
            c1, c2 = dt.columns(2)
            with c1: 
                if not df_i_proc.empty and not df_i_proc[df_i_proc['Mês/Ano']==m].empty:
                    dt.markdown(gerar_html_calendario(df_i_proc[df_i_proc['Mês/Ano']==m], a_int, m_int, col_val, f"IDA: {orig_ida}➔{dest_ida}", is_pts, g_min, g_max, threshold_i), unsafe_allow_html=True)
            with c2: 
                if not df_v_proc.empty and not df_v_proc[df_v_proc['Mês/Ano']==m].empty:
                    dt.markdown(gerar_html_calendario(df_v_proc[df_v_proc['Mês/Ano']==m], a_int, m_int, col_val, f"VOLTA: {orig_volta}➔{dest_volta}", is_pts, g_min, g_max, threshold_v), unsafe_allow_html=True)
            dt.markdown("<hr style='margin:10px 0; border:0.5px solid #eee;'>", unsafe_allow_html=True)
