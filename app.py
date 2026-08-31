from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)

DATABASE = "cultiva.db"


def conectar_banco():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_banco():
    conexao = conectar_banco()

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS aplicacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto TEXT NOT NULL,
            talhao TEXT NOT NULL,
            data_aplicacao TEXT NOT NULL,
            quantidade REAL NOT NULL,
            unidade TEXT NOT NULL,
            periodo_carencia INTEGER NOT NULL DEFAULT 0,
            data_liberacao TEXT,
            observacao TEXT
        )
    """)

    # Verifica quais colunas já existem
    colunas = conexao.execute(
        "PRAGMA table_info(aplicacoes)"
    ).fetchall()

    nomes_colunas = [coluna["name"] for coluna in colunas]

    if "periodo_carencia" not in nomes_colunas:
        conexao.execute("""
            ALTER TABLE aplicacoes
            ADD COLUMN periodo_carencia INTEGER NOT NULL DEFAULT 0
        """)

    if "data_liberacao" not in nomes_colunas:
        conexao.execute("""
            ALTER TABLE aplicacoes
            ADD COLUMN data_liberacao TEXT
        """)

    conexao.commit()
    conexao.close()

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/aplicacoes")
def aplicacoes():
    conexao = conectar_banco()

    aplicacoes = conexao.execute("""
        SELECT *
        FROM aplicacoes
        ORDER BY data_aplicacao DESC
    """).fetchall()

    conexao.close()

    return render_template(
        "aplicacoes.html",
        aplicacoes=aplicacoes
    )


@app.route("/aplicacoes/nova", methods=["GET", "POST"])
def nova_aplicacao():

    if request.method == "POST":

        produto = request.form["produto"]
        talhao = request.form["talhao"]
        data_aplicacao = request.form["data_aplicacao"]
        quantidade = request.form["quantidade"]
        unidade = request.form["unidade"]
        periodo_carencia = request.form["periodo_carencia"]
        observacao = request.form["observacao"]

        # Calcula a data de liberação para colheita
        data = datetime.strptime(data_aplicacao, "%Y-%m-%d")
        dias_carencia = int(periodo_carencia)

        data_liberacao = data + timedelta(days=dias_carencia)

        conexao = conectar_banco()

        conexao.execute("""
            INSERT INTO aplicacoes
            (
                produto,
                talhao,
                data_aplicacao,
                quantidade,
                unidade,
                periodo_carencia,
                data_liberacao,
                observacao
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            produto,
            talhao,
            data_aplicacao,
            quantidade,
            unidade,
            dias_carencia,
            data_liberacao.strftime("%Y-%m-%d"),
            observacao
        ))

        conexao.commit()
        conexao.close()

        return redirect(url_for("aplicacoes"))

    return render_template("nova_aplicacao.html")
@app.route("/aplicacoes/editar/<int:id>", methods=["GET", "POST"])
def editar_aplicacao(id):

    conexao = conectar_banco()

    aplicacao = conexao.execute(
        "SELECT * FROM aplicacoes WHERE id = ?",
        (id,)
    ).fetchone()

    if aplicacao is None:
        conexao.close()
        return "Aplicação não encontrada", 404

    if request.method == "POST":

        produto = request.form["produto"]
        talhao = request.form["talhao"]
        data_aplicacao = request.form["data_aplicacao"]
        quantidade = request.form["quantidade"]
        unidade = request.form["unidade"]
        periodo_carencia = int(request.form["periodo_carencia"])
        observacao = request.form["observacao"]

        # Recalcula a data de liberação
        data = datetime.strptime(data_aplicacao, "%Y-%m-%d")
        data_liberacao = data + timedelta(days=periodo_carencia)

        conexao.execute("""
            UPDATE aplicacoes
            SET
                produto = ?,
                talhao = ?,
                data_aplicacao = ?,
                quantidade = ?,
                unidade = ?,
                periodo_carencia = ?,
                data_liberacao = ?,
                observacao = ?
            WHERE id = ?
        """, (
            produto,
            talhao,
            data_aplicacao,
            quantidade,
            unidade,
            periodo_carencia,
            data_liberacao.strftime("%Y-%m-%d"),
            observacao,
            id
        ))

        conexao.commit()
        conexao.close()

        return redirect(url_for("aplicacoes"))

    conexao.close()

    return render_template(
        "editar_aplicacao.html",
        aplicacao=aplicacao
    )
@app.route("/aplicacoes/excluir/<int:id>", methods=["POST"])
def excluir_aplicacao(id):

    conexao = conectar_banco()

    conexao.execute(
        "DELETE FROM aplicacoes WHERE id = ?",
        (id,)
    )

    conexao.commit()
    conexao.close()

    return redirect(url_for("aplicacoes"))

if __name__ == "__main__":
    criar_banco()
    app.run(debug=True)