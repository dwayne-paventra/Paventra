import streamlit as st


def load_css():
    st.markdown(
        """
<style>

/* Hide Streamlit UI */
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
header {visibility:hidden;}

/* Main page */
.block-container{
    padding-top:1.5rem;
    padding-bottom:2rem;
}

/* Sidebar */
[data-testid="stSidebar"]{
    background:#F6F8FB;
}

/* Metric Cards */

.metric-card{
    background:white;
    border-radius:18px;
    padding:22px;
    box-shadow:0 4px 14px rgba(0,0,0,.08);
    transition:.3s;
}

.metric-card:hover{
    transform:translateY(-4px);
    box-shadow:0 8px 22px rgba(0,0,0,.12);
}

</style>
""",
        unsafe_allow_html=True,
    )