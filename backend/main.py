import secrets
from datetime import datetime, timezone, timedelta
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List
from . import auth, database
from .ai_engine import processar_e_gerar_aula, processar_cascata, gerar_arquivo_pptx

app = FastAPI(title="LecionIA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

@app.get("/ping")
def ping():
    return {"status": "ok", "message": "LecionIA API está ativa"}

def obter_usuario_logado(token: str = Depends(oauth2_scheme)):
    payload = auth.decodificar_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    
    user_id = int(payload["sub"])
    usuario = database.buscar_usuario_por_id(user_id)
    if not usuario or not usuario.get("ativo", True):
        raise HTTPException(status_code=403, detail="Sua conta está inativa. Entre em contato com o suporte.")
        
    return payload

@app.post("/cadastrar")
def cadastrar(request: Request, nome: str = Form(...), email: str = Form(...), senha: str = Form(...)):
    existing_user = database.buscar_usuario_por_email(email)
    if existing_user:
         raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    senha_hash = auth.hash_senha(senha)
    user_id = database.criar_usuario(nome, email, senha_hash)
    if not user_id:
        raise HTTPException(status_code=500, detail="Erro interno ao criar usuário.")
        
    ip_cliente = request.client.host if request.client else "IP Desconhecido"
    user_agent = request.headers.get("user-agent", "UA Desconhecido")
    
    auth.enviar_email_novo_usuario(nome, email, ip_cliente, user_agent)
    token = auth.criar_token({"sub": str(user_id), "nome": nome, "email": email})

    return {
        "access_token": token,
        "token_type": "bearer",
        "requisicoes": 5
    }

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    usuario = database.buscar_usuario_por_email(form_data.username)
    if not usuario:
        raise HTTPException(status_code=400, detail="E-mail ou senha incorretos.")
    
    if not usuario.get("ativo", True):
        raise HTTPException(status_code=403, detail="Sua conta está inativa. Entre em contato com o suporte.")

    try:
        senha_valida = auth.verificar_senha(form_data.password, usuario["senha_hash"])
    except Exception as e:
        print(f"❌ [ERRO DE AUTENTICAÇÃO]: Senha no banco de dados está em formato inválido ou texto puro. Erro: {e}")
        raise HTTPException(status_code=400, detail="Erro de consistência cadastral. Entre em contato com o suporte.")

    if not senha_valida:
        raise HTTPException(status_code=400, detail="E-mail ou senha incorretos.")
    
    token = auth.criar_token({"sub": str(usuario["id"]), "nome": usuario["nome"], "email": form_data.username})
    return {"access_token": token, "token_type": "bearer", "requisicoes": usuario["requisicoes_restantes"]}

# --- ROTAS ADMINISTRATIVAS ---

@app.get("/admin/usuarios")
def listar_usuarios_admin(user_data: dict = Depends(obter_usuario_logado)):
    if user_data.get("email") != "nicolaspn09@gmail.com":
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores.")
    return database.listar_todos_usuarios()

@app.post("/admin/status-usuario/{target_id}")
def mudar_status_usuario(target_id: int, ativo: bool = Form(...), user_data: dict = Depends(obter_usuario_logado)):
    if user_data.get("email") != "nicolaspn09@gmail.com":
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores.")
    
    sucesso = database.alterar_status_usuario(target_id, ativo)
    if not sucesso:
        raise HTTPException(status_code=500, detail="Erro ao alterar status do usuário.")
        
    status_str = "ativado" if ativo else "inativado"
    auth.enviar_email_alerta_admin("ATIVADO" if ativo else "INATIVADO", target_id, user_data.get("email"))
    return {"status": "success", "mensagem": f"Usuário {target_id} foi {status_str} com sucesso."}

@app.delete("/admin/deletar-usuario/{target_id}")
def deletar_usuario_admin(target_id: int, user_data: dict = Depends(obter_usuario_logado)):
    if user_data.get("email") != "nicolaspn09@gmail.com":
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores.")
    
    sucesso = database.deletar_usuario(target_id)
    if not sucesso:
        raise HTTPException(status_code=500, detail="Erro ao deletar usuário.")
    
    auth.enviar_email_alerta_admin("EXCLUÍDO", target_id, user_data.get("email"))
    return {"status": "success", "mensagem": f"Usuário {target_id} deletado permanentemente."}

# --- FIM ROTAS ADMINISTRATIVAS ---

@app.get("/meu-saldo")
def ver_saldo(user_data: dict = Depends(obter_usuario_logado)):
    user_id = int(user_data["sub"])
    usuario = database.buscar_usuario_por_id(user_id)
    
    # --- REGRA DE 7 DIAS GRÁTIS (usando criado_em) ---
    if usuario["plano"] == "Grátis" and usuario["requisicoes_restantes"] > 0:
        data_cad = usuario.get("criado_em")
        if data_cad:
            if data_cad.tzinfo is None:
                data_cad = data_cad.replace(tzinfo=timezone.utc)
                
            hoje = datetime.now(timezone.utc)
            diferenca = hoje - data_cad
            
            if diferenca.days >= 7:
                print(f"🕒 [TRIAL EXPIRED]: Usuário {user_id} passou dos 7 dias. Zerando tokens.")
                database.zerar_tokens_usuario(user_id)
                usuario["requisicoes_restantes"] = 0

    total_gerado = database.contar_geracoes(user_id)

    # Capacidade total baseada no plano para cálculo de porcentagem no frontend
    capacidade_total = 50
    if usuario["plano"] == "Grátis":
        capacidade_total = 5
    elif usuario["plano"] == "Essencial":
        capacidade_total = 20
    elif usuario["plano"] == "Enterprise" or usuario["plano"] == "Administrador":
        capacidade_total = 100 # Referencial para Admin, mas o frontend tratará como infinito

    return {
        "restantes": usuario["requisicoes_restantes"],
        "plano": usuario["plano"],
        "logo": usuario.get("logo_base64", None),
        "avatar": usuario.get("avatar_base64", None),
        "escola": usuario.get("escola", "Minha Escola"),
        "total_gerado": total_gerado,
        "capacidade_total": capacidade_total,
        "criado_em": usuario.get("criado_em").isoformat() if usuario.get("criado_em") else None
    }

@app.post("/atualizar-perfil")
def update_perfil(
    nome: str = Form(...),
    escola: str = Form(...),
    avatar_base64: str = Form(None),
    user_data: dict = Depends(obter_usuario_logado)
):
    user_id = int(user_data["sub"])
    database.atualizar_perfil(user_id, nome, escola, avatar_base64)
    return {"status": "success"}

@app.post("/atualizar-senha")
def update_senha(
    senha_atual: str = Form(...),
    nova_senha: str = Form(...),
    user_data: dict = Depends(obter_usuario_logado)
):
    user_id = int(user_data["sub"])
    usuario = database.buscar_usuario_por_email(user_data["email"])
    
    if not auth.verificar_senha(senha_atual, usuario["senha_hash"]):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    
    nova_hash = auth.hash_senha(nova_senha)
    database.atualizar_senha_e_limpar_token(user_id, nova_hash)
    return {"status": "success"}

@app.post("/gerar-aula")
async def gerar_aula(
    tipo: str = Form(...),
    materia: str = Form(...),
    ano: str = Form(...),
    necessidades: str = Form(""),
    prompt_chat: str = Form(...),
    arquivos: Optional[List[UploadFile]] = File(None),
    user_data: dict = Depends(obter_usuario_logado)
):
    user_id = int(user_data["sub"])
    lista_arquivos = arquivos if arquivos else []
    usuario = database.buscar_usuario_por_id(user_id)
    
    # Re-verifica trial antes de gerar
    if usuario["plano"] == "Grátis":
        data_cad = usuario.get("criado_em")
        if data_cad:
            if data_cad.tzinfo is None: data_cad = data_cad.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - data_cad).days >= 7:
                database.zerar_tokens_usuario(user_id)
                raise HTTPException(status_code=403, detail="Seu período de teste de 7 dias expirou.")

    if usuario["requisicoes_restantes"] <= 0 and usuario["plano"] not in ["Administrador", "Enterprise"]:
        raise HTTPException(status_code=403, detail="Sem saldo de tokens!")

    try:
        resultado = await processar_e_gerar_aula(tipo, materia, ano, necessidades, prompt_chat, lista_arquivos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    database.decrementar_requisicao(user_id)
    return {"status": "success", "roteiro": resultado}

@app.post("/salvar-aprovado")
async def salvar_aprovado(
    tipo: str = Form(...),
    materia: str = Form(...),
    ano: str = Form(...),
    conteudo: str = Form(...),
    aluno_id: str = Form(None),
    user_data: dict = Depends(obter_usuario_logado)
):
    user_id = int(user_data["sub"])
    aid = int(aluno_id) if aluno_id and aluno_id != "null" else None
    database.salvar_geracao(user_id, tipo, materia, ano, conteudo, aid)
    return {"status": "saved"}

@app.get("/historico")
def ver_historico(user_data: dict = Depends(obter_usuario_logado)):
    user_id = int(user_data["sub"])
    return database.listar_historico(user_id)

@app.get("/alunos")
def pegar_alunos(user_data: dict = Depends(obter_usuario_logado)):
    user_id = int(user_data["sub"])
    return database.listar_alunos(user_id)

@app.post("/alunos")
def cadastrar_aluno(nome: str = Form(...), serie: str = Form(...), user_data: dict = Depends(obter_usuario_logado)):
    user_id = int(user_data["sub"])
    return database.criar_aluno(user_id, nome, serie)

@app.post("/minha-logo")
def upload_logo(logo_base64: str = Form(...), user_data: dict = Depends(obter_usuario_logado)):
    user_id = int(user_data["sub"])
    database.atualizar_logo(user_id, logo_base64)
    return {"status": "ok"}

@app.post("/gerar-cascata")
async def gerar_cascata(tipo: str = Form(...), conteudo_base: str = Form(...), user_data: dict = Depends(obter_usuario_logado)):
    user_id = int(user_data["sub"])
    usuario = database.buscar_usuario_por_id(user_id)
    
    if usuario["plano"] == "Grátis":
        data_cad = usuario.get("criado_em")
        if data_cad:
            if data_cad.tzinfo is None: data_cad = data_cad.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - data_cad).days >= 7:
                database.zerar_tokens_usuario(user_id)
                raise HTTPException(status_code=403, detail="Teste expirado.")

    if usuario["requisicoes_restantes"] <= 0 and usuario["plano"] not in ["Administrador", "Enterprise"]:
        raise HTTPException(status_code=403, detail="Sem saldo!")
    
    resultado = await processar_cascata(tipo, conteudo_base)
    database.decrementar_requisicao(user_id)
    return {"status": "success", "roteiro": resultado}

@app.post("/gerar-slide-pptx")
async def endpoint_gerar_slide(conteudo_base: str = Form(...), user_data: dict = Depends(obter_usuario_logado)):
    user_id = int(user_data["sub"])
    usuario = database.buscar_usuario_por_id(user_id)
    
    if usuario["plano"] == "Grátis":
        data_cad = usuario.get("criado_em")
        if data_cad:
            if data_cad.tzinfo is None: data_cad = data_cad.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - data_cad).days >= 7:
                database.zerar_tokens_usuario(user_id)
                raise HTTPException(status_code=403, detail="Teste expirado.")

    if usuario["requisicoes_restantes"] <= 0 and usuario["plano"] not in ["Administrador", "Enterprise"]:
        raise HTTPException(status_code=403, detail="Sem saldo!")
    
    logo_escola = usuario.get("logo_base64", None)
    b64_file = await gerar_arquivo_pptx(conteudo_base, logo_escola)
    database.decrementar_requisicao(user_id)
    
    return {"status": "success", "file_b64": b64_file}

@app.post("/esqueci-senha")
def esqueci_senha(email: str = Form(...)):
    user = database.buscar_usuario_por_email(email)
    if not user:
        return {"status": "ok"}
    
    token = secrets.token_urlsafe(32)
    database.salvar_token_reset(email, token)
    link = f"https://lecionaai.com.br/redefinir-senha.html?token={token}"
    auth.enviar_email_recuperacao(email, link)
    return {"status": "ok"}

@app.post("/redefinir-senha-final")
def redefinir_final(token: str = Form(...), nova_senha: str = Form(...)):
    user_id = database.buscar_usuario_por_token(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Solicite novamente.")
    
    hash_nova = auth.hash_senha(nova_senha)
    database.atualizar_senha_e_limpar_token(user_id, hash_nova)
    return {"status": "success"}

@app.post("/sugestao")
def enviar_sugestao(
    sugestao: str = Form(...),
    email_contato: str = Form(""),
    user_data: dict = Depends(obter_usuario_logado)
):
    user_id = int(user_data["sub"])
    database.salvar_sugestao(user_id, sugestao, email_contato)
    auth.enviar_email_sugestao(sugestao, email_contato)
    return {"status": "success", "mensagem": "Sugestão enviada com sucesso!"}

app.mount("/images", StaticFiles(directory="images"), name="images")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
