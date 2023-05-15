import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# didn't get how werkzeug.security works

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get user's info
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    stocks = db.execute(
        "SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", session["user_id"])
    total = cash + sum([stock["shares"] * lookup(stock["symbol"])["price"] for stock in stocks])
    # Get stock's info
    for stock in stocks:
        stock["name"] = lookup(stock["symbol"])["name"]
        stock["price"] = lookup(stock["symbol"])["price"]
        stock["total"] = stock["shares"] * stock["price"]
    # Render index
    return render_template("index.html", stocks=stocks, cash=cash, total=total)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        cash = request.form.get("cash")
        if not cash:
            return apology("must provide a number", 400)
        elif not cash.isdigit():
            return apology("must provide a positive integer", 400)
        elif int(cash) < 1:
            return apology("must provide a positive number", 400)
        else:
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", cash, session["user_id"])
            return redirect("/")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        # Checks for problems
        if not symbol:
            return apology("must provide a symbol", 400)
        elif not shares:
            return apology("must provide a number of shares", 400)
        elif not shares.isdigit():
            return apology("must provide a positive integer", 400)
        elif not lookup(symbol):
            return apology("invalid symbol", 400)
        elif int(shares) < 1:
            return apology("must provide a positive number of shares", 400)
        # Checks if user has money
        elif lookup(symbol)["price"] * float(shares) > db.execute("SELECT cash FROM users WHERE id = ?",
                                                                  session["user_id"])[0]["cash"]:
            return apology("sorry, can't afford", 400)
        # No problem, buy stocks and update database
        else:
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, datetime('now'))",
                       session["user_id"], symbol, shares, lookup(symbol)["price"])
            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", lookup(symbol)["price"] * float(shares), session["user_id"])
            return redirect("/")
    else:

        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT symbol, shares, price, date FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide a symbol", 400)
        else:
            quote = lookup(symbol)
            if not quote:
                return apology("invalid symbol", 400)
            else:
                return render_template("quoted.html", name=quote["name"], symbol=quote["symbol"], price=quote["price"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        user = db.execute("SELECT * FROM users WHERE username = ?", username)
        if not username:
            return apology("must provide a username", 400)
        elif not password:
            return apology("must provide a password", 400)
        elif not confirmation:
            return apology("must confirm password", 400)
        elif password != confirmation:
            return apology("passwords don't match", 400)
        elif user:
            return apology("username already exist", 400)
        else:
            hash = generate_password_hash(request.form.get("password"))
            result = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)
            if not result:
                return apology("username already exist", 400)
            else:
                session["user_id"] = result
                return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("must provide a symbol", 400)
        elif not shares:
            return apology("must provide a number of shares", 400)
        elif not shares.isdigit():
            return apology("must provide a positive integer", 400)
        elif int(shares) < 1:
            return apology("must provide a positive number of shares", 400)
        elif not lookup(symbol):
            return apology("invalid symbol", 400)
        elif db.execute("SELECT SUM(shares) FROM transactions WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)[0]["SUM(shares)"] < int(shares):
            return apology("sorry, can't sell", 400)
        else:
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, datetime('now'))",
                       session["user_id"], symbol, -int(shares), lookup(symbol)["price"])
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", lookup(symbol)["price"] * float(shares), session["user_id"])
            return redirect("/")
    else:
        stocks = db.execute("SELECT symbol FROM transactions WHERE user_id = ?", session["user_id"])
        return render_template("sell.html", stocks=stocks)