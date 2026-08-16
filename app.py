from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
import sqlite3, csv, io, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "plex-change-this-secret-key"
DB = os.path.join(os.path.dirname(__file__), "plex_assets.db")

FIELDS = [
    "asset_name","description","tag_number","location","serial_number",
    "model","user_name","custodian","status","condition","remarks"
]

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_name TEXT NOT NULL,
        description TEXT,
        tag_number TEXT,
        location TEXT,
        serial_number TEXT,
        model TEXT,
        user_name TEXT,
        custodian TEXT,
        status TEXT DEFAULT 'Verified',
        condition TEXT DEFAULT 'Good',
        remarks TEXT,
        source TEXT DEFAULT 'Field',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS far (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_name TEXT,
        description TEXT,
        tag_number TEXT,
        location TEXT,
        serial_number TEXT,
        model TEXT,
        user_name TEXT,
        custodian TEXT,
        source_row INTEGER,
        created_at TEXT NOT NULL
    )
    """)
    con.commit(); con.close()

init_db()

@app.route("/")
def dashboard():
    con = db()
    total = con.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"]
    verified = con.execute("SELECT COUNT(*) c FROM assets WHERE status='Verified'").fetchone()["c"]
    missing = con.execute("SELECT COUNT(*) c FROM assets WHERE status='Not Found'").fetchone()["c"]
    untagged = con.execute("SELECT COUNT(*) c FROM assets WHERE status='Untagged'").fetchone()["c"]
    far_count = con.execute("SELECT COUNT(*) c FROM far").fetchone()["c"]
    con.close()
    return render_template("dashboard.html", total=total, verified=verified, missing=missing,
                           untagged=untagged, far_count=far_count)

@app.route("/assets")
def assets():
    q = request.args.get("q","").strip()
    con = db()
    if q:
        rows = con.execute("""SELECT * FROM assets WHERE
            asset_name LIKE ? OR description LIKE ? OR tag_number LIKE ? OR
            serial_number LIKE ? OR location LIKE ? OR custodian LIKE ?
            ORDER BY id DESC""", tuple([f"%{q}%"]*6)).fetchall()
    else:
        rows = con.execute("SELECT * FROM assets ORDER BY id DESC").fetchall()
    con.close()
    return render_template("assets.html", assets=rows, q=q)

@app.route("/assets/new", methods=["GET","POST"])
def new_asset():
    if request.method == "POST":
        data = {f: request.form.get(f,"").strip() for f in FIELDS}
        if not data["asset_name"]:
            flash("Asset name is required.", "error")
            return render_template("asset_form.html", asset=data, title="New Asset")
        now = datetime.now().isoformat(timespec="seconds")
        con = db()
        con.execute("""INSERT INTO assets
        (asset_name,description,tag_number,location,serial_number,model,user_name,custodian,status,condition,remarks,source,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (*[data[f] for f in FIELDS], "Field", now, now))
        con.commit(); con.close()
        flash("Asset captured successfully.", "success")
        return redirect(url_for("assets"))
    return render_template("asset_form.html", asset={}, title="New Asset")

@app.route("/assets/<int:asset_id>/edit", methods=["GET","POST"])
def edit_asset(asset_id):
    con = db()
    row = con.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
    if not row:
        con.close(); return "Asset not found", 404
    if request.method == "POST":
        data = {f: request.form.get(f,"").strip() for f in FIELDS}
        now = datetime.now().isoformat(timespec="seconds")
        con.execute("""UPDATE assets SET asset_name=?,description=?,tag_number=?,location=?,
            serial_number=?,model=?,user_name=?,custodian=?,status=?,condition=?,remarks=?,updated_at=? WHERE id=?""",
            (*[data[f] for f in FIELDS], now, asset_id))
        con.commit(); con.close()
        flash("Asset updated.", "success")
        return redirect(url_for("assets"))
    con.close()
    return render_template("asset_form.html", asset=row, title="Edit Asset")

@app.route("/assets/<int:asset_id>/delete", methods=["POST"])
def delete_asset(asset_id):
    con=db(); con.execute("DELETE FROM assets WHERE id=?", (asset_id,)); con.commit(); con.close()
    flash("Asset deleted.", "success")
    return redirect(url_for("assets"))

@app.route("/import-far", methods=["GET","POST"])
def import_far():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename.lower().endswith(".csv"):
            flash("Please upload a CSV FAR file.", "error")
            return redirect(url_for("import_far"))
        text = f.read().decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        con = db()
        con.execute("DELETE FROM far")
        now = datetime.now().isoformat(timespec="seconds")
        for i,row in enumerate(reader, start=2):
            def pick(*names):
                for n in names:
                    for k in row.keys():
                        if k and k.strip().lower() == n:
                            return (row.get(k) or "").strip()
                return ""
            vals = [
                pick("asset name","asset_name","asset"),
                pick("description","asset description"),
                pick("tag number","tag_number","asset tag","tag"),
                pick("location"),
                pick("serial number","serial_number","serial"),
                pick("model","model number"),
                pick("user","user name","user_name"),
                pick("custodian"),
            ]
            con.execute("""INSERT INTO far
            (asset_name,description,tag_number,location,serial_number,model,user_name,custodian,source_row,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (*vals,i,now))
        con.commit(); con.close()
        flash("FAR imported. Reconciliation is now available.", "success")
        return redirect(url_for("reconcile"))
    return render_template("import_far.html")

@app.route("/reconcile")
def reconcile():
    con=db()
    far_rows=con.execute("SELECT * FROM far ORDER BY id").fetchall()
    assets_rows=con.execute("SELECT * FROM assets ORDER BY id").fetchall()
    con.close()
    # Simple audit-grade matching hierarchy: tag -> serial -> normalized description+location.
    def norm(v): return "".join((v or "").lower().split())
    by_tag={norm(r["tag_number"]):r for r in assets_rows if norm(r["tag_number"])}
    by_serial={norm(r["serial_number"]):r for r in assets_rows if norm(r["serial_number"])}
    results=[]
    used=set()
    for f in far_rows:
        match=None; basis=""
        if norm(f["tag_number"]) and norm(f["tag_number"]) in by_tag:
            match=by_tag[norm(f["tag_number"])]; basis="Tag Number"
        elif norm(f["serial_number"]) and norm(f["serial_number"]) in by_serial:
            match=by_serial[norm(f["serial_number"])]; basis="Serial Number"
        else:
            key=(norm(f["asset_name"]),norm(f["location"]))
            candidates=[r for r in assets_rows if (norm(r["asset_name"]),norm(r["location"]))==key]
            if len(candidates)==1:
                match=candidates[0]; basis="Asset + Location"
        if match:
            used.add(match["id"])
            diffs=[]
            for fld in ["asset_name","description","tag_number","location","serial_number","model","user_name","custodian"]:
                if norm(f[fld]) != norm(match[fld]):
                    diffs.append(fld)
            results.append((f,match,basis,"Matched" if not diffs else "Matched - Differences",diffs))
        else:
            results.append((f,None,"","Not Found in Field",[]))
    field_only=[r for r in assets_rows if r["id"] not in used]
    con=db()
    stats={
        "far":len(far_rows),"matched":sum(1 for r in results if r[3].startswith("Matched")),
        "differences":sum(1 for r in results if r[3]=="Matched - Differences"),
        "not_found":sum(1 for r in results if r[3]=="Not Found in Field"),
        "field_only":len(field_only)
    }
    con.close()
    return render_template("reconcile.html", results=results, field_only=field_only, stats=stats)

@app.route("/export")
def export():
    con=db(); rows=con.execute("SELECT * FROM assets ORDER BY id").fetchall(); con.close()
    out=io.StringIO(); writer=csv.writer(out)
    writer.writerow(["ID"]+FIELDS+["Source","Created At","Updated At"])
    for r in rows:
        writer.writerow([r["id"]]+[r[f] for f in FIELDS]+[r["source"],r["created_at"],r["updated_at"]])
    data=io.BytesIO(out.getvalue().encode("utf-8-sig"))
    return send_file(data, mimetype="text/csv", as_attachment=True, download_name="Plex_Field_Verification_Register.csv")

@app.route("/api/assets")
def api_assets():
    con=db(); rows=[dict(r) for r in con.execute("SELECT * FROM assets ORDER BY id DESC").fetchall()]; con.close()
    return jsonify(rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
