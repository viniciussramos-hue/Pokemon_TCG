import re
import requests
import streamlit as st
from PIL import Image

st.set_page_config(page_title="Pokémon TCG Price", page_icon="🎴", layout="centered")

st.title("🎴 Pokémon TCG Card Search")
st.caption("Consulte valores e detalhes das cartas em tempo real via TCGdex API.")

def fetch_card_price(card_number: str):
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
        st.error(f"Erro na requisição: {e}")
        return None
    return None

tab1, tab2 = st.tabs(["🔢 Buscar por Número", "📷 Upload / Foto da Carta"])

with tab1:
    card_num_input = st.text_input("Número da carta (ex: 083 ou 151):", value="")
    search_btn = st.button("🔍 Buscar Cotação", key="btn_direct")

with tab2:
    uploaded_file = st.file_uploader("Foto para referência visual", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        raw_image = Image.open(uploaded_file)
        raw_image.thumbnail((500, 500))
        st.image(raw_image, caption="Carta Carregada", use_container_width=True)
        
    num_from_photo = st.text_input("Digite o número visto na carta acima:", key="photo_num")
    search_btn_photo = st.button("🔍 Buscar Cotação da Foto", key="btn_photo")

target_card_num = None
if search_btn and card_num_input:
    target_card_num = card_num_input
elif search_btn_photo and num_from_photo:
    target_card_num = num_from_photo

if target_card_num:
    clean_num = re.findall(r'\d+', target_card_num)
    search_id = clean_num[0] if clean_num else target_card_num.strip()

    with st.spinner(f"Consultando cotação para a carta nº {search_id}..."):
        card_data = fetch_card_price(card_number=search_id)

        if card_data:
            st.markdown("---")
            st.subheader(f"🃏 {card_data.get('name', 'Carta Pokémon')}")
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                card_image_url = card_data.get("image")
                if card_image_url:
                    st.image(f"{card_image_url}/high.webp", use_container_width=True)
                else:
                    st.info("Imagem não disponível.")

            with col2:
                st.write(f"**Coleção:** {card_data.get('set', {}).get('name', 'N/A')}")
                st.write(f"**Raridade:** {card_data.get('rarity', 'N/A')}")
                st.write(f"**Número Local:** {card_data.get('localId', 'N/A')}")

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
                    st.info("Cotação em tempo real indisponível para esta carta.")
        else:
            st.error(f"Nenhuma carta encontrada com o número **{search_id}**.")
