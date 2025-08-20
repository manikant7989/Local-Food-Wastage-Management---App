import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px
from contextlib import closing

DB_PATH = "local_food_wastage.db"

# --- App Config ---
st.set_page_config(page_title="Local Food Wastage Management", layout="wide")
st.title("🍽️ Local Food Wastage Management System")

# --- Utility functions ---
@st.cache_data(show_spinner=False)
def run_query(q, params=None):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return pd.read_sql_query(q, conn, params=params or {})

def exec_write(sql, params=None):
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        conn.commit()

# --- Sidebar Filters ---
st.sidebar.header("🔎 Filters")

cities = run_query("SELECT DISTINCT City AS city FROM providers ORDER BY City")["city"].dropna().tolist()
provider_types = run_query("SELECT DISTINCT Type AS provider_type FROM providers ORDER BY Type")["provider_type"].dropna().tolist()
food_types = run_query("SELECT DISTINCT Food_Type AS food_type FROM food_listings ORDER BY Food_Type")["food_type"].dropna().tolist()
meal_types = run_query("SELECT DISTINCT Meal_Type AS meal_type FROM food_listings ORDER BY Meal_Type")["meal_type"].dropna().tolist()
claim_statuses = run_query("SELECT DISTINCT Status AS status FROM claims ORDER BY Status")["status"].dropna().tolist()


city_f = st.sidebar.multiselect("City", cities)
ptype_f = st.sidebar.multiselect("Provider Type", provider_types)
ftype_f = st.sidebar.multiselect("Food Type", food_types)
mtype_f = st.sidebar.multiselect("Meal Type", meal_types)
claim_f = st.sidebar.multiselect("Claim Status", claim_statuses)

# Build WHERE clause for listings
where = []
params = {}
if city_f:
    where.append("fl.Location IN ({})".format(",".join([f":c{i}" for i in range(len(city_f))])))
    params.update({f"c{i}": v for i, v in enumerate(city_f)})
if ptype_f:
    where.append("fl.Provider_Type IN ({})".format(",".join([f":p{i}" for i in range(len(ptype_f))])))
    params.update({f"p{i}": v for i, v in enumerate(ptype_f)})
if ftype_f:
    where.append("fl.Food_Type IN ({})".format(",".join([f":f{i}" for i in range(len(ftype_f))])))
    params.update({f"f{i}": v for i, v in enumerate(ftype_f)})
if mtype_f:
    where.append("fl.Meal_Type IN ({})".format(",".join([f":m{i}" for i in range(len(mtype_f))])))
    params.update({f"m{i}": v for i, v in enumerate(mtype_f)})

where_sql = ("WHERE " + " AND ".join(where)) if where else ""

# --- Dashboard KPIs ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("🍱 Food Listings", run_query("SELECT COUNT(*) AS n FROM food_listings")["n"].iloc[0])
col2.metric("📦 Claims", run_query("SELECT COUNT(*) AS n FROM claims")["n"].iloc[0])
col3.metric("🏢 Providers", run_query("SELECT COUNT(*) AS n FROM providers")["n"].iloc[0])
col4.metric("🙋 Receivers", run_query("SELECT COUNT(*) AS n FROM receivers")["n"].iloc[0])

# --- Quick Charts ---
left, right = st.columns(2)
status_df = run_query("SELECT Status AS status, COUNT(*) AS count FROM claims GROUP BY Status")
with left:
    st.subheader("Claims by Status")
    st.altair_chart(
        alt.Chart(status_df).mark_bar().encode(x="status:N", y="count:Q", tooltip=["status","count"]),
        use_container_width=True
    )

city_df = run_query("SELECT Location AS city, COUNT(*) AS listings FROM food_listings GROUP BY Location ORDER BY listings DESC")
with right:
    st.subheader("Listings by City")
    st.plotly_chart(px.bar(city_df, x="city", y="listings", color="listings", text="listings"), use_container_width=True)

st.divider()

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 15 SQL Queries", "📋 Filtered Listings", "📦 Claims", "📞 Contacts", "🛠️ CRUD", "🔎 Custom Query"
])

with tab1:
    st.caption("Outputs required by the brief (15 queries).")
    queries = {
        "1. Providers & Receivers per City": """
            SELECT p.City AS city, COUNT(DISTINCT p.Provider_ID) AS providers,
                   COUNT(DISTINCT r.Receiver_ID) AS receivers
            FROM providers p
            LEFT JOIN receivers r ON r.City = p.City
            GROUP BY p.City
            ORDER BY providers DESC;
        """,
        "2. Top Provider Types by Listings": """
            SELECT Provider_Type AS provider_type, COUNT(*) AS count
            FROM food_listings
            GROUP BY Provider_Type
            ORDER BY count DESC;
        """,
        "3. Food Type Distribution": """
            SELECT Food_Type AS food_type, COUNT(*) AS count
            FROM food_listings
            GROUP BY Food_Type
            ORDER BY count DESC;
        """,
        # ... add the rest of the 15 queries here
    }
    for title, sql in queries.items():
        st.markdown(f"**{title}**")
        df = run_query(sql, params=params)
        st.dataframe(df, use_container_width=True)

with tab2:
    st.caption("Listings filtered by your sidebar selections.")
    listings_sql = f"""
        SELECT Food_ID, Food_Name, Quantity, Expiry_Date,
               Provider_ID, Provider_Type, Location, Food_Type, Meal_Type
        FROM food_listings fl
        {where_sql}
        ORDER BY Expiry_Date ASC
    """
    listings = run_query(listings_sql, params=params)
    st.dataframe(listings, use_container_width=True)

with tab3:
    st.caption("All claims (filtered by Claim Status).")
    claim_sql = f"""
        SELECT * FROM claims
        {"WHERE Status IN (" + ",".join([f":s{i}" for i in range(len(claim_f))]) + ")" if claim_f else ""}
        ORDER BY Timestamp DESC
    """
    claim_params = {f"s{i}": v for i, v in enumerate(claim_f)}
    claims = run_query(claim_sql, params=claim_params)
    st.dataframe(claims, use_container_width=True)

with tab4:
    st.caption("Provider & Receiver contacts (filtered by City).")
    pc = run_query(f"""SELECT Name, Type, City, Contact FROM providers
                      {"WHERE City IN (" + ",".join([f":c{i}" for i in range(len(city_f))]) + ")" if city_f else ""}
                      ORDER BY City, Name""", params=params)
    rc = run_query(f"""SELECT Name, Type, City, Contact FROM receivers
                      {"WHERE City IN (" + ",".join([f":c{i}" for i in range(len(city_f))]) + ")" if city_f else ""}
                      ORDER BY City, Name""", params=params)
    c1, c2 = st.columns(2)
    with c1: st.subheader("Providers"); st.dataframe(pc, use_container_width=True)
    with c2: st.subheader("Receivers"); st.dataframe(rc, use_container_width=True)

with tab5:
    st.caption("Minimal CRUD — add listing, update claim status, delete listing.")
    c1, c2, c3 = st.columns(3)

    with c1:
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
                exec_write("""
                    INSERT INTO food_listings (Food_Name, Quantity, Expiry_Date, Provider_ID,
                                               Provider_Type, Location, Food_Type, Meal_Type)
                    VALUES (:n, :q, :e, :pid, :pt, :loc, :ft, :mt)
                """, {
                    "n": food_name, "q": int(qty), "e": str(expiry),
                    "pid": int(provider_id), "pt": provider_type_in, "loc": location,
                    "ft": food_type_in, "mt": meal_type_in
                })
                st.success("✅ Listing added.")

    with c2:
        st.subheader("Update Claim Status")
        with st.form("update_claim"):
            claim_id = st.number_input("Claim ID", min_value=1, step=1)
            new_status = st.selectbox("New Status", ["Pending", "Completed", "Cancelled"])
            submitted2 = st.form_submit_button("Update")
            if submitted2:
                exec_write("UPDATE claims SET Status = :s WHERE Claim_ID = :cid",
                           {"s": new_status, "cid": int(claim_id)})
                st.success("✅ Claim updated.")

    with c3:
        st.subheader("Delete Listing")
        with st.form("delete_listing"):
            del_food_id = st.number_input("Food ID", min_value=1, step=1)
            submitted3 = st.form_submit_button("Delete")
            if submitted3:
                exec_write("DELETE FROM food_listings WHERE Food_ID = :fid", {"fid": int(del_food_id)})
                st.warning("⚠️ Listing deleted.")

with tab6:
    st.caption("Write and execute your own SQL query below ⬇️")
    sql_input = st.text_area("Enter SQL Query:", height=150)
    if st.button("Run Query"):
        try:
            df = run_query(sql_input)
            st.success("✅ Query executed successfully!")
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"❌ Error: {e}")
