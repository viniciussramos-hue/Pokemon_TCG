import re
import requests
import numpy as np
import cv2
import easyocr
import streamlit as st
from PIL import Image
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

# ---------------------------------------------------------
# Configuração da Página
# ---------------------------------------------------------
st.set_page_config(
    page_title="Pokémon TCG Price Scanner",
    page_icon="🎴",
    layout="centered"
)

st.title("🎴 Pokémon TCG Card Scanner")
st.caption("Aponte a câmera para o nome e o número da carta no canto inferior.")

# Configuração de suporte a câmeras em dispositivos móveis (WebRTC ICE servers público)
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# ---------------------------------------------------------
# Inicialização do Leitor OCR (Caching para carregar rápido)
# ---------------------------------------------------------
@st.cache_resource
def load_ocr_reader():
    # Inicializa EasyOCR para o idioma inglês
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr_reader()

# ---------------------------------------------------------
# Função de Consulta à API TCGdex
# ---------------------------------------------------------
def fetch_card_price(card_number: str, card_name: str = ""):
    """Busca o preço da carta na API da TCGdex com base no número ou nome."""
    try:
        # Se temos nome, pesquisamos por nome
        if card_name:
            url = f"https://api.tcgdex.net/v2/en/cards?name={card_name.strip()}"
        else:
            # Caso contrário, busca direto pelo ID da coleção
            url = f"https://api.tcgdex.net/v2/en/cards?localId={card_number.strip()}"

        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None

        data = response.json()
        if not data:
            return None

        # Procura o item que contenha exatamente o número da carta
        matching_card = None
        for item in data:
            if str(item.get("localId", "")).strip() == str(card_number).strip():
                matching_card = item
                break

        if not matching_card:
            matching_card = data[0]

        # Busca detalhes completos (incluindo preço) usando o ID retornado
        card_id = matching_card.get("id")
        detail_res = requests.get(f"https://api.tcgdex.net/v2/en/cards/{card_id}", timeout=5)
        
        if detail_res.status_code == 200:
            return detail_res.json()

    except Exception as e:
        st.error(f"Erro ao consultar API: {e}")
        return None
    return None

# ---------------------------------------------------------
# Interface do Usuário - Modos de Leitura
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📷 Câmera ao Vivo / Foto", "📂 Upload de Imagem"])

img_file = None

with tab1:
    st.write("### Capturar com a Câmera")
    camera_img = st.camera_input("Tire uma foto clara do canto inferior da carta")
    if camera_img is not None:
        img_file = camera_img

with tab2:
    st.write("### Selecionar Imagem do Celular")
    uploaded_file = st.file_uploader("Escolha a imagem da carta", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        img_file = uploaded_file

# ---------------------------------------------------------
# Processamento de Imagem e Exibição de Resultados
# ---------------------------------------------------------
if img_file is not None:
    image = Image.open(img_file)
    st.image(image, caption="Imagem Carregada", use_column_width=True)

    with st.spinner("Processando texto com EasyOCR..."):
        # Converter Imagem PIL para Array OpenCV
        img_np = np.array(image)
        if len(img_np.shape) == 2:  # Grayscale
            img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        elif img_np.shape[2] == 4:  # RGBA
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)

        # Rodar OCR na imagem
        results = reader.readtext(img_np)
        
        full_text = " ".join([res[1] for res in results])
        st.write("**Texto Detectado pelo OCR:**", full_text if full_text else "Nenhum texto claro identificado.")

        # Expressão Regular para encontrar o número da carta (ex: 004/102, 151/197, 25/102)
        match = re.search(r'(\d{1,3})\s*[\/\\]\s*(\d{1,3})', full_text)
        
        card_num = None
        if match:
            card_num = match.group(1)
            st.success(f"Número da Carta Encontrado: **{card_num}/{match.group(2)}**")
        else:
            # Fallback: tentar encontrar isoladamente qualquer padrão de 1 a 3 dígitos se não achar com barra
            digit_matches = re.findall(r'\b\d{1,3}\b', full_text)
            if digit_matches:
                card_num = digit_matches[0]
                st.warning(f"Não encontramos o formato XXX/XXX, mas tentaremos buscar com o número isolado: **{card_num}**")

    # Realizar Busca na API TCGdex
    if card_num:
        with st.spinner("Buscando cotações na API da TCGdex..."):
            card_data = fetch_card_price(card_number=card_num)

            if card_data:
                st.markdown("---")
                st.subheader(f"🃏 {card_data.get('name', 'Nome desconhecido')}")
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    card_image_url = card_data.get("image")
                    if card_image_url:
                        st.image(f"{card_image_url}/high.webp", use_column_width=True)
                    else:
                        st.info("Imagem oficial indisponível na API.")

                with col2:
                    st.write(f"**Coleção:** {card_data.get('set', {}).get('name', 'N/A')}")
                    st.write(f"**Raridade:** {card_data.get('rarity', 'N/A')}")
                    st.write(f"**Número Local:** {card_data.get('localId', 'N/A')}")

                    # Extração dos Preços de Mercado
                    tcg_prices = card_data.get("pricing", {}).get("tcgplayer", {})
                    cardmarket_prices = card_data.get("pricing", {}).get("cardmarket", {})

                    st.markdown("#### 💲 Preços de Mercado")

                    if tcg_prices:
                        st.write("**TCGPlayer (USD):**")
                        if "normal" in tcg_prices:
                            st.write(f"• Normal: **${tcg_prices['normal'].get('marketPrice', 'N/A')}**")
                        if "holofoil" in tcg_prices:
                            st.write(f"• Holofoil: **${tcg_prices['holofoil'].get('marketPrice', 'N/A')}**")
                        if "reverseHolofoil" in tcg_prices:
                            st.write(f"• Reverse Holo: **${tcg_prices['reverseHolofoil'].get('marketPrice', 'N/A')}**")
                    
                    elif cardmarket_prices:
                        st.write("**Cardmarket (EUR):**")
                        st.write(f"• Média: **€{cardmarket_prices.get('avg', 'N/A')}**")
                        st.write(f"• Mínimo: **€{cardmarket_prices.get('low', 'N/A')}**")
                    else:
                        st.info("Sem dados de preço atualizados para esta carta específica.")
            else:
                st.error("Carta não localizada na base de dados da TCGdex com os números extraídos.")
    else:
        st.info("💡 **Dica:** Tente tirar a foto focando no canto inferior esquerdo/direito da carta, onde ficam o nome e o número de coleção.")
