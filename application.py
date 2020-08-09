from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    """Loads index page"""
    
    # opens a list of all stocks bought by the user
    rows = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id", user_id = session["user_id"])
    
    # updates current_price and total
    for row in rows:
        db.execute("UPDATE portfolio SET current_price = :current_price WHERE symbol = :symbol AND user_id = :user_id", current_price = lookup(row["symbol"]).get("price"), symbol = row["symbol"], user_id = session["user_id"])
        db.execute("UPDATE portfolio SET total = shares * current_price")
        
    # returns updated list and formats it for printing
    rows = db.execute("SELECT symbol, name, SUM(shares), current_price, SUM(total) FROM portfolio WHERE user_id = :user_id GROUP BY symbol ORDER BY symbol, shares DESC", user_id = session["user_id"])
    for row in rows:
        if row["SUM(shares)"] == 0:
            rows.remove(row)
    
    # returns cash of a user
    cash = int(db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"])
    
    # returns the total of all totals
    total = db.execute("SELECT SUM(total) FROM portfolio WHERE user_id = :user_id", user_id = session["user_id"])[0]["SUM(total)"]
    
    # adds cash to total
    if total is None:
        total = cash
    else:
        total += cash
    
    # renders page and prints each row
    return render_template("index.html", rows = rows, cash = cash, total = total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
    
        # retrieves a dict of the inputted symbol
        quote = lookup(request.form.get("symbol").strip())
        
        # ensures valid symbol
        if quote is None:
            return apology("invalid symbol")
    
        # ensures valid amount of shares
        if not isPositiveInt(request.form.get("shares")):
            return apology("invalid amount of shares")
            
        # retrieves amount of cash
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"]
        
        # ensures user has sufficient cash
        if cash < quote.get("price") * int(request.form.get("shares")):
            return apology("not enough cash")
        
        # stores details of purchase
        db.execute("INSERT INTO portfolio (user_id, symbol, shares, name, total, price, current_price) VALUES (:user_id, :symbol, :shares, :name, :total, :price, :current_price)", user_id = session["user_id"], symbol = quote.get("symbol"), shares = int(request.form.get("shares")), name = quote.get("name"), total = quote.get("price") * int(request.form.get("shares")), price = quote.get("price"), current_price = quote.get("price"))
        
        # updates cash value in database    
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash - quote.get("price") * int(request.form.get("shares")), id = session["user_id"])
        
        # redirect user to home page
        return redirect(url_for("index"))    
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    
    # retrieve all stocks
    rows = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id ORDER BY time DESC", user_id = session["user_id"])
    
    # renders page and prints each row
    return render_template("history.html", rows = rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username").lower())

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # retrieves a dict of the inputted symbol
        quote = lookup(request.form.get("symbol").strip())
        
        # ensures valid symbol
        if quote is None:
            return apology("must provide a valid symbol")
        
        # display the quote
        return render_template("quoted.html", name = quote.get("name"), symbol = quote.get("symbol"), price = usd(quote.get("price")))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # forget any user_id
    session.clear()
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
            
        # ensure confirm passsword    
        elif not request.form.get("confirmPassword"):
            return apology("must confirm password")
        
        # ensure passwords match
        elif request.form.get("password") != request.form.get("confirmPassword"):
            return apology("passwords must match")
            
        # ensure password is strong
        elif len(request.form.get("password")) < 8:
            return apology("password must be at least 8 characters long")
    
        # hash password for security
        hash = pwd_context.hash(request.form.get("password"))
        
        # insert username into database and apologize if username is already taken
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username = request.form.get("username").lower(), hash = hash)
        if not result:
            return apology("this username is already taken")
            
        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username").lower())
        
        # automatically log the user in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # retrieves a dict of the inputted symbol
        quote = lookup(request.form.get("symbol").strip())
        
        # ensures valid symbol
        if quote is None:
            return apology("invalid symbol")
    
        # ensures valid amount of shares
        if not isPositiveInt(request.form.get("shares")):
            return apology("invalid amount of shares")
        
        # retrieves amount of cash
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"]
        
        # ensures user has inputted stock
        rows = db.execute("SELECT SUM(shares) FROM portfolio WHERE symbol = :symbol AND user_id = :user_id", symbol = quote.get("symbol"), user_id = session["user_id"])
        if rows is None:
            return apology("you don't own this stock")
            
        # ensures user has sufficient amount of shares
        if  rows[0]["SUM(shares)"] < int(request.form.get("shares")):
            return apology("you don't own that many shares")
        
        # stores details of sale
        db.execute("INSERT INTO portfolio (user_id, symbol, shares, name, total, price, current_price) VALUES (:user_id, :symbol, :shares, :name, :total, :price, :current_price)", user_id = session["user_id"], symbol = quote.get("symbol"), shares = -int(request.form.get("shares")), name = quote.get("name"), total = quote.get("price") * -int(request.form.get("shares")), price = quote.get("price"), current_price = quote.get("price"))
        
        # updates cash value in database    
        db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash + quote.get("price") * int(request.form.get("shares")), id = session["user_id"])

        # redirect user to home page
        return redirect(url_for("index"))
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")

@app.route("/changepassword", methods=["GET", "POST"])
@login_required
def changepassword():
    """Changes user's password."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])

        # ensure password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid password")
            
        # ensure new password was submitted
        elif not request.form.get("newPassword"):
            return apology("must provide new password")
        
        # ensure password confirmation was submitted
        elif not request.form.get("confirmPassword"):
            return apology("must confirm new password")
            
        # ensure password is strong
        elif len(request.form.get("newPassword")) < 8:
            return apology("new password must be at least 8 characters long")
            
        # ensure password and confirmation match
        elif request.form.get("newPassword") != request.form.get("confirmPassword"):
            return apology("passwords must match")
            
        # create hash
        hash = pwd_context.hash(request.form.get("newPassword"))
        
        # username must be a unique field
        db.execute("UPDATE users SET hash = :hash WHERE id = :id", hash = hash, id = session["user_id"])

        # redirect user to home page
        return redirect(url_for("index"))
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("changepassword.html")