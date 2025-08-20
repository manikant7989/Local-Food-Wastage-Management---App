# Streamlit.py
import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
from contextlib import closing

# -----------------------------
# App Config
# -----------------------------
DB_PATH = "Local_Food_Wastage.db"   # <— make sure this file exists in your repo root

st.set_page_config(page_title="Local Food Wastage Management", layout="wide")
st.title("🍽️ Local Food Wastage Management System")

# -----------------------------
# Helpers
# -----------------------------
@st.cache_data(show_spinner=False)
def run_query(q: str, params: dict | None = None) -> pd.DataFrame:
    """Fast, cached SELECT helper. Raises if SQL/DB truly broken."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return pd.read_sql_query(q, conn, params=params or {})

def exec_write(sql: str, params: dict | None = None) -> None:
    """Write helper (INSERT/UPDATE/DELETE)."""
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        conn.commit()

def safe_query(q: str, params: dict | None = None) -> pd.DataFrame:
    """Non-crashing wrapper for UI; shows a warning and returns empty DataFrame on error."""
    try:
        return run_query(q, params=params)
    except Exception as e:
        st.warning(f"Query failed: {e}")
        return pd.DataFrame()

# -----------------------------
# Optional Debug (toggle in sidebar)
# -----------------------------
st.sidebar.header("🔧 Options")
show_debug = st.sidebar.checkbox("Show database schemas (debug)", value=False)

if show_debug:
    st.subheader("Database Table Columns (Debug)")
    for table in ["providers", "food_listings", "receivers", "claims"]:
        try:
            cols = run_query(f"PRAGMA table_info({table});")["name"].tolist()
            st.write(f"**{table}** → {cols}")
        except Exception as e:
            st.write(f"⚠️ Error reading `{table}`: {e}")

st.sidebar.markdown("---")

# -----------------------------
# Sidebar Filters
# -----------------------------
st.sidebar.header("🔎 Filters")

cities_df = safe_query("SELECT DISTINCT City FROM providers ORDER BY City")
cities = cities_df["City"].dropna().tolist() if not cities_df.empty else []

types_df = safe_query("SELECT DISTINCT Type FROM providers ORDER BY Type")
provider_types = types_df["Type"].dropna().tolist() if not types_df.empty else []

food_types_df = safe_query("SELECT DISTINCT Food_Type FROM food_listings ORDER BY Food_Type")
food_types = food_types_df["Food_Type"].dropna().tolist() if not food_types_df.empty else []

meal_types_df = safe_query("SELECT DISTINCT Meal_Type FROM food_listings ORDER BY Meal_Type")
meal_types = meal_types_df["Meal_Type"].dropna().tolist() if not meal_types_df.empty else []

city_f = st.sidebar.multiselect("City", cities)
ptype_f = st.sidebar.multiselect("Provider Type", provider_types)
ftype_f = st.sidebar.multiselect("Food Type", food_types)
mtype_f = st.sidebar.multiselect("Meal Type", meal_types)

# Build WHERE for listings safely
where_parts, params = [], {}

if city_f:
    where_parts.append("fl.Location IN ({})".format(",".join([f":c{i}" for i in range(len(city_f))])))
    params.update({f"c{i}": v for i, v in enumerate(city_f)})

if ptype_f:
    where_parts.append("fl.Provider_Type IN ({})".format(",".join([f":p{i}" for i in range(len(ptype_f))])))
    params.update({f"p{i}": v for i, v in enumerate(ptype_f)})

if ftype_f:
    where_parts.append("fl.Food_Type IN ({})".format(",".join([f":f{i}" for i in range(len(ftype_f))])))
    params.update({f"f{i}": v for i, v in enumerate(ftype_f)})

if mtype_f:
    where_parts.append("fl.Meal_Type IN ({})".format(",".join([f":m{i}" for i in range(len(mtype_f))])))
    params.update({f"m{i}": v for i, v in enumerate(mtype_f)})

where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

# -----------------------------
# KPI Cards
# -----------------------------
c1, c2, c3, c4 = st.columns(4)
total_listings = safe_query("SELECT COUNT(*) AS n FROM food_listings")
total_claims   = safe_query("SELECT COUNT(*) AS n FROM claims")
total_prov     = safe_query("SELECT COUNT(*) AS n FROM providers")
total_recv     = safe_query("SELECT COUNT(*) AS n FROM receivers")

c1.metric("🍱 Food Listings", int(total_listings["n"].iloc[0]) if not total_listings.empty else 0)
c2.metric("📦 Claims",        int(total_claims["n"].iloc[0])   if not total_claims.empty   else 0)
c3.metric("🏢 Providers",     int(total_prov["n"].iloc[0])     if not total_prov.empty     else 0)
c4.metric("🙋 Receivers",     int(total_recv["n"].iloc[0])     if not total_recv.empty     else 0)

# -----------------------------
# Quick Charts (Altair)
# -----------------------------
lc, rc = st.columns(2)

claims_status = safe_query("SELECT Status, COUNT(*) AS Count FROM claims GROUP BY Status")
with lc:
    st.subheader("Claims by Status")
    if not claims_status.empty:
        chart1 = (
            alt.Chart(claims_status)
            .mark_bar()
            .encode(x=alt.X("Status:N", title="Status"),
                    y=alt.Y("Count:Q", title="Count"),
                    tooltip=["Status", "Count"])
        )
        st.altair_chart(chart1, use_container_width=True)
    else:
        st.info("No claims data available.")

city_listings = safe_query("""
    SELECT Location AS City, COUNT(*) AS Listings
    FROM food_listings
    GROUP BY Location
    ORDER BY Listings DESC
""")
with rc:
    st.subheader("Listings by City")
    if not city_listings.empty:
        chart2 = (
            alt.Chart(city_listings)
            .mark_bar()
            .encode(y=alt.Y("City:N", sort="-x", title="City"),
                    x=alt.X("Listings:Q", title="Listings"),
                    tooltip=["City", "Listings"])
        )
        st.altair_chart(chart2, use_container_width=True)
    else:
        st.info("No listing data available.")

st.divider()

# -----------------------------
# Tabs
# -----------------------------
t1, t2, t3, t4, t5, t6 = st.tabs([
    "📚 15 SQL Queries", "📋 Filtered Listings", "📦 Claims",
    "📞 Contacts", "🛠️ CRUD", "🔎 Custom SQL"
])

# ---- 15 SQL queries (with expanders)
with t1:
    st.caption("Key insights required by the brief. Expand to view data.")
    queries = {
        "1) Providers & Receivers per City": """
            SELECT p.City,
                   COUNT(DISTINCT p.Provider_ID) AS Providers,
                   COUNT(DISTINCT r.Receiver_ID) AS Receivers
            FROM providers p
            LEFT JOIN receivers r ON r.City = p.City
            GROUP BY p.City
            ORDER BY Providers DESC;
        """,
        "2) Top Provider Types by Listings": """
            SELECT Provider_Type, COUNT(*) AS Count
            FROM food_listings
            GROUP BY Provider_Type
            ORDER BY Count DESC;
        """,
        "3) Food Type Distribution": """
            SELECT Food_Type, COUNT(*) AS Count
            FROM food_listings
            GROUP BY Food_Type
            ORDER BY Count DESC;
        """,
        "4) Receivers with Most Claims": """
            SELECT Receiver_ID, COUNT(*) AS Total_Claims
            FROM claims
            GROUP BY Receiver_ID
            ORDER BY Total_Claims DESC
            LIMIT 10;
        """,
        "5) Total Quantity Available": """
            SELECT COALESCE(SUM(Quantity),0) AS Total_Quantity
            FROM food_listings;
        """,
        "6) City with Most Listings": """
            SELECT Location AS City, COUNT(*) AS Listings
            FROM food_listings
            GROUP BY Location
            ORDER BY Listings DESC
            LIMIT 1;
        """,
        "7) Most Common Food Types": """
            SELECT Food_Type, COUNT(*) AS Count
            FROM food_listings
            GROUP BY Food_Type
            ORDER BY Count DESC;
        """,
        "8) Claims per Food Item": """
            SELECT Food_ID, COUNT(*) AS Total_Claims
            FROM claims
            GROUP BY Food_ID
            ORDER BY Total_Claims DESC
            LIMIT 10;
        """,
        "9) Provider with Most Successful Claims": """
            SELECT fl.Provider_ID, COUNT(*) AS Successful_Claims
            FROM claims c
            JOIN food_listings fl ON fl.Food_ID = c.Food_ID
            WHERE c.Status = 'Completed'
            GROUP BY fl.Provider_ID
            ORDER BY Successful_Claims DESC
            LIMIT 1;
        """,
        "10) Claims Status % Split": """
            SELECT Status,
                   ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM claims), 2) AS Percent
            FROM claims
            GROUP BY Status;
        """,
        "11) Avg Quantity Claimed per Receiver": """
            SELECT c.Receiver_ID, ROUND(AVG(fl.Quantity), 2) AS Avg_Qty
            FROM claims c
            JOIN food_listings fl ON fl.Food_ID = c.Food_ID
            GROUP BY c.Receiver_ID
            ORDER BY Avg_Qty DESC
            LIMIT 10;
        """,
        "12) Most Claimed Meal Type": """
            SELECT fl.Meal_Type, COUNT(*) AS Claimed_Count
            FROM claims c
            JOIN food_listings fl ON fl.Food_ID = c.Food_ID
            GROUP BY fl.Meal_Type
            ORDER BY Claimed_Count DESC
            LIMIT 1;
        """,
        "13) Total Quantity Donated by Provider": """
            SELECT Provider_ID, SUM(Quantity) AS Total_Qty
            FROM food_listings
            GROUP BY Provider_ID
            ORDER BY Total_Qty DESC
            LIMIT 10;
        """,
        "14) Pending Claims Count": """
            SELECT COUNT(*) AS Pending_Count
            FROM claims
            WHERE Status = 'Pending';
        """,
        "15) Completed Claims (Last 30 Days)": """
            SELECT COUNT(*) AS Completed_Last_30_Days
            FROM claims
            WHERE Status = 'Completed'
              AND DATE(Timestamp) >= DATE('now','-30 day');
        """
    }

    for title, sql in queries.items():
        with st.expander(title, expanded=False):
            df = safe_query(sql)
            st.dataframe(df, use_container_width=True)

# ---- Filtered Listings
with t2:
    st.caption("Listings filtered by your sidebar selections.")
    listings_sql = f"""
        SELECT fl.Food_ID, fl.Food_Name, fl.Quantity, fl.Expiry_Date,
               fl.Provider_ID, fl.Provider_Type, fl.Location, fl.Food_Type, fl.Meal_Type
        FROM food_listings fl
        {where_sql}
        ORDER BY fl.Expiry_Date ASC
    """
    listings = safe_query(listings_sql, params=params)
    st.dataframe(listings, use_container_width=True)

# ---- Claims
with t3:
    st.caption("All claims with status filter.")
    status_opts_df = safe_query("SELECT DISTINCT Status FROM claims ORDER BY Status")
    status_opts = status_opts_df["Status"].tolist() if not status_opts_df.empty else []
    sel = st.multiselect("Filter Claim Status", status_opts)
    where_claim = "WHERE Status IN ({})".format(",".join([f":s{i}" for i in range(len(sel))])) if sel else ""
    claim_params = {f"s{i}": v for i, v in enumerate(sel)}
    claims = safe_query(f"SELECT * FROM claims {where_claim} ORDER BY Timestamp DESC", params=claim_params)
    st.dataframe(claims, use_container_width=True)

# ---- Contacts
with t4:
    st.caption("Provider & Receiver contacts (use City filter on the left).")
    pc = safe_query(
        "SELECT Name, Type, City, Contact FROM providers "
        + ("WHERE City IN (" + ",".join([f":c{i}" for i in range(len(city_f))]) + ")" if city_f else "")
        + " ORDER BY City, Name",
        params=params
    )
    rc = safe_query(
        "SELECT Name, Type, City, Contact FROM receivers "
        + ("WHERE City IN (" + ",".join([f":c{i}" for i in range(len(city_f))]) + ")" if city_f else "")
        + " ORDER BY City, Name",
        params=params
    )
    cc1, cc2 = st.columns(2)
    with cc1:
        st.subheader("Providers")
        st.dataframe(pc, use_container_width=True)
    with cc2:
        st.subheader("Receivers")
        st.dataframe(rc, use_container_width=True)

# ---- CRUD
with t5:
    st.caption("Minimal CRUD — add listing, update claim status, delete listing.")
    a, b, c = st.columns(3)

    with a:
        st.subheader("Add Listing")
        with st.form("add_listing"):
            food_name = st.text_input("Food Name")
            qty = st.number_input("Quantity", min_value=1, step=1)
            expiry = st.date_input("Expiry Date")
            provider_id = st.number_input("Provider ID", min_value=1, step=1)
            provider_type_in = st.text_input("Provider Type")
            location = st.text_input("City")
            food_type_in = st.text_input("Food Type")
            meal_type_in = st.text_input("Meal Type")
            submitted = st.form_submit_button("Add")
            if submitted:
                try:
                    exec_write("""
                        INSERT INTO food_listings
                          (Food_Name, Quantity, Expiry_Date, Provider_ID,
                           Provider_Type, Location, Food_Type, Meal_Type)
                        VALUES (:n, :q, :e, :pid, :pt, :loc, :ft, :mt)
                    """, {
                        "n": food_name, "q": int(qty), "e": str(expiry),
                        "pid": int(provider_id), "pt": provider_type_in, "loc": location,
                        "ft": food_type_in, "mt": meal_type_in
                    })
                    st.success("✅ Listing added.")
                    st.cache_data.clear()  # refresh cached queries
                except Exception as e:
                    st.error(f"❌ Failed to add listing: {e}")

    with b:
        st.subheader("Update Claim Status")
        with st.form("update_claim"):
            claim_id = st.number_input("Claim ID", min_value=1, step=1)
            new_status = st.selectbox("New Status", ["Pending", "Completed", "Cancelled"])
            submitted2 = st.form_submit_button("Update")
            if submitted2:
                try:
                    exec_write("UPDATE claims SET Status = :s WHERE Claim_ID = :cid",
                               {"s": new_status, "cid": int(claim_id)})
                    st.success("✅ Claim updated.")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"❌ Failed to update claim: {e}")

    with c:
        st.subheader("Delete Listing")
        with st.form("delete_listing"):
            del_food_id = st.number_input("Food ID", min_value=1, step=1)
            submitted3 = st.form_submit_button("Delete")
            if submitted3:
                try:
                    exec_write("DELETE FROM food_listings WHERE Food_ID = :fid", {"fid": int(del_food_id)})
                    st.warning("⚠️ Listing deleted.")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"❌ Failed to delete listing: {e}")

# ---- Custom SQL
with t6:
    st.caption("Write and run your own SQL (read-only recommended).")
    ex = st.toggle("Show sample queries")
    if ex:
        st.code(
            "SELECT * FROM providers LIMIT 5;\n"
            "SELECT City, COUNT(*) AS n FROM providers GROUP BY City ORDER BY n DESC;\n"
            "SELECT * FROM food_listings WHERE Location = 'Hyderabad' ORDER BY Expiry_Date;"
        )
    sql_input = st.text_area("Enter SQL Query:", height=160, placeholder="SELECT * FROM providers LIMIT 10;")
    run_btn = st.button("Run Query")
    if run_btn and sql_input.strip():
        try:
            df = run_query(sql_input)   # use cached SELECT
            st.success("✅ Query executed successfully!")
            st.dataframe(df, use_container_width=True)
            if not df.empty:
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("Download results as CSV", data=csv, file_name="query_results.csv", mime="text/csv")
        except Exception as e:
            st.error(f"❌ Error: {e}")
