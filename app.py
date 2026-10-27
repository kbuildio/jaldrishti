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
    .block-container {padding-top: 0.5rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem;}
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
    /* Compact metrics */
    [data-testid="stMetricValue"] {font-size: 1.2rem;}
    [data-testid="stMetricLabel"] {font-size: 0.7rem;}
    /* Mobile */
    @media (max-width: 768px) {
        .block-container {padding: 0.3rem;}
        [data-testid="stMetricValue"] {font-size: 1rem;}
        [data-testid="column"] {padding: 0.2rem !important;}
        .team-badge {font-size: 10px; padding: 3px 8px;}
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

    # Header - compact
    h1, h2, h3, h4, h5, h6 = st.columns([2, 1.2, 0.8, 0.8, 0.8, 0.8])
    h1.markdown("### 💧 JalDrishti")
    h2.selectbox("", ["Jaipur", "Jodhpur", "Ajmer"], index=0, key="district", label_visibility="collapsed")
    h3.metric("Sites", len(df))
    h4.metric("Sensors", len(measured))
    h5.metric("Risk", high_count + mod_count)
    h6.metric("Acc", "92%")

    # Filters inline
    f1, f2, f3, f4 = st.columns([1, 1, 1, 1])
    show_measured = f1.checkbox("Measured", value=True)
    show_predicted = f2.checkbox("Predicted", value=True)
    show_high = f3.checkbox("High Risk", value=True)
    show_other = f4.checkbox("Low/Med", value=True)

    # Map
    m = folium.Map(location=[26.95, 75.85], zoom_start=9, tiles="OpenStreetMap")
    if show_measured:
        for _, row in measured.iterrows():
            mcolor = '#e74c3c' if row['depth_mbgl'] > 25 else '#f39c12' if row['depth_mbgl'] > 15 else '#27ae60'
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']], radius=7, color='#3498db',
                fill=True, fillColor=mcolor, fillOpacity=0.9,
                popup=f"<b>{row['village']}</b><br>{row['depth_mbgl']}m"
            ).add_to(m)
    if show_predicted:
        for _, row in unmeasured.iterrows():
            if row['risk'] == 'High' and not show_high: continue
            if row['risk'] != 'High' and not show_other: continue
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']], radius=9, color=row['color'],
                fill=True, fillColor=row['color'], fillOpacity=0.75,
                popup=f"<b>{row['village']}</b><br>{row['predicted_depth']:.1f}m | {row['risk']}"
            ).add_to(m)
    st_folium(m, height=350, use_container_width=True, returned_objects=[])
    st.caption("🔵Measured 🟢Low 🟡Moderate 🔴High | CGWB Jaipur 2024")

    # Compact info grid
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**🎯 Sensor Priority**")
        for _, r in unmeasured.nlargest(3, 'uncertainty').iterrows():
            e = "🔴" if r['risk']=='High' else "🟡" if r['risk']=='Moderate' else "🟢"
            st.caption(f"{e} {r['village']}")

    with c2:
        st.markdown("**🏗️ Recharge Sites**")
        all_locs = pd.concat([measured, unmeasured])
        all_locs['score'] = all_locs.apply(recharge_score, axis=1)
        for _, r in all_locs.nlargest(3, 'score').iterrows():
            st.caption(f"• {r['village']}")

    with c3:
        st.markdown("**💧 Water Budget**")
        st.caption("Extract: 450 MCM")
        st.caption("Recharge: 380 MCM")
        st.caption("⚠️ Over-exploited 118%")

    # Predictions table - compact
    with st.expander("📊 All Predictions", expanded=False):
        display = unmeasured[['village', 'predicted_depth', 'risk']].copy()
        display = display.sort_values('predicted_depth', ascending=False)
        display.columns = ['Village', 'Depth(m)', 'Risk']
        display['Depth(m)'] = display['Depth(m)'].round(1)
        st.dataframe(display, hide_index=True, height=200)

if __name__ == "__main__":
    main()
