import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
from contextlib import closing

DB_PATH = "local_food_wastage.db"

st.set_page_config(page_title="Local Food Wastage Management", layout="wide")
st.title("Local Food Wastage Management System")

# -------------------------
# Helper Functions
# -------------------------
@st.cache_data(show_spinner=False)
def run_query(q, params=None):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return pd.read_sql_query(q, conn, params=params or {})

def exec_write(sql, params=None):
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        conn.commit()

# -------------------------
# Sidebar Filters
# -------------------------
st.sidebar.header("Filters")

cities = run_query("SELECT DISTINCT City AS city FROM providers ORDER BY City")["city"].dropna().tolist()
provider_types = run_query("SELECT DISTINCT Type AS provider_type FROM providers ORDER BY Type")["provider_type"].dropna().tolist()
food_types = run_query("SELECT DISTINCT Food_Type AS food_type FROM food_listings ORDER BY Food_Type")["food_type"].dropna().tolist()
meal_types = run_query("SELECT DISTINCT Meal_Type AS meal_type FROM food_listings ORDER BY Meal_Type")["meal_type"].dropna().tolist()

city_f = st.sidebar.multiselect("City", cities)
ptype_f = st.sidebar.multiselect("Provider Type", provider_types)
ftype_f = st.sidebar.multiselect("Food Type", food_types)
mtype_f = st.sidebar.multiselect("Meal Type", meal_types)

# -------------------------
# WHERE clause builder
# -------------------------
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

# -------------------------
# Overview Metrics
# -------------------------
col1, col2, col3, col4 = st.columns(4)
total_listings = run_query("SELECT COUNT(*) AS n FROM food_listings")["n"].iloc[0]
total_claims = run_query("SELECT COUNT(*) AS n FROM claims")["n"].iloc[0]
total_providers = run_query("SELECT COUNT(*) AS n FROM providers")["n"].iloc[0]
total_receivers = run_query("SELECT COUNT(*) AS n FROM receivers")["n"].iloc[0]

col1.metric("Food Listings", total_listings)
col2.metric("Claims", total_claims)
col3.metric("Providers", total_providers)
col4.metric("Receivers", total_receivers)

# -------------------------
# Quick Charts
# -------------------------
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
    st.altair_chart(
        alt.Chart(city_df).mark_bar().encode(y=alt.Y("city:N", sort="-x"), x="listings:Q", tooltip=["city","listings"]),
        use_container_width=True
    )

st.divider()

# -------------------------
# Tabs
# -------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["15 SQL Queries", "Filtered Listings", "Claims", "Contacts", "CRUD"])

# --- Tab 1: Queries
with tab1:
    st.caption("Outputs required by the brief (15 queries).")
    queries = {
        "1. Providers & Receivers per City": """
            SELECT p.City AS city,
                   COUNT(DISTINCT p.Provider_ID) AS providers,
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
        "3. Provider Contacts in Selected City": f"""
            SELECT Name, Type, Address, City, Contact
            FROM providers
            {"WHERE City IN (" + ",".join([f":c{i}" for i in range(len(city_f))]) + ")" if city_f else ""}
            ORDER BY Name;
        """,
        "4. Receivers with Most Claims": """
            SELECT Receiver_ID, COUNT(*) AS total_claims
            FROM claims
            GROUP BY Receiver_ID
            ORDER BY total_claims DESC
            LIMIT 10;
        """,
        "5. Total Quantity Available": """
            SELECT SUM(Quantity) AS total_quantity FROM food_listings;
        """,
        "6. City with Most Listings": """
            SELECT Location AS city, COUNT(*) AS listings
            FROM food_listings
            GROUP BY Location
            ORDER BY listings DESC
            LIMIT 1;
        """,
        "7. Most Common Food Types": """
            SELECT Food_Type AS food_type, COUNT(*) AS count
            FROM food_listings
            GROUP BY Food_Type
            ORDER BY count DESC;
        """,
        "8. Claims per Food Item": """
            SELECT Food_ID, COUNT(*) AS total_claims
            FROM claims
            GROUP BY Food_ID
            ORDER BY total_claims DESC
            LIMIT 10;
        """,
        "9. Provider with Most Successful Claims": """
            SELECT fl.Provider_ID, COUNT(*) AS successful_claims
            FROM claims c
            JOIN food_listings fl ON fl.Food_ID = c.Food_ID
            WHERE c.Status = 'Completed'
            GROUP BY fl.Provider_ID
            ORDER BY successful_claims DESC
            LIMIT 1;
        """,
        "10. Claims Status % Split": """
            SELECT Status AS status,
                   ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM claims), 2) AS pct
            FROM claims
            GROUP BY Status;
        """,
        "11. Avg Quantity Claimed per Receiver": """
            SELECT c.Receiver_ID, ROUND(AVG(fl.Quantity), 2) AS avg_qty
            FROM claims c
            JOIN food_listings fl ON fl.Food_ID = c.Food_ID
            GROUP BY c.Receiver_ID
            ORDER BY avg_qty DESC
            LIMIT 10;
        """,
        "12. Most Claimed Meal Type": """
            SELECT fl.Meal_Type AS meal_type, COUNT(*) AS claimed_count
            FROM claims c
            JOIN food_listings fl ON fl.Food_ID = c.Food_ID
            GROUP BY fl.Meal_Type
            ORDER BY claimed_count DESC
            LIMIT 1;
        """,
        "13. Total Quantity Donated by Provider": """
            SELECT Provider_ID, SUM(Quantity) AS total_qty
            FROM food_listings
            GROUP BY Provider_ID
            ORDER BY total_qty DESC
            LIMIT 10;
        """,
        "14. Pending Claims Count": """
            SELECT COUNT(*) AS pending_count FROM claims WHERE Status = 'Pending';
        """,
        "15. Completed Claims (Last 30 Days)": """
            SELECT COUNT(*) AS completed_last_30_days
            FROM claims
            WHERE Status = 'Completed'
              AND DATE(Timestamp) >= DATE('now','-30 day');
        """
    }
    for title, sql in queries.items():
        st.markdown(f"**{title}**")
        df = run_query(sql, params=params)
        st.dataframe(df, use_container_width=True)

# --- Tab 2: Listings
with tab2:
    st.caption("Listings filtered by your sidebar selections.")
    listings_sql = f"""
        SELECT fl.Food_ID, fl.Food_Name, fl.Quantity, fl.Expiry_Date,
               fl.Provider_ID, fl.Provider_Type, fl.Location, fl.Food_Type, fl.Meal_Type
        FROM food_listings fl
        {where_sql}
        ORDER BY fl.Expiry_Date ASC
    """
    listings = run_query(listings_sql, params=params)
    st.dataframe(listings, use_container_width=True)

# --- Tab 3: Claims
with tab3:
    st.caption("All claims with simple status filter.")
    claim_status = st.multiselect("Filter Claim Status", run_query("SELECT DISTINCT Status AS status FROM claims")["status"].tolist())
    where_claim = "WHERE Status IN ({})".format(",".join([f":s{i}" for i in range(len(claim_status))])) if claim_status else ""
    claim_params = {f"s{i}": v for i, v in enumerate(claim_status)}
    claims = run_query(f"SELECT * FROM claims {where_claim} ORDER BY Timestamp DESC", params=claim_params)
    st.dataframe(claims, use_container_width=True)

# --- Tab 4: Contacts
with tab4:
    st.caption("Provider & Receiver contacts (select a city to narrow).")
    pc = run_query(f"""SELECT Name, Type, City, Contact FROM providers
                      {"WHERE City IN (" + ",".join([f":c{i}" for i in range(len(city_f))]) + ")" if city_f else ""}
                      ORDER BY City, Name""", params=params)
    rc = run_query(f"""SELECT Name, Type, City, Contact FROM receivers
                      {"WHERE City IN (" + ",".join([f":c{i}" for i in range(len(city_f))]) + ")" if city_f else ""}
                      ORDER BY City, Name""", params=params)
    c1, c2 = st.columns(2)
    with c1: st.subheader("Providers"); st.dataframe(pc, use_container_width=True)
    with c2: st.subheader("Receivers"); st.dataframe(rc, use_container_width=True)

# --- Tab 5: CRUD
with tab5:
    st.caption("Minimal CRUD — add listing, update claim status, delete listing.")
    c1, c2, c3 = st.columns(3)

    # Add Listing
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
                st.success("Listing added.")

    # Update Claim
    with c2:
        st.subheader("Update Claim Status")
        with st.form("update_claim"):
            claim_id = st.number_input("Claim ID", min_value=1, step=1)
            new_status = st.selectbox("New Status", ["Pending", "Completed", "Cancelled"])
            submitted2 = st.form_submit_button("Update")
            if submitted2:
                exec_write("UPDATE claims SET Status = :s WHERE Claim_ID = :cid",
                           {"s": new_status, "cid": int(claim_id)})
                st.success("Claim updated.")

    # Delete Listing
    with c3:
        st.subheader("Delete Listing")
        with st.form("delete_listing"):
            del_food_id = st.number_input("Food ID", min_value=1, step=1)
            submitted3 = st.form_submit_button("Delete")
            if submitted3:
                exec_write("DELETE FROM food_listings WHERE Food_ID = :fid", {"fid": int(del_food_id)})
                st.warning("Listing deleted.")
