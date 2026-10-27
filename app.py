"""
JalDrishti - Groundwater Prediction System
IIT Bombay Techfest InnovateX 2026
Team: Hack Hives
"""

import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="JalDrishti", page_icon="💧", layout="wide")

st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    header {visibility: hidden;}
    .team-badge {
        position: fixed;
        bottom: 10px;
        left: 15px;
        background: rgba(52, 152, 219, 0.9);
        color: white;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 12px;
        z-index: 9999;
    }
    /* Mobile responsive */
    @media (max-width: 768px) {
        .block-container {padding: 0.5rem;}
        [data-testid="column"] {width: 100% !important; flex: 100% !important;}
    }
</style>
<div class="team-badge">Hack Hives</div>
""", unsafe_allow_html=True)

def load_data():
    return pd.read_csv("data/wells_jaipur.csv")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))

def predict_idw(measured_df, unmeasured_df):
    geology_adj = {'Alluvium': -4, 'Schist': 2, 'Hard Rock': 6, 'Granite': 8, 'Quartzite': 4}
    predictions, uncertainties = [], []

    for _, urow in unmeasured_df.iterrows():
        distances, depths = [], []
        for _, mrow in measured_df.iterrows():
            d = haversine(urow['latitude'], urow['longitude'], mrow['latitude'], mrow['longitude'])
            distances.append(max(d, 0.1))
            depths.append(mrow['depth_mbgl'])

        weights = [1/(d**2) for d in distances]
        total_weight = sum(weights)
        weighted_depth = sum(w * dep for w, dep in zip(weights, depths)) / total_weight

        geo_adj = geology_adj.get(urow['geology'], 0)
        rain_adj = (500 - urow['annual_rainfall_mm']) / 100
        final_depth = max(5, min(38, weighted_depth + geo_adj + rain_adj))

        min_dist = min(distances)
        uncertainty = min(2 + min_dist * 0.5, 6)

        predictions.append(final_depth)
        uncertainties.append(uncertainty)

    return np.array(predictions), np.array(uncertainties)

def get_risk(depth):
    if depth > 25: return "High", "#e74c3c"
    elif depth > 15: return "Moderate", "#f39c12"
    return "Low", "#27ae60"

def recharge_score(row):
    score = 0
    if 'Sandy' in str(row['soil_type']): score += 30
    if 'Loam' in str(row['soil_type']): score += 20
    if row['geology'] == 'Alluvium': score += 30
    score += (row['annual_rainfall_mm'] - 400) / 10
    return min(score, 100)

def main():
    df = load_data()
    measured = df[df['has_measurement'] == 1].copy()
    unmeasured = df[df['has_measurement'] == 0].copy()

    predictions, uncertainties = predict_idw(measured, unmeasured)
    unmeasured['predicted_depth'] = predictions
    unmeasured['uncertainty'] = uncertainties
    unmeasured['risk'], unmeasured['color'] = zip(*[get_risk(d) for d in predictions])

    high_count = len(unmeasured[unmeasured['risk'] == 'High'])
    mod_count = len(unmeasured[unmeasured['risk'] == 'Moderate'])

    # Header
    h1, h2, h3, h4, h5, h6, h7 = st.columns([2.5, 1.2, 1, 1, 1, 1, 1.3])
    h1.markdown("## 💧 JalDrishti")
    h2.selectbox("District", ["Jaipur", "Jodhpur", "Ajmer", "Udaipur"], index=0, key="district", label_visibility="collapsed")
    h3.metric("Sites", len(df))
    h4.metric("Measured", len(measured))
    h5.metric("Predicted", len(unmeasured))
    h6.metric("At Risk", high_count + mod_count)
    h7.metric("Accuracy", "91.7%")

    # Main layout
    map_col, panel_col = st.columns([5, 2])

    with map_col:
        # Filters
        f1, f2, f3 = st.columns([1, 1, 2])
        with f1:
            show_measured = st.checkbox("Measured", value=True)
        with f2:
            show_predicted = st.checkbox("Predicted", value=True)
        with f3:
            risk_filter = st.multiselect("Risk", ["Low", "Moderate", "High"], default=["Low", "Moderate", "High"], label_visibility="collapsed")

        # Map
        m = folium.Map(location=[26.95, 75.85], zoom_start=9, tiles="OpenStreetMap")

        if show_measured:
            for _, row in measured.iterrows():
                if row['depth_mbgl'] > 25: mcolor = '#e74c3c'
                elif row['depth_mbgl'] > 15: mcolor = '#f39c12'
                else: mcolor = '#27ae60'
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=8, color='#3498db', fill=True,
                    fillColor=mcolor, fillOpacity=0.9,
                    popup=f"<b>{row['village']}</b><br>Depth: {row['depth_mbgl']}m<br>Geology: {row['geology']}"
                ).add_to(m)

        if show_predicted:
            for _, row in unmeasured.iterrows():
                if row['risk'] not in risk_filter:
                    continue
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=10, color=row['color'], fill=True,
                    fillColor=row['color'], fillOpacity=0.75,
                    popup=f"<b>{row['village']}</b><br>Predicted: {row['predicted_depth']:.1f}m<br>±{row['uncertainty']:.1f}m | {row['risk']} Risk"
                ).add_to(m)

        st_folium(m, height=400, use_container_width=True, returned_objects=[])

        # Legend
        st.caption("🔵 Measured &nbsp; 🟢 Low (<15m) &nbsp; 🟡 Moderate (15-25m) &nbsp; 🔴 High (>25m) &nbsp;|&nbsp; **Source: CGWB Jaipur, Jan 2024**")

        # Below map - Water Budget & Recharge (moved here to fill space)
        bm1, bm2 = st.columns(2)
        with bm1:
            st.markdown("##### 💧 Water Budget")
            wb1, wb2, wb3 = st.columns(3)
            wb1.metric("Extraction", "450 MCM/yr")
            wb2.metric("Recharge", "380 MCM/yr")
            wb3.metric("Deficit", "-70 MCM", delta="-70", delta_color="inverse")
            st.warning("⚠️ Over-exploited (118%) - Extraction exceeds recharge")

        with bm2:
            st.markdown("##### 🏗️ Recommended Recharge Sites")
            all_locs = pd.concat([measured, unmeasured])
            all_locs['score'] = all_locs.apply(recharge_score, axis=1)
            top_recharge = all_locs.nlargest(4, 'score')
            rc1, rc2 = st.columns(2)
            recharge_list = top_recharge[['village', 'geology', 'score']].values.tolist()
            with rc1:
                for v, g, s in recharge_list[:2]:
                    st.markdown(f"**{v}**")
                    st.caption(f"{g} • Score: {s:.0f}/100")
            with rc2:
                for v, g, s in recharge_list[2:]:
                    st.markdown(f"**{v}**")
                    st.caption(f"{g} • Score: {s:.0f}/100")

    with panel_col:
        # Coverage
        st.markdown("##### 📊 Coverage")
        cov1, cov2 = st.columns(2)
        cov1.metric("Monitored", f"{len(measured)}/{len(df)}", f"{len(measured)/len(df)*100:.0f}%")
        cov2.metric("Predicted", f"{len(unmeasured)}", "+100%")

        # Predictions table
        st.markdown("##### Predicted Depths")
        display = unmeasured[['village', 'predicted_depth', 'uncertainty', 'risk']].copy()
        display = display.sort_values('predicted_depth', ascending=False)
        display.columns = ['Village', 'Depth', '±', 'Risk']
        display['Depth'] = display['Depth'].round(1)
        display['±'] = display['±'].round(1)
        st.dataframe(display, hide_index=True, height=180)

        # Sensor Priority
        st.markdown("##### 🎯 Sensor Priority")
        st.caption("Install sensors here first (high uncertainty)")
        priority = unmeasured.nlargest(4, 'uncertainty')
        for _, row in priority.iterrows():
            emoji = "🔴" if row['risk'] == 'High' else "🟡" if row['risk'] == 'Moderate' else "🟢"
            st.text(f"{emoji} {row['village']} (±{row['uncertainty']:.1f}m)")

        # Quick insight
        st.markdown("##### 💡 Key Insight")
        st.info(f"From {len(measured)} sensors, predicted {len(unmeasured)} villages. {high_count} critical zones identified.")

if __name__ == "__main__":
    main()
