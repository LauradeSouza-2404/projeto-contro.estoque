from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "cultiva-chave-secreta"

DATABASE = "banco.db"


# ============================================================
# BANCO DE DADOS
# ============================================================

def conectar_banco():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    return conexao


def inicializar_banco():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    # Tabela de produtos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            principio_ativo TEXT NOT NULL,
            fabricante TEXT,
            quantidade REAL NOT NULL DEFAULT 0,
            unidade TEXT NOT NULL,
            periodo_carencia INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Tabela de movimentações
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

    # Tabela de talhões
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS talhoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            area REAL NOT NULL,
            cultura TEXT NOT NULL
        )
    """)

    # Tabela de aplicações
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

    conexao.commit()
    conexao.close()


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def index():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("SELECT COUNT(*) FROM produtos")
    total_produtos = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM produtos
        WHERE quantidade <= 10
    """)
    estoque_baixo = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM talhoes")
    total_talhoes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM aplicacoes")
    total_aplicacoes = cursor.fetchone()[0]

    # Aplicações ainda dentro do período de carência
    hoje = datetime.now().date().isoformat()

    cursor.execute("""
        SELECT COUNT(*) FROM aplicacoes
        WHERE data_liberacao > ?
    """, (hoje,))

    em_carencia = cursor.fetchone()[0]

    conexao.close()

    return render_template(
        "index.html",
        total_produtos=total_produtos,
        estoque_baixo=estoque_baixo,
        total_talhoes=total_talhoes,
        total_aplicacoes=total_aplicacoes,
        em_carencia=em_carencia
    )


# ============================================================
# ESTOQUE
# ============================================================

@app.route("/estoque")
def estoque():
    conexao = conectar_banco()

    produtos = conexao.execute("""
        SELECT *
        FROM produtos
        ORDER BY nome
    """).fetchall()

    conexao.close()

    return render_template("estoque.html", produtos=produtos)


@app.route("/produto/cadastrar", methods=["GET", "POST"])
def cadastrar_produto():

    if request.method == "POST":

        nome = request.form["nome"]
        principio_ativo = request.form["principio_ativo"]
        fabricante = request.form["fabricante"]
        quantidade = float(request.form["quantidade"])
        unidade = request.form["unidade"]
        periodo_carencia = int(request.form["periodo_carencia"])

        conexao = conectar_banco()

        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO produtos
            (
                nome,
                principio_ativo,
                fabricante,
                quantidade,
                unidade,
                periodo_carencia
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            nome,
            principio_ativo,
            fabricante,
            quantidade,
            unidade,
            periodo_carencia
        ))

        conexao.commit()
        conexao.close()

        flash("Produto cadastrado com sucesso!", "sucesso")

        return redirect(url_for("estoque"))

    return render_template("cadastro_produto.html")


# ============================================================
# MOVIMENTAÇÕES
# ============================================================

@app.route("/movimentacoes", methods=["GET", "POST"])
def movimentacoes():

    conexao = conectar_banco()

    if request.method == "POST":

        produto_id = int(request.form["produto_id"])
        tipo = request.form["tipo"]
        quantidade = float(request.form["quantidade"])
        observacao = request.form["observacao"]

        produto = conexao.execute("""
            SELECT *
            FROM produtos
            WHERE id = ?
        """, (produto_id,)).fetchone()

        if not produto:
            flash("Produto não encontrado.", "erro")
            conexao.close()
            return redirect(url_for("movimentacoes"))

        estoque_atual = produto["quantidade"]

        if tipo == "SAIDA":

            if quantidade > estoque_atual:
                flash("Quantidade de saída maior que o estoque disponível.", "erro")
                conexao.close()
                return redirect(url_for("movimentacoes"))

            nova_quantidade = estoque_atual - quantidade

        else:
            nova_quantidade = estoque_atual + quantidade

        # Atualiza estoque
        conexao.execute("""
            UPDATE produtos
            SET quantidade = ?
            WHERE id = ?
        """, (nova_quantidade, produto_id))

        # Registra movimentação
        conexao.execute("""
            INSERT INTO movimentacoes
            (
                produto_id,
                tipo,
                quantidade,
                data,
                observacao
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            produto_id,
            tipo,
            quantidade,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            observacao
        ))

        conexao.commit()

        flash("Movimentação registrada com sucesso!", "sucesso")

        return redirect(url_for("movimentacoes"))

    produtos = conexao.execute("""
        SELECT *
        FROM produtos
        ORDER BY nome
    """).fetchall()

    movimentacoes_lista = conexao.execute("""
        SELECT
            movimentacoes.*,
            produtos.nome AS produto_nome,
            produtos.unidade
        FROM movimentacoes
        JOIN produtos
            ON produtos.id = movimentacoes.produto_id
        ORDER BY movimentacoes.id DESC
    """).fetchall()

    conexao.close()

    return render_template(
        "movimentacao.html",
        produtos=produtos,
        movimentacoes=movimentacoes_lista
    )


# ============================================================
# TALHÕES
# ============================================================

@app.route("/talhoes")
def talhoes():

    conexao = conectar_banco()

    talhoes_lista = conexao.execute("""
        SELECT *
        FROM talhoes
        ORDER BY nome
    """).fetchall()

    conexao.close()

    return render_template(
        "talhoes.html",
        talhoes=talhoes_lista
    )


@app.route("/talhao/cadastrar", methods=["GET", "POST"])
def cadastrar_talhao():

    if request.method == "POST":

        nome = request.form["nome"]
        area = float(request.form["area"])
        cultura = request.form["cultura"]

        conexao = conectar_banco()

        conexao.execute("""
            INSERT INTO talhoes
            (
                nome,
                area,
                cultura
            )
            VALUES (?, ?, ?)
        """, (
            nome,
            area,
            cultura
        ))

        conexao.commit()
        conexao.close()

        flash("Talhão cadastrado com sucesso!", "sucesso")

        return redirect(url_for("talhoes"))

    return render_template("cadastro_talhao.html")


# ============================================================
# APLICAÇÕES
# ============================================================

@app.route("/aplicacoes", methods=["GET", "POST"])
def aplicacoes():

    conexao = conectar_banco()

    if request.method == "POST":

        produto_id = int(request.form["produto_id"])
        talhao_id = int(request.form["talhao_id"])
        quantidade = float(request.form["quantidade"])
        data_aplicacao = request.form["data_aplicacao"]
        observacao = request.form["observacao"]

        produto = conexao.execute("""
            SELECT *
            FROM produtos
            WHERE id = ?
        """, (produto_id,)).fetchone()

        if not produto:
            flash("Produto não encontrado.", "erro")
            conexao.close()
            return redirect(url_for("aplicacoes"))

        # Verifica estoque
        if quantidade > produto["quantidade"]:
            flash("Quantidade informada maior que o estoque disponível.", "erro")
            conexao.close()
            return redirect(url_for("aplicacoes"))

        # Calcula período de carência
        data = datetime.strptime(data_aplicacao, "%Y-%m-%d").date()

        data_liberacao = data + timedelta(
            days=produto["periodo_carencia"]
        )

        # Atualiza estoque
        nova_quantidade = produto["quantidade"] - quantidade

        conexao.execute("""
            UPDATE produtos
            SET quantidade = ?
            WHERE id = ?
        """, (
            nova_quantidade,
            produto_id
        ))

        # Registra saída automaticamente
        conexao.execute("""
            INSERT INTO movimentacoes
            (
                produto_id,
                tipo,
                quantidade,
                data,
                observacao
            )
            VALUES (?, 'SAIDA', ?, ?, ?)
        """, (
            produto_id,
            quantidade,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Saída referente à aplicação"
        ))

        # Registra aplicação
        conexao.execute("""
            INSERT INTO aplicacoes
            (
                produto_id,
                talhao_id,
                quantidade,
                data_aplicacao,
                data_liberacao,
                observacao
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            produto_id,
            talhao_id,
            quantidade,
            data_aplicacao,
            data_liberacao.isoformat(),
            observacao
        ))

        conexao.commit()

        flash("Aplicação registrada com sucesso!", "sucesso")

        return redirect(url_for("aplicacoes"))

    produtos = conexao.execute("""
        SELECT *
        FROM produtos
        ORDER BY nome
    """).fetchall()

    talhoes_lista = conexao.execute("""
        SELECT *
        FROM talhoes
        ORDER BY nome
    """).fetchall()

    aplicacoes_lista = conexao.execute("""
        SELECT
            aplicacoes.*,
            produtos.nome AS produto_nome,
            produtos.unidade,
            talhoes.nome AS talhao_nome,
            talhoes.cultura
        FROM aplicacoes
        JOIN produtos
            ON produtos.id = aplicacoes.produto_id
        JOIN talhoes
            ON talhoes.id = aplicacoes.talhao_id
        ORDER BY aplicacoes.id DESC
    """).fetchall()

    conexao.close()

    return render_template(
        "aplicacoes.html",
        produtos=produtos,
        talhoes=talhoes_lista,
        aplicacoes=aplicacoes_lista
    )


# ============================================================
# HISTÓRICO / RASTREABILIDADE
# ============================================================

@app.route("/historico")
def historico():

    conexao = conectar_banco()

    registros = conexao.execute("""
        SELECT
            aplicacoes.*,
            produtos.nome AS produto_nome,
            produtos.principio_ativo,
            produtos.unidade,
            talhoes.nome AS talhao_nome,
            talhoes.cultura
        FROM aplicacoes
        JOIN produtos
            ON produtos.id = aplicacoes.produto_id
        JOIN talhoes
            ON talhoes.id = aplicacoes.talhao_id
        ORDER BY aplicacoes.data_aplicacao DESC
    """).fetchall()

    conexao.close()

    hoje = datetime.now().date()

    return render_template(
        "historico.html",
        registros=registros,
        hoje=hoje.isoformat()
    )


# ============================================================
# INICIALIZAÇÃO
# ============================================================

@app.route("/listagem")
def listagem():
    conexao = conectar_banco()

    produtos = conexao.execute("""
        SELECT *
        FROM produtos
        ORDER BY nome
    """).fetchall()

    talhoes = conexao.execute("""
        SELECT *
        FROM talhoes
        ORDER BY nome
    """).fetchall()

    aplicacoes = conexao.execute("""
        SELECT
            aplicacoes.*,
            produtos.nome AS produto_nome,
            produtos.principio_ativo,
            produtos.unidade,
            talhoes.nome AS talhao_nome,
            talhoes.cultura
        FROM aplicacoes
        JOIN produtos
            ON produtos.id = aplicacoes.produto_id
        JOIN talhoes
            ON talhoes.id = aplicacoes.talhao_id
        ORDER BY aplicacoes.data_aplicacao DESC
    """).fetchall()

    movimentacoes = conexao.execute("""
        SELECT
            movimentacoes.*,
            produtos.nome AS produto_nome,
            produtos.unidade
        FROM movimentacoes
        JOIN produtos
            ON produtos.id = movimentacoes.produto_id
        ORDER BY movimentacoes.id DESC
    """).fetchall()

    conexao.close()

    return render_template(
        "listagem.html",
        produtos=produtos,
        talhoes=talhoes,
        aplicacoes=aplicacoes,
        movimentacoes=movimentacoes
    )

if __name__ == "__main__":
    inicializar_banco()
    app.run(debug=True)