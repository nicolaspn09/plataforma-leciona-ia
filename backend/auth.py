import os
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
import jwt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
from dotenv import load_dotenv

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Definindo uma chave padrão estática e forte caso o .env falhe temporariamente
SECRET_KEY = os.getenv("JWT_SECRET", "8f3a9b2c1d4e7f6a5b8c9d0e1f2a3b4c")
ALGORITHM = "HS256"

def hash_senha(senha: str):
    return pwd_context.hash(senha)

def verificar_senha(senha_pura: str, senha_hash: str):
    return pwd_context.verify(senha_pura, senha_hash)

def criar_token(dados: dict):
    to_encode = dados.copy()
    # Expiração cravada em 4 horas
    expira = datetime.now(timezone.utc) + timedelta(hours=4)
    to_encode.update({"exp": expira})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decodificar_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        print("Log: Token expirado.")
        return None
    except jwt.PyJWTError as e:
        print(f"Log: Erro na leitura do Token - {e}")
        return None

def enviar_email_recuperacao(email_destino, link):
    msg_corpo = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>Recuperação de Senha - LecionIA</h2>
            <p>Olá! Você solicitou a redefinição de sua senha.</p>
            <p>Clique no botão abaixo para criar uma nova senha. Este link expira em 1 hora.</p>
            <a href="{link}" style="background:#dda0dd; color:white; padding:12px 24px; text-decoration:none; border-radius:6px; font-weight:bold; display:inline-block; margin-top:10px;">Redefinir Minha Senha</a>
            <p style="margin-top: 30px; font-size: 12px; color: #999;">Se você não solicitou isso, ignore este e-mail.</p>
        </body>
    </html>
    """
    
    msg = MIMEMultipart()
    # Usando os exatos nomes que você colocou no seu .env
    msg['From'] = os.getenv("GMAIL")
    msg['To'] = email_destino
    msg['Subject'] = "Recuperação de Senha - LecionIA"
    msg.attach(MIMEText(msg_corpo, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv("GMAIL"), os.getenv("GMAIL_PASSWORD"))
        server.sendmail(msg['From'], email_destino, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ [ERRO SMTP GMAIL]: {e}")
        return False

def enviar_email_sugestao(sugestao, email_usuario):
    msg_corpo = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2>💡 Nova Sugestão - LecionIA</h2>
            <p><strong>E-mail de Contato deixado pelo usuário:</strong> {email_usuario}</p>
            <p><strong>Sugestão / Feedback:</strong></p>
            <blockquote style="background:#f9f4fa; padding:15px; border-left:5px solid #dda0dd; border-radius: 4px;">
                {sugestao}
            </blockquote>
        </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['From'] = os.getenv("GMAIL")
    msg['To'] = "nicolaspn09@gmail.com, suyggomes@gmail.com"
    msg['Subject'] = "💡 Nova Sugestão de Melhoria - LecionIA"
    msg.attach(MIMEText(msg_corpo, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv("GMAIL"), os.getenv("GMAIL_PASSWORD"))
        # Envia para a lista de e-mails
        destinatarios = ["nicolaspn09@gmail.com", "suyggomes@gmail.com"]
        server.sendmail(msg['From'], destinatarios, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ [ERRO SMTP SUGESTÃO]: {e}")
        return False

def enviar_email_novo_usuario(nome, email, ip, user_agent):
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")
    
    msg_corpo = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #4CAF50;">🚀 Novo Usuário Cadastrado!</h2>
            <p>Um novo professor acaba de se juntar ao LecionIA.</p>
            <hr>
            <p><strong>Nome:</strong> {nome}</p>
            <p><strong>E-mail:</strong> {email}</p>
            <p><strong>Data/Hora (UTC):</strong> {agora}</p>
            <p><strong>IP do Cliente:</strong> {ip}</p>
            <p><strong>User-Agent:</strong> {user_agent}</p>
            <p><strong>Plano Inicial:</strong> Grátis (5 tokens)</p>
            <hr>
            <p style="font-size: 12px; color: #777;">Este é um e-mail automático de observabilidade do LecionIA.</p>
        </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['From'] = os.getenv("GMAIL")
    msg['Subject'] = f"🆕 Novo Usuário: {nome}"
    msg.attach(MIMEText(msg_corpo, 'html'))

    destinatarios = ["nicolaspn09@gmail.com", "suyggomes@gmail.com"]

    try:
        gmail_user = os.getenv("GMAIL")
        gmail_pass = os.getenv("GMAIL_PASSWORD")
        
        if not gmail_user or not gmail_pass:
            print("❌ [ERRO SMTP]: GMAIL ou GMAIL_PASSWORD não configurados no .env")
            return False

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_pass)
        server.sendmail(msg['From'], destinatarios, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ [ERRO SMTP NOVO USUÁRIO]: {e}")
        return False

def enviar_email_alerta_admin(acao, target_id, admin_email, extra_info=""):
    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")
    
    cores = {
        "ATIVADO": "#4CAF50",
        "INATIVADO": "#FF9800",
        "EXCLUÍDO": "#F44336"
    }
    cor = cores.get(acao, "#333")

    msg_corpo = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: {cor};">⚠️ Alerta Administrativo: {acao}</h2>
            <p>Uma ação administrativa foi realizada no sistema.</p>
            <hr>
            <p><strong>Ação:</strong> {acao}</p>
            <p><strong>ID do Usuário Alvo:</strong> {target_id}</p>
            <p><strong>Realizado por:</strong> {admin_email}</p>
            <p><strong>Data/Hora (UTC):</strong> {agora}</p>
            {f"<p><strong>Informação Extra:</strong> {extra_info}</p>" if extra_info else ""}
            <hr>
            <p style="font-size: 12px; color: #777;">Observabilidade LecionIA - Gestão de Acessos.</p>
        </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['From'] = os.getenv("GMAIL")
    msg['Subject'] = f"⚠️ {acao}: Usuário {target_id}"
    msg.attach(MIMEText(msg_corpo, 'html'))

    destinatarios = ["nicolaspn09@gmail.com", "suyggomes@gmail.com"]

    try:
        gmail_user = os.getenv("GMAIL")
        gmail_pass = os.getenv("GMAIL_PASSWORD")

        if not gmail_user or not gmail_pass:
            print("❌ [ERRO SMTP ADMIN]: GMAIL ou GMAIL_PASSWORD não configurados no .env")
            return False
        
        # Log para depuração no terminal do usuário
        print(f"📧 [SMTP]: Tentando enviar alerta para {destinatarios} usando {gmail_user}...")
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_pass)
        server.sendmail(msg['From'], destinatarios, msg.as_string())
        server.quit()
        
        print(f"✅ [SMTP]: Alerta de {acao} enviado com sucesso!")
        return True
    except Exception as e:
        print(f"❌ [ERRO SMTP ALERTA ADMIN]: {e}")
        return False