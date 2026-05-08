"""Shared AppBid Terminal-inspired UI helpers for Streamlit pages."""

from __future__ import annotations

import streamlit as st


def apply_appbid_theme() -> None:
    """Inject global CSS inspired by the handoff design tokens."""
    st.markdown(
        """
<style>
:root {
  --navy-950: #0a1628;
  --navy-900: #0f1f3d;
  --gold-500: #ca8a04;
  --gold-300: #f4c668;
  --ink-950: #0c0d10;
  --ink-700: #353941;
  --ink-500: #6b7180;
  --ink-150: #e6e8ee;
  --ink-100: #eef0f4;
  --ink-50: #f7f8fa;
  --paper: #ffffff;
  --success-600: #15803d;
}

.stApp {
  background: var(--ink-50);
}

[data-testid="stSidebar"] {
  background: var(--paper);
  border-right: 1px solid var(--ink-150);
}

[data-testid="stSidebar"] > div:first-child {
  padding-top: 0.6rem;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
  color: var(--ink-950);
}

[data-testid="stMetric"] {
  background: var(--paper);
  border: 1px solid var(--ink-150);
  border-radius: 8px;
  padding: 10px 12px;
}

div[data-testid="stVerticalBlock"] div:has(> [data-testid="stMetric"]) {
  gap: 10px;
}

[data-testid="stMetricLabel"] {
  color: var(--ink-500);
}

[data-testid="stMetricValue"] {
  color: var(--ink-950);
}

[data-baseweb="tab-list"] {
  gap: 8px;
  margin-bottom: 8px;
}

[data-baseweb="tab"] {
  background: var(--paper);
  border: 1px solid var(--ink-150);
  border-radius: 6px;
  padding: 6px 12px;
}

[aria-selected="true"][data-baseweb="tab"] {
  background: var(--navy-900);
  color: #fff;
  border-color: var(--navy-900);
}

.stExpander {
  border: 1px solid var(--ink-150) !important;
  border-radius: 8px !important;
  background: var(--paper);
}

[data-testid="stButton"] button[kind="primary"] {
  background: var(--navy-900);
  border-color: var(--navy-900);
}

[data-testid="stButton"] button[kind="primary"]:hover {
  background: #14305c;
  border-color: #14305c;
}

.appbid-sidebar-brand {
  background: linear-gradient(140deg, var(--navy-950), var(--navy-900));
  border: 1px solid #0f1f3d;
  border-radius: 8px;
  padding: 12px 12px;
  margin-bottom: 12px;
}

.appbid-sidebar-brand h3 {
  margin: 0;
  color: #fff;
  font-size: 1rem;
  letter-spacing: -0.01em;
}

.appbid-sidebar-brand p {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.75);
  font-size: 0.78rem;
}

.appbid-header {
  background: linear-gradient(120deg, var(--navy-950), var(--navy-900));
  color: #fff;
  border: 1px solid #0f1f3d;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 8px 24px rgba(15, 31, 61, 0.12);
}

.appbid-header h2 {
  margin: 0 0 6px 0;
  color: #fff;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.appbid-header p {
  margin: 0;
  color: rgba(255, 255, 255, 0.82);
  font-size: 0.92rem;
}

.appbid-pill {
  display: inline-block;
  margin-top: 10px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(202, 138, 4, 0.2);
  border: 1px solid rgba(244, 198, 104, 0.4);
  color: var(--gold-300);
  font-size: 0.74rem;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.appbid-section-label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink-500);
  font-size: 0.72rem;
  font-weight: 600;
  margin-bottom: 0.3rem;
}

.appbid-overview-card {
  background: var(--paper);
  border: 1px solid var(--ink-150);
  border-radius: 8px;
  padding: 12px;
  min-height: 92px;
}

.appbid-overview-card .label {
  color: var(--ink-500);
  font-size: 0.72rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-weight: 600;
  margin-bottom: 4px;
}

.appbid-overview-card .value {
  color: var(--ink-950);
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.1;
}

.appbid-overview-card .sub {
  color: var(--ink-500);
  font-size: 0.76rem;
  margin-top: 4px;
}

.appbid-health-live {
  display: inline-block;
  margin-top: 6px;
  padding: 2px 7px;
  border-radius: 999px;
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
  color: var(--success-600);
  font-size: 0.67rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str, mode_label: str) -> None:
    """Render a branded header card aligned with the handoff style."""
    st.markdown(
        f"""
<section class="appbid-header">
  <h2>{title}</h2>
  <p>{subtitle}</p>
  <span class="appbid-pill">DEMO MODE · {mode_label}</span>
</section>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    """Render prototype-inspired brand card in Streamlit sidebar."""
    st.markdown(
        """
<section class="appbid-sidebar-brand">
  <h3>AppBid Terminal</h3>
  <p>Marketplace Console · v0.4.2</p>
</section>
        """,
        unsafe_allow_html=True,
    )
