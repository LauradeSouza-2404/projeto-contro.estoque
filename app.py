from flask import Flask, render_template, request, redirect

app = Flask(__name__)


# Produtos do estoque
produtos = [
    {
        "nome": "Produto A",
        "categoria": "Defensivo",
        "quantidade": 20,
        "unidade": "L",
        "status": "Disponível"
    },
    {
        "nome": "Produto B",
        "categoria": "Defensivo",
        "quantidade": 15,
        "unidade": "L",
        "status": "Disponível"
    },
    {
        "nome": "Produto C",
        "categoria": "Defensivo",
        "quantidade": 10,
        "unidade": "L",
        "status": "Disponível"
    }
]


# Histórico das movimentações
movimentacoes = []


# Página inicial
@app.route("/")
def inicio():
    return render_template("index.html")


# Dados do campo
@app.route("/dados-campo")
def dados_campo():

    dados = [
        {
            "talhao": "Talhão 01",
            "cultura": "Soja",
            "defensivo": "Produto A",
            "quantidade": "20 L",
            "data": "25/08/2026",
            "status": "Aplicado"
        },
        {
            "talhao": "Talhão 02",
            "cultura": "Milho",
            "defensivo": "Produto B",
            "quantidade": "15 L",
            "data": "26/08/2026",
            "status": "Pendente"
        },
        {
            "talhao": "Talhão 03",
            "cultura": "Soja",
            "defensivo": "Produto C",
            "quantidade": "10 L",
            "data": "28/08/2026",
            "status": "Aplicado"
        }
    ]

    return render_template("dados_campo.html", dados=dados)


# Estoque
@app.route("/estoque")
def estoque():
    return render_template("estoque.html", produtos=produtos)


# Cadastrar produto
@app.route("/cadastrar-produto", methods=["GET", "POST"])
def cadastrar_produto():

    if request.method == "POST":

        nome = request.form["nome"]
        categoria = request.form["categoria"]
        quantidade = int(request.form["quantidade"])
        unidade = request.form["unidade"]

        novo_produto = {
            "nome": nome,
            "categoria": categoria,
            "quantidade": quantidade,
            "unidade": unidade,
            "status": "Disponível"
        }

        produtos.append(novo_produto)

        return redirect("/estoque")

    return render_template("cadastrar_produto.html")


# Entrada de estoque
@app.route("/entrada", methods=["GET", "POST"])
def entrada():

    if request.method == "POST":

        nome = request.form["nome"]
        quantidade = int(request.form["quantidade"])

        for produto in produtos:

            if produto["nome"] == nome:

                produto["quantidade"] += quantidade

                movimentacoes.append({
                    "produto": nome,
                    "tipo": "Entrada",
                    "quantidade": quantidade,
                    "unidade": produto["unidade"],
                    "data": "31/08/2026"
                })

                break

        return redirect("/estoque")

    return render_template("entrada.html", produtos=produtos)


# Saída de estoque
@app.route("/saida", methods=["GET", "POST"])
def saida():

    if request.method == "POST":

        nome = request.form["nome"]
        quantidade = int(request.form["quantidade"])

        for produto in produtos:

            if produto["nome"] == nome:

                if produto["quantidade"] >= quantidade:

                    produto["quantidade"] -= quantidade

                    movimentacoes.append({
                        "produto": nome,
                        "tipo": "Saída",
                        "quantidade": quantidade,
                        "unidade": produto["unidade"],
                        "data": "31/08/2026"
                    })

                break

        return redirect("/estoque")

    return render_template("saida.html", produtos=produtos)


# Histórico
@app.route("/historico")
def historico():

    return render_template(
        "historico.html",
        movimentacoes=movimentacoes
    )


# Rastreabilidade
@app.route("/rastreabilidade")
def rastreabilidade():

    registros = [
        {
            "talhao": "Talhão 01",
            "cultura": "Soja",
            "produto": "Produto A",
            "quantidade": "20 L",
            "data": "25/08/2026",
            "status": "Aplicado"
        },
        {
            "talhao": "Talhão 02",
            "cultura": "Milho",
            "produto": "Produto B",
            "quantidade": "15 L",
            "data": "26/08/2026",
            "status": "Pendente"
        },
        {
            "talhao": "Talhão 03",
            "cultura": "Soja",
            "produto": "Produto C",
            "quantidade": "10 L",
            "data": "28/08/2026",
            "status": "Aplicado"
        }
    ]

    return render_template(
        "rastreabilidade.html",
        registros=registros
    )
# =========================
# EDITAR PRODUTO - UPDATE
# =========================

@app.route("/editar-produto/<nome>", methods=["GET", "POST"])
def editar_produto(nome):

    produto_encontrado = None

    for produto in produtos:

        if produto["nome"] == nome:

            produto_encontrado = produto

            break

    if produto_encontrado is None:
        return "Produto não encontrado"

    if request.method == "POST":

        produto_encontrado["nome"] = request.form["nome"]

        produto_encontrado["categoria"] = request.form["categoria"]

        produto_encontrado["quantidade"] = int(
            request.form["quantidade"]
        )

        produto_encontrado["unidade"] = request.form["unidade"]

        return redirect("/estoque")

    return render_template(
        "editar_produto.html",
        produto=produto_encontrado
    )


# =========================
# EXCLUIR PRODUTO - DELETE
# =========================

@app.route("/excluir-produto/<nome>", methods=["POST"])
def excluir_produto(nome):

    for produto in produtos:

        if produto["nome"] == nome:

            produtos.remove(produto)

            break

    return redirect("/estoque")


# =========================
# EXECUTAR A APLICAÇÃO
# =========================

if __name__ == "__main__":
    app.run(debug=True)
 


# Executar aplicação
if __name__ == "__main__":
    app.run(debug=True)