"""labdata dashboard adapter bundled with chipmunk-dashboard."""

dashboard_name = "**Chipmunk**"


def dashboard_function(schema=None):
    """Render the Chipmunk dashboard inside labdata's Streamlit app."""
    from chipmunk_dashboard.streamlit_page import render_dashboard

    return render_dashboard(schema=schema)
