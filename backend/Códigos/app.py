import streamlit as st
import os
import base64
import tempfile
import shutil
from groq import Groq
from langchain_postgres.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv

# 1. SETUP E CRÍTICA DE AMBIENTE
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

st.set_page_config(page_title="EduGPT: BNCC + AEE Specialist", layout="wide")

# Inicialização de Embeddings (Deve ser o mesmo usado na ingestão)
@st.cache_resource
def get_vectorstore(collection_name):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    conn_string = PGVector.connection_string_from_db_params(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        database=os.getenv("PG_DATABASE"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        driver="psycopg",
    )
    return PGVector(connection=conn_string, collection_name=collection_name, embeddings=embeddings, create_extension=False)

# Conectando às duas bases
db_bncc = get_vectorstore("bncc_embeddings")
db_aee = get_vectorstore("diretrizes_aee")

# 2. GESTÃO DE ESTADO (MEMÓRIA)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pedagogical_summary" not in st.session_state:
    st.session_state.pedagogical_summary = ""
if "processing_done" not in st.session_state:
    st.session_state.processing_done = False

# 3. CORE: PROCESSAMENTO E ECONOMIA DE TOKENS
def distill_tokens(raw_text):
    """
    Destilação Pedagógica: Transforma o texto bruto das imagens em um resumo 
    compacto para economizar tokens nas próximas interações do chat.
    """
    prompt = f"""
    Resuma este conteúdo de livro didático para um planejamento de aula.
    Mantenha apenas: temas centrais, vocabulário chave (se for inglês, mantenha em inglês), 
    objetivos implícitos e tipos de exercícios. Delete repetições e textos irrelevantes.
    TEXTO BRUTO: {raw_text[:15000]} 
    """
    res = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return res.choices[0].message.content

def process_uploaded_material(files):
    full_text = ""
    temp_dir = tempfile.mkdtemp()
    try:
        for file in files[:10]:
            file_path = os.path.join(temp_dir, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            
            if file.type == "application/pdf":
                loader = PyPDFLoader(file_path)
                pages = loader.load()
                full_text += "\n".join([p.page_content for p in pages])
            else:
                # OCR via Llama Vision
                img_b64 = base64.b64encode(file.getvalue()).decode('utf-8')
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extraia todo o conteúdo educacional desta imagem."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }]
                )
                full_text += response.choices[0].message.content
    finally:
        shutil.rmtree(temp_dir)
    return distill_tokens(full_text)

# 4. INTERFACE LATERAL (INPUTS)
with st.sidebar:
    st.title("📚 Configurações")
    materia = st.selectbox("Disciplina", ["Língua Inglesa", "Matemática", "Português", "Ciências", "História"])
    ano = st.selectbox("Ano", [f"{i}º ano" for i in range(1, 10)])
    
    st.subheader("♿ Inclusão (AEE)")
    aee_targets = st.multiselect("Necessidades na Turma:", 
                                 ["Autismo", "TDAH", "Dislexia", "Baixa Visão", "Deficiência Intelectual"])
    
    uploaded_files = st.file_uploader("Fotos/PDFs do Livro (Max 10)", type=["jpg", "png", "pdf"], accept_multiple_files=True)
    
    if st.button("🔄 Processar e Iniciar Chat") and uploaded_files:
        with st.spinner("Lendo material e destilando tokens..."):
            st.session_state.pedagogical_summary = process_uploaded_material(uploaded_files)
            st.session_state.processing_done = True
            st.success("Contexto gerado!")

# 5. CHAT INTERATIVO (DUAL-RAG)
st.title("💬 Planejador de Aulas AI")

if not st.session_state.processing_done:
    st.info("Suba o material na barra lateral para começar.")
else:
    # Exibe o sumário destilado para o professor validar
    with st.expander("📌 Resumo Pedagógico do Material (Base do Chat)"):
        st.write(st.session_state.pedagogical_summary)

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if chat_input := st.chat_input("Ex: 'Crie uma atividade de introdução para este conteúdo...'"):
        st.session_state.messages.append({"role": "user", "content": chat_input})
        st.chat_message("user").write(chat_input)

        with st.spinner("Consultando BNCC e Diretrizes de Inclusão..."):
            # BUSCA DUAL-RAG
            query_rag = f"{materia} {ano}: {chat_input}"
            
            # Busca BNCC (O que ensinar)
            docs_bncc = db_bncc.similarity_search(query_rag, k=3)
            contexto_bncc = "\n".join([d.page_content for d in docs_bncc])
            
            # Busca AEE (Como adaptar)
            contexto_aee = ""
            if aee_targets:
                query_aee = f"Estratégias pedagógicas para: {', '.join(aee_targets)}"
                docs_aee = db_aee.similarity_search(query_aee, k=3)
                contexto_aee = "\n".join([d.page_content for d in docs_aee])

            # Prompt Final do Sistema (Injecting Summary + RAG)
            system_instruction = f"""
            Você é um Mentor Pedagógico Sênior.
            CONTEXTO DO LIVRO (SUMÁRIO): {st.session_state.pedagogical_summary}
            DISCIPLINA: {materia} | ANO: {ano}
            
            DIRETRIZES BNCC:
            {contexto_bncc}
            
            DIRETRIZES AEE (INCLUSÃO):
            {contexto_aee if contexto_aee else "Não há necessidades específicas para esta aula."}

            REGRAS:
            1. Use o SUMÁRIO como base para as atividades.
            2. Se houver AEE, proponha adaptações TÉCNICAS baseadas nas diretrizes fornecidas.
            3. Responda de forma prática e direta para o professor.
            """

            full_messages = [{"role": "system", "content": system_instruction}] + st.session_state.messages
            
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=full_messages,
                temperature=0
            )

            answer = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.chat_message("assistant").write(answer)