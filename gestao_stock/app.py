import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import os
import cv2
#from pyzbar.pyzbar import decode   # comentado porque precisa de libzbar0 no deploy → descomenta só localmente
import pytesseract
from PIL import Image
import io
import numpy as np
import json

# ────────────────────────────────────────────────
#          CONFIGURAÇÕES GLOBAIS
# ────────────────────────────────────────────────

# Caminho do Tesseract → ajustar conforme o teu sistema
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

EMAIL_REMETENTE = "seuemail@gmail.com"
SENHA_APP = "sua-senha-de-app"          # ← Usa senha de aplicativo do Gmail (não a senha normal)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ────────────────────────────────────────────────
#          CONEXÃO E INICIALIZAÇÃO DO BANCO
# ────────────────────────────────────────────────

def get_db_connection():
    conn = sqlite3.connect('stock.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS materiais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT NOT NULL,
        referencia TEXT,
        fornecedor TEXT,
        cliente TEXT,
        gramas REAL,
        metros REAL,
        comprimento REAL,
        peso REAL,
        quantidade INTEGER DEFAULT 0,
        stock_minimo INTEGER DEFAULT 10,
        largura REAL,
        m2 REAL,
        medida TEXT,
        data_atualizacao TEXT,
        foto_path TEXT,
        campos_extra TEXT          -- JSON com campos personalizados
    )
    ''')
    conn.commit()
    conn.close()

init_db()

# ────────────────────────────────────────────────
#          FUNÇÃO DE ENVIO DE EMAIL
# ────────────────────────────────────────────────

def enviar_alerta_email(cliente_email, item, quantidade):
    if not cliente_email:
        return
    msg = MIMEText(f"Alerta: Stock baixo do item {item}!\nQuantidade atual: {quantidade}\nPor favor, verifique.")
    msg['Subject'] = f"Alerta de Stock Baixo - {item}"
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = cliente_email

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_REMETENTE, SENHA_APP)
        server.send_message(msg)
        server.quit()
        st.success(f"Email enviado para {cliente_email}")
    except Exception as e:
        st.error(f"Erro ao enviar email: {e}")

# ────────────────────────────────────────────────
#          INTERFACE PRINCIPAL
# ────────────────────────────────────────────────

st.sidebar.title("Gestão de Stock")
pagina = st.sidebar.radio("Selecione", ["Dashboard", "Adicionar/Editar", "Listar/Remover", "Exportar Excel"])

# Cache dos dados (atualiza a cada 10 segundos)
@st.cache_data(ttl=10)
def carregar_dados():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM materiais", conn)
    conn.close()
    return df

df = carregar_dados()

# Alerta visual de stock baixo (não envia email aqui)
if not df.empty:
    baixos = df[df['quantidade'] <= df['stock_minimo']]
    if not baixos.empty:
        st.warning("Itens com stock baixo!")
        st.dataframe(baixos[['categoria', 'referencia', 'cliente', 'quantidade', 'stock_minimo']])

# ────────────────────────────────────────────────
#          PÁGINAS
# ────────────────────────────────────────────────

if pagina == "Dashboard":
    st.title("Dashboard de Stock")
    if not df.empty:
        st.dataframe(df)
        st.subheader("Resumo por Categoria")
        st.bar_chart(df['categoria'].value_counts())
    else:
        st.info("Ainda não há itens no stock.")

elif pagina == "Adicionar/Editar":
    st.title("Adicionar ou Editar Item")

    metodo = st.radio("Como inserir?", ["Manual", "Foto + OCR","Webcam"])  # Tirei webcam por agora (não funciona no cloud)

    # Variável sempre definida → evita NameError
    uploaded_file = None

    categoria = st.selectbox("Categoria", ["BOBINES", "PALETE", "COLA", "SOBRA", "FILME", "TACOS", "Outra"])
    referencia = st.text_input("Referência")
    fornecedor = st.text_input("Fornecedor") if categoria in ["BOBINES"] else ""
    cliente    = st.text_input("Cliente")    if categoria in ["COLA"]     else ""
    gramas     = st.number_input("Gramas", min_value=0.0, step=0.1)     if categoria in ["BOBINES", "SOBRA"] else 0.0
    metros     = st.number_input("Metros", min_value=0.0, step=1.0)     if categoria in ["BOBINES"] else 0.0
    comprimento= st.number_input("Comprimento", min_value=0.0, step=1.0)if categoria in ["BOBINES"] else 0.0
    peso       = st.number_input("Peso", min_value=0.0, step=0.1)
    quantidade = st.number_input("Quantidade / Stock Atual", min_value=0, step=1, value=1)
    stock_minimo = st.number_input("Stock Mínimo (para alerta)", min_value=1, value=10)
    largura    = st.number_input("Largura", min_value=0.0, step=1.0)    if categoria in ["SOBRA"] else 0.0
    m2         = st.number_input("m²", min_value=0.0, step=1.0)         if categoria in ["SOBRA"] else 0.0
    medida     = st.text_input("Medida (ex: 140/180)")                  if categoria in ["TACOS"] else ""

    if metodo == "Foto + OCR":
        uploaded_file = st.file_uploader("Tire ou envie foto da etiqueta", type=["jpg", "png"])
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption="Foto carregada", use_column_width=True)

            # Pré-processamento OCR
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            texto_ocr = pytesseract.image_to_string(thresh, lang='por+eng')
            st.text_area("Texto detectado (OCR)", texto_ocr, height=150)

            # Tentativa simples de extrair referência
            if "ref" in texto_ocr.lower():
                ref_start = texto_ocr.lower().find("ref") + 3
                ref = texto_ocr[ref_start:ref_start+15].strip()
                referencia = st.text_input("Referência (do OCR)", value=ref)
                
        #elif metodo == "Leitura Código de Barras (Webcam)":
        #st.warning("Esta funcionalidade só funciona quando a app está a correr LOCALMENTE (no computador com câmera).")
        
        #st.write("Aponte a câmera para o código de barras...")
        
        #cap = cv2.VideoCapture(0)
        #frame_placeholder = st.empty()
        #stop_button_pressed = st.button("Parar leitura")

        #while cap.isOpened() and not stop_button_pressed:
            #ret, frame = cap.read()
            #if not ret:
                #st.error("Não foi possível aceder à câmera.")
                #break

            #frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            #frame_placeholder.image(frame_rgb, channels="RGB", use_column_width=True)

            # Decodifica barcode (precisa do import from pyzbar.pyzbar import decode)
            #barcodes = decode(frame)
            #if barcodes:
                #barcode_data = barcodes[0].data.decode('utf-8')
                #st.success(f"Código lido: {barcode_data}")
                #referencia = st.text_input("Referência (do barcode)", value=barcode_data)
                # Opcional: break  # para parar após ler o primeiro código

        cap.release()
        frame_placeholder.empty()
    # Botão de salvar – só executa quando clicado
    if st.button("Salvar Item"):
        conn = get_db_connection()
        c = conn.cursor()
        data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        foto_path = None
        if uploaded_file is not None:
            os.makedirs("imagens", exist_ok=True)
            foto_path = f"imagens/{referencia or 'item'}_{datetime.now().strftime('%Y%m%d_%H%M')}.jpg"
            with open(foto_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

        # Campos extras (se quiseres implementar depois)
        campos_extra_json = json.dumps({})  # por agora vazio – podes expandir depois

        # INSERT no banco
        c.execute('''
            INSERT INTO materiais (
                categoria, referencia, fornecedor, cliente, gramas, metros, comprimento, peso,
                quantidade, stock_minimo, largura, m2, medida, data_atualizacao, foto_path, campos_extra
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            categoria, referencia, fornecedor, cliente, gramas, metros, comprimento, peso,
            quantidade, stock_minimo, largura, m2, medida, data_atual, foto_path, campos_extra_json
        ))

        conn.commit()
        conn.close()

        # Alerta de stock baixo
        if quantidade <= stock_minimo and cliente:
            enviar_alerta_email("cliente@exemplo.com", referencia or categoria, quantidade)

        st.success("Item adicionado com sucesso!")
        st.rerun()

elif pagina == "Listar/Remover":
    st.title("Lista de Itens")
    if not df.empty:
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

        if st.button("Salvar Alterações"):
            conn = get_db_connection()
            edited_df.to_sql("materiais", conn, if_exists="replace", index=False)
            conn.close()
            st.success("Alterações salvas!")
            st.rerun()

        id_remover = st.number_input("ID do item a remover", min_value=1, step=1)
        if st.button("Remover Item"):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("DELETE FROM materiais WHERE id = ?", (id_remover,))
            conn.commit()
            conn.close()
            st.success("Item removido!")
            st.rerun()
    else:
        st.info("Nenhum item cadastrado.")

elif pagina == "Exportar Excel":
    st.title("Exportar para Excel")
    if not df.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Stock')
        output.seek(0)
        st.download_button(
            label="Baixar Excel",
            data=output,
            file_name=f"stock_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Nada para exportar.")
