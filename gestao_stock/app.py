import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
import os
import cv2
# from pyzbar.pyzbar import decode   # Descomenta só para usar Webcam local
import pytesseract
from PIL import Image
import io
import numpy as np
import json
import openai   # para o Grok

# ========================= CONFIGURAÇÕES =========================
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

EMAIL_REMETENTE = "seuemail@gmail.com"
SENHA_APP = "sua-senha-de-app"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Configuração Grok (xAI) - coloca a chave em Secrets do Streamlit Cloud
client = openai.OpenAI(
    api_key=st.secrets.get("XAI_API_KEY", "coloque_aqui_sua_chave"),
    base_url="https://api.x.ai/v1"
)

# ========================= BANCO DE DADOS =========================
def get_db_connection():
    conn = sqlite3.connect('stock.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Tabela materiais (stock)
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
        campos_extra TEXT
    )
    ''')
    
    # Nova tabela: Lembretes / Tarefas
    c.execute('''
    CREATE TABLE IF NOT EXISTS lembretes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        data DATE NOT NULL,
        hora TEXT,
        descricao TEXT,
        prioridade TEXT DEFAULT 'Média',
        categoria TEXT,
        concluido INTEGER DEFAULT 0
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ========================= FUNÇÕES =========================
def enviar_alerta_email(cliente_email, item, quantidade):
    # (mantida igual à versão anterior)
    pass  # substitui pelo teu código anterior de email se quiseres

@st.cache_data(ttl=10)
def carregar_dados():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM materiais", conn)
    conn.close()
    return df

def chamar_ia(pergunta, df):
    dados = df.to_string() if not df.empty else "Nenhum stock registado ainda."
    system_prompt = f"""
    És um assistente inteligente de gestão de stock. 
    Dados atuais: {dados}
    Ajuda o utilizador em português com previsões, sugestões de compra, correção de problemas futuros e ajuda em tarefas.
    """
    response = client.chat.completions.create(
        model="grok-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pergunta}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

# ========================= INTERFACE =========================
st.sidebar.title("📦 Gestão de Stock")
pagina = st.sidebar.radio("Selecione", [
    "Dashboard", 
    "Adicionar/Editar", 
    "Listar/Remover", 
    "Exportar Excel", 
    "Calendário & Lembretes",
    "🤖 Assistente IA"
])

df = carregar_dados()

# Alerta stock baixo
if not df.empty:
    baixos = df[df['quantidade'] <= df['stock_minimo']]
    if not baixos.empty:
        st.warning("⚠️ Itens com stock baixo!")
        st.dataframe(baixos[['categoria', 'referencia', 'quantidade', 'stock_minimo']])

# ========================= PÁGINAS =========================

if pagina == "Dashboard":
    st.title("Dashboard de Stock")
    if not df.empty:
        st.dataframe(df)
        st.subheader("Resumo por Categoria")
        st.bar_chart(df['categoria'].value_counts())
    
    # Próximos lembretes no Dashboard
    conn = get_db_connection()
    lembretes_hoje = pd.read_sql_query(
        "SELECT * FROM lembretes WHERE data >= date('now') ORDER BY data, hora LIMIT 5", conn)
    conn.close()
    if not lembretes_hoje.empty:
        st.subheader("📅 Próximos Lembretes")
        st.dataframe(lembretes_hoje[['titulo', 'data', 'hora', 'prioridade']])

elif pagina == "Adicionar/Editar":
    # (todo o código anterior com as 4 opções de inserção: Manual, Foto+OCR, Webcam local comentada, Câmera browser)
    # Mantive exatamente como na última versão que te enviei
    st.title("Adicionar ou Editar Item")
    metodo = st.radio("Como inserir?", ["Manual", "Foto + OCR", "Webcam (apenas local)", "Câmera do browser (online)"])
    uploaded_file = None
    # ... (todo o resto do bloco Adicionar/Editar que já tinhas, incluindo as duas câmeras) ...

    # (cola aqui o bloco completo do Adicionar/Editar da minha resposta anterior se quiseres, ou avisa que envio só essa parte)

elif pagina == "Listar/Remover":
    # (código anterior mantido)

elif pagina == "Exportar Excel":
    # (código anterior mantido)

# ========================= NOVA PÁGINA: CALENDÁRIO & LEMBRETES =========================
elif pagina == "Calendário & Lembretes":
    st.title("📅 Calendário e Lembretes")

    tab1, tab2 = st.tabs(["➕ Adicionar Lembrete", "📋 Meus Lembretes"])

    with tab1:
        st.subheader("Novo Lembrete / Tarefa")
        col1, col2 = st.columns(2)
        with col1:
            titulo = st.text_input("Título do lembrete")
            data = st.date_input("Data", value=date.today())
            hora = st.time_input("Hora (opcional)")
        with col2:
            prioridade = st.selectbox("Prioridade", ["Alta", "Média", "Baixa"])
            categoria_lembrete = st.selectbox("Categoria", ["Stock", "Manutenção", "Compra", "Outros"])
        
        descricao = st.text_area("Descrição / Notas")

        if st.button("💾 Guardar Lembrete"):
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('''
                INSERT INTO lembretes (titulo, data, hora, descricao, prioridade, categoria)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (titulo, data, str(hora) if hora else None, descricao, prioridade, categoria_lembrete))
            conn.commit()
            conn.close()
            st.success("Lembrete guardado com sucesso!")
            st.rerun()

    with tab2:
        st.subheader("Todos os Lembretes")
        conn = get_db_connection()
        df_lembretes = pd.read_sql_query("SELECT * FROM lembretes ORDER BY data, hora", conn)
        conn.close()
        
        if not df_lembretes.empty:
            df_lembretes['data'] = pd.to_datetime(df_lembretes['data']).dt.date
            st.dataframe(df_lembretes[['titulo', 'data', 'hora', 'prioridade', 'categoria', 'descricao']])
        else:
            st.info("Ainda não tens lembretes.")

# ========================= ASSISTENTE IA =========================
elif pagina == "🤖 Assistente IA":
    st.title("🤖 Assistente IA - Gestor de Stock")
    st.write("Pergunta qualquer coisa: previsões, sugestões, ajuda em tarefas, correção de problemas futuros...")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ex: Quando vai acabar o stock de bobines?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("A IA está a pensar..."):
                resposta = chamar_ia(prompt, df)
                st.markdown(resposta)
        
        st.session_state.messages.append({"role": "assistant", "content": resposta})

# ========================= FIM =========================
