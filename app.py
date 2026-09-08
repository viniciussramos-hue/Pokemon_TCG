import re
import requests
import numpy as np
import cv2
import easyocr
import streamlit as st
from PIL import Image

# ---------------------------------------------------------
# Configuração da Página
# ---------------------------------------------------------
st.set_page_config(
    page_title="Pokémon TCG Scanner",
    page_icon="🎴",
    layout="centered"
)

st.title("🎴 Pokémon TCG Card Scanner")
st.caption("Aponte a câmera para o número da carta no canto inferior (ex: 083/142).")

# ---------------------------------------------------------
# Inicialização do Leitor OCR com Caching
# ---------------------------------------------------------
@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr_reader()

# ---------------------------------------------------------
# Otimização de Imagem para Evitar Estouro de RAM
# ---------------------------------------------------------
def preprocess_image(image: Image.Image, max_size: int = 800):
    """Redimensiona a imagem mantendo a proporção para economizar memória RAM."""
    img = image.copy()
    img.thumbnail((max_size, max_size))
    return img

# ---------------------------------------------------------
# Função de Consulta à API TCGdex
# ---------------------------------------------------------
def fetch_card_price(card_number: str):
    """Busca o preço da carta na API da TCGdex com base no número."""
    try:
        url = f"https://api.tcgdex.net/v2/en/cards?localId={card_number.strip()}"
        response = requests.get(url, timeout=6)
        if response.status_code != 200:
            return None

        data = response.json()
        if not data:
            return None

        matching_card = None
        for item in data:
            if str(item.get("localId", "")).strip() == str(card_number).strip():
                matching_card = item
                break

        if not matching_card:
            matching_card = data[0]

        card_id = matching_card.get("id")
        detail_res = requests.get(f"https://api.tcgdex.net/v2/en/cards/{card_id}", timeout=6)
        
        if detail_res.status_code == 200:
            return detail_res.json()

    except Exception as e:
        st.error(f"Erro ao consultar API: {e}")
        return None
    return None

# ---------------------------------------------------------
# Modos de Captura
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📷 Câmera do Celular", "📂 Upload de Imagem"])

img_file = None

with tab1:
    camera_img = st.camera_input("Tire uma foto clara do canto inferior da carta")
    if camera_img is not None:
        img_file = camera_img

with tab2:
    uploaded_file = st.file_uploader("Escolha a foto no celular", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        img_file = uploaded_file

# ---------------------------------------------------------
# Processamento de Imagem
# ---------------------------------------------------------
if img_file is not None:
    try:
        raw_image = Image.open(img_file)
        
        # 1. Redimensiona a foto para economizar memória
        optimized_image = preprocess_image(raw_image, max_size=800)
        
        st.image(optimized_image, caption="Imagem Processada", use_container_width=True)

        with st.spinner("Analisando número da carta..."):
            # 2. Converte para NumPy Array e ajusta canais de cor
            img_np = np.array(optimized_image)
            if len(img_np.shape) == 2:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
            elif img_np.shape[2] == 4:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)

            # 3. Executa OCR na imagem redimensionada
            results = reader.readtext(img_np)
            full_text = " ".join([res[1] for res in results])
            
            st.write("**Texto Lido:**", f"`{full_text}`" if full_text else "Nenhum texto identificado.")

            # Busca padrão tipo 083/142, 151/197, etc.
            match = re.search(r'(\d{1,3})\s*[/VR\\]\s*(\d{1,3})', full_text, re.IGNORECASE)
            
            card_num = None
            if match:
                card_num = match.group(1)
                total_set = match.group(2)
                st.success(f"Número da Carta Identificado: **{card_num}/{total_set}**")
            else:
                digit_matches = re.findall(r'\b\d{1,3}\b', full_text)
                if digit_matches:
                    card_num = digit_matches[0]
                    st.warning(f"Número identificado (simplificado): **{card_num}**")

        # ---------------------------------------------------------
        # Busca de Cotação
        # ---------------------------------------------------------
        if card_num:
            with st.spinner("Consultando cotação de mercado..."):
                card_data = fetch_card_price(card_number=card_num)

                if card_data:
                    st.markdown("---")
                    st.subheader(f"🃏 {card_data.get('name', 'Carta Pokémon')}")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        card_image_url = card_data.get("image")
                        if card_image_url:
                            st.image(f"{card_image_url}/high.webp", use_container_width=True)
                        else:
                            st.info("Imagem oficial não disponível.")

                    with col2:
                        st.write(f"**Coleção:** {card_data.get('set', {}).get('name', 'N/A')}")
                        st.write(f"**Raridade:** {card_data.get('rarity', 'N/A')}")
                        st.write(f"**Número:** {card_data.get('localId', 'N/A')}")

                        tcg_prices = card_data.get("pricing", {}).get("tcgplayer", {})
                        cardmarket_prices = card_data.get("pricing", {}).get("cardmarket", {})

                        st.markdown("#### 💲 Preços de Mercado")

                        if tcg_prices:
                            st.write("**TCGPlayer (USD):**")
                            if "normal" in tcg_prices:
                                st.write(f"• Normal: **${tcg_prices['normal'].get('marketPrice', 'N/A')}**")
                            if "holofoil" in tcg_prices:
                                st.write(f"• Holo: **${tcg_prices['holofoil'].get('marketPrice', 'N/A')}**")
                            if "reverseHolofoil" in tcg_prices:
                                st.write(f"• Reverse Holo: **${tcg_prices['reverseHolofoil'].get('marketPrice', 'N/A')}**")
                        elif cardmarket_prices:
                            st.write("**Cardmarket (EUR):**")
                            st.write(f"• Média: **€{cardmarket_prices.get('avg', 'N/A')}**")
                            st.write(f"• Mínimo: **€{cardmarket_prices.get('low', 'N/A')}**")
                        else:
                            st.info("Cotação em tempo real não disponível para esta carta.")
                else:
                    st.error("Não foi possível encontrar a carta na base TCGdex com o número lido.")
        else:
            st.info("💡 **Dica:** Aproxime a foto do canto inferior da carta para focar nos números.")

    except Exception as err:
        st.error(f"Erro ao processar a imagem: {err}")
