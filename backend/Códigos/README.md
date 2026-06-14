# EduGPT: BNCC + AEE Specialist

Aplicação em **Streamlit** que ajuda professores a planejar aulas com base no material do livro (PDF ou imagens), consultando em paralelo a **BNCC** e **diretrizes de inclusão / AEE** armazenadas em um banco **PostgreSQL com PGVector** (RAG). O modelo de linguagem usado na interface é a API **Groq** (Llama 4 Scout).

## O que cada arquivo faz

| Arquivo | Função |
|--------|--------|
| `app.py` | Interface web: upload de material, destilação do texto para economizar tokens, chat com busca dupla (BNCC + AEE) e respostas via Groq. |
| `rag.py` | Script de **ingestão**: lê PDFs de uma pasta, divide em chunks, gera embeddings e grava na coleção `bncc_embeddings` do PGVector. |
| `rag_deficiencia.py` | Igual ao `rag.py`, porém aponta para outra pasta de documentos e grava na coleção `diretrizes_aee` (diretrizes de inclusão / planejamento AEE). |
| `.env` | Credenciais e parâmetros de conexão (não versionar em repositório público). |

## Fluxo geral

1. **Preparar o banco vetorial** (uma vez ou quando atualizar os PDFs): rodar `rag.py` e `rag_deficiencia.py` após colocar os PDFs nas pastas configuradas nos scripts.
2. **Subir o app**: executar `app.py` com Streamlit, configurar disciplina, ano e necessidades da turma na barra lateral.
3. **Enviar material**: até 10 arquivos (JPG, PNG ou PDF). O app extrai texto (PDF via LangChain; imagens via visão no Groq) e gera um **resumo pedagógico** reutilizado no chat.
4. **Conversar**: cada mensagem dispara busca por similaridade na BNCC e, se houver seleção AEE, nas diretrizes de inclusão; o sistema monta o contexto e o Groq responde.

## Requisitos

- Python 3.10+ (recomendado)
- Conta e chave **Groq** (`GROQ_API_KEY`)
- **PostgreSQL** com extensão **pgvector** acessível na rede (por exemplo, VPS/EasyPanel)
- Pacotes Python (instale conforme seu ambiente), incluindo por exemplo:

```bash
pip install streamlit groq python-dotenv langchain-community langchain-postgres langchain-huggingface pypdf psycopg[binary] sentence-transformers torch
```

Ajuste versões se o seu projeto já usar um `requirements.txt` global.

## Variáveis de ambiente (`.env`)

Defina pelo menos:

- `GROQ_API_KEY` — API Groq
- `PG_HOST`, `PG_PORT`, `PG_DATABASE`, `PG_USER`, `PG_PASSWORD` — conexão PostgreSQL usada pelo PGVector (driver `psycopg` na string gerada pelo código)

## Pastas de documentos (ingestão)

Os scripts usam caminhos absolutos no Windows; altere `caminho_arquivos` se mover o projeto:

- **BNCC** (`rag.py`): `...\Agente - Planejador Aulas\Docs`
- **AEE / deficiência** (`rag_deficiencia.py`): `...\Agente - Planejador Aulas\Docs\Planejamento - Deficiencia`

Apenas arquivos **`.pdf`** são processados no loop atual dos scripts `rag*.py`.

## Coleções PGVector

O `app.py` espera estas coleções:

- `bncc_embeddings` — alimentada por `rag.py`
- `diretrizes_aee` — alimentada por `rag_deficiencia.py`

No `app.py`, os embeddings usados na consulta são `sentence-transformers/all-MiniLM-L6-v2`. Para melhor recuperação, use o **mesmo modelo de embedding** na ingestão (`HuggingFaceEmbeddings` nos scripts) ou alinhe explicitamente o `model_name` nos três arquivos.

## Executar a interface

Na pasta deste projeto:

```bash
streamlit run app.py
```

Na barra lateral: escolha disciplina, ano, necessidades (Autismo, TDAH, Dislexia, etc.), envie os arquivos e clique em **Processar e Iniciar Chat**. Depois use o campo de chat na página principal.

## Observações

- O resumo do material limita o texto bruto enviado à destilação (trecho de até ~15 000 caracteres no prompt de resumo).
- Imagens são enviadas como JPEG em base64 no fluxo atual; formatos muito diferentes podem exigir ajuste de MIME tipo ou pré-processamento.
- `rag.py` e `rag_deficiencia.py` usam `pre_delete_collection=False`; ao reindexar do zero, avalie limpar a coleção ou trocar o nome da coleção para evitar duplicidade de chunks.

## Licença e dados

BNCC e documentos oficiais de inclusão pertencem aos respectivos órgãos; use apenas cópias que você tenha direito de armazenar e indexar.
