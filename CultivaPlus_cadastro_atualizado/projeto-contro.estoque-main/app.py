import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-por-uma-chave-segura")
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banco.db")


def conectar_banco():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def inicializar_banco():
    """Cria tabelas e adiciona as colunas de proprietário sem apagar dados existentes."""
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            principio_ativo TEXT NOT NULL,
            fabricante TEXT,
            quantidade REAL NOT NULL DEFAULT 0,
            unidade TEXT NOT NULL,
            periodo_carencia INTEGER NOT NULL DEFAULT 0,
            usuario_id INTEGER REFERENCES usuarios(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            quantidade REAL NOT NULL,
            data TEXT NOT NULL,
            observacao TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS talhoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            area REAL NOT NULL,
            cultura TEXT NOT NULL,
            usuario_id INTEGER REFERENCES usuarios(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aplicacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            talhao_id INTEGER NOT NULL,
            quantidade REAL NOT NULL,
            data_aplicacao TEXT NOT NULL,
            data_liberacao TEXT NOT NULL,
            observacao TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id),
            FOREIGN KEY (talhao_id) REFERENCES talhoes(id)
        )
    """)

    # Migração para bancos criados antes do isolamento por usuário.
    for tabela in ("produtos", "talhoes"):
        colunas = {linha["name"] for linha in cursor.execute(f"PRAGMA table_info({tabela})")}
        if "usuario_id" not in colunas:
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id)")

    # Se houver exatamente uma conta, associa a ela os registros antigos sem proprietário.
    # Se houver várias contas, os registros antigos ficam sem proprietário até serem
    # atribuídos manualmente, evitando entregar dados compartilhados à conta errada.
    quantidade_usuarios = cursor.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if quantidade_usuarios == 1:
        unico_usuario = cursor.execute("SELECT id FROM usuarios LIMIT 1").fetchone()["id"]
        cursor.execute("UPDATE produtos SET usuario_id = ? WHERE usuario_id IS NULL", (unico_usuario,))
        cursor.execute("UPDATE talhoes SET usuario_id = ? WHERE usuario_id IS NULL", (unico_usuario,))

    conexao.commit()
    conexao.close()


@app.before_request
def proteger_paginas():
    paginas_publicas = ("login", "cadastro", "static")
    if request.endpoint is not None and request.endpoint not in paginas_publicas:
        if "usuario_id" not in session:
            return redirect(url_for("login"))


def usuario_id_atual():
    return session["usuario_id"]


@app.route("/")
def index():
    uid = usuario_id_atual()
    conexao = conectar_banco()
    total_produtos = conexao.execute(
        "SELECT COUNT(*) FROM produtos WHERE usuario_id = ?", (uid,)
    ).fetchone()[0]
    estoque_baixo = conexao.execute(
        "SELECT COUNT(*) FROM produtos WHERE usuario_id = ? AND quantidade <= 10", (uid,)
    ).fetchone()[0]
    total_talhoes = conexao.execute(
        "SELECT COUNT(*) FROM talhoes WHERE usuario_id = ?", (uid,)
    ).fetchone()[0]
    total_aplicacoes = conexao.execute("""
        SELECT COUNT(*) FROM aplicacoes a
        JOIN produtos p ON p.id = a.produto_id
        WHERE p.usuario_id = ?
    """, (uid,)).fetchone()[0]
    hoje = datetime.now().date().isoformat()
    em_carencia = conexao.execute("""
        SELECT COUNT(*) FROM aplicacoes a
        JOIN produtos p ON p.id = a.produto_id
        WHERE p.usuario_id = ? AND a.data_liberacao > ?
    """, (uid, hoje)).fetchone()[0]
    conexao.close()
    return render_template("index.html", total_produtos=total_produtos,
        estoque_baixo=estoque_baixo, total_talhoes=total_talhoes,
        total_aplicacoes=total_aplicacoes, em_carencia=em_carencia)


@app.route("/estoque")
def estoque():
    conexao = conectar_banco()
    produtos = conexao.execute(
        "SELECT * FROM produtos WHERE usuario_id = ? ORDER BY nome", (usuario_id_atual(),)
    ).fetchall()
    conexao.close()
    return render_template("estoque.html", produtos=produtos)


@app.route("/produto/cadastrar", methods=["GET", "POST"])
def cadastrar_produto():
    if request.method == "POST":
        nome = request.form["nome"]
        principio_ativo = request.form["principio_ativo"]
        fabricante = request.form.get("fabricante", "")
        quantidade = float(request.form["quantidade"])
        unidade = request.form["unidade"]
        periodo_carencia = int(request.form["periodo_carencia"])
        conexao = conectar_banco()
        conexao.execute("""
            INSERT INTO produtos
            (nome, principio_ativo, fabricante, quantidade, unidade, periodo_carencia, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nome, principio_ativo, fabricante, quantidade, unidade, periodo_carencia, usuario_id_atual()))
        conexao.commit()
        conexao.close()
        flash("Produto cadastrado com sucesso!", "sucesso")
        return redirect(url_for("estoque"))
    return render_template("cadastro_produto.html")


@app.route("/movimentacoes", methods=["GET", "POST"])
def movimentacoes():
    uid = usuario_id_atual()
    conexao = conectar_banco()
    if request.method == "POST":
        try:
            produto_id = int(request.form["produto_id"])
            tipo = request.form["tipo"]
            quantidade = float(request.form["quantidade"])
            observacao = request.form.get("observacao", "")
        except (ValueError, KeyError):
            conexao.close()
            flash("Dados da movimentação inválidos.", "erro")
            return redirect(url_for("movimentacoes"))

        produto = conexao.execute(
            "SELECT * FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid)
        ).fetchone()
        if not produto:
            conexao.close()
            flash("Produto não encontrado.", "erro")
            return redirect(url_for("movimentacoes"))
        if quantidade <= 0 or tipo not in ("ENTRADA", "SAIDA"):
            conexao.close()
            flash("Informe um tipo e uma quantidade válidos.", "erro")
            return redirect(url_for("movimentacoes"))
        if tipo == "SAIDA" and quantidade > produto["quantidade"]:
            conexao.close()
            flash("Quantidade de saída maior que o estoque disponível.", "erro")
            return redirect(url_for("movimentacoes"))
        nova_quantidade = produto["quantidade"] + quantidade if tipo == "ENTRADA" else produto["quantidade"] - quantidade
        conexao.execute("UPDATE produtos SET quantidade = ? WHERE id = ? AND usuario_id = ?",
                        (nova_quantidade, produto_id, uid))
        conexao.execute("""
            INSERT INTO movimentacoes (produto_id, tipo, quantidade, data, observacao)
            VALUES (?, ?, ?, ?, ?)
        """, (produto_id, tipo, quantidade, datetime.now().strftime("%Y-%m-%d %H:%M"), observacao))
        conexao.commit()
        conexao.close()
        flash("Movimentação registrada com sucesso!", "sucesso")
        return redirect(url_for("movimentacoes"))

    produtos = conexao.execute(
        "SELECT * FROM produtos WHERE usuario_id = ? ORDER BY nome", (uid,)
    ).fetchall()
    movimentacoes_lista = conexao.execute("""
        SELECT m.*, p.nome AS produto_nome, p.unidade
        FROM movimentacoes m JOIN produtos p ON p.id = m.produto_id
        WHERE p.usuario_id = ? ORDER BY m.id DESC
    """, (uid,)).fetchall()
    conexao.close()
    return render_template("movimentacao.html", produtos=produtos, movimentacoes=movimentacoes_lista)


@app.route("/talhoes")
def talhoes():
    conexao = conectar_banco()
    lista = conexao.execute(
        "SELECT * FROM talhoes WHERE usuario_id = ? ORDER BY nome", (usuario_id_atual(),)
    ).fetchall()
    conexao.close()
    return render_template("talhoes.html", talhoes=lista)


@app.route("/talhao/cadastrar", methods=["GET", "POST"])
def cadastrar_talhao():
    if request.method == "POST":
        nome = request.form["nome"]
        area = float(request.form["area"])
        cultura = request.form["cultura"]
        conexao = conectar_banco()
        conexao.execute(
            "INSERT INTO talhoes (nome, area, cultura, usuario_id) VALUES (?, ?, ?, ?)",
            (nome, area, cultura, usuario_id_atual())
        )
        conexao.commit()
        conexao.close()
        flash("Talhão cadastrado com sucesso!", "sucesso")
        return redirect(url_for("talhoes"))
    return render_template("cadastro_talhao.html")


@app.route("/aplicacoes", methods=["GET", "POST"])
def aplicacoes():
    uid = usuario_id_atual()
    conexao = conectar_banco()
    if request.method == "POST":
        try:
            produto_id = int(request.form["produto_id"])
            talhao_id = int(request.form["talhao_id"])
            quantidade = float(request.form["quantidade"])
            data_aplicacao = request.form["data_aplicacao"]
            observacao = request.form.get("observacao", "")
            data = datetime.strptime(data_aplicacao, "%Y-%m-%d").date()
        except (ValueError, KeyError):
            conexao.close()
            flash("Confira os dados da aplicação.", "erro")
            return redirect(url_for("aplicacoes"))

        produto = conexao.execute(
            "SELECT * FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid)
        ).fetchone()
        talhao = conexao.execute(
            "SELECT * FROM talhoes WHERE id = ? AND usuario_id = ?", (talhao_id, uid)
        ).fetchone()
        if not produto or not talhao:
            conexao.close()
            flash("Produto ou talhão não encontrado na sua conta.", "erro")
            return redirect(url_for("aplicacoes"))
        if quantidade <= 0 or quantidade > produto["quantidade"]:
            conexao.close()
            flash("A quantidade deve ser positiva e não pode superar o estoque disponível.", "erro")
            return redirect(url_for("aplicacoes"))

        data_liberacao = data + timedelta(days=produto["periodo_carencia"])
        conexao.execute(
            "UPDATE produtos SET quantidade = ? WHERE id = ? AND usuario_id = ?",
            (produto["quantidade"] - quantidade, produto_id, uid)
        )
        conexao.execute("""
            INSERT INTO movimentacoes (produto_id, tipo, quantidade, data, observacao)
            VALUES (?, 'SAIDA', ?, ?, ?)
        """, (produto_id, quantidade, datetime.now().strftime("%Y-%m-%d %H:%M"),
              "Saída referente à aplicação"))
        conexao.execute("""
            INSERT INTO aplicacoes
            (produto_id, talhao_id, quantidade, data_aplicacao, data_liberacao, observacao)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (produto_id, talhao_id, quantidade, data_aplicacao, data_liberacao.isoformat(), observacao))
        conexao.commit()
        conexao.close()
        flash("Aplicação registrada com sucesso!", "sucesso")
        return redirect(url_for("aplicacoes"))

    produtos = conexao.execute(
        "SELECT * FROM produtos WHERE usuario_id = ? ORDER BY nome", (uid,)
    ).fetchall()
    talhoes_lista = conexao.execute(
        "SELECT * FROM talhoes WHERE usuario_id = ? ORDER BY nome", (uid,)
    ).fetchall()
    aplicacoes_lista = conexao.execute("""
        SELECT a.*, p.nome AS produto_nome, p.unidade, t.nome AS talhao_nome, t.cultura
        FROM aplicacoes a
        JOIN produtos p ON p.id = a.produto_id
        JOIN talhoes t ON t.id = a.talhao_id
        WHERE p.usuario_id = ? AND t.usuario_id = ?
        ORDER BY a.id DESC
    """, (uid, uid)).fetchall()
    conexao.close()
    return render_template("aplicacoes.html", produtos=produtos,
                           talhoes=talhoes_lista, aplicacoes=aplicacoes_lista)


@app.route("/historico")
def historico():
    uid = usuario_id_atual()
    conexao = conectar_banco()
    registros = conexao.execute("""
        SELECT a.*, p.nome AS produto_nome, p.principio_ativo, p.unidade,
               t.nome AS talhao_nome, t.cultura
        FROM aplicacoes a
        JOIN produtos p ON p.id = a.produto_id
        JOIN talhoes t ON t.id = a.talhao_id
        WHERE p.usuario_id = ? AND t.usuario_id = ?
        ORDER BY a.data_aplicacao DESC
    """, (uid, uid)).fetchall()
    conexao.close()
    hoje = datetime.now().date()
    return render_template("historico.html", registros=registros, hoje=hoje.isoformat())


@app.route("/listagem")
def listagem():
    uid = usuario_id_atual()
    conexao = conectar_banco()
    produtos = conexao.execute(
        "SELECT * FROM produtos WHERE usuario_id = ? ORDER BY nome", (uid,)
    ).fetchall()
    talhoes = conexao.execute(
        "SELECT * FROM talhoes WHERE usuario_id = ? ORDER BY nome", (uid,)
    ).fetchall()
    aplicacoes_lista = conexao.execute("""
        SELECT a.*, p.nome AS produto_nome, p.principio_ativo, p.unidade,
               t.nome AS talhao_nome, t.cultura
        FROM aplicacoes a
        JOIN produtos p ON p.id = a.produto_id
        JOIN talhoes t ON t.id = a.talhao_id
        WHERE p.usuario_id = ? AND t.usuario_id = ?
        ORDER BY a.data_aplicacao DESC
    """, (uid, uid)).fetchall()
    movimentacoes_lista = conexao.execute("""
        SELECT m.*, p.nome AS produto_nome, p.unidade
        FROM movimentacoes m JOIN produtos p ON p.id = m.produto_id
        WHERE p.usuario_id = ? ORDER BY m.id DESC
    """, (uid,)).fetchall()
    conexao.close()
    return render_template("listagem.html", produtos=produtos, talhoes=talhoes,
                           aplicacoes=aplicacoes_lista, movimentacoes=movimentacoes_lista)


@app.route("/produto/editar/<int:produto_id>", methods=["GET", "POST"])
def editar_produto(produto_id):
    uid = usuario_id_atual()
    conexao = conectar_banco()
    produto = conexao.execute(
        "SELECT * FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid)
    ).fetchone()
    if not produto:
        conexao.close()
        flash("Produto não encontrado.", "erro")
        return redirect(url_for("estoque"))
    if request.method == "POST":
        try:
            nome = request.form["nome"]
            principio_ativo = request.form["principio_ativo"]
            fabricante = request.form.get("fabricante", "")
            quantidade = float(request.form["quantidade"])
            unidade = request.form["unidade"]
            periodo_carencia = int(request.form["periodo_carencia"])
        except (ValueError, KeyError):
            conexao.close()
            flash("Confira os dados do produto.", "erro")
            return redirect(url_for("estoque"))
        conexao.execute("""
            UPDATE produtos SET nome = ?, principio_ativo = ?, fabricante = ?,
                quantidade = ?, unidade = ?, periodo_carencia = ?
            WHERE id = ? AND usuario_id = ?
        """, (nome, principio_ativo, fabricante, quantidade, unidade, periodo_carencia, produto_id, uid))
        conexao.commit()
        conexao.close()
        flash("Produto atualizado com sucesso!", "sucesso")
        return redirect(url_for("estoque"))
    conexao.close()
    return render_template("editar_produto.html", produto=produto)


@app.route("/produto/excluir/<int:produto_id>", methods=["POST"])
def excluir_produto(produto_id):
    uid = usuario_id_atual()
    conexao = conectar_banco()
    produto = conexao.execute(
        "SELECT id FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid)
    ).fetchone()
    if not produto:
        conexao.close()
        flash("Produto não encontrado.", "erro")
        return redirect(url_for("estoque"))
    # Evita deixar movimentações/aplicações órfãs no histórico.
    existe_aplicacao = conexao.execute(
        "SELECT 1 FROM aplicacoes WHERE produto_id = ? LIMIT 1", (produto_id,)
    ).fetchone()
    existe_movimentacao = conexao.execute(
        "SELECT 1 FROM movimentacoes WHERE produto_id = ? LIMIT 1", (produto_id,)
    ).fetchone()
    if existe_aplicacao or existe_movimentacao:
        conexao.close()
        flash("Não é possível excluir um produto com movimentações ou aplicações registradas.", "erro")
        return redirect(url_for("estoque"))
    conexao.execute("DELETE FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, uid))
    conexao.commit()
    conexao.close()
    flash("Produto excluído com sucesso!", "sucesso")
    return redirect(url_for("estoque"))


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
           if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        if len(senha) < 8:
            flash("A senha deve ter pelo menos 8 caracteres.", "error")
            return redirect(url_for("cadastro"))

        senha_hash = generate_password_hash(senha)
        conexao = conectar_banco()

        try:
            conexao.execute(
                "INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)",
                (nome, email, senha_hash)
            )
            conexao.commit()
            flash("Cadastro realizado com sucesso!", "sucesso")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Este e-mail já está cadastrado.", "erro")

        finally:
            conexao.close()

    return render_template("cadastro.html")
            flash("Cadastro realizado com sucesso!", "sucesso")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Este e-mail já está cadastrado.", "erro")

        finally:
            conexao.close()

    return render_template("cadastro.html")    except sqlite3.IntegrityError:
            flash("Este e-mail já está cadastrado.", "erro")
        finally:
            conexao.close()
    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        conexao = conectar_banco()
        usuario = conexao.execute(
            "SELECT * FROM usuarios WHERE email = ?", (email,)
        ).fetchone()
        conexao.close()
        if usuario and check_password_hash(usuario["senha"], senha):
            session.clear()
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = usuario["nome"]
            flash("Login realizado com sucesso!", "sucesso")
            return redirect(url_for("index"))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("login"))


# Executa também quando o PythonAnywhere importa o módulo via WSGI.
inicializar_banco()

if __name__ == "__main__":
    app.run(debug=True)
