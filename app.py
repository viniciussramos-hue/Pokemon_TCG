import re
import requests
import numpy as np
import cv2
import pytesseract
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
# Otimização de Imagem
# ---------------------------------------------------------
def preprocess_for_ocr(image: Image.Image, max_size: int = 800):
    """Redimensiona e aplica filtros leves para facilitar a leitura do Tesseract sem consumir RAM."""
    img = image.copy()
    img.thumbnail((max_size, max_size))
    
    # Converter para OpenCV
    img_np = np.array(img)
    if len(img_np.shape) == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np
        
    # Aumentar contraste levemente
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return gray, img

# ---------------------------------------------------------
# Função de Consulta à API TCGdex
# ---------------------------------------------------------
def fetch_card_price(card_number: str):
    """Busca o preço da carta na API da TCGdex com base no número local."""
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
    camera_img = st.camera_input("Tire uma foto clara do número no canto da carta")
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
        processed_gray, display_img = preprocess_for_ocr(raw_image, max_size=800)
        
        st.image(display_img, caption="Imagem Carregada", use_container_width=True)

        with st.spinner("Lendo número da carta com Tesseract..."):
            # Executa OCR no canal em escala de cinza otimizado
            full_text = pytesseract.image_to_string(processed_gray, config='--psm 6')
            
            st.write("**Texto Detectado:**", f"`{full_text.strip()}`" if full_text.strip() else "Nenhum texto identificado.")

            # Regex para buscar padrões como 083/142, 151/197, 83/142
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
                    st.warning(f"Número identificado (aproximado): **{card_num}**")

        # ---------------------------------------------------------
        # Busca de Cotação
        # ---------------------------------------------------------
        if card_num:
            with st.spinner("Buscando valores na TCGdex..."):
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
                            st.info("Imagem oficial indisponível.")

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
                    st.error("Carta não localizada na base TCGdex.")
        else:
            st.info("💡 **Dica:** Tire a foto bem focada no canto inferior da carta para ler os números claramente.")

    except Exception as err:
        st.error(f"Ocorreu um erro no processamento: {err}")
