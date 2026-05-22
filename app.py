import streamlit as st
import pandas as pd
import os
import calendar

# 1. Configuração da página
st.set_page_config(page_title="Calendário Azul", layout="wide")
st.title("📅 Calendário de Passagens - Azul")

caminho_csv = "https://drive.google.com/file/d/1VFLoXan_R9NgwPrk_Qw5VZg1wrdtMraI"

# --- DIAGNÓSTICO EM TEMPO REAL NA BARRA LATERAL ---
st.sidebar.header("⚙️ Status do Arquivo")
if os.path.exists(caminho_csv):
    st.sidebar.success("✅ Arquivo carregado com sucesso!")
else:
    st.sidebar.error("❌ Arquivo NÃO encontrado.")
    st.sidebar.info(f"Caminho:\n{caminho_csv}")

# --- CSS DO CALENDÁRIO ---
st.markdown("""
<style>
    .cal-container { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; margin-bottom: 30px; }
    .cal-header { text-align: center; font-weight: bold; padding: 5px; color: #555; }
    .cal-day { padding: 15px 5px; border-radius: 8px; text-align: center; border: 1px solid #e0e0e0; display: flex; flex-direction: column; justify-content: center; min-height: 80px;}
    .cal-date { font-weight: bold; font-size: 1.1em; margin-bottom: 5px; }
    .cal-price { font-size: 0.9em; font-weight: 600;}
    .best-price { background-color: #28a745; color: white; border-color: #28a745; box-shadow: 0 4px 6px rgba(40,167,69,0.3);}
    .cheap { background-color: #d4edda; color: #155724; border-color: #c3e6cb; }
    .medium { background-color: #fff3cd; color: #856404; border-color: #ffeeba; }
    .expensive { background-color: #f8d7da; color: #721c24; border-color: #f5c6cb; }
    .empty { background-color: #f8f9fa; color: #adb5bd; }
    .blank { background: transparent; border: none; }
</style>
""", unsafe_allow_html=True)

# Nova função de matemática (Multiplica por 1000 para corrigir a formatação do Excel)
def limpar_preco(preco_val):
    if pd.isna(preco_val):
        return None
    preco_str = str(preco_val).strip()
    
    # "Ind" captura a palavra Indisponível mesmo que o Excel tenha bugado o acento
    if "Ind" in preco_str or "Não" in preco_str:
        return None
    try:
        # Pega "35.2" e transforma matematicamente em 35200
        preco_float = float(preco_str.replace(',', '.'))
        return int(preco_float * 1000)
    except:
        return None

@st.cache_data(ttl=30)
def carregar_dados():
    if not os.path.exists(caminho_csv):
        return None
    try:
        # Mudamos o separador para VÍRGULA, conforme a nova planilha
        df = pd.read_csv(caminho_csv, sep=',', encoding='utf-8', on_bad_lines='skip')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao ler o CSV: {e}")
        return None

df_bruto = carregar_dados()

if df_bruto is not None:
    # Procura a coluna de preço automaticamente (para ignorar o erro do "PreÃ§o")
    col_data = "Data Voo" if "Data Voo" in df_bruto.columns else None
    col_preco = [c for c in df_bruto.columns if "Pre" in c]
    col_preco = col_preco[0] if len(col_preco) > 0 else None
    
    if col_data and col_preco and "Origem" in df_bruto.columns and "Destino" in df_bruto.columns:
        
        df_processado = df_bruto.copy()
        df_processado['Data Formatada'] = pd.to_datetime(df_processado[col_data], format='%d/%m/%Y', errors='coerce')
        df_processado['Preco_Num'] = df_processado[col_preco].apply(limpar_preco)
        
        st.sidebar.header("🔎 Filtrar Rota")
        origens = sorted(df_processado["Origem"].dropna().unique())
        origem_sel = st.sidebar.selectbox("Origem:", origens)
        
        destinos = sorted(df_processado[df_processado["Origem"] == origem_sel]["Destino"].dropna().unique())
        destino_sel = st.sidebar.selectbox("Destino:", destinos)
        
        df_rota = df_processado[(df_processado["Origem"] == origem_sel) & (df_processado["Destino"] == destino_sel)].copy()
        
        if not df_rota.empty:
            st.subheader(f"Visão Mensal: {origem_sel} ➔ {destino_sel}")
            
            precos_diarios = df_rota.groupby('Data Formatada')['Preco_Num'].min()
            
            if precos_diarios.notna().any():
                preco_min_absoluto = precos_diarios.min()
                preco_max = precos_diarios.max()
                diferenca = preco_max - preco_min_absoluto
                limite_barato = preco_min_absoluto + (diferenca * 0.25)
                limite_medio = preco_min_absoluto + (diferenca * 0.60)
            else:
                preco_min_absoluto = limite_barato = limite_medio = 0

            meses_pt = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
            meses_presentes = df_rota['Data Formatada'].dropna().dt.to_period('M').unique()
            
            for mes_ano in sorted(meses_presentes):
                ano = mes_ano.year
                mes = mes_ano.month
                st.markdown(f"### {meses_pt[mes]} {ano}")
                
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
                            if data_atual in precos_diarios.index and pd.notna(precos_diarios[data_atual]):
                                preco = precos_diarios[data_atual]
                                preco_exibicao = f"{int(preco):,} Pts".replace(",", ".")
                                
                                if preco == preco_min_absoluto:
                                    css_class = "best-price"
                                elif preco <= limite_barato:
                                    css_class = "cheap"
                                elif preco <= limite_medio:
                                    css_class = "medium"
                                else:
                                    css_class = "expensive"
                                    
                                html_cal += f'<div class="cal-day {css_class}"><div class="cal-date">{dia}</div><div class="cal-price">{preco_exibicao}</div></div>'
                            else:
                                html_cal += f'<div class="cal-day empty"><div class="cal-date">{dia}</div><div class="cal-price">-</div></div>'
                                
                html_cal += '</div>'
                st.markdown(html_cal, unsafe_allow_html=True)
                
            st.markdown("---")
            st.subheader("📋 Lista Detalhada dos Voos Encontrados")
            # Substitui a coluna "bugada" do Excel por um nome bonito na exibição da tabela
            df_exibicao = df_rota.drop(columns=['Data Formatada', 'Preco_Num']).rename(columns={col_preco: "Pontos (Mil)"})
            st.dataframe(df_exibicao, use_container_width=True)
        else:
            st.info("Nenhuma data encontrada para esta rota.")
    else:
        st.error("Colunas essenciais não encontradas. O site não conseguiu ler o Excel.")
        st.write("Colunas detetadas:", df_bruto.columns.tolist())