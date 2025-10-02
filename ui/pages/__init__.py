"""Page modules for the planning application.

Streamlit multi-page application structure:
- Pages are automatically discovered from numbered files in this directory
- Format: N_Page_Name.py (e.g., 1_Upload_Data.py, 2_Data_Summary.py)
- Pages appear in sidebar navigation in numerical order

Available pages:
1. Upload Data - Data upload and parsing
2. Data Summary - View loaded data
3. Planning Workflow - Execute planning process
4. Production Schedule - Production analysis
5. Distribution Plan - Distribution and truck loading
6. Cost Analysis - Cost breakdown and analysis
7. Network Visualization - Network graph visualization
8. Route Analysis - Route finding and analysis
9. Settings - Application settings

Legacy page modules (deprecated - use numbered pages instead):
"""

# Legacy imports maintained for backwards compatibility
# These are no longer used in the multi-page structure
from .planning_workflow import render_planning_workflow_page
from .production_schedule import render_production_schedule_page
from .distribution_plan import render_distribution_plan_page
from .cost_analysis import render_cost_analysis_page

__all__ = [
    'render_planning_workflow_page',
    'render_production_schedule_page',
    'render_distribution_plan_page',
    'render_cost_analysis_page',
]
