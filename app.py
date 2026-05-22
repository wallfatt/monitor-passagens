import streamlit as st
import pandas as pd
import calendar

# 1. Configuração da página
st.set_page_config(page_title="Radar Azul - Ida e Volta", layout="wide")
st.title("✈️ Radar de Passagens - Ida e Volta")

caminho_csv = "https://drive.google.com/uc?export=download&id=1VFLoXan_R9NgwPrk_Qw5VZg1wrdtMraI"

st.sidebar.header("⚙️ Estado do Ficheiro")
st.sidebar.info("🌐 A ler dados da nuvem...")

# --- CSS DO CALENDÁRIO ---
st.markdown("""
<style>
    .cal-container { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin-bottom: 20px; }
    .cal-header { text-align: center; font-weight: bold; padding: 2px; color: #555; font-size: 0.85em; }
    .cal-day { padding: 5px 2px; border-radius: 4px; text-align: center; border: 1px solid #e0e0e0; display: flex; flex-direction: column; justify-content: center; min-height: 55px; cursor: help;}
    .cal-day:hover { transform: scale(1.05); transition: 0.2s; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    .cal-date { font-weight: bold; font-size: 0.9em; margin-bottom: 2px; color: #333;}
    .cal-price { font-size: 0.75em; font-weight: 700; line-height: 1.1;}
    .best-price { background-color: #28a745; color: white; border-color: #28a745; box-shadow: 0 2px 4px rgba(40,167,69,0.3);}
    .cheap { background-color: #d4edda; color: #155724; border-color: #c3e6cb; }
    .medium { background-color: #fff3cd; color: #856404; border-color: #ffeeba; }
    .expensive { background-color: #f8d7da; color: #721c24; border-color: #f5c6cb; }
    .empty { background-color: #f8f9fa; color: #adb5bd; cursor: default; }
    .empty:hover { transform: none; box-shadow: none; }
    .blank { background: transparent; border: none; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA E FORMATAÇÃO ---
def limpar_preco(preco_val):
    if pd.isna(preco_val): return None
    preco_str = str(preco_val).strip()
    if "Ind" in preco_str or "Não" in preco_str: return None
    try:
        return int(float(preco_str.replace(',', '.')) * 1000)
    except:
        return None

def formatar_preco(pontos, modo, milheiro):
    """Formata o valor para Pontos ou Reais dependendo da escolha do utilizador."""
    if pd.isna(pontos): return "Esgotado"
    if modo == "Pontos":
        return f"{int(pontos):,} Pts".replace(",", ".")
    else:
        reais = (pontos / 1000) * milheiro
        # Formata para padrão moeda (ex: R$ 528,00)
        return f"R$ {reais:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def criar_dicionario_tooltips(df_rota, modo, milheiro):
    voos_dict = {}
    if df_rota.empty: return voos_dict
    
    for data, grupo in df_rota.groupby('Data Formatada'):
        grupo_ordenado = grupo.sort_values('Preco_Num', na_position='last')
        linhas = [f"Voos em {data.strftime('%d/%m/%Y')}:"]
        
        for _, row in grupo_ordenado.iterrows():
            preco_str = formatar_preco(row['Preco_Num'], modo, milheiro)
            linhas.append(f"• {row['Partida']} ➔ {row['Chegada']} | {preco_str}")
            
        voos_dict[data] = "&#10;".join(linhas)
    return voos_dict

def formatar_tabela_exibicao(df_filtrado, col_preco, modo, milheiro):
    """Ajusta a tabela inferior para mostrar a coluna certa consoante a moeda."""
    df_exibicao = df_filtrado.drop(columns=['Data Formatada', 'Preco_Num']).copy()
    if modo == "Reais":
        df_exibicao["Preço (R$)"] = df_filtrado["Preco_Num"].apply(
            lambda x: formatar_preco(x, modo, milheiro) if pd.notna(x) else "Esgotado"
        )
        df_exibicao = df_exibicao.drop(columns=[col_preco])
    else:
        df_exibicao = df_exibicao.rename(columns={col_preco: "Pontos (Mil)"})
    return df_exibicao

@st.cache_data(ttl=30)
def carregar_dados():
    try:
        df = pd.read_csv(caminho_csv, sep=',', encoding='utf-8', on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao ler o CSV da nuvem: {e}")
        return None

def gerar_html_calendario(ano, mes, precos_diarios, min_abs, lim_barato, lim_medio, tooltips_dict, modo, milheiro):
    cal = calendar.monthcalendar(ano, mes)
    html_cal = '<div class="cal-container">'
    
    for d in ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']:
        html_cal += f'<div class="cal-header">{d}</div>'
        
    for semana in cal:
        for dia in semana:
            if dia == 0:
                html_cal += '<div class="blank"></div>'
            else:
                data_atual = pd.Timestamp(year=ano, month=mes, day=dia)
                tooltip_texto = tooltips_dict.get(data_atual, "Sem voos registados")
                
                if precos_diarios is not None and data_atual in precos_diarios.index and pd.notna(precos_diarios[data_atual]):
                    preco = precos_diarios[data_atual]
                    preco_exibicao = formatar_preco(preco, modo, milheiro)
                    
                    if preco == min_abs: css_class = "best-price"
                    elif preco <= lim_barato: css_class = "cheap"
                    elif preco <= lim_medio: css_class = "medium"
                    else: css_class = "expensive"
                        
                    html_cal += f'<div class="cal-day {css_class}" title="{tooltip_texto}"><div class="cal-date">{dia}</div><div class="cal-price">{preco_exibicao}</div></div>'
                else:
                    html_cal += f'<div class="cal-day empty" title="Sem opções para este dia"><div class="cal-date">{dia}</div><div class="cal-price">-</div></div>'
    html_cal += '</div>'
    return html_cal

# --- EXECUÇÃO PRINCIPAL ---
df_bruto = carregar_dados()

if df_bruto is not None:
    col_data = "Data Voo" if "Data Voo" in df_bruto.columns else None
    col_preco = [c for c in df_bruto.columns if "Pre" in c]
    col_preco = col_preco[0] if len(col_preco) > 0 else None
    
    if col_data and col_preco and "Origem" in df_bruto.columns and "Destino" in df_bruto.columns:
        
        df_processado = df_bruto.copy()
        df_processado['Data Formatada'] = pd.to_datetime(df_processado[col_data], format='%d/%m/%Y', errors='coerce')
        df_processado['Preco_Num'] = df_processado[col_preco].apply(limpar_preco)
        
        # Filtros de Rota
        st.sidebar.markdown("---")
        st.sidebar.header("🔎 Selecione a Ida")
        origens = sorted(df_processado["Origem"].dropna().unique())
        origem_sel = st.sidebar.selectbox("Origem (Ida):", origens)
        
        destinos = sorted(df_processado[df_processado["Origem"] == origem_sel]["Destino"].dropna().unique())
        destino_sel = st.sidebar.selectbox("Destino (Ida):", destinos)
        
        # Filtros de Moeda
        st.sidebar.markdown("---")
        st.sidebar.header("💰 Moeda de Exibição")
        modo_exibicao = st.sidebar.radio("Mostrar preços em:", ["Pontos", "Reais"])
        
        valor_milheiro = 0.0
        if modo_exibicao == "Reais":
            valor_milheiro = st.sidebar.number_input("Valor de 1.000 pontos (R$):", min_value=0.01, value=15.00, step=0.50, format="%.2f")
        
        df_ida = df_processado[(df_processado["Origem"] == origem_sel) & (df_processado["Destino"] == destino_sel)].copy()
        df_volta = df_processado[(df_processado["Origem"] == destino_sel) & (df_processado["Destino"] == origem_sel)].copy()
        
        if not df_ida.empty or not df_volta.empty:
            
            tooltips_ida = criar_dicionario_tooltips(df_ida, modo_exibicao, valor_milheiro)
            tooltips_volta = criar_dicionario_tooltips(df_volta, modo_exibicao, valor_milheiro)
            
            col_ida, col_volta = st.columns(2)
            
            with col_ida: st.subheader(f"🛫 IDA: {origem_sel} ➔ {destino_sel}")
            with col_volta: st.subheader(f"🛬 VOLTA: {destino_sel} ➔ {origem_sel}")
            
            # Limites Ida
            if not df_ida.empty:
                precos_ida = df_ida.groupby('Data Formatada')['Preco_Num'].min()
                min_ida = precos_ida.min()
                dif_ida = precos_ida.max() - min_ida
                barato_ida = min_ida + (dif_ida * 0.25)
                medio_ida = min_ida + (dif_ida * 0.60)
            else:
                precos_ida = None; min_ida = barato_ida = medio_ida = 0
                
            # Limites Volta
            if not df_volta.empty:
                precos_volta = df_volta.groupby('Data Formatada')['Preco_Num'].min()
                min_volta = precos_volta.min()
                dif_volta = precos_volta.max() - min_volta
                barato_volta = min_volta + (dif_volta * 0.25)
                medio_volta = min_volta + (dif_volta * 0.60)
            else:
                precos_volta = None; min_volta = barato_volta = medio_volta = 0

            meses_ida = df_ida['Data Formatada'].dropna().dt.to_period('M').unique() if not df_ida.empty else []
            meses_volta = df_volta['Data Formatada'].dropna().dt.to_period('M').unique() if not df_volta.empty else []
            todos_meses = sorted(list(set(meses_ida).union(set(meses_volta))))
            meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
            
            for mes_ano in todos_meses:
                ano = mes_ano.year; mes = mes_ano.month
                
                with col_ida:
                    st.markdown(f"#### {meses_pt[mes]} {ano}")
                    html_ida = gerar_html_calendario(ano, mes, precos_ida, min_ida, barato_ida, medio_ida, tooltips_ida, modo_exibicao, valor_milheiro)
                    st.markdown(html_ida, unsafe_allow_html=True)
                    
                with col_volta:
                    st.markdown(f"#### {meses_pt[mes]} {ano}")
                    html_volta = gerar_html_calendario(ano, mes, precos_volta, min_volta, barato_volta, medio_volta, tooltips_volta, modo_exibicao, valor_milheiro)
                    st.markdown(html_volta, unsafe_allow_html=True)
                
                st.markdown("<hr style='margin: 10px 0; opacity: 0.2;'>", unsafe_allow_html=True)
                
            # --- SECÇÃO DE INSPEÇÃO DETALHADA ---
            st.markdown("---")
            st.subheader("🔍 Inspeção Diária de Horários")
            
            col_detalhe_ida, col_detalhe_volta = st.columns(2)
            
            with col_detalhe_ida:
                datas_ida_lista = [d.strftime('%d/%m/%Y') for d in sorted(df_ida['Data Formatada'].dropna().unique())] if not df_ida.empty else []
                if datas_ida_lista:
                    dia_ida = st.selectbox("Detalhar dia de Ida:", ["Selecione..."] + datas_ida_lista)
                    if dia_ida != "Selecione...":
                        df_filtro = df_ida[df_ida['Data Formatada'] == pd.to_datetime(dia_ida, format='%d/%m/%Y')].sort_values('Preco_Num', na_position='last')
                        st.dataframe(formatar_tabela_exibicao(df_filtro, col_preco, modo_exibicao, valor_milheiro), hide_index=True)
                        
            with col_detalhe_volta:
                datas_volta_lista = [d.strftime('%d/%m/%Y') for d in sorted(df_volta['Data Formatada'].dropna().unique())] if not df_volta.empty else []
                if datas_volta_lista:
                    dia_volta = st.selectbox("Detalhar dia de Volta:", ["Selecione..."] + datas_volta_lista)
                    if dia_volta != "Selecione...":
                        df_filtro = df_volta[df_volta['Data Formatada'] == pd.to_datetime(dia_volta, format='%d/%m/%Y')].sort_values('Preco_Num', na_position='last')
                        st.dataframe(formatar_tabela_exibicao(df_filtro, col_preco, modo_exibicao, valor_milheiro), hide_index=True)

        else:
            st.info("Nenhuma data encontrada para esta rota.")
    else:
        st.error("Colunas essenciais não encontradas. O site não conseguiu ler o Excel.")
