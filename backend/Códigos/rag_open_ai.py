import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from dotenv import load_dotenv, find_dotenv

# Obtém o caminho do diretório onde o script está localizado
script_dir = os.path.dirname(os.path.abspath(__file__))
# Procura o .env a partir do diretório do script
dotenv_path = find_dotenv(os.path.join(script_dir, '.env'))
# Carrega o .env
load_dotenv(dotenv_path)

# Forçando a leitura da chave de API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("⚠️ ERRO: A variável OPENAI_API_KEY não foi encontrada no arquivo .env!")

PG_HOST = os.getenv("PG_HOST") 
PG_PORT = os.getenv("PG_PORT")
PG_DATABASE = os.getenv("PG_DATABASE") 
PG_USER = os.getenv("PG_USER") 
PG_PASSWORD = os.getenv("PG_PASSWORD") 

print("Conectando ao banco de dados PostgreSQL...")
CONNECTION_STRING = PGVector.connection_string_from_db_params(
    host=PG_HOST, port=PG_PORT, database=PG_DATABASE, user=PG_USER, password=PG_PASSWORD, driver="psycopg",
)

# Inicializa o motor de vetores da OpenAI forçando a chave
embedding = OpenAIEmbeddings(
    model="text-embedding-3-small", 
    api_key=OPENAI_API_KEY
)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

def processar_pasta(caminho_pasta, nome_colecao):
    print(f"\n--- Iniciando RAG para a coleção: {nome_colecao} ---")
    
    if not os.path.exists(caminho_pasta):
        print(f"Pasta não encontrada: {caminho_pasta}")
        return

    for file_name in os.listdir(caminho_pasta):
        file_path = os.path.join(caminho_pasta, file_name)
        docs_to_add = []

        if file_name.endswith(".pdf"):
            print(f"Lendo: {file_name}")
            loader = PyPDFLoader(file_path)
            try:
                docs_to_add = loader.load()
                for doc in docs_to_add:
                    doc.metadata["source"] = file_name
            except Exception as e:
                print(f"Erro ao ler {file_name}: {e}")
                continue

        if docs_to_add:
            chunks = text_splitter.split_documents(documents=docs_to_add)
            PGVector.from_documents(
                documents=chunks,
                embedding=embedding,
                collection_name=nome_colecao,
                connection=CONNECTION_STRING,
                pre_delete_collection=False,
            )
            print(f"✅ {file_name} salvo com sucesso.")

# Rode para criar as novas tabelas da OpenAI
processar_pasta(r"C:\Users\nicol\OneDrive\Cursos online\Treinamento Python - Hashtag\Códigos\Projeto - LecionaIA\Docs\Planejamento - Deficiencia", "diretrizes_aee_openai")
processar_pasta(r"C:\Users\nicol\OneDrive\Cursos online\Treinamento Python - Hashtag\Códigos\Projeto - LecionaIA\Docs", "bncc_embeddings_openai")

print("\n🚀 RAG da OpenAI finalizado com sucesso!")