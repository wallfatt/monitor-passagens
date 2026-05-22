import streamlit as st
import base64
import requests
from io import BytesIO

# --- CÓDIGO PARA O NOVO TÍTULO COM IMAGEM E LINK ---

# 1. Configurações solicitadas
# Texto solicitado verbatim: "@Casadldaspassagens" (conforme solicitado)
TEXTO_EXIBIDO = "@Casadldaspassagens" 
LINK_INSTAGRAM = "https://www.instagram.com/casaldaspassagens_?igsh=MThxZTl2NHVwbTl2ZQ%3D%3D"

# Link do Google Drive convertido para download direto da imagem
URL_FOTO_PERFIL = "https://drive.google.com/uc?export=download&id=1a_NhrKaI4PLBedx1T6gxHzq4eF57n2ke"

# 2. Função para carregar a imagem e converter para Base64 (necessário para exibição no HTML do Streamlit)
@st.cache_data # Cache para evitar carregar a imagem a cada reload
def obter_imagem_base64_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status() # Verifica se o download funcionou
        img_bytes = BytesIO(response.content)
        encoded_string = base64.b64encode(img_bytes.read()).decode()
        return encoded_string
    except Exception as e:
        st.error(f"Erro ao carregar imagem do perfil: {e}")
        return None

# Carrega a imagem
img_base64 = obter_imagem_base64_url(URL_FOTO_PERFIL)

if img_base64:
    # 3. HTML e CSS para alinhar a imagem e o texto (verbatim solicitado)
    # display: flex alinha os itens na horizontal
    # align-items: center alinha verticalmente
    # gap: 15px dá o espaçamento entre a foto e o texto
    # text-decoration: none remove o sublinhado do link
    
    html_titulo = f"""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="data:image/jpeg;base64,{img_base64}" 
             style="border-radius: 50%; width: 50px; height: 50px; object-fit: cover;">
        <a href="{LINK_INSTAGRAM}" target="_blank" 
           style="text-decoration: none; color: inherit; font-size: 2.5em; font-weight: bold;">
           {TEXTO_EXIBIDO}
        </a>
    </div>
    """
    # Exibe o título customizado
    st.markdown(html_titulo, unsafe_allow_html=True)
else:
    # Fallback caso a imagem falhe (verbatim solicitado)
    st.markdown(f"#[{TEXTO_EXIBIDO}]({LINK_INSTAGRAM})", unsafe_allow_html=True)

# --------------------------------------------------

# Continue com o restante do seu código abaixo...
