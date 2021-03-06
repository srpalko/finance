import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stock_data = db.execute("SELECT stock_symbol, SUM(num_shares) FROM transactions WHERE user_id = :id GROUP BY stock_symbol" , id = session["user_id"])
    for entry in stock_data:
        current_data = lookup(entry["stock_symbol"])
        entry["name"] = current_data["name"]
        entry["price"] = float(current_data["price"])
        entry["shares"] = entry["SUM(num_shares)"]
        entry["total"] = usd(entry["price"] * entry["shares"])
        entry["usd_price"] = usd(entry["price"])
        entry["stock_symbol"] = entry["stock_symbol"].upper()
    cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
    cash = cash[0]["cash"]
    portfolio_total = 0
    for entry in stock_data:
        stock_total = entry["price"] * entry["shares"]
        portfolio_total += stock_total
    net = cash + portfolio_total
    return render_template("index.html", stock_data = stock_data, cash = usd(cash), net = usd(net))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            #return apology("Please enter a stock symbol", 403)
            flash("Please enter a stock symbol.")
            return redirect("/buy")
        quote = lookup(request.form.get("symbol"))
        if quote == None:
            #return apology("That stock does not exist", 403)
            flash("That is not a valid stock symbol.")
            return redirect("/buy")
        if not request.form.get("shares") or int(request.form.get("shares")) < 1:
            #return apology("Please enter the number of shares", 403)
            flash("Please enter the number of shares that you would like to purchase.")
            return redirect("/buy")
        else:
            quote = lookup(request.form.get("symbol"))
            session["cash"] = db.execute("SELECT cash FROM users WHERE id = :id", id = session.get("user_id"))
            cash = session.get("cash")
            cash = cash[0]["cash"]
            shares = int(request.form.get("shares"))
            price = float(quote["price"]) * shares
            if cash >= price:
                new_balance = cash - price
                db.execute("UPDATE users SET cash = :new_balance WHERE id = :id", new_balance = new_balance, id = session.get(
                "user_id"))
                db.execute("INSERT INTO transactions (user_id, total_price, price, num_shares, stock_symbol)VALUES (:id, :total_price, :price, :num_shares, :stock_symbol)", id = session.get("user_id"), total_price = price, price = float(quote["price"]), num_shares = shares, stock_symbol = request.form.get("symbol"))
                flash("Purchase completed.")
                return redirect("/")
            else:
                #return apology("Price exceeds account balance", 403)
                flash("Insufficient funds.")
                return redirect("/buy")
    else:
        session["cash"] = db.execute("SELECT cash FROM users WHERE id = :id", id = session.get("user_id"))
        cash = session.get("cash")
        cash = usd(cash[0]["cash"])
        return render_template("buy.html", cash = cash)



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = :id", id = session.get("user_id"))
    for entry in transactions:
        iex_data = lookup(entry["stock_symbol"])
        entry["name"] = iex_data["name"]
        entry["stock_symbol"] = entry["stock_symbol"].upper()
        entry["total_price"] = usd(entry["total_price"])

    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            #return apology("must provide username", 403)
            flash("Please enter a username")
            return redirect("/login")
        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Please enter your password.")
            return redirect("/login")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Invalid username and/or password.")
            return redirect("/login")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        username = session["username"]

        # Redirect user to home page
        flash(f"Welcome back, {username}.")
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
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            flash("Please enter a stock symbol")
            return redirect("/quote")
        else:
            quote = lookup(request.form.get("symbol"))
            if quote == None:
                flash("Invalid stock symbol")
                return redirect("/quote")
            else:
                return render_template("quoted.html", quote = quote)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Check to make sure username is not blank.
        if not request.form.get("username"):
            #return apology("please enter a username", 403)
            flash("Please enter a username")
            return redirect("/register")
        # Check to make sure that username is not taken.
        elif len(db.execute("SELECT * FROM users WHERE username = :username;", username = request.form.get("username"))) != 0:
            #return apology("username unavailable", 403)
            flash("That username is already taken")
            return redirect("/register")
        # Check to make sure that password is not blank.
        if not request.form.get("password"):
            #return apology("please enter a password", 403)
            flash("Please enter a password")
            return redirect("/register")
        # Check to make sure that confirmation of password is not blank.
        if not request.form.get("confirmation"):
            #return apology("please confirm your password", 403)
            flash("Please confirm your password.")
            return redirect("/register")
        # Check to make sure that password fields match
        if request.form.get("password") != request.form.get("confirmation"):
            #return apology("passwords do not match", 403)
            flash("Passwords do not match.")
            return redirect("/register")
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash);", username = request.form.get("username"), hash = generate_password_hash(request.form.get("password")) )
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stock_data = db.execute("SELECT stock_symbol, SUM(num_shares) FROM transactions WHERE user_id = :id GROUP BY stock_symbol" , id = session["user_id"])
    for entry in stock_data:
        entry["shares"] = entry["SUM(num_shares)"]
        entry["stock_symbol"] = entry["stock_symbol"].upper()

    if request.method == "POST":
        stock_to_sell = request.form.get("sell")
        shares_to_sell = request.form.get("shares")
        this_stock_data = db.execute("SELECT SUM(num_shares) FROM transactions WHERE user_id = :id AND stock_symbol = :symbol", id = session["user_id"], symbol = stock_to_sell.lower())
        shares_you_have = this_stock_data[0]["SUM(num_shares)"]
        if not stock_to_sell:
            #return apology("Please select a stock to sell", 403)
            flash("Please select a stock.")
            return redirect("/sell")
        elif not shares_to_sell or int(shares_to_sell) < 1:
            #return apology("Please select the number of shares to sell")
            flash("Please enter the number of shares to sell.")
            return redirect("/sell")
        elif int(shares_to_sell) > int(shares_you_have):
            #return apology("You don't own that many shares!", 403)
            flash("You do not own that many shares!")
            return redirect("/sell")
        else:
            sold_stock = lookup(stock_to_sell)
            id = session["user_id"]
            price = 0 - float(sold_stock["price"])
            shares = 0 - int(shares_to_sell)
            total_price = shares * (0 - price)
            symbol = stock_to_sell.lower()
            cash = db.execute("SELECT cash FROM users WHERE id = :id", id = id)
            new_cash = float(cash[0]["cash"]) - total_price
            db.execute("INSERT INTO transactions (user_id, total_price, price, num_shares, stock_symbol) VALUES (:id, :total_price, :price, :shares, :symbol)", id = id, total_price = total_price, price = price, shares = shares, symbol = symbol)
            db.execute("UPDATE users SET cash = :new_cash WHERE id = :id", new_cash = new_cash, id = id)
            flash("Sale completed.")
            return redirect("/")
    else:
        return render_template("sell.html", stock_data = stock_data)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Account settings"""
    user_info = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
    return render_template("account.html", username = user_info[0]["username"])

@app.route("/password_change", methods=["POST"])
@login_required
def password_change():
    """Change password"""
    current_password_hash = db.execute("SELECT hash FROM users WHERE id = :id", id = session["user_id"])
    if not request.form.get("old_password"):
        flash("Please enter your old password.")
        return redirect("/account")
    if not request.form.get("new_password"):
        flash("Please enter a new password")
        return redirect("/account")
    if not request.form.get("check_new_password"):
        flash("Please confirm your password.")
        return redirect("/account")
    if not check_password_hash(current_password_hash[0]["hash"], request.form.get("old_password")):
        flash("Current password incorrect")
        return redirect("/account")
    if request.form.get("new_password") != request.form.get("check_new_password"):
        flash("New passwords do not match.")
        return redirect("/account")
    db.execute("UPDATE users SET hash = :new_hash WHERE id = :id", id = session["user_id"], new_hash = generate_password_hash(request.form.get("new_password")))
    flash("Password updated")
    return redirect("/account")

@app.route("/add_funds", methods=["POST"])
@login_required
def add_funds():
    current_funds = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
    added_funds = request.form.get("new_funds")
    new_funds = float(current_funds[0]["cash"]) + float(added_funds)
    db.execute("UPDATE users SET cash = :new_cash WHERE id = :id", id = session["user_id"], new_cash = new_funds)
    flash("{added} added to account. Your new balance is {new}. Long live the Illuminati.".format(added = usd(float(added_funds)), new = usd(float(new_funds))))
    return redirect("/account")

@app.route("/index_transaction", methods=["POST"])
@login_required







def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
