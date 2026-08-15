import streamlit as st


def load_css():
    st.markdown(
        """
<style>

/* Keep presentation chrome quiet while preserving the responsive sidebar control. */
#MainMenu {visibility:hidden;}
footer {visibility:hidden;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stToolbar"] {visibility:hidden;}

/* Main page */
.block-container{
    max-width:1380px;
    padding-top:1rem;
    padding-bottom:2rem;
}

/* Sidebar */
[data-testid="stSidebar"]{
    background:#F6F8FB;
}

h1 {
    color:#0b3c5d;
    font-size:clamp(1.8rem, 3vw, 2.65rem) !important;
    letter-spacing:-.025em;
    line-height:1.08 !important;
}

h2, h3 { color:#17324d; }

[data-testid="stMetric"] {
    background:#ffffff;
    border:1px solid #dce6ed;
    border-radius:12px;
    box-shadow:0 3px 12px rgba(11,60,93,.07);
    min-height:112px;
    padding:16px 18px;
}

[data-testid="stMetricLabel"] { color:#52697a; }
[data-testid="stMetricValue"] { color:#0b3c5d; }

.paventra-status-chip {
    background:#e7f0f6;
    border:1px solid #bfd1dd;
    border-radius:999px;
    color:#0b3c5d;
    display:inline-block;
    font-size:.76rem;
    font-weight:700;
    letter-spacing:.03em;
    margin:0 0 .35rem;
    padding:.22rem .6rem;
    text-transform:uppercase;
}

.paventra-workflow-arrow {
    color:#7892a5;
    font-size:1.5rem;
    line-height:1;
    padding:.25rem 0;
    text-align:center;
}

.pilot-notice {
    background:#eef5f9;
    border-left:4px solid #4d7f9f;
    border-radius:7px;
    color:#17324d;
    font-size:.86rem;
    margin:.5rem 0 1rem;
    padding:.65rem .8rem;
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

@media (max-width: 768px) {
    .block-container { padding-top:.65rem; }
    [data-testid="stMetric"] { min-height:96px; padding:12px; }
}

</style>
""",
        unsafe_allow_html=True,
    )
