import streamlit as st
import requests
import os
import io
from PIL import Image
import base64

# --- Configuração da Página ---
st.set_page_config(page_title="Gerador de ImAnIgense", layout="centered")

st.title("🤖 Gerador de Imagens AI")
st.markdown("Descreva a imagem que você gostaria de criar e clique em 'Gerar'.")

# --- Chave da API ---
# Pega a chave de API das variáveis de ambiente
# É mais seguro do que colocar a chave diretamente no código
API_KEY = os.environ.get("GOOGLE_API_KEY")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={API_KEY}"

# --- Funções da API ---

def generate_image(prompt_text):
    """
    Chama a API do Google para gerar uma imagem com base no prompt.
    """
    payload = {
        "instances": [{"prompt": prompt_text}],
        "parameters": {"sampleCount": 1}
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()  # Lança um erro se a requisição falhar (status != 200)
        
        result = response.json()
        
        if "predictions" in result and len(result["predictions"]) > 0:
            base64_data = result["predictions"][0].get("bytesBase64Encoded")
            if base64_data:
                # Decodifica a imagem
                image_data = base64.b64decode(base64_data)
                image = Image.open(io.BytesIO(image_data))
                return image
            else:
                return "Não foi possível extrair a imagem da resposta."
        else:
            return f"Resposta inesperada da API: {result}"
            
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao chamar a API: {e}")
        if e.response:
            try:
                st.error(f"Detalhes: {e.response.json()}")
            except:
                st.error(f"Detalhes: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Um erro inesperado ocorreu: {e}")
        return None

# --- Interface do Usuário (UI) ---

if not API_KEY:
    st.error("Chave de API (GOOGLE_API_KEY) não encontrada nas variáveis de ambiente.")
    st.info("Por favor, defina a variável de ambiente GOOGLE_API_KEY para usar este app.")
else:
    # Campo de texto para o prompt
    prompt = st.text_area("Seu prompt:", height=100, placeholder="Um gato astronauta azul flutuando no espaço...")

    # Botão para gerar
    if st.button("Gerar Imagem", type="primary"):
        if prompt:
            # Mostra um spinner enquanto gera
            with st.spinner("Mágica da IA em progresso... 🎨"):
                image_or_error = generate_image(prompt)
                
                if isinstance(image_or_error, Image.Image):
                    st.image(image_or_error, caption="Sua imagem gerada!", use_column_width=True)
                elif isinstance(image_or_error, str):
                    st.error(image_or_error) # Mostra mensagem de erro
        else:
            st.warning("Por favor, digite uma descrição para gerar a imagem.")

st.caption("Criado com Streamlit e a API do Google.")