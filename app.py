import streamlit as st
import pandas as pd
import calendar

# 1. Configuração da página (Uso total da tela)
st.set_page_config(page_title="Radar Azul - Ida e Volta", layout="wide")
st.title("✈️ Radar de Passagens - Ida e Volta")

# Link do Google Drive convertido para modo de leitura direta
caminho_csv = "https://drive.google.com/uc?export=download&id=1VFLoXan_R9NgwPrk_Qw5VZg1wrdtMraI"

st.sidebar.header("⚙️ Status do Arquivo")
st.sidebar.info("🌐 Lendo dados da nuvem...")

# --- CSS DO CALENDÁRIO COMPACTO ---
# Reduzimos paddings, fontes e alturas para caberem lado a lado perfeitamente
st.markdown("""
<style>
    .cal-container { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin-bottom: 20px; }
    .cal-header { text-align: center; font-weight: bold; padding: 2px; color: #555; font-size: 0.85em; }
    .cal-day { padding: 5px 2px; border-radius: 4px; text-align: center; border: 1px solid #e0e0e0; display: flex; flex-direction: column; justify-content: center; min-height: 55px;}
    .cal-date { font-weight: bold; font-size: 0.9em; margin-bottom: 2px; color: #333;}
    .cal-price { font-size: 0.75em; font-weight: 700; line-height: 1.1;}
    .best-price { background-color: #28a745; color: white; border-color: #28a745; box-shadow: 0 2px 4px rgba(40,167,69,0.3);}
    .cheap { background-color: #d4edda; color: #155724; border-color: #c3e6cb; }
    .medium { background-color: #fff3cd; color: #856404; border-color: #ffeeba; }
    .expensive { background-color: #f8d7da; color: #721c24; border-color: #f5c6cb; }
    .empty { background-color: #f8f9fa; color: #adb5bd; }
    .blank { background: transparent; border: none; }
</style>
""", unsafe_allow_html=True)

def limpar_preco(preco_val):
    if pd.isna(preco_val):
        return None
    preco_str = str(preco_val).strip()
    if "Ind" in preco_str or "Não" in preco_str:
        return None
    try:
        preco_float = float(preco_str.replace(',', '.'))
        return int(preco_float * 1000)
    except:
        return None

@st.cache_data(ttl=30)
def carregar_dados():
    try:
        df = pd.read_csv(caminho_csv, sep=',', encoding='utf-8', on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao ler o CSV da nuvem: {e}")
        return None

# Função auxiliar para gerar o HTML do calendário (evita repetição de código)
def gerar_html_calendario(ano, mes, precos_diarios, min_abs, lim_barato, lim_medio):
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
                if precos_diarios is not None and data_atual in precos_diarios.index and pd.notna(precos_diarios[data_atual]):
                    preco = precos_diarios[data_atual]
                    preco_exibicao = f"{int(preco):,} Pts".replace(",", ".")
                    
                    if preco == min_abs: css_class = "best-price"
                    elif preco <= lim_barato: css_class = "cheap"
                    elif preco <= lim_medio: css_class = "medium"
                    else: css_class = "expensive"
                        
                    html_cal += f'<div class="cal-day {css_class}"><div class="cal-date">{dia}</div><div class="cal-price">{preco_exibicao}</div></div>'
                else:
                    html_cal += f'<div class="cal-day empty"><div class="cal-date">{dia}</div><div class="cal-price">-</div></div>'
    html_cal += '</div>'
    return html_cal

df_bruto = carregar_dados()

if df_bruto is not None:
    col_data = "Data Voo" if "Data Voo" in df_bruto.columns else None
    col_preco = [c for c in df_bruto.columns if "Pre" in c]
    col_preco = col_preco[0] if len(col_preco) > 0 else None
    
    if col_data and col_preco and "Origem" in df_bruto.columns and "Destino" in df_bruto.columns:
        
        df_processado = df_bruto.copy()
        df_processado['Data Formatada'] = pd.to_datetime(df_processado[col_data], format='%d/%m/%Y', errors='coerce')
        df_processado['Preco_Num'] = df_processado[col_preco].apply(limpar_preco)
        
        st.sidebar.header("🔎 Selecione a Ida")
        st.sidebar.write("*(A volta será calculada automaticamente)*")
        origens = sorted(df_processado["Origem"].dropna().unique())
        origem_sel = st.sidebar.selectbox("Origem (Ida):", origens)
        
        destinos = sorted(df_processado[df_processado["Origem"] == origem_sel]["Destino"].dropna().unique())
        destino_sel = st.sidebar.selectbox("Destino (Ida):", destinos)
        
        # Separa os dados de IDA e VOLTA
        df_ida = df_processado[(df_processado["Origem"] == origem_sel) & (df_processado["Destino"] == destino_sel)].copy()
        df_volta = df_processado[(df_processado["Origem"] == destino_sel) & (df_processado["Destino"] == origem_sel)].copy()
        
        if not df_ida.empty or not df_volta.empty:
            
            # Divide a tela em duas colunas principais
            col_ida, col_volta = st.columns(2)
            
            with col_ida:
                st.subheader(f"🛫 IDA: {origem_sel} ➔ {destino_sel}")
            with col_volta:
                st.subheader(f"🛬 VOLTA: {destino_sel} ➔ {origem_sel}")
            
            # Calcula os limites de cores para a IDA
            if not df_ida.empty:
                precos_ida = df_ida.groupby('Data Formatada')['Preco_Num'].min()
                min_ida = precos_ida.min()
                max_ida = precos_ida.max()
                dif_ida = max_ida - min_ida
                barato_ida = min_ida + (dif_ida * 0.25)
                medio_ida = min_ida + (dif_ida * 0.60)
            else:
                precos_ida = None; min_ida = barato_ida = medio_ida = 0
                
            # Calcula os limites de cores para a VOLTA
            if not df_volta.empty:
                precos_volta = df_volta.groupby('Data Formatada')['Preco_Num'].min()
                min_volta = precos_volta.min()
                max_volta = precos_volta.max()
                dif_volta = max_volta - min_volta
                barato_volta = min_volta + (dif_volta * 0.25)
                medio_volta = min_volta + (dif_volta * 0.60)
            else:
                precos_volta = None; min_volta = barato_volta = medio_volta = 0

            # Descobre todos os meses que precisamos desenhar (juntando ida e volta)
            meses_ida = df_ida['Data Formatada'].dropna().dt.to_period('M').unique() if not df_ida.empty else []
            meses_volta = df_volta['Data Formatada'].dropna().dt.to_period('M').unique() if not df_volta.empty else []
            todos_meses = sorted(list(set(meses_ida).union(set(meses_volta))))
            
            meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
            
            # Renderiza os calendários lado a lado, mês a mês
            for mes_ano in todos_meses:
                ano = mes_ano.year
                mes = mes_ano.month
                
                with col_ida:
                    st.markdown(f"#### {meses_pt[mes]} {ano}")
                    html_ida = gerar_html_calendario(ano, mes, precos_ida, min_ida, barato_ida, medio_ida)
                    st.markdown(html_ida, unsafe_allow_html=True)
                    
                with col_volta:
                    st.markdown(f"#### {meses_pt[mes]} {ano}")
                    html_volta = gerar_html_calendario(ano, mes, precos_volta, min_volta, barato_volta, medio_volta)
                    st.markdown(html_volta, unsafe_allow_html=True)
                
                # Linha divisória suave entre os meses
                st.markdown("<hr style='margin: 10px 0; opacity: 0.2;'>", unsafe_allow_html=True)
                
            st.markdown("---")
            st.subheader("📋 Lista Detalhada dos Voos")
            
            # Exibe tabelas separadas para facilitar a leitura
            tab1, tab2 = st.tabs(["Voos de Ida", "Voos de Volta"])
            with tab1:
                if not df_ida.empty:
                    st.dataframe(df_ida.drop(columns=['Data Formatada', 'Preco_Num']).rename(columns={col_preco: "Pontos (Mil)"}), use_container_width=True)
                else:
                    st.info("Sem dados para a ida.")
            with tab2:
                if not df_volta.empty:
                    st.dataframe(df_volta.drop(columns=['Data Formatada', 'Preco_Num']).rename(columns={col_preco: "Pontos (Mil)"}), use_container_width=True)
                else:
                    st.info("Sem dados para a volta.")
        else:
            st.info("Nenhuma data encontrada para esta rota.")
    else:
        st.error("Colunas essenciais não encontradas. O site não conseguiu ler o Excel.")
