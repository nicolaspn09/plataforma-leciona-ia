import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres.vectorstores import PGVector
from dotenv import load_dotenv


load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")
all_docs = []

# --- Configurações do PostgreSQL ---
PG_HOST = os.getenv("PG_HOST") # O IP público do seu servidor Hostinger
PG_PORT = os.getenv("PG_PORT")
PG_DATABASE = os.getenv("PG_DATABASE") # O nome do banco de dados do EasyPanel
PG_USER = os.getenv("PG_USER") # O usuário do banco de dados
PG_PASSWORD = os.getenv("PG_PASSWORD") # A senha do banco de dados

print("Conectando ao banco de dados PostgreSQL...")
# String de conexão para o PGVector
CONNECTION_STRING = PGVector.connection_string_from_db_params(
    host=PG_HOST,
    port=PG_PORT,
    database=PG_DATABASE,
    user=PG_USER,
    password=PG_PASSWORD,
    driver="psycopg",
)
print("Conexão estabelecida com sucesso!")

caminho_arquivos = r"Docs"
# caminho_arquivos = "/home/codigos_airflow/livros/Rag/Data"
# persist_directory = rf"C:\Users\nicol\OneDrive\Cursos online\Treinamento Python - Hashtag\Códigos\Rag Alexandre\db"

print("Iniciando o processo de carregamento e armazenamento dos arquivos...")
# Inicializa o embedding uma única vez
embedding = HuggingFaceEmbeddings()
print("Embedding inicializado com sucesso!")

# Nome da tabela no PostgreSQL onde os vetores e metadados serão armazenados.
# A LangChain criará esta tabela automaticamente se ela não existir.
COLLECTION_NAME = "bncc_embeddings" # Um nome descritivo para sua tabela de vetores

# Configura o splitter uma única vez
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1000, # Ou o tamanho que você definir
    chunk_overlap = 200, # Ou o overlap que você definir
)

print("Iniciando o processo de embedding e armazenamento no PGVector...")

# Faz a RAG por metadados (ajuda na recuperação)
for file_name in os.listdir(caminho_arquivos):
    file_path = os.path.join(caminho_arquivos, file_name)
    docs_to_add = []

    if file_name.endswith(".pdf"):
        print(f"Carregando arquivo: {file_name}")
        loader = PyPDFLoader(file_path)
        try:
            # Carrega o documento
            docs_to_add = loader.load()
            # Adiciona o nome do arquivo como metadado "source" a cada chunk
            for doc in docs_to_add:
                doc.metadata["source"] = file_name
        except Exception as e:
            print(f"Erro ao carregar arquivo {file_name}: {e}")
            continue

    if docs_to_add:
        print(f"Dividindo {file_name} em chunks...")
        chunks = text_splitter.split_documents(documents=docs_to_add)

        print(f"Adicionando {len(chunks)} chunks de {file_name} ao PGVector...")
        try:
            PGVector.from_documents(
                documents=chunks,
                embedding=embedding,
                collection_name=COLLECTION_NAME,
                connection=CONNECTION_STRING,
                pre_delete_collection=False,
            )
            print(f"Concluído: {file_name} adicionado ao PGVector.")
        except Exception as e:
            print(f"Erro ao adicionar chunks de {file_name} ao PGVector: {e}")

print("\nProcessamento de todos os arquivos concluído e armazenado no PGVector!")