import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

load_dotenv()

db_pool = psycopg2.pool.ThreadedConnectionPool(
    1, 10,
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

def get_connection():
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        db_pool.putconn(conn, close=True)
        conn = db_pool.getconn()
    return conn

def release_connection(conn):
    try:
        if not conn.closed:
            conn.rollback()
    except Exception:
        pass
    finally:
        db_pool.putconn(conn)

def criar_usuario(nome, email, senha_hash):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Novo usuário entra no plano Grátis com 5 requisições, Ativo por padrão e criado_em automático
            cur.execute("""
                INSERT INTO lecionia.usuarios (nome, email, senha_hash, requisicoes_restantes, plano, ativo, criado_em)
                VALUES (%s, %s, %s, 5, 'Grátis', TRUE, CURRENT_TIMESTAMP) RETURNING id;
            """, (nome, email, senha_hash))
            user_id = cur.fetchone()[0]
            conn.commit()
            return user_id
    except psycopg2.IntegrityError:
        conn.rollback()
        return None
    finally:
        release_connection(conn)

def buscar_usuario_por_email(email):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome, senha_hash, requisicoes_restantes, plano, ativo, criado_em FROM lecionia.usuarios WHERE email = %s;", (email,))
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0], "nome": row[1], "senha_hash": row[2], 
                    "requisicoes_restantes": row[3], "plano": row[4], 
                    "ativo": row[5], "criado_em": row[6]
                }
            return None
    finally:
        release_connection(conn)

def buscar_usuario_por_id(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Tenta adicionar as colunas novas caso não existam (migração automática simples)
            try:
                cur.execute("ALTER TABLE lecionia.usuarios ADD COLUMN IF NOT EXISTS escola TEXT;")
                cur.execute("ALTER TABLE lecionia.usuarios ADD COLUMN IF NOT EXISTS avatar_base64 TEXT;")
                cur.execute("ALTER TABLE lecionia.usuarios ADD COLUMN IF NOT EXISTS logo_base64 TEXT;")
                conn.commit()
            except:
                conn.rollback()

            cur.execute("""
                SELECT requisicoes_restantes, plano, ativo, criado_em, 
                       nome, email, escola, logo_base64, avatar_base64 
                FROM lecionia.usuarios WHERE id = %s;
            """, (user_id,))
            row = cur.fetchone()
            if row:
                return {
                    "requisicoes_restantes": row[0], "plano": row[1],
                    "ativo": row[2], "criado_em": row[3],
                    "nome": row[4], "email": row[5], "escola": row[6] or "",
                    "logo_base64": row[7], "avatar_base64": row[8]
                }
            return None
    except Exception as e:
        print(f"❌ [ERRO BUSCAR USUARIO]: {e}")
        return None
    finally:
        release_connection(conn)

def atualizar_perfil(user_id, nome, escola, avatar_base64=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if avatar_base64:
                cur.execute("UPDATE lecionia.usuarios SET nome = %s, escola = %s, avatar_base64 = %s WHERE id = %s;", (nome, escola, avatar_base64, user_id))
            else:
                cur.execute("UPDATE lecionia.usuarios SET nome = %s, escola = %s WHERE id = %s;", (nome, escola, user_id))
            conn.commit()
            return True
    finally:
        release_connection(conn)
def alterar_status_usuario(user_id, novo_status: bool):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE lecionia.usuarios SET ativo = %s WHERE id = %s;", (novo_status, user_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ [ERRO DATABASE STATUS]: {e}")
        conn.rollback()
        return False
    finally:
        release_connection(conn)

def atualizar_plano_usuario(user_id, novo_plano: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE lecionia.usuarios SET plano = %s WHERE id = %s;", (novo_plano, user_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ [ERRO DATABASE PLANO]: {e}")
        conn.rollback()
        return False
    finally:
        release_connection(conn)

def zerar_tokens_usuario(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE lecionia.usuarios SET requisicoes_restantes = 0 WHERE id = %s;", (user_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ [ERRO DATABASE ZERAR]: {e}")
        conn.rollback()
        return False
    finally:
        release_connection(conn)

def listar_todos_usuarios():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome, email, plano, ativo, requisicoes_restantes, criado_em FROM lecionia.usuarios ORDER BY id DESC;")
            rows = cur.fetchall()
            return [
                {
                    "id": r[0], "nome": r[1], "email": r[2], 
                    "plano": r[3], "ativo": r[4], "requisicoes": r[5],
                    "data_cadastro": r[6].strftime("%d/%m/%Y") if r[6] else "-"
                }
                for r in rows
            ]
    finally:
        release_connection(conn)

def decrementar_requisicao(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE lecionia.usuarios SET requisicoes_restantes = requisicoes_restantes - 1 WHERE id = %s;", (user_id,))
            conn.commit()
    finally:
        release_connection(conn)

def adicionar_requisicoes(user_id, quantidade):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE lecionia.usuarios SET requisicoes_restantes = requisicoes_restantes + %s WHERE id = %s;", (quantidade, user_id))
            conn.commit()
    finally:
        release_connection(conn)

def contar_geracoes(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM lecionia.historico_planejamento WHERE usuario_id = %s;", (user_id,))
            return cur.fetchone()[0]
    finally:
        release_connection(conn)

def salvar_geracao(user_id, tipo, materia, ano, conteudo, aluno_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO lecionia.historico_planejamento (usuario_id, tipo_material, materia, ano, conteudo_gerado, aluno_id)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (user_id, tipo, materia, ano, conteudo, aluno_id))
            conn.commit()
    finally:
        release_connection(conn)

def listar_historico(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # ⚠️ - interval '3 hours' corrige o fuso para Brasília
            cur.execute("""
                SELECT h.tipo_material, h.materia, h.ano, (h.data_geracao - interval '3 hours'), h.conteudo_gerado, a.nome 
                FROM lecionia.historico_planejamento h
                LEFT JOIN lecionia.alunos a ON h.aluno_id = a.id
                WHERE h.usuario_id = %s ORDER BY h.data_geracao DESC;
            """, (user_id,))
            rows = cur.fetchall()
            return [{
                "tipo": r[0], "materia": r[1], "ano": r[2], 
                "data": r[3].strftime("%d/%m/%Y %H:%M"), 
                "conteudo": r[4], "aluno_nome": r[5]
            } for r in rows]
    finally:
        release_connection(conn)

def criar_aluno(professor_id, nome, serie):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO lecionia.alunos (professor_id, nome, serie) VALUES (%s, %s, %s) RETURNING id;", (professor_id, nome, serie))
            aluno_id = cur.fetchone()[0]
            conn.commit()
            return aluno_id
    finally:
        release_connection(conn)

def listar_alunos(professor_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome, serie FROM lecionia.alunos WHERE professor_id = %s ORDER BY nome;", (professor_id,))
            rows = cur.fetchall()
            return [{"id": r[0], "nome": r[1], "serie": r[2]} for r in rows]
    finally:
        release_connection(conn)

def salvar_sugestao(user_id, sugestao, email_contato):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO lecionia.sugestoes (usuario_id, sugestao, email_contato)
                VALUES (%s, %s, %s);
            """, (user_id, sugestao, email_contato))
            conn.commit()
    finally:
        release_connection(conn)

def atualizar_logo(user_id, logo_base64):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE lecionia.usuarios SET logo_base64 = %s WHERE id = %s;", (logo_base64, user_id))
            conn.commit()
    finally:
        release_connection(conn)

def salvar_token_reset(email, token):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE lecionia.usuarios 
                SET reset_token = %s, reset_token_exp = CURRENT_TIMESTAMP + INTERVAL '1 hour'
                WHERE email = %s;
            """, (token, email))
            conn.commit()
    finally:
        release_connection(conn)

def buscar_usuario_por_token(token):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM lecionia.usuarios WHERE reset_token = %s AND reset_token_exp > CURRENT_TIMESTAMP;", (token,))
            res = cur.fetchone()
            return res[0] if res else None
    finally:
        release_connection(conn)

def atualizar_senha_e_limpar_token(user_id, nova_senha_hash):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE lecionia.usuarios SET senha_hash = %s, reset_token = NULL, reset_token_exp = NULL WHERE id = %s;", (nova_senha_hash, user_id))
            conn.commit()
    finally:
        release_connection(conn)

def deletar_usuario(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Remove dependências se necessário (pela regra de cascata do banco ou manualmente)
            cur.execute("DELETE FROM lecionia.historico_planejamento WHERE usuario_id = %s;", (user_id,))
            cur.execute("DELETE FROM lecionia.alunos WHERE professor_id = %s;", (user_id,))
            cur.execute("DELETE FROM lecionia.sugestoes WHERE usuario_id = %s;", (user_id,))
            
            # Deleta o usuário
            cur.execute("DELETE FROM lecionia.usuarios WHERE id = %s;", (user_id,))
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ [ERRO DATABASE DELETE]: {e}")
        conn.rollback()
        return False
    finally:
        release_connection(conn)
