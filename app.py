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
    page_title="Pokémon TCG Scanner & Price",
    page_icon="🎴",
    layout="centered"
)

st.title("🎴 Pokémon TCG Card Scanner")
st.caption("Aponte a câmera para o nome e o número da carta no canto inferior (ex: 083/142).")

# ---------------------------------------------------------
# Inicialização do Leitor OCR (Cache para otimizar carregamento)
# ---------------------------------------------------------
@st.cache_resource
def load_ocr_reader():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr_reader()

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
        st.error(f"Erro ao consultar API da TCGdex: {e}")
        return None
    return None

# ---------------------------------------------------------
# Modos de Captura & Botões de Lanterna
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["📷 Câmera do Celular", "📂 Upload de Imagem"])

img_file = None

with tab1:
    st.write("### Captura com Lanterna")
    
    # HTML/JS Customizado para controle da Lanterna do Celular (Torch API)
    torch_js_code = """
    <div style="background:#1e293b; padding:12px; border-radius:10px; text-align:center; color:white; margin-bottom: 10px;">
        <p style="margin-bottom:8px; font-weight:bold; font-size:14px;">⚡ Controle de Iluminação / Lanterna</p>
        <button id="btn-torch-on" style="background-color:#22c55e; color:white; border:none; padding:8px 14px; font-size:13px; border-radius:6px; margin-right:6px; cursor:pointer;">💡 Ligar Lanterna</button>
        <button id="btn-torch-off" style="background-color:#ef4444; color:white; border:none; padding:8px 14px; font-size:13px; border-radius:6px; cursor:pointer;">🔌 Desligar</button>
        <p id="torch-status" style="margin-top:6px; font-size:11px; color:#94a3b8;"></p>
    </div>

    <script>
    let track = null;

    async function toggleTorch(turnOn) {
        const statusEl = document.getElementById('torch-status');
        try {
            if (!track) {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: { exact: "environment" } }
                }).catch(() => navigator.mediaDevices.getUserMedia({ video: true }));
                
                track = stream.getVideoTracks()[0];
            }

            const capabilities = track.getCapabilities ? track.getCapabilities() : {};
            if (!capabilities.torch) {
                statusEl.innerText = "Aviso: Lanterna não suportada por esta câmera/navegador.";
                return;
            }

            await track.applyConstraints({
                advanced: [{ torch: turnOn }]
            });

            statusEl.innerText = turnOn ? "Lanterna Ligada!" : "Lanterna Desligada.";
        } catch (err) {
            statusEl.innerText = "Erro ao acessar lanterna: " + err.message;
        }
    }

    document.getElementById('btn-torch-on').addEventListener('click', () => toggleTorch(true));
    document.getElementById('btn-torch-off').addEventListener('click', () => toggleTorch(false));
    </script>
    """
    st.components.v1.html(torch_js_code, height=120)

    camera_img = st.camera_input("Tire uma foto clara da carta")
    if camera_img is not None:
        img_file = camera_img

with tab2:
    st.write("### Upload de Imagem")
    uploaded_file = st.file_uploader("Escolha a foto da carta no celular", type=["jpg", "jpeg", "png"])
    if uploaded_file is not None:
        img_file = uploaded_file

# ---------------------------------------------------------
# Processamento de Imagem & Exibição de Resultados
# ---------------------------------------------------------
if img_file is not None:
    image = Image.open(img_file)
    # Correção do Erro: Ajustado para use_container_width=True
    st.image(image, caption="Imagem Selecionada", use_container_width=True)

    with st.spinner("Analisando texto e número da carta com EasyOCR..."):
        img_np = np.array(image)
        if len(img_np.shape) == 2:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        elif img_np.shape[2] == 4:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)

        results = reader.readtext(img_np)
        full_text = " ".join([res[1] for res in results])
        
        st.write("**Texto Lido:**", f"`{full_text}`" if full_text else "Nenhum texto identificado.")

        match = re.search(r'(\d{1,3})\s*[\/\\]\s*(\d{1,3})', full_text)
        
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

    if card_num:
        with st.spinner("Consultando cotação na API TCGdex..."):
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
                        st.info("Cotação não disponível para este card.")
            else:
                st.error("Carta não localizada na base de dados com o número extraído.")
    else:
        st.info("💡 **Dica:** Aproxime a foto do canto inferior da carta (ex: 083/142 no Mienfoo da foto).")
