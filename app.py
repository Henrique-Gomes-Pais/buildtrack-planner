import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime, date, timedelta
import calendar
import os
import shutil
import webbrowser
import hashlib
import secrets


# ============================================================
# CONFIGURAÇÕES
# ============================================================

APP_TITLE = "Planejamento de Construção"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "meu_organizador_novo.db")
ANEXOS_DIR = os.path.join(BASE_DIR, "anexos")

os.makedirs(ANEXOS_DIR, exist_ok=True)

BG = "#F4F7FB"
WHITE = "#FFFFFF"
BLUE = "#1769E0"
BLUE_DARK = "#0E4FA8"
BLUE_LIGHT = "#EAF2FF"
TEXT = "#172033"
TEXT_LIGHT = "#667085"
BORDER = "#D9E2F0"
GREEN = "#19A974"
RED = "#E5484D"
ORANGE = "#F59E0B"
PURPLE = "#7C3AED"
SIDEBAR = "#0F172A"
YELLOW_LIGHT = "#FFF8E7"
RED_LIGHT = "#FFF0F0"
GREEN_LIGHT = "#EAF8F1"


# ============================================================
# BANCO
# ============================================================

def conectar():
    conexao = sqlite3.connect(DB_FILE)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def gerar_hash_senha(senha_texto, salt=None):
    """Gera um hash seguro (PBKDF2) para a senha, com salt aleatório.
    Formato salvo: '<salt>$<hash>'."""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_senha = hashlib.pbkdf2_hmac(
        "sha256",
        (senha_texto or "").encode("utf-8"),
        salt.encode("utf-8"),
        100_000
    ).hex()
    return f"{salt}${hash_senha}"


def verificar_senha(senha_texto, senha_armazenada):
    """Confere uma senha digitada contra o hash salvo no formato '<salt>$<hash>'."""
    try:
        salt, hash_esperado = (senha_armazenada or "").split("$", 1)
    except ValueError:
        return False
    hash_calculado = hashlib.pbkdf2_hmac(
        "sha256",
        (senha_texto or "").encode("utf-8"),
        salt.encode("utf-8"),
        100_000
    ).hex()
    return hash_calculado == hash_esperado


def coluna_existe(cursor, tabela, coluna):
    resultado = cursor.execute(
        f"PRAGMA table_info({tabela})"
    ).fetchall()

    return any(row[1] == coluna for row in resultado)


def adicionar_coluna(cursor, tabela, coluna, definicao):
    if not coluna_existe(cursor, tabela, coluna):
        cursor.execute(
            f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}"
        )


def criar_banco():
    """
    Cria o banco e acrescenta as estruturas novas.
    A função tenta preservar bancos existentes.
    """

    conexao = conectar()
    cursor = conexao.cursor()

    # --------------------------------------------------------
    # USUÁRIOS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            login TEXT UNIQUE,
            senha TEXT NOT NULL,
            perfil TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Compatibilidade com versões antigas.
    # Se existia uma tabela com "usuario" em vez de "login",
    # tentamos preservar os dados.
    if not coluna_existe(cursor, "usuarios", "login"):
        adicionar_coluna(cursor, "usuarios", "login", "TEXT")

    if not coluna_existe(cursor, "usuarios", "ativo"):
        adicionar_coluna(cursor, "usuarios", "ativo", "INTEGER DEFAULT 1")

    # --------------------------------------------------------
    # PLANOS DO DIA
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS planos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            texto TEXT NOT NULL DEFAULT '',
            atualizado_em TEXT NOT NULL,
            UNIQUE(usuario_id, data),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    # --------------------------------------------------------
    # TAREFAS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT DEFAULT '',
            data TEXT NOT NULL,
            concluida INTEGER NOT NULL DEFAULT 0,
            criada_em TEXT NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    # Novas colunas de tarefas.
    adicionar_coluna(
        cursor,
        "tarefas",
        "projeto",
        "TEXT DEFAULT ''"
    )

    adicionar_coluna(
        cursor,
        "tarefas",
        "prioridade",
        "TEXT DEFAULT 'Normal'"
    )

    adicionar_coluna(
        cursor,
        "tarefas",
        "ordem",
        "INTEGER DEFAULT 0"
    )

    adicionar_coluna(
        cursor,
        "tarefas",
        "criada_por",
        "INTEGER"
    )

    # V7: tarefas passam a apontar para o cadastro central de projetos.
    # Mantemos também a coluna textual "projeto" para compatibilidade com registros antigos.
    adicionar_coluna(
        cursor,
        "tarefas",
        "projeto_id",
        "INTEGER"
    )

    # --------------------------------------------------------
    # CONVERSAS / ALTERAÇÕES DAS TAREFAS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tarefa_conversas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarefa_id INTEGER NOT NULL,
            autor_id INTEGER NOT NULL,
            participantes TEXT DEFAULT '',
            texto TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(tarefa_id) REFERENCES tarefas(id),
            FOREIGN KEY(autor_id) REFERENCES usuarios(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tarefa_conversa_anexos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversa_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            caminho TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(conversa_id) REFERENCES tarefa_conversas(id)
        )
    """)

    # --------------------------------------------------------
    # PROJETOS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            endereco TEXT DEFAULT '',
            caminho TEXT DEFAULT '',
            descricao TEXT DEFAULT '',
            criado_por INTEGER,
            criado_em TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    # V7: cadastro central de obras/projetos. Nada é apagado; apenas acrescentamos metadados.
    adicionar_coluna(cursor, "projetos", "codigo", "TEXT DEFAULT ''")
    adicionar_coluna(cursor, "projetos", "cliente", "TEXT DEFAULT ''")
    adicionar_coluna(cursor, "projetos", "status", "TEXT DEFAULT 'Ativo'")
    adicionar_coluna(cursor, "projetos", "atualizado_em", "TEXT DEFAULT ''")
    adicionar_coluna(cursor, "projetos", "finalizado_em", "TEXT DEFAULT ''")

    # Converte de forma conservadora o campo antigo "ativo" para o novo status.
    cursor.execute("""
        UPDATE projetos
        SET status = CASE
            WHEN COALESCE(ativo, 1) = 1 THEN 'Ativo'
            ELSE CASE
                WHEN TRIM(COALESCE(status, '')) = '' OR status = 'Ativo' THEN 'Finalizado'
                ELSE status
            END
        END
        WHERE status IS NULL OR TRIM(status) = '' OR (COALESCE(ativo, 1) = 0 AND status = 'Ativo')
    """)

    # --------------------------------------------------------
    # CONFERÊNCIAS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conferencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            trabalhador_id INTEGER,
            conferido_por INTEGER NOT NULL,
            observacao TEXT DEFAULT '',
            conferido_em TEXT NOT NULL,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(trabalhador_id) REFERENCES usuarios(id),
            FOREIGN KEY(conferido_por) REFERENCES usuarios(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projeto_status_trabalhador (
            projeto_id INTEGER NOT NULL,
            trabalhador_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Em andamento',
            atualizado_em TEXT NOT NULL,
            PRIMARY KEY (projeto_id, trabalhador_id),
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(trabalhador_id) REFERENCES usuarios(id)
        )
    """)

    # --------------------------------------------------------
    # SOLICITAÇÕES DE CONFERÊNCIA (V7)
    # --------------------------------------------------------
    # Cada envio de plano agora é um registro próprio. Isso separa projeto,
    # autor, conferidor e histórico e permite aplicar privacidade por grupo.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS solicitacoes_conferencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            autor_id INTEGER NOT NULL,
            nome_plano TEXT NOT NULL DEFAULT '',
            caminho TEXT DEFAULT '',
            descricao TEXT DEFAULT '',
            estado TEXT NOT NULL DEFAULT 'aguardando',
            status_operacional TEXT NOT NULL DEFAULT 'Em andamento',
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            conferido_por INTEGER,
            conferido_em TEXT,
            observacao_conferencia TEXT DEFAULT '',
            legacy_chave TEXT UNIQUE,
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(autor_id) REFERENCES usuarios(id),
            FOREIGN KEY(conferido_por) REFERENCES usuarios(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS solicitacao_conferencia_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solicitacao_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            usuario_id INTEGER,
            texto TEXT DEFAULT '',
            criado_em TEXT NOT NULL,
            FOREIGN KEY(solicitacao_id) REFERENCES solicitacoes_conferencia(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    # --------------------------------------------------------
    # INFORMAÇÕES ADICIONAIS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS informacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trabalhador_id INTEGER NOT NULL,
            projeto_id INTEGER,
            autor_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            texto TEXT DEFAULT '',
            prioridade TEXT DEFAULT 'Normal',
            criado_em TEXT NOT NULL,
            FOREIGN KEY(trabalhador_id) REFERENCES usuarios(id),
            FOREIGN KEY(projeto_id) REFERENCES projetos(id),
            FOREIGN KEY(autor_id) REFERENCES usuarios(id)
        )
    """)

    adicionar_coluna(
        cursor,
        "informacoes",
        "caminho_pasta",
        "TEXT DEFAULT ''"
    )

    # --------------------------------------------------------
    # ANEXOS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anexos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            informacao_id INTEGER,
            projeto_id INTEGER,
            nome TEXT NOT NULL,
            caminho TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(informacao_id) REFERENCES informacoes(id),
            FOREIGN KEY(projeto_id) REFERENCES projetos(id)
        )
    """)

    # --------------------------------------------------------
    # LEITURA DAS INFORMAÇÕES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS informacoes_leitura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            informacao_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            lido_em TEXT NOT NULL,
            UNIQUE(informacao_id, usuario_id),
            FOREIGN KEY(informacao_id) REFERENCES informacoes(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    # --------------------------------------------------------
    # EVENTOS DO CALENDÁRIO
    # férias planejadas / férias confirmadas / Feierabend
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos_calendario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            data_inicio TEXT NOT NULL,
            data_fim TEXT NOT NULL,
            hora TEXT DEFAULT '',
            observacao TEXT DEFAULT '',
            criado_em TEXT NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    # --------------------------------------------------------
    # USUÁRIOS REAIS
    # --------------------------------------------------------

    usuarios = [
        ("Alex", "alex", "alex123", "worker"),
        ("Sam", "sam", "sam123", "worker"),
        ("Noah", "noah", "noah123", "worker"),
        ("Liam", "liam", "liam123", "worker"),
        ("Mia", "mia", "mia123", "worker"),
        ("Chris", "chris", "chris123", "worker"),
        ("Owen", "owen", "owen123", "worker"),
        ("Zoe", "zoe", "zoe123", "worker"),

        ("Dana", "dana", "dana123", "planner"),
        ("Kai", "kai", "kai123", "planner"),
        ("Theo", "theo", "theo123", "planner"),

        ("Priya", "priya", "priya123", "lead"),

        ("Jordan", "jordan", "jordan123", "manager"),
    ]

    # Primeiro, tenta preencher login para bases antigas
    # que possuíam a coluna "usuario".
    if coluna_existe(cursor, "usuarios", "usuario"):
        antigos = cursor.execute("""
            SELECT id, usuario
            FROM usuarios
            WHERE (login IS NULL OR login = '')
              AND usuario IS NOT NULL
        """).fetchall()

        for antigo in antigos:
            try:
                cursor.execute(
                    """
                    UPDATE usuarios
                    SET login = ?
                    WHERE id = ?
                    """,
                    (antigo["usuario"], antigo["id"])
                )
            except sqlite3.IntegrityError:
                pass

    for nome, login, senha, perfil in usuarios:

        existente = cursor.execute("""
            SELECT id
            FROM usuarios
            WHERE login = ?
        """, (login,)).fetchone()

        if existente:
            cursor.execute("""
                UPDATE usuarios
                SET nome = ?,
                    perfil = ?,
                    ativo = 1
                WHERE login = ?
            """, (nome, perfil, login))
        else:
            try:
                cursor.execute("""
                    INSERT INTO usuarios
                    (nome, login, senha, perfil, ativo)
                    VALUES (?, ?, ?, ?, 1)
                """, (nome, login, gerar_hash_senha(senha), perfil))
            except sqlite3.IntegrityError:
                pass

    # Observação: a senha NÃO é mais resetada aqui a cada abertura do programa.
    # Isso permitia, antes, que uma troca de senha feita pelo usuário fosse
    # apagada no próximo início do app. A senha só é definida na criação
    # do usuário (acima) ou via alterar_senha().

    # V7: associa tarefas antigas ao projeto central quando o nome já coincide.
    cursor.execute("""
        UPDATE tarefas
        SET projeto_id = (
            SELECT p.id
            FROM projetos p
            WHERE LOWER(TRIM(p.nome)) = LOWER(TRIM(tarefas.projeto))
            ORDER BY p.id
            LIMIT 1
        )
        WHERE projeto_id IS NULL
          AND TRIM(COALESCE(projeto, '')) <> ''
          AND EXISTS (
              SELECT 1 FROM projetos p
              WHERE LOWER(TRIM(p.nome)) = LOWER(TRIM(tarefas.projeto))
          )
    """)

    # Preserva conferências antigas: cada combinação projeto/trabalhador vira
    # uma solicitação "legada" somente uma vez. O histórico antigo continua
    # também intacto na tabela conferencias.
    antigos = cursor.execute("""
        SELECT c.projeto_id, c.trabalhador_id,
               MIN(c.conferido_em) AS primeiro_em,
               MAX(c.conferido_em) AS ultimo_em
        FROM conferencias c
        WHERE c.trabalhador_id IS NOT NULL
        GROUP BY c.projeto_id, c.trabalhador_id
    """).fetchall()

    for antigo in antigos:
        chave = f"conf-{antigo['projeto_id']}-{antigo['trabalhador_id']}"
        ja = cursor.execute(
            "SELECT id FROM solicitacoes_conferencia WHERE legacy_chave = ?",
            (chave,)
        ).fetchone()
        if ja:
            continue

        ult = cursor.execute("""
            SELECT c.*, u.nome AS conferidor
            FROM conferencias c
            LEFT JOIN usuarios u ON u.id = c.conferido_por
            WHERE c.projeto_id = ? AND c.trabalhador_id = ?
            ORDER BY c.conferido_em DESC, c.id DESC
            LIMIT 1
        """, (antigo["projeto_id"], antigo["trabalhador_id"])).fetchone()

        projeto = cursor.execute(
            "SELECT nome FROM projetos WHERE id = ?",
            (antigo["projeto_id"],)
        ).fetchone()

        status_antigo = cursor.execute("""
            SELECT status
            FROM projeto_status_trabalhador
            WHERE projeto_id = ? AND trabalhador_id = ?
        """, (antigo["projeto_id"], antigo["trabalhador_id"])).fetchone()

        criado_em = antigo["primeiro_em"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conferido_em = ult["conferido_em"] if ult else antigo["ultimo_em"]
        conferido_por = ult["conferido_por"] if ult else None
        nome_plano = (projeto["nome"] if projeto else "Projeto") + " — registro anterior"

        cur_legacy = cursor.execute("""
            INSERT INTO solicitacoes_conferencia
            (projeto_id, autor_id, nome_plano, caminho, descricao, estado,
             status_operacional, criado_em, atualizado_em, conferido_por,
             conferido_em, observacao_conferencia, legacy_chave)
            VALUES (?, ?, ?, '', ?, 'conferido', ?, ?, ?, ?, ?, '', ?)
        """, (
            antigo["projeto_id"],
            antigo["trabalhador_id"],
            nome_plano,
            "Migrado automaticamente do histórico de conferências da versão anterior.",
            status_antigo["status"] if status_antigo else "Em andamento",
            criado_em,
            conferido_em or criado_em,
            conferido_por,
            conferido_em,
            chave
        ))
        sid = cur_legacy.lastrowid
        cursor.execute("""
            INSERT INTO solicitacao_conferencia_historico
            (solicitacao_id, tipo, usuario_id, texto, criado_em)
            VALUES (?, 'migracao', ?, ?, ?)
        """, (
            sid,
            conferido_por,
            "Registro preservado da versão anterior.",
            conferido_em or criado_em
        ))

    conexao.commit()
    conexao.close()


# ============================================================
# USUÁRIOS
# ============================================================

def buscar_usuario(login, senha):
    conexao = conectar()

    usuario = conexao.execute("""
        SELECT *
        FROM usuarios
        WHERE login = ?
          AND ativo = 1
    """, (login,)).fetchone()

    if not usuario:
        conexao.close()
        return None

    senha_armazenada = usuario["senha"] or ""

    if "$" in senha_armazenada:
        # Já está no formato protegido (salt$hash).
        if not verificar_senha(senha, senha_armazenada):
            conexao.close()
            return None
    else:
        # Formato antigo (texto puro). Se a senha bater, aproveitamos
        # o login para migrar automaticamente para o formato protegido.
        if senha_armazenada != senha:
            conexao.close()
            return None
        conexao.execute(
            "UPDATE usuarios SET senha = ? WHERE id = ?",
            (gerar_hash_senha(senha), usuario["id"])
        )
        conexao.commit()

    conexao.close()
    return usuario


def alterar_senha(usuario_id, senha_atual, senha_nova):
    """Permite que o próprio usuário troque a senha, validando a senha atual
    (aceita tanto o formato antigo quanto o novo, migrando para o hash)."""
    conexao = conectar()
    usuario = conexao.execute(
        "SELECT senha FROM usuarios WHERE id = ?", (usuario_id,)
    ).fetchone()
    if not usuario:
        conexao.close()
        raise ValueError("User not found.")

    senha_armazenada = usuario["senha"] or ""
    if "$" in senha_armazenada:
        valida = verificar_senha(senha_atual, senha_armazenada)
    else:
        valida = senha_armazenada == senha_atual

    if not valida:
        conexao.close()
        raise ValueError("A senha atual está incorreta.")

    if len(senha_nova or "") < 6:
        conexao.close()
        raise ValueError("A nova senha deve ter pelo menos 6 caracteres.")

    conexao.execute(
        "UPDATE usuarios SET senha = ? WHERE id = ?",
        (gerar_hash_senha(senha_nova), usuario_id)
    )
    conexao.commit()
    conexao.close()


def buscar_usuarios_por_perfil(perfis):
    conexao = conectar()

    placeholders = ",".join("?" for _ in perfis)

    usuarios = conexao.execute(
        f"""
        SELECT *
        FROM usuarios
        WHERE perfil IN ({placeholders})
          AND ativo = 1
        ORDER BY nome
        """,
        tuple(perfis)
    ).fetchall()

    conexao.close()
    return usuarios


def buscar_trabalhadores():
    return buscar_usuarios_por_perfil(["worker"])


def buscar_planejadores():
    return buscar_usuarios_por_perfil(["planner"])


def buscar_usuarios_acompanhamento():
    return buscar_usuarios_por_perfil(
        ["worker", "planner"]
    )


# ============================================================
# PLANOS
# ============================================================

def buscar_plano(usuario_id, data_str):
    conexao = conectar()

    plano = conexao.execute("""
        SELECT *
        FROM planos
        WHERE usuario_id = ?
          AND data = ?
    """, (usuario_id, data_str)).fetchone()

    conexao.close()
    return plano


def salvar_plano(usuario_id, data_str, texto, autor_id=None):
    """Salva um plano. Quando autor_id é informado, somente o próprio usuário pode editar."""
    if autor_id is not None and int(autor_id) != int(usuario_id):
        raise PermissionError("Somente o próprio trabalhador pode editar este plano.")

    conexao = conectar()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conexao.execute("""
        INSERT INTO planos
        (usuario_id, data, texto, atualizado_em)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(usuario_id, data)
        DO UPDATE SET
            texto = excluded.texto,
            atualizado_em = excluded.atualizado_em
    """, (usuario_id, data_str, texto, agora))

    conexao.commit()
    conexao.close()


def buscar_planos_para_data(data_str):
    conexao = conectar()
    registros = conexao.execute("""
        SELECT p.*, u.nome, u.login
        FROM planos p
        INNER JOIN usuarios u ON u.id = p.usuario_id
        WHERE p.data = ?
          AND u.perfil = 'trabalhador'
          AND u.ativo = 1
          AND TRIM(p.texto) <> ''
        ORDER BY u.nome COLLATE NOCASE
    """, (data_str,)).fetchall()
    conexao.close()
    return registros


def contar_informacoes_nao_lidas(usuario_id):
    conexao = conectar()
    registro = conexao.execute("""
        SELECT COUNT(*) AS total
        FROM informacoes i
        LEFT JOIN informacoes_leitura il
          ON il.informacao_id = i.id
         AND il.usuario_id = ?
        WHERE i.trabalhador_id = ?
          AND il.id IS NULL
    """, (usuario_id, usuario_id)).fetchone()
    conexao.close()
    return int(registro["total"] if registro else 0)


# ============================================================
# EVENTOS DO CALENDÁRIO
# ============================================================

PRESENCA_GRUPO_1 = {"noah", "liam", "owen"}
PRESENCA_GRUPO_2 = {"alex", "mia", "chris", "sam", "priya"}
PRESENCA_SETOR_LOGINS = PRESENCA_GRUPO_1 | PRESENCA_GRUPO_2

def grupo_presenca(login):
    login = (login or "").strip().lower()
    if login in PRESENCA_GRUPO_1:
        return PRESENCA_GRUPO_1
    if login in PRESENCA_GRUPO_2:
        return PRESENCA_GRUPO_2
    return set()


def logins_eventos_visiveis(login, perfil):
    """
    Gestores/planejamento/chefia enxergam toda a equipe.
    Trabalhadores enxergam férias/presença do próprio bloco para conseguirem
    coordenar cobertura, além de seus próprios registros.
    """
    login = (login or "").strip().lower()
    if perfil in ("planner", "lead", "manager"):
        return None
    grupo = grupo_presenca(login)
    return grupo if grupo else {login}


def criar_evento_calendario(usuario_id, tipo, data_inicio, data_fim=None, hora="", observacao=""):
    data_fim = data_fim or data_inicio
    conexao = conectar()
    conexao.execute("""
        INSERT INTO eventos_calendario
        (usuario_id, tipo, data_inicio, data_fim, hora, observacao, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        usuario_id, tipo, data_inicio, data_fim, hora, observacao,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conexao.commit()
    conexao.close()

def buscar_eventos_periodo(data_inicio, data_fim, usuario_id=None):
    conexao = conectar()
    params = [data_fim, data_inicio]
    filtro = ""
    if usuario_id is not None:
        filtro = " AND e.usuario_id = ?"
        params.append(usuario_id)
    registros = conexao.execute(f"""
        SELECT e.*, u.nome, u.login, u.perfil
        FROM eventos_calendario e
        INNER JOIN usuarios u ON u.id = e.usuario_id
        WHERE e.data_inicio <= ?
          AND e.data_fim >= ?
          {filtro}
        ORDER BY e.data_inicio, u.nome COLLATE NOCASE, e.tipo
    """, tuple(params)).fetchall()
    conexao.close()
    return registros

def buscar_eventos_data(data_str, usuario_id=None):
    return buscar_eventos_periodo(data_str, data_str, usuario_id)

def usuario_em_ferias_na_data(usuario_id, data_str):
    conexao = conectar()
    reg = conexao.execute("""
        SELECT 1
        FROM eventos_calendario
        WHERE usuario_id = ?
          AND tipo = 'ferias'
          AND data_inicio <= ?
          AND data_fim >= ?
        LIMIT 1
    """, (usuario_id, data_str, data_str)).fetchone()
    conexao.close()
    return reg is not None


def pode_registrar_feierabend(usuario_id, data_str, hora):
    """Seg-qui: pelo menos uma pessoa do MESMO grupo deve permanecer até 16:30."""
    try:
        d = datetime.strptime(data_str, "%Y-%m-%d").date()
        h = datetime.strptime(hora, "%H:%M").time()
    except ValueError:
        return False, "Data ou hora inválida."

    conexao = conectar()
    usuario = conexao.execute(
        "SELECT id, nome, login FROM usuarios WHERE id = ? AND ativo = 1",
        (usuario_id,)
    ).fetchone()
    if not usuario:
        conexao.close()
        return False, "User not found."

    grupo = grupo_presenca(usuario["login"])
    if not grupo:
        conexao.close()
        return False, "Seu perfil não participa de um grupo de cobertura de Feierabend."

    # Sexta e fim de semana: sem trava de cobertura.
    if d.weekday() >= 4:
        conexao.close()
        return True, ""

    if h < datetime.strptime("15:00", "%H:%M").time():
        conexao.close()
        return False, "De segunda a quinta o Feierabend não pode ser registrado antes das 15:00."

    if h >= datetime.strptime("16:30", "%H:%M").time():
        conexao.close()
        return True, ""

    placeholders = ",".join("?" for _ in grupo)
    pessoas = conexao.execute(f"""
        SELECT id, nome, login
        FROM usuarios
        WHERE ativo = 1
          AND login IN ({placeholders})
        ORDER BY nome
    """, tuple(sorted(grupo))).fetchall()

    for pessoa in pessoas:
        if int(pessoa["id"]) == int(usuario_id):
            continue

        # Férias aprovadas removem a pessoa da cobertura.
        ferias = conexao.execute("""
            SELECT 1 FROM eventos_calendario
            WHERE usuario_id = ? AND tipo = 'ferias'
              AND data_inicio <= ? AND data_fim >= ?
            LIMIT 1
        """, (pessoa["id"], data_str, data_str)).fetchone()
        if ferias:
            continue

        saida = conexao.execute("""
            SELECT hora FROM eventos_calendario
            WHERE usuario_id = ? AND tipo = 'feierabend'
              AND data_inicio = ?
            ORDER BY id DESC LIMIT 1
        """, (pessoa["id"], data_str)).fetchone()

        # Sem registro = permanece; >=16:30 = cobre o setor.
        if not saida or not saida["hora"] or saida["hora"] >= "16:30":
            conexao.close()
            return True, ""

    nomes = " / ".join(p["nome"] for p in pessoas)
    conexao.close()
    return False, (
        "Não é possível registrar essa saída: com os registros atuais, ninguém "
        f"do seu grupo ({nomes}) permaneceria no setor até 16:30."
    )



def aprovar_ferias(evento_id, aprovador_id):
    """Marion transforma férias planejadas em férias aprovadas/confirmadas."""
    conexao = conectar()
    aprovador = conexao.execute(
        "SELECT login FROM usuarios WHERE id = ?",
        (aprovador_id,)
    ).fetchone()
    evento = conexao.execute(
        "SELECT * FROM eventos_calendario WHERE id = ?",
        (evento_id,)
    ).fetchone()
    if not aprovador or aprovador["login"].lower() != "priya":
        conexao.close()
        raise PermissionError("Somente Marion pode aprovar férias nesta versão.")
    if not evento or evento["tipo"] != "ferias_planejadas":
        conexao.close()
        raise ValueError("Este registro não é um planejamento de férias pendente.")
    conexao.execute(
        "UPDATE eventos_calendario SET tipo = 'ferias' WHERE id = ?",
        (evento_id,)
    )
    conexao.commit()
    conexao.close()


def excluir_evento_calendario(evento_id, usuario_id):
    conexao = conectar()
    evento = conexao.execute(
        "SELECT usuario_id FROM eventos_calendario WHERE id = ?",
        (evento_id,)
    ).fetchone()
    if not evento:
        conexao.close()
        return
    if int(evento["usuario_id"]) != int(usuario_id):
        conexao.close()
        raise PermissionError("Somente o autor pode excluir seu registro.")
    conexao.execute("DELETE FROM eventos_calendario WHERE id = ?", (evento_id,))
    conexao.commit()
    conexao.close()

def substituir_feierabend(usuario_id, data_str, hora, observacao=""):
    ok, motivo = pode_registrar_feierabend(usuario_id, data_str, hora)
    if not ok:
        raise ValueError(motivo)
    conexao = conectar()
    conexao.execute("DELETE FROM eventos_calendario WHERE usuario_id = ? AND tipo = 'feierabend' AND data_inicio = ?", (usuario_id, data_str))
    conexao.execute("""
        INSERT INTO eventos_calendario
        (usuario_id, tipo, data_inicio, data_fim, hora, observacao, criado_em)
        VALUES (?, 'feierabend', ?, ?, ?, ?, ?)
    """, (usuario_id, data_str, data_str, hora, observacao, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conexao.commit()
    conexao.close()


def buscar_planos_periodo(data_inicio, data_fim, usuario_id=None):
    conexao = conectar()
    params = [data_inicio, data_fim]
    filtro = ""
    if usuario_id is not None:
        filtro = " AND p.usuario_id = ?"
        params.append(usuario_id)
    regs = conexao.execute(f"""
        SELECT p.*, u.nome, u.login
        FROM planos p
        INNER JOIN usuarios u ON u.id = p.usuario_id
        WHERE p.data BETWEEN ? AND ?
          AND u.perfil = 'trabalhador'
          AND u.ativo = 1
          AND TRIM(p.texto) <> ''
          {filtro}
        ORDER BY p.data, u.nome COLLATE NOCASE
    """, tuple(params)).fetchall()
    conexao.close()
    return regs

# ============================================================
# TAREFAS
# ============================================================

def buscar_tarefas(usuario_id, somente_concluidas=False):
    conexao = conectar()

    if somente_concluidas:
        tarefas = conexao.execute("""
            SELECT *
            FROM tarefas
            WHERE usuario_id = ?
              AND concluida = 1
            ORDER BY data DESC, ordem ASC, id DESC
        """, (usuario_id,)).fetchall()
    else:
        tarefas = conexao.execute("""
            SELECT *
            FROM tarefas
            WHERE usuario_id = ?
              AND concluida = 0
            ORDER BY ordem ASC, data ASC, id ASC
        """, (usuario_id,)).fetchall()

    conexao.close()
    return tarefas


def buscar_tarefa(tarefa_id):
    conexao = conectar()

    tarefa = conexao.execute("""
        SELECT *
        FROM tarefas
        WHERE id = ?
    """, (tarefa_id,)).fetchone()

    conexao.close()
    return tarefa



def criar_tarefa(
    usuario_id,
    titulo,
    descricao,
    data_str,
    projeto="",
    prioridade="Normal",
    criada_por=None,
    projeto_id=None
):
    conexao = conectar()

    if projeto_id:
        p = conexao.execute("SELECT nome FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
        if p:
            projeto = p["nome"]

    maior_ordem = conexao.execute("""
        SELECT COALESCE(MAX(ordem), 0)
        FROM tarefas
        WHERE usuario_id = ?
          AND concluida = 0
    """, (usuario_id,)).fetchone()[0]

    conexao.execute("""
        INSERT INTO tarefas
        (
            usuario_id, titulo, descricao, data, concluida, criada_em,
            projeto, prioridade, ordem, criada_por, projeto_id
        )
        VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
    """, (
        usuario_id, titulo, descricao, data_str,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        projeto, prioridade, maior_ordem + 1, criada_por, projeto_id
    ))

    conexao.commit()
    conexao.close()



def atualizar_tarefa(
    tarefa_id,
    titulo,
    descricao,
    data_str,
    projeto="",
    prioridade="Normal",
    projeto_id=None
):
    conexao = conectar()

    if projeto_id:
        p = conexao.execute("SELECT nome FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
        if p:
            projeto = p["nome"]

    conexao.execute("""
        UPDATE tarefas
        SET titulo = ?,
            descricao = ?,
            data = ?,
            projeto = ?,
            prioridade = ?,
            projeto_id = ?
        WHERE id = ?
    """, (
        titulo, descricao, data_str, projeto, prioridade, projeto_id, tarefa_id
    ))

    conexao.commit()
    conexao.close()


def concluir_tarefa(tarefa_id):
    conexao = conectar()

    conexao.execute("""
        UPDATE tarefas
        SET concluida = 1
        WHERE id = ?
    """, (tarefa_id,))

    conexao.commit()
    conexao.close()


def reabrir_tarefa(tarefa_id):
    conexao = conectar()

    maior_ordem = conexao.execute("""
        SELECT COALESCE(MAX(ordem), 0)
        FROM tarefas
        WHERE concluida = 0
    """).fetchone()[0]

    conexao.execute("""
        UPDATE tarefas
        SET concluida = 0,
            ordem = ?
        WHERE id = ?
    """, (maior_ordem + 1, tarefa_id))

    conexao.commit()
    conexao.close()


def excluir_tarefa(tarefa_id):
    conexao = conectar()

    conexao.execute("""
        DELETE FROM tarefas
        WHERE id = ?
    """, (tarefa_id,))

    conexao.commit()
    conexao.close()


def mover_tarefa(tarefa_id, direcao):
    conexao = conectar()

    atual = conexao.execute("""
        SELECT id, ordem, usuario_id
        FROM tarefas
        WHERE id = ?
          AND concluida = 0
    """, (tarefa_id,)).fetchone()

    if not atual:
        conexao.close()
        return

    if direcao == "cima":
        vizinha = conexao.execute("""
            SELECT id, ordem
            FROM tarefas
            WHERE usuario_id = ?
              AND concluida = 0
              AND ordem < ?
            ORDER BY ordem DESC
            LIMIT 1
        """, (
            atual["usuario_id"],
            atual["ordem"]
        )).fetchone()

    else:
        vizinha = conexao.execute("""
            SELECT id, ordem
            FROM tarefas
            WHERE usuario_id = ?
              AND concluida = 0
              AND ordem > ?
            ORDER BY ordem ASC
            LIMIT 1
        """, (
            atual["usuario_id"],
            atual["ordem"]
        )).fetchone()

    if vizinha:
        conexao.execute("""
            UPDATE tarefas
            SET ordem = ?
            WHERE id = ?
        """, (
            vizinha["ordem"],
            atual["id"]
        ))

        conexao.execute("""
            UPDATE tarefas
            SET ordem = ?
            WHERE id = ?
        """, (
            atual["ordem"],
            vizinha["id"]
        ))

    conexao.commit()
    conexao.close()


# ============================================================
# PROJETOS
# ============================================================


def buscar_projetos(status="Ativo"):
    """
    Retorna projetos do cadastro central.
    Por padrão, somente os projetos Ativos aparecem nos seletores operacionais.
    Passe status=None para obter todos.
    """
    conexao = conectar()
    if status is None:
        projetos = conexao.execute("""
            SELECT p.*, u.nome AS criado_por_nome
            FROM projetos p
            LEFT JOIN usuarios u ON u.id = p.criado_por
            ORDER BY
                CASE p.status
                    WHEN 'Ativo' THEN 0
                    WHEN 'Pausado' THEN 1
                    WHEN 'Finalizado' THEN 2
                    WHEN 'Arquivado' THEN 3
                    ELSE 4
                END,
                p.nome COLLATE NOCASE
        """).fetchall()
    else:
        projetos = conexao.execute("""
            SELECT p.*, u.nome AS criado_por_nome
            FROM projetos p
            LEFT JOIN usuarios u ON u.id = p.criado_por
            WHERE p.status = ?
            ORDER BY p.nome COLLATE NOCASE
        """, (status,)).fetchall()
    conexao.close()
    return projetos


def buscar_projeto(projeto_id):
    conexao = conectar()

    projeto = conexao.execute("""
        SELECT *
        FROM projetos
        WHERE id = ?
    """, (projeto_id,)).fetchone()

    conexao.close()
    return projeto



def criar_projeto(
    nome,
    endereco="",
    caminho="",
    descricao="",
    criado_por=None,
    codigo="",
    cliente="",
    status="Ativo"
):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("O projeto precisa ter um nome.")

    conexao = conectar()
    existente = conexao.execute("""
        SELECT id FROM projetos
        WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
        LIMIT 1
    """, (nome,)).fetchone()
    if existente:
        conexao.close()
        raise ValueError("Já existe um projeto com esse nome.")

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ativo = 1 if status == "Ativo" else 0
    finalizado_em = agora if status in ("Finalizado", "Arquivado") else ""

    cursor = conexao.execute("""
        INSERT INTO projetos
        (nome, endereco, caminho, descricao, criado_por, criado_em, ativo,
         codigo, cliente, status, atualizado_em, finalizado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        nome, endereco or "", caminho or "", descricao or "", criado_por, agora,
        ativo, codigo or "", cliente or "", status, agora, finalizado_em
    ))
    projeto_id = cursor.lastrowid
    conexao.commit()
    conexao.close()
    return projeto_id



def atualizar_projeto(
    projeto_id,
    nome,
    endereco="",
    caminho="",
    descricao="",
    codigo="",
    cliente="",
    status="Ativo"
):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("O projeto precisa ter um nome.")

    conexao = conectar()
    duplicado = conexao.execute("""
        SELECT id FROM projetos
        WHERE LOWER(TRIM(nome)) = LOWER(TRIM(?))
          AND id <> ?
        LIMIT 1
    """, (nome, projeto_id)).fetchone()
    if duplicado:
        conexao.close()
        raise ValueError("Já existe outro projeto com esse nome.")

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ativo = 1 if status == "Ativo" else 0
    atual = conexao.execute(
        "SELECT status, finalizado_em FROM projetos WHERE id = ?",
        (projeto_id,)
    ).fetchone()
    if status in ("Finalizado", "Arquivado"):
        finalizado_em = (atual["finalizado_em"] if atual and atual["finalizado_em"] else agora)
    else:
        finalizado_em = ""

    conexao.execute("""
        UPDATE projetos
        SET nome = ?, endereco = ?, caminho = ?, descricao = ?,
            codigo = ?, cliente = ?, status = ?, ativo = ?,
            atualizado_em = ?, finalizado_em = ?
        WHERE id = ?
    """, (
        nome, endereco or "", caminho or "", descricao or "", codigo or "",
        cliente or "", status, ativo, agora, finalizado_em, projeto_id
    ))

    # Mantém o nome textual das tarefas sincronizado quando elas já estão ligadas por projeto_id.
    conexao.execute("""
        UPDATE tarefas SET projeto = ?
        WHERE projeto_id = ?
    """, (nome, projeto_id))

    conexao.commit()
    conexao.close()


def estatisticas_projeto(projeto_id):
    conexao = conectar()
    projeto = conexao.execute("SELECT nome FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
    nome = projeto["nome"] if projeto else ""

    abertas = conexao.execute("""
        SELECT COUNT(*) AS n FROM tarefas
        WHERE concluida = 0 AND (projeto_id = ? OR (projeto_id IS NULL AND projeto = ?))
    """, (projeto_id, nome)).fetchone()["n"]

    concluidas = conexao.execute("""
        SELECT COUNT(*) AS n FROM tarefas
        WHERE concluida = 1 AND (projeto_id = ? OR (projeto_id IS NULL AND projeto = ?))
    """, (projeto_id, nome)).fetchone()["n"]

    solicitacoes = conexao.execute("""
        SELECT COUNT(*) AS n FROM solicitacoes_conferencia
        WHERE projeto_id = ?
    """, (projeto_id,)).fetchone()["n"]

    pendentes = conexao.execute("""
        SELECT COUNT(*) AS n FROM solicitacoes_conferencia
        WHERE projeto_id = ? AND estado = 'aguardando'
    """, (projeto_id,)).fetchone()["n"]

    conversas = conexao.execute("""
        SELECT COUNT(*) AS n
        FROM tarefa_conversas c
        INNER JOIN tarefas t ON t.id = c.tarefa_id
        WHERE t.projeto_id = ? OR (t.projeto_id IS NULL AND t.projeto = ?)
    """, (projeto_id, nome)).fetchone()["n"]

    conexao.close()
    return {
        "abertas": int(abertas),
        "concluidas": int(concluidas),
        "solicitacoes": int(solicitacoes),
        "pendentes": int(pendentes),
        "conversas": int(conversas),
    }

def buscar_status_projeto_trabalhador(projeto_id, trabalhador_id):
    conexao=conectar(); r=conexao.execute("SELECT status FROM projeto_status_trabalhador WHERE projeto_id=? AND trabalhador_id=?",(projeto_id,trabalhador_id)).fetchone(); conexao.close()
    return r["status"] if r else "Em andamento"

def salvar_status_projeto_trabalhador(projeto_id, trabalhador_id, status):
    conexao=conectar(); agora=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conexao.execute("""INSERT INTO projeto_status_trabalhador(projeto_id,trabalhador_id,status,atualizado_em) VALUES(?,?,?,?)
                    ON CONFLICT(projeto_id,trabalhador_id) DO UPDATE SET status=excluded.status, atualizado_em=excluded.atualizado_em""",(projeto_id,trabalhador_id,status,agora)); conexao.commit(); conexao.close()

# ============================================================
# CONVERSAS / ALTERAÇÕES DE TAREFAS
# ============================================================

def buscar_conversas_tarefa(tarefa_id):
    conexao = conectar()
    rows = conexao.execute("""
        SELECT c.*, u.nome AS autor_nome
        FROM tarefa_conversas c
        LEFT JOIN usuarios u ON u.id = c.autor_id
        WHERE c.tarefa_id = ?
        ORDER BY c.criado_em DESC, c.id DESC
    """, (tarefa_id,)).fetchall()
    conexao.close()
    return rows

def buscar_anexos_conversa(conversa_id):
    conexao = conectar()
    rows = conexao.execute("SELECT * FROM tarefa_conversa_anexos WHERE conversa_id=? ORDER BY id", (conversa_id,)).fetchall()
    conexao.close()
    return rows

def adicionar_conversa_tarefa(tarefa_id, autor_id, participantes, texto, arquivos=None):
    conexao = conectar()
    cur = conexao.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO tarefa_conversas (tarefa_id, autor_id, participantes, texto, criado_em) VALUES (?, ?, ?, ?, ?)",
                (tarefa_id, autor_id, participantes, texto, agora))
    conversa_id = cur.lastrowid
    pasta = os.path.join(ANEXOS_DIR, "conversas", str(tarefa_id), str(conversa_id))
    os.makedirs(pasta, exist_ok=True)
    for origem in (arquivos or []):
        nome = os.path.basename(origem)
        destino = os.path.join(pasta, nome)
        base, ext = os.path.splitext(nome); n=1
        while os.path.exists(destino):
            destino = os.path.join(pasta, f"{base}_{n}{ext}"); n += 1
        shutil.copy2(origem, destino)
        cur.execute("INSERT INTO tarefa_conversa_anexos (conversa_id, nome, caminho, criado_em) VALUES (?, ?, ?, ?)",
                    (conversa_id, os.path.basename(destino), destino, agora))
    conexao.commit(); conexao.close()
    return conversa_id

# Matriz de conferência V7 é calculada por grupo_conferencia().
# Bene é conferidor geral e não pertence operacionalmente aos grupos.


def grupo_conferencia(login):
    login = (login or "").strip().lower()
    grupo_1 = {"noah", "liam", "owen"}
    grupo_2 = {"alex", "mia", "chris", "sam", "priya"}
    if login in grupo_1:
        return "grupo_1"
    if login in grupo_2:
        return "grupo_2"
    return None


def pode_ver_solicitacao(login_visualizador, login_autor):
    """Privacidade real: o registro só é entregue ao próprio grupo e ao Bene."""
    visualizador = (login_visualizador or "").strip().lower()
    autor = (login_autor or "").strip().lower()
    if not visualizador or not autor:
        return False
    if visualizador == "dana":
        return True
    if visualizador == autor:
        return True
    gv = grupo_conferencia(visualizador)
    ga = grupo_conferencia(autor)
    return gv is not None and gv == ga


def pode_conferir_plano(login_conferidor, login_autor):
    """Bene confere todos. Os demais só conferem outro membro do próprio grupo."""
    conferidor = (login_conferidor or "").strip().lower()
    autor = (login_autor or "").strip().lower()
    if not conferidor or not autor or conferidor == autor:
        return False
    if conferidor == "dana":
        return True
    gc = grupo_conferencia(conferidor)
    ga = grupo_conferencia(autor)
    return gc is not None and gc == ga

# ============================================================
# CONFERÊNCIAS
# ============================================================


def criar_solicitacao_conferencia(
    projeto_id,
    autor_id,
    nome_plano,
    caminho="",
    descricao=""
):
    conexao = conectar()
    autor = conexao.execute("SELECT login FROM usuarios WHERE id = ?", (autor_id,)).fetchone()
    if not autor:
        conexao.close()
        raise ValueError("User not found.")
    if autor["login"].lower() == "dana":
        conexao.close()
        raise PermissionError("Bene é conferidor geral e não envia planos para conferência.")

    projeto = conexao.execute("""
        SELECT id, status FROM projetos WHERE id = ?
    """, (projeto_id,)).fetchone()
    if not projeto:
        conexao.close()
        raise ValueError("Projeto não encontrado.")
    if projeto["status"] != "Ativo":
        conexao.close()
        raise ValueError("Somente projetos ativos podem receber novos planos para conferência.")

    nome_plano = (nome_plano or "").strip()
    if not nome_plano:
        conexao.close()
        raise ValueError("Informe o nome/tipo do plano.")

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conexao.execute("""
        INSERT INTO solicitacoes_conferencia
        (projeto_id, autor_id, nome_plano, caminho, descricao, estado,
         status_operacional, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?, 'aguardando', 'Em andamento', ?, ?)
    """, (projeto_id, autor_id, nome_plano, caminho or "", descricao or "", agora, agora))
    sid = cur.lastrowid
    conexao.execute("""
        INSERT INTO solicitacao_conferencia_historico
        (solicitacao_id, tipo, usuario_id, texto, criado_em)
        VALUES (?, 'envio', ?, 'Plano enviado para conferência.', ?)
    """, (sid, autor_id, agora))
    conexao.commit()
    conexao.close()
    return sid


def buscar_solicitacao_conferencia(solicitacao_id):
    conexao = conectar()
    reg = conexao.execute("""
        SELECT s.*, p.nome AS projeto_nome, p.caminho AS projeto_caminho,
               a.nome AS autor_nome, a.login AS autor_login,
               c.nome AS conferidor_nome, c.login AS conferidor_login
        FROM solicitacoes_conferencia s
        INNER JOIN projetos p ON p.id = s.projeto_id
        INNER JOIN usuarios a ON a.id = s.autor_id
        LEFT JOIN usuarios c ON c.id = s.conferido_por
        WHERE s.id = ?
    """, (solicitacao_id,)).fetchone()
    conexao.close()
    return reg


def buscar_solicitacoes_visiveis(login_visualizador):
    conexao = conectar()
    regs = conexao.execute("""
        SELECT s.*, p.nome AS projeto_nome, p.caminho AS projeto_caminho,
               p.status AS projeto_status,
               a.nome AS autor_nome, a.login AS autor_login,
               c.nome AS conferidor_nome, c.login AS conferidor_login
        FROM solicitacoes_conferencia s
        INNER JOIN projetos p ON p.id = s.projeto_id
        INNER JOIN usuarios a ON a.id = s.autor_id
        LEFT JOIN usuarios c ON c.id = s.conferido_por
        ORDER BY
            CASE s.estado WHEN 'aguardando' THEN 0 ELSE 1 END,
            s.atualizado_em DESC,
            s.id DESC
    """).fetchall()
    conexao.close()
    return [
        r for r in regs
        if pode_ver_solicitacao(login_visualizador, r["autor_login"])
    ]


def atualizar_status_solicitacao(solicitacao_id, autor_id, status):
    permitidos = {"Em andamento", "Ajustar após conferência", "Concluído"}
    if status not in permitidos:
        raise ValueError("Status inválido.")
    conexao = conectar()
    sol = conexao.execute("""
        SELECT autor_id FROM solicitacoes_conferencia WHERE id = ?
    """, (solicitacao_id,)).fetchone()
    if not sol:
        conexao.close()
        raise ValueError("Solicitação não encontrada.")
    if int(sol["autor_id"]) != int(autor_id):
        conexao.close()
        raise PermissionError("Somente o autor do plano pode alterar este status.")
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conexao.execute("""
        UPDATE solicitacoes_conferencia
        SET status_operacional = ?, atualizado_em = ?
        WHERE id = ?
    """, (status, agora, solicitacao_id))
    conexao.execute("""
        INSERT INTO solicitacao_conferencia_historico
        (solicitacao_id, tipo, usuario_id, texto, criado_em)
        VALUES (?, 'status', ?, ?, ?)
    """, (solicitacao_id, autor_id, f"Status alterado para: {status}", agora))
    conexao.commit()
    conexao.close()


def conferir_solicitacao(solicitacao_id, conferidor_id, observacao=""):
    conexao = conectar()
    sol = conexao.execute("""
        SELECT s.*, a.login AS autor_login
        FROM solicitacoes_conferencia s
        INNER JOIN usuarios a ON a.id = s.autor_id
        WHERE s.id = ?
    """, (solicitacao_id,)).fetchone()
    conf = conexao.execute("""
        SELECT id, nome, login FROM usuarios WHERE id = ?
    """, (conferidor_id,)).fetchone()

    if not sol or not conf:
        conexao.close()
        raise ValueError("Solicitação ou conferidor não encontrado.")
    if not pode_conferir_plano(conf["login"], sol["autor_login"]):
        conexao.close()
        raise PermissionError("Você não está no grupo autorizado para conferir este plano.")

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conexao.execute("""
        UPDATE solicitacoes_conferencia
        SET estado = 'conferido',
            conferido_por = ?,
            conferido_em = ?,
            observacao_conferencia = ?,
            atualizado_em = ?
        WHERE id = ?
    """, (conferidor_id, agora, observacao or "", agora, solicitacao_id))

    conexao.execute("""
        INSERT INTO solicitacao_conferencia_historico
        (solicitacao_id, tipo, usuario_id, texto, criado_em)
        VALUES (?, 'conferencia', ?, ?, ?)
    """, (
        solicitacao_id, conferidor_id,
        "Plano conferido." + (f" Observação: {observacao}" if observacao else ""),
        agora
    ))

    # Mantém a tabela antiga alimentada para compatibilidade com históricos já existentes.
    conexao.execute("""
        INSERT INTO conferencias
        (projeto_id, trabalhador_id, conferido_por, observacao, conferido_em)
        VALUES (?, ?, ?, ?, ?)
    """, (sol["projeto_id"], sol["autor_id"], conferidor_id, observacao or "", agora))

    conexao.commit()
    conexao.close()


def buscar_historico_solicitacao(solicitacao_id):
    conexao = conectar()
    regs = conexao.execute("""
        SELECT h.*, u.nome AS usuario_nome
        FROM solicitacao_conferencia_historico h
        LEFT JOIN usuarios u ON u.id = h.usuario_id
        WHERE h.solicitacao_id = ?
        ORDER BY h.criado_em DESC, h.id DESC
    """, (solicitacao_id,)).fetchall()
    conexao.close()
    return regs

def buscar_conferencias(projeto_id):
    conexao = conectar()

    registros = conexao.execute("""
        SELECT
            c.*,
            u.nome AS conferidor,
            t.nome AS trabalhador
        FROM conferencias c
        LEFT JOIN usuarios u
            ON u.id = c.conferido_por
        LEFT JOIN usuarios t
            ON t.id = c.trabalhador_id
        WHERE c.projeto_id = ?
        ORDER BY c.conferido_em DESC
    """, (projeto_id,)).fetchall()

    conexao.close()
    return registros


def buscar_ultima_conferencia(projeto_id, trabalhador_id):
    conexao = conectar()
    registro = conexao.execute("""
        SELECT c.*, u.nome AS conferidor
        FROM conferencias c
        LEFT JOIN usuarios u ON u.id = c.conferido_por
        WHERE c.projeto_id = ? AND c.trabalhador_id = ?
        ORDER BY c.conferido_em DESC, c.id DESC
        LIMIT 1
    """, (projeto_id, trabalhador_id)).fetchone()
    conexao.close()
    return registro


def registrar_conferencia(
    projeto_id,
    trabalhador_id,
    conferido_por,
    observacao=""
):
    conexao = conectar()

    conexao.execute("""
        INSERT INTO conferencias
        (
            projeto_id,
            trabalhador_id,
            conferido_por,
            observacao,
            conferido_em
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        projeto_id,
        trabalhador_id,
        conferido_por,
        observacao,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conexao.commit()
    conexao.close()


# ============================================================
# INFORMAÇÕES
# ============================================================

def criar_informacao(
    trabalhador_id,
    projeto_id,
    autor_id,
    titulo,
    texto,
    prioridade,
    caminho_pasta=""
):
    conexao = conectar()

    cursor = conexao.execute("""
        INSERT INTO informacoes
        (
            trabalhador_id,
            projeto_id,
            autor_id,
            titulo,
            texto,
            prioridade,
            caminho_pasta,
            criado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trabalhador_id,
        projeto_id,
        autor_id,
        titulo,
        texto,
        prioridade,
        caminho_pasta,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    informacao_id = cursor.lastrowid
    conexao.commit()
    conexao.close()
    return informacao_id


def buscar_informacoes_para_usuario(usuario_id):
    conexao = conectar()

    registros = conexao.execute("""
        SELECT
            i.*,
            u.nome AS autor_nome,
            p.nome AS projeto_nome
        FROM informacoes i
        LEFT JOIN usuarios u
            ON u.id = i.autor_id
        LEFT JOIN projetos p
            ON p.id = i.projeto_id
        WHERE i.trabalhador_id = ?
        ORDER BY i.criado_em DESC
    """, (usuario_id,)).fetchall()

    conexao.close()
    return registros


def buscar_todas_informacoes():
    conexao = conectar()

    registros = conexao.execute("""
        SELECT
            i.*,
            u.nome AS autor_nome,
            t.nome AS trabalhador_nome,
            p.nome AS projeto_nome
        FROM informacoes i
        LEFT JOIN usuarios u
            ON u.id = i.autor_id
        LEFT JOIN usuarios t
            ON t.id = i.trabalhador_id
        LEFT JOIN projetos p
            ON p.id = i.projeto_id
        ORDER BY i.criado_em DESC
    """).fetchall()

    conexao.close()
    return registros


def buscar_informacao(informacao_id):
    conexao = conectar()

    registro = conexao.execute("""
        SELECT
            i.*,
            u.nome AS autor_nome,
            t.nome AS trabalhador_nome,
            p.nome AS projeto_nome
        FROM informacoes i
        LEFT JOIN usuarios u
            ON u.id = i.autor_id
        LEFT JOIN usuarios t
            ON t.id = i.trabalhador_id
        LEFT JOIN projetos p
            ON p.id = i.projeto_id
        WHERE i.id = ?
    """, (informacao_id,)).fetchone()

    conexao.close()
    return registro


def marcar_informacao_lida(informacao_id, usuario_id):
    conexao = conectar()

    conexao.execute("""
        INSERT INTO informacoes_leitura
        (informacao_id, usuario_id, lido_em)
        VALUES (?, ?, ?)
        ON CONFLICT(informacao_id, usuario_id)
        DO UPDATE SET
            lido_em = excluded.lido_em
    """, (
        informacao_id,
        usuario_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conexao.commit()
    conexao.close()


def informacao_foi_lida(informacao_id, usuario_id):
    conexao = conectar()

    registro = conexao.execute("""
        SELECT *
        FROM informacoes_leitura
        WHERE informacao_id = ?
          AND usuario_id = ?
    """, (
        informacao_id,
        usuario_id
    )).fetchone()

    conexao.close()

    return registro is not None


# ============================================================
# ANEXOS
# ============================================================

def adicionar_anexo(
    informacao_id,
    projeto_id,
    origem
):
    nome = os.path.basename(origem)

    pasta = os.path.join(
        ANEXOS_DIR,
        str(informacao_id)
    )

    os.makedirs(pasta, exist_ok=True)

    destino = os.path.join(
        pasta,
        nome
    )

    # Evita conflito de nomes.
    if os.path.exists(destino):
        base, extensao = os.path.splitext(nome)

        contador = 2

        while os.path.exists(destino):
            novo_nome = f"{base}_{contador}{extensao}"
            destino = os.path.join(pasta, novo_nome)
            contador += 1

    shutil.copy2(
        origem,
        destino
    )

    conexao = conectar()

    conexao.execute("""
        INSERT INTO anexos
        (
            informacao_id,
            projeto_id,
            nome,
            caminho,
            criado_em
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        informacao_id,
        projeto_id,
        os.path.basename(destino),
        destino,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conexao.commit()
    conexao.close()


def criar_backup_banco():
    """Copia o arquivo do banco atual para uma pasta 'backups' com data/hora no nome."""
    pasta_backup = os.path.join(BASE_DIR, "backups")
    os.makedirs(pasta_backup, exist_ok=True)
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = os.path.join(pasta_backup, f"backup_{carimbo}.db")
    shutil.copy2(DB_FILE, destino)
    return destino


def buscar_anexos(informacao_id):
    conexao = conectar()

    anexos = conexao.execute("""
        SELECT *
        FROM anexos
        WHERE informacao_id = ?
        ORDER BY nome
    """, (informacao_id,)).fetchall()

    conexao.close()
    return anexos


# ============================================================
# APLICAÇÃO
# ============================================================

class MeuOrganizador:


    def __init__(self, root):
        self.root = root
        self.usuario = None
        self.menu_atual = None
        self.trabalhadores = []
        self.trabalhador_selecionado = None
        self.planejadores = []
        self.gestor_selecionado = None
        self._modo_sidebar = None
        self._resize_after = None

        hoje = date.today()
        self.data_atual = hoje.strftime("%Y-%m-%d")
        self.calendario_ano = hoje.year
        self.calendario_mes = hoje.month
        self.tarefa_selecionada = None

        self.root.title(APP_TITLE)
        self.root.geometry("1200x760")
        # Evita o ponto em que componentes ficam sobrepostos; abaixo disso
        # usamos rolagem/compactação em vez de "sumir" com conteúdo.
        self.root.minsize(760, 520)
        self.root.configure(bg=BG)
        self.configurar_estilos()
        self.mostrar_login()

    # ========================================================
    # ESTILO
    # ========================================================


    def configurar_estilos(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Treeview",
            background=WHITE,
            foreground=TEXT,
            fieldbackground=WHITE,
            rowheight=42,
            borderwidth=0,
            font=("Segoe UI", 10)
        )
        style.configure(
            "Treeview.Heading",
            background="#EDF2F7",
            foreground=TEXT,
            font=("Segoe UI Semibold", 10),
            relief="flat"
        )
        style.map(
            "Treeview",
            background=[("selected", BLUE_LIGHT)],
            foreground=[("selected", TEXT)]
        )

        style.configure(
            "Modern.TCombobox",
            padding=7,
            relief="flat",
            borderwidth=1,
            fieldbackground=WHITE,
            background=WHITE,
            foreground=TEXT,
            arrowcolor=BLUE_DARK
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", WHITE)],
            background=[("readonly", WHITE), ("active", BLUE_LIGHT)],
            selectbackground=[("readonly", WHITE)],
            selectforeground=[("readonly", TEXT)]
        )

        # Scrollbars modernas: finas, sem setas e sem o visual clássico do Windows.
        # O layout abaixo mantém somente trilho + alça. A rolagem pelo mouse continua normal.
        style.layout(
            "Modern.Vertical.TScrollbar",
            [(
                "Vertical.Scrollbar.trough",
                {
                    "sticky": "ns",
                    "children": [(
                        "Vertical.Scrollbar.thumb",
                        {"expand": "1", "sticky": "nswe"}
                    )]
                }
            )]
        )
        style.configure(
            "Modern.Vertical.TScrollbar",
            gripcount=0,
            relief="flat",
            borderwidth=0,
            arrowsize=0,
            width=9,
            background="#94A3B8",
            troughcolor=BG,
            bordercolor=BG,
            lightcolor="#94A3B8",
            darkcolor="#94A3B8"
        )
        style.map(
            "Modern.Vertical.TScrollbar",
            background=[("active", "#64748B"), ("pressed", BLUE_DARK)],
            lightcolor=[("active", "#64748B"), ("pressed", BLUE_DARK)],
            darkcolor=[("active", "#64748B"), ("pressed", BLUE_DARK)]
        )

        style.layout(
            "Modern.Horizontal.TScrollbar",
            [(
                "Horizontal.Scrollbar.trough",
                {
                    "sticky": "ew",
                    "children": [(
                        "Horizontal.Scrollbar.thumb",
                        {"expand": "1", "sticky": "nswe"}
                    )]
                }
            )]
        )
        style.configure(
            "Modern.Horizontal.TScrollbar",
            gripcount=0,
            relief="flat",
            borderwidth=0,
            arrowsize=0,
            width=9,
            background="#94A3B8",
            troughcolor=BG,
            bordercolor=BG,
            lightcolor="#94A3B8",
            darkcolor="#94A3B8"
        )
        style.map(
            "Modern.Horizontal.TScrollbar",
            background=[("active", "#64748B"), ("pressed", BLUE_DARK)],
            lightcolor=[("active", "#64748B"), ("pressed", BLUE_DARK)],
            darkcolor=[("active", "#64748B"), ("pressed", BLUE_DARK)]
        )

        style.configure(
            "Modern.TNotebook",
            background=WHITE,
            borderwidth=0,
            tabmargins=(0, 0, 0, 0)
        )
        style.configure(
            "Modern.TNotebook.Tab",
            padding=(18, 9),
            font=("Segoe UI Semibold", 9),
            background="#EEF2F7",
            foreground=TEXT_LIGHT,
            borderwidth=0
        )
        style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", WHITE), ("active", BLUE_LIGHT)],
            foreground=[("selected", BLUE_DARK), ("active", BLUE_DARK)]
        )

    # ========================================================
    # LIMPEZA
    # ========================================================

    def limpar_tela(self):

        for widget in self.root.winfo_children():
            widget.destroy()

    def limpar_conteudo(self):

        for widget in self.conteudo.winfo_children():
            widget.destroy()

    # ========================================================
    # LOGIN
    # ========================================================


    def mostrar_login(self):
        self.limpar_tela()
        self.root.geometry("1050x650")

        fundo = tk.Frame(self.root, bg=BG)
        fundo.pack(fill="both", expand=True)
        fundo.grid_rowconfigure(0, weight=1)
        fundo.grid_columnconfigure(0, weight=4, minsize=310)
        fundo.grid_columnconfigure(1, weight=6, minsize=390)

        esquerda = tk.Frame(fundo, bg=SIDEBAR)
        esquerda.grid(row=0, column=0, sticky="nsew")
        direita = tk.Frame(fundo, bg=WHITE)
        direita.grid(row=0, column=1, sticky="nsew")

        marca = tk.Frame(esquerda, bg=SIDEBAR)
        marca.pack(fill="both", expand=True, padx=28, pady=45)

        tk.Label(
            marca,
            text="Planejamento de Construção",
            bg=SIDEBAR,
            fg=WHITE,
            font=("Segoe UI", 21, "bold"),
            justify="left",
            wraplength=330
        ).pack(anchor="center", pady=(50, 4))
        tk.Label(
            marca,
            text="Team Planning & Projects",
            bg=SIDEBAR,
            fg="#94A3B8",
            font=("Segoe UI", 10)
        ).pack(anchor="center", pady=(0, 18))

        selo = tk.Frame(marca, bg=WHITE, padx=16, pady=10)
        selo.pack(anchor="center")
        tk.Label(selo, text="BuildTrack", bg=WHITE, fg=BLUE,
                 font=("Segoe UI", 16, "bold")).pack()

        tk.Label(
            marca,
            text="Plan • Track • Deliver",
            bg=SIDEBAR,
            fg="#64748B",
            font=("Segoe UI", 9)
        ).pack(anchor="center", pady=20)

        # Sem largura fixa: o formulário acompanha a janela e não invade o painel esquerdo.
        card_externo = tk.Frame(direita, bg=WHITE)
        card_externo.pack(fill="both", expand=True, padx=42, pady=40)
        card = tk.Frame(card_externo, bg=WHITE)
        card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.86)

        tk.Label(card, text="Welcome", bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 26, "bold")).pack(anchor="w")
        tk.Label(card, text="Sign in to access your workspace.",
                 bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 28))

        tk.Label(card, text="Username", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="w")
        self.login_entry = tk.Entry(card, font=("Segoe UI", 12), relief="solid", bd=1)
        self.login_entry.pack(fill="x", ipady=9, pady=(5, 16))

        tk.Label(card, text="Password", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="w")
        self.senha_entry = tk.Entry(card, font=("Segoe UI", 12), relief="solid", bd=1, show="●")
        self.senha_entry.pack(fill="x", ipady=9, pady=(5, 22))

        tk.Button(
            card, text="ENTRAR", bg=BLUE, fg=WHITE,
            activebackground=BLUE_DARK, activeforeground=WHITE,
            relief="flat", bd=0, cursor="hand2",
            font=("Segoe UI Semibold", 11), command=self.fazer_login
        ).pack(fill="x", ipady=11)

        self.login_entry.focus_set()
        self.root.bind("<Return>", self.login_enter)

    def login_enter(self, event=None):
        self.fazer_login()

    def fazer_login(self):

        login = self.login_entry.get().strip()
        senha = self.senha_entry.get()

        if not login or not senha:

            messagebox.showwarning(
                "Login",
                "Digite o usuário e a senha."
            )

            return

        usuario = buscar_usuario(
            login,
            senha
        )

        if not usuario:

            messagebox.showerror(
                "Login",
                "Incorrect username or password."
            )

            self.senha_entry.delete(
                0,
                "end"
            )

            self.senha_entry.focus_set()

            return

        self.root.unbind("<Return>")

        self.usuario = usuario

        self.trabalhadores = buscar_trabalhadores()

        if self.trabalhadores:

            self.trabalhador_selecionado = self.trabalhadores[0]

        self.mostrar_app()

    # ========================================================
    # APLICAÇÃO PRINCIPAL
    # ========================================================


    def mostrar_app(self):
        self.limpar_tela()
        self.root.geometry("1200x760")

        principal = tk.Frame(self.root, bg=BG)
        principal.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(principal, bg=SIDEBAR, width=225)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        area_scroll = tk.Frame(principal, bg=BG)
        area_scroll.pack(side="left", fill="both", expand=True)

        self.canvas_conteudo = tk.Canvas(
            area_scroll, bg=BG, highlightthickness=0, bd=0
        )
        self.scrollbar_conteudo = ttk.Scrollbar(
            area_scroll, orient="vertical",
            command=self.canvas_conteudo.yview,
            style="Modern.Vertical.TScrollbar"
        )
        self.scrollbar_horizontal = ttk.Scrollbar(
            area_scroll, orient="horizontal",
            command=self.canvas_conteudo.xview,
            style="Modern.Horizontal.TScrollbar"
        )
        self.canvas_conteudo.configure(
            yscrollcommand=self.scrollbar_conteudo.set,
            xscrollcommand=self.scrollbar_horizontal.set
        )

        self.scrollbar_conteudo.pack(side="right", fill="y")
        self.scrollbar_horizontal.pack(side="bottom", fill="x")
        self.canvas_conteudo.pack(side="left", fill="both", expand=True)

        self.conteudo = tk.Frame(self.canvas_conteudo, bg=BG)
        self._conteudo_window = self.canvas_conteudo.create_window(
            (0, 0), window=self.conteudo, anchor="nw"
        )

        def sincronizar(event=None):
            if not self.canvas_conteudo.winfo_exists():
                return
            canvas_w = max(self.canvas_conteudo.winfo_width(), 1)
            pedido = max(self.conteudo.winfo_reqwidth(), 1)

            # A tela acompanha a largura quando consegue. Se algum formulário/tabela
            # realmente precisar de mais espaço, preserva a largura requisitada e
            # a barra horizontal passa a funcionar em vez de cortar o conteúdo.
            largura = max(canvas_w, pedido if pedido > canvas_w else canvas_w)
            self.canvas_conteudo.itemconfigure(self._conteudo_window, width=largura)
            self.canvas_conteudo.configure(scrollregion=self.canvas_conteudo.bbox("all"))

        self.conteudo.bind("<Configure>", sincronizar)
        self.canvas_conteudo.bind("<Configure>", sincronizar)

        def rolar(event):
            if event.delta:
                self.canvas_conteudo.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas_conteudo.bind_all("<MouseWheel>", rolar)

        self.criar_sidebar()
        self.root.bind("<Configure>", self.ajustar_layout_responsivo, add="+")
        self.mostrar_inicio()
        self.root.after(50, self.ajustar_layout_responsivo)


    def ajustar_layout_responsivo(self, event=None):
        if not hasattr(self, "sidebar") or not self.sidebar.winfo_exists():
            return

        largura = self.root.winfo_width()

        if largura < 860:
            modo = "compacto"
            sidebar_w = 76
        elif largura < 1080:
            modo = "medio"
            sidebar_w = 178
        else:
            modo = "normal"
            sidebar_w = 225

        if self._modo_sidebar != modo:
            self._modo_sidebar = modo
            self.sidebar.configure(width=sidebar_w)

            if hasattr(self, "sidebar_titulo"):
                if modo == "compacto":
                    self.sidebar_titulo.configure(text="PC", font=("Segoe UI", 14, "bold"), justify="center")
                    self.sidebar_subtitulo.configure(text="")
                    self.sidebar_logos_frame.pack_forget()
                    self.sidebar_topo.pack_configure(padx=8, pady=(18, 18))
                elif modo == "medio":
                    self.sidebar_titulo.configure(text="Planejamento\nde Construção", font=("Segoe UI", 11, "bold"), justify="left")
                    self.sidebar_subtitulo.configure(text="Planung & Projetos", font=("Segoe UI", 7))
                    if not self.sidebar_logos_frame.winfo_ismapped():
                        self.sidebar_logos_frame.pack(fill="x", pady=(7, 0))
                    self.sidebar_topo.pack_configure(padx=12, pady=(20, 22))
                else:
                    self.sidebar_titulo.configure(text="Planejamento de\nConstrução", font=("Segoe UI", 13, "bold"), justify="left")
                    self.sidebar_subtitulo.configure(text="Team Planning & Projects", font=("Segoe UI", 8))
                    if not self.sidebar_logos_frame.winfo_ismapped():
                        self.sidebar_logos_frame.pack(fill="x", pady=(7, 0))
                    self.sidebar_topo.pack_configure(padx=20, pady=(25, 30))

            for chave, botao in getattr(self, "botoes_menu", {}).items():
                icone, texto = self.menu_meta.get(chave, ("•", chave))
                if modo == "compacto":
                    botao.configure(
                        text=f"{icone}",
                        anchor="center",
                        font=("Segoe UI Symbol", 11),
                        padx=4, pady=12
                    )
                    botao.pack_configure(padx=8)
                elif modo == "medio":
                    botao.configure(
                        text=f" {icone}  {texto}",
                        anchor="w",
                        font=("Segoe UI", 9),
                        padx=10, pady=11
                    )
                    botao.pack_configure(padx=8)
                else:
                    botao.configure(
                        text=f"  {icone}    {texto}",
                        anchor="w",
                        font=("Segoe UI", 10),
                        padx=18, pady=12
                    )
                    botao.pack_configure(padx=10)

            if hasattr(self, "sidebar_usuario_nome"):
                if modo == "compacto":
                    nome = (self.usuario["nome"][:2] if self.usuario else "")
                    self.sidebar_usuario_nome.configure(text=nome, anchor="center")
                    self.sidebar_usuario_perfil.configure(text="")
                    self.sidebar_sair.configure(text="↪", anchor="center")
                    self.sidebar_usuario_frame.pack_configure(padx=8)
                else:
                    self.sidebar_usuario_nome.configure(text=self.usuario["nome"], anchor="w")
                    perfil_nomes = {"worker": "WORKER", "planner": "PLANNER",
                                    "lead": "LEAD", "manager": "MANAGER"}
                    self.sidebar_usuario_perfil.configure(
                        text=perfil_nomes.get(self.usuario["perfil"], self.usuario["perfil"].upper())
                    )
                    self.sidebar_sair.configure(text="Log out", anchor="w")
                    self.sidebar_usuario_frame.pack_configure(padx=12)

        self.sidebar.configure(width=sidebar_w)
        self._organizar_cards_inicio(largura)

    # ========================================================
    # SIDEBAR
    # ========================================================


    def _organizar_cards_inicio(self, largura=None):
        """Reorganiza os cards do início em 1/2/4 colunas conforme a largura."""
        parent = getattr(self, "cards_inicio", None)
        if not parent or not parent.winfo_exists():
            return
        largura = largura or self.root.winfo_width()
        if largura < 860:
            colunas = 1
        elif largura < 1180:
            colunas = 2
        else:
            colunas = 4

        cards = getattr(parent, "_cards", [])
        for c in range(4):
            parent.grid_columnconfigure(c, weight=0)
        for i, card in enumerate(cards):
            row = i // colunas
            col = i % colunas
            card.grid(row=row, column=col, sticky="nsew", padx=(0, 10), pady=(0, 10))
            parent.grid_columnconfigure(col, weight=1)


    def criar_sidebar(self):
        self.sidebar_topo = tk.Frame(self.sidebar, bg=SIDEBAR)
        self.sidebar_topo.pack(fill="x", padx=20, pady=(25, 30))

        marca = tk.Frame(self.sidebar_topo, bg=SIDEBAR)
        marca.pack(fill="x")

        self.sidebar_titulo = tk.Label(
            marca, text="Planejamento de\nConstrução", bg=SIDEBAR, fg=WHITE,
            font=("Segoe UI", 13, "bold"), justify="left"
        )
        self.sidebar_titulo.pack(anchor="w")

        self.sidebar_subtitulo = tk.Label(
            marca, text="Team Planning & Projects", bg=SIDEBAR, fg="#94A3B8",
            font=("Segoe UI", 8)
        )
        self.sidebar_subtitulo.pack(anchor="w", pady=(3, 0))

        self.sidebar_logos_frame = tk.Frame(marca, bg=SIDEBAR)
        self.sidebar_logos_frame.pack(fill="x", pady=(7, 0))
        tk.Label(self.sidebar_logos_frame, text="BuildTrack", bg=SIDEBAR, fg=BLUE,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.botoes_menu = {}
        self.menu_meta = {}

        self.adicionar_botao_menu("inicio", "⌂", "Home", self.mostrar_inicio)
        self.adicionar_botao_menu("tarefas", "✓", "Tasks", self.mostrar_tarefas)
        self.adicionar_botao_menu("projetos", "▤", "Projects", self.mostrar_projetos)
        self.adicionar_botao_menu("conferencias", "✓", "Plans to review", self.mostrar_conferencias)

        if self.usuario["perfil"] in ("worker", "planner", "lead"):
            self.adicionar_botao_menu("informacoes", "ℹ", "Messages", self.mostrar_informacoes)

        self.adicionar_botao_menu("calendario", "▣", "Calendar", self.mostrar_calendario)
        self.adicionar_botao_menu("antigas", "◷", "Archive", self.mostrar_antigas)

        self.sidebar_spacer = tk.Frame(self.sidebar, bg=SIDEBAR)
        self.sidebar_spacer.pack(fill="both", expand=True)

        self.sidebar_usuario_frame = tk.Frame(self.sidebar, bg="#172033")
        self.sidebar_usuario_frame.pack(fill="x", padx=12, pady=12)

        perfil_nomes = {
            "worker": "WORKER",
            "planner": "PLANNER",
            "lead": "LEAD",
            "manager": "MANAGER"
        }

        self.sidebar_usuario_nome = tk.Label(
            self.sidebar_usuario_frame, text=self.usuario["nome"], bg="#172033", fg=WHITE,
            font=("Segoe UI Semibold", 10)
        )
        self.sidebar_usuario_nome.pack(anchor="w", padx=12, pady=(10, 0))

        self.sidebar_usuario_perfil = tk.Label(
            self.sidebar_usuario_frame,
            text=perfil_nomes.get(self.usuario["perfil"], self.usuario["perfil"].upper()),
            bg="#172033", fg="#94A3B8", font=("Segoe UI", 8)
        )
        self.sidebar_usuario_perfil.pack(anchor="w", padx=12)

        self.sidebar_trocar_senha = tk.Button(
            self.sidebar_usuario_frame, text="Change password", bg="#172033", fg="#CBD5E1",
            activebackground="#243047", activeforeground=WHITE, relief="flat", bd=0,
            cursor="hand2", anchor="w", command=self.abrir_troca_senha
        )
        self.sidebar_trocar_senha.pack(fill="x", padx=7, pady=(8, 0), ipady=5)

        if self.usuario["perfil"] in ("planner", "lead", "manager"):
            self.sidebar_backup = tk.Button(
                self.sidebar_usuario_frame, text="Backup database", bg="#172033", fg="#CBD5E1",
                activebackground="#243047", activeforeground=WHITE, relief="flat", bd=0,
                cursor="hand2", anchor="w", command=self.fazer_backup_banco
            )
            self.sidebar_backup.pack(fill="x", padx=7, pady=(0, 0), ipady=5)

        self.sidebar_sair = tk.Button(
            self.sidebar_usuario_frame, text="Log out", bg="#172033", fg="#CBD5E1",
            activebackground="#243047", activeforeground=WHITE, relief="flat", bd=0,
            cursor="hand2", anchor="w", command=self.logout
        )
        self.sidebar_sair.pack(fill="x", padx=7, pady=8, ipady=5)


    def adicionar_botao_menu(self, chave, icone, texto, comando):
        self.menu_meta[chave] = (icone, texto)
        botao = tk.Button(
            self.sidebar,
            text=f"  {icone}    {texto}",
            bg=SIDEBAR,
            fg="#CBD5E1",
            activebackground="#1E293B",
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            anchor="w",
            cursor="hand2",
            font=("Segoe UI", 10),
            padx=18,
            pady=12,
            command=lambda: self.clicar_menu(chave, comando)
        )
        botao.pack(fill="x", padx=10, pady=2)
        self.botoes_menu[chave] = botao

    def clicar_menu(
        self,
        chave,
        comando
    ):

        if self.menu_atual == chave:

            self.menu_atual = None

            self.limpar_conteudo()

            self.marcar_menu(None)

            return

        self.menu_atual = chave

        self.marcar_menu(chave)

        comando()

    def marcar_menu(self, ativo):

        for chave, botao in self.botoes_menu.items():

            if chave == ativo:

                botao.configure(
                    bg=BLUE,
                    fg=WHITE
                )

            else:

                botao.configure(
                    bg=SIDEBAR,
                    fg="#CBD5E1"
                )

    # ========================================================
    # CABEÇALHO
    # ========================================================

    def titulo_pagina(
        self,
        titulo,
        subtitulo=""
    ):

        cabecalho = tk.Frame(
            self.conteudo,
            bg=BG
        )

        cabecalho.pack(
            fill="x",
            padx=30,
            pady=(25, 15)
        )

        tk.Label(
            cabecalho,
            text=titulo,
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 22, "bold")
        ).pack(anchor="w")

        if subtitulo:

            tk.Label(
                cabecalho,
                text=subtitulo,
                bg=BG,
                fg=TEXT_LIGHT,
                font=("Segoe UI", 10)
            ).pack(
                anchor="w",
                pady=(3, 0)
            )

    # ========================================================
    # ALVO ATUAL
    # ========================================================

    def alvo_atual(self):

        perfil = self.usuario["perfil"]

        if perfil in (
            "lead",
            "planner",
            "manager"
        ):

            return self.trabalhador_selecionado

        return self.usuario

    # ========================================================
    # SELETOR
    # ========================================================

    def criar_seletor_trabalhador(self, parent):

        if self.usuario["perfil"] not in (
            "lead",
            "planner",
            "manager"
        ):
            return

        barra = tk.Frame(
            parent,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        barra.pack(
            fill="x",
            padx=30,
            pady=(0, 12)
        )

        tk.Label(
            barra,
            text="👤 Trabalhador:",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI Semibold", 10)
        ).pack(
            side="left",
            padx=(15, 8),
            pady=10
        )

        nomes = [
            f"{u['nome']} ({u['login']})"
            for u in self.trabalhadores
        ]

        self.combo_funcionario = ttk.Combobox(
            barra,
            style="Modern.TCombobox",
            values=nomes,
            state="readonly",
            width=28
        )

        self.combo_funcionario.pack(
            side="left",
            padx=5,
            pady=8
        )

        indice = 0

        if self.trabalhador_selecionado:

            for i, trabalhador in enumerate(
                self.trabalhadores
            ):

                if (
                    trabalhador["id"]
                    == self.trabalhador_selecionado["id"]
                ):

                    indice = i
                    break

        if nomes:
            self.combo_funcionario.current(indice)

        self.combo_funcionario.bind(
            "<<ComboboxSelected>>",
            self.funcionario_alterado
        )

    def funcionario_alterado(
        self,
        event=None
    ):

        indice = self.combo_funcionario.current()

        if 0 <= indice < len(self.trabalhadores):

            self.trabalhador_selecionado = (
                self.trabalhadores[indice]
            )

        if self.menu_atual == "tarefas":
            self.mostrar_tarefas()

        elif self.menu_atual == "calendario":
            self.mostrar_calendario()

        elif self.menu_atual == "antigas":
            self.mostrar_antigas()

        elif self.menu_atual == "conferencias":
            self.mostrar_conferencias()

        elif self.menu_atual == "informacoes":
            self.mostrar_informacoes()

        else:
            self.mostrar_inicio()

    # ========================================================
    # INÍCIO
    # ========================================================

    def mostrar_inicio(self):

        self.menu_atual = "inicio"

        self.marcar_menu("inicio")

        self.limpar_conteudo()

        alvo = self.alvo_atual()

        nome = (
            alvo["nome"]
            if alvo
            else self.usuario["nome"]
        )

        self.titulo_pagina(
            "Bom dia, " + nome + " 👋",
            "Aqui está o seu espaço de trabalho."
        )

        if self.usuario["login"] == "priya":
            self.criar_painel_marion(self.conteudo)

        self.criar_seletor_trabalhador(
            self.conteudo
        )

        area = tk.Frame(
            self.conteudo,
            bg=BG
        )

        area.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=10
        )

        # ----------------------------------------------------
        # CARDS
        # ----------------------------------------------------

        cards = tk.Frame(
            area,
            bg=BG
        )

        cards.pack(fill="x")
        self.cards_inicio = cards

        tarefas = (
            buscar_tarefas(alvo["id"])
            if alvo
            else []
        )

        antigas = (
            buscar_tarefas(
                alvo["id"],
                True
            )
            if alvo
            else []
        )

        self.criar_card(
            cards,
            "TAREFAS ABERTAS",
            str(len(tarefas)),
            BLUE
        )

        self.criar_card(
            cards,
            "CONCLUÍDAS",
            str(len(antigas)),
            GREEN
        )

        plano = (
            buscar_plano(
                alvo["id"],
                self.data_atual
            )
            if alvo
            else None
        )

        plano_texto = (
            plano["texto"]
            if plano
            else ""
        )

        self.criar_card(
            cards,
            "PLANO DE HOJE",
            "Preenchido"
            if plano_texto.strip()
            else "Vazio",
            ORANGE
        )

        if self.usuario["perfil"] == "worker":
            self.criar_card(
                cards,
                "INFORMAÇÕES NOVAS",
                str(contar_informacoes_nao_lidas(self.usuario["id"])),
                PURPLE
            )

        # ----------------------------------------------------
        # PLANO DO DIA COMPACTO
        # ----------------------------------------------------

        painel = tk.Frame(
            area,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        painel.pack(
            fill="x",
            pady=(20, 0)
        )

        cab = tk.Frame(
            painel,
            bg=WHITE
        )

        cab.pack(
            fill="x",
            padx=20,
            pady=(15, 5)
        )

        tk.Label(
            cab,
            text="📝  Plano do dia",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI", 15, "bold")
        ).pack(side="left")

        tk.Label(
            cab,
            text=self.formatar_data(
                self.data_atual
            ),
            bg=WHITE,
            fg=TEXT_LIGHT,
            font=("Segoe UI", 9)
        ).pack(
            side="left",
            padx=12
        )

        pode_editar_hoje = (
            self.usuario["perfil"] == "worker"
            and alvo is not None
            and int(alvo["id"]) == int(self.usuario["id"])
        )

        if plano_texto.strip():
            texto_frame = tk.Frame(painel, bg="#FBFCFE")
            texto_frame.pack(fill="x", padx=20, pady=(4, 15))
            tk.Label(
                texto_frame,
                text=plano_texto,
                bg="#FBFCFE",
                fg=TEXT,
                justify="left",
                anchor="w",
                wraplength=850,
                font=("Segoe UI", 11)
            ).pack(side="left", fill="x", expand=True, padx=12, pady=12)

            if pode_editar_hoje:
                tk.Button(
                    texto_frame,
                    text="✎",
                    bg=BLUE_LIGHT,
                    fg=BLUE_DARK,
                    activebackground="#DCEAFF",
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    font=("Segoe UI", 12, "bold"),
                    command=self.editar_plano
                ).pack(side="right", padx=10, pady=10, ipadx=8, ipady=5)

        elif pode_editar_hoje:
            tk.Label(
                painel,
                text="Escreva rapidamente o que você pretende fazer hoje.",
                bg=WHITE,
                fg=TEXT_LIGHT,
                font=("Segoe UI", 9)
            ).pack(anchor="w", padx=20, pady=(0, 8))

            self.plano_text = tk.Text(
                painel,
                height=3,
                bg="#FBFCFE",
                fg=TEXT,
                font=("Segoe UI", 10),
                relief="solid",
                bd=1,
                wrap="word",
                padx=10,
                pady=8
            )
            self.plano_text.pack(fill="x", padx=20)

            tk.Button(
                painel,
                text="Salvar plano",
                bg=BLUE,
                fg=WHITE,
                activebackground=BLUE_DARK,
                activeforeground=WHITE,
                relief="flat",
                bd=0,
                cursor="hand2",
                font=("Segoe UI Semibold", 9),
                command=self.salvar_plano_tela
            ).pack(anchor="e", padx=20, pady=10, ipadx=12, ipady=5)

        else:
            tk.Label(
                painel,
                text="Nenhum planejamento registrado para hoje.",
                bg=WHITE,
                fg=TEXT_LIGHT,
                font=("Segoe UI", 9)
            ).pack(anchor="w", padx=20, pady=(2, 15))

        # ----------------------------------------------------
        # PLANEJAMENTO DE AMANHÃ
        # ----------------------------------------------------
        amanha = (date.fromisoformat(self.data_atual) + timedelta(days=1)).strftime("%Y-%m-%d")
        plano_amanha = buscar_plano(alvo["id"], amanha) if alvo else None
        texto_amanha = plano_amanha["texto"] if plano_amanha else ""

        painel_amanha = tk.Frame(
            area,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        painel_amanha.pack(fill="x", pady=(12, 0))

        cab_amanha = tk.Frame(painel_amanha, bg=WHITE)
        cab_amanha.pack(fill="x", padx=20, pady=(13, 5))
        tk.Label(
            cab_amanha,
            text="📅  O que pretendo fazer amanhã",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI", 14, "bold")
        ).pack(side="left")
        tk.Label(
            cab_amanha,
            text=self.formatar_data(amanha),
            bg=WHITE,
            fg=TEXT_LIGHT,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=12)

        if texto_amanha.strip():
            linha_amanha = tk.Frame(painel_amanha, bg="#FBFCFE")
            linha_amanha.pack(fill="x", padx=20, pady=(4, 14))
            tk.Label(
                linha_amanha,
                text=texto_amanha,
                bg="#FBFCFE",
                fg=TEXT,
                justify="left",
                anchor="w",
                wraplength=850,
                font=("Segoe UI", 10)
            ).pack(side="left", fill="x", expand=True, padx=12, pady=10)
            if pode_editar_hoje:
                tk.Button(
                    linha_amanha,
                    text="✎",
                    bg=BLUE_LIGHT,
                    fg=BLUE_DARK,
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    font=("Segoe UI", 11, "bold"),
                    command=self.editar_plano_amanha
                ).pack(side="right", padx=10, pady=8, ipadx=7, ipady=4)
        elif pode_editar_hoje:
            self.plano_amanha_text = tk.Text(
                painel_amanha,
                height=2,
                bg="#FBFCFE",
                fg=TEXT,
                font=("Segoe UI", 10),
                relief="solid",
                bd=1,
                wrap="word",
                padx=10,
                pady=7
            )
            self.plano_amanha_text.pack(fill="x", padx=20)
            tk.Button(
                painel_amanha,
                text="Salvar planejamento de amanhã",
                bg=BLUE,
                fg=WHITE,
                activebackground=BLUE_DARK,
                activeforeground=WHITE,
                relief="flat",
                bd=0,
                cursor="hand2",
                font=("Segoe UI Semibold", 9),
                command=self.salvar_plano_amanha_tela
            ).pack(anchor="e", padx=20, pady=9, ipadx=10, ipady=5)
        else:
            tk.Label(
                painel_amanha,
                text="Nenhum planejamento de amanhã registrado.",
                bg=WHITE,
                fg=TEXT_LIGHT,
                font=("Segoe UI", 9)
            ).pack(anchor="w", padx=20, pady=(2, 14))

        # ----------------------------------------------------
        # RESUMO RÁPIDO
        # ----------------------------------------------------

        resumo = tk.Frame(
            area,
            bg=BG
        )

        resumo.pack(
            fill="both",
            expand=True,
            pady=(15, 0)
        )

        self.criar_resumo_inicio(
            resumo,
            alvo
        )

    def criar_painel_marion(self, parent):
        """Resumo exclusivo da Marion para a reunião diária."""
        painel = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        painel.pack(fill="x", padx=30, pady=(0, 12))

        hoje = self.data_atual
        amanha = (date.fromisoformat(hoje) + timedelta(days=1)).strftime("%Y-%m-%d")
        planos_hoje = buscar_planos_para_data(hoje)
        planos_amanha = buscar_planos_para_data(amanha)

        cab = tk.Frame(painel, bg=WHITE)
        cab.pack(fill="x", padx=18, pady=(12, 5))
        tk.Label(cab, text="📋 Resumo da reunião", bg=WHITE, fg=TEXT, font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(cab, text="Leitura rápida", bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)).pack(side="left", padx=10)

        corpo = tk.Frame(painel, bg=WHITE)
        corpo.pack(fill="x", padx=18, pady=(0, 10))
        self._adicionar_linhas_resumo_marion(corpo, "Tarefas de hoje", planos_hoje)
        tk.Frame(corpo, bg=BORDER, height=1).pack(fill="x", pady=7)
        self._adicionar_linhas_resumo_marion(corpo, "Planejamento de amanhã", planos_amanha)

    def _adicionar_linhas_resumo_marion(self, parent, titulo, registros):
        tk.Label(parent, text=titulo, bg=WHITE, fg=TEXT, font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(2, 4))
        if not registros:
            tk.Label(parent, text="Nenhum planejamento registrado.", bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 5))
            return
        for registro in registros:
            linha = tk.Frame(parent, bg="#FBFCFE")
            linha.pack(fill="x", pady=1)
            tk.Label(linha, text=registro["nome"], bg="#FBFCFE", fg=TEXT, width=14, anchor="w", font=("Segoe UI Semibold", 9)).pack(side="left", padx=(8, 4), pady=5)
            tk.Label(linha, text=registro["texto"], bg="#FBFCFE", fg=TEXT, anchor="w", justify="left", wraplength=760, font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=4, pady=5)


    def criar_card(self, parent, titulo, valor, cor):
        card = tk.Frame(
            parent, bg=WHITE,
            highlightbackground=BORDER, highlightthickness=1
        )
        if not hasattr(parent, "_cards"):
            parent._cards = []
        parent._cards.append(card)

        faixa = tk.Frame(card, bg=cor, width=5)
        faixa.pack(side="left", fill="y")

        interno = tk.Frame(card, bg=WHITE)
        interno.pack(fill="both", expand=True, padx=16, pady=14)

        tk.Label(
            interno, text=titulo, bg=WHITE, fg=TEXT_LIGHT,
            font=("Segoe UI Semibold", 8)
        ).pack(anchor="w")
        tk.Label(
            interno, text=valor, bg=WHITE, fg=TEXT,
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", pady=(4, 0))

        self._organizar_cards_inicio()

    def criar_resumo_inicio(
        self,
        parent,
        alvo
    ):

        if not alvo:
            return

        frame = tk.Frame(
            parent,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        frame.pack(
            fill="both",
            expand=True
        )

        tk.Label(
            frame,
            text="Próximas tarefas",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI", 13, "bold")
        ).pack(
            anchor="w",
            padx=18,
            pady=(14, 8)
        )

        tarefas = buscar_tarefas(
            alvo["id"]
        )

        if not tarefas:

            tk.Label(
                frame,
                text="Nenhuma tarefa aberta.",
                bg=WHITE,
                fg=TEXT_LIGHT,
                font=("Segoe UI", 10)
            ).pack(
                anchor="w",
                padx=18,
                pady=10
            )

            return

        for tarefa in tarefas[:5]:

            linha = tk.Frame(
                frame,
                bg="#FBFCFE"
            )

            linha.pack(
                fill="x",
                padx=15,
                pady=2
            )

            cor = {
                "Alta": RED,
                "Urgente": RED,
                "Baixa": TEXT_LIGHT,
                "Normal": BLUE
            }.get(
                tarefa["prioridade"],
                BLUE
            )

            tk.Frame(
                linha,
                bg=cor,
                width=4
            ).pack(
                side="left",
                fill="y"
            )

            tk.Label(
                linha,
                text=tarefa["titulo"],
                bg="#FBFCFE",
                fg=TEXT,
                font=("Segoe UI Semibold", 9)
            ).pack(
                side="left",
                padx=10,
                pady=7
            )

            tk.Label(
                linha,
                text=tarefa["prioridade"],
                bg="#FBFCFE",
                fg=cor,
                font=("Segoe UI", 8)
            ).pack(
                side="right",
                padx=10
            )

    def editar_plano(self):
        alvo = self.alvo_atual()
        if not alvo or self.usuario["perfil"] != "worker" or int(alvo["id"]) != int(self.usuario["id"]):
            messagebox.showwarning("Permissão", "Somente você pode editar seu próprio Plano do Dia.")
            return
        plano = buscar_plano(alvo["id"], self.data_atual)
        self.abrir_editor_plano(plano["texto"] if plano else "", self.data_atual, "Plano do dia")

    def editar_plano_amanha(self):
        alvo = self.alvo_atual()
        if not alvo or self.usuario["perfil"] != "worker" or int(alvo["id"]) != int(self.usuario["id"]):
            messagebox.showwarning("Permissão", "Somente você pode editar seu próprio planejamento.")
            return
        amanha = (date.fromisoformat(self.data_atual) + timedelta(days=1)).strftime("%Y-%m-%d")
        plano = buscar_plano(alvo["id"], amanha)
        self.abrir_editor_plano(plano["texto"] if plano else "", amanha, "Planejamento de amanhã")

    def abrir_editor_plano(self, texto_atual="", data_str=None, titulo_editor="Plano do dia"):
        janela = tk.Toplevel(self.root)
        janela.title("Editar " + titulo_editor.lower())
        janela.geometry("550x330")
        janela.configure(bg=WHITE)
        janela.transient(self.root)
        janela.grab_set()

        frame = tk.Frame(janela, bg=WHITE)
        frame.pack(fill="both", expand=True, padx=25, pady=25)
        tk.Label(frame, text=titulo_editor, bg=WHITE, fg=TEXT, font=("Segoe UI", 19, "bold")).pack(anchor="w")

        texto = tk.Text(frame, height=7, font=("Segoe UI", 10), relief="solid", bd=1, wrap="word", padx=10, pady=8)
        texto.pack(fill="both", expand=True, pady=(15, 12))
        texto.insert("1.0", texto_atual)

        def salvar():
            alvo = self.alvo_atual()
            if not alvo or self.usuario["perfil"] != "worker" or int(alvo["id"]) != int(self.usuario["id"]):
                messagebox.showerror("Permissão", "Somente você pode editar seu próprio planejamento.")
                return
            data_salvar = data_str or self.data_atual
            texto_novo = texto.get("1.0", "end-1c").strip()
            if not texto_novo:
                messagebox.showwarning("Plano", "Escreva alguma coisa antes de salvar.")
                return
            try:
                salvar_plano(alvo["id"], data_salvar, texto_novo, self.usuario["id"])
            except PermissionError as erro:
                messagebox.showerror("Permissão", str(erro))
                return
            janela.destroy()
            self.mostrar_inicio()

        tk.Button(frame, text="Salvar", bg=BLUE, fg=WHITE, activebackground=BLUE_DARK, activeforeground=WHITE, relief="flat", bd=0, command=salvar, cursor="hand2").pack(anchor="e", ipadx=20, ipady=6)

    def salvar_plano_tela(self):
        alvo = self.alvo_atual()
        if not alvo or self.usuario["perfil"] != "worker" or int(alvo["id"]) != int(self.usuario["id"]):
            messagebox.showerror("Permissão", "Somente você pode editar seu próprio Plano do Dia.")
            return
        texto = self.plano_text.get("1.0", "end-1c").strip()
        if not texto:
            messagebox.showwarning("Plano", "Escreva alguma coisa antes de salvar.")
            return
        try:
            salvar_plano(alvo["id"], self.data_atual, texto, self.usuario["id"])
        except PermissionError as erro:
            messagebox.showerror("Permissão", str(erro))
            return
        self.mostrar_inicio()

    def salvar_plano_amanha_tela(self):
        alvo = self.alvo_atual()
        if not alvo or self.usuario["perfil"] != "worker" or int(alvo["id"]) != int(self.usuario["id"]):
            messagebox.showerror("Permissão", "Somente você pode editar seu próprio planejamento.")
            return
        texto = self.plano_amanha_text.get("1.0", "end-1c").strip()
        if not texto:
            messagebox.showwarning("Amanhã", "Escreva alguma coisa antes de salvar.")
            return
        amanha = (date.fromisoformat(self.data_atual) + timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            salvar_plano(alvo["id"], amanha, texto, self.usuario["id"])
        except PermissionError as erro:
            messagebox.showerror("Permissão", str(erro))
            return
        self.mostrar_inicio()

    # ========================================================
    # TAREFAS
    # ========================================================

    def mostrar_tarefas(self):

        self.menu_atual = "tarefas"

        self.marcar_menu("tarefas")

        self.limpar_conteudo()

        alvo = self.alvo_atual()

        nome = alvo["nome"] if alvo else ""

        self.titulo_pagina(
            "Tarefas",
            f"Lista de trabalho de {nome}"
        )

        self.criar_seletor_trabalhador(
            self.conteudo
        )

        area = tk.Frame(
            self.conteudo,
            bg=BG
        )

        area.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(0, 25)
        )

        area.grid_rowconfigure(
            0,
            weight=1
        )

        area.grid_columnconfigure(
            0,
            weight=1
        )

        lista_frame = tk.Frame(
            area,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        lista_frame.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        lista_frame.grid_rowconfigure(
            0,
            weight=1
        )

        lista_frame.grid_columnconfigure(
            0,
            weight=1
        )

        colunas = (
            "ordem",
            "titulo",
            "projeto",
            "prioridade",
            "data",
            "descricao"
        )

        self.tabela = ttk.Treeview(
            lista_frame,
            columns=colunas,
            show="headings",
            selectmode="browse"
        )

        self.tabela.heading(
            "ordem",
            text="#"
        )

        self.tabela.heading(
            "titulo",
            text="Tarefa"
        )

        self.tabela.heading(
            "projeto",
            text="Projeto"
        )

        self.tabela.heading(
            "prioridade",
            text="Prioridade"
        )

        self.tabela.heading(
            "data",
            text="Data"
        )

        self.tabela.heading(
            "descricao",
            text="Descrição"
        )

        self.tabela.column(
            "ordem",
            width=45,
            anchor="center"
        )

        self.tabela.column(
            "titulo",
            width=230
        )

        self.tabela.column(
            "projeto",
            width=140
        )

        self.tabela.column(
            "prioridade",
            width=100,
            anchor="center"
        )

        self.tabela.column(
            "data",
            width=100,
            anchor="center"
        )

        self.tabela.column(
            "descricao",
            width=330
        )

        scrollbar = ttk.Scrollbar(
            lista_frame,
            orient="vertical",
            command=self.tabela.yview
        )

        self.tabela.configure(
            yscrollcommand=scrollbar.set
        )

        self.tabela.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        self.tabela.bind(
            "<Double-1>",
            lambda event: self.editar_tarefa()
        )

        tarefas = (
            buscar_tarefas(
                alvo["id"]
            )
            if alvo
            else []
        )

        for indice, tarefa in enumerate(
            tarefas,
            start=1
        ):

            self.tabela.insert(
                "",
                "end",
                iid=str(tarefa["id"]),
                values=(
                    indice,
                    tarefa["titulo"],
                    tarefa["projeto"] or "",
                    tarefa["prioridade"] or "Normal",
                    self.formatar_data(
                        tarefa["data"]
                    ),
                    tarefa["descricao"] or ""
                )
            )

        # ----------------------------------------------------
        # BARRA FIXA
        # ----------------------------------------------------

        botoes = tk.Frame(
            area,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        botoes.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(10, 0)
        )

        botoes.columnconfigure(
            0,
            weight=1
        )

        esquerda = tk.Frame(
            botoes,
            bg=WHITE
        )

        esquerda.grid(
            row=0,
            column=0,
            sticky="w"
        )

        direita = tk.Frame(
            botoes,
            bg=WHITE
        )

        direita.grid(
            row=0,
            column=1,
            sticky="e"
        )

        tk.Button(
            esquerda,
            text="+  Nova tarefa",
            bg=BLUE,
            fg=WHITE,
            activebackground=BLUE_DARK,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
            command=self.nova_tarefa
        ).pack(
            side="left",
            padx=12,
            pady=10,
            ipadx=8,
            ipady=5
        )

        tk.Button(
            esquerda,
            text="↑",
            bg=BLUE_LIGHT,
            fg=BLUE_DARK,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.mover_tarefa_tela("cima")
        ).pack(
            side="left",
            padx=2,
            pady=10,
            ipadx=8,
            ipady=5
        )

        tk.Button(
            esquerda,
            text="↓",
            bg=BLUE_LIGHT,
            fg=BLUE_DARK,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=lambda: self.mover_tarefa_tela("baixo")
        ).pack(
            side="left",
            padx=2,
            pady=10,
            ipadx=8,
            ipady=5
        )

        tk.Button(
            direita,
            text="✓ Concluir",
            bg=GREEN_LIGHT,
            fg=GREEN,
            activebackground="#D6F4E5",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            command=self.concluir_tarefa_tela
        ).pack(
            side="left",
            padx=3,
            pady=10,
            ipadx=8,
            ipady=5
        )

        tk.Button(
            direita,
            text="✎ Editar",
            bg=BLUE_LIGHT,
            fg=BLUE_DARK,
            activebackground="#DCEAFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            command=self.editar_tarefa
        ).pack(
            side="left",
            padx=3,
            pady=10,
            ipadx=8,
            ipady=5
        )

        tk.Button(
            direita,
            text="🗑 Excluir",
            bg=RED_LIGHT,
            fg=RED,
            activebackground="#FFE0E0",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            command=self.excluir_tarefa_tela
        ).pack(
            side="left",
            padx=(3, 12),
            pady=10,
            ipadx=8,
            ipady=5
        )

    def abrir_conversas_tarefa(self, tarefa):
        if not tarefa:
            messagebox.showinfo("Conversa / Alterações", "Salve a tarefa primeiro para registrar conversas e scanners.")
            return
        janela = tk.Toplevel(self.root)
        janela.title("Conversa / Alterações — " + tarefa["titulo"])
        janela.geometry("820x650"); janela.minsize(650, 500); janela.configure(bg=BG); janela.transient(self.root)
        topo = tk.Frame(janela, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        topo.pack(fill="x", padx=22, pady=(22,10))
        tk.Label(topo, text="Conversa / Alterações", bg=WHITE, fg=TEXT, font=("Segoe UI",18,"bold")).pack(anchor="w", padx=18, pady=(15,2))
        tk.Label(topo, text=tarefa["titulo"] + "  •  histórico técnico, decisões e scanners", bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI",9)).pack(anchor="w", padx=18, pady=(0,15))
        form = tk.Frame(janela, bg=WHITE, highlightbackground=BORDER, highlightthickness=1); form.pack(fill="x", padx=22, pady=6)
        fi=tk.Frame(form,bg=WHITE); fi.pack(fill="x",padx=18,pady=15)
        tk.Label(fi,text="Participantes",bg=WHITE,fg=TEXT,font=("Segoe UI Semibold",9)).pack(anchor="w")
        participantes=tk.Entry(fi,font=("Segoe UI",10),relief="solid",bd=1); participantes.pack(fill="x",ipady=6,pady=(4,10))
        tk.Label(fi,text="Decisão / motivo da alteração",bg=WHITE,fg=TEXT,font=("Segoe UI Semibold",9)).pack(anchor="w")
        texto=tk.Text(fi,height=4,font=("Segoe UI",10),relief="solid",bd=1,wrap="word"); texto.pack(fill="x",pady=(4,8))
        arquivos=[]; arq_lbl=tk.Label(fi,text="Nenhum scanner/anexo selecionado.",bg=WHITE,fg=TEXT_LIGHT,font=("Segoe UI",8)); arq_lbl.pack(anchor="w")
        botoes=tk.Frame(fi,bg=WHITE); botoes.pack(fill="x",pady=(8,0))
        def selecionar():
            vals=filedialog.askopenfilenames(title="Selecionar scanners, PDFs ou imagens", parent=janela)
            if vals:
                arquivos[:] = vals; arq_lbl.config(text=f"{len(vals)} arquivo(s) selecionado(s)")
        def salvar_conv():
            msg=texto.get("1.0","end-1c").strip()
            if not msg:
                messagebox.showwarning("Conversa", "Descreva a decisão ou alteração.", parent=janela); return
            adicionar_conversa_tarefa(tarefa["id"], self.usuario["id"], participantes.get().strip(), msg, arquivos)
            janela.destroy(); self.abrir_conversas_tarefa(tarefa)
        tk.Button(botoes,text="📎 Anexar scanner/documento",bg="#EEF2F7",fg=TEXT,relief="flat",bd=0,cursor="hand2",command=selecionar).pack(side="left",ipadx=9,ipady=5)
        tk.Button(botoes,text="Registrar conversa",bg=BLUE,fg=WHITE,activebackground=BLUE_DARK,relief="flat",bd=0,cursor="hand2",font=("Segoe UI Semibold",9),command=salvar_conv).pack(side="right",ipadx=12,ipady=6)
        hist=tk.Frame(janela,bg=WHITE,highlightbackground=BORDER,highlightthickness=1); hist.pack(fill="both",expand=True,padx=22,pady=(6,22))
        tk.Label(hist,text="Histórico",bg=WHITE,fg=TEXT,font=("Segoe UI",13,"bold")).pack(anchor="w",padx=18,pady=(14,8))
        canvas=tk.Canvas(hist,bg=WHITE,highlightthickness=0); sb=ttk.Scrollbar(hist,orient="vertical",command=canvas.yview,style="Modern.Vertical.TScrollbar"); lista=tk.Frame(canvas,bg=WHITE)
        lista.bind("<Configure>",lambda e: canvas.configure(scrollregion=canvas.bbox("all"))); canvas.create_window((0,0),window=lista,anchor="nw"); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left",fill="both",expand=True,padx=(14,0),pady=(0,12)); sb.pack(side="right",fill="y",pady=(0,12),padx=(0,8))
        registros=buscar_conversas_tarefa(tarefa["id"])
        if not registros: tk.Label(lista,text="Nenhuma conversa registrada ainda.",bg=WHITE,fg=TEXT_LIGHT).pack(anchor="w",padx=5,pady=12)
        for r in registros:
            card=tk.Frame(lista,bg="#F8FAFC",highlightbackground=BORDER,highlightthickness=1); card.pack(fill="x",padx=5,pady=4)
            cab=f"{r['autor_nome'] or 'Usuário'} — {self.formatar_data_hora(r['criado_em'])}"
            tk.Label(card,text=cab,bg="#F8FAFC",fg=BLUE_DARK,font=("Segoe UI Semibold",9)).pack(anchor="w",padx=12,pady=(9,2))
            if r['participantes']: tk.Label(card,text="Participantes: "+r['participantes'],bg="#F8FAFC",fg=TEXT_LIGHT,font=("Segoe UI",8)).pack(anchor="w",padx=12)
            tk.Label(card,text=r['texto'],bg="#F8FAFC",fg=TEXT,font=("Segoe UI",9),justify="left",wraplength=700).pack(anchor="w",padx=12,pady=(4,7))
            af=tk.Frame(card,bg="#F8FAFC"); af.pack(fill="x",padx=9,pady=(0,8))
            for a in buscar_anexos_conversa(r['id']):
                tk.Button(af,text="📎 "+a['nome'],bg=BLUE_LIGHT,fg=BLUE_DARK,relief="flat",bd=0,cursor="hand2",command=lambda x=a:self.abrir_caminho(x['caminho'])).pack(side="left",padx=3,ipadx=5,ipady=3)

    def obter_tarefa_selecionada(self):

        selecionado = self.tabela.selection()

        if not selecionado:
            return None

        return buscar_tarefa(
            int(selecionado[0])
        )

    def nova_tarefa(self):
        self.abrir_editor_tarefa()

    def editar_tarefa(self):

        tarefa = self.obter_tarefa_selecionada()

        if not tarefa:

            messagebox.showwarning(
                "Tarefa",
                "Selecione uma tarefa primeiro."
            )

            return

        self.abrir_editor_tarefa(
            tarefa
        )


    def abrir_editor_tarefa(self, tarefa=None):
        janela = tk.Toplevel(self.root)
        janela.title("Editar tarefa" if tarefa else "Nova tarefa")
        janela.geometry("600x650")
        janela.minsize(500, 520)
        janela.configure(bg=WHITE)
        janela.transient(self.root)
        janela.grab_set()

        # Conteúdo rolável também nas janelas de edição.
        externo = tk.Frame(janela, bg=WHITE)
        externo.pack(fill="both", expand=True)
        canvas = tk.Canvas(externo, bg=WHITE, highlightthickness=0)
        sb = ttk.Scrollbar(externo, orient="vertical", command=canvas.yview,
                           style="Modern.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame = tk.Frame(canvas, bg=WHITE)
        win = canvas.create_window((0, 0), window=frame, anchor="nw")

        def sync(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def width(event):
            canvas.itemconfigure(win, width=event.width)
        frame.bind("<Configure>", sync)
        canvas.bind("<Configure>", width)

        interno = tk.Frame(frame, bg=WHITE)
        interno.pack(fill="both", expand=True, padx=30, pady=25)

        tk.Label(
            interno, text="Editar tarefa" if tarefa else "Nova tarefa",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 20, "bold")
        ).pack(anchor="w")

        tk.Label(interno, text="Título", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(20, 4))
        titulo_entry = tk.Entry(interno, font=("Segoe UI", 11), relief="solid", bd=1)
        titulo_entry.pack(fill="x", ipady=8)

        tk.Label(interno, text="Projeto", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(12, 4))

        # A tarefa NÃO cria projeto. Ela somente aponta para o cadastro central.
        projetos = buscar_projetos("Ativo")
        projeto_por_nome = {p["nome"]: p for p in projetos}
        projeto_nomes = ["— Sem projeto —"] + [p["nome"] for p in projetos]

        projeto_atual_nome = (tarefa["projeto"] or "") if tarefa else ""
        if projeto_atual_nome and projeto_atual_nome not in projeto_por_nome:
            # Permite editar um registro antigo ou ligado a projeto já finalizado,
            # sem transformar o texto em um novo projeto.
            projeto_nomes.append(projeto_atual_nome)

        projeto_combo = ttk.Combobox(
            interno, values=projeto_nomes, state="readonly",
            style="Modern.TCombobox"
        )
        projeto_combo.pack(fill="x")
        projeto_combo.set(projeto_atual_nome if projeto_atual_nome else "— Sem projeto —")

        tk.Label(
            interno,
            text="Os projetos desta lista são administrados no menu Projetos.",
            bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 8)
        ).pack(anchor="w", pady=(3, 0))

        tk.Label(interno, text="Data (AAAA-MM-DD)", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(12, 4))
        data_entry = tk.Entry(interno, font=("Segoe UI", 11), relief="solid", bd=1)
        data_entry.pack(fill="x", ipady=8)

        tk.Label(interno, text="Prioridade", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(12, 4))
        prioridade_combo = ttk.Combobox(
            interno,
            values=["Baixa", "Normal", "Alta", "Urgente"],
            state="readonly", style="Modern.TCombobox"
        )
        prioridade_combo.pack(fill="x")
        prioridade_combo.set("Normal")

        tk.Label(interno, text="Descrição", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(12, 4))
        descricao = tk.Text(
            interno, height=7, font=("Segoe UI", 10),
            relief="solid", bd=1, wrap="word", padx=8, pady=7
        )
        descricao.pack(fill="x")

        if tarefa:
            titulo_entry.insert(0, tarefa["titulo"])
            data_entry.insert(0, tarefa["data"])
            prioridade_combo.set(tarefa["prioridade"] or "Normal")
            descricao.insert("1.0", tarefa["descricao"] or "")
        else:
            data_entry.insert(0, self.data_atual)

        def salvar():
            titulo = titulo_entry.get().strip()
            projeto_nome = projeto_combo.get().strip()
            if projeto_nome == "— Sem projeto —":
                projeto_nome = ""

            projeto_id = None
            if projeto_nome:
                reg = projeto_por_nome.get(projeto_nome)
                if reg:
                    projeto_id = reg["id"]
                elif tarefa and tarefa["projeto"] == projeto_nome:
                    # Registro legado/inativo: preserva o projeto_id antigo, se houver.
                    try:
                        projeto_id = tarefa["projeto_id"]
                    except Exception:
                        projeto_id = None

            data_str = data_entry.get().strip()
            prioridade = prioridade_combo.get() or "Normal"
            desc = descricao.get("1.0", "end-1c")

            if not titulo:
                messagebox.showwarning("Tarefa", "Digite o título da tarefa.", parent=janela)
                return

            try:
                datetime.strptime(data_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showwarning(
                    "Data", "A data precisa estar no formato AAAA-MM-DD.", parent=janela
                )
                return

            alvo = self.alvo_atual()
            if not alvo:
                return

            if tarefa:
                atualizar_tarefa(
                    tarefa["id"], titulo, desc, data_str,
                    projeto_nome, prioridade, projeto_id
                )
            else:
                criar_tarefa(
                    alvo["id"], titulo, desc, data_str,
                    projeto_nome, prioridade, self.usuario["id"], projeto_id
                )

            janela.destroy()
            self.mostrar_tarefas()

        if tarefa:
            tk.Button(
                interno,
                text="💬 Conversa / Alterações e scanners",
                bg="#EEF2FF", fg=BLUE_DARK,
                activebackground=BLUE_LIGHT, relief="flat", bd=0,
                cursor="hand2", font=("Segoe UI Semibold", 9),
                command=lambda: self.abrir_conversas_tarefa(tarefa)
            ).pack(anchor="w", pady=(14, 0), ipadx=10, ipady=6)

        tk.Button(
            interno, text="Salvar", bg=BLUE, fg=WHITE,
            activebackground=BLUE_DARK, activeforeground=WHITE,
            relief="flat", bd=0, cursor="hand2",
            font=("Segoe UI Semibold", 10), command=salvar
        ).pack(anchor="e", pady=(14, 0), ipadx=20, ipady=7)

        titulo_entry.focus_set()

    def concluir_tarefa_tela(self):

        tarefa = self.obter_tarefa_selecionada()

        if not tarefa:

            messagebox.showwarning(
                "Tarefa",
                "Selecione uma tarefa primeiro."
            )

            return

        concluir_tarefa(
            tarefa["id"]
        )

        self.mostrar_tarefas()

    def excluir_tarefa_tela(self):

        tarefa = self.obter_tarefa_selecionada()

        if not tarefa:

            messagebox.showwarning(
                "Tarefa",
                "Selecione uma tarefa primeiro."
            )

            return

        resposta = messagebox.askyesno(
            "Excluir tarefa",
            f'Deseja realmente excluir "{tarefa["titulo"]}"?'
        )

        if resposta:

            excluir_tarefa(
                tarefa["id"]
            )

            self.mostrar_tarefas()

    def mover_tarefa_tela(
        self,
        direcao
    ):

        tarefa = self.obter_tarefa_selecionada()

        if not tarefa:

            messagebox.showwarning(
                "Prioridade",
                "Selecione uma tarefa primeiro."
            )

            return

        mover_tarefa(
            tarefa["id"],
            direcao
        )

        self.mostrar_tarefas()

    # ========================================================
    # ANTIGAS
    # ========================================================

    def mostrar_antigas(self):

        self.menu_atual = "antigas"

        self.marcar_menu("antigas")

        self.limpar_conteudo()

        alvo = self.alvo_atual()

        self.titulo_pagina(
            "Antigas",
            "Registro das tarefas que já foram concluídas."
        )

        self.criar_seletor_trabalhador(
            self.conteudo
        )

        area = tk.Frame(
            self.conteudo,
            bg=BG
        )

        area.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(0, 25)
        )

        area.grid_rowconfigure(
            0,
            weight=1
        )

        area.grid_columnconfigure(
            0,
            weight=1
        )

        frame = tk.Frame(
            area,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        frame.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        frame.grid_rowconfigure(
            0,
            weight=1
        )

        frame.grid_columnconfigure(
            0,
            weight=1
        )

        tabela = ttk.Treeview(
            frame,
            columns=(
                "titulo",
                "projeto",
                "data",
                "descricao"
            ),
            show="headings",
            selectmode="browse"
        )

        tabela.heading(
            "titulo",
            text="Tarefa"
        )

        tabela.heading(
            "projeto",
            text="Projeto"
        )

        tabela.heading(
            "data",
            text="Data"
        )

        tabela.heading(
            "descricao",
            text="Descrição"
        )

        tabela.column(
            "titulo",
            width=280
        )

        tabela.column(
            "projeto",
            width=150
        )

        tabela.column(
            "data",
            width=120,
            anchor="center"
        )

        tabela.column(
            "descricao",
            width=450
        )

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=tabela.yview
        )

        tabela.configure(
            yscrollcommand=scrollbar.set
        )

        tabela.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        tarefas = (
            buscar_tarefas(
                alvo["id"],
                True
            )
            if alvo
            else []
        )

        for tarefa in tarefas:

            tabela.insert(
                "",
                "end",
                iid=str(tarefa["id"]),
                values=(
                    tarefa["titulo"],
                    tarefa["projeto"] or "",
                    self.formatar_data(
                        tarefa["data"]
                    ),
                    tarefa["descricao"] or ""
                )
            )

        botoes = tk.Frame(
            area,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        botoes.grid(
            row=1,
            column=0,
            sticky="ew",
            pady=(10, 0)
        )

        def reabrir():

            selecionado = tabela.selection()

            if not selecionado:

                messagebox.showwarning(
                    "Antigas",
                    "Selecione uma tarefa."
                )

                return

            reabrir_tarefa(
                int(selecionado[0])
            )

            self.mostrar_antigas()

        tk.Button(
            botoes,
            text="↻ Reabrir tarefa",
            bg=BLUE_LIGHT,
            fg=BLUE_DARK,
            activebackground="#DCEAFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            command=reabrir
        ).pack(
            side="left",
            padx=12,
            pady=10,
            ipadx=10,
            ipady=5
        )

    # ========================================================
    # CALENDÁRIO
    # ========================================================


    def mostrar_calendario(self):
        self.menu_atual = "calendario"
        self.marcar_menu("calendario")
        self.limpar_conteudo()

        perfil = self.usuario["perfil"]
        visao_equipe = perfil in ("planner", "lead", "manager")
        login_atual = self.usuario["login"].lower()

        self.titulo_pagina(
            "Calendário da equipe" if visao_equipe else "Calendário",
            (
                "Planejamento, férias e presença em uma visão rápida."
                if visao_equipe
                else "Seu planejamento e a disponibilidade da equipe."
            )
        )

        area = tk.Frame(self.conteudo, bg=BG)
        area.pack(fill="both", expand=True, padx=30, pady=(0, 25))

        cab = tk.Frame(area, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        cab.pack(fill="x")
        nomes_meses = [
            "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ]

        tk.Button(
            cab, text="‹", bg=WHITE, fg=TEXT,
            activebackground=BLUE_LIGHT, relief="flat", bd=0,
            font=("Segoe UI", 18, "bold"), cursor="hand2",
            command=self.mes_anterior
        ).pack(side="left", padx=15, pady=8)

        tk.Label(
            cab,
            text=f"{nomes_meses[self.calendario_mes]} {self.calendario_ano}",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 15, "bold")
        ).pack(side="left", expand=True)

        tk.Button(
            cab, text="›", bg=WHITE, fg=TEXT,
            activebackground=BLUE_LIGHT, relief="flat", bd=0,
            font=("Segoe UI", 18, "bold"), cursor="hand2",
            command=self.proximo_mes
        ).pack(side="right", padx=15, pady=8)

        # Trabalhadores podem registrar férias; Feierabend somente nos blocos de presença.
        # Marion também está no bloco 2 e pode registrar o próprio Feierabend.
        pode_criar = perfil == "worker" or login_atual in PRESENCA_SETOR_LOGINS
        if pode_criar:
            tk.Button(
                area, text="+ Adicionar ao calendário",
                bg=BLUE, fg=WHITE, relief="flat", bd=0,
                cursor="hand2", font=("Segoe UI Semibold", 9),
                command=self.abrir_editor_evento_calendario
            ).pack(anchor="e", pady=(10, 8), ipadx=10, ipady=5)

        # Carrega eventos do mês uma vez para criar indicadores discretos nos dias.
        primeiro = date(self.calendario_ano, self.calendario_mes, 1)
        if self.calendario_mes == 12:
            proximo = date(self.calendario_ano + 1, 1, 1)
        else:
            proximo = date(self.calendario_ano, self.calendario_mes + 1, 1)
        ultimo = proximo - timedelta(days=1)

        eventos_mes_todos = buscar_eventos_periodo(primeiro.isoformat(), ultimo.isoformat(), None)

        def evento_visivel(e):
            # Férias (planejadas ou aprovadas) são visíveis para toda a equipe,
            # pois impactam o planejamento geral do escritório.
            if e["tipo"] in ("ferias_planejadas", "ferias"):
                return True

            # Feierabend é operacional por bloco. Chefia/planejamento/gestão vê tudo;
            # trabalhadores veem somente o próprio bloco.
            if visao_equipe:
                return True
            if e["tipo"] == "feierabend":
                grupo = grupo_presenca(login_atual)
                return e["login"].lower() in grupo if grupo else e["login"].lower() == login_atual
            return e["login"].lower() == login_atual

        eventos_mes = [e for e in eventos_mes_todos if evento_visivel(e)]

        calendario_frame = tk.Frame(
            area, bg=WHITE,
            highlightbackground=BORDER, highlightthickness=1
        )
        calendario_frame.pack(fill="x", pady=(2, 0))

        for c in range(7):
            calendario_frame.grid_columnconfigure(c, weight=1, uniform="dia")

        dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        for c, nome in enumerate(dias_semana):
            tk.Label(
                calendario_frame, text=nome, bg="#EDF2F7", fg=TEXT,
                font=("Segoe UI Semibold", 9), pady=6
            ).grid(row=0, column=c, sticky="nsew", padx=1, pady=1)

        detalhe = tk.Frame(
            area, bg=WHITE,
            highlightbackground=BORDER, highlightthickness=1
        )
        detalhe.pack(fill="x", pady=(14, 0))
        detalhe_interno = tk.Frame(detalhe, bg=WHITE)
        detalhe_interno.pack(fill="x", padx=20, pady=16)

        def renderizar_dia(dia):
            for w in detalhe_interno.winfo_children():
                w.destroy()

            data_sel = date(self.calendario_ano, self.calendario_mes, dia)
            data_str = data_sel.isoformat()
            nomes_dias = [
                "Segunda-feira", "Terça-feira", "Quarta-feira",
                "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"
            ]

            tk.Label(
                detalhe_interno,
                text=(
                    f"{nomes_dias[data_sel.weekday()]}, "
                    f"{dia:02d}/{self.calendario_mes:02d}/{self.calendario_ano}"
                ),
                bg=WHITE, fg=TEXT, font=("Segoe UI", 16, "bold")
            ).pack(anchor="w")

            planos = buscar_planos_periodo(
                data_str, data_str,
                None if visao_equipe else self.usuario["id"]
            )
            eventos = [
                e for e in buscar_eventos_periodo(data_str, data_str, None)
                if evento_visivel(e)
            ]

            tk.Label(
                detalhe_interno, text="Planejamento",
                bg=WHITE, fg=TEXT, font=("Segoe UI", 11, "bold")
            ).pack(anchor="w", pady=(14, 5))

            if planos:
                for p in planos:
                    linha = tk.Frame(detalhe_interno, bg="#F8FAFC")
                    linha.pack(fill="x", pady=2)
                    if visao_equipe:
                        tk.Label(
                            linha, text=p["nome"], width=18, anchor="w",
                            bg="#F8FAFC", fg=TEXT,
                            font=("Segoe UI Semibold", 9)
                        ).pack(side="left", padx=(10, 4), pady=7)

                    tk.Label(
                        linha, text=p["texto"], anchor="w", justify="left",
                        bg="#F8FAFC", fg=TEXT, font=("Segoe UI", 9),
                        wraplength=700
                    ).pack(side="left", fill="x", expand=True, padx=4, pady=7)
            else:
                tk.Label(
                    detalhe_interno,
                    text="Nenhum planejamento registrado para este dia.",
                    bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)
                ).pack(anchor="w", pady=4)

            tk.Label(
                detalhe_interno, text="Férias e presença",
                bg=WHITE, fg=TEXT, font=("Segoe UI", 11, "bold")
            ).pack(anchor="w", pady=(14, 5))

            if eventos:
                for e in eventos:
                    if e["tipo"] == "ferias":
                        titulo = "Férias aprovadas"
                        cor, fundo = GREEN, GREEN_LIGHT
                    elif e["tipo"] == "ferias_planejadas":
                        titulo = "Férias planejadas"
                        cor, fundo = ORANGE, YELLOW_LIGHT
                    else:
                        titulo = f"Feierabend {e['hora']}" if e["hora"] else "Feierabend"
                        cor, fundo = BLUE_DARK, BLUE_LIGHT

                    linha = tk.Frame(detalhe_interno, bg=fundo)
                    linha.pack(fill="x", pady=2)

                    texto = f"{e['nome']}: {titulo}"
                    if e["observacao"]:
                        texto += f" — {e['observacao']}"

                    tk.Label(
                        linha, text=texto, bg=fundo, fg=cor,
                        anchor="w", justify="left",
                        font=("Segoe UI Semibold", 9),
                        padx=10, pady=7
                    ).pack(side="left", fill="x", expand=True)

                    if login_atual == "priya" and e["tipo"] == "ferias_planejadas":
                        tk.Button(
                            linha, text="✓ Aprovar",
                            bg=WHITE, fg=GREEN, relief="flat", bd=0,
                            cursor="hand2", font=("Segoe UI Semibold", 8),
                            command=lambda eid=e["id"]: self.aprovar_ferias_tela(eid)
                        ).pack(side="right", padx=5, pady=4, ipadx=6, ipady=2)

                    if int(e["usuario_id"]) == int(self.usuario["id"]):
                        tk.Button(
                            linha, text="×",
                            bg=fundo, fg=TEXT_LIGHT, relief="flat", bd=0,
                            cursor="hand2", font=("Segoe UI", 10, "bold"),
                            command=lambda eid=e["id"]: self.excluir_evento_tela(eid)
                        ).pack(side="right", padx=(0, 7), pady=3)
            else:
                tk.Label(
                    detalhe_interno, text="Nenhum registro adicional.",
                    bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)
                ).pack(anchor="w", pady=4)

        # Índice de indicadores por dia. Não colocamos textos dentro das células:
        # apenas pequenos pontos, preservando o calendário limpo.
        indicadores = {}
        for e in eventos_mes:
            inicio = max(date.fromisoformat(e["data_inicio"]), primeiro)
            fim = min(date.fromisoformat(e["data_fim"]), ultimo)
            atual = inicio
            while atual <= fim:
                indicadores.setdefault(atual.day, set()).add(e["tipo"])
                atual += timedelta(days=1)

        matriz = calendar.monthcalendar(self.calendario_ano, self.calendario_mes)
        hoje = date.today()

        # Células do calendário: número em uma área própria + indicadores em uma faixa
        # separada. Evitamos usar place() sobre o botão, porque isso fazia os pontos
        # sobreporem os números e "vazarem" para outras semanas em algumas resoluções.
        for r, semana in enumerate(matriz, start=1):
            calendario_frame.grid_rowconfigure(r, minsize=58, weight=1, uniform="semana")

            for c, dia in enumerate(semana):
                cel = tk.Frame(
                    calendario_frame,
                    bg=WHITE,
                    highlightbackground="#EDF2F7",
                    highlightthickness=1
                )
                cel.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                cel.grid_columnconfigure(0, weight=1)
                cel.grid_rowconfigure(0, weight=1)
                cel.grid_rowconfigure(1, minsize=8)

                if dia == 0:
                    cel.configure(bg="#FAFBFD")
                    vazio = tk.Frame(cel, bg="#FAFBFD")
                    vazio.grid(row=0, column=0, rowspan=2, sticky="nsew")
                    continue

                atual = (
                    dia == hoje.day
                    and self.calendario_mes == hoje.month
                    and self.calendario_ano == hoje.year
                )
                fundo_normal = BLUE_LIGHT if atual else WHITE

                botao = tk.Button(
                    cel,
                    text=str(dia),
                    bg=fundo_normal,
                    fg=BLUE_DARK if atual else TEXT,
                    activebackground="#DCEAFF",
                    activeforeground=BLUE_DARK,
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    font=("Segoe UI Semibold", 10),
                    command=lambda d=dia: renderizar_dia(d)
                )
                botao.grid(row=0, column=0, sticky="nsew")

                # Indicadores discretos ficam numa faixa reservada no rodapé da célula.
                # Assim o calendário continua limpo e os marcadores nunca cobrem o dia.
                tipos = indicadores.get(dia, set())
                marcadores = tk.Frame(cel, bg=fundo_normal, height=8)
                marcadores.grid(row=1, column=0, sticky="ew")
                marcadores.grid_propagate(False)

                centro_marcadores = tk.Frame(marcadores, bg=fundo_normal)
                centro_marcadores.place(relx=0.5, rely=0.5, anchor="center")

                barras = []
                if "ferias" in tipos:
                    barra = tk.Frame(centro_marcadores, bg=GREEN, width=12, height=3)
                    barra.pack(side="left", padx=1)
                    barra.pack_propagate(False)
                    barras.append(barra)
                if "ferias_planejadas" in tipos:
                    barra = tk.Frame(centro_marcadores, bg=ORANGE, width=12, height=3)
                    barra.pack(side="left", padx=1)
                    barra.pack_propagate(False)
                    barras.append(barra)
                if "feierabend" in tipos:
                    barra = tk.Frame(centro_marcadores, bg=BLUE, width=12, height=3)
                    barra.pack(side="left", padx=1)
                    barra.pack_propagate(False)
                    barras.append(barra)

                def aplicar_fundo(cor, b=botao, celula=cel, rodape=marcadores, centro=centro_marcadores):
                    b.configure(bg=cor)
                    celula.configure(bg=cor)
                    rodape.configure(bg=cor)
                    centro.configure(bg=cor)

                # IMPORTANTE: capturamos a função desta célula nos argumentos padrão.
                # Sem isso, os callbacks do Tkinter terminavam todos apontando para a
                # última célula criada no mês (por exemplo, o dia 31).
                def entrar(event, aplicar=aplicar_fundo):
                    aplicar("#DCEAFF")

                def sair(event, aplicar=aplicar_fundo, f=fundo_normal):
                    aplicar(f)

                # Hover funciona tanto no número quanto na faixa inferior da célula.
                for widget_hover in (cel, botao, marcadores, centro_marcadores):
                    widget_hover.bind("<Enter>", entrar)
                    widget_hover.bind("<Leave>", sair)

                # A faixa inferior também seleciona o dia, evitando uma pequena área
                # "morta" abaixo do número.
                marcadores.bind("<Button-1>", lambda event, d=dia: renderizar_dia(d))
                centro_marcadores.bind("<Button-1>", lambda event, d=dia: renderizar_dia(d))
                for barra in barras:
                    barra.bind("<Button-1>", lambda event, d=dia: renderizar_dia(d))
                    barra.bind("<Enter>", entrar)
                    barra.bind("<Leave>", sair)

        dia_inicial = (
            hoje.day
            if self.calendario_mes == hoje.month and self.calendario_ano == hoje.year
            else 1
        )
        renderizar_dia(dia_inicial)


    def aprovar_ferias_tela(self, evento_id):
        try:
            aprovar_ferias(evento_id, self.usuario["id"])
        except (ValueError, PermissionError) as erro:
            messagebox.showwarning("Férias", str(erro))
            return
        self.mostrar_calendario()


    def excluir_evento_tela(self, evento_id):
        if not messagebox.askyesno("Calendário", "Excluir este registro do calendário?"):
            return
        try:
            excluir_evento_calendario(evento_id, self.usuario["id"])
        except PermissionError as erro:
            messagebox.showwarning("Calendário", str(erro))
            return
        self.mostrar_calendario()


    def abrir_editor_evento_calendario(self):
        perfil = self.usuario["perfil"]
        login = self.usuario["login"].lower()

        if perfil != "worker" and login not in PRESENCA_SETOR_LOGINS:
            return

        janela = tk.Toplevel(self.root)
        janela.title("Adicionar ao calendário")
        janela.geometry("540x520")
        janela.minsize(470, 460)
        janela.configure(bg=WHITE)
        janela.transient(self.root)
        janela.grab_set()

        frame = tk.Frame(janela, bg=WHITE)
        frame.pack(fill="both", expand=True, padx=25, pady=22)

        tk.Label(
            frame, text="Adicionar ao calendário",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 19, "bold")
        ).pack(anchor="w")

        tipos = ["Férias planejadas", "Férias confirmadas"]
        if login in PRESENCA_SETOR_LOGINS:
            tipos.append("Feierabend")

        tk.Label(frame, text="Tipo", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(18, 4))
        tipo_combo = ttk.Combobox(
            frame, values=tipos, state="readonly",
            style="Modern.TCombobox"
        )
        tipo_combo.pack(fill="x")
        tipo_combo.current(0)

        hoje = date.today().isoformat()

        tk.Label(frame, text="Data inicial (AAAA-MM-DD)", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(12, 4))
        inicio = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1)
        inicio.pack(fill="x", ipady=6)
        inicio.insert(0, hoje)

        tk.Label(frame, text="Data final (para férias)", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(12, 4))
        fim = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1)
        fim.pack(fill="x", ipady=6)
        fim.insert(0, hoje)

        tk.Label(frame, text="Hora de saída HH:MM (Feierabend)", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(12, 4))
        hora = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1)
        hora.pack(fill="x", ipady=6)
        hora.insert(0, "15:00")

        tk.Label(frame, text="Observação (opcional)", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(12, 4))
        obs = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1)
        obs.pack(fill="x", ipady=6)

        aviso = tk.Label(
            frame,
            text=(
                "Férias planejadas aparecem em amarelo. Quando Marion aprovar, "
                "o período passa a aparecer em verde."
            ),
            bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 8),
            justify="left", wraplength=460
        )
        aviso.pack(anchor="w", pady=(10, 0))

        def salvar():
            mapa = {
                "Férias planejadas": "ferias_planejadas",
                "Férias confirmadas": "ferias",
                "Feierabend": "feierabend"
            }
            tipo = mapa[tipo_combo.get()]
            di = inicio.get().strip()
            df = fim.get().strip() or di

            try:
                di_date = datetime.strptime(di, "%Y-%m-%d").date()
                df_date = datetime.strptime(df, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showwarning(
                    "Calendário", "Use datas no formato AAAA-MM-DD.", parent=janela
                )
                return

            if df_date < di_date:
                messagebox.showwarning(
                    "Calendário", "A data final não pode ser anterior à inicial.", parent=janela
                )
                return

            try:
                if tipo == "feierabend":
                    df = di
                    substituir_feierabend(
                        self.usuario["id"], di,
                        hora.get().strip(), obs.get().strip()
                    )
                else:
                    criar_evento_calendario(
                        self.usuario["id"], tipo, di, df, "", obs.get().strip()
                    )
            except ValueError as erro:
                messagebox.showwarning("Regra de presença", str(erro), parent=janela)
                return

            janela.destroy()
            self.mostrar_calendario()

        tk.Button(
            frame, text="Salvar",
            bg=BLUE, fg=WHITE, activebackground=BLUE_DARK,
            activeforeground=WHITE, relief="flat", bd=0,
            cursor="hand2", font=("Segoe UI Semibold", 9),
            command=salvar
        ).pack(anchor="e", pady=(18, 0), ipadx=18, ipady=6)

    def mes_anterior(self):

        self.calendario_mes -= 1

        if self.calendario_mes == 0:

            self.calendario_mes = 12
            self.calendario_ano -= 1

        self.mostrar_calendario()

    def proximo_mes(self):

        self.calendario_mes += 1

        if self.calendario_mes == 13:

            self.calendario_mes = 1
            self.calendario_ano += 1

        self.mostrar_calendario()

    # ========================================================
    # PLANOS A CONFERIR
    # ========================================================


    def mostrar_projetos(self):
        self.menu_atual = "projetos"
        self.marcar_menu("projetos")
        self.limpar_conteudo()

        self.titulo_pagina(
            "Projetos",
            "Cadastro central das obras em planejamento e produção de projetos."
        )

        area = tk.Frame(self.conteudo, bg=BG)
        area.pack(fill="both", expand=True, padx=30, pady=(0, 25))

        topo = tk.Frame(
            area, bg=WHITE,
            highlightbackground=BORDER, highlightthickness=1
        )
        topo.pack(fill="x", pady=(0, 12))

        filtros = tk.Frame(topo, bg=WHITE)
        filtros.pack(fill="x", padx=16, pady=12)

        tk.Label(
            filtros, text="Status:", bg=WHITE, fg=TEXT,
            font=("Segoe UI Semibold", 9)
        ).pack(side="left")

        status_combo = ttk.Combobox(
            filtros,
            values=["Ativo", "Pausado", "Finalizado", "Arquivado", "Todos"],
            state="readonly", width=15, style="Modern.TCombobox"
        )
        status_combo.set("Ativo")
        status_combo.pack(side="left", padx=(8, 14))

        pode_gerir = self.usuario["perfil"] in ("planner", "lead")

        if pode_gerir:
            tk.Button(
                filtros, text="+ Novo projeto",
                bg=BLUE, fg=WHITE, activebackground=BLUE_DARK,
                activeforeground=WHITE, relief="flat", bd=0,
                cursor="hand2", font=("Segoe UI Semibold", 9),
                command=lambda: self.abrir_editor_projeto()
            ).pack(side="right", ipadx=10, ipady=5)

        lista = tk.Frame(area, bg=BG)
        lista.pack(fill="both", expand=True)

        def renderizar(event=None):
            for w in lista.winfo_children():
                w.destroy()

            status = status_combo.get()
            projetos = buscar_projetos(None if status == "Todos" else status)

            if not projetos:
                self.criar_mensagem_vazia(
                    lista,
                    "Nenhum projeto neste status.",
                    "Os projetos cadastrados aparecerão aqui."
                )
                return

            for projeto in projetos:
                self.criar_card_projeto_central(lista, projeto, pode_gerir)

        status_combo.bind("<<ComboboxSelected>>", renderizar)
        renderizar()


    def criar_card_projeto_central(self, parent, projeto, pode_gerir=False):
        card = tk.Frame(
            parent, bg=WHITE,
            highlightbackground=BORDER, highlightthickness=1
        )
        card.pack(fill="x", pady=5)

        corpo = tk.Frame(card, bg=WHITE)
        corpo.pack(fill="x", padx=18, pady=14)

        linha_topo = tk.Frame(corpo, bg=WHITE)
        linha_topo.pack(fill="x")

        titulo = projeto["nome"]
        if projeto["codigo"]:
            titulo = f"{projeto['codigo']} · {titulo}"

        tk.Label(
            linha_topo, text=titulo, bg=WHITE, fg=TEXT,
            font=("Segoe UI", 13, "bold")
        ).pack(side="left")

        cor_status = {
            "Ativo": GREEN,
            "Pausado": ORANGE,
            "Finalizado": BLUE,
            "Arquivado": TEXT_LIGHT
        }.get(projeto["status"], TEXT_LIGHT)

        tk.Label(
            linha_topo, text=projeto["status"], bg="#F8FAFC",
            fg=cor_status, font=("Segoe UI Semibold", 8),
            padx=8, pady=4
        ).pack(side="right")

        meta = []
        if projeto["cliente"]:
            meta.append(projeto["cliente"])
        if projeto["endereco"]:
            meta.append(projeto["endereco"])
        if meta:
            tk.Label(
                corpo, text=" • ".join(meta), bg=WHITE, fg=TEXT_LIGHT,
                font=("Segoe UI", 9)
            ).pack(anchor="w", pady=(3, 0))

        if projeto["descricao"]:
            tk.Label(
                corpo, text=projeto["descricao"], bg=WHITE, fg=TEXT_LIGHT,
                font=("Segoe UI", 9), justify="left", anchor="w",
                wraplength=820
            ).pack(fill="x", anchor="w", pady=(4, 0))

        stats = estatisticas_projeto(projeto["id"])
        resumo = (
            f"{stats['abertas']} tarefas abertas  •  "
            f"{stats['concluidas']} concluídas  •  "
            f"{stats['solicitacoes']} envios para conferência"
        )
        if stats["pendentes"]:
            resumo += f"  •  {stats['pendentes']} pendente(s)"
        if stats["conversas"]:
            resumo += f"  •  {stats['conversas']} conversa(s)"

        tk.Label(
            corpo, text=resumo, bg=WHITE, fg=TEXT,
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(9, 0))

        botoes = tk.Frame(corpo, bg=WHITE)
        botoes.pack(fill="x", pady=(10, 0))

        if projeto["caminho"]:
            tk.Button(
                botoes, text="📂 Abrir pasta",
                bg=BLUE_LIGHT, fg=BLUE_DARK,
                activebackground="#DCEAFF", relief="flat", bd=0,
                cursor="hand2",
                command=lambda p=projeto: self.abrir_caminho(p["caminho"])
            ).pack(side="left", padx=(0, 5), ipadx=7, ipady=4)

        if pode_gerir:
            tk.Button(
                botoes, text="✎ Editar projeto",
                bg="#F1F5F9", fg=TEXT,
                activebackground="#E2E8F0", relief="flat", bd=0,
                cursor="hand2",
                command=lambda p=projeto: self.abrir_editor_projeto(p)
            ).pack(side="left", padx=3, ipadx=7, ipady=4)


    def abrir_editor_projeto(self, projeto=None):
        if self.usuario["perfil"] not in ("planner", "lead"):
            messagebox.showwarning(
                "Projetos",
                "Seu perfil pode consultar projetos, mas não alterar o cadastro."
            )
            return

        janela = tk.Toplevel(self.root)
        janela.title("Editar projeto" if projeto else "Novo projeto")
        janela.geometry("620x650")
        janela.minsize(520, 540)
        janela.configure(bg=WHITE)
        janela.transient(self.root)
        janela.grab_set()

        externo = tk.Frame(janela, bg=WHITE)
        externo.pack(fill="both", expand=True)
        canvas = tk.Canvas(externo, bg=WHITE, highlightthickness=0)
        sb = ttk.Scrollbar(
            externo, orient="vertical", command=canvas.yview,
            style="Modern.Vertical.TScrollbar"
        )
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame = tk.Frame(canvas, bg=WHITE)
        win = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(win, width=e.width)
        )

        interno = tk.Frame(frame, bg=WHITE)
        interno.pack(fill="both", expand=True, padx=28, pady=24)

        tk.Label(
            interno,
            text="Editar projeto" if projeto else "Novo projeto",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 20, "bold")
        ).pack(anchor="w")

        def campo_rotulo(texto):
            tk.Label(
                interno, text=texto, bg=WHITE, fg=TEXT,
                font=("Segoe UI Semibold", 9)
            ).pack(anchor="w", pady=(13, 4))

        campo_rotulo("Nome do projeto")
        nome = tk.Entry(interno, font=("Segoe UI", 10), relief="solid", bd=1)
        nome.pack(fill="x", ipady=7)

        linha = tk.Frame(interno, bg=WHITE)
        linha.pack(fill="x", pady=(0, 0))
        b1 = tk.Frame(linha, bg=WHITE)
        b1.pack(side="left", fill="x", expand=True, padx=(0, 6))
        b2 = tk.Frame(linha, bg=WHITE)
        b2.pack(side="left", fill="x", expand=True, padx=(6, 0))

        tk.Label(b1, text="Código / número", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(13, 4))
        codigo = tk.Entry(b1, font=("Segoe UI", 10), relief="solid", bd=1)
        codigo.pack(fill="x", ipady=7)

        tk.Label(b2, text="Cliente", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(13, 4))
        cliente = tk.Entry(b2, font=("Segoe UI", 10), relief="solid", bd=1)
        cliente.pack(fill="x", ipady=7)

        campo_rotulo("Endereço / obra")
        endereco = tk.Entry(interno, font=("Segoe UI", 10), relief="solid", bd=1)
        endereco.pack(fill="x", ipady=7)

        campo_rotulo("Caminho da pasta no servidor")
        caminho = tk.Entry(interno, font=("Segoe UI", 10), relief="solid", bd=1)
        caminho.pack(fill="x", ipady=7)

        campo_rotulo("Status")
        status = ttk.Combobox(
            interno,
            values=["Ativo", "Pausado", "Finalizado", "Arquivado"],
            state="readonly", style="Modern.TCombobox"
        )
        status.set("Ativo")
        status.pack(fill="x")

        campo_rotulo("Descrição / observações")
        descricao = tk.Text(
            interno, height=7, font=("Segoe UI", 10),
            relief="solid", bd=1, wrap="word", padx=8, pady=7
        )
        descricao.pack(fill="x")

        if projeto:
            nome.insert(0, projeto["nome"])
            codigo.insert(0, projeto["codigo"] or "")
            cliente.insert(0, projeto["cliente"] or "")
            endereco.insert(0, projeto["endereco"] or "")
            caminho.insert(0, projeto["caminho"] or "")
            status.set(projeto["status"] or "Ativo")
            descricao.insert("1.0", projeto["descricao"] or "")

        def salvar():
            try:
                if projeto:
                    atualizar_projeto(
                        projeto["id"],
                        nome.get().strip(),
                        endereco.get().strip(),
                        caminho.get().strip(),
                        descricao.get("1.0", "end-1c").strip(),
                        codigo.get().strip(),
                        cliente.get().strip(),
                        status.get()
                    )
                else:
                    criar_projeto(
                        nome.get().strip(),
                        endereco.get().strip(),
                        caminho.get().strip(),
                        descricao.get("1.0", "end-1c").strip(),
                        self.usuario["id"],
                        codigo.get().strip(),
                        cliente.get().strip(),
                        status.get()
                    )
            except (ValueError, sqlite3.IntegrityError) as erro:
                messagebox.showwarning("Projetos", str(erro), parent=janela)
                return

            janela.destroy()
            self.mostrar_projetos()

        tk.Button(
            interno, text="Salvar projeto",
            bg=BLUE, fg=WHITE, activebackground=BLUE_DARK,
            activeforeground=WHITE, relief="flat", bd=0,
            cursor="hand2", font=("Segoe UI Semibold", 10),
            command=salvar
        ).pack(anchor="e", pady=(16, 0), ipadx=14, ipady=6)


    def mostrar_conferencias(self):
        self.menu_atual = "conferencias"
        self.marcar_menu("conferencias")
        self.limpar_conteudo()

        self.titulo_pagina(
            "Planos a conferir",
            "Envios privados por grupo. Você só vê os planos relacionados ao seu setor."
        )

        area = tk.Frame(self.conteudo, bg=BG)
        area.pack(fill="both", expand=True, padx=30, pady=(0, 25))

        topo = tk.Frame(
            area, bg=WHITE,
            highlightbackground=BORDER, highlightthickness=1
        )
        topo.pack(fill="x", pady=(0, 12))

        info = tk.Frame(topo, bg=WHITE)
        info.pack(fill="x", padx=16, pady=12)

        login = self.usuario["login"].lower()
        grupo = grupo_conferencia(login)
        if login == "dana":
            texto_grupo = "Conferidor geral · acesso aos dois grupos"
        elif grupo == "grupo_1":
            texto_grupo = "Grupo: Alaa · Azat · Herbert · Bene"
        elif grupo == "grupo_2":
            texto_grupo = "Grupo: Henrique · Anni · Steffen · Bilal · Marion · Bene"
        else:
            texto_grupo = "Seus envios ficam privados; Bene permanece como conferidor geral."

        tk.Label(
            info, text=texto_grupo, bg=WHITE, fg=TEXT_LIGHT,
            font=("Segoe UI", 9)
        ).pack(side="left")

        if login != "dana":
            tk.Button(
                info, text="+ Enviar plano para conferência",
                bg=BLUE, fg=WHITE, activebackground=BLUE_DARK,
                activeforeground=WHITE, relief="flat", bd=0,
                cursor="hand2", font=("Segoe UI Semibold", 9),
                command=self.abrir_editor_solicitacao
            ).pack(side="right", ipadx=10, ipady=5)

        lista = tk.Frame(area, bg=BG)
        lista.pack(fill="both", expand=True)

        solicitacoes = buscar_solicitacoes_visiveis(login)

        if not solicitacoes:
            self.criar_mensagem_vazia(
                lista,
                "Nenhum plano disponível para você.",
                "Quando alguém do seu grupo enviar um plano, ele aparecerá aqui."
            )
            return

        for solicitacao in solicitacoes:
            self.criar_card_solicitacao(lista, solicitacao)


    def abrir_editor_solicitacao(self):
        if self.usuario["login"].lower() == "dana":
            return

        projetos = buscar_projetos("Ativo")
        if not projetos:
            messagebox.showwarning(
                "Planos a conferir",
                "Não há projetos ativos. O planejamento/chefia precisa cadastrar um projeto primeiro."
            )
            return

        janela = tk.Toplevel(self.root)
        janela.title("Enviar plano para conferência")
        janela.geometry("620x590")
        janela.minsize(520, 500)
        janela.configure(bg=WHITE)
        janela.transient(self.root)
        janela.grab_set()

        frame = tk.Frame(janela, bg=WHITE)
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        tk.Label(
            frame, text="Enviar plano para conferência",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 20, "bold")
        ).pack(anchor="w")

        grupo = grupo_conferencia(self.usuario["login"])
        if grupo == "grupo_1":
            destino = "Visível para Alaa, Azat, Herbert e Bene."
        elif grupo == "grupo_2":
            destino = "Visível para Henrique, Anni, Steffen, Bilal, Marion e Bene."
        else:
            destino = "Visível para você e para Bene."
        tk.Label(
            frame, text=destino, bg=WHITE, fg=TEXT_LIGHT,
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(3, 14))

        tk.Label(frame, text="Projeto", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(8, 4))
        nomes = [p["nome"] for p in projetos]
        combo = ttk.Combobox(
            frame, values=nomes, state="readonly",
            style="Modern.TCombobox"
        )
        combo.pack(fill="x")
        combo.current(0)

        tk.Label(frame, text="Plano / tipo de desenho", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(13, 4))
        nome_plano = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1)
        nome_plano.pack(fill="x", ipady=7)

        tk.Label(frame, text="Caminho do arquivo ou da pasta", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(13, 4))
        caminho = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1)
        caminho.pack(fill="x", ipady=7)

        tk.Label(frame, text="Observação", bg=WHITE, fg=TEXT,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(13, 4))
        descricao = tk.Text(
            frame, height=7, font=("Segoe UI", 10),
            relief="solid", bd=1, wrap="word", padx=8, pady=7
        )
        descricao.pack(fill="both", expand=True)

        def salvar():
            idx = combo.current()
            if idx < 0:
                return
            try:
                criar_solicitacao_conferencia(
                    projetos[idx]["id"],
                    self.usuario["id"],
                    nome_plano.get().strip(),
                    caminho.get().strip(),
                    descricao.get("1.0", "end-1c").strip()
                )
            except (ValueError, PermissionError) as erro:
                messagebox.showwarning("Conferência", str(erro), parent=janela)
                return

            janela.destroy()
            self.mostrar_conferencias()

        tk.Button(
            frame, text="Enviar para conferência",
            bg=BLUE, fg=WHITE, activebackground=BLUE_DARK,
            activeforeground=WHITE, relief="flat", bd=0,
            cursor="hand2", font=("Segoe UI Semibold", 10),
            command=salvar
        ).pack(anchor="e", pady=(16, 0), ipadx=12, ipady=6)


    def criar_card_solicitacao(self, parent, solicitacao):
        card = tk.Frame(
            parent, bg=WHITE,
            highlightbackground=BORDER, highlightthickness=1
        )
        card.pack(fill="x", pady=5)

        corpo = tk.Frame(card, bg=WHITE)
        corpo.pack(fill="x", padx=18, pady=14)

        topo = tk.Frame(corpo, bg=WHITE)
        topo.pack(fill="x")

        tk.Label(
            topo,
            text=f"{solicitacao['projeto_nome']} · {solicitacao['nome_plano']}",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 13, "bold")
        ).pack(side="left", anchor="w")

        if solicitacao["estado"] == "conferido":
            badge_texto = (
                f"✓ Conferido por {solicitacao['conferidor_nome'] or 'Conferidor'}"
                f" — {self.formatar_data_hora(solicitacao['conferido_em'])}"
            )
            badge_bg, badge_fg = GREEN_LIGHT, GREEN
        else:
            badge_texto = "● Aguardando conferência"
            badge_bg, badge_fg = YELLOW_LIGHT, ORANGE

        tk.Label(
            corpo, text=badge_texto, bg=badge_bg, fg=badge_fg,
            font=("Segoe UI Semibold", 9), padx=9, pady=5
        ).pack(anchor="w", pady=(7, 3))

        tk.Label(
            corpo,
            text=(
                f"Enviado por {solicitacao['autor_nome']} · "
                f"{self.formatar_data_hora(solicitacao['criado_em'])}"
            ),
            bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(2, 0))

        if solicitacao["descricao"]:
            tk.Label(
                corpo, text=solicitacao["descricao"],
                bg=WHITE, fg=TEXT, font=("Segoe UI", 9),
                justify="left", anchor="w", wraplength=820
            ).pack(fill="x", anchor="w", pady=(7, 0))

        # Status operacional é privado para edição do autor.
        linha_status = tk.Frame(corpo, bg=WHITE)
        linha_status.pack(fill="x", pady=(9, 2))
        tk.Label(
            linha_status, text="Status do plano:",
            bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI Semibold", 8)
        ).pack(side="left")

        eh_autor = int(self.usuario["id"]) == int(solicitacao["autor_id"])
        if eh_autor:
            status_combo = ttk.Combobox(
                linha_status,
                values=["Em andamento", "Ajustar após conferência", "Concluído"],
                state="readonly", width=25, style="Modern.TCombobox"
            )
            status_combo.set(solicitacao["status_operacional"])
            status_combo.pack(side="left", padx=8)

            def salvar_status(event=None, sid=solicitacao["id"], combo=status_combo):
                try:
                    atualizar_status_solicitacao(sid, self.usuario["id"], combo.get())
                except (ValueError, PermissionError) as erro:
                    messagebox.showwarning("Status", str(erro))
                    return
                self.mostrar_conferencias()

            status_combo.bind("<<ComboboxSelected>>", salvar_status)
        else:
            tk.Label(
                linha_status, text=solicitacao["status_operacional"],
                bg="#F1F5F9", fg=TEXT,
                font=("Segoe UI Semibold", 8), padx=8, pady=4
            ).pack(side="left", padx=8)

        botoes = tk.Frame(corpo, bg=WHITE)
        botoes.pack(fill="x", pady=(9, 0))

        caminho_abrir = solicitacao["caminho"] or solicitacao["projeto_caminho"]
        if caminho_abrir:
            tk.Button(
                botoes, text="📂 Abrir arquivo/pasta",
                bg=BLUE_LIGHT, fg=BLUE_DARK,
                activebackground="#DCEAFF", relief="flat", bd=0,
                cursor="hand2",
                command=lambda c=caminho_abrir: self.abrir_caminho(c)
            ).pack(side="left", padx=(0, 4), ipadx=6, ipady=4)

        # O autor nunca vê "Conferir". Fora do grupo, o registro nem chega à tela.
        if (
            not eh_autor
            and solicitacao["estado"] == "aguardando"
            and pode_conferir_plano(
                self.usuario["login"],
                solicitacao["autor_login"]
            )
        ):
            tk.Button(
                botoes, text="✓ Conferir",
                bg=GREEN_LIGHT, fg=GREEN,
                activebackground="#D6F4E5", relief="flat", bd=0,
                cursor="hand2", font=("Segoe UI Semibold", 9),
                command=lambda s=solicitacao: self.conferir_solicitacao_tela(s)
            ).pack(side="left", padx=3, ipadx=7, ipady=4)

        tk.Button(
            botoes, text="Histórico",
            bg="#F1F5F9", fg=TEXT,
            activebackground="#E2E8F0", relief="flat", bd=0,
            cursor="hand2",
            command=lambda s=solicitacao: self.ver_historico_solicitacao(s)
        ).pack(side="left", padx=3, ipadx=7, ipady=4)


    def _metodo_legado_card_projeto(self, parent, projeto):
        """Mantido apenas para compatibilidade interna da V6; a V7 usa solicitações."""
        return


    def conferir_solicitacao_tela(self, solicitacao):
        if not pode_conferir_plano(
            self.usuario["login"],
            solicitacao["autor_login"]
        ):
            messagebox.showwarning(
                "Conferência",
                "Você não está no grupo autorizado para conferir este plano."
            )
            return

        observacao = ""
        resposta = messagebox.askyesno(
            "Conferir plano",
            (
                f"Marcar como conferido?\n\n"
                f"Projeto: {solicitacao['projeto_nome']}\n"
                f"Plano: {solicitacao['nome_plano']}\n"
                f"Autor: {solicitacao['autor_nome']}"
            )
        )
        if not resposta:
            return

        try:
            conferir_solicitacao(
                solicitacao["id"],
                self.usuario["id"],
                observacao
            )
        except (ValueError, PermissionError) as erro:
            messagebox.showwarning("Conferência", str(erro))
            return

        messagebox.showinfo(
            "Conferência registrada",
            f"{solicitacao['nome_plano']} conferido por {self.usuario['nome']}."
        )
        self.mostrar_conferencias()


    def ver_historico_solicitacao(self, solicitacao):
        registros = buscar_historico_solicitacao(solicitacao["id"])

        janela = tk.Toplevel(self.root)
        janela.title("Histórico de conferência")
        janela.geometry("700x480")
        janela.minsize(560, 380)
        janela.configure(bg=WHITE)

        externo = tk.Frame(janela, bg=WHITE)
        externo.pack(fill="both", expand=True)
        canvas = tk.Canvas(externo, bg=WHITE, highlightthickness=0)
        sb = ttk.Scrollbar(
            externo, orient="vertical", command=canvas.yview,
            style="Modern.Vertical.TScrollbar"
        )
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        frame = tk.Frame(canvas, bg=WHITE)
        win = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        interno = tk.Frame(frame, bg=WHITE)
        interno.pack(fill="both", expand=True, padx=25, pady=25)

        tk.Label(
            interno,
            text=f"{solicitacao['projeto_nome']} · {solicitacao['nome_plano']}",
            bg=WHITE, fg=TEXT, font=("Segoe UI", 18, "bold")
        ).pack(anchor="w")
        tk.Label(
            interno, text=f"Autor: {solicitacao['autor_nome']}",
            bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(3, 14))

        if not registros:
            tk.Label(
                interno, text="Ainda não há histórico.",
                bg=WHITE, fg=TEXT_LIGHT
            ).pack(anchor="w", pady=20)
            return

        for registro in registros:
            linha = tk.Frame(interno, bg="#F8FAFC")
            linha.pack(fill="x", pady=3)
            nome = registro["usuario_nome"] or "Sistema"
            texto = registro["texto"] or registro["tipo"]
            tk.Label(
                linha,
                text=f"{self.formatar_data_hora(registro['criado_em'])} · {nome}\n{texto}",
                bg="#F8FAFC", fg=TEXT, justify="left", anchor="w",
                font=("Segoe UI", 9), padx=10, pady=8
            ).pack(fill="x")

    # ========================================================
    # INFORMAÇÕES
    # ========================================================

    def mostrar_informacoes(self):

        self.menu_atual = "informacoes"

        self.marcar_menu("informacoes")

        self.limpar_conteudo()

        perfil = self.usuario["perfil"]

        if perfil in (
            "planner",
            "lead"
        ):

            self.mostrar_informacoes_envio()

        else:

            self.mostrar_informacoes_recebidas()

    def mostrar_informacoes_recebidas(self):

        self.titulo_pagina(
            "Informações adicionais",
            "Orientações, documentos e informações enviadas para você."
        )

        area = tk.Frame(
            self.conteudo,
            bg=BG
        )

        area.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(0, 25)
        )

        registros = buscar_informacoes_para_usuario(
            self.usuario["id"]
        )

        if not registros:

            self.criar_mensagem_vazia(
                area,
                "Nenhuma informação nova.",
                "Quando o planejamento ou a chefia enviar alguma informação, ela aparecerá aqui."
            )

            return

        for registro in registros:

            self.criar_card_informacao(
                area,
                registro
            )

    def criar_card_informacao(
        self,
        parent,
        registro
    ):

        lida = informacao_foi_lida(
            registro["id"],
            self.usuario["id"]
        )

        cor = (
            GREEN
            if lida
            else ORANGE
        )

        card = tk.Frame(
            parent,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        card.pack(
            fill="x",
            pady=5
        )

        faixa = tk.Frame(
            card,
            bg=cor,
            width=5
        )

        faixa.pack(
            side="left",
            fill="y"
        )

        corpo = tk.Frame(
            card,
            bg=WHITE
        )

        corpo.pack(
            fill="x",
            padx=15,
            pady=13
        )

        topo = tk.Frame(
            corpo,
            bg=WHITE
        )

        topo.pack(
            fill="x"
        )

        tk.Label(
            topo,
            text=registro["titulo"],
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI", 12, "bold")
        ).pack(
            side="left"
        )

        tk.Label(
            topo,
            text=(
                "✓ Lido"
                if lida
                else "● Nova"
            ),
            bg=WHITE,
            fg=cor,
            font=("Segoe UI Semibold", 8)
        ).pack(
            side="right"
        )

        projeto = (
            registro["projeto_nome"]
            or "Sem projeto"
        )

        tk.Label(
            corpo,
            text=(
                f"Projeto: {projeto}   •   "
                f"De: {registro['autor_nome']}"
            ),
            bg=WHITE,
            fg=TEXT_LIGHT,
            font=("Segoe UI", 9)
        ).pack(
            anchor="w",
            pady=(3, 5)
        )

        tk.Label(
            corpo,
            text=registro["texto"],
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI", 10),
            justify="left",
            wraplength=850
        ).pack(
            anchor="w"
        )

        anexos = buscar_anexos(
            registro["id"]
        )

        if anexos:

            anexos_frame = tk.Frame(
                corpo,
                bg=WHITE
            )

            anexos_frame.pack(
                anchor="w",
                pady=(8, 0)
            )

            for anexo in anexos:

                tk.Button(
                    anexos_frame,
                    text="📎 " + anexo["nome"],
                    bg=BLUE_LIGHT,
                    fg=BLUE_DARK,
                    relief="flat",
                    bd=0,
                    cursor="hand2",
                    command=lambda a=anexo: self.abrir_caminho(
                        a["caminho"]
                    )
                ).pack(
                    side="left",
                    padx=3
                )

        caminho_pasta = registro["caminho_pasta"] if "caminho_pasta" in registro.keys() else ""
        if caminho_pasta:
            tk.Button(
                corpo,
                text="📂 Abrir pasta",
                bg="#F1F5F9",
                fg=TEXT,
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda c=caminho_pasta: self.abrir_caminho(c)
            ).pack(anchor="w", pady=(8, 0))

        if not lida:

            tk.Button(
                corpo,
                text="✓ Marcar como visto",
                bg=GREEN_LIGHT,
                fg=GREEN,
                relief="flat",
                bd=0,
                cursor="hand2",
                command=lambda r=registro: self.marcar_informacao_vista(
                    r["id"]
                )
            ).pack(
                anchor="e",
                pady=(8, 0)
            )

    def marcar_informacao_vista(
        self,
        informacao_id
    ):

        marcar_informacao_lida(
            informacao_id,
            self.usuario["id"]
        )

        self.mostrar_informacoes()

    def mostrar_informacoes_envio(self):

        self.titulo_pagina(
            "Informações adicionais",
            "Envie orientações, documentos e informações para os trabalhadores."
        )

        area = tk.Frame(
            self.conteudo,
            bg=BG
        )

        area.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=(0, 25)
        )

        # ----------------------------------------------------
        # FORMULÁRIO
        # ----------------------------------------------------

        formulario = tk.Frame(
            area,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        formulario.pack(
            fill="x"
        )

        interno = tk.Frame(
            formulario,
            bg=WHITE
        )

        interno.pack(
            fill="x",
            padx=20,
            pady=18
        )

        tk.Label(
            interno,
            text="Enviar nova informação",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI", 15, "bold")
        ).pack(
            anchor="w"
        )

        linha = tk.Frame(
            interno,
            bg=WHITE
        )

        linha.pack(
            fill="x",
            pady=(15, 0)
        )

        # trabalhador
        bloco1 = tk.Frame(
            linha,
            bg=WHITE
        )

        bloco1.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 8)
        )

        tk.Label(
            bloco1,
            text="Trabalhador",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI Semibold", 9)
        ).pack(
            anchor="w"
        )

        trabalhadores = buscar_trabalhadores()

        nomes_trabalhadores = [
            t["nome"]
            for t in trabalhadores
        ]

        trabalhador_combo = ttk.Combobox(
            bloco1,
            values=nomes_trabalhadores,
            state="readonly",
            style="Modern.TCombobox"
        )

        trabalhador_combo.pack(
            fill="x",
            pady=(4, 0)
        )

        if nomes_trabalhadores:
            trabalhador_combo.current(0)

        # projeto
        bloco2 = tk.Frame(
            linha,
            bg=WHITE
        )

        bloco2.pack(
            side="left",
            fill="x",
            expand=True,
            padx=(8, 0)
        )

        tk.Label(
            bloco2,
            text="Projeto",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI Semibold", 9)
        ).pack(
            anchor="w"
        )

        projetos = buscar_projetos()

        nomes_projetos = [
            p["nome"]
            for p in projetos
        ]

        projeto_combo = ttk.Combobox(
            bloco2,
            values=nomes_projetos,
            state="readonly",
            style="Modern.TCombobox"
        )

        projeto_combo.pack(
            fill="x",
            pady=(4, 0)
        )

        if nomes_projetos:
            projeto_combo.current(0)

        tk.Label(
            interno,
            text="Título",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI Semibold", 9)
        ).pack(
            anchor="w",
            pady=(15, 4)
        )

        titulo = tk.Entry(
            interno,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1
        )

        titulo.pack(
            fill="x",
            ipady=7
        )

        linha2 = tk.Frame(
            interno,
            bg=WHITE
        )

        linha2.pack(
            fill="x",
            pady=(12, 0)
        )

        tk.Label(
            linha2,
            text="Prioridade",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI Semibold", 9)
        ).pack(
            side="left"
        )

        prioridade_combo = ttk.Combobox(
            linha2,
            values=[
                "Baixa",
                "Normal",
                "Alta",
                "Urgente"
            ],
            state="readonly",
            width=12,
            style="Modern.TCombobox"
        )

        prioridade_combo.pack(
            side="left",
            padx=10
        )

        prioridade_combo.set(
            "Normal"
        )

        tk.Label(
            interno,
            text="Caminho da pasta no servidor (opcional)",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI Semibold", 9)
        ).pack(anchor="w", pady=(12, 4))

        caminho_pasta = tk.Entry(
            interno,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1
        )
        caminho_pasta.pack(fill="x", ipady=7)

        tk.Label(
            interno,
            text="Mensagem",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI Semibold", 9)
        ).pack(
            anchor="w",
            pady=(12, 4)
        )

        mensagem = tk.Text(
            interno,
            height=5,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1,
            wrap="word"
        )

        mensagem.pack(
            fill="x"
        )

        anexos_selecionados = []

        anexos_label = tk.Label(
            interno,
            text="Nenhum anexo selecionado.",
            bg=WHITE,
            fg=TEXT_LIGHT,
            font=("Segoe UI", 8)
        )

        anexos_label.pack(
            anchor="w",
            pady=(8, 0)
        )

        def selecionar_anexos():

            arquivos = filedialog.askopenfilenames(
                title="Selecionar anexos"
            )

            if arquivos:

                anexos_selecionados.clear()

                anexos_selecionados.extend(
                    arquivos
                )

                anexos_label.configure(
                    text=(
                        f"{len(arquivos)} "
                        f"arquivo(s) selecionado(s)."
                    )
                )

        botoes = tk.Frame(
            interno,
            bg=WHITE
        )

        botoes.pack(
            fill="x",
            pady=(12, 0)
        )

        tk.Button(
            botoes,
            text="📎 Anexar arquivos",
            bg="#F1F5F9",
            fg=TEXT,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=selecionar_anexos
        ).pack(
            side="left",
            ipadx=8,
            ipady=5
        )

        def enviar():

            if not trabalhadores:
                return

            indice = trabalhador_combo.current()

            if indice < 0:
                messagebox.showwarning(
                    "Informação",
                    "Selecione um trabalhador."
                )
                return

            trabalhador = trabalhadores[indice]

            projeto_id = None

            indice_projeto = projeto_combo.current()

            if 0 <= indice_projeto < len(projetos):
                projeto_id = projetos[indice_projeto]["id"]

            titulo_texto = (
                titulo.get().strip()
            )

            mensagem_texto = mensagem.get(
                "1.0",
                "end-1c"
            ).strip()

            if not titulo_texto:

                messagebox.showwarning(
                    "Informação",
                    "Digite um título."
                )

                return

            if not mensagem_texto:

                messagebox.showwarning(
                    "Informação",
                    "Digite a mensagem."
                )

                return

            informacao_id = criar_informacao(
                trabalhador["id"],
                projeto_id,
                self.usuario["id"],
                titulo_texto,
                mensagem_texto,
                prioridade_combo.get(),
                caminho_pasta.get().strip()
            )

            for arquivo in anexos_selecionados:

                try:

                    adicionar_anexo(
                        informacao_id,
                        projeto_id,
                        arquivo
                    )

                except Exception as erro:

                    messagebox.showwarning(
                        "Anexo",
                        f"Não foi possível anexar:\n{arquivo}\n\n{erro}"
                    )

            messagebox.showinfo(
                "Enviado",
                f"Informação enviada para {trabalhador['nome']}."
            )

            titulo.delete(
                0,
                "end"
            )

            mensagem.delete(
                "1.0",
                "end"
            )

            anexos_selecionados.clear()

            anexos_label.configure(
                text="Nenhum anexo selecionado."
            )

            self.mostrar_informacoes()

        tk.Button(
            botoes,
            text="Enviar informação",
            bg=BLUE,
            fg=WHITE,
            activebackground=BLUE_DARK,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            command=enviar
        ).pack(
            side="right",
            ipadx=12,
            ipady=6
        )

        # ----------------------------------------------------
        # HISTÓRICO
        # ----------------------------------------------------

        historico = tk.Frame(
            area,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        historico.pack(
            fill="both",
            expand=True,
            pady=(12, 0)
        )

        tk.Label(
            historico,
            text="Informações enviadas",
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI", 13, "bold")
        ).pack(
            anchor="w",
            padx=18,
            pady=(14, 8)
        )

        registros = buscar_todas_informacoes()

        for registro in registros[:8]:

            lido = informacao_foi_lida(
                registro["id"],
                registro["trabalhador_id"]
            )

            linha = tk.Frame(
                historico,
                bg="#FBFCFE"
            )

            linha.pack(
                fill="x",
                padx=15,
                pady=2
            )

            tk.Label(
                linha,
                text=(
                    f"{registro['titulo']} — "
                    f"{registro['trabalhador_nome']} — "
                    f"{registro['projeto_nome'] or 'Sem projeto'}"
                ),
                bg="#FBFCFE",
                fg=TEXT,
                font=("Segoe UI", 9)
            ).pack(
                side="left",
                padx=10,
                pady=7
            )

            tk.Label(
                linha,
                text="✓ Visualizado"
                if lido
                else "● Não visualizado",
                bg="#FBFCFE",
                fg=GREEN
                if lido
                else ORANGE,
                font=("Segoe UI", 8)
            ).pack(
                side="right",
                padx=10
            )

    # ========================================================
    # UTILITÁRIOS
    # ========================================================

    def criar_mensagem_vazia(
        self,
        parent,
        titulo,
        subtitulo
    ):

        frame = tk.Frame(
            parent,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        frame.pack(
            fill="x",
            pady=10
        )

        tk.Label(
            frame,
            text=titulo,
            bg=WHITE,
            fg=TEXT,
            font=("Segoe UI", 13, "bold")
        ).pack(
            pady=(25, 5)
        )

        tk.Label(
            frame,
            text=subtitulo,
            bg=WHITE,
            fg=TEXT_LIGHT,
            font=("Segoe UI", 9)
        ).pack(
            pady=(0, 25)
        )

    def abrir_caminho(
        self,
        caminho
    ):

        if not caminho:
            return

        try:

            if os.path.exists(caminho):

                os.startfile(caminho)

            else:

                webbrowser.open(
                    caminho
                )

        except Exception as erro:

            messagebox.showerror(
                "Abrir projeto",
                f"Não foi possível abrir o local:\n\n{caminho}\n\n{erro}"
            )

    def formatar_data(
        self,
        data_str
    ):

        try:

            data = datetime.strptime(
                data_str,
                "%Y-%m-%d"
            )

            return data.strftime(
                "%d/%m/%Y"
            )

        except Exception:

            return data_str

    def formatar_data_hora(
        self,
        data_str
    ):

        try:

            data = datetime.strptime(
                data_str,
                "%Y-%m-%d %H:%M:%S"
            )

            return data.strftime(
                "%d/%m/%Y %H:%M"
            )

        except Exception:

            return data_str

    # ========================================================
    # SENHA E BACKUP
    # ========================================================

    def abrir_troca_senha(self):
        janela = tk.Toplevel(self.root)
        janela.title("Change password")
        janela.geometry("380x340")
        janela.configure(bg=WHITE)
        janela.transient(self.root)
        janela.grab_set()

        frame = tk.Frame(janela, bg=WHITE)
        frame.pack(fill="both", expand=True, padx=25, pady=25)

        tk.Label(frame, text="Change password", bg=WHITE, fg=TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w")

        tk.Label(frame, text="Current password", bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)).pack(anchor="w", pady=(18, 3))
        atual_entry = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1, show="●")
        atual_entry.pack(fill="x", ipady=7)

        tk.Label(frame, text="New password", bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)).pack(anchor="w", pady=(14, 3))
        nova_entry = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1, show="●")
        nova_entry.pack(fill="x", ipady=7)

        tk.Label(frame, text="Confirm new password", bg=WHITE, fg=TEXT_LIGHT, font=("Segoe UI", 9)).pack(anchor="w", pady=(14, 3))
        confirmar_entry = tk.Entry(frame, font=("Segoe UI", 10), relief="solid", bd=1, show="●")
        confirmar_entry.pack(fill="x", ipady=7)

        def salvar():
            senha_atual = atual_entry.get()
            senha_nova = nova_entry.get()
            senha_confirmar = confirmar_entry.get()

            if senha_nova != senha_confirmar:
                messagebox.showwarning("Change password", "The new password and confirmation do not match.")
                return

            try:
                alterar_senha(self.usuario["id"], senha_atual, senha_nova)
            except ValueError as erro:
                messagebox.showerror("Change password", str(erro))
                return

            janela.destroy()
            messagebox.showinfo("Change password", "Password changed successfully.")

        tk.Button(
            frame, text="Save new password", bg=BLUE, fg=WHITE,
            activebackground=BLUE_DARK, activeforeground=WHITE,
            relief="flat", bd=0, command=salvar, cursor="hand2"
        ).pack(anchor="e", pady=(20, 0), ipadx=14, ipady=6)

    def fazer_backup_banco(self):
        try:
            destino = criar_backup_banco()
        except Exception as erro:
            messagebox.showerror("Backup", f"Could not create the backup:\n\n{erro}")
            return
        messagebox.showinfo("Backup", f"Backup created successfully at:\n\n{destino}")

    # ========================================================
    # LOGOUT
    # ========================================================

    def logout(self):

        resposta = messagebox.askyesno(
            "Log out",
            "Are you sure you want to log out?"
        )

        if not resposta:
            return

        self.usuario = None

        self.menu_atual = None

        self.trabalhadores = []

        self.trabalhador_selecionado = None

        self.mostrar_login()


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        criar_banco()

    except Exception as erro:

        root_erro = tk.Tk()
        root_erro.withdraw()

        messagebox.showerror(
            "Erro ao criar banco",
            "Não foi possível iniciar o banco de dados:\n\n"
            + str(erro)
        )

        root_erro.destroy()

        return

    root = tk.Tk()

    app = MeuOrganizador(
        root
    )

    root.mainloop()




if __name__ == "__main__":
    main()